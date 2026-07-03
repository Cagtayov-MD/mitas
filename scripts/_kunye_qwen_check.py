# -*- coding: utf-8 -*-
"""KÜNYE PDF — gemma-vision KATI doğrulama (2026-06-23: qwen2.5vl → gemma-4-31b-it-qat-vision; TEK MODEL).
NOT: dosya adı tarihsel ('qwen'); mitas_pipeline importu kırılmasın diye değişmedi.
PDF önizleme PNG'sine bakıp kullanıcının 6 beklentisini SADECE-gördüğünü kuralıyla kontrol eder.
Kullanım: python _kunye_qwen_check.py <kunye_onizleme.png>
Çıktı: JSON {ozet_var, oyuncu_sayisi, yapimci_var, yonetmen_var, ses_dil_var, afis_var,
             hepsi_buyuk_harf, turkce_karakter_dogru, notlar}
"""
import sys, os, json, base64
from pathlib import Path
from _ollama import ollama_chat

OLLAMA_HOST = "http://127.0.0.1:11434"
MODEL = "gemma-4-31b-it-qat-vision:latest"
PROMPT = (
    "Bu bir MİTAS içerik künye belgesinin görüntüsü. ÇOK KATI ol. SADECE GÖRDÜĞÜNÜ "
    "değerlendir; tahmin, varsayım, uydurma KESİNLİKLE YOK. Emin değilsen false yaz.\n"
    "Şu maddeleri tek tek kontrol et ve YALNIZCA geçerli JSON döndür (başka hiçbir metin yok):\n"
    "{\n"
    '  "ozet_var": true|false,              // ÖZET bölümü GERÇEK metinle dolu mu (placeholder/parantez ise false)\n'
    '  "oyuncu_sayisi": <tamsayi>,          // OYUNCULAR bölümündeki kişi adedi\n'
    '  "yapimci_var": true|false,           // YAPIM EKİBİ -> Yapımcı satırı dolu mu\n'
    '  "yonetmen_var": true|false,          // YAPIM EKİBİ -> Yönetmen satırı dolu mu\n'
    '  "ses_dil_var": true|false,           // SES & ALTYAZI / ANA DİL bilgisi dolu mu (— degil)\n'
    '  "afis_var": true|false,              // sayfada afiş/poster GÖRSELİ var mı\n'
    '  "hepsi_buyuk_harf": true|false,      // OYUNCULAR+YAPIM EKİBİ isimleri TAMAMEN BÜYÜK harf mi\n'
    '  "turkce_karakter_bozuk_var": true|false, // İ/Ş/Ç/Ğ/Ö/Ü yerine bozuk/yanlış karakter var mı\n'
    '  "latin_disi_alfabe_var": true|false,  // Latin DISI alfabe harfi GORUYOR musun: Kiril (Ж Д И), Yunan (Ω Δ), Arap (ع), Cince/Japon/Kore (中 日 한). Kunye SADECE Latin olmali; boyle bir harf varsa true\n'
    '  "yabanci_ad_ascii_degil": true|false, // Acikca YABANCI (Turk olmayan) bir kisi adinda ASCII disi harf var mi: JEAN-PİERRE, DARROUSSİN, ANDRÉ, WİLMS gibi. Turk kisi adinda ç ğ ı İ ö ş ü normaldir; yabanci kisi adi SADE ASCII olmali (JEAN-PIERRE, ANDRE, FRANCOIS, JOSE)\n'
    '  "notlar": "<kisa: eksik veya yanlis ne>"\n'
    "}\n/no_think"
)


def check(png_path: str) -> dict:
    b64 = base64.b64encode(Path(png_path).read_bytes()).decode()
    resp = ollama_chat(
        model=MODEL,
        prompt=PROMPT,
        images=[b64],
        fmt="json",
        timeout=300,
        host=OLLAMA_HOST,
        options={"temperature": 0},
        think=False,   # gemma-4 düşünme modeli → JSON `format` ile over-think çakışmasın
        keep_alive=os.environ.get("MITAS_OLLAMA_KEEP_ALIVE", "5m"),  # VRAM-hijyeni 2026-07-04 (byte-nötr; _ollama.py **extra)
    )
    if resp is None:
        return {}
    return json.loads(resp.get("response", "{}"))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("kullanim: python _kunye_qwen_check.py <kunye_onizleme.png>"); sys.exit(1)
    out = check(sys.argv[1])
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))
