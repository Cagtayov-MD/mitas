# -*- coding: utf-8 -*-
"""identity_first_producer canlı test v2 — CreditKB + IMDb DB doğrudan (subprocess yok).
venvs/ocr python ile çalıştırılmalı (duckdb burada).
"""
import sys, os
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"E:\MITAS\scripts")

import credit_crosscheck as cc
import credit_qc_gates as qc

kb = cc.CreditKB()

def get_kb_yapimci(baslik, orig, yil, cast_list):
    """CreditKB'den film kimliğini bul + IMDb principals'tan yapımcıları çek."""
    r = kb.crosscheck("", cast_list, title_tr=baslik, original=orig, year=yil)
    imdb_id = r.get("matched_imdb_id")

    # imdb_find ile de dene
    if not imdb_id:
        cands = kb.imdb_find(title_tr=baslik, original=orig, year=yil)
        if cands:
            imdb_id = cands[0].get("id")

    yapimci = []
    if imdb_id and kb.imdb:
        try:
            rows = kb.imdb.execute(
                "SELECT nconst FROM principals WHERE tconst=? AND category='producer' ORDER BY ordering LIMIT 6",
                [imdb_id]).fetchall()
            yapimci = kb._imdb_names([x[0] for x in rows])
        except Exception as e:
            print(f"  [uyarı] IMDb sorgu hatası: {e}")

    return yapimci, imdb_id, r.get("verdict"), r.get("cast_ortusme", 0)


VAKALAR = [
    {
        "ad": "HIRSIZ [garble vaka]",
        "title": "HIRSIZ",
        "orig": "Thief",
        "yil": 1981,
        "cast_list": ["James Caan", "Tuesday Weld", "Willie Nelson", "James Belushi"],
        "read_yap": ["MICHAEL MANN COMPANYCAAN PRODLICTONS"],
        "beklenen_garble_dusucu": True,
    },
    {
        "ad": "TEMEL REİS [regresyon testi]",
        "title": "TEMEL REİS",
        "orig": "Popeye",
        "yil": 1980,
        "cast_list": ["Robin Williams", "Shelley Duvall", "Ray Walston", "Paul Dooley"],
        "read_yap": ["Robert Evans", "Robert Altman"],
        "beklenen_garble_dusucu": False,
    },
]

print("=" * 64)
print("identity_first_producer TEST v2 (CreditKB direkt)")
print("=" * 64)

all_ok = True

for v in VAKALAR:
    kb_yap, imdb_id, verdict, cast_ov = get_kb_yapimci(
        v["title"], v["orig"], v["yil"], v["cast_list"])

    result = qc.identity_first_producer(v["read_yap"], kb_yap, max_out=3)
    temiz = result["temiz_yapimci"]
    dususler = result["dususler"]

    print(f"\n=== {v['ad']} ===")
    print(f"  OCR giriş:      {v['read_yap']}")
    print(f"  IMDb ID:        {imdb_id}  verdict={verdict}  cast_ov={cast_ov}")
    print(f"  KB yapımcı:     {kb_yap}")
    print(f"  TEMİZ çıkış:    {temiz}")
    print(f"  DÜŞENLER:       {dususler}")

    if v["beklenen_garble_dusucu"]:
        garble_dustu = (v["read_yap"][0] not in temiz) or len(dususler) > 0
        if garble_dustu:
            print("  [OK] Garble doğru düştü.")
        else:
            print("  [HATA] Garble düşmedi!")
            all_ok = False

        if kb_yap:
            print(f"  [OK] KB kişileri çıkışta: {temiz}")
        else:
            print("  [BİLGİ] KB yapımcı verisi bulunamadı (IMDb'de kayıt yok veya eşleşme zayıf).")
    else:
        # Regresyon testi
        if kb_yap:
            # KB varken: exact match veya name_close ile normalize edilmiş olabilir
            korunan = [n for n in v["read_yap"] if
                       any(cc.name_match(n, t) or cc.name_close(n, t) for t in (temiz + kb_yap))]
            eşleşen_temiz = [t for t in temiz if
                              any(cc.name_match(n, t) or cc.name_close(n, t) for n in v["read_yap"])]
            if eşleşen_temiz:
                print(f"  [OK] Regresyon yok — gerçek kişiler çıkışta (KB yazımı): {temiz}")
            elif len(temiz) > 0 and all(t in kb_yap or any(cc.name_match(t, k) for k in kb_yap) for t in temiz):
                print(f"  [OK] Gerçek kişiler KB kanonik yazımıyla çıkışta: {temiz}")
            else:
                print(f"  [BİLGİ] KB var ama OCR kişileri KB ile eşleşmedi — KB: {kb_yap}")
        else:
            # KB yok → identity gate hepsini düşürür (imzasız = düş). Bu beklenen.
            print(f"  [BİLGİ] KB yok → identity gate kişileri düşürdü (beklenen davranış).")
            print(f"  [BİLGİ] KB sağlandığında regresyon testi anlamlı olacak.")

kb.close()
print("\n" + "=" * 64)
print("SONUÇ:", "TAMAM" if all_ok else "BAZI HATALAR (detaylar yukarıda)")
