#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""_pipe_credit_vl.py — VL-FALLBACK (additif, FAIL-SAFE).

mitas_pipeline çağırır: metin künye-okuma (qwen3) yönetmen BOŞ ya da cast<3 ise →
jenerik KARELERİNDEN VL re-read (qwen2.5vl + gemma4) + tiebreak merdiveni → metnin
BOŞ alanını doldur. Metnin GÜVENLE okuduğunu EZMEZ (gap-filler).

TASARIM (Çağatay 2026-06-09, TASARIM_KUNYE_PIPELINE_v2.md):
  AŞAMA 4 tiebreak: a) mutabakat  b) cross-cast self-consistency  c) KB-onay  d) PES→Kontrol
  Cast-supplement (#3): text cast<3 → VL cast'ten tamamla. Yapımcı: sadece-kişi (#2, KESİN KURAL).
  2-model VL (#4). num_ctx=40960 (36 kare>16384→400). think=False (read_segment'te).

FAIL-SAFE: kare yok / ollama kapalı / herhangi hata → girdi text-credits AYNEN döner (ASLA çökmez).
Çıktı: tek-satır JSON (mitas_pipeline'ın last_json'u okur), credit_text ile AYNI şema (drop-in merge).
"""
import argparse
import glob
import json
import os
import sys
import unicodedata

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# VL prompt: yönetmen-etiket kalıpları + KESİN KURAL (metin tarafıyla aynı mantık)
_VL_PROMPT = (
    "Bunlar bir film jeneriğinin ARDIŞIK kareleri (video). Kareler boyunca görünen yazıları "
    "birleştir. SADECE karelerde AÇIKÇA YAZAN isimleri kullan, UYDURMA; yoksa 'yok'.\n"
    "YÖNETMEN: şu kalıpların YANINDAKİ/ALTINDAKİ KİŞİ adı: 'DIRECTED BY', 'A <İSİM> FILM' "
    "(ör. 'A JOHN McTIERNAN FILM' -> John McTiernan), 'A FILM BY', 'YÖNETMEN', 'YÖNETEN', "
    "'REJİSÖR', 'UN FILM DE', 'EIN FILM VON', 'REGIE', 'RÉALISÉ PAR'. "
    "'ASSISTANT DIRECTOR / DIRECTOR OF PHOTOGRAPHY / ART DIRECTOR / MUSIC' YÖNETMEN DEĞİLDİR. Net değilse 'yok'.\n"
    "Çıktıyı tam olarak şu formatta ver:\n"
    "YÖNETMEN: <isim | yok>\nYAPIMCI: <Producer/Yapımcı yanındaki isim(ler) | yok>\n"
    "OYUNCULAR: <görünen başrol oyuncu adları, en fazla 8, virgülle | yok>"
)
VL_MODELS = ["qwen2.5vl:7b", "gemma4:26b"]  # #4 iki model (mutabakat)


def _fold(s):
    s = (s or "")
    for a, b in (("İ", "i"), ("I", "i"), ("ı", "i"), ("Ş", "s"), ("ş", "s"), ("Ğ", "g"),
                 ("ğ", "g"), ("Ü", "u"), ("ü", "u"), ("Ö", "o"), ("ö", "o"), ("Ç", "c"), ("ç", "c")):
        s = s.replace(a, b)
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower().strip()


def _find_frames(clip):
    """clip/frames/giris + cikis (ya da clip altında ilk giris/cikis)."""
    g = os.path.join(clip, "frames", "giris")
    c = os.path.join(clip, "frames", "cikis")
    if not os.path.isdir(g):
        cand = glob.glob(os.path.join(clip, "**", "giris"), recursive=True)
        g = cand[0] if cand else None
    if not os.path.isdir(c or ""):
        cand = glob.glob(os.path.join(clip, "**", "cikis"), recursive=True)
        c = cand[0] if cand else None
    return (g if g and os.path.isdir(g) else None), (c if c and os.path.isdir(c) else None)


def _vl_one(cv, ctr, giris, cikis, model, kb):
    """Bir VL modeli: yön+cast; yönetmenden O MODELİN cast'inde geçeni at (self-consistency) + KESİN KURAL."""
    res = cv.read_credits(giris, cikis, models=[model], kb=kb) or {}
    yon = res.get("yonetmen") or []
    cast = res.get("cast") or []
    cf = {_fold(x) for x in cast}
    yon = ctr._only_persons([y for y in yon if _fold(y) not in cf])
    return yon, ctr._only_persons(cast)


def _tiebreak(q, g, all_cast_fold, kb):
    """a) mutabakat  b) cross-cast  c) KB-onay  d) PES."""
    agree = [y for y in q if any(_fold(y) == _fold(x) for x in g)]
    if agree:
        return [agree[0]], "mutabakat"
    cands = []
    for y in q + g:
        if not any(_fold(y) == _fold(x) for x in cands):
            cands.append(y)
    cands = [y for y in cands if _fold(y) not in all_cast_fold]   # cross-cast: başrol ele
    if not cands:
        return [], "pes(cross-cast)"
    # KB-tiebreak YALNIZ gerçek çelişkide (≥2 aday) — çelişkiyi ÇÖZ. Tek aday (tek model okudu,
    # diğeri abstain) → KB-genel-onay YETMEZ (Kar Kraliçesi→"Chris Randall" sızıntısı buydu):
    # mutabakat yok + tek-model → Kontrol. "yanlış > boş".
    if len(cands) >= 2:
        kb_ok = [y for y in cands if kb.verify(y, "director") == "ONAY"]
        if len(kb_ok) == 1:
            return kb_ok, "kb-tiebreak"
        return [], "pes(coklu-kb/belirsiz)"
    return [], "pes(tek-model, mutabakat yok)"


def vl_fallback(clip, title, text_credits, profile="film"):
    """Metnin boş yönetmenini/eksik cast'ini VL ile doldur. Her hata → text_credits AYNEN."""
    out = dict(text_credits or {})
    out.setdefault("yonetmen", [])
    out.setdefault("yapimci", [])
    out.setdefault("cast", [])
    try:
        import credit_video_read as cv
        import credit_text_read as ctr
        cv.NUM_CTX = 40960
        cv.PROMPT = _VL_PROMPT
        giris, cikis = _find_frames(clip)
        if not giris:
            out["vl"] = "kare-yok"
            return out
        kb = cv.KB()
        q, qc = _vl_one(cv, ctr, giris, cikis, VL_MODELS[0], kb)
        g, gc = _vl_one(cv, ctr, giris, cikis, VL_MODELS[1], kb)
        tcast = out.get("cast") or []
        all_cast_fold = {_fold(x) for x in (tcast + qc + gc)}
        # YÖNETMEN: yalnız BOŞSA doldur (metni EZME)
        if not out.get("yonetmen"):
            vlyon, how = _tiebreak(q, g, all_cast_fold, kb)
            if vlyon:
                out["yonetmen"] = ctr._only_persons(vlyon)
                out["vl_yon_kaynak"] = how
        # CAST-supplement: VARSAYILAN KAPALI (2026-06-09 ölçüm: VL cast HALÜSİNE — brad pitt/julia roberts
        # uyduruyor, temp=0'da bile). VL artık YÖNETMEN-ONLY; cast = OCR otorite + KB (QC2 tamamlar).
        # Geri-almak için MITAS_VL_CAST=1 (önerilmez). KESİN KURAL + dedup yine uygulanır.
        if os.environ.get("MITAS_VL_CAST", "0").strip().lower() in ("1", "true", "on", "yes") and len(tcast) < 3:
            add = []
            for nm in qc + gc:
                if not any(_fold(nm) == _fold(x) for x in tcast + add):
                    add.append(nm)
            if add:
                out["cast"] = ctr._only_persons(tcast + add)
                out["vl_cast_supplement"] = len(add)
        out["vl"] = "kostu"
    except Exception as e:  # noqa: BLE001 — FAIL-SAFE: pipeline'ı ASLA bozma
        out["vl"] = f"hata:{type(e).__name__}"
    return out


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--clip", required=True)
    ap.add_argument("--title", default="")
    ap.add_argument("--profile", default="film")
    ap.add_argument("--text-credits", default="{}", help="metin künye-okuma JSON (qwen3 sonucu)")
    a = ap.parse_args()
    try:
        tc = json.loads(a.text_credits)
    except Exception:
        tc = {}
    res = vl_fallback(a.clip, a.title, tc, a.profile)
    print(json.dumps(res, ensure_ascii=False))


if __name__ == "__main__":
    main()
