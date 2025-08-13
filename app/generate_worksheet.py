#!/usr/bin/env python3
import argparse
import math
import os
from pathlib import Path
from io import BytesIO
import re
import sys
from typing import Tuple

import requests
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.colors import Color, black, gray
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont


GOOGLE_FONTS_CSS_API = "https://fonts.googleapis.com/css2?family={family}:wght@{weight}"


def ensure_directory(path: Path) -> None:
    if not path.exists():
        path.mkdir(parents=True, exist_ok=True)


def get_ttf_url_from_google_fonts(font_family: str, weight: int = 400) -> str:
    family_q = font_family.replace(" ", "+")
    url = GOOGLE_FONTS_CSS_API.format(family=family_q, weight=weight)
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers, timeout=20)
    response.raise_for_status()
    css = response.text
    match = re.search(r"url\((https://fonts.gstatic.com/s/.*?\.ttf)\)", css)
    if not match:
        raise RuntimeError("Could not find a TTF URL in Google Fonts CSS for the requested font.")
    return match.group(1)


def download_ttf_to_cache(font_family: str, weight: int = 400, cache_dir: Path | None = None) -> Path:
    if cache_dir is None:
        # Project-local cache directory
        project_root = Path(__file__).resolve().parents[1]
        cache_dir = project_root / ".cache" / "fonts"
    ensure_directory(cache_dir)

    safe_name = font_family.lower().replace(" ", "-")
    target_path = cache_dir / f"{safe_name}-{weight}.ttf"
    if target_path.exists() and target_path.stat().st_size > 0:
        return target_path

    ttf_url = get_ttf_url_from_google_fonts(font_family, weight)
    headers = {"User-Agent": "Mozilla/5.0"}
    resp = requests.get(ttf_url, headers=headers, timeout=30)
    resp.raise_for_status()
    target_path.write_bytes(resp.content)
    return target_path


def register_font_from_ttf_path(font_family: str, weight: int, ttf_path: Path) -> str:
    # Normalize a font name for use in reportlab
    font_name = f"{font_family}-{weight}"
    if font_name not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont(font_name, str(ttf_path)))
    return font_name


def draw_handwriting_lines(
    pdf: canvas.Canvas,
    left_x: float,
    right_x: float,
    top_y: float,
    row_height: float,
    num_rows: int,
    line_color: Color = gray(0.75),
    solid_width: float = 1.0,
    dashed_width: float = 0.8,
    middle_dash: Tuple[int, int] = (6, 4),
    row_gap: float = 8.0,
) -> list[Tuple[float, float, float]]:
    """
    Draws primary-handwriting guide lines: top solid, middle dashed, bottom solid.
    Returns a list of (y_top, y_mid, y_bottom) per row for further text placement.
    """
    rows_y: list[Tuple[float, float, float]] = []
    x0 = left_x
    x1 = right_x

    pdf.setStrokeColor(line_color)

    for i in range(num_rows):
        row_top_y = top_y - i * (row_height + row_gap)
        row_mid_y = row_top_y - (row_height / 2.0)
        row_bottom_y = row_top_y - row_height

        # Top solid
        pdf.setLineWidth(solid_width)
        pdf.setDash()  # solid
        pdf.line(x0, row_top_y, x1, row_top_y)

        # Middle dashed
        pdf.setLineWidth(dashed_width)
        pdf.setDash(middle_dash[0], middle_dash[1])
        pdf.line(x0, row_mid_y, x1, row_mid_y)

        # Bottom solid
        pdf.setLineWidth(solid_width)
        pdf.setDash()
        pdf.line(x0, row_bottom_y, x1, row_bottom_y)

        rows_y.append((row_top_y, row_mid_y, row_bottom_y))

    # Reset dash
    pdf.setDash()
    return rows_y


