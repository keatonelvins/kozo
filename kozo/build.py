"""Build Kozo from Paper Mono: uv run kozo [--style medium] [--out build]"""
import argparse
import copy
import functools
import tarfile
import time
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

import glyphsLib
import ufo2ft
import ufoLib2
from fontTools import subset
from fontTools.designspaceLib import InstanceDescriptor
from fontTools.misc.timeTools import timestampSinceEpoch
from fontTools.ttLib import TTFont, newTable
from fontTools.ttLib.tables.ttProgram import Program
from ufo2ft.instantiator import Instantiator

from . import config, dots, figures, grid, letters, marks
from .charset import add_stand_ins, keeps_codepoint, kept_glyphs, prune_features
from .outline import decompose, is_translation, parts_touch, remove_overlaps, snap

# In order: the wedges use the dots, and the G reads Paper Mono's u.
DRAWN = (
    dots.square_dots, marks.wedges, marks.rules, marks.arrows, letters.plain_r, letters.straight_y, letters.spurred_g,
    letters.plain_u, figures.o_for_zero, figures.swooped_one, figures.flat_three, figures.open_four, figures.even_six,
    letters.straight_q, marks.asterisk,
)

LICENSE = (
    "This Font Software is licensed under the SIL Open Font License, Version 1.1. "
    "This license is available with a FAQ at: https://openfontlicense.org"
)


def _source() -> Path:
    """Paper Mono's Glyphs source at the pinned commit, downloaded on the first build."""
    folder = config.ROOT / "paper-mono"
    if not folder.exists():
        url = f"https://github.com/paper-design/paper-mono/archive/{config.PAPER_MONO}.tar.gz"
        with urllib.request.urlopen(url) as response, tarfile.open(fileobj=response, mode="r|gz") as archive:
            archive.extractall(config.ROOT, filter="data")
        (config.ROOT / f"paper-mono-{config.PAPER_MONO}").rename(folder)
    return folder / "sources" / "PaperMono.glyphspackage"


@functools.cache
def _instantiator() -> Instantiator:
    designspace = glyphsLib.to_designspace(glyphsLib.GSFont(str(_source())), ufo_module=ufoLib2, minimal=True)
    return Instantiator.from_designspace(designspace, round_geometry=False)


@functools.cache
def _instance(weight: float) -> ufoLib2.Font:
    location = InstanceDescriptor(designLocation={"Weight": weight}, styleName=f"w{weight:g}")
    return _instantiator().generate_instance(location)


def paper_mono(weight: float) -> ufoLib2.Font:
    """A fresh copy of Paper Mono at `weight` on its design axis."""
    return copy.deepcopy(_instance(float(weight)))


def letter(style: config.Style):
    """Paper Mono at this style's weight, on the grid, with Kozo's letters drawn. Returns font, kept glyphs, metrics."""
    font = paper_mono(style.paper_weight)
    metrics = grid.measure(font)
    add_stand_ins(font)
    kept = sorted(kept_glyphs(font))
    font.features.text = prune_features(font.features.text, font.keys())
    for name in kept:
        remove_overlaps(font[name])
    metrics = grid.fit(font, kept, metrics)
    for redraw in DRAWN:
        redraw(font, metrics)
    return font, kept, metrics


def draw(style: config.Style):
    """Kozo at this style, ready to compile. Returns the font and its kept glyph names."""
    font, kept, _ = letter(style)
    # A composite stays one only if it places separate, unturned parts side by side.
    for name in kept:
        glyph = font[name]
        if glyph.components and (
            len(glyph.contours) or not all(map(is_translation, glyph.components)) or parts_touch(font, glyph)
        ):
            decompose(font, glyph)
        remove_overlaps(glyph)
    return font, kept


def name(font, style: config.Style) -> None:
    """Fill in the font info."""
    info = font.info
    major, minor = config.VERSION
    info.familyName = config.FAMILY
    info.styleName = style.name
    info.styleMapFamilyName = config.FAMILY if style.name == "Regular" else f"{config.FAMILY} {style.name}"
    info.postscriptFontName = style.filename
    info.openTypeOS2WeightClass = style.weight_class
    info.postscriptIsFixedPitch = True
    info.versionMajor, info.versionMinor = major, minor
    info.openTypeNameUniqueID = f"{major}.{minor:03d};{style.filename}"
    info.copyright = config.COPYRIGHT
    info.openTypeNameDesigner = f"{info.openTypeNameDesigner}, {config.DESIGNER}"  # after Paper Mono's
    info.openTypeNameDesignerURL = config.REPOSITORY
    info.openTypeNameManufacturer = config.DESIGNER
    info.openTypeNameManufacturerURL = config.REPOSITORY
    info.openTypeNameLicense = LICENSE
    info.openTypeNameLicenseURL = "https://openfontlicense.org"
    info.openTypeOS2VendorID = "NONE"


def compile_ttf(font, kept) -> TTFont:
    """Compile to TrueType, cut down to the characters among `kept` and what typing them needs."""
    for glyph_name in kept:
        snap(font[glyph_name])
    ttf = ufo2ft.compileTTF(font, removeOverlaps=False, dropImpliedOnCurves=True, flattenComponents=True)
    options = subset.Options(
        name_IDs=["*"],
        glyph_names=True,
        notdef_outline=True,
        passthrough_tables=True,
        recalc_average_width=True,
    )
    subsetter = subset.Subsetter(options)
    codes = [code for glyph_name in kept for code in font[glyph_name].unicodes if keeps_codepoint(code)]
    subsetter.populate(unicodes=codes)
    subsetter.subset(ttf)
    # Unhinted: Windows smooths at every size and keeps thin strokes whole.
    ttf["gasp"] = gasp = newTable("gasp")
    gasp.gaspRange = {0xFFFF: 0x000F}
    ttf["prep"] = prep = newTable("prep")
    prep.program = Program()
    prep.program.fromAssembly(["PUSHW[]", "511", "SCANCTRL[]", "PUSHB[]", "4", "SCANTYPE[]"])
    ttf["head"].flags |= 1 << 3  # sizes are whole pixels
    released = timestampSinceEpoch(datetime(*config.RELEASED, tzinfo=UTC).timestamp())
    ttf["head"].created = ttf["head"].modified = released
    ttf.recalcTimestamp = False
    return ttf


def build(style: config.Style, out: Path) -> None:
    """Write the style's .ttf and .woff2 into `out`."""
    font, kept = draw(style)
    name(font, style)
    ttf = compile_ttf(font, kept)
    out.mkdir(parents=True, exist_ok=True)
    for flavor in (None, "woff2"):
        ttf.flavor = flavor
        ttf.save(out / f"{style.filename}.{flavor or 'ttf'}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the Kozo fonts.")
    names = [style.name for style in config.STYLES]
    parser.add_argument("--style", action="append", type=str.title, choices=names, help="build only this style")
    parser.add_argument("--out", type=Path, default=config.FONTS, help="output folder (default: fonts/)")
    args = parser.parse_args()
    for style in config.STYLES:
        if args.style and style.name not in args.style:
            continue
        start = time.perf_counter()
        build(style, args.out)
        print(f"{style.filename}  {time.perf_counter() - start:.1f}s")


if __name__ == "__main__":
    main()
