"""Letters: r, u, y, G, Q."""
import math

from fontTools.misc.bezierTools import splitCubic
from ufoLib2.objects import Font

from .grid import Metrics
from .outline import Point, closed_path, polygons, segments

R_STEM_AT = 0.25  # where the left side of r's stem stands, in cells

Y_JOIN = 0.1  # where the middles of y's two strokes meet, in x-heights above the baseline
Y_FOOT = 0.9  # how wide y's long stroke is at its foot, in widths at its head

Q_ANGLE = math.radians(40)  # how steeply Q's tail falls to the right
Q_WEIGHT = 0.9              # its thickness, in capital stems
Q_REACH = 0.035             # how far left of the bowl's centre it starts, in cells
Q_DEPTH = 0.32              # how far below the baseline it ends, of the descender


def plain_r(font: Font, metrics: Metrics) -> None:
    """One stem and an arm made from the arch of n: no foot, no serif."""
    glyph = font["r"]
    end = max(x for outline in polygons(font, glyph) for x, _ in outline)  # where Paper Mono's arm ends
    left = R_STEM_AT * metrics.advance
    right = left + metrics.stem

    # n, from the foot of its first stem: up inside its arch, down inside its second stem, back over the outside.
    _, (n_stem, _), spring, inside, _, _, _, side, far, near, head, _ = segments(font["n"].contours[0])
    crest, under_crest = far[-1], inside[-1]

    # The back of the arm is n's, cut at `top` and opened out until the cut falls on the arm's end.
    top = 2 * metrics.xheight - crest[1]
    _, back = splitCubic(side, *far, top, True)
    open_out = (end - right) / (back[0][0] - n_stem)

    def over(point: Point) -> Point:
        """A point of n's back, where it lies on r's."""
        return right + (point[0] - n_stem) * open_out, point[1]

    # The underside is the inside of n's shoulder, enlarged until its crest stands under the back's.
    enlarged = (over(crest)[0] - right) / (under_crest[0] - n_stem)

    def rising(point: Point) -> Point:
        """A point of n's inner shoulder, where it lies on r's underside."""
        return right + (point[0] - n_stem) * enlarged, under_crest[1] - (under_crest[1] - point[1]) * enlarged

    # Past the crest the underside is the back again, falling far enough to end one stem below it.
    further = (under_crest[1] - (top - metrics.stem)) / (crest[1] - top)

    def falling(point: Point) -> Point:
        """A point of n's back past its crest, where it lies on r's underside."""
        x, y = over(point)
        return x, under_crest[1] - (crest[1] - y) * further

    glyph.clearContours()
    glyph.contours.append(
        closed_path(
            (left, 0),
            (right, 0),
            rising(spring),
            tuple(map(rising, inside)),
            tuple(map(falling, back[2::-1])),
            (end, top),
            tuple(map(over, back[1:])),
            tuple(map(over, near)),
            over(head),
            (left, metrics.xheight),
        )
    )

    # An accent above sits over the middle of the letter; one below hangs from the stem.
    _seat(font, "r", {"top": (left + end) / 2, "bottom": (left + right) / 2})


def _seat(font: Font, name: str, seats: dict[str, float]) -> None:
    """Move a letter's anchors sideways to `seats`, and the accents of its accented forms with them."""
    shifts = {}
    for anchor in font[name].anchors:
        if anchor.name in seats:
            shifts[anchor.name] = seats[anchor.name] - anchor.x
            anchor.x = seats[anchor.name]
    for accented in font:
        if not any(component.baseGlyph == name for component in accented.components):
            continue
        for anchor in accented.anchors:
            anchor.x += shifts.get(anchor.name, 0)
        for component in accented.components:
            if component.baseGlyph != name:
                # An accent hangs from the anchor that matches its own: `_top` sits on `top`.
                seat = next(anchor.name[1:] for anchor in font[component.baseGlyph].anchors if anchor.name[0] == "_")
                *matrix, dx, dy = component.transformation
                component.transformation = (*matrix, dx + shifts.get(seat, 0), dy)


def plain_u(font: Font, metrics: Metrics) -> None:
    """A bowl with no spur: the left half of Paper Mono's, widened to the middle and mirrored, like its U."""
    glyph = font["u"]
    # Paper Mono's u, from the bottom of its bowl: round to the spur and up the right stem,
    # down the inside and round the counter, then the left stem from inside to outside.
    outside, _, _, (right, _), _, _, _, (*_, floor), inside, head_inside, head, side = segments(glyph.contours[0])
    middle = (side[0] + right) / 2

    def widened(point: Point, stem: float, turn: float) -> Point:
        """A point of the left half, stretched sideways so the curve that turned at x = `turn` turns in the middle."""
        return stem + (point[0] - stem) * (middle - stem) / (turn - stem), point[1]

    def mirrored(point: Point) -> Point:
        return 2 * middle - point[0], point[1]

    out_leaving, out_arriving, bottom = (widened(point, side[0], outside[-1][0]) for point in outside)
    in_leaving, in_arriving, shoulder = (widened(point, inside[-1][0], floor[0]) for point in (inside[0], inside[1], inside[-1]))
    floor = (middle, floor[1])

    glyph.clearContours()
    glyph.contours.append(
        closed_path(
            (out_leaving, out_arriving, bottom),
            (mirrored(out_arriving), mirrored(out_leaving), mirrored(side)),
            mirrored(head),
            mirrored(head_inside),
            mirrored(shoulder),
            (mirrored(in_arriving), mirrored(in_leaving), floor),
            (in_leaving, in_arriving, shoulder),
            head_inside,
            head,
            side,
        )
    )

    # A mark below hangs from the middle, and the ogonek from where it hangs on U.
    capital = [x for outline in polygons(font, font["U"]) for x, _ in outline]
    (hook,) = (anchor.x for anchor in font["U"].anchors if anchor.name == "ogonek")
    reach = (hook - (min(capital) + max(capital)) / 2) / (max(capital) - min(capital))
    _seat(font, "u", {"bottom": middle, "ogonek": middle + reach * (right - side[0])})


