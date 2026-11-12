"""One fact about each letter Kozo draws, at both weights, and what the built fonts promise."""
import io
import math

import pytest
from fontTools.ttLib import TTFont

from kozo import build, config
from kozo.charset import FEATURES, keeps_codepoint
from kozo.outline import polygons, runs


@pytest.fixture(scope="module", params=config.STYLES, ids=lambda style: style.name.lower())
def lettered(request):
    """Paper Mono at one weight, on the grid, with Kozo's letters drawn and nothing else done."""
    font, _, metrics = build.letter(request.param)
    return font, metrics


def corners(contour) -> list[tuple[float, float]]:
    return [(point.x, point.y) for point in contour.points if point.type is not None]


def level_edges(font, name: str, height: float) -> list[float]:
    """The lengths of the glyph's straight edges that lie along `height`."""
    lengths = []
    for contour in font[name].contours:
        points = corners(contour)
        for (x0, y0), (x1, y1) in zip(points, points[1:] + points[:1]):
            if abs(y0 - height) < 0.01 and abs(y1 - height) < 0.01:
                lengths.append(abs(x1 - x0))
    return lengths


def test_dots_are_squares_on_their_lines(lettered):
    font, metrics = lettered
    (period,) = font["period"].contours
    xs, ys = zip(*corners(period))
    assert len(period.points) == 4
    assert max(xs) - min(xs) == max(ys) - min(ys)
    assert min(ys) == 0
    upper, _ = sorted(font["colon"].contours, key=lambda contour: -contour.points[0].y)
    assert max(y for _, y in corners(upper)) == pytest.approx(metrics.xheight)
    (bullet,) = font["bullet"].contours
    bullet_xs, bullet_ys = zip(*corners(bullet))
    assert max(bullet_xs) - min(bullet_xs) == max(bullet_ys) - min(bullet_ys) == 2 * (max(xs) - min(xs))
    assert len(font["degree"].contours[0].points) > 4  # a ring stays round


def test_one_mark_one_size(lettered):
    font, _ = lettered

    def dot_side(name: str) -> float:
        """The side of the glyph's squares (they are all one size)."""
        sides = set()
        for contour in font[name].contours:
            xs, ys = zip(*corners(contour))
            if len(contour.points) == 4 and max(xs) - min(xs) == max(ys) - min(ys):
                sides.add(max(xs) - min(xs))
        (side,) = sides
        return side

    assert dot_side("exclam") == dot_side("question") < dot_side("period")  # a point under a stroke is the smaller
    assert dot_side("divide") == dot_side("dotaccentcomb")


def test_zero_is_the_capital_o(lettered):
    font, _ = lettered
    assert polygons(font, font["zero"]) == polygons(font, font["O"])


def test_i_dot_stands_on_its_stem(lettered):
    font, metrics = lettered
    left, right = runs(polygons(font, font["idotless"]), y=metrics.xheight / 2)[0]
    dot = font["dotaccentcomb"].contours[0]
    xs = [x for x, _ in corners(dot)]
    offset = font["i"].components[1].transformation[4]
    assert (min(xs) + max(xs)) / 2 + offset == pytest.approx((left + right) / 2, abs=0.01)


def test_r_is_a_stem_and_an_arm(lettered):
    font, metrics = lettered
    outline = polygons(font, font["r"])
    foot, head = runs(outline, y=1), runs(outline, y=metrics.xheight - 1)
    assert len(foot) == 1 and foot[0][1] - foot[0][0] == pytest.approx(metrics.stem, abs=1)  # no slab
    assert head[0][0] == pytest.approx(foot[0][0])  # no serif at the head
    end, n_side = (max(x for x, _ in polygons(font, font[name])[0]) for name in "rn")
    low, high = runs(outline, x=end - 1)[0]
    assert n_side < end < n_side + metrics.stem / 2  # the arm ends a little past n's right side
    assert high < metrics.xheight and high - low == pytest.approx(metrics.stem, abs=1)  # in a stem-tall cut that hangs


def test_one_hangs_its_flag_on_the_x_height(lettered):
    font, metrics = lettered
    assert max(level_edges(font, "one", metrics.xheight)) > metrics.stem


