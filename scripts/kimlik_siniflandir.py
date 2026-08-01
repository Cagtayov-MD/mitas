#!/usr/bin/env python3
"""KİMLİK HATA SINIFLANDIRICI — "çelişki" tek kelimesini gerçek sınıflara ayırır.

ÇAĞATAY TALİMATI (2026-08-01): "hataları bir sınıflandıralım düzgünce — biz
okuyamadık başka bir şey, okuduk ama XML kıyasında sorun oldu başka bir şey,
çelişki başka bir şey."

ÖLÇÜLEN GEREKÇE: 'kimlik çelişkisi (KB cross-check)' etiketi her şeye basılıyordu.
Gecenin 17 filminin 14'ü KAYNAK_YOK, 2'si OKUNAN_YOK, 1'i ÇELİŞKİ idi.
Tüm DB'de KB otoriter yönetmeni olan 164 filmin 109'unda (%66) AYNI ismi okuduk.
Gerçek çelişki %5. Tek etiket bu farkı gizliyordu.

AYIRICI SİNYAL — cast_ov (oyuncu örtüşmesi):
  Kimliğin doğru kurulup kurulmadığını oyuncu örtüşmesi söyler, yönetmen değil.
    cast_ov YÜKSEK + yönetmen farklı  → kimlik DOĞRU, demek ki BİZİM yönetmen yanlış
                                        (koreograf/oyuncu/yapımcı satırını yönetmen
                                         sanmışız — rol-eşleme hatası)
    cast_ov SIFIR   + yönetmen farklı → kimliğin kendisi şüpheli; KB yanlış filmi
                                        eşleştirmiş olabilir (jenerik başlık tuzağı:
                                        XML başlığı düpedüz 'ÇİZGİ FİLM' olabiliyor)
Bu ayrım fix'in adresini değiştirir: birincide rol-eşleme, ikincide kimlik eşleme.

KULLANIM:
    python3 scripts/kimlik_siniflandir.py            # özet tablo
    python3 scripts/kimlik_siniflandir.py --detay    # film film
    python3 scripts/kimlik_siniflandir.py --json
"""
from __future__ import annotations

import argparse
import json
import os
import re
import unicodedata
from collections import Counter
from pathlib import Path

PROJE = Path(os.environ.get("MITAS_PROJECT_ROOT", "/opt/mitas"))
DB = PROJE / "Database"

# cast_ov bu değerin altındaysa kimlik çapası ZAYIF sayılır (pipeline'ın kendi
# eşiği de 2: "cast-örtüşme<2 → kimlik kurulamadı").
CAST_OV_ESIK = 2

SINIFLAR = {
    "okuyamadik":       "BİZ okuyamadık — yönetmen alanı boş (çelişki DEĞİL)",
    "kaynak_yok":       "Kıyas kaynağı yok — KB/web referansı yok (çelişki DEĞİL)",
    "uyusuyor":         "Okuduk ve KB ile AYNI — sorun yok",
    "yazim_farki":      "Aynı kişi, yazım/aksan farkı (Ágúst~AGUST) — otomatik çözülmeli",
    "bizim_yonetmen_yanlis": "Kimlik DOĞRU (cast örtüşüyor) ama bizim yönetmen farklı "
                             "→ rol-eşleme hatası (koreograf/oyuncu/yapımcı satırı)",
    "kimlik_supheli":   "cast örtüşmesi YOK — KB yanlış filmi eşleştirmiş olabilir "
                        "(jenerik başlık tuzağı)",
}


# AKSAN OLMAYAN özel harfler: NFKD bunları çözmez, çıplak silme İSMİ BOZAR.
# Kanıt: 'Guðmundsson' → ð silinince 'gumundsson' olup 'GUDMUNDSSON' ile
# eşleşmiyordu ve aynı kişi "çelişki" sayılıyordu (DENİZ EJDERİ 1990-0350).
_OZEL_HARF = str.maketrans({
    "ð": "d", "Ð": "d", "þ": "th", "Þ": "th", "ø": "o", "Ø": "o",
    "æ": "ae", "Æ": "ae", "œ": "oe", "Œ": "oe", "ł": "l", "Ł": "l",
    "đ": "d", "Đ": "d", "ß": "ss", "å": "a", "Å": "a",
})


def fold(s: str) -> str:
    s = (s or "").translate(str.maketrans({
        "ı": "i", "İ": "i", "I": "i", "ş": "s", "Ş": "s", "ğ": "g", "Ğ": "g",
        "ü": "u", "Ü": "u", "ö": "o", "Ö": "o", "ç": "c", "Ç": "c"})).lower()
    s = s.translate(_OZEL_HARF)
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z ]", "", s).strip()


