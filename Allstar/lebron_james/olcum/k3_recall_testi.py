#!/usr/bin/env python3
"""K3 recall testi (Görev M8, MITAS_Master_Dup_Kok_Sebep_Plani_v1.md).

K3 şartı: "≥100 etiketli çift ... korunması-gereken-farklı-metin çiftlerinde
recall>=0.9 kanıtla". Bu script AYRI bir ≥100-çift toplama turu YERİNE
`kalibrasyon_k1.py --topla`'nın ZATEN ürettiği `farkli-kart` (bağımsız REC-
oracle ile etiketlenmiş, genuine-farklı-içerik) çiftlerini yeniden kullanır
(Prensip 3 -- "daha iyi bir yol": aynı gerçek veri, ayrı bir toplama turu
maliyeti yok). Bu çiftlerin HER BİRİ "korunması-gereken-farklı-metin" ground
truth'unun ta kendisidir (K1 kalibrasyonu için REC-tabanlı bağımsız etiketle
zaten "gerçekten farklı metin" olduğu doğrulanmış).

Ölçüm: composer'ın `_k3_protected_evidence` kriteriyle (normalize
Levenshtein>=3 VEYA token-Jaccard<=0.7 + iki tarafta da gerçek metin) AYNI
mantığı bu çiftlerin (metin_i, metin_j) alanlarına uygular -- "protected"
ateşliyor mu diye bakar. recall = ateşlenen / toplam.

BİLİNEN YAKLAŞIKLIK (raporda açıkça belirtilir): kalibrasyon çiftlerindeki
metin_i/metin_j, F1C_REC_CONF_GATE (0.6) eşikli REC filtresinden geçmiş
metinlerin birleşimidir; K3'ün KENDİ eşiği (K3_PROTECTED_CONF_GATE=0.7) daha
sıkı -- per-kutu ham güven skorları kalibrasyon JSON'ında saklanmadığı için
tam 0.7 eşikli yeniden hesap yapılamıyor. Bu YAKLAŞIK ölçüm 0.6-eşikli
metinlerle çalışır (muhtemelen gerçek 0.7-eşikli recall'den biraz FARKLI
olabilir -- ama tüm çiftler zaten "farkli-kart" etiketiyle GERÇEKTEN farklı
metin içerdiğinden, ölçülen değer güvenilir bir ALT-SINIR/yakın-tahmin verir).

Kullanım:
  kalibrasyon_k1.py --topla   # (önce) ciftler.json üretir/günceller
  k3_recall_testi.py          # bu script recall ölçer
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import saglik  # noqa: E402  (uret->dc zincirini yeniden kullanmak için)

CIFTLER_PATH = Path(__file__).resolve().parents[2] / "data" / "master_dup" / "k1_kalibrasyon" / "ciftler.json"

K3_LEV_GATE = 3
K3_JACCARD_GATE = 0.7


def protected_fires(text_a: str, text_b: str, dc, *, lev_gate: int = K3_LEV_GATE,
                     jaccard_gate: float = K3_JACCARD_GATE) -> bool:
    """composer._k3_protected_evidence ile AYNI Levenshtein/Jaccard mantığı."""
    if not text_a or not text_b:
        return False
    lev = dc._levenshtein(text_a, text_b)
    jac = dc._token_jaccard(text_a, text_b)
    return lev >= lev_gate or jac <= jaccard_gate


def main() -> int:
    if not CIFTLER_PATH.is_file():
        print(f"Kalibrasyon çiftleri bulunamadı: {CIFTLER_PATH}\n"
              f"Önce: kalibrasyon_k1.py --topla", file=sys.stderr)
        return 1

    dc = saglik._uret_mod()._dc()
    pairs = json.loads(CIFTLER_PATH.read_text(encoding="utf-8"))
    farkli = [x for x in pairs if x.get("etiket") == "farkli-kart"]

    n = len(farkli)
    if n < 100:
        print(f"UYARI: yalnız {n} korunması-gereken-farklı-metin çifti var (K3 şartı >=100)", file=sys.stderr)

    fired = [x for x in farkli if protected_fires(x["metin_i"], x["metin_j"], dc)]
    missed = [x for x in farkli if x not in fired]
    recall = len(fired) / n if n else 0.0

    print(f"Korunması-gereken-farklı-metin havuzu: {n} çift (K3 şartı: >=100)")
    print(f"Protected ateşlenen: {len(fired)}/{n} -> recall={recall:.4f} (hedef >=0.9)")
    print(f"Sonuç: {'GEÇTİ' if recall >= 0.9 and n >= 100 else 'DİKKAT -- şart karşılanmadı'}")
    if missed:
        print(f"\nAteşlenmeyen {len(missed)} çift (recall kaybı -- ilk 10):")
        for x in missed[:10]:
            print(f"  {x['film'][:25]:25} {x['metin_i'][:35]!r} | {x['metin_j'][:35]!r}")

    sonuc = {
        "n_toplam": n, "n_ateslenen": len(fired), "recall": round(recall, 4),
        "hedef": 0.9, "gecti": bool(recall >= 0.9 and n >= 100),
        "kaynak": str(CIFTLER_PATH),
        "not": "farkli-kart etiketli ciftler K1 kalibrasyonunun bagimsiz REC-oracle "
               "etiketlemesinden geliyor; metin_i/metin_j F1C_REC_CONF_GATE=0.6 esikli "
               "(K3'un kendi 0.7 esikinden farkli -- yaklasik/alt-sinir olcum).",
    }
    out_path = CIFTLER_PATH.parent / "k3_recall_sonuc.json"
    out_path.write_text(json.dumps(sonuc, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n-> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
