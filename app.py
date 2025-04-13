from flask import Flask, render_template, request, send_file, jsonify
import json
import os
import pandas as pd
from fpdf import FPDF
from docx import Document
from docx.shared import Inches, Pt

app = Flask(__name__)

# JSON-Datei laden mit Fehlerbehandlung
def load_json():
    try:
        if not os.path.exists("run_Anhang.json"):
            return {}

        with open("run_Anhang.json", "r", encoding="utf-8") as file:
            return json.load(file)
    except (json.JSONDecodeError, IOError) as e:
        print(f"Fehler beim Laden der JSON-Datei: {e}")
        return {}

# Startseite mit Filtermöglichkeiten
@app.route('/')
def index():
    data = load_json()
    categories = list(data.keys()) if data else []  # Themenbereiche
    return render_template("index.html", categories=categories)

# Gefilterte Anforderungen anzeigen
@app.route('/filter', methods=['POST'])
def filter_data():
    data = load_json()
    selected_grades = request.form.getlist("umsetzungsgrad")
    selected_category = request.form.get("category", "").strip()

    if not selected_category or selected_category not in data:
        return jsonify({"error": "Ungültige Kategorie"}), 400

    filtered = [req for req in data[selected_category] if req["Umsetzungsgrad"] in selected_grades]
    return jsonify(filtered)

def create_word_document(filtered_data, full_description=False):
    doc = Document()
    section = doc.sections[0]
    section.orientation = 1  # Querformat
    section.page_width = Inches(11.69)
    section.page_height = Inches(8.27)

    doc.add_heading("Checkliste", level=1)

    table = doc.add_table(rows=1, cols=4)
    table.style = "Table Grid"

    # Spaltenbreite einstellen
    table.columns[0].width = Inches(1)  # Schmale Spalte
    table.columns[2].width = Inches(1)  # Schmale Spalte

    hdr_cells = table.rows[0].cells
    hdr_cells[0].text = "Anforderungsnr."
    hdr_cells[1].text = "Name"
    hdr_cells[2].text = "Umsetzungsgrad"
    hdr_cells[3].text = "Status"

    last_integer = None
    for item in filtered_data:
        current_number = item['Anforderungsnummer']
        
        # Prüfen, ob die Anforderungsnummer einen Punkt enthält
        if '.' in str(current_number):
            current_integer = int(str(current_number).split('.')[0])
            if current_integer != last_integer:
                # Neue Zeile für die Integer-Nummer und den Namen hinzufügen
                integer_row = table.add_row().cells
                integer_row[0].text = str(current_integer)
                paragraph = integer_row[1].paragraphs[0]
                run = paragraph.add_run(item['Name'])
                run.bold = True
                integer_row[2].text = ""
                integer_row[3].text = ""
                last_integer = current_integer

            # Zeile für den Unterpunkt hinzufügen
            row_cells = table.add_row().cells
            row_cells[0].text = str(current_number)
            paragraph = row_cells[1].paragraphs[0]
            if full_description:
                paragraph.add_run(item['Beschreibung'])
            else:
                first_sentence = item['Beschreibung'].split('.')[0] + '.'
                paragraph.add_run(first_sentence)
            row_cells[2].text = item['Umsetzungsgrad']
            row_cells[3].text = ""
        else:
            # Zeile für die Integer-Nummer ohne Unterpunkte
            row_cells = table.add_row().cells
            row_cells[0].text = str(current_number)
            paragraph = row_cells[1].paragraphs[0]
            run = paragraph.add_run(item['Name'])
            run.bold = True
            if full_description:
                paragraph.add_run(f"\n{item['Beschreibung']}")
            else:
                first_sentence = item['Beschreibung'].split('.')[0] + '.'
                paragraph.add_run(f"\n{first_sentence}")
            row_cells[2].text = item['Umsetzungsgrad']
            row_cells[3].text = ""

    return doc

