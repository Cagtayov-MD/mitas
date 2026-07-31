#!/usr/bin/env python3
"""qc1_olcum.py — QC1 kalite kapısının başarı oranını ÖLÇER (salt-okur).

NEDEN VAR (2026-07-31): QC1 kendi başarısını görmüyordu. `credit_qc1_passed`
yalnız "RED → VL-fallback → kurtarıldı" yolunu kapsıyordu; ilk denemede geçen film
HİÇ olay basmıyordu (yalnız `dbg.emit`, o da per-film trace'e gider,
system_events.jsonl'e DEĞİL). Ampirik: 33 filmden 16'sı RED'e girmiş, kalan
17 film sıfır olay → **başarı oranının paydası log'da yoktu.** Tek dolaylı yol
`credit_text_completed − credit_qc1_red` idi ve kırılgandı (profil filtresi,
--no-ocr, USE_VIDEO_CREDITS, kill-switch dalları paydayı bozuyor).

`mitas_pipeline.py`'ye eklenen kancalarla kapsam tamamlandı. Bu araç o olayları
film bazında toplayıp kohort tablosu üretir.

OLAY ŞEMASI — dallar KARŞILIKLI DIŞLAYICI (mitas_pipeline.py QC1 bloğu):
    QC1 koştu mu?
      ├─ evet, ilk denemede geçti      → credit_qc1_passed_first_try
      ├─ evet, RED (girdi olayı)       → credit_qc1_red
      │     ├─ VL sonrası geçti        → credit_qc1_passed
      │     └─ VL sonrası da RED       → credit_qc1_failed
      │           └─ (sonra) validate kurtardı → credit_qc1_recovered_by_validate
      ├─ kapatıldı (NO_VL_FALLBACK)    → credit_qc1_skipped
      └─ hiç koşmadı (profil/--no-ocr/
         USE_VIDEO_CREDITS/boş künye)  → OLAY YOK

MUHASEBE:
    KOŞTU     = passed_first_try + red + skipped
    GEÇTİ     = passed_first_try + passed + recovered_by_validate
    BAŞARISIZ = failed − recovered_by_validate
    ORAN      = GEÇTİ / (passed_first_try + red)      # skipped paydaya girmez:
                                                     # değerlendirilmedi, geçmedi de

KULLANIM:
    python3 scripts/qc1_olcum.py                        # tüm olay dosyaları
    python3 scripts/qc1_olcum.py --liste kliplerim.txt  # yalnız bu filmler
    python3 scripts/qc1_olcum.py --json                 # makine-okunur
    python3 scripts/qc1_olcum.py --detay                # film-film döküm

SALT-OKUR: hiçbir dosyaya yazmaz, üretime dokunmaz. Rotasyona uğramış arşivi
(system_events.1.jsonl) da okur — yoksa kohort yarım çıkar.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

MID_DESEN = re.compile(r"(\d{4}-\d{4}-\d-\d{4}-\d{2}-\d)")

# QC1 olay kümeleri — muhasebe bunlara dayanır
GIRDI_RED = "credit_qc1_red"
ILK_GECTI = "credit_qc1_passed_first_try"
VL_GECTI = "credit_qc1_passed"
VL_RED = "credit_qc1_failed"
KURTARILDI = "credit_qc1_recovered_by_validate"
ATLANDI = "credit_qc1_skipped"
QC1_KINDS = {GIRDI_RED, ILK_GECTI, VL_GECTI, VL_RED, KURTARILDI, ATLANDI}

# Vekil payda: künye ayıklaması tamamlanan her film QC1'e girmiş olmalı. Bu sayı
# QC1 olayı olan film sayısından BÜYÜKSE, aradaki fark 2026-07-31 öncesi koşulardan
# gelen "sessiz geçmiş" filmlerdir — o kohortta başarı oranı SİSTEMATİK OLARAK
# DÜŞÜK çıkar (payda eksik değil, PAY eksik: geçenler görünmüyor).
VEKIL_PAYDA = "credit_text_completed"


def _proje_kok() -> Path:
    """Env-aware kök. mitas_roots env yoksa Windows'a düşüyor (mitas_roots.py:28),
    o yüzden burada doğrudan env + betik konumu zincirini kullanıyoruz."""
    env = (os.environ.get("MITAS_PROJECT_ROOT") or "").strip()
    if env and Path(env).is_dir():
        return Path(env)
    return Path(__file__).resolve().parent.parent


def olay_dosyalari(acik: list[str] | None) -> list[Path]:
    """Verilmediyse kanonik dosya + rotasyon arşivi. Arşivi ATLAMAK kohortu yarılar."""
    if acik:
        return [Path(y) for y in acik]
    out_dir = _proje_kok() / "outputs"
    adaylar = [out_dir / "system_events.jsonl"]
    # rotasyon: system_events.1.jsonl (mitas_pipeline.py yalnız 1 önceki tutar)
    adaylar += sorted(out_dir.glob("system_events.*.jsonl"))
    return [p for p in adaylar if p.is_file()]


def olaylari_yukle(yollar: list[Path]) -> list[dict]:
    """JSONL satır satır; bozuk satır ATLANIR (araç asla çökmez)."""
    olaylar: list[dict] = []
    for p in yollar:
        try:
            metin = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:  # noqa: BLE001
            continue
        for satir in metin.splitlines():
            satir = satir.strip()
            if not satir:
                continue
            try:
                olaylar.append(json.loads(satir))
            except Exception:  # noqa: BLE001 — kısmi yazılmış son satır olabilir
                continue
    return olaylar


def _film_kimligi(ev: dict) -> str | None:
    """Film ayrımı: media_id birincil, yoksa dosya adından TRT-ID, yoksa filename."""
    mid = (ev.get("media_id") or "").strip()
    if mid:
        return mid
    fn = (ev.get("filename") or "").strip()
    if fn:
        m = MID_DESEN.search(fn)
        return m.group(1) if m else fn
    return None


def filmlere_dagit(olaylar: list[dict]) -> dict[str, dict]:
    """film_kimligi → {kind: olay}. Aynı kind tekrar ederse EN YENİSİ kalır
    (yeniden koşulan film: son koşunun sonucu geçerli)."""
    filmler: dict[str, dict] = {}
    for ev in olaylar:
        kind = ev.get("kind")
        if kind not in QC1_KINDS:
            continue
        fid = _film_kimligi(ev)
        if not fid:
            continue
        kayit = filmler.setdefault(fid, {})
        onceki = kayit.get(kind)
        if onceki is None or str(ev.get("ts") or "") >= str(onceki.get("ts") or ""):
            kayit[kind] = ev
    return filmler


def vekil_payda_filmleri(olaylar: list[dict]) -> set[str]:
    """Künye ayıklaması tamamlanan filmler — QC1'e girmiş olması BEKLENEN küme."""
    out: set[str] = set()
    for ev in olaylar:
        if ev.get("kind") != VEKIL_PAYDA:
            continue
        fid = _film_kimligi(ev)
        if fid:
            out.add(fid)
    return out


