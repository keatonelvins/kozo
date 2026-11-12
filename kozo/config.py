"""The grid, the weights, the names."""
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAPER_MONO = "74fc5537cc1f7b39aa8cccfa7dd3822e17143cca"  # the upstream commit Kozo is drawn from
FONTS = ROOT / "fonts"

FAMILY = "Kozo"
VERSION = (1, 0)
RELEASED = (2026, 11, 12)  # stamped in place of the build time, so a build repeats exactly
REPOSITORY = "https://github.com/keatonelvins/kozo"
COPYRIGHT = " ".join(f"{notice}." for notice in (ROOT / "OFL.txt").read_text().split("\n\n")[0].splitlines())
DESIGNER = "Keaton Elvins"

# Font units, 1000 to the em. The cell and the x-height are whole pixels on a 2x screen at 15 and 20 px.
CELL = 600
X_HEIGHT = 500
DESCENDER = -225


@dataclass(frozen=True)
class Style:
    name: str
    weight_class: int     # CSS weight
    paper_weight: float   # on Paper Mono's weight axis (its Regular is 86)

    @property
    def filename(self) -> str:
        return f"{FAMILY}-{self.name}"


STYLES = (Style("Regular", 400, 76), Style("Medium", 500, 93))
