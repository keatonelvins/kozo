"""Marks: wedges, rules, the two-headed arrow, the asterisk."""
import math
from copy import deepcopy

from ufoLib2.objects import Component, Contour, Font

from .grid import Metrics
from .outline import Point, closed_path, polygons

TAPER = 0.5  # the width of a wedge at its foot, in widths at its head
WEDGED = ("quotesingle", "quotedbl", "exclam", "comma")
TURNED = {"quoteleft": "quoteright", "quotedblleft": "quotedblright"}  # each opening quote and the closing one it is

RULES = ("emdash", "underscore")

ARMS = 6
REACH = 0.31    # length of an asterisk's arm, centre to tip, in cap heights
SLENDER = 2.5   # an arm's length over the width of its tip
WAIST = 0.71    # the width an arm narrows to at the centre, of its tip


def wedges(font: Font, metrics: Metrics) -> None:
    """Quotes, comma and exclamation mark as wedges; the semicolon and the opening quotes made from them."""
    for name in WEDGED:
        glyph = font[name]
        glyph.contours[:] = [_wedge(contour) for contour in glyph.contours]

    upper_dot = max(font["colon"].contours, key=lambda contour: contour.points[0].y)
    font["semicolon"].contours[:] = [deepcopy(upper_dot), deepcopy(font["comma"].contours[0])]

    for opening, closing in TURNED.items():
        (raised,) = font[closing].components  # the low quote, lifted to its line
        heights = [y for outline in polygons(font, font[raised.baseGlyph]) for _, y in outline]
        rise = raised.transformation[5]
        font[opening].components[:] = [
            Component(raised.baseGlyph, (-1, 0, 0, -1, metrics.advance, min(heights) + max(heights) + rise))
        ]


def _wedge(stroke: Contour) -> Contour:
    """A wedge with the stroke's ink and lean. A contour that is no stroke is left alone."""
    (left, foot), (right, _), (head_left, head), (head_right, _) = sorted(
        ((point.x, point.y) for point in stroke.points), key=lambda point: point[::-1]
    )
    if head - foot < 2 * max(right - left, head_right - head_left):
        return stroke
    wide = (right - left + head_right - head_left) / (1 + TAPER)
    narrow = TAPER * wide
    low, high = (left + right) / 2, (head_left + head_right) / 2
    return closed_path((low - narrow / 2, foot), (low + narrow / 2, foot), (high + wide / 2, head), (high - wide / 2, head))


def rules(font: Font, metrics: Metrics) -> None:
    """The em dash and the underscore fill the cell, so a row of them is one line."""
    for name in RULES:
        (rule,) = font[name].contours
        for point in rule.points:
            point.x = 0 if point.x < metrics.advance / 2 else metrics.advance


def arrows(font: Font, metrics: Metrics) -> None:
    """The two-headed arrow, its heads moved in to the width of the one-headed ones."""
    middle = metrics.advance / 2
    reach, allowed = (
        max(x for outline in polygons(font, font[name]) for x, _ in outline) - middle
        for name in ("leftRightArrow", "rightArrow")
    )
    for contour in font["leftRightArrow"].contours:
        for point in contour.points:
            point.x += reach - allowed if point.x < middle else allowed - reach


def asterisk(font: Font, metrics: Metrics) -> None:
    """Six arms, two of them level, hanging under the cap height."""
    glyph = font["asterisk"]
    step = math.tau / ARMS
    reach = REACH * metrics.cap
    # About a stem wide at Regular; a heavier weight adds only half of what its stem gains.
    tip = (reach / SLENDER + metrics.stem) / 2
    # Neighbouring sides cross on the line halfway between two arms.
    taper = (1 - WAIST) * tip / 2 / reach
    notch = WAIST * tip / 2 / (math.sin(step / 2) - taper * math.cos(step / 2))

    def at(radius: float, angle: float, side: float = 0) -> Point:
        """The point `radius` out from the centre along `angle`, then `side` to the left."""
        cos, sin = math.cos(angle), math.sin(angle)
        return radius * cos - side * sin, radius * sin + side * cos

    star: list[Point] = []
    for arm in range(ARMS):
        angle = arm * step
        star += [at(reach, angle, -tip / 2), at(reach, angle, tip / 2), at(notch, angle + step / 2)]

    # Centred in the cell, its top corners one overshoot short of the cap height.
    dx = metrics.advance / 2
    dy = metrics.cap - metrics.overshoot - max(y for _, y in star)
    glyph.clearContours()
    glyph.contours.append(closed_path(*((x + dx, y + dy) for x, y in star)))