def test_three_has_a_flat_top(lettered):
    font, metrics = lettered
    top = max(y for outline in polygons(font, font["seven"]) for _, y in outline)
    assert max(level_edges(font, "three", top)) > 2 * metrics.stem


def test_four_is_open_at_the_top(lettered):
    font, metrics = lettered
    outline = polygons(font, font["four"])
    top = max(y for poly in outline for _, y in poly)
    (arm, stem), (bar,) = runs(outline, y=top - 1), runs(outline, y=metrics.cap / 3.5)
    assert arm[1] < stem[0]  # two strokes that do not meet
    assert arm[1] - arm[0] == pytest.approx(stem[1] - stem[0])
    assert bar[0] == arm[0] and bar[1] > stem[1]  # the bar runs through the stem
    assert bar[0] == pytest.approx(metrics.advance - bar[1])  # square in its cell


def test_quotes_comma_and_exclamation_are_wedges(lettered):
    font, _ = lettered
    marks = ("quotesingle", "quotedbl", "exclam", "comma", "semicolon")
    strokes = [sides(contour) for name in marks for contour in font[name].contours]
    strokes = [(foot, head) for foot, head in strokes if foot != head]  # a square is no stroke
    assert len(strokes) == 6
    for foot, head in strokes:
        assert foot == pytest.approx(0.5 * head)


def sides(contour) -> tuple[float, float]:
    """The lengths of a four-cornered contour's lower and upper sides."""
    low_left, low_right, high_left, high_right = sorted(corners(contour), key=lambda point: point[::-1])
    return low_right[0] - low_left[0], high_right[0] - high_left[0]


def ink_box(font, name: str) -> tuple[float, float, float, float]:
    """Left, bottom, right and top of a glyph's ink, components included."""
    xs, ys = zip(*(point for outline in polygons(font, font[name]) for point in outline))
    return min(xs), min(ys), max(xs), max(ys)


def test_marks_are_put_together_from_shared_parts(lettered):
    font, metrics = lettered
    upper_dot = max(font["colon"].contours, key=lambda contour: contour.points[0].y)
    assert list(map(corners, font["semicolon"].contours)) == [corners(upper_dot), corners(font["comma"].contours[0])]
    for opening, closing in (("quoteleft", "quoteright"), ("quotedblleft", "quotedblright")):
        left, bottom, right, top = ink_box(font, opening)
        closing_left, closing_bottom, closing_right, closing_top = ink_box(font, closing)
        assert (bottom, top) == pytest.approx((closing_bottom, closing_top))  # on one line
        assert (left, right) == pytest.approx((metrics.advance - closing_right, metrics.advance - closing_left))  # mirrored


def test_rules_fill_the_cell(lettered):
    font, metrics = lettered
    for name in ("emdash", "underscore"):
        left, _, right, _ = ink_box(font, name)
        assert (left, right) == (0, metrics.advance)


def test_two_headed_arrow_keeps_to_its_cell(lettered):
    font, _ = lettered
    left, _, right, _ = ink_box(font, "leftRightArrow")
    one_headed_left, _, one_headed_right, _ = ink_box(font, "rightArrow")
    assert (left, right) == pytest.approx((one_headed_left, one_headed_right))


def test_q_tail_is_a_straight_bar_through_the_bowl(lettered):
    font, metrics = lettered
    q = font["Q"]
    assert [component.baseGlyph for component in q.components] == ["O"]
    (tail,) = q.contours
    a, b, c, d = corners(tail)
    assert math.degrees(math.atan2(b[1] - c[1], c[0] - b[0])) == pytest.approx(40)
    assert math.dist(a, b) == pytest.approx(0.9 * metrics.cap_stem)
    bowl = polygons(font, font["O"])
    assert runs(bowl, y=a[1])[0][1] < a[0] < runs(bowl, y=a[1])[-1][0]  # starts in the white of the counter
    assert metrics.descender < min(y for _, y in (a, b, c, d)) < 0


def test_asterisk_is_raised_with_two_arms_level(lettered):
    font, metrics = lettered
    (star,) = font["asterisk"].contours
    points = corners(star)
    xs, ys = zip(*points)
    assert len(points) == 18
    assert max(ys) == pytest.approx(metrics.cap - metrics.overshoot)
    assert (min(xs) + max(xs)) / 2 == pytest.approx(config.CELL / 2)
    assert max(xs) - min(xs) > max(ys) - min(ys)  # the level arms reach furthest


