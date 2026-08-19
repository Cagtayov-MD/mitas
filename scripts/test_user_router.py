# -*- coding: utf-8 -*-
"""
DİL TESPİT VE YÖNLENDİRME (ROUTER) TEST SCRIPTİ
"""
import cv2
import pytesseract
import glob
import os
from paddleocr import PaddleOCR

def detect_script(image_path: str) -> str:
    """Görüntüye bakıp alfabeyi tespit eder (OCR yapmadan, çok hızlı)."""
    try:
        img = cv2.imread(image_path)
        if img is None:
            return None
        # --psm 0 = Orientation and Script Detection (Sadece alfabe tespiti)
        osd = pytesseract.image_to_osd(img, config='--psm 0', output_type=pytesseract.Output.DICT)
        script = osd.get('script', 'Latin')
        return script
    except Exception as e:
        print(f"  [Tesseract Hata]: {e}")
        return None

def main():
    frames_dir = "/home/cagatay/Programlar/mitas/Database/DOLUNAY ZAMANI 2019-1055-1-0000-50-0/frames/cikis"
    
    # Özellikle Arapça jeneriğin aktığı kareleri deneyelim (c_0472.png, c_0500.png, c_0553.png, c_0600.png)
    sample_frames = [
        os.path.join(frames_dir, "c_0472.png"),
        os.path.join(frames_dir, "c_0500.png"),
        os.path.join(frames_dir, "c_0553.png"),
        os.path.join(frames_dir, "c_0600.png"),
        os.path.join(frames_dir, "c_0650.png"),
    ]

    print("--- 1. ADIM: DİL VE ALFABE TESPİTİ (Tesseract OSD) ---")
    detected_scripts = []
    for p in sample_frames:
        if not os.path.exists(p): continue
        frame_name = os.path.basename(p)
        print(f"\nInceleniyor: {frame_name}")
        script = detect_script(p)
        if script:
            print(f"Kare: {frame_name} -> Tespit Edilen Alfabe: {script}")
            detected_scripts.append(script)
        else:
            print(f"Kare: {frame_name} -> Yazı bulunamadı/okunamadı.")

    # Karar Mekanizması (Routing)
    target_lang = "en"  # Varsayılan Latin
    if any(s in ["Arabic", "Hebrew", "Persian"] for s in detected_scripts):
        target_lang = "ar"
    elif any(s == "Cyrillic" for s in detected_scripts):
        target_lang = "ru"
    elif any(s in ["Chinese", "Japanese", "Korean", "Han"] for s in detected_scripts):
        target_lang = "ch"

    print(f"\n[ROUTER KARARI] Sistem bu jeneriği '{target_lang}' dili olarak işleyecek.")

    # 2. ADIM: DOĞRU OCR MOTORU İLE 1 KAREYİ OKUMA TESTİ
    print("\n--- 2. ADIM: SEÇİLEN OCR MOTORU İLE ÖRNEK OKUMA ---")
    print(f"PaddleOCR({target_lang}) başlatılıyor...")
    
    try:
        # PaddleOCR v4 parameter fix
        ocr_engine = PaddleOCR(use_textline_orientation=True, lang=target_lang)
        test_frame_path = os.path.join(frames_dir, "c_0553.png")
        print(f"Okunuyor: {os.path.basename(test_frame_path)}")
        
        img = cv2.imread(test_frame_path)
        result = ocr_engine.predict(img)

        if result and result[0]:
            print("\nOKUNAN METİNLER:")
            for line in result[0]:
                text = line[1][0] if isinstance(line, (list, tuple)) and len(line) > 1 else str(line)
                print(f" -> {text}")
        else:
            print("Bu karede metin bulunamadı.")
    except Exception as e:
        print(f"PaddleOCR çalıştırma hatası: {e}")

if __name__ == "__main__":
    main()
