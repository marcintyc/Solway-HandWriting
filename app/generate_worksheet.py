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

TRACE_UPPER = "A B C D E F G H I J K L M N O P Q R S T U V W X Y Z"
TRACE_LOWER = "a b c d e f g h i j k l m n o p q r s t u v w x y z"
TRACE_DIGITS = "0 1 2 3 4 5 6 7 8 9"
TRACE_WORDS_PL = [
    "Ala ma kota.",
    "Lubię czytać książki.",
    "Mama i tata idą do domu.",
    "Zosia rysuje zielone drzewo.",
]


PT_PER_MM = 72.0 / 25.4


def mm_to_pt(mm: float) -> float:
    return float(mm) * PT_PER_MM


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

        pdf.setDash()
        # Top pair
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
    text_color: Color = Color(0.45, 0.45, 0.45),
    spacing_em: float = 0.75,
) -> None:
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
        pdf.drawString(x, baseline_y, unit)
        x += unit_width


def fit_font_size_to_zone(font_name: str, base_font_size: float, zone_height: float) -> float:
    if base_font_size <= 0:
        base_font_size = 64.0
    ascent, descent = pdfmetrics.getAscentDescent(font_name, base_font_size)
    if ascent <= 0:
        return base_font_size
    scale = zone_height / float(ascent)
    size = base_font_size * scale
    return max(56.0, min(800.0, size))


def resolve_page_size(
    page_size: tuple[float, float],
    width_mm: float | None,
    height_mm: float | None,
) -> tuple[float, float]:
    if width_mm and height_mm:
        return (mm_to_pt(width_mm), mm_to_pt(height_mm))
    return page_size


