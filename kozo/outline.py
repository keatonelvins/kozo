"""Outline helpers."""
from collections.abc import Iterator

from booleanOperations import union
from fontTools.misc.bezierTools import cubicPointAtT
from fontTools.misc.roundTools import otRound
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.pointPen import SegmentToPointPen
from fontTools.pens.recordingPen import DecomposingRecordingPen
from ufoLib2.objects import Contour
from ufoLib2.objects import Point as OutlinePoint

Point = tuple[float, float]
Curve = tuple[Point, Point, Point]


def is_curve(segment: Point | Curve) -> bool:
    return isinstance(segment[0], tuple)


def end_of(segment: Point | Curve) -> Point:
    return segment[-1] if is_curve(segment) else segment


def closed_path(*segments: Point | Curve) -> Contour:
    """A closed contour, fill on the left, from segment ends: `(x, y)` a line, `(handle, handle, (x, y))` a curve."""
    contour = Contour()
    for segment in segments:
        if is_curve(segment):
            contour.points.extend(OutlinePoint(x, y) for x, y in segment[:2])
        contour.points.append(OutlinePoint(*end_of(segment), "curve" if is_curve(segment) else "line"))
    return contour


def segments(contour: Contour) -> list[Point | Curve]:
    """A closed contour in the form `closed_path` takes, starting at its lowest point (the leftmost of several)."""
    points = list(contour.points)
    while points[-1].type is None:  # handles after the last point belong to the first segment
        points.insert(0, points.pop())
    path: list[Point | Curve] = []
    handles: list[Point] = []
    for point in points:
        if point.type is None:
            handles.append((point.x, point.y))
        else:
            path.append((*handles, (point.x, point.y)) if handles else (point.x, point.y))
            handles = []
    start = min(range(len(path)), key=lambda index: end_of(path[index])[::-1])
    return path[start:] + path[:start]


def is_translation(component) -> bool:
    xx, xy, yx, yy, _, _ = component.transformation
    return (xx, xy, yx, yy) == (1, 0, 0, 1)


def parts_touch(font, glyph) -> bool:
    """Whether any two components of a composite share ink (judged by their bounding boxes)."""
    boxes = []
    for component in glyph.components:
        pen = BoundsPen(font)
        component.draw(pen)
        if pen.bounds is None:
            continue
        left, bottom, right, top = pen.bounds
        if any(left < x1 and x0 < right and bottom < y1 and y0 < top for x0, y0, x1, y1 in boxes):
            return True
        boxes.append(pen.bounds)
    return False


def decompose(font, glyph) -> None:
    """Replace the glyph's components by their outlines."""
    recording = DecomposingRecordingPen(font)
    for component in glyph.components:
        component.draw(recording)
    glyph.components.clear()
    recording.replay(SegmentToPointPen(glyph.getPointPen()))


def remove_overlaps(glyph) -> None:
    """Merge the glyph's contours into one overlap-free outline."""
    contours = list(glyph.contours)
    if not contours:
        return
    glyph.clearContours()
    union(contours, glyph.getPointPen())


def snap(glyph) -> None:
    """Put every point on a whole unit, dropping a segment that closes up to nothing."""
    for contour in glyph.contours:
        points = contour.points
        for point in points:
            point.x, point.y = otRound(point.x), otRound(point.y)
        ends = [index for index, point in enumerate(points) if point.type is not None]
        dropped: set[int] = set()
        for previous, end in zip(ends[-1:] + ends[:-1], ends):
            handles = [(previous + 1 + step) % len(points) for step in range((end - previous - 1) % len(points))]
            if (points[end].x, points[end].y) == (points[previous].x, points[previous].y):
                dropped.update(handles, [end])
        if len(ends) - sum(index in dropped for index in ends) > 1:
            contour.points = [point for index, point in enumerate(points) if index not in dropped]


def polygons(font, glyph, steps: int = 12) -> list[list[Point]]:
    """The glyph's outline, components included, flattened to closed polylines."""
    recording = DecomposingRecordingPen(font)
    glyph.draw(recording)
    result: list[list[Point]] = []
    current: list[Point] = []
    for operator, points in recording.value:
        if operator == "moveTo":
            current = [points[0]]
        elif operator == "lineTo":
            current.append(points[0])
        elif operator == "curveTo":
            start = current[-1]
            current.extend(cubicPointAtT(start, *points, i / steps) for i in range(1, steps + 1))
        elif operator in ("closePath", "endPath"):
            result.append(current)
    return result


def _crossings(polys: list[list[Point]], *, x: float | None = None, y: float | None = None) -> Iterator[tuple[float, int]]:
    """Where the outline crosses the line x = const or y = const, with winding direction."""
    axis, level = (0, x) if x is not None else (1, y)
    for poly in polys:
        for a, b in zip(poly, poly[1:] + poly[:1]):
            if (a[axis] <= level) == (b[axis] <= level):
                continue
            t = (level - a[axis]) / (b[axis] - a[axis])
            yield a[1 - axis] + t * (b[1 - axis] - a[1 - axis]), 1 if b[axis] > a[axis] else -1


def runs(polys: list[list[Point]], *, x: float | None = None, y: float | None = None) -> list[tuple[float, float]]:
    """The stretches of ink along a vertical (x=) or horizontal (y=) line."""
    inked: list[tuple[float, float]] = []
    winding, start = 0, 0.0
    for position, direction in sorted(_crossings(polys, x=x, y=y)):
        if winding == 0:
            start = position
        winding += direction
        if winding == 0:
            inked.append((start, position))
    return inked