def film_sonucu(kinds: dict) -> str:
    """Bir filmin QC1 nihai durumu. Öncelik: en SPESİFİK sonuç kazanır.
    KURTARILDI, VL_RED'den SONRA gelir (bayrağı o kaldırıyor) → önce sınanır."""
    if KURTARILDI in kinds:
        return "kurtarildi"
    if VL_GECTI in kinds:
        return "vl_gecti"
    if VL_RED in kinds:
        return "basarisiz"
    if ILK_GECTI in kinds:
        return "ilk_gecti"
    if ATLANDI in kinds:
        return "atlandi"
    if GIRDI_RED in kinds:
        # RED girdi olayı var ama sonuç olayı yok → koşu yarıda kesilmiş
        return "yarim_kaldi"
    return "bilinmiyor"


SONUC_ETIKET = {
    "ilk_gecti": "İlk denemede geçti",
    "vl_gecti": "VL-fallback kurtardı",
    "kurtarildi": "credit_validate kurtardı",
    "basarisiz": "BAŞARISIZ (VL sonrası da RED)",
    "atlandi": "Değerlendirilmedi (NO_VL_FALLBACK)",
    "yarim_kaldi": "YARIM KALDI (RED sonrası sonuç yok)",
    "bilinmiyor": "bilinmiyor",
}
GECEN = {"ilk_gecti", "vl_gecti", "kurtarildi"}


def ozetle(filmler: dict[str, dict]) -> dict:
    sayim: dict[str, int] = {k: 0 for k in SONUC_ETIKET}
    sonuclar: dict[str, str] = {}
    for fid, kinds in filmler.items():
        s = film_sonucu(kinds)
        sonuclar[fid] = s
        sayim[s] = sayim.get(s, 0) + 1

    kostu = sum(sayim[k] for k in ("ilk_gecti", "vl_gecti", "kurtarildi",
                                   "basarisiz", "yarim_kaldi"))
    gecti = sum(sayim[k] for k in GECEN)
    # Payda: değerlendirilen filmler. 'atlandi' girmez (geçmedi de, kalmadı da);
    # 'yarim_kaldi' GİRER — koşu kesilmesi başarı sayılamaz, görünür kalmalı.
    payda = kostu
    return {
        "film_n": len(filmler),
        "sayim": sayim,
        "kostu": kostu,
        "gecti": gecti,
        "oran": (round(gecti / payda, 4) if payda else None),
        "sonuclar": sonuclar,
    }


