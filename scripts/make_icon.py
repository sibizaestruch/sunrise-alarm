"""Generate the brand icon PNGs for the integration.

Run: uv run --no-project --with pillow python scripts/make_icon.py
"""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "custom_components" / "sunrise_alarm" / "brand"
SS = 4  # supersample factor, downscaled at the end for antialiasing

# sky, top to bottom: night -> dawn
SKY = [
    (0.00, (0x10, 0x1B, 0x45)),
    (0.34, (0x3A, 0x2A, 0x6B)),
    (0.56, (0x9B, 0x3F, 0x6E)),
    (0.74, (0xE2, 0x6A, 0x3C)),
    (1.00, (0xFF, 0xB5, 0x3D)),
]
GROUND = (0x24, 0x16, 0x38)
SUN_CORE = (0xFF, 0xF6, 0xD4)
SUN_EDGE = (0xFF, 0xC1, 0x3C)


def lerp(a: tuple[int, ...], b: tuple[int, ...], t: float) -> tuple[int, ...]:
    """Blend two colours."""
    return tuple(round(x + (y - x) * t) for x, y in zip(a, b))


def sky_color(t: float) -> tuple[int, ...]:
    """Colour of the sky at `t` of the way down the icon."""
    for (p0, c0), (p1, c1) in zip(SKY, SKY[1:]):
        if t <= p1:
            return lerp(c0, c1, (t - p0) / (p1 - p0))
    return SKY[-1][1]


def draw(size: int) -> Image.Image:
    """Render the icon at `size` pixels square."""
    s = size * SS
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # circular sky, painted as horizontal slices of the gradient
    sky = Image.new("RGBA", (s, s))
    sd = ImageDraw.Draw(sky)
    for y in range(s):
        sd.line([(0, y), (s, y)], fill=(*sky_color(y / (s - 1)), 255))
    mask = Image.new("L", (s, s), 0)
    ImageDraw.Draw(mask).ellipse([0, 0, s - 1, s - 1], fill=255)
    img.paste(sky, (0, 0), mask)

    horizon = s * 0.73
    sun_r = s * 0.27
    cx = s / 2

    # rays: tapered wedges fanning out of the sun
    ray = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    rd = ImageDraw.Draw(ray)
    for i in range(7):
        a = math.radians(180 + 15 + i * 25)
        inner, outer, half = sun_r * 1.22, sun_r * 1.92, math.radians(3.2)
        rd.polygon(
            [
                (cx + inner * math.cos(a - half), horizon + inner * math.sin(a - half)),
                (cx + outer * math.cos(a), horizon + outer * math.sin(a)),
                (cx + inner * math.cos(a + half), horizon + inner * math.sin(a + half)),
            ],
            fill=(*SUN_CORE, 205),
        )
    blank = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    img.alpha_composite(Image.composite(ray, blank, mask))

    # sun: radial gradient, drawn as shrinking discs
    steps = 90
    for i in range(steps, 0, -1):
        t = i / steps
        d.ellipse(
            [cx - sun_r * t, horizon - sun_r * t, cx + sun_r * t, horizon + sun_r * t],
            fill=(*lerp(SUN_CORE, SUN_EDGE, t), 255),
        )

    # ground: hides the lower half of the sun, keeps the circle edge clean
    ground = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    gd = ImageDraw.Draw(ground)
    for y in range(int(horizon), s):
        t = (y - horizon) / (s - horizon)
        gd.line([(0, y), (s, y)], fill=(*lerp(GROUND, (0x0D, 0x08, 0x1B), t), 255))
    img.alpha_composite(Image.composite(ground, blank, mask))

    return img.resize((size, size), Image.LANCZOS)


def main() -> None:
    """Write every icon size the brands spec asks for."""
    OUT.mkdir(parents=True, exist_ok=True)
    for size, name in ((256, "icon.png"), (512, "icon@2x.png")):
        draw(size).save(OUT / name, optimize=True)
        print(OUT / name)


if __name__ == "__main__":
    main()
