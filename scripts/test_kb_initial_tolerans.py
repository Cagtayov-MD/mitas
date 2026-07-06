# -*- coding: utf-8 -*-
"""DETERMINISTIK REGRESYON TESTI — _kb_verify_flex tek-harf kısaltma toleransı (2026-07-07).

Kök vaka: ANGOLA'DAN KAÇIŞ / Escape from Angola. Ekran jeneriği "DIRECTED BY LESLIE
MARTINSON" (sade) basar; KB'de yönetmen "Leslie H. Martinson" (director) kayıtlı, sade
"Leslie Martinson" ise BAŞKA kişi (production dept) → kb.verify RED → doğru okunan yönetmen
_fuse_yonetmen'de düşüyordu. Fix: _kb_verify_flex(B) — tek-harf (baş/orta) token yok sayarak
çekirdek ad+soyad eşit TEK rol-ONAY'lı KB kaydı ara → ONAY.

KB deterministik (ollama YOK) → bu test HER koşuda aynı sonucu verir; golden'ın (VL-stokastik)
aksine fix'in güvenilir bekçisidir. Koş: venvs/ocr python ile."""
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))
import credit_text_read as ctr

# (isim, rol, beklenen, açıklama)
VAKALAR = [
    ("Leslie Martinson", "director", "ONAY",
     "HEDEF: KB'de 'Leslie H. Martinson' yönetmen → sade-ad köprüsü ONAY"),
    ("Leslie Martinson", "actor", "RED",
     "NEGATİF: sade 'Leslie Martinson' = production dept → oyuncu DEĞİL, RED kalmalı"),
    ("Leslie H. Martinson", "director", "ONAY",
     "REGRESYON: tam-ad zaten ONAY (bozulmamalı)"),
    ("Zqxvw Ppplmn", "director", "kayit-yok",
     "NEGATİF: KB'de hiç yok → uydurma köprü kurmamalı"),
]


def main() -> int:
    kb = ctr._get_kb()
    gecti = 0
    print("=== _kb_verify_flex tek-harf kısaltma toleransı (deterministik) ===")
    for nm, role, bekle, acik in VAKALAR:
        got = ctr._kb_verify_flex(kb, nm, role)
        ok = (got == bekle)
        gecti += ok
        print(f"  {'PASS' if ok else 'FAIL':4s} _kb_verify_flex({nm!r:22s},{role:9s}) = "
              f"{got:10s} bekle={bekle:10s} | {acik}")
    # Kill-switch: OFF iken (B) yönü DEVRE DIŞI → eski davranış (RED) korunmalı (fail-safe)
    os.environ["MITAS_KB_INITIAL_TOLERANS"] = "0"
    off = ctr._kb_verify_flex(kb, "Leslie Martinson", "director")
    os.environ.pop("MITAS_KB_INITIAL_TOLERANS", None)
    ks_ok = (off == "RED")
    gecti += ks_ok
    print(f"  {'PASS' if ks_ok else 'FAIL':4s} kill-switch OFF → 'Leslie Martinson'/director = "
          f"{off} (RED = eski davranış korunur)")
    n = len(VAKALAR) + 1
    print(f"\n=== SONUÇ: {gecti}/{n} — {'TEMİZ' if gecti == n else 'REGRESYON VAR!'}")
    return 0 if gecti == n else 1


if __name__ == "__main__":
    sys.exit(main())
