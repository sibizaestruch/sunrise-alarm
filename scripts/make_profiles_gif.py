#!/usr/bin/env python3
"""Render the sunrise profiles as docs/profiles.gif: 30 minutes in 4 seconds.

uv run --no-project --with pillow python scripts/make_profiles_gif.py
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]

# sunrise.py is loaded by path: importing the package would pull in homeassistant
_spec = importlib.util.spec_from_file_location(
    "sunrise", ROOT / "custom_components/sunrise_alarm/sunrise.py"
)
_sunrise = importlib.util.module_from_spec(_spec)
sys.modules["sunrise"] = _sunrise  # the dataclass looks its own module up here
_spec.loader.exec_module(_sunrise)
PROFILES, state_at = _sunrise.PROFILES, _sunrise.state_at

W, FRAMES, DURATION = 480, 40, 30
PAD, ROW, GAP, TOP = 20, 54, 12, 46
BG, DIM = (13, 13, 17), 0.22  # DIM: how dark the not-yet-reached part of the curve is
H = TOP + len(PROFILES) * (ROW + GAP) + 8


def _font(size: int, bold: bool = False):
    """A real font if the system has one, else Pillow's bitmap default."""
    for path in ("/System/Library/Fonts/Supplemental/Arial{}.ttf",
                 "/usr/share/fonts/truetype/dejavu/DejaVuSans{}.ttf"):
        try:
            return ImageFont.truetype(path.format(" Bold" if bold else ""), size)
        except OSError:
            continue
    return ImageFont.load_default()


FONT, FONT_BOLD = _font(14), _font(15, bold=True)
INNER = W - 2 * PAD


def curve_strip(points) -> Image.Image:
    """The whole sunrise as one gradient: x is time, colour is the lit bulb."""
    strip = Image.new("RGB", (INNER, 1))
    px = strip.load()
    for x in range(INNER):
        brightness, rgb = state_at(x / (INNER - 1), points=points)
        px[x, 0] = tuple(round(c * brightness / 100) for c in rgb)
    return strip.resize((INNER, ROW))


strips = {name: curve_strip(points) for name, points in PROFILES.items()}
corners = Image.new("L", (INNER, ROW), 0)
ImageDraw.Draw(corners).rounded_rectangle((0, 0, INNER - 1, ROW - 1), 10, fill=255)

frames = []
for i in range(FRAMES):
    progress = i / (FRAMES - 1)
    played = round(INNER * progress)
    minutes = progress * DURATION
    frame = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(frame)
    d.text((PAD, 14), "Sunrise profiles", font=FONT_BOLD, fill=(236, 236, 244))
    d.text((W - PAD - 96, 15),
           f"{int(minutes):02d}:{round(minutes % 1 * 60):02d} of {DURATION} min",
           font=FONT, fill=(126, 126, 142))

    for row, (name, points) in enumerate(PROFILES.items()):
        y = TOP + row * (ROW + GAP)
        strip = strips[name].copy()
        ahead = strip.crop((played, 0, INNER, ROW)).point(lambda c: round(c * DIM))
        strip.paste(ahead, (played, 0))
        frame.paste(strip, (PAD, y), corners)

        brightness, _ = state_at(progress, points=points)
        ink = (26, 20, 14) if brightness > 45 else (208, 208, 220)
        d.text((PAD + 14, y + ROW // 2 - 9), name, font=FONT_BOLD, fill=ink)
        d.text((PAD + INNER - 58, y + ROW // 2 - 8), f"{brightness:>3d}%", font=FONT, fill=ink)
        if 0 < played < INNER:  # playhead, skipped at both ends so it never clips a corner
            d.line((PAD + played, y + 2, PAD + played, y + ROW - 3), fill=(255, 255, 255), width=2)

    frames.append(frame.convert("P", palette=Image.ADAPTIVE, colors=64))

out = ROOT / "docs/profiles.gif"
frames[0].save(out, save_all=True, append_images=frames[1:], duration=110, loop=0, optimize=True)
print(f"{out.relative_to(ROOT)}  {out.stat().st_size / 1024:.0f} KB  {frames[0].size}")
