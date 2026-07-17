# -*- coding: utf-8 -*-
import os, io, sys, json, glob
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
import fitz

PDFS = [
    r"E:\MITAS\Mitas Output\export\KONTROL\1999-0473-1-0000-00-1 ÖLÜM BÖLGESİ.pdf",
    r"E:\MITAS\Mitas Output\export\KONTROL\1969-0023-1-0000-90-1 MACKENNA'NIN ALTINLARI.pdf",
    r"E:\MITAS\Mitas Output\export\KONTROL\1970-0038-1-0000-40-1 İTALYA SAVAŞ İÇİNDE.pdf",
    r"E:\MITAS\Mitas Output\export\KONTROL\1984-0018-1-0000-40-1 KANUNSUZLAR.pdf",
    r"E:\MITAS\Mitas Output\export\KONTROL\1990-0950-1-0000-00-1 TEK BAŞINA MÜCADELE.pdf",
]
DB = r"E:\MITAS\Database"

def find_hub(trt):
    # trt_id ile _DURUM.json bul
    for d in glob.glob(os.path.join(DB, "*", "_DURUM.json")):
        try:
            j = json.load(open(d, encoding="utf-8"))
            if j.get("trt_id") == trt:
                return d, j
        except Exception:
            pass
    return None, None

for p in PDFS:
    name = os.path.basename(p)
    trt = name.split(" ", 1)[0]
    print("=" * 70)
    print(name)
    # PDF metni
    txt = ""
    try:
        doc = fitz.open(p)
        for pg in doc:
            txt += pg.get_text()
        doc.close()
    except Exception as e:
        print("  PDF okunamadı:", e)
    # Özet + ses bloklarını göster
    import re
    for blok, pat in [("ÖZET", r"(Özet|ÖZET)[\s\S]{0,400}"),
                      ("SES", r"(Ses|SES)[\s\S]{0,150}"),
                      ("YÖNETMEN", r"(Yönetmen|YÖNETMEN)[^\n]{0,80}")]:
        m = re.search(pat, txt)
        snip = (m.group(0)[:300].replace("\n", " ⏎ ") if m else "(BULUNAMADI)")
        print(f"  [{blok}] {snip}")
    # _DURUM.json nedeni
    d, j = find_hub(trt)
    if j:
        print(f"  >>> KARAR: {j.get('karar')}  NEDEN: {j.get('neden')}")
        print(f"  >>> ASR: {j.get('asr_status')} seg={j.get('asr_segments')} chars={j.get('transcript_chars')}")
        qq = j.get("qwen_qc") or {}
        print(f"  >>> qwen_qc: ozet_var={qq.get('ozet_var')} ses_dil_var={qq.get('ses_dil_var')} yon_var={qq.get('yonetmen_var')}")
        # chlang
        hub = os.path.dirname(d)
        cl = glob.glob(os.path.join(hub, "asr", "*", "run", "chlang.json"))
        if cl:
            clj = json.load(open(cl[0], encoding="utf-8"))
            sel = clj.get("selected", {})
            print(f"  >>> chlang: label={sel.get('label')} lang={sel.get('language')} conf={sel.get('confidence')} reason={clj.get('select_reason')}")
        else:
            print("  >>> chlang.json YOK")
    else:
        print("  >>> _DURUM.json BULUNAMADI (hub yok / farklı isim)")
    print()
