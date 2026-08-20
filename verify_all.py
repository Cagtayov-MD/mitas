import os
import glob
import re
import json
import xml.etree.ElementTree as ET
from pypdf import PdfReader

def parse_xml(xml_path):
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
    except Exception as e:
        return None, f"XML Parse Hatası: {e}"

    directors = []
    actors = []
    synopsis = ""
    title = ""
    subtitle = ""

    for prop in root.findall(".//PROPERTY"):
        name = prop.get("NAME")
        
        if name == "JT:V_ROLE:V_ROL":
            bean = prop.find("BEAN")
            if bean is not None:
                first_name = ""
                last_name = ""
                role_type = ""
                for p in bean.findall("PROPERTY"):
                    p_name = p.get("NAME")
                    if p_name == "V_ROL_FIRST" and p.text:
                        first_name = p.text.strip()
                    elif p_name == "V_ROL_LAST" and p.text:
                        last_name = p.text.strip()
                    elif p_name == "V_ROLE_TYPE" and p.text:
                        role_type = p.text.strip()
                
                full_name = f"{first_name} {last_name}".strip()
                if role_type == "YÖNETMEN":
                    directors.append(full_name)
                elif role_type == "OYUNCU":
                    actors.append(full_name)
                    
        elif name == "JT:EDC_DUBLIN_CORE:DC_DESCRIPTION":
            bean = prop.find("BEAN")
            if bean is not None:
                for p in bean.findall("PROPERTY"):
                    p_name = p.get("NAME")
                    if p_name == "DM_SYNOPSIS" and p.text:
                        synopsis = p.text.strip()
                    elif p_name == "DM_TITLE" and p.text:
                        title = p.text.strip()
                    elif p_name == "DM_SUBTITLE" and p.text:
                        subtitle = p.text.strip()

    return {
        "directors": directors,
        "actors": actors,
        "synopsis": synopsis,
        "title": title,
        "subtitle": subtitle
    }, None

def extract_pdf_text(pdf_path):
    try:
        reader = PdfReader(pdf_path)
        full_text = ""
        for page in reader.pages:
            t = page.extract_text()
            if t:
                full_text += t + "\n"
        return full_text, None
    except Exception as e:
        return "", f"PDF Okuma Hatası: {e}"

def verify_file(xml_path, pdf_dir):
    basename = os.path.basename(xml_path)
    match = re.search(r"(\d{4}-\d{4}-\d+-\d+-\d+-\d+)-(.*?)\.xml", basename)
    if match:
        trt_id = match.group(1)
        name = match.group(2)
        pdf_name = f"{trt_id} {name}.pdf"
    else:
        pdf_name = basename.replace(".xml", ".pdf")

    pdf_path = os.path.join(pdf_dir, pdf_name)
    
    if not os.path.exists(pdf_path):
        return {
            "xml_file": basename,
            "pdf_file": pdf_name,
            "status": "MISSING_PDF",
            "errors": ["PDF dosyası bulunamadı."]
        }

    xml_data, xml_err = parse_xml(xml_path)
    if xml_err:
        return {
            "xml_file": basename,
            "pdf_file": pdf_name,
            "status": "XML_ERROR",
            "errors": [xml_err]
        }

    pdf_text, pdf_err = extract_pdf_text(pdf_path)
    if pdf_err:
        return {
            "xml_file": basename,
            "pdf_file": pdf_name,
            "status": "PDF_ERROR",
            "errors": [pdf_err]
        }

    errors = []
    
    # Normalize PDF text whitespace
    norm_pdf_text = re.sub(r'\s+', ' ', pdf_text)

    # 1. Yönetmen Doğrulama
    for d in xml_data["directors"]:
        norm_d = re.sub(r'\s+', ' ', d)
        if norm_d and norm_d not in norm_pdf_text:
            errors.append(f"Yönetmen eksik veya hatalı: '{d}' PDF içinde bulunamadı.")

    # 2. Oyuncu Doğrulama
    for a in xml_data["actors"]:
        norm_a = re.sub(r'\s+', ' ', a)
        if norm_a and norm_a not in norm_pdf_text:
            errors.append(f"Oyuncu eksik veya hatalı: '{a}' PDF içinde bulunamadı.")

    # 3. Özet Doğrulama
    if xml_data["synopsis"]:
        clean_xml_synopsis = re.sub(r'\s+', ' ', xml_data["synopsis"])
        if clean_xml_synopsis not in norm_pdf_text:
            xml_words = clean_xml_synopsis.split()
            missing_words = [w for w in xml_words if w not in norm_pdf_text]
            if len(missing_words) > 0:
                errors.append(f"Özet eşleşmedi ({len(missing_words)} kelime eksik). İlk eksik kelimeler: {missing_words[:5]}")

    status = "SUCCESS" if not errors else "MISMATCH"
    
    return {
        "xml_file": basename,
        "pdf_file": pdf_name,
        "status": status,
        "errors": errors,
        "directors_count": len(xml_data["directors"]),
        "actors_count": len(xml_data["actors"]),
        "has_synopsis": bool(xml_data["synopsis"])
    }

def main():
    xml_dir = "/mnt/trt_depo/Film Kapanış"
    pdf_dir = "/home/cagatay/Belgeler/pdfler"
    
    xml_files = glob.glob(os.path.join(xml_dir, "*.xml"))
    xml_files.sort()
    
    total = len(xml_files)
    print(f"Toplam {total} XML dosyası çapraz teyit için taranıyor...")
    
    results = []
    success_count = 0
    mismatch_count = 0
    missing_count = 0
    error_count = 0
    
    for idx, xml_path in enumerate(xml_files, 1):
        res = verify_file(xml_path, pdf_dir)
        results.append(res)
        
        st = res["status"]
        if st == "SUCCESS":
            success_count += 1
        elif st == "MISMATCH":
            mismatch_count += 1
            print(f"[{idx}/{total}] [UYUSMAZLIK] {res['xml_file']} -> {res['errors']}")
        elif st == "MISSING_PDF":
            missing_count += 1
            print(f"[{idx}/{total}] [EKSİK PDF] {res['xml_file']}")
        else:
            error_count += 1
            print(f"[{idx}/{total}] [HATA] {res['xml_file']} -> {res['errors']}")

        if idx % 100 == 0 or idx == total:
            print(f"İlerleme: {idx}/{total} - Tam Başarılı: {success_count}, Uyuşmazlık: {mismatch_count}, Eksik: {missing_count}, Hata: {error_count}")

    report_path = "/home/cagatay/Programlar/mitas/dogrulama_raporu.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
        
    print("\n--- ÇAPRAZ TEYİT VE DOĞRULAMA RAPORU ---")
    print(f"Toplam İncelenen XML: {total}")
    print(f"Birebir Eşleşen (Kusursuz): {success_count}")
    print(f"Uyuşmazlık Bulunan: {mismatch_count}")
    print(f"Eksik PDF: {missing_count}")
    print(f"Okuma/Ayrıştırma Hatası: {error_count}")
    print(f"Detaylı rapor kaydedildi: {report_path}")

if __name__ == "__main__":
    main()
