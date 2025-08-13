from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.colors import gray, black, Color
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import requests
import re
from io import BytesIO

def get_ttf_url_from_google_fonts(font_family, weight=400):
    font_family_url = font_family.replace(" ", "+")
    api_url = f"https://fonts.googleapis.com/css2?family={font_family_url}:wght@{weight}"
    try:
        response = requests.get(api_url, headers={'User-Agent': 'Mozilla/5.0'})
        response.raise_for_status()
        css_content = response.text
        ttf_url = re.search(r'url\((https://fonts.gstatic.com/s/.*?ttf)\)', css_content)
        if ttf_url:
            return ttf_url.group(1)
        else:
            raise Exception("No TTF URL found in Google Fonts CSS")
    except requests.RequestException as e:
        raise Exception(f"Failed to fetch CSS from Google Fonts: {e}")

def create_handwriting_worksheet(font_url, output_filename):
    try:
        response = requests.get(font_url)
        response.raise_for_status()
        font_data = BytesIO(response.content)
    except requests.RequestException as e:
        raise Exception(f"Failed to download font from {font_url}: {e}")

    pdfmetrics.registerFont(TTFont("Solway", font_data))
    c = canvas.Canvas(output_filename, pagesize=A4)
    width, height = A4

    # Settings
    font_size = 20
    line_spacing = 30
    x_start = 50
    y_start = height - 50
    dash_pattern = (3, 3)
    width_available = width - 2 * x_start

    c.setStrokeColor(Color(0.8, 0.8, 0.8))  # Lighter color for lines

    # Page 1: Lowercase letters
    c.setFillColor(gray)
    c.drawString(50, height - 30, "Lowercase Handwriting")
    c.setFont("Solway", font_size)
    y = y_start
    for letter in 'abcdefghijklmnopqrstuvwxyz':
        if y - 20 < 50:  # Adjust for the height of the lines
            c.showPage()
            c.setStrokeColor(Color(0.8, 0.8, 0.8))
            c.setFillColor(gray)
            c.drawString(50, height - 30, "Lowercase Handwriting")
            y = y_start
        # Fill the line with repeated letters
        single_width = c.stringWidth(letter, "Solway", font_size)
        num = max(1, int(width_available / single_width))
        text = letter * num
        # Draw lines
        top_y = y
        middle_y = y - 10
        bottom_y = y - 20
        c.line(x_start, top_y, width - x_start, top_y)  # Top solid
        c.setDash(dash_pattern)
        c.line(x_start, middle_y, width - x_start, middle_y)  # Middle dashed
        c.setDash()
        c.line(x_start, bottom_y, width - x_start, bottom_y)  # Bottom solid
        # Draw text with baseline on bottom line
        c.drawString(x_start, bottom_y, text)
        y -= line_spacing

    # Page 2+: Sentences for lowercase practice
    c.showPage()
    c.setFillColor(gray)
    c.drawString(50, height - 30, "Lowercase Handwriting Sentences")
    c.setFont("Solway", font_size)
    sentences = [
        "the quick brown fox jumps over the lazy dog.",
        "pack my box with five dozen liquor jugs.",
        "jackdaws love my big sphinx of quartz.",
        "the five boxing wizards jump quickly.",
        "waltz, bad nymph, for quick jigs vex."
    ] * 4  # Repeat to add more content, total 20 sentences
    y = y_start
    for sentence in sentences:
        if y - 20 < 50:
            c.showPage()
            c.setStrokeColor(Color(0.8, 0.8, 0.8))
            c.setFillColor(gray)
            c.drawString(50, height - 30, "Lowercase Handwriting Sentences")
            y = y_start
        # Draw lines
        top_y = y
        middle_y = y - 10
        bottom_y = y - 20
        c.line(x_start, top_y, width - x_start, top_y)  # Top solid
        c.setDash(dash_pattern)
        c.line(x_start, middle_y, width - x_start, middle_y)  # Middle dashed
        c.setDash()
        c.line(x_start, bottom_y, width - x_start, bottom_y)  # Bottom solid
        # Draw text with baseline on bottom line
        c.drawString(x_start, bottom_y, sentence)
        y -= line_spacing

    # Page 3: Uppercase letters
    c.showPage()
    c.setFillColor(gray)
    c.drawString(50, height - 30, "Uppercase Handwriting")
    c.setFont("Solway", font_size)
    y = y_start
    for letter in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ':
        if y - 20 < 50:
            c.showPage()
            c.setStrokeColor(Color(0.8, 0.8, 0.8))
            c.setFillColor(gray)
            c.drawString(50, height - 30, "Uppercase Handwriting")
            y = y_start
        # Fill the line with repeated letters
        single_width = c.stringWidth(letter, "Solway", font_size)
        num = max(1, int(width_available / single_width))
        text = letter * num
        # Draw lines
        top_y = y
        middle_y = y - 10
        bottom_y = y - 20
        c.line(x_start, top_y, width - x_start, top_y)  # Top solid
        c.setDash(dash_pattern)
        c.line(x_start, middle_y, width - x_start, middle_y)  # Middle dashed
        c.setDash()
        c.line(x_start, bottom_y, width - x_start, bottom_y)  # Bottom solid
        # Draw text with baseline on bottom line
        c.drawString(x_start, bottom_y, text)
        y -= line_spacing

    # Add Uppercase sentences for more content
    c.showPage()
    c.setFillColor(gray)
    c.drawString(50, height - 30, "Uppercase Handwriting Sentences")
    c.setFont("Solway", font_size)
    uppercase_sentences = [
        "THE QUICK BROWN FOX JUMPS OVER THE LAZY DOG.",
        "PACK MY BOX WITH FIVE DOZEN LIQUOR JUGS.",
        "JACKDAWS LOVE MY BIG SPHINX OF QUARTZ.",
        "THE FIVE BOXING WIZARDS JUMP QUICKLY.",
        "WALTZ, BAD NYMPH, FOR QUICK JIGS VEX."
    ] * 4  # Repeat to add more content, total 20 sentences
    y = y_start
    for sentence in uppercase_sentences:
        if y - 20 < 50:
            c.showPage()
            c.setStrokeColor(Color(0.8, 0.8, 0.8))
            c.setFillColor(gray)
            c.drawString(50, height - 30, "Uppercase Handwriting Sentences")
            y = y_start
        # Draw lines
        top_y = y
        middle_y = y - 10
        bottom_y = y - 20
        c.line(x_start, top_y, width - x_start, top_y)  # Top solid
        c.setDash(dash_pattern)
        c.line(x_start, middle_y, width - x_start, middle_y)  # Middle dashed
        c.setDash()
        c.line(x_start, bottom_y, width - x_start, bottom_y)  # Bottom solid
        # Draw text with baseline on bottom line
        c.drawString(x_start, bottom_y, sentence)
        y -= line_spacing

    c.setStrokeColor(black)  # Reset stroke color if needed
    c.save()
    print(f"Worksheet saved as: {output_filename}")

try:
    font_url = get_ttf_url_from_google_fonts("Solway", weight=400)
    print(f"Downloading font from: {font_url}")
    create_handwriting_worksheet(
        font_url=font_url,
        output_filename="handwriting_worksheet.pdf"
    )
except Exception as e:
    print(f"Error: {e}")
