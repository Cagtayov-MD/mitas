import sys
import xml.etree.ElementTree as ET
from fpdf import FPDF

def create_pdf(xml_path, pdf_path):
    tree = ET.parse(xml_path)
    root = tree.getroot()

    directors = []
    actors = []
    synopsis = ""
    title = ""
    subtitle = ""

    # Parse XML
    for prop in root.findall(".//PROPERTY"):
        name = prop.get("NAME")
        
        # Check for roles (Directors, Actors)
        if name == "JT:V_ROLE:V_ROL":
            bean = prop.find("BEAN")
            if bean is not None:
                first_name = ""
                last_name = ""
                role_type = ""
                for p in bean.findall("PROPERTY"):
                    p_name = p.get("NAME")
                    if p_name == "V_ROL_FIRST" and p.text:
                        first_name = p.text
                    elif p_name == "V_ROL_LAST" and p.text:
                        last_name = p.text
                    elif p_name == "V_ROLE_TYPE" and p.text:
                        role_type = p.text
                
                full_name = f"{first_name} {last_name}".strip()
                if role_type == "YÖNETMEN":
                    directors.append(full_name)
                elif role_type == "OYUNCU":
                    actors.append(full_name)
                    
        # Check for description (Synopsis, Title)
        elif name == "JT:EDC_DUBLIN_CORE:DC_DESCRIPTION":
            bean = prop.find("BEAN")
            if bean is not None:
                for p in bean.findall("PROPERTY"):
                    p_name = p.get("NAME")
                    if p_name == "DM_SYNOPSIS" and p.text:
                        synopsis = p.text
                    elif p_name == "DM_TITLE" and p.text:
                        title = p.text
                    elif p_name == "DM_SUBTITLE" and p.text:
                        subtitle = p.text

    # Generate PDF
    pdf = FPDF()
    pdf.add_page()
    
    # Use DejaVu font for Turkish characters
    font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    try:
        pdf.add_font("DejaVu", "", font_path)
        pdf.set_font("DejaVu", size=12)
    except Exception as e:
        print(f"Warning: Could not load DejaVu font, using default. Error: {e}")
        pdf.set_font("Arial", size=12)

    def add_section(title_text, content):
        pdf.set_font("DejaVu", size=14)
        pdf.cell(200, 10, text=title_text, new_x="LMARGIN", new_y="NEXT", align="L")
        pdf.set_font("DejaVu", size=12)
        pdf.multi_cell(0, 10, text=content)
        pdf.ln(5)

    if title or subtitle:
        display_title = title
        if subtitle:
            display_title += f" / {subtitle}"
        add_section("Film Adı:", display_title)

    if directors:
        add_section("Yönetmen(ler):", ", ".join(directors))
    else:
        add_section("Yönetmen:", "Bulunamadı")

    if actors:
        add_section("Oyuncular:", ", ".join(actors))
    else:
        add_section("Oyuncular:", "Bulunamadı")

    if synopsis:
        add_section("Özet:", synopsis)
    else:
        add_section("Özet:", "Bulunamadı")

    pdf.output(pdf_path)
    print(f"Başarıyla PDF oluşturuldu: {pdf_path}")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Kullanım: python xml_to_pdf.py <girdi_xml> <çıktı_pdf>")
        sys.exit(1)
        
    xml_file = sys.argv[1]
    pdf_file = sys.argv[2]
    
    create_pdf(xml_file, pdf_file)
