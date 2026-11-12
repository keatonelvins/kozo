"""Figures: 0, 1, 3, 4, 6, 9."""
import math

from fontTools.misc.bezierTools import calcCubicBounds, curveLineIntersections, splitCubicAtT
from ufoLib2.objects import Component, Font

from .grid import Metrics
from .outline import Curve, Point, closed_path, end_of, is_curve, polygons, runs, segments


def o_for_zero(font: Font, metrics: Metrics) -> None:
    """The 0 is the capital O."""
    zero = font["zero"]
    zero.clearContours()
    zero.components.append(Component("O"))


def swooped_one(font: Font, metrics: Metrics) -> None:
    """The flag hangs level on the x-height and sweeps into the stem by n's shoulder, turned over."""
    glyph, low = font["one"], metrics.xheight
    # The inside of n's shoulder, measured from where it leaves the stem.
    n = segments(font["n"].contours[0])
    index = next(index for index, segment in enumerate(n) if is_curve(segment))
    x, y = n[index - 1]
    shoulder = tuple((px - x, py - y) for px, py in n[index])

    path = segments(glyph.contours[0])
    # Paper Mono's 1, from its stem's top right: the stem's top, the flag's tip above and below, the join.
    start = max(range(len(path)), key=lambda index: path[index][::-1])
    corner, top, tip, under, join, *rest = path[start:] + path[:start]

    # The diagonal flag's weight, measured square to the stroke.
    weight = (tip[1] - under[1]) * (top[0] - tip[0]) / math.dist(top, tip)
    # The shoulder comes down from the top of the stem and levels out at the tip's upper edge.
    scale = (top[1] - low - weight) / shoulder[-1][1]
    top = (join[0], top[1])  # on the stem's left side, so the stem is whole above the flag
    sweep = tuple((top[0] - scale * x, top[1] - scale * y) for x, y in shoulder)

    glyph.contours[0] = closed_path(corner, top, sweep, (tip[0], low + weight), (tip[0], low), (join[0], low), *rest)


def flat_three(font: Font, metrics: Metrics) -> None:
    """The lower bowl under the top of the 7."""
    glyph = font["three"]
    # Paper Mono's 7, from the foot of its diagonal round to the crotch under its bar.
    _, _, (right, shoulder), (_, top), _, (_, under), _ = segments(font["seven"].contours[0])
    weight = top - under
    left = runs(polygons(font, glyph), y=under)[0][0]  # where the round top passes the bar's underside

    # Paper Mono's 3, from the bottom of its bowl. Its one upright straight is the cut at the waist;
    # the lower bowl runs from the foot of that cut, round the terminal, back to the right side.
    path = segments(glyph.contours[0])
    ends = [end_of(segment) for segment in path]
    cut = next(
        index
        for index, (x, y) in enumerate(ends)
        if not is_curve(path[index]) and abs(x - ends[index - 1][0]) < abs(y - ends[index - 1][1])
    )
    bottom, side, waist, foot = ends[0], ends[1], ends[cut - 1], ends[cut]

    # The bowl's upper right, hidden in Paper Mono: its lower right turned over.
    leaving, arriving, _ = path[1]
    fit = (waist[1] - side[1]) / (side[1] - bottom[1])
    over = tuple((x, side[1] + (side[1] - y) * fit) for x, y in (arriving, leaving, bottom))

    # The diagonal's upper edge runs into the corner of the cut; its lower edge ends inside the bowl's stroke.
    run, rise = right - waist[0], shoulder - waist[1]
    slope = math.tan(math.atan2(rise, run) + math.asin(weight / math.hypot(run, rise)))
    depth = (waist[1] - foot[1]) / 2

    glyph.clearContours()
    glyph.contours.append(closed_path(*path[cut:], *path[:2], over, waist))
    glyph.contours.append(
        closed_path(
            (right, shoulder),
            (right, top),
            (left, top),
            (left, under),
            (waist[0] + (under - waist[1]) / slope, under),
            waist,
            (right - (rise + depth) / slope, waist[1] - depth),
        )
    )


