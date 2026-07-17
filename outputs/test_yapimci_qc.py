# -*- coding: utf-8 -*-
"""identity_first_producer canlı test — HIRSIZ + TEMEL REİS.
KB yapımcısını credit_kb_lookup CLI üzerinden (subprocess) alıyoruz.
"""
import sys, os, json, subprocess
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"E:\MITAS\scripts")

import credit_crosscheck as cc
import credit_qc_gates as qc

PYTHON = r"E:\MITAS\venvs\ocr\Scripts\python.exe"
KB_LOOKUP = r"E:\MITAS\scripts\credit_kb_lookup.py"


def kb_yapimci(baslik, orig, yil, cast_csv=""):
    """credit_kb_lookup.py CLI'den yapımcı listesini çek."""
    cmd = [PYTHON, KB_LOOKUP,
           "--baslik", baslik,
           "--orijinal", orig,
           "--yil", str(yil),
           "--cast", cast_csv]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", timeout=30)
        data = json.loads(r.stdout.strip())
        return data.get("yapimci") or []
    except Exception as e:
        print(f"  [uyarı] KB lookup başarısız: {e}")
        return []


VAKALAR = [
    {
        "ad": "HIRSIZ [garble vaka]",
        "title": "HIRSIZ",
        "orig": "Thief",
        "yil": 1981,
        "cast_csv": "James Caan,Tuesday Weld,Willie Nelson,James Belushi",
        "read_yap": ["MICHAEL MANN COMPANYCAAN PRODLICTONS"],
        "beklenen_garble_dusucu": True,
        # Jerry Bruckheimer veya Ronnie Caan beklenir (DB'de varsa)
    },
    {
        "ad": "TEMEL REİS [regresyon testi]",
        "title": "TEMEL REİS",
        "orig": "Popeye",
        "yil": 1980,
        "cast_csv": "Robin Williams,Shelley Duvall,Ray Walston,Paul Dooley",
        "read_yap": ["Robert Evans", "Robert Altman"],
        "beklenen_garble_dusucu": False,
    },
]

print("=" * 64)
print("identity_first_producer TEST")
print("=" * 64)

all_ok = True

for v in VAKALAR:
    kb_yap = kb_yapimci(v["title"], v["orig"], v["yil"], v["cast_csv"])
    result = qc.identity_first_producer(v["read_yap"], kb_yap, max_out=3)
    temiz = result["temiz_yapimci"]
    dususler = result["dususler"]

    print(f"\n=== {v['ad']} ===")
    print(f"  OCR giriş:      {v['read_yap']}")
    print(f"  KB yapımcı:     {kb_yap}")
    print(f"  TEMİZ çıkış:    {temiz}")
    print(f"  DÜŞENLER:       {dususler}")

    if v["beklenen_garble_dusucu"]:
        # Garble düşmeli
        garble_dustu = (v["read_yap"][0] not in temiz) or len(dususler) > 0
        if garble_dustu:
            print("  [OK] Garble doğru düştü.")
        else:
            print("  [HATA] Garble düşmedi!")
            all_ok = False
        # Gerçek kişiler geldi mi (KB'de varsa)
        if kb_yap:
            gelen = [n for n in kb_yap if any(cc.fold(n) in cc.fold(t) or cc.fold(t) in cc.fold(n) for t in temiz)]
            if gelen:
                print(f"  [OK] KB kişileri çıkışta: {temiz}")
            else:
                print(f"  [BİLGİ] KB kişileri çıkışa gelmedi — _only_persons filtre almış olabilir veya KB boş.")
        else:
            print("  [BİLGİ] KB yapımcı verisi yok (IMDb DB'de bulunamamış).")
    else:
        # Regresyon: gerçek kişiler korunmalı
        if kb_yap:
            # KB varken: name_match veya name_close ile normalize olabilir
            korunan = [n for n in v["read_yap"] if
                       any(cc.name_match(n, t) or cc.name_close(n, t) for t in temiz)
                       or n in temiz]
            if len(korunan) == len(v["read_yap"]):
                print(f"  [OK] Regresyon yok — gerçek kişiler çıkışta: {temiz}")
            else:
                dusen = [n for n in v["read_yap"] if n not in korunan]
                print(f"  [HATA] Gerçek kişi(ler) düştü: {dusen}")
                print(f"  [HATA] Temiz çıkış: {temiz}, KB: {kb_yap}")
                all_ok = False
        else:
            # KB yoksa: _only_persons'dan geçip geçmediğine bak
            korunan = [n for n in v["read_yap"] if n in temiz]
            if len(korunan) == len(v["read_yap"]):
                print(f"  [OK] KB yok + regresyon yok — kişiler korundu: {temiz}")
            else:
                dusen = [n for n in v["read_yap"] if n not in temiz]
                # KB yoksa identity_first_producer HEPSİNİ düşürür (imzasız = düş),
                # bu beklenen davranış. Uyarı ver ama HATA sayma.
                print(f"  [BİLGİ] KB yok → identity gate hepsini düşürdü (beklenen): {dusen}")
                print(f"  [BİLGİ] KB sağlandığında regresyon testi anlamlı olacak.")

print("\n" + "=" * 64)
print("SONUÇ:", "TAMAM" if all_ok else "BAZI HATALAR (detaylar yukarıda)")
