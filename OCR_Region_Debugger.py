"""
GSPro Region Debug Tool
=======================
Captures your defined screen regions, runs OCR on them, and saves
annotated PNG files so you can verify coordinates are correct.

Usage:
    python region_debug.py

Output files:
    debug_handedness_region.png  - what the handedness OCR sees
    debug_club_region.png        - what the club OCR sees

Adjust the regions at the bottom of this file to match your screen.
"""

import mss
import pytesseract
from PIL import Image, ImageDraw, ImageFont
import re
import os
import time

# ─── Configure your regions here ─────────────────────────────────────────────

HANDEDNESS_REGION = {
    'left':   1478,
    'top':    1123,
    'width':  100,
    'height': 45,
}

CLUB_REGION = {
    'left':   1478,
    'top':    1055,
    'width':  100,
    'height': 45,
}

# ─────────────────────────────────────────────────────────────────────────────


def capture(region):
    with mss.mss() as sct:
        screenshot = sct.grab(region)
        img = Image.frombytes('RGB', screenshot.size, screenshot.bgra, 'raw', 'BGRX')
    return img


def ocr_handedness(image):
    results = {}

    # Primary method
    text = pytesseract.image_to_string(image, config='--psm 6 -c tessedit_char_whitelist=RHLH')
    results['whitelist psm6'] = text.strip()

    for psm in [7, 8, 10]:
        text = pytesseract.image_to_string(image, config=f'--psm {psm}')
        results[f'psm {psm}'] = text.strip()

    # Determine best guess
    best = None
    for method, text in results.items():
        t = text.upper()
        if 'RH' in t or re.search(r'R\s*H', t) or 'WH' in t:
            best = 'RH'
            break
        if 'LH' in t or re.search(r'L\s*H', t):
            best = 'LH'
            break

    return results, best


def ocr_club(image):
    results = {}
    for psm in [7, 8, 6]:
        text = pytesseract.image_to_string(image, config=f'--psm {psm}')
        results[f'psm {psm}'] = text.strip()

    best = next((v for v in results.values() if v.strip()), None)
    return results, best


def scale_image(img, min_width=400, min_height=150, scale=4):
    """Upscale tiny captures so they're readable in the output PNG."""
    w = max(img.width * scale, min_width)
    h = max(img.height * scale, min_height)
    return img.resize((w, h), Image.NEAREST)


def save_debug_image(img, region, ocr_results, best_guess, output_path, label):
    """Build an annotated debug PNG with the capture and OCR results."""
    # Upscale the captured region for visibility
    capture_display = scale_image(img)
    cap_w, cap_h = capture_display.size

    # Info panel height
    line_height = 22
    padding = 12
    lines = [
        f"=== {label} ===",
        f"Region: left={region['left']}  top={region['top']}  "
        f"width={region['width']}  height={region['height']}",
        f"Best guess: {best_guess if best_guess else '(nothing detected)'}",
        "--- OCR results by method ---",
    ] + [f"  {m}: '{v}'" for m, v in ocr_results.items()]

    panel_h = padding * 2 + line_height * len(lines)
    total_h = cap_h + panel_h

    out = Image.new('RGB', (max(cap_w, 700), total_h), color=(30, 30, 30))

    # Paste the capture at the top with a border
    out.paste(capture_display, (0, 0))

    draw = ImageDraw.Draw(out)

    # Border around capture
    draw.rectangle([0, 0, cap_w - 1, cap_h - 1], outline=(0, 200, 100), width=2)

    # Info panel text
    try:
        font = ImageFont.truetype("arial.ttf", 15)
        font_bold = ImageFont.truetype("arialbd.ttf", 16)
    except Exception:
        font = ImageFont.load_default()
        font_bold = font

    y = cap_h + padding
    for i, line in enumerate(lines):
        color = (255, 220, 0) if i == 0 else (
            (0, 255, 140) if 'Best guess' in line else (200, 200, 200)
        )
        f = font_bold if i == 0 else font
        draw.text((padding, y), line, fill=color, font=f)
        y += line_height

    out.save(output_path)
    print(f"  Saved → {output_path}")


def main():
    print("=" * 60)
    print("GSPro Region Debug Tool")
    print("=" * 60)
    print("Switch to your GSPro window NOW.")
    print("Capturing in 3 seconds...\n")
    time.sleep(3)

    # ── Handedness region ────────────────────────────────────────
    print("[1/2] Capturing handedness region...")
    img_h = capture(HANDEDNESS_REGION)
    ocr_results_h, best_h = ocr_handedness(img_h)
    print(f"      Best guess: {best_h if best_h else '(nothing detected)'}")
    for method, val in ocr_results_h.items():
        print(f"      {method}: '{val}'")
    save_debug_image(
        img_h, HANDEDNESS_REGION, ocr_results_h, best_h,
        'debug_handedness_region.png', 'Handedness Region'
    )

    print()

    # ── Club region ──────────────────────────────────────────────
    print("[2/2] Capturing club region...")
    img_c = capture(CLUB_REGION)
    ocr_results_c, best_c = ocr_club(img_c)
    print(f"      Best guess: {best_c if best_c else '(nothing detected)'}")
    for method, val in ocr_results_c.items():
        print(f"      {method}: '{val}'")
    save_debug_image(
        img_c, CLUB_REGION, ocr_results_c, best_c,
        'debug_club_region.png', 'Club Region'
    )

    print()
    print("=" * 60)
    print("Done! Open the two PNG files to check your regions:")
    print("  debug_handedness_region.png")
    print("  debug_club_region.png")
    print()
    print("If the captured image looks wrong, adjust the left/top/width/height")
    print("values in the HANDEDNESS_REGION and CLUB_REGION dicts at the top")
    print("of this script, then run it again.")
    print("=" * 60)


if __name__ == "__main__":
    main()