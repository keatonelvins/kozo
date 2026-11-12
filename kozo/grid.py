"""The grid: a 600-unit cell, a 500-unit x-height, and longer descenders."""
import dataclasses

from . import config
from .outline import polygons, runs

# The letters whose descenders grow (y is drawn in letters.py).
DESCENDING = ("g", "jdotless", "ij", "p", "q", "thorn", "eng", "Eng", "micro")


@dataclasses.dataclass(frozen=True)
class Metrics:
    advance: float     # the cell
    xheight: float
    cap: float
    ascender: float
    descender: float
    overshoot: float   # how far rounds pass the baseline and the x-height
    stem: float        # of n
    cap_stem: float    # of H


def measure(font) -> Metrics:
    """Read the lines, the overshoot and the stems off a font as it stands."""
    info = font.info
    return Metrics(
        advance=font["n"].width,
        xheight=info.xHeight,
        cap=info.capHeight,
        ascender=info.ascender,
        descender=info.descender,
        overshoot=-min(y for outline in polygons(font, font["o"]) for _, y in outline),
        stem=_first_stem(font, "n", info.xHeight),
        cap_stem=_first_stem(font, "H", info.capHeight),
    )


def _first_stem(font, name: str, height: float) -> float:
    """How wide the leftmost stroke of a glyph is, a quarter of the way up `height`."""
    left, right = runs(polygons(font, font[name]), y=height / 4)[0]
    return right - left


def fit(font, kept, metrics: Metrics) -> Metrics:
    """Scale the kept glyphs onto the grid, centred in the cell, and lengthen the descenders: the new metrics."""
    scale = config.X_HEIGHT / metrics.xheight
    shift = (config.CELL - metrics.advance * scale) / 2
    for name in kept:
        glyph = font[name]
        for contour in glyph.contours:
            for point in contour.points:
                point.x, point.y = point.x * scale + shift, point.y * scale
        for anchor in glyph.anchors:
            anchor.x, anchor.y = anchor.x * scale + shift, anchor.y * scale
        # A turned or mirrored part carries the shift round with it.
        for component in glyph.components:
            xx, xy, yx, yy, dx, dy = component.transformation
            component.transformation = (xx, xy, yx, yy, dx * scale + shift * (1 - xx), dy * scale - shift * xy)
        if glyph.width:
            glyph.width = config.CELL
    info = font.info
    for field in ("xHeight", "capHeight", "ascender", "descender"):
        setattr(info, field, round(getattr(info, field) * scale))
    metrics = dataclasses.replace(
        metrics,
        advance=config.CELL,
        **{
            field.name: getattr(metrics, field.name) * scale
            for field in dataclasses.fields(metrics)
            if field.name != "advance"
        },
    )
    return _lengthen(font, metrics)


def _lengthen(font, metrics: Metrics) -> Metrics:
    """Let the descenders down: everything below the foot of the straight sides moves as one piece."""
    drop = config.DESCENDER - metrics.descender
    for name in DESCENDING:
        glyph = font[name]
        cut = _cut(glyph)
        for contour in glyph.contours:
            for point in contour.points:
                if point.y <= cut:
                    point.y += drop
        # A mark below hangs from the foot, on the letter and on its accented forms.
        for marked in font:
            if marked is glyph or any(component.baseGlyph == name for component in marked.components):
                for anchor in marked.anchors:
                    if anchor.y <= cut:
                        anchor.y += drop
    font.info.descender = config.DESCENDER
    return dataclasses.replace(metrics, descender=config.DESCENDER)


def _cut(glyph) -> float:
    """The lowest height from which the outline hangs by upright straight sides alone."""
    for cut in sorted({point.y for contour in glyph.contours for point in contour.points}):
        if all(
            a.type and b.type == "line" and abs(a.x - b.x) < 0.01
            for contour in glyph.contours
            for a, b in zip(contour.points, contour.points[1:] + contour.points[:1])
            if (a.y <= cut) != (b.y <= cut)
        ):
            return cut
    raise ValueError(f"{glyph.name} has no upright sides to lengthen")
