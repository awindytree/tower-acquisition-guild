"""Generate data/font_8x16.png: a CP437 tilesheet (16 columns of 8x16-pixel glyphs; rows
0-15 are CP437, the rows after hold the extra letters CP437 lacks, see EXTRA).

Built from GNU Unifont, a pixel font, so every glyph lands exactly on the
pixel grid. You only need this to rebuild the font or try another one.
Requires Pillow:  pip install pillow

    python tools/make_tileset.py path/to/unifont.otf
"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H = 8, 16
OUT = Path(__file__).resolve().parent.parent / "data" / "font_8x16.png"

# Letters the game needs that aren't in CP437, in this order (main.py and
# game/font.py read the same list). Add more at the end, then re-run.
EXTRA = "þÞ"

# CP437 characters 0-31 and 127 as tcod's CHARMAP_CP437 maps them.
LOW = " ☺☻♥♦♣♠•◘○◙♂♀♪♫☼►◄↕‼¶§▬↨↑↓→←∟↔▲▼"


def cp437_char(i: int) -> str:
    if i < 32:
        return LOW[i]
    if i == 127:
        return "⌂"
    return bytes([i]).decode("cp437")


def main(font_path: str) -> None:
    font = ImageFont.truetype(font_path, 16)
    # 16 columns: rows 0-15 are CP437; the rows after hold EXTRA, in order (v0.51.2: one sheet,
    # loaded with one charmap, so the extra letters need no tile-by-tile copying at startup).
    rows = 16 + (len(EXTRA) + 15) // 16
    sheet = Image.new("RGBA", (W * 16, H * rows), (0, 0, 0, 0))
    for i in range(256):
        sheet.paste(render(font, cp437_char(i)), ((i % 16) * W, (i // 16) * H))
    for j, ch in enumerate(EXTRA):
        i = 256 + j
        sheet.paste(render(font, ch), ((i % 16) * W, (i // 16) * H))
    sheet.save(OUT)
    print(f"Wrote {OUT} ({rows} rows)")


def render(font, ch: str) -> Image.Image:
    """One glyph. Drawn on a wider scratch cell (a few glyphs are double-width
    in Unifont), keeping the left 8 pixels, snapped to fully on/off pixels."""
    cell = Image.new("L", (W * 2, H), 0)
    ImageDraw.Draw(cell).text((0, 0), ch, font=font, fill=255)
    mask = cell.crop((0, 0, W, H)).point(lambda v: 255 if v >= 128 else 0)
    glyph = Image.new("RGBA", (W, H), (255, 255, 255, 0))
    glyph.putalpha(mask)
    return glyph


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "unifont.otf")
