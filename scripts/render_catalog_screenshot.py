#!/usr/bin/env python3
"""Render real CLI stdout captured during the workflow (not fabricated UI)."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

source = Path("/tmp/ventoy-list.txt")
lines = source.read_text(encoding="utf-8", errors="replace").splitlines()
lines = ["$ ventoy-fetch --list", ""] + lines[:80]
font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
font = ImageFont.truetype(font_path, 17)
width = 1250
height = 90 + 26 * len(lines)
im = Image.new("RGB", (width, height), "#10151f")
draw = ImageDraw.Draw(im)
draw.rounded_rectangle([22, 22, width-22, height-22], radius=14, fill="#18202c", outline="#354252", width=2)
draw.text((46, 38), "Ventoy Fetch • actual CLI catalog • Linux CI", fill="#98a9bc", font=font)
for idx, line in enumerate(lines):
    draw.text((46, 81 + idx*26), line[:105], fill="#f4c366" if idx == 0 else "#d6e1ee", font=font)
dest = Path("docs/screenshots/catalog-cli.png")
dest.parent.mkdir(parents=True, exist_ok=True)
im.save(dest)
print(f"Wrote {dest} using {len(lines)-2} captured CLI output lines")
