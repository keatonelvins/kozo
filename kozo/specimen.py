"""Draw kozo.svg, the specimen, from the built fonts: uv run python -m kozo.specimen"""
import textwrap

from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.ttLib import TTFont

from . import config

PAPER, INK, MUTED = "#fbfbfa", "#111110", "#8a8a85"
WIDTH, MARGIN = 1200, 60
MEASURE = WIDTH - 2 * MARGIN
EM = config.CELL / 1000
TEXT = 20  # the text size: 100 cells across the sheet

BODY = (
    "Kōzo (Broussonetia × kazinoki) is a flowering plant in the family Moraceae, a natural hybrid of the paper "
    "mulberry found in Japan and Korea. It is cultivated for its bark and valued for its long, strong fibres. "
    "The stems are steamed and stripped, and the inner bark is boiled and beaten into pulp. Kōzo is the most "
    "widely used raw material in washi, traditional Japanese paper. The paper is thin and strong, and is used "
    "for calligraphy, printmaking, screens and the repair of books."
)
ALPHABET = ("ABCDEFGHIJKLM", "NOPQRSTUVWXYZ", "abcdefghijklm", "nopqrstuvwxyz", "0123456789&→!")
SAMPLES = {"Regular": "Broussonetia × kazinoki", "Medium": "typed on mulberry paper"}


class Sheet:
    """An SVG page set in Kozo's own outlines, so it needs no font to view."""

    def __init__(self) -> None:
        self.fonts = {style.name: TTFont(config.FONTS / f"{style.filename}.ttf") for style in config.STYLES}
        self.paths: dict[str, str] = {}
        self.lines: list[str] = []

    def line(self, text: str, x: float, y: float, size: float, style: str = "Regular", fill: str = INK) -> None:
        """Set one line with its baseline at (x, y)."""
        font = self.fonts[style]
        glyphs, cmap = font.getGlyphSet(), font.getBestCmap()
        uses = []
        for column, character in enumerate(text):
            if character == " ":
                continue
            name = cmap[ord(character)]
            if (key := f"{style}-{name}") not in self.paths:
                pen = SVGPathPen(glyphs)
                glyphs[name].draw(pen)
                self.paths[key] = pen.getCommands()
            uses.append(f'<use href="#{key}" x="{column * config.CELL}"/>')
        scale = size / 1000
        self.lines.append(f'<g transform="translate({x:g} {y:g}) scale({scale:g} {-scale:g})" fill="{fill}">{"".join(uses)}</g>')

    def save(self, height: float) -> None:
        paths = "".join(f'<path id="{key}" d="{d}"/>' for key, d in self.paths.items())
        (config.ROOT / "kozo.svg").write_text(
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH} {height:g}" width="{WIDTH}" height="{height:g}">'
            f'<rect width="100%" height="100%" fill="{PAPER}"/><defs>{paths}</defs>{"".join(self.lines)}</svg>\n'
        )


def filling(columns: int) -> float:
    """The size at which `columns` characters fill the measure."""
    return MEASURE / columns / EM


def main() -> None:
    sheet = Sheet()
    right = WIDTH - MARGIN

    def label(left: str, end: str, y: float) -> None:
        sheet.line(left, MARGIN, y, TEXT, fill=MUTED)
        sheet.line(end, right - len(end) * TEXT * EM, y, TEXT, fill=MUTED)

    y = 150 + filling(4) * 0.7
    sheet.line(config.FAMILY, MARGIN, y, filling(4))

    y += 150
    sheet.line("A typewriter face", MARGIN, y, TEXT)
    for row in textwrap.wrap(BODY, 64):
        sheet.line(row, right - 64 * TEXT * EM, y, TEXT)
        y += TEXT * 1.5

    y += 120
    size = filling(13)
    for row in ALPHABET:
        y += size * 1.2
        sheet.line(row, MARGIN, y, size)

    y += 60
    size = filling(23)
    for style in config.STYLES:
        y += 130
        label(style.name, str(style.weight_class), y)
        y += size * 1.15
        sheet.line(SAMPLES[style.name], MARGIN, y, size, style.name)

    font = sheet.fonts["Regular"]
    glyphs, shown = font.getGlyphSet(), {}
    for code, name in sorted(font.getBestCmap().items()):
        if glyphs[name].width and not chr(code).isspace():
            shown.setdefault(name, chr(code))  # each glyph once
    characters = list(shown.values())
    y += 190
    label("Glyphs", str(len(characters)), y)
    size = MEASURE / (2 * 32 - 1) / EM  # 32 to a row, a cell apart
    y += 30
    for start in range(0, len(characters), 32):
        y += size * 1.9
        sheet.line(" ".join(characters[start : start + 32]), MARGIN, y, size)

    sheet.save(y + 150)


if __name__ == "__main__":
    main()