def _mesafe(a: str, b: str) -> int:
    """Levenshtein (kısa isimler için yeterli, bağımlılıksız)."""
    if a == b:
        return 0
    onceki = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        simdi = [i]
        for j, cb in enumerate(b, 1):
            simdi.append(min(onceki[j] + 1, simdi[j - 1] + 1,
                             onceki[j - 1] + (ca != cb)))
        onceki = simdi
    return onceki[-1]


def _yakin(a: str, b: str) -> bool:
    """Aynı kişinin yazım varyantı mı? (aksan/OCR farkı — Levenshtein'siz, ucuz)"""
    fa, fb = fold(a), fold(b)
    if fa == fb:
        return True
    ta, tb = set(fa.split()), set(fb.split())
    if ta and tb and (ta & tb) and len(ta ^ tb) <= 1:
        return True                      # bir token farkı (orta ad vb.)
    # Tüm ad üzerinde küçük düzenleme mesafesi = OCR/aksan varyantı, farklı kişi değil.
    # Eşik uzunluğa göre: kısa adda 1, uzun adda en fazla 2 (muhafazakâr —
    # 'Noel Black' ile 'John Stockwell' arasında 10+ var, asla karışmaz).
    esik = 1 if max(len(fa), len(fb)) <= 12 else 2
    return _mesafe(fa, fb) <= esik


def film_oku(d: Path) -> dict | None:
    tr = d / "debug_trace" / "trace.jsonl"
    if not tr.is_file():
        return None
    try:
        ham = tr.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None
    m = re.search(r'"otoriter_yonetmen":\s*\[([^\]]*)\]', ham)
    kb = [x.strip(' "') for x in m.group(1).split(",") if x.strip(' "')] if m else []
    ov = re.search(r'"cast_ov"\s*:\s*(\d+)', ham)
    cast_ov = int(ov.group(1)) if ov else None
    biz, verdict = [], None
    for ln in ham.splitlines():
        if '"kimlik_dogru"' in ln:
            try:
                e = json.loads(ln).get("evidence") or {}
            except Exception:  # noqa: BLE001
                e = {}
            if "verdict" in e:
                verdict = e.get("verdict")
        if '"v4_pdf_fields"' not in ln:
            continue
        try:
            aft = (json.loads(ln).get("subject") or {}).get("after") or {}
        except Exception:  # noqa: BLE001
            continue
        for rol, adlar in (aft.get("crew") or []):
            if "önetmen" in str(rol):
                biz = [a for a in adlar if a and a != "—"]
    return {"film": d.name, "biz": biz, "kb": kb, "cast_ov": cast_ov, "verdict": verdict}


def siniflandir(r: dict) -> str:
    biz, kb = r["biz"], r["kb"]
    if not kb:
        return "kaynak_yok"
    if not biz:
        return "okuyamadik"
    if any(fold(b) == fold(k) for b in biz for k in kb):
        return "uyusuyor"
    if any(_yakin(b, k) for b in biz for k in kb):
        return "yazim_farki"
    ov = r.get("cast_ov")
    if ov is not None and ov >= CAST_OV_ESIK:
        return "bizim_yonetmen_yanlis"
    return "kimlik_supheli"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--detay", action="store_true")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--sinif", default=None)
    a = ap.parse_args()

    kayit = []
    for d in sorted(DB.iterdir()):
        if not d.is_dir():
            continue
        r = film_oku(d)
        if not r:
            continue
        r["sinif"] = siniflandir(r)
        kayit.append(r)

    sayim = Counter(k["sinif"] for k in kayit)
    if a.json:
        print(json.dumps({"toplam": len(kayit), "sayim": sayim, "filmler": kayit},
                         ensure_ascii=False, indent=1))
        return 0

    print(f"=== KİMLİK SINIFLANDIRMASI — {len(kayit)} film ===\n")
    for s, n in sayim.most_common():
        print(f"  {n:>4}  {s:<24} {SINIFLAR.get(s, '')}")
    print()
    hedef = a.sinif or ("bizim_yonetmen_yanlis" if not a.detay else None)
    for k in kayit:
        if a.sinif and k["sinif"] != a.sinif:
            continue
        if not a.detay and k["sinif"] != hedef:
            continue
        ad = k["film"].split(" 1")[0].split(" 2")[0][:26]
        print(f"   {ad:<28}biz={str(k['biz'])[:28]:<30}KB={str(k['kb'])[:26]:<28}"
              f"cast_ov={k['cast_ov']}")
    print("\n  detay: --detay | --sinif <ad> | --json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
