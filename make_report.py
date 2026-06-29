import json
import unicodedata
from fpdf import FPDF
from datetime import date

# --- Read the log of supplements ---
with open("log.json", "r") as f:
    log = json.load(f)

# --- Create the PDF ---
pdf = FPDF()
pdf.add_page()

# Title
pdf.set_font("Helvetica", "B", 16)
pdf.cell(0, 10, "Supplement Record", new_x="LMARGIN", new_y="NEXT")

# Date generated
pdf.set_font("Helvetica", "", 10)
pdf.cell(0, 8, f"Generated: {date.today().strftime('%d %B %Y')}", new_x="LMARGIN", new_y="NEXT")
pdf.ln(4)

# --- Loop through each logged supplement ---
for entry in log:
    # Product name
    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(0, 9, entry["product_name"], new_x="LMARGIN", new_y="NEXT")

    # Form and directions
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, f"Form: {entry['form']}", new_x="LMARGIN", new_y="NEXT")
    pdf.multi_cell(0, 6, f"Directions: {entry['directions']}")
    pdf.ln(2)

    # Ingredients
    pdf.set_font("Helvetica", "", 10)
    for item in entry["ingredients"]:
        unit = item["unit"].replace("µg", "mcg").replace("μg", "mcg")
        line = f"  - {item['name']}: {item['amount']} {unit}"
        safe_line = line.encode("latin-1", "ignore").decode("latin-1")
        pdf.set_x(pdf.l_margin)
        pdf.multi_cell(pdf.epw, 6, safe_line)

    pdf.ln(6)  # space before the next supplement

# --- Save the PDF ---
pdf.output("supplement_report.pdf")
print("Done! Created supplement_report.pdf")