# PDF-Export mit validierter Eingabe
@app.route('/export/pdf', methods=['POST'])
def export_pdf():
    try:
        filtered_data = json.loads(request.form.get("data", "[]"))
        if not isinstance(filtered_data, list) or not filtered_data:
            return jsonify({"error": "Keine Daten zum Exportieren"}), 400

        class PDF(FPDF):
            def footer(self):
                self.set_y(-15)
                self.set_font('Arial', 'I', 8)
                self.cell(0, 10, 'Erstellt auf Basis Anlage BSI RUN, Stand 2025', 0, 0, 'C')
                self.ln(5)
                self.cell(0, 10, 'Disclaimer: Es wird keine Gewähr für die Richtigkeit der Daten übernommen.', 0, 0, 'C')

        pdf = PDF(orientation="L", unit="mm", format="A4")  # Querformat
        pdf.add_page()

        # Standard Arial-Schriftart für FPDF
        pdf.set_font('Arial', size=12)
        pdf.cell(0, 10, "Checkliste", ln=True, align="C")
        pdf.ln(10)

        # Kopfzeile
        pdf.cell(30, 10, "Anforderungsnr.", 1)
        pdf.cell(100, 10, "Name", 1)
        pdf.cell(30, 10, "Umsetzungsgrad", 1)
        pdf.cell(70, 10, "Status", 1)
        pdf.ln()

        # Datenzeilen
        for item in filtered_data:
            name_text = item['Name']
            lines = pdf.multi_cell(100, 10, name_text, border=0, split_only=True)
            name_height = len(lines) * 10
            row_height = max(10, name_height)

            if pdf.get_y() + row_height > pdf.page_break_trigger:
                pdf.add_page()
                pdf.cell(30, 10, "Anforderungsnr.", 1)
                pdf.cell(100, 10, "Name", 1)
                pdf.cell(30, 10, "Umsetzungsgrad", 1)
                pdf.cell(70, 10, "Status", 1)
                pdf.ln()

            y_before = pdf.get_y()
            pdf.cell(30, row_height, str(item['Anforderungsnummer']), 1)
            x, y = pdf.get_x(), pdf.get_y()  # speichere aktuelle Position
            pdf.multi_cell(100, 10, name_text, 1)
            y_after = pdf.get_y()
            row_height = y_after - y_before

            pdf.set_xy(x + 100, y_before)  # setze X-Position nach Namensfeld, Y bleibt gleich
            pdf.cell(30, row_height, item['Umsetzungsgrad'], 1)
            pdf.cell(70, row_height, "", 1)  # Leeres Feld ohne Häkchen
            pdf.ln(row_height)

        pdf_path = "checkliste.pdf"
        pdf.output(pdf_path)
        return send_file(pdf_path, as_attachment=True)

    except Exception as e:
        return jsonify({"error": f"Fehler beim Exportieren: PDF"}), 500

# Word-Export Variante 1
@app.route('/export/word_variante1', methods=['POST'])
def export_word_variante1():
    try:
        filtered_data = json.loads(request.form.get("data", "[]"))
        if not isinstance(filtered_data, list) or not filtered_data:
            return jsonify({"error": "Keine Daten zum Exportieren"}), 400

        doc = create_word_document(filtered_data, full_description=False)
        doc_path = "checkliste_variante1.docx"
        doc.save(doc_path)
        return send_file(doc_path, as_attachment=True)

    except Exception as e:
        return jsonify({"error": f"Fehler beim Exportieren: Word Variante 1"}), 500

# Word-Export Variante 2
@app.route('/export/word_variante2', methods=['POST'])
def export_word_variante2():
    try:
        filtered_data = json.loads(request.form.get("data", "[]"))
        if not isinstance(filtered_data, list) or not filtered_data:
            return jsonify({"error": "Keine Daten zum Exportieren"}), 400

        doc = create_word_document(filtered_data, full_description=True)
        doc_path = "checkliste_variante2.docx"
        doc.save(doc_path)
        return send_file(doc_path, as_attachment=True)

    except Exception as e:
        return jsonify({"error": f"Fehler beim Exportieren: Word Variante 2"}), 500

if __name__ == '__main__':
    app.run(debug=False)