def _liste_yukle(yol: str) -> set[str]:
    """Satır başına clip_dir veya film adı → TRT-ID kümesi."""
    kume: set[str] = set()
    for satir in Path(yol).read_text(encoding="utf-8", errors="ignore").splitlines():
        satir = satir.strip()
        if not satir or satir.startswith("#"):
            continue
        m = MID_DESEN.search(satir)
        kume.add(m.group(1) if m else Path(satir).name)
    return kume


def main() -> int:
    ap = argparse.ArgumentParser(description="QC1 başarı oranı ölçümü (salt-okur)")
    ap.add_argument("--events", action="append", default=None,
                    help="olay dosyası (tekrarlanabilir); verilmezse kanonik + rotasyon")
    ap.add_argument("--liste", default=None,
                    help="yalnız bu filmler (satır başına clip_dir/ad/TRT-ID)")
    ap.add_argument("--json", action="store_true", help="makine-okunur çıktı")
    ap.add_argument("--detay", action="store_true", help="film-film döküm")
    a = ap.parse_args()

    yollar = olay_dosyalari(a.events)
    if not yollar:
        print("HATA: olay dosyası bulunamadı. --events ile açıkça verin.", file=sys.stderr)
        return 2

    olaylar = olaylari_yukle(yollar)
    filmler = filmlere_dagit(olaylar)
    vekil = vekil_payda_filmleri(olaylar)

    if a.liste:
        istenen = _liste_yukle(a.liste)

        def _istendi(f: str) -> bool:
            return f in istenen or any(f in i or i in f for i in istenen)

        filmler = {f: k for f, k in filmler.items() if _istendi(f)}
        vekil = {f for f in vekil if _istendi(f)}

    ozet = ozetle(filmler)
    # KÖR FİLMLER: künyesi ayıklanmış ama hiç QC1 olayı yok → 2026-07-31 öncesi
    # koşu. Bu kohortta oran GÜVENİLMEZ; geçenler görünmediği için düşük çıkar.
    kor = sorted(vekil - set(filmler))
    ozet["vekil_payda_n"] = len(vekil)
    ozet["kor_film_n"] = len(kor)
    ozet["kor_filmler"] = kor
    ozet["oran_guvenilir"] = (len(kor) == 0)

    if a.json:
        print(json.dumps({"kaynaklar": [str(p) for p in yollar], **ozet},
                         ensure_ascii=False, indent=1))
        return 0

    print("=== QC1 ÖLÇÜM ===")
    print(f"Kaynak: {', '.join(p.name for p in yollar)}")
    print(f"QC1 olayı olan film: {ozet['film_n']}")
    print()
    for k, etiket in SONUC_ETIKET.items():
        n = ozet["sayim"].get(k, 0)
        if n:
            print(f"  {etiket:<38} {n:>4}")
    print()
    print(f"  Değerlendirilen (payda)                {ozet['kostu']:>4}")
    print(f"  Geçen                                  {ozet['gecti']:>4}")
    if ozet["oran"] is None:
        print("  BAŞARI ORANI                           ölçülemiyor (payda 0)")
    elif ozet["oran_guvenilir"]:
        print(f"  BAŞARI ORANI                          {ozet['oran'] * 100:>5.1f}%")
    else:
        print(f"  BAŞARI ORANI                          {ozet['oran'] * 100:>5.1f}%  ⚠ GÜVENİLMEZ")
        print()
        print(f"  ⛔ {ozet['kor_film_n']} filmin künyesi ayıklanmış ama HİÇ QC1 olayı yok.")
        print("     Bunlar 2026-07-31 öncesi koşular: o sürümde 'ilk denemede geçti'")
        print("     loglanmıyordu (yalnız dbg.emit, system_events'e gitmiyor).")
        print("     Eksik olan PAYDA değil PAY — geçen filmler görünmüyor, bu yüzden")
        print(f"     oran SİSTEMATİK OLARAK DÜŞÜK. Gerçek payda ≈ {ozet['vekil_payda_n']}.")
        print("     Bu sayıyı baseline olarak KULLANMAYIN; fix sonrası yeniden koşun.")

    if ozet["sayim"].get("yarim_kaldi"):
        print()
        print(f"  ⚠ {ozet['sayim']['yarim_kaldi']} filmde RED sonrası sonuç olayı yok — "
              "koşu kesilmiş olabilir, başarı sayılmadı.")
    if ozet["sayim"].get("atlandi"):
        print(f"  ⚠ {ozet['sayim']['atlandi']} filmde QC1 hiç değerlendirilmedi "
              "(MITAS_NO_VL_FALLBACK) — paydaya girmedi.")

    if a.detay:
        print()
        print("=== FİLM DÖKÜMÜ ===")
        for fid in sorted(ozet["sonuclar"]):
            print(f"  {fid:<32} {SONUC_ETIKET[ozet['sonuclar'][fid]]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
