"""Generate the cockpit PWA icon set into assets/hub-icons/.

Two variants per size: `any` (glyph at ~62% width) and `maskable`
(full-bleed background, glyph within the 80% safe zone so Android's
circle/squircle mask never clips it).
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "assets" / "hub-icons"
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
BG = (26, 111, 181)
FG = (255, 255, 255)
LADDER = (255, 255, 255, 110)


def _icon(size: int, glyph_frac: float) -> Image.Image:
    img = Image.new("RGB", (size, size), BG)
    draw = ImageDraw.Draw(img, "RGBA")

    font = ImageFont.truetype(FONT, int(size * glyph_frac * 0.62))
    left, top, right, bottom = draw.textbbox((0, 0), "em", font=font)
    w, h = right - left, bottom - top
    x = (size - w) / 2 - left
    y = (size - h) / 2 - top - size * 0.06
    draw.text((x, y), "em", font=font, fill=FG)

    step_w = size * glyph_frac * 0.14
    step_h = max(2, int(size * 0.018))
    base_y = y + top + h + size * 0.10
    cx = size / 2
    for i, rise in enumerate((0.0, 0.045, 0.09)):
        sx = cx - step_w * 1.9 + i * step_w * 1.3
        sy = base_y - size * rise
        draw.rounded_rectangle([sx, sy, sx + step_w, sy + step_h], radius=step_h / 2, fill=LADDER)
    return img


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for size in (192, 512):
        _icon(size, 0.88).save(OUT / f"icon-{size}.png")
        _icon(size, 0.78).save(OUT / f"icon-maskable-{size}.png")
        print(f"wrote icon-{size}.png + icon-maskable-{size}.png")


if __name__ == "__main__":
    main()
