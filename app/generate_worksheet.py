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
from reportlab.lib.colors import Color, black
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


def draw_double_pair_lines(
    pdf: canvas.Canvas,
    left_x: float,
    right_x: float,
    top_y: float,
    row_height: float,
    num_rows: int,
    line_color: Color = Color(0.85, 0.85, 0.85),
    solid_width: float = 1.2,
    pair_spacing: float = 4.0,
    row_gap: float = 16.0,
) -> list[Tuple[float, float, float, float]]:
    """
    Double-pair layout per row: two close lines at the top edge and two close lines at the bottom edge.
    Middle is open (blank). Returns list of (y_top_outer, y_top_inner, y_bottom_inner, y_bottom_outer).
    """
    rows_y: list[Tuple[float, float, float, float]] = []
    x0 = left_x
    x1 = right_x

    pdf.setStrokeColor(line_color)
    pdf.setLineWidth(solid_width)

    for i in range(num_rows):
        y_top_outer = top_y - i * (row_height + row_gap)
        y_top_inner = y_top_outer - pair_spacing
        y_bottom_outer = y_top_outer - row_height
        y_bottom_inner = y_bottom_outer + pair_spacing

        # Top pair
        pdf.setDash()
        pdf.line(x0, y_top_outer, x1, y_top_outer)
        pdf.line(x0, y_top_inner, x1, y_top_inner)

        # Bottom pair
        pdf.line(x0, y_bottom_outer, x1, y_bottom_outer)
        pdf.line(x0, y_bottom_inner, x1, y_bottom_inner)

        rows_y.append((y_top_outer, y_top_inner, y_bottom_inner, y_bottom_outer))

    return rows_y


def draw_repeated_trace_text(
    pdf: canvas.Canvas,
    text: str,
    font_name: str,
    font_size: float,
    left_x: float,
    right_x: float,
    baseline_y: float,
    text_color: Color = Color(0.5, 0.5, 0.5),
    spacing_em: float = 0.75,
) -> None:
    """Repeat the given text across the available width with spacing until it fills the line."""
    pdf.setFillColor(text_color)
    pdf.setFont(font_name, font_size)

    token = text.strip()
    if not token:
        return

    spacing = " " * max(1, int(spacing_em))
    unit = f"{token}{spacing}"
    unit_width = pdfmetrics.stringWidth(unit, font_name, font_size)
    if unit_width <= 0:
        return

    max_width = right_x - left_x
    count = max(1, int(max_width // unit_width))

    x = left_x
    for _ in range(count):
        pdf.drawString(x, baseline_y + 0.5, unit)
        x += unit_width


def generate_pdf(
    output_path: Path,
    text: str,
    font_family: str = "Solway",
    font_weight: int = 400,
    page_size=A4,
    margin: float = 54.0,
    row_height: float = 0.0,
    row_gap: float = 16.0,
    font_size: float = 64.0,
    pair_spacing: float = 4.0,
) -> None:
    width, height = page_size
    left_x = margin
    right_x = width - margin
    top_y = height - margin

    if row_height is None or row_height <= 0:
        row_height = max(60.0, font_size)

    ttf_path = download_ttf_to_cache(font_family, font_weight)
    font_name = register_font_from_ttf_path(font_family, font_weight, ttf_path)

    usable_height = height - 2 * margin
    num_rows = max(1, int((usable_height + row_gap) // (row_height + row_gap)))

    pdf = canvas.Canvas(str(output_path), pagesize=page_size)

    rows = draw_double_pair_lines(
        pdf,
        left_x=left_x,
        right_x=right_x,
        top_y=top_y,
        row_height=row_height,
        num_rows=num_rows,
        line_color=Color(0.85, 0.85, 0.85),
        solid_width=1.2,
        pair_spacing=pair_spacing,
        row_gap=row_gap,
    )

    # Place tracing text centered vertically in the middle gap per alternate row
    for idx, (y_top_outer, y_top_inner, y_bottom_inner, y_bottom_outer) in enumerate(rows):
        if idx % 2 == 0:
            middle_center = (y_top_inner + y_bottom_inner) / 2.0
            draw_repeated_trace_text(
                pdf,
                text=text,
                font_name=font_name,
                font_size=font_size,
                left_x=left_x + 8,
                right_x=right_x - 8,
                baseline_y=middle_center - (font_size * 0.3),
                text_color=Color(0.5, 0.5, 0.5),
                spacing_em=1.0,
            )

    pdf.setFillColor(Color(0.5, 0.5, 0.5))
    pdf.setFont("Helvetica", 8)
    pdf.drawRightString(right_x, margin * 0.5, "Liniatura podwójna (double-line) • Solway • generator PDF")

    pdf.showPage()
    pdf.save()


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generuj karty do pisania: liniatura podwójna (double-line) z czcionką Solway.")
    parser.add_argument("--text", type=str, default="Aa Bb Cc", help="Tekst do śledzenia na liniach (powtarzany)")
    parser.add_argument("--output", type=str, default="output/worksheet.pdf", help="Ścieżka wyjściowego PDF")
    parser.add_argument("--font-family", type=str, default="Solway", help="Nazwa rodziny z Google Fonts")
    parser.add_argument("--font-weight", type=int, default=400, help="Grubość czcionki (Google Fonts)")
    parser.add_argument("--margin", type=float, default=54.0, help="Margines strony w pt")
    parser.add_argument("--row-height", type=float, default=0.0, help="Wysokość wiersza w pt; 0 = równa rozmiarowi czcionki")
    parser.add_argument("--row-gap", type=float, default=16.0, help="Odstęp między wierszami w pt")
    parser.add_argument("--font-size", type=float, default=64.0, help="Rozmiar czcionki w pt (zalecane 60–72 pt)")
    parser.add_argument("--pair-spacing", type=float, default=4.0, help="Odstęp wewnątrz pary linii (pt)")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)

    project_root = Path(__file__).resolve().parents[1]
    output_path = Path(args.output)
    if not output_path.is_absolute():
        output_path = project_root / output_path

    output_dir = output_path.parent
    ensure_directory(output_dir)

    try:
        generate_pdf(
            output_path=output_path,
            text=args.text,
            font_family=args.font_family,
            font_weight=args.font_weight,
            margin=args.margin,
            row_height=args.row_height,
            row_gap=args.row_gap,
            font_size=args.font_size,
            pair_spacing=args.pair_spacing,
        )
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"Saved: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))