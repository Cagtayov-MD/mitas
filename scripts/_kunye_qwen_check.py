# -*- coding: utf-8 -*-
"""KÜNYE PDF — qwen2.5vl KATI doğrulama.
PDF önizleme PNG'sine bakıp kullanıcının 6 beklentisini SADECE-gördüğünü kuralıyla kontrol eder.
Kullanım: python _kunye_qwen_check.py <kunye_onizleme.png>
Çıktı: JSON {ozet_var, oyuncu_sayisi, yapimci_var, yonetmen_var, ses_dil_var, afis_var,
             hepsi_buyuk_harf, turkce_karakter_dogru, notlar}
"""
import sys, json, base64, urllib.request
from pathlib import Path

OLLAMA = "http://127.0.0.1:11434/api/generate"
MODEL = "qwen2.5vl:7b"
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
    '  "notlar": "<kisa: eksik veya yanlis ne>"\n'
    "}\n/no_think"
)


def check(png_path: str) -> dict:
    b64 = base64.b64encode(Path(png_path).read_bytes()).decode()
    body = json.dumps({
        "model": MODEL, "prompt": PROMPT, "images": [b64],
        "stream": False, "format": "json", "options": {"temperature": 0},
    }).encode("utf-8")
    req = urllib.request.Request(OLLAMA, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        resp = json.loads(r.read())
    return json.loads(resp.get("response", "{}"))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("kullanim: python _kunye_qwen_check.py <kunye_onizleme.png>"); sys.exit(1)
    out = check(sys.argv[1])
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))