def test_descenders_reach_their_line(lettered):
    font, metrics = lettered

    def lowest(name: str) -> tuple[float, float]:
        return min(((point.x, point.y) for contour in font[name].contours for point in contour.points), key=lambda p: p[1])

    assert metrics.descender == config.DESCENDER
    assert lowest("p")[1] == lowest("q")[1] == pytest.approx(config.DESCENDER)  # a stem stands on it
    under, foot = lowest("g")
    assert foot == lowest("jdotless")[1] == pytest.approx(config.DESCENDER - metrics.overshoot)  # a hook passes it
    (low, high), *_ = runs(polygons(font, font["g"]), x=under)
    assert high - low == pytest.approx(metrics.stem, rel=0.15)  # and is as heavy as it was: only the upright above it grew
    (below,) = (anchor.y for anchor in font["g"].anchors if anchor.name == "bottom")
    assert below == pytest.approx(foot)  # a mark below hangs from the new foot


def test_y_is_two_straight_strokes_that_meet_above_the_baseline(lettered):
    font, metrics = lettered
    (outline,) = font["y"].contours
    assert all(point.type == "line" for point in outline.points)  # no hook, no bend
    toe, heel, notch, crotch, *heads = sorted(corners(outline), key=lambda point: point[::-1])  # from the foot up
    assert len(heads) == 4  # and no other corner: the long stroke's outer side is one line from head to heel
    assert toe[1] == heel[1] == metrics.descender  # one level cut, on the line p stands on
    assert notch[1] > 0  # the short stroke lands above the baseline
    (ax, ay), (bx, by) = sorted(heads)[2], toe  # the long stroke's inner side, from its head to the toe,
    for x, y in (crotch, notch):  # passes through both corners of the join
        assert (x - ax) * (by - ay) == pytest.approx((y - ay) * (bx - ax))


def test_u_is_a_bowl_without_a_spur(lettered):
    font, metrics = lettered
    outline = polygons(font, font["u"])
    left, _, right, _ = ink_box(font, "u")
    ((start, end),) = runs(outline, y=0)  # one stretch of ink on the baseline: the bowl, and no foot beside it
    assert start + end == pytest.approx(left + right)
    for height in (metrics.xheight / 4, metrics.xheight / 2):  # and the two sides mirror each other
        (a, b), (c, d) = runs(outline, y=height)
        assert (a + d, b + c) == pytest.approx((left + right, left + right))


def test_g_stands_on_a_spur(lettered):
    font, metrics = lettered
    outline = polygons(font, font["G"])
    left, right = runs(outline, y=1)[-1]  # the ink furthest right on the baseline
    assert right - left == pytest.approx(metrics.cap_stem)
    assert level_edges(font, "G", 0) == [pytest.approx(metrics.cap_stem)]  # a square foot
    foot, head = runs(outline, x=(left + right) / 2)[0]  # the stem, from the baseline up
    bar_left, bar_right = runs(outline, y=head - 1)[-1]
    assert foot == 0 and bar_left < left and bar_right == pytest.approx(right)  # under the bar's right end


def test_six_and_nine_have_no_inlet(lettered):
    font, _ = lettered
    assert [component.baseGlyph for component in font["nine"].components] == ["six"]  # the 9 is the 6 turned round
    left, _, right, _ = ink_box(font, "six")
    assert left + right == pytest.approx(config.CELL)  # in the middle of the cell, so both are
    ring, _ = font["six"].contours
    points = list(ring.points)
    # Bowl and stem part where the ring's curve stops and the stem's straight side begins.
    following = points[1:] + points[:1]
    at = next(i for i, (point, after) in enumerate(zip(points, following)) if (point.type, after.type) == ("curve", "line"))
    notch = points[at]
    bowl, stem = points[at - 1], points[(at + 1) % len(points)]  # the way the bowl leaves it, and the stem
    spread = math.atan2(stem.y - notch.y, stem.x - notch.x) - math.atan2(bowl.y - notch.y, bowl.x - notch.x)
    assert math.degrees(spread) > 40  # at a wide angle
    xs = [point.x for point in points]
    _, (under, top), *_ = runs(polygons(font, font["six"]), x=(min(xs) + max(xs)) / 2)  # the top of the bowl
    assert top - notch.y < (top - under) / 4  # and the white between them stops high in its stroke


