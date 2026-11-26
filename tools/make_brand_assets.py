r"""Generate the neutral brand assets for the integration.

The integration no longer uses the LEA logo. The icon is an independent fuel
pump mark in a dark blue rounded square, and the logo combines that icon with
the product name.

Run from the project root:
    .\.venv\Scripts\python.exe tools\make_brand_assets.py
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
BRAND = ROOT / "custom_components" / "lt_fuel_prices" / "brand"

NAVY = (30, 58, 138, 255)  # #1e3a8a
BLUE = (37, 99, 235, 255)  # #2563eb
WHITE = (255, 255, 255, 255)
LIGHT_TEXT = (30, 58, 138, 255)
DARK_TEXT = (242, 242, 242, 255)

NAME = "Degalų kainos Lietuvoje"


def _font(size: int) -> ImageFont.FreeTypeFont:
    """Load a bold font that covers Lithuanian diacritics."""
    for candidate in (
        r"C:\Windows\Fonts\segoeuib.ttf",
        r"C:\Windows\Fonts\arialbd.ttf",
    ):
        path = Path(candidate)
        if path.is_file():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default(size)


def _pump_icon(size: int) -> Image.Image:
    """Draw the rounded-square icon with a white fuel pump."""
    scale = 4
    s = size * scale

    # Background layer, clipped to the rounded square so the blue corner
    # accent never paints outside the icon shape.
    background = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    bg_draw = ImageDraw.Draw(background)
    bg_draw.rounded_rectangle(
        (0, 0, s - 1, s - 1), radius=int(s * 0.22), fill=NAVY
    )
    bg_draw.pieslice(
        (int(s * 0.55), int(s * 0.55), int(s * 1.55), int(s * 1.55)),
        start=180,
        end=270,
        fill=BLUE,
    )
    mask = Image.new("L", (s, s), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        (0, 0, s - 1, s - 1), radius=int(s * 0.22), fill=255
    )
    background.putalpha(mask)

    canvas = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    canvas.alpha_composite(background)
    draw = ImageDraw.Draw(canvas)

    def r(value: float) -> int:
        return int(value * s)

    # Pump body, base, screen, hose and nozzle.
    draw.rounded_rectangle(
        (r(0.30), r(0.17), r(0.60), r(0.72)), radius=r(0.035), fill=WHITE
    )
    draw.rounded_rectangle(
        (r(0.23), r(0.74), r(0.75), r(0.80)), radius=r(0.02), fill=WHITE
    )
    draw.rounded_rectangle(
        (r(0.35), r(0.24), r(0.55), r(0.35)), radius=r(0.015), fill=NAVY
    )
    draw.line(
        [(r(0.60), r(0.40)), (r(0.68), r(0.40)), (r(0.68), r(0.61))],
        fill=WHITE,
        width=r(0.035),
        joint="curve",
    )
    draw.rounded_rectangle(
        (r(0.63), r(0.60), r(0.74), r(0.66)), radius=r(0.012), fill=WHITE
    )
    draw.rectangle((r(0.74), r(0.62), r(0.78), r(0.65)), fill=WHITE)

    return canvas.resize((size, size), Image.LANCZOS)


def _logo(icon: Image.Image, text_color: tuple[int, int, int, int]) -> Image.Image:
    """Draw the horizontal logo: icon on the left, product name on the right."""
    width, height = 1600, 256
    canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))

    icon_size = 224
    small = icon.resize((icon_size, icon_size), Image.LANCZOS)
    canvas.alpha_composite(small, (16, (height - icon_size) // 2))

    draw = ImageDraw.Draw(canvas)
    text_x = 272
    font_size = 118
    while font_size > 40:
        font = _font(font_size)
        if draw.textlength(NAME, font=font) <= width - text_x - 8:
            break
        font_size -= 2

    draw.text(
        (text_x, height // 2),
        NAME,
        font=font,
        fill=text_color,
        anchor="lm",
    )
    return canvas


def main() -> None:
    """Write the icon and logo files."""
    BRAND.mkdir(parents=True, exist_ok=True)

    icon = _pump_icon(512)
    icon.save(BRAND / "icon@2x.png")
    icon.resize((256, 256), Image.LANCZOS).save(BRAND / "icon.png")

    light = _logo(icon, LIGHT_TEXT)
    light.save(BRAND / "logo@2x.png")
    light.resize((800, 128), Image.LANCZOS).save(BRAND / "logo.png")

    dark = _logo(icon, DARK_TEXT)
    dark.save(BRAND / "dark_logo@2x.png")
    dark.resize((800, 128), Image.LANCZOS).save(BRAND / "dark_logo.png")

    for path in sorted(BRAND.iterdir()):
        with Image.open(path) as image:
            print(f"{path.name}: {image.size}")


if __name__ == "__main__":
    main()
