"""Square dots, each with the ink of the round dot it replaces, flat on its line and centred on its stem."""
import math

from ufoLib2.objects import Component, Contour, Font, Glyph

from .grid import Metrics
from .outline import Point, closed_path, is_translation, polygons, runs

# The outlines that carry round dots. Every other dotted glyph is a composite of these.
DOTTED = (
    "period", "colon", "ellipsis", "exclam", "question", "questiondown", "divide",
    "dotaccentcomb", "dotaccentcomb.case", "dieresiscomb", "dieresiscomb.case", "ij",
)

# One mark, one size: the point of ? is the point of !, the dots of ÷ are the dot of i.
KIN = {"question": "exclam", "questiondown": "exclam", "divide": "dotaccentcomb"}

BULLET = 2  # the side of the bullet, in sides of the period

# The dots that stand on a stem.
ON_STEM = {"i": "idotless", "j": "jdotless"}
LIGATURES = ("ij",)


def square_dots(font: Font, metrics: Metrics) -> None:
    sides = {name: _side(font, font[name]) for name in DOTTED}
    sides.update({name: sides[kin] for name, kin in KIN.items()})
    rises = {name: _square_dots(font, font[name], sides[name], metrics) for name in DOTTED}
    for glyph in font:
        for component in glyph.components:
            if component.baseGlyph in rises and is_translation(component):
                _follow(glyph, component, *rises[component.baseGlyph])
    for dotted, dotless in ON_STEM.items():
        _centre_marks(font, font[dotted], font[dotless], metrics)
    for name in LIGATURES:
        _centre_dots(font, font[name], metrics)
    (disc,) = polygons(font, font["bullet"])
    font["bullet"].contours[0] = _square(disc, BULLET * sides["period"], metrics)


def _round_dots(font: Font, glyph: Glyph) -> dict[int, list[Point]]:
    """The glyph's dots, by contour index: the contours drawn without a straight line."""
    return {
        index: outline
        for index, (contour, outline) in enumerate(zip(glyph.contours, polygons(font, glyph)))
        if all(point.type != "line" for point in contour.points)
    }


def _side(font: Font, glyph: Glyph) -> int:
    """One side for all the dots of a glyph, from the ink they hold, in whole units."""
    dots = _round_dots(font, glyph)
    return round(math.sqrt(sum(map(_area, dots.values())) / len(dots)))


def _square_dots(font: Font, glyph: Glyph, side: int, metrics: Metrics) -> tuple[float, float]:
    """Square the glyph's round dots. Returns how far its middle and its top rose."""
    low, high = _extent(font, glyph)
    for index, outline in _round_dots(font, glyph).items():
        glyph.contours[index] = _square(outline, side, metrics)
    new_low, new_high = _extent(font, glyph)
    _move_top_anchor(glyph, dy=new_high - high)
    return (new_low + new_high - low - high) / 2, new_high - high


def _square(dot: list[Point], side: float, metrics: Metrics) -> Contour:
    """A square where a round dot was, the dot given as its flattened outline."""
    xs, ys = zip(*dot)
    x = (min(xs) + max(xs) - side) / 2
    y = (min(ys) + max(ys) - side) / 2
    if _drawn_to(min(ys), 0, metrics):
        y = 0
    for line in (metrics.xheight, metrics.ascender):
        if _drawn_to(max(ys), line, metrics):
            y = line - side
    return closed_path((x, y), (x + side, y), (x + side, y + side), (x, y + side))


def _drawn_to(edge: float, line: float, metrics: Metrics) -> bool:
    """Whether a round dot's edge was meant for this line: within an overshoot of it."""
    return abs(edge - line) <= metrics.overshoot + 0.5


def _follow(glyph: Glyph, component: Component, middle: float, top: float) -> None:
    """Keep a composite true to a dot whose middle and top have risen: a floating dot keeps its centre."""
    *matrix, dx, dy = component.transformation
    if dy:
        component.transformation = (*matrix, dx, dy - middle)
        top -= middle
    _move_top_anchor(glyph, dy=top)


def _centre_marks(font: Font, dotted: Glyph, dotless: Glyph, metrics: Metrics) -> None:
    """Stand the dot of i or j on the middle of its stem, and the other accents with it."""
    dot = [x for outline in polygons(font, dotted) for x, y in outline if y > metrics.xheight + metrics.overshoot]
    shift = _off_stem(font, dotless, dot, metrics)
    for glyph in font:
        if glyph is dotless or any(component.baseGlyph == dotless.name for component in glyph.components):
            for component in glyph.components:
                if any(anchor.name == "_top" for anchor in font[component.baseGlyph].anchors):
                    *matrix, dx, dy = component.transformation
                    component.transformation = (*matrix, dx + shift, dy)
            _move_top_anchor(glyph, dx=shift)


def _centre_dots(font: Font, ligature: Glyph, metrics: Metrics) -> None:
    """Stand each dot a ligature draws on the middle of the stem under it."""
    for contour in ligature.contours:
        if all(point.y > metrics.xheight for point in contour.points):
            shift = _off_stem(font, ligature, [point.x for point in contour.points], metrics)
            for point in contour.points:
                point.x += shift


def _off_stem(font: Font, glyph: Glyph, dot: list[float], metrics: Metrics) -> float:
    """How far right of a dot, given by its x coordinates, the middle of the nearest stem lies."""
    middle = (min(dot) + max(dot)) / 2
    stems = [(left + right) / 2 for left, right in runs(polygons(font, glyph), y=metrics.xheight / 2)]
    return min(stems, key=lambda stem: abs(stem - middle)) - middle


def _move_top_anchor(glyph: Glyph, dx: float = 0, dy: float = 0) -> None:
    for anchor in glyph.anchors:
        if anchor.name == "top":
            anchor.x, anchor.y = anchor.x + dx, anchor.y + dy


def _area(outline: list[Point]) -> float:
    return sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(outline, outline[1:] + outline[:1])) / 2


def _extent(font: Font, glyph: Glyph) -> tuple[float, float]:
    """The glyph's lowest and highest point."""
    ys = [y for outline in polygons(font, glyph) for _, y in outline]
    return min(ys), max(ys)