TYPED_PAGE = (
    "April is older now and has both hands on her windowsill. "
    "“She mustn’t mince it” — 17th, 1955; Mütter, naïve, façade, Łódź, Þór. "
    "0123456789 ← → ↑ ↓ * & @ ? ! § † © ™ … – —"
)


@pytest.fixture(scope="module", params=config.STYLES, ids=lambda style: style.filename)
def built(request) -> tuple[config.Style, TTFont]:
    style = request.param
    font, kept = build.draw(style)
    build.name(font, style)
    return style, build.compile_ttf(font, kept)


def test_one_cell_per_character(built):
    _, ttf = built
    advances = {advance for advance, _ in ttf["hmtx"].metrics.values()}
    assert advances <= {0, config.CELL}
    assert ttf["OS/2"].xAvgCharWidth == config.CELL
    assert ttf["post"].isFixedPitch


def test_sits_on_the_grid(built):
    _, ttf = built
    assert ttf["head"].unitsPerEm == 1000
    assert ttf["OS/2"].sxHeight == config.X_HEIGHT
    assert ttf["glyf"]["x"].yMax == config.X_HEIGHT
    assert ttf["glyf"]["x"].yMin == 0


def test_no_point_sits_on_its_neighbour(built):
    _, ttf = built
    glyf = ttf["glyf"]
    for name in ttf.getGlyphOrder():
        glyph = glyf[name]
        start = 0
        for end in glyph.endPtsOfContours if glyph.numberOfContours > 0 else ():
            points = [tuple(glyph.coordinates[index]) for index in range(start, end + 1)]
            assert all(a != b for a, b in zip(points, points[1:] + points[:1])), name
            start = end + 1


def test_builds_the_same_twice(built):
    style, ttf = built
    font, kept = build.draw(style)
    build.name(font, style)
    again = build.compile_ttf(font, kept)
    files = [io.BytesIO(), io.BytesIO()]
    ttf.save(files[0])
    again.save(files[1])
    assert files[0].getvalue() == files[1].getvalue()


def test_types_a_page(built):
    _, ttf = built
    cmap = ttf.getBestCmap()
    missing = {character for character in TYPED_PAGE if not character.isspace() and ord(character) not in cmap}
    assert not missing


def test_has_every_character_it_promises(built):
    """Everything in the kept ranges that Paper Mono draws at one cell is in the font."""
    _, ttf = built
    cmap = ttf.getBestCmap()
    source_font = build.paper_mono(86)
    cell = source_font["n"].width
    promised = {
        code
        for glyph in source_font
        for code in glyph.unicodes
        if keeps_codepoint(code) and glyph.width in (0, cell)
    }
    assert not {chr(code) for code in promised - set(cmap)}
    assert not {chr(code) for code in range(0x21, 0x7F) if code not in cmap}
    assert 0x2010 in cmap and 0x00B2 not in cmap  # a stand-in is typed, a small figure is not


def test_no_code_apparatus(built):
    _, ttf = built
    names = ttf.getGlyphOrder()
    assert not [name for name in names if "liga" in name or name.endswith((".zero", ".ss02", ".ss03", ".ss04", ".cv01"))]
    assert not [code for code in ttf.getBestCmap() if 0x2500 <= code <= 0x259F]
    features = {record.FeatureTag for record in ttf["GSUB"].table.FeatureList.FeatureRecord}
    assert features == set(FEATURES)


def test_names_its_style(built):
    style, ttf = built
    name = ttf["name"]
    assert name.getBestFamilyName() == config.FAMILY
    assert name.getBestSubFamilyName() == style.name
    assert ttf["OS/2"].usWeightClass == style.weight_class
    assert ttf["head"].macStyle == 0 and ttf["post"].italicAngle == 0
    assert "SIL Open Font License" in name.getDebugName(13)
    assert all(holder in name.getDebugName(0) for holder in ("Kozo", "Paper Design", "Vercel"))
    assert name.getDebugName(9).endswith(f", {config.DESIGNER}")  # after Paper Mono's designers
