#!/usr/bin/env python3
"""Print the sunrise curve without waiting for a real sunrise.

python scripts/simulate_sunrise.py --duration 30
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from custom_components.sunrise_alarm.sunrise import PROFILES, state_at  # noqa: E402


def main() -> None:
    """Render the curve as a table plus ASCII graphs."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--duration", type=float, default=30, help="minutes")
    parser.add_argument("--steps", type=int, default=20)
    parser.add_argument("--max-brightness", type=float, default=100)
    parser.add_argument("--profile", choices=list(PROFILES), default="philips")
    args = parser.parse_args()
    points = PROFILES[args.profile]

    print(f"Sunrise duration: {args.duration:g} minutes, profile: {args.profile}\n")
    print("  time  progress  brightness  rgb                bar")
    for step in range(args.steps + 1):
        progress = step / args.steps
        brightness, rgb = state_at(progress, args.max_brightness, points)
        minutes = progress * args.duration
        bar = "#" * round(brightness / 2)
        print(
            f"  {int(minutes):02d}:{round(minutes % 1 * 60):02d}"
            f"  {progress:>7.2f}  {brightness:>9d}%"
            f"  ({rgb[0]:>3},{rgb[1]:>3},{rgb[2]:>3})    {bar}"
        )

    print("\nRGB channels (R=r G=g B=b):")
    for step in range(args.steps + 1):
        progress = step / args.steps
        _, rgb = state_at(progress, args.max_brightness, points)
        row = [" "] * 52
        for channel, char in zip(rgb, "rgb"):
            row[round(channel / 5)] = char
        print(f"  {progress:>4.2f} |{''.join(row)}")


if __name__ == "__main__":
    main()
