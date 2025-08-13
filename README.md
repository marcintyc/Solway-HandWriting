# Solway-HandWriting

Static preview: GitHub Pages publishes `web/index.html` and the generated `worksheet.pdf` on each push to `main`.

Local run:

```
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python app/generate_worksheet.py --text "Aa Bb Cc" --output output/worksheet.pdf
```