# -*- coding: utf-8 -*-
"""VL (credit_video_read, gemma4:26b+qwen2.5vl:7b, KARE girişi) vs METİN yolu karşılaştırması.
Metin yolunun ÇEKİMSER kaldığı (yönetmen okunamadı) filmlerde VL gerçek kareye bakıp
yönetmeni okuyabiliyor mu? Kareler: Database/<film>/frames/giris + /cikis."""
import glob, sys
sys.path.insert(0, r"E:\MITAS\scripts")
import credit_video_read as cv

# FIX: 36 kare × ~1000 token > 16384 → HTTP 400. num_ctx yükselt (qwen2.5vl 32k+ destekler).
cv.NUM_CTX = 40960
# Batch ile GPU paylaşımı: ağır gemma4:26b (17GB) yerine hafif qwen2.5vl:7b (6GB, vision) — OOM riski düşük.
VL_MODELS = ["qwen2.5vl:7b"]

# (TRT-id, GT yönetmen, metin-yolu-sonucu, ad)
FILMS = [
    ("1978-0178", "GEORGE ROY HILL", "[] (çekimser)", "Waldo Pepper"),
    ("1987-0248", "PETER HYAMS",     "[] (çekimser)", "Outland/Uzaydaki Sır"),
    ("1997-0280", "JOHN MOORE",      "[] (çekimser)", "Düşman Hattında"),
    ("1977-0211", "GEORGE LUCAS",    "GEORGE LUCAS",  "Star Wars (kontrol)"),
    ("1980-0191", "MICHAEL CIMINO",  "MİCHAEL CİMİNO","Cennetin Kapısı (kontrol)"),
]

kb = cv.KB()
print(f"{'FİLM':<26}{'GT':<16}{'METİN':<16}{'VL YÖNETMEN':<24}{'VL GÜVEN'}")
print("-"*100)
for fid, gt, txt, name in FILMS:
    base = glob.glob(rf"E:\MITAS\Database\evoArcadmin*{fid}*")
    if not base:
        print(f"{name:<26}— film klasörü yok"); continue
    giris = base[0] + r"\frames\giris"
    cikis = base[0] + r"\frames\cikis"
    try:
        res = cv.read_credits(giris if glob.os.path.isdir(giris) else None,
                              cikis if glob.os.path.isdir(cikis) else None, models=VL_MODELS, kb=kb)
        yon = res.get("yonetmen") or []
        cast = res.get("cast") or []
        print(f"{name:<26}{gt:<16}{txt:<16}{str(yon)[:23]:<24}{res.get('guven','')}")
        print(f"{'':<26}VL cast: {cast[:6]}")
    except Exception as e:
        print(f"{name:<26}{gt:<16}{txt:<16}HATA: {type(e).__name__}: {str(e)[:40]}")
print("-"*100)
print("SORU: VL, metin yolunun çekimser kaldığı 3 filmde yönetmeni KURTARDI mı, yoksa o da mı boş/yanlış?")
