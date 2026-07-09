# -*- coding: utf-8 -*-
"""DETERMINISTIK TEST (2026-07-09) — tek_film_kunye.py İSİM-DÜZEYİ TEYİT SÜZGECİ SINIF-1 fix'i +
DÖRDÜNCÜ kapı (cast-bağlamı vetosu, JERICO APARTMANI/"Antonio Wilford" kökü, aynı gece).
Gerçek DB dosyaları + gerçek fonksiyonlar (_valid_person_name, CreditKB._imdb_people_by_folds,
_stok_footage_yakinda, _cast_baglaminda_mi) üzerinden, tam üretim kapı-sırasıyla KEPT/DROPPED hükmü verir.
KRİTİK: ONDAN UZAKTA/Ernst Kettler regresyon-kalkanı MUTLAKA DROPPED kalmalı.
NOT (JERICO/"Martin Pollins"): bilinçli olarak test-vakası DIŞINDA bırakıldı — gate2 (CreditKB
geniş-KB-varlığı, _imdb_people_by_folds) bu adı zaten HİÇ bulamıyor (ayrı/önceden-var bir KB-kapsam
boşluğu, bu fix'ten TAMAMEN bağımsız) — beklenen="KEPT" yazmak yanıltıcı olurdu (gerçekte DROPPED
kalıyor ama SEBEBİ gate4 değil gate2). "Ian Steel" ise gate1-3'ü geçtiği için gate4'ün gerçek
kapı-bağlamlı isimleri YANLIŞLIKLA veto ETMEDİĞİNİ doğrulayan asıl pozitif-kontrol vakasıdır.
"""
import os
import sys

sys.path.insert(0, r"E:\MITAS\scripts")
sys.stdout.reconfigure(encoding="utf-8")

import tek_film_kunye as tfk          # noqa: E402
import credit_text_read as ctr        # noqa: E402
import credit_crosscheck as cc        # noqa: E402

DB = r"E:\MITAS\Database"


def _fold_tx(t):
    return tfk.nn.ascii_fold(t or "").upper()


def _load_raw(clip_dirname, ocr_subdir):
    kunye_p = os.path.join(DB, clip_dirname, "ocr", ocr_subdir, "kunye.txt")
    dilim_p = os.path.join(DB, clip_dirname, "master_dilim", "dilim_oneocr.txt")
    fr = _fold_tx(open(kunye_p, encoding="utf-8", errors="ignore").read()) if os.path.exists(kunye_p) else ""
    dl = _fold_tx(open(dilim_p, encoding="utf-8", errors="ignore").read()) if os.path.exists(dilim_p) else ""
    return fr, dl


def gate_verdict(name, fr_txt, dl_txt, kb):
    """tek_film_kunye.py'nin YENİ else-dalıyla BİREBİR aynı kapı sırası (4 kapı, 2026-07-09)."""
    if not ctr._valid_person_name(name):
        return "DROPPED", "yapisal-gecersiz/garble"
    if not (kb and kb._imdb_people_by_folds([cc.fold(name)])):
        return "DROPPED", "genis KB'de de yok"
    if tfk._stok_footage_yakinda(name, (fr_txt, dl_txt)):
        return "DROPPED", "STOK-FOOTAGE yakininda (ONDAN UZAKTA sinifi)"
    if tfk._cast_baglaminda_mi(name, dl_txt):
        return "DROPPED", "kadro-listesi karakter-rolu (JERICO APARTMANI sinifi)"
    return "KEPT", "her 4 kapidan gecti"


def main():
    kb = cc.CreditKB()

    vaka = []

    # --- Pozitif hedefler (SINIF-1, kurtarilmasi beklenir) ---
    fr, dl = _load_raw("VANYA DAYI 1989-0476-1-0000-00-1", "ocr-ee227bdb")
    vaka.append(("VANYA DAYI", "EVGENIY MAKAROV", fr, dl, "KEPT"))

    fr, dl = _load_raw("ZAMAN VE RÜZGAR 1990-0336-1-0000-00-1", "ocr-e1b3223a")
    vaka.append(("ZAMAN VE RÜZGAR", "PAULO JOSE", fr, dl, "KEPT"))

    fr, dl = _load_raw("SON YARIŞ 1992-0308-1-0000-00-1", "ocr-0a296778")
    vaka.append(("SON YARIŞ", "JOVAN RANCIC", fr, dl, "KEPT"))

    # --- KRİTİK REGRESYON-KALKANI: bu MUTLAKA DROPPED kalmali ---
    fr, dl = _load_raw("ONDAN UZAKTA 2006-9175-1-0000-00-1", "ocr-a0f1b3ba")
    vaka.append(("ONDAN UZAKTA", "ERNST KETTLER", fr, dl, "DROPPED"))

    # --- YENİ, 4. KAPI: JERICO APARTMANI/"Antonio Wilford" kökü (2026-07-09) ---
    # "CAST IN ALPHABETICAL ORDER" listesinde "Director" adli KARAKTERİ oynayan oyuncu — gercek
    # yonetmen degil. "Ian Steel" gercek "Directors Martin Pollins/Ian Steel" yapim-blogundan
    # (kadro+stunt bittikten, "...PARTICIPATION OF..." satirindan SONRA) — gate4 onu YANLISLIKLA
    # veto ETMEMELI (pozitif-kontrol: gate4 asiri-tetiklenmiyor).
    fr, dl = _load_raw("JERICO APARTMANI 2003-9195-1-0000-00-1", "ocr-ae638012")
    vaka.append(("JERICO APARTMANI", "ANTONIO WILFORD", fr, dl, "DROPPED"))
    vaka.append(("JERICO APARTMANI", "IAN STEEL", fr, dl, "KEPT"))

    # --- Onceden-kanitli QC2 vakalari (ayni iki kapi, bu kod-yolunda da bozulmamali) ---
    import glob
    ks = glob.glob(os.path.join(DB, "İKİNCİ ŞANS 1992-0465-1-0000-00-1", "ocr", "ocr-*", "kunye.txt"))
    fr = _fold_tx(open(ks[0], encoding="utf-8", errors="ignore").read()) if ks else ""
    dl_p = os.path.join(DB, "İKİNCİ ŞANS 1992-0465-1-0000-00-1", "master_dilim", "dilim_oneocr.txt")
    dl = _fold_tx(open(dl_p, encoding="utf-8", errors="ignore").read()) if os.path.exists(dl_p) else ""
    vaka.append(("İKİNCİ ŞANS", "REUBEN ROSE", fr, dl, "KEPT"))
    vaka.append(("İKİNCİ ŞANS (senaryo)", "DELMER DAVES", "", "", "KEPT"))  # KB-var, metin-baglami onemsiz

    # --- Garble/negatif kontrol (hala reddedilmeli) ---
    vaka.append(("sentetik-garble", "ABRURRAK ROROSKO", "", "", "DROPPED"))
    vaka.append(("sentetik-rastgele", "XQZVK JBTRW", "", "", "DROPPED"))

    print(f"{'FILM':22s} {'ISIM':20s} {'BEKLENEN':10s} {'SONUC':10s} {'DETAY'}")
    print("-" * 100)
    all_ok = True
    for film, name, fr, dl, expect in vaka:
        verdict, detail = gate_verdict(name, fr, dl, kb)
        ok = (verdict == expect)
        all_ok &= ok
        print(f"{film:22s} {name:20s} {expect:10s} {verdict:10s} {'OK ' if ok else '<<< FAIL'} {detail}")

    print()
    print("=== TUM VAKALAR GECTI ===" if all_ok else "=== FAIL VAR — DUR, KOMITLEME ===")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
