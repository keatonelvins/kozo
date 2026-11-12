"""What Kozo types, and what that keeps of Paper Mono's glyphs and features."""
from io import StringIO

from fontTools.feaLib import ast
from fontTools.feaLib.parser import Parser

CHARACTERS = (
    range(0x0020, 0x007F),  # ASCII
    range(0x00A0, 0x0180),  # Latin-1 and Latin Extended-A
    (0x0218, 0x0219, 0x021A, 0x021B, 0x0237, 0x03BC, 0x1E9E),  # Ș ș Ț ț ȷ μ ẞ
    range(0x02C6, 0x02DE),  # accents standing alone
    range(0x0300, 0x0370),  # accents that combine
    (0x2013, 0x2014, 0x2018, 0x2019, 0x201A, 0x201C, 0x201D, 0x201E),  # – — ‘ ’ ‚ “ ” „
    (0x2020, 0x2021, 0x2022, 0x2026, 0x2030, 0x2032, 0x2033, 0x2039, 0x203A),  # † ‡ • … ‰ ′ ″ ‹ ›
    (0x20AC, 0x2122, 0x2212, 0x2248, 0x2260, 0x2264, 0x2265),  # € ™ − ≈ ≠ ≤ ≥
    range(0x2190, 0x219A),  # ← ↑ → ↓ ↔ ↕ ↖ ↗ ↘ ↙
)
SMALL_FIGURES = (0x00B2, 0x00B3, 0x00B9, 0x00BC, 0x00BD, 0x00BE)  # ² ³ ¹ ¼ ½ ¾, left out

# Characters Paper Mono lacks, and the glyph each is typed with, so no line leaves the grid.
STAND_INS = {
    "space": (*range(0x2000, 0x200B), 0x202F, 0x205F),
    "hyphen": (0x2010, 0x2011),
}

FEATURES = ("ccmp", "locl")  # accents that compose, and the forms a language asks for


def keeps_codepoint(code: int) -> bool:
    if code in SMALL_FIGURES:
        return False
    return any(code in characters for characters in (*CHARACTERS, *STAND_INS.values()))


def kept_glyphs(font) -> set[str]:
    """The glyphs Kozo types, the unencoded ones (alternates and parts) and the parts its composites need."""
    kept = {glyph.name for glyph in font if not glyph.unicodes or any(map(keeps_codepoint, glyph.unicodes))}
    parts = set(kept)
    while parts := {component.baseGlyph for name in parts for component in font[name].components} - kept:
        kept |= parts
    return kept


def add_stand_ins(font) -> None:
    """Let the glyphs in `STAND_INS` answer for their extra characters."""
    for name, codes in STAND_INS.items():
        font[name].unicodes = [*font[name].unicodes, *codes]


def prune_features(feature_text: str, glyph_names) -> str:
    """Paper Mono's feature code, without the features that are not in `FEATURES`."""
    doc = Parser(StringIO(feature_text), glyphNames=set(glyph_names)).parse()
    doc.statements = [
        statement
        for statement in doc.statements
        if not isinstance(statement, ast.FeatureBlock) or statement.name in FEATURES
    ]
    return doc.asFea()