def generate_pdf(
    output_path: Path,
    text: str,
    font_family: str = "Solway",
    font_weight: int = 400,
    page_size=A4,
    page_width_mm: float | None = None,
    page_height_mm: float | None = None,
    margin: float = 54.0,
    margin_mm: float | None = None,
    row_height: float = 0.0,
    row_height_mm: float | None = None,
    row_gap: float = 16.0,
    row_gap_mm: float | None = None,
    font_size: float = 64.0,
    pair_spacing: float = 4.0,
    pair_spacing_mm: float | None = None,
    fit_to_zone: bool = True,
) -> None:
    # Resolve page size (pt)
    width, height = resolve_page_size(page_size, page_width_mm, page_height_mm)

    # Resolve margins
    if margin_mm is not None and margin_mm > 0:
        margin = mm_to_pt(margin_mm)

    left_x = margin
    right_x = width - margin
    top_y = height - margin

    # Resolve geometry in pt
    if row_height_mm is not None and row_height_mm > 0:
        row_height = mm_to_pt(row_height_mm)
    if row_gap_mm is not None and row_gap_mm > 0:
        row_gap = mm_to_pt(row_gap_mm)
    if pair_spacing_mm is not None and pair_spacing_mm > 0:
        pair_spacing = mm_to_pt(pair_spacing_mm)

    if row_height is None or row_height <= 0:
        row_height = max(60.0, font_size)

    ttf_path = download_ttf_to_cache(font_family, font_weight)
    font_name = register_font_from_ttf_path(font_family, font_weight, ttf_path)

    usable_height = height - 2 * margin
    num_rows = max(1, int((usable_height + row_gap) // (row_height + row_gap)))

    pdf = canvas.Canvas(str(output_path), pagesize=(width, height))

    rows = draw_double_pair_lines(
        pdf,
        left_x=left_x,
        right_x=right_x,
        top_y=top_y,
        row_height=row_height,
        num_rows=num_rows,
        line_color=Color(0.85, 0.85, 0.85),
        solid_width=1.4 if width > 2 * A4[0] else 1.2,
        pair_spacing=pair_spacing,
        row_gap=row_gap,
    )

    sequence: list[str] = [TRACE_UPPER, TRACE_LOWER, *TRACE_WORDS_PL, TRACE_DIGITS] if not text else [text]

    if rows:
        _, y_top_inner0, y_bottom_inner0, _ = rows[0]
        zone_height = (y_top_inner0 - y_bottom_inner0)
        if fit_to_zone:
            font_size = fit_font_size_to_zone(font_name, font_size, zone_height)

    for idx, (y_top_outer, y_top_inner, y_bottom_inner, y_bottom_outer) in enumerate(rows):
        if idx % 2 == 0:
            baseline = y_bottom_inner
            content = sequence[idx % len(sequence)]
            draw_repeated_trace_text(
                pdf,
                text=content,
                font_name=font_name,
                font_size=font_size,
                left_x=left_x + pair_spacing * 2,
                right_x=right_x - pair_spacing * 2,
                baseline_y=baseline,
                text_color=Color(0.45, 0.45, 0.45),
                spacing_em=1.0,
            )

    pdf.setFillColor(Color(0.5, 0.5, 0.5))
    pdf.setFont("Helvetica", 8)
    footer = "Liniatura podwójna (typ C) • baseline = dolna linia wewnętrzna • Solway"
    pdf.drawRightString(right_x, margin * 0.5, footer)

    pdf.showPage()
    pdf.save()


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generuj karty/plakaty do pisania: liniatura podwójna (typ C) z czcionką Solway.")
    parser.add_argument("--text", type=str, default="", help="Tekst do śledzenia (jeśli pusty: alfabet, zdania, cyfry)")
    parser.add_argument("--output", type=str, default="output/worksheet.pdf", help="Ścieżka wyjściowego PDF")
    parser.add_argument("--font-family", type=str, default="Solway", help="Nazwa rodziny z Google Fonts")
    parser.add_argument("--font-weight", type=int, default=400, help="Grubość czcionki (Google Fonts)")

    # Page size (choose either A4 default or width/height in mm)
    parser.add_argument("--page-width-mm", type=float, default=0.0, help="Szerokość strony w mm (np. 2000)")
    parser.add_argument("--page-height-mm", type=float, default=0.0, help="Wysokość strony w mm (np. 1000)")

    # Margins and geometry in pt or mm
    parser.add_argument("--margin", type=float, default=54.0, help="Margines w pt")
    parser.add_argument("--margin-mm", type=float, default=0.0, help="Margines w mm (jeśli >0, nadpisuje --margin)")

    parser.add_argument("--row-height", type=float, default=0.0, help="Wysokość wiersza w pt; 0 = równa rozmiarowi czcionki")
    parser.add_argument("--row-height-mm", type=float, default=0.0, help="Wysokość wiersza w mm")

    parser.add_argument("--row-gap", type=float, default=16.0, help="Odstęp między wierszami w pt")
    parser.add_argument("--row-gap-mm", type=float, default=0.0, help="Odstęp między wierszami w mm")

    parser.add_argument("--font-size", type=float, default=64.0, help="Początkowy rozmiar czcionki w pt (dopasowywany do strefy)")

    parser.add_argument("--pair-spacing", type=float, default=4.0, help="Odstęp wewnątrz pary linii (pt)")
    parser.add_argument("--pair-spacing-mm", type=float, default=0.0, help="Odstęp wewnątrz pary linii w mm")

    parser.add_argument("--no-fit-to-zone", dest="fit_to_zone", action="store_false", help="Nie dopasowuj rozmiaru do wysokości strefy")
    parser.set_defaults(fit_to_zone=True)
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
            page_size=A4,
            page_width_mm=args.page_width_mm if args.page_width_mm > 0 else None,
            page_height_mm=args.page_height_mm if args.page_height_mm > 0 else None,
            margin=args.margin,
            margin_mm=args.margin_mm if args.margin_mm > 0 else None,
            row_height=args.row_height,
            row_height_mm=args.row_height_mm if args.row_height_mm > 0 else None,
            row_gap=args.row_gap,
            row_gap_mm=args.row_gap_mm if args.row_gap_mm > 0 else None,
            font_size=args.font_size,
            pair_spacing=args.pair_spacing,
            pair_spacing_mm=args.pair_spacing_mm if args.pair_spacing_mm > 0 else None,
            fit_to_zone=args.fit_to_zone,
        )
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"Saved: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))