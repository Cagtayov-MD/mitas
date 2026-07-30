# harness/track_kunye/metrik.py
"""Fuzzy+KB'li künye skorlayıcı — exact-token tuzağının (havaci %91 artefakt) ilacı."""
from __future__ import annotations

from ronaldo import fold_tr, token_esle


def skorla(cikti_satirlar: list[str], referans_tok: set[str], kb_tok: set[str]) -> dict:
    cikti_tok = {t for s in cikti_satirlar for t in fold_tr(s).split() if len(t) >= 3}
    eslesen = sum(1 for r in referans_tok
                  if any(token_esle(r, c, kb_tok) for c in cikti_tok))
    recall = eslesen / len(referans_tok) if referans_tok else 0.0

    # Precision satır-bazlı: bir KB-isimli satır (örn. "Neill Archer") referansla
    # EN AZ bir token'da eşleşirse bütün satır doğru sayılır — aynı ada ait ama
    # referansta ayrı listelenmeyen token (soyad/ad ikilisi gibi) satırı
    # cezalandırmaz. Rol satırları ("SUNG BY") zaten KB token içermediği için
    # paydaya hiç girmez.
    kb_satirlar = [fold_tr(s).split() for s in cikti_satirlar
                   if any(t in kb_tok for t in fold_tr(s).split())]
    dogru_satir = sum(1 for toks in kb_satirlar
                       if any(token_esle(t, r, kb_tok) for t in toks for r in referans_tok))
    precision = dogru_satir / len(kb_satirlar) if kb_satirlar else 0.0

    f1 = (2 * recall * precision / (recall + precision)) if (recall + precision) else 0.0
    # 3 ondalık yuvarlama 1e-6 toleranslı testle çakışıyordu (2/3→0.667,
    # sapma ~3.3e-4) — 6 ondalığa çıkarıldı (SAPMA, bkz. rapor).
    return {"recall": round(recall, 6), "precision": round(precision, 6),
            "f1": round(f1, 6), "eslesen": eslesen,
            "cikti_tok_n": len(cikti_tok), "referans_n": len(referans_tok)}