def straight_y(font: Font, metrics: Metrics) -> None:
    """Two straight strokes that meet above the baseline."""
    glyph = font["y"]
    # Paper Mono's y, from the lowest point of its hook: only the heads of its arms are kept.
    _, _, head, head_inside, _, arm_inside, arm, *_ = segments(glyph.contours[0])
    middle = (arm[0] + head[0]) / 2
    top, low, join = head[1], metrics.descender, Y_JOIN * metrics.xheight

    # The long stroke runs from its head through the join to the descender line.
    lean = ((head[0] + head_inside[0]) / 2 - middle) / (top - join)  # sideways for each unit down
    centre = middle - lean * (join - low)
    width = Y_FOOT * (head[0] - head_inside[0])
    toe, heel = (centre - width / 2, low), (centre + width / 2, low)

    # Each side of the short stroke runs down from its head until it meets the long one.
    crotch = _crossing(head_inside, toe, arm_inside, _mirrored(arm_inside, head_inside, toe))
    notch = _crossing(head_inside, toe, arm, _mirrored(arm, head, heel))

    glyph.clearContours()
    glyph.contours.append(closed_path(toe, heel, head, head_inside, crotch, arm_inside, arm, notch))

    # A mark below hangs under the foot, on y and on the accented y's.
    for marked in font:
        if marked is glyph or any(component.baseGlyph == "y" for component in marked.components):
            for anchor in marked.anchors:
                if anchor.name == "bottom":
                    anchor.x, anchor.y = centre, low


def _mirrored(start: Point, other_start: Point, other_end: Point) -> Point:
    """A second point on the line from `start` that leans as the other line does, the other way."""
    return start[0] - (other_end[0] - other_start[0]), start[1] + (other_end[1] - other_start[1])


def _crossing(a: Point, b: Point, c: Point, d: Point) -> Point:
    """Where the line through a and b crosses the line through c and d."""
    (ax, ay), (bx, by), (cx, cy), (dx, dy) = a, b, c, d
    along = ((cx - ax) * (dy - cy) - (cy - ay) * (dx - cx)) / ((bx - ax) * (dy - cy) - (by - ay) * (dx - cx))
    return ax + along * (bx - ax), ay + along * (by - ay)


def spurred_g(font: Font, metrics: Metrics) -> None:
    """The bowl runs into a stem that stands on the baseline as a spur."""
    glyph = font["G"]
    # Paper Mono's G, from the bottom of its bowl: up the outside to the bar, round it, down the inside, over the top.
    back, outside, (right, top), bar_top, bar_foot, (wall, under), inside, *rest = segments(glyph.contours[0])
    bottom, floor = back[-1], inside[-1]
    left = right - metrics.cap_stem

    # Paper Mono's u, from the bottom of its bowl: the outside ends in the crotch at the stem.
    _, (_, _, (_, crotch)), *_ = segments(font["u"].contours[0])

    # The outside of G's bowl as far up as that, drawn in to end on the stem's side.
    rise, _ = splitCubic(bottom, *outside, crotch, True)
    leaving, arriving, _ = _narrowed(rise[1:], bottom, rise[-1][0], left)

    glyph.clearContours()
    glyph.contours.append(
        closed_path(
            back,
            (leaving, arriving, (left, crotch)),
            (left, 0),
            (right, 0),
            (right, top),
            bar_top,
            bar_foot,
            (left, under),
            # Paper Mono's bowl is a hair lighter than a capital stem where it leaves the bar.
            _narrowed(inside, floor, wall, left),
            *rest,
        )
    )


def _narrowed(curve: tuple[Point, ...], fixed: Point, side: float, to: float) -> tuple[Point, ...]:
    """A curve squeezed sideways towards its end `fixed`, until what stood at x = `side` stands at `to`."""
    squeeze = (to - fixed[0]) / (side - fixed[0])
    return tuple((fixed[0] + (x - fixed[0]) * squeeze, y) for x, y in curve)


def straight_q(font: Font, metrics: Metrics) -> None:
    """A straight tail from inside the bowl, cut square at both ends."""
    q = font["Q"]
    xs = [x for outline in polygons(font, font["O"]) for x, _ in outline]
    centre, right = (min(xs) + max(xs)) / 2, max(xs)
    thickness = Q_WEIGHT * metrics.cap_stem
    half_x, half_y = math.sin(Q_ANGLE) * thickness / 2, math.cos(Q_ANGLE) * thickness / 2

    # The centre line ends under the bowl's right edge, high enough to put the lower corner at Q_DEPTH.
    outer_x, outer_y = right, Q_DEPTH * metrics.descender + half_y
    inner_x = centre - Q_REACH * metrics.advance
    inner_y = outer_y + math.tan(Q_ANGLE) * (outer_x - inner_x)

    q.clearContours()
    q.contours.append(
        closed_path(
            (inner_x + half_x, inner_y + half_y),
            (inner_x - half_x, inner_y - half_y),
            (outer_x - half_x, outer_y - half_y),
            (outer_x + half_x, outer_y + half_y),
        )
    )

    # On Q the ogonek hangs from the foot of the bowl.
    for anchor in q.anchors:
        if anchor.name == "ogonek":
            anchor.x = centre