def draw_repeated_trace_text(
    pdf: canvas.Canvas,
    text: str,
    font_name: str,
    font_size: float,
    left_x: float,
    right_x: float,
    baseline_y: float,
    text_color: Color = gray(0.55),
    spacing_em: float = 0.75,
) -> None:
    """Repeat the given text across the available width with spacing until it fills the line."""
    pdf.setFillColor(text_color)
    pdf.setFont(font_name, font_size)

    token = text.strip()
    if not token:
        return

    # Build a spacing string approximately proportional to font size
    spacing = " " * max(1, int(spacing_em))
    unit = f"{token}{spacing}"
    unit_width = pdfmetrics.stringWidth(unit, font_name, font_size)
    if unit_width <= 0:
        return

    max_width = right_x - left_x
    count = max(1, int(max_width // unit_width))

    x = left_x
    for _ in range(count):
        pdf.drawString(x, baseline_y + 0.5, unit)  # small lift to clear bottom line stroke
        x += unit_width


def generate_pdf(
    output_path: Path,
    text: str,
    font_family: str = "Solway",
    font_weight: int = 400,
    page_size=A4,
    margin: float = 54.0,
    row_height: float = 64.0,
    row_gap: float = 8.0,
    font_size: float | None = None,
) -> None:
    width, height = page_size
    left_x = margin
    right_x = width - margin
    top_y = height - margin

    if font_size is None:
        font_size = max(10.0, row_height * 0.66)

    # Prepare font
    ttf_path = download_ttf_to_cache(font_family, font_weight)
    font_name = register_font_from_ttf_path(font_family, font_weight, ttf_path)

    # Calculate rows that can fit
    usable_height = height - 2 * margin
    num_rows = max(1, int((usable_height + row_gap) // (row_height + row_gap)))

    pdf = canvas.Canvas(str(output_path), pagesize=page_size)

    rows = draw_handwriting_lines(
        pdf,
        left_x=left_x,
        right_x=right_x,
        top_y=top_y,
        row_height=row_height,
        num_rows=num_rows,
        line_color=gray(0.8),
        solid_width=1.0,
        dashed_width=0.8,
        middle_dash=(6, 6),
        row_gap=row_gap,
    )

    # Draw repeated trace text on every other line (first, third, ...) to mimic worksheets
    for idx, (_, _mid, bottom) in enumerate(rows):
        if idx % 2 == 0:
            draw_repeated_trace_text(
                pdf,
                text=text,
                font_name=font_name,
                font_size=font_size,
                left_x=left_x + 8,
                right_x=right_x - 8,
                baseline_y=bottom,
                text_color=gray(0.6),
                spacing_em=1.0,
            )

    # Footer note
    pdf.setFillColor(gray(0.5))
    pdf.setFont("Helvetica", 8)
    pdf.drawRightString(right_x, margin * 0.5, "Generated with Solway handwriting worksheet generator")

    pdf.showPage()
    pdf.save()


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate handwriting worksheets PDF with Solway font.")
    parser.add_argument("--text", type=str, default="Aa Bb Cc", help="Text to repeat on tracing lines")
    parser.add_argument("--output", type=str, default="output/worksheet.pdf", help="Output PDF path")
    parser.add_argument("--font-family", type=str, default="Solway", help="Google Fonts family name")
    parser.add_argument("--font-weight", type=int, default=400, help="Font weight (Google Fonts)")
    parser.add_argument("--margin", type=float, default=54.0, help="Page margin in points")
    parser.add_argument("--row-height", type=float, default=64.0, help="Row height in points")
    parser.add_argument("--row-gap", type=float, default=8.0, help="Gap between rows in points")
    parser.add_argument("--font-size", type=float, default=0.0, help="Font size; if 0 uses 66% of row height")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)

    project_root = Path(__file__).resolve().parents[1]
    output_path = Path(args.output)
    if not output_path.is_absolute():
        output_path = project_root / output_path

    output_dir = output_path.parent
    ensure_directory(output_dir)

    font_size = None if args.font_size in (None, 0.0) else args.font_size

    try:
        generate_pdf(
            output_path=output_path,
            text=args.text,
            font_family=args.font_family,
            font_weight=args.font_weight,
            margin=args.margin,
            row_height=args.row_height,
            row_gap=args.row_gap,
            font_size=font_size,
        )
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"Saved: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))