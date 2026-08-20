import os
import sys
import glob
import re
import xml.etree.ElementTree as ET
from fpdf import FPDF

def create_pdf(xml_path, pdf_path):
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
    except Exception as e:
        print(f"XML parse error for {xml_path}: {e}")
        return False

    title = ""
    subtitle = ""

    # Parse XML for title/subtitle only
    for prop in root.findall(".//PROPERTY"):
        name = prop.get("NAME")
        if name == "JT:EDC_DUBLIN_CORE:DC_DESCRIPTION":
            bean = prop.find("BEAN")
            if bean is not None:
                for p in bean.findall("PROPERTY"):
                    p_name = p.get("NAME")
                    if p_name == "DM_TITLE" and p.text:
                        title = p.text.strip()
                    elif p_name == "DM_SUBTITLE" and p.text:
                        subtitle = p.text.strip()

    # Generate PDF with only Film Name
    pdf = FPDF()
    pdf.add_page()
    
    font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    try:
        pdf.add_font("DejaVu", "", font_path)
        pdf.set_font("DejaVu", size=14)
    except Exception as e:
        pdf.set_font("Arial", size=14)

    if title or subtitle:
        display_title = title
        if subtitle and subtitle != title:
            display_title += f" / {subtitle}"
    else:
        # Fallback to name from filename if missing in XML
        basename = os.path.basename(xml_path)
        match = re.search(r"(\d{4}-\d{4}-\d+-\d+-\d+-\d+)-(.*?)\.xml", basename)
        if match:
            display_title = match.group(2).replace("_", " ")
        else:
            display_title = basename.replace(".xml", "")

    pdf.cell(200, 10, text="Film Adı:", new_x="LMARGIN", new_y="NEXT", align="L")
    pdf.set_font("DejaVu", size=12)
    pdf.multi_cell(0, 10, text=display_title)

    try:
        pdf.output(pdf_path)
        return True
    except Exception as e:
        print(f"Error saving PDF {pdf_path}: {e}")
        return False

def main():
    input_dir = "/mnt/trt_depo/Film Kapanış"
    output_dir = "/home/cagatay/Belgeler/pdfler"
    os.makedirs(output_dir, exist_ok=True)
    
    xml_files = glob.glob(os.path.join(input_dir, "*.xml"))
    xml_files.sort()
    
    total = len(xml_files)
    print(f"Toplam {total} XML dosyası yeniden işleniyor (sadece film adı kalacak)...")
    
    success_count = 0
    for i, xml_path in enumerate(xml_files, 1):
        basename = os.path.basename(xml_path)
        
        match = re.search(r"(\d{4}-\d{4}-\d+-\d+-\d+-\d+)-(.*?)\.xml", basename)
        if match:
            trt_id = match.group(1)
            name = match.group(2)
            pdf_name = f"{trt_id} {name}.pdf"
        else:
            pdf_name = basename.replace(".xml", ".pdf")
            
        pdf_path = os.path.join(output_dir, pdf_name)
        
        if create_pdf(xml_path, pdf_path):
            success_count += 1
            
        if i % 100 == 0 or i == total:
            print(f"İlerleme: {i}/{total} PDF güncellendi.")
            
    print(f"\nİşlem tamamlandı. {total} PDF dosyasından {success_count} tanesi sadece film adı içerecek şekilde güncellendi.")

if __name__ == "__main__":
    main()