def open_four(font: Font, metrics: Metrics) -> None:
    """An upright left stroke that never meets the stem, and a bar through the stem."""
    four = font["four"]
    # Paper Mono's 4 is all straights.
    corners = [end_of(segment) for segment in segments(four.contours[0])]
    foot_left, foot_right = corners[0], corners[1]
    reach = max(x for x, _ in corners)
    bar_bottom, bar_top = sorted(y for x, y in corners if x == reach)
    top = max(y for _, y in corners)
    left = metrics.advance - reach  # as far in from the left as the bar's end is from the right
    weight = foot_right[0] - foot_left[0]

    four.clearContours()
    four.contours.append(closed_path(foot_left, foot_right, (foot_right[0], top), (foot_left[0], top)))
    four.contours.append(
        closed_path(
            (left, bar_bottom),
            (reach, bar_bottom),
            (reach, bar_top),
            (left + weight, bar_top),
            (left + weight, top),
            (left, top),
        )
    )


def even_six(font: Font, metrics: Metrics) -> None:
    """An even ring with a straight stem leaning on it. The 9 is the 6 turned round."""
    glyph = font["six"]
    outside, counter = sorted(glyph.contours, key=lambda contour: min(point.y for point in contour.points))
    # Paper Mono's 6, from the bottom of its bowl: up the lower right quarter, over the top into the join,
    # up the stem's right side, across its head, down its left side and by the sweep back into the bowl.
    back, rise, over, *join, shoulder, head, neck, sweep = segments(outside)
    (_, low), (right, level), (_, high), (left, _) = (end_of(segment) for segment in (back, rise, over, sweep))
    middle = (left + right) / 2

    # The ring: the lower right quarter four times round the middle, with the counter centred in it.
    south, east, north, west = (middle, low), (right, level), (middle, high), (left, level)
    quarter = (end_of(back), *rise)
    to_east, to_west = _fitted(quarter, south, east), _fitted(quarter, north, west)
    to_north, to_south = _fitted(quarter[::-1], east, north), _fitted(quarter[::-1], west, south)
    xs = [point.x for point in counter.points]
    for point in counter.points:
        point.x += middle - (min(xs) + max(xs)) / 2

    lean = (head[0] - neck[0]) / (head[1] - neck[1])  # of the stem's left side: sideways for each unit up

    def across(point: Point) -> float:
        """How far right a point stands of the line through the origin that leans as the stem's left side does."""
        return point[0] - lean * point[1]

    # The stem steps right until its left side touches the ring.
    upper_left = (north, *to_west)
    touching = calcCubicBounds(*((across(point), point[1]) for point in upper_left))[0]
    step = touching - across(head)
    foot, shoulder, head = ((x + step, y) for x, y in (end_of(join[-1]), shoulder, head))

    # Its right side lands on the top of the ring, and the ring stops there.
    landing = min(curveLineIntersections(upper_left, (shoulder, foot)), key=lambda crossing: crossing.t1)
    crown, _ = splitCubicAtT(*upper_left, landing.t1)

    # Its left side runs into the ring's leftmost point by Paper Mono's sweep, scaled down.
    end = end_of(sweep)
    size = (touching - across(west)) / (across(neck) - across(end))
    start, leaving, arriving, _ = (
        (west[0] + (x - end[0]) * size, west[1] + (y - end[1]) * size) for x, y in (neck, *sweep)
    )
    # Leave the stem along its line (Paper Mono's sweep is a fraction of a degree off).
    leaving = (start[0] - lean * (start[1] - leaving[1]), leaving[1])

    glyph.clearContours()
    glyph.contours.append(
        closed_path(to_south, to_east, to_north, crown[1:], shoulder, head, start, (leaving, arriving, west))
    )
    glyph.contours.append(counter)
    for contour in glyph.contours:  # the ring stands in the middle of the cell, so the 9 does too
        for point in contour.points:
            point.x += metrics.advance / 2 - middle


def _fitted(quarter: tuple[Point, ...], start: Point, end: Point) -> Curve:
    """A quarter of a round moved, stretched and turned over as needed to run from `start` to `end`."""
    (x0, y0), (x1, y1) = quarter[0], quarter[-1]
    wider, taller = (end[0] - start[0]) / (x1 - x0), (end[1] - start[1]) / (y1 - y0)
    return tuple((start[0] + (x - x0) * wider, start[1] + (y - y0) * taller) for x, y in quarter[1:])
