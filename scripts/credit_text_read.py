#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""credit_text_read.py — OneOCR+GLM HAM METNİNDEN rol-eşleme (VLM-okuma YERİNE).

KURAL (Çağatay 2026-06-08): Okuma OneOCR+GLM ile yapılır; isimler OCR METNİNDEN gelir.
LLM yalnız ROL-EŞLEME yapar (pikselden OKUMAZ) → halüsinasyon imkânsız: her çıktı ismi
OCR metninde token olarak bulunmazsa ATILIR (anti-halüsinasyon kalkanı).

read_credits_from_text(lines, title, model) -> {"yonetmen":[...],"yapimci":[...],"cast":[...],"guven":...,"ham":...}

Akış: ham OCR satırları → LLM (rol-eşleme JSON, isim-metinden) → KALKAN (token-doğrulama) → KB'siz çıktı.
Doğrulama/afiş/tür sonradan credit_kb_lookup + tek_film_kunye kırmızı-çizgi mantığıyla yapılır.
"""
from __future__ import annotations
import json
import os
import re
import sys
import unicodedata
import urllib.request

OLLAMA = os.environ.get("MITAS_OLLAMA", "http://127.0.0.1:11434")
DEFAULT_MODEL = os.environ.get("MITAS_CREDIT_TEXT_MODEL", "qwen3:8b")

_TR_FOLD = str.maketrans("ışğçöüİIÄ", "isgcouiia")


def _fold(s: str) -> str:
    s = (s or "").casefold().translate(_TR_FOLD)
    s = "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9 ]+", " ", s)


def _toks(s: str):
    return [t for t in _fold(s).split() if len(t) > 2]


SCHEMA = {
    "type": "object",
    "properties": {
        "yonetmen": {"type": "array", "items": {"type": "string"}},
        "yapimci": {"type": "array", "items": {"type": "string"}},
        "oyuncular": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["yonetmen", "yapimci", "oyuncular"],
}

PROMPT = """Aşağıda bir filmin jeneriğinden (künye) OCR ile okunan satırlar var. Satırlar BOZUK/eksik olabilir.
GÖREVİN: bu satırlardan YÖNETMEN, YAPIMCI ve baş OYUNCULARI çıkarmak — YENİDEN OKUMAK ya da bilgiden EKLEMEK DEĞİL.

KESİN KURALLAR:
1. SADECE aşağıdaki satırlarda GEÇEN isimleri kullan. Kendi bilginden/hafızandan İSİM EKLEME, TAHMİN ETME. Bir alan satırlarda yoksa boş liste [] ver.
2. Bir satır "KARAKTER_ADI OYUNCU_ADI" biçimindeyse (ör. "CAL MORSE SAM WATERSTON", "FLETCHER REEDE JIM CARREY", "MARGARET THATCHER MERYL STREEP"), yalnız OYUNCU (gerçek kişi) adını al; KARAKTER adını KOYMA. Tek başına KARAKTER/ROL adı görünüyorsa (ör. yalnız "FLETCHER REEDE" veya "MARGARET THATCHER") onu LİSTEYE KOYMA — sadece gerçek oyuncu adlarını ver.
3. Rol etiketleri (DIRECTED BY, PRODUCED BY, YÖNETMEN, YAPIMCI, CAST, STARRING, THE END, MUSIC BY, WRITTEN BY...) ve şirket/kurum adları (FILM, FILMS, PRODUCTION, PICTURES, STUDIO, MEDIA, TV) İSİM DEĞİLDİR — listeye koyma.
4. YÖNETMEN: "DIRECTED BY / YÖNETMEN / UN FILM DE / REGIE / REALISE PAR" etiketinin YANINDAKİ veya hemen ALTINDAKİ kişi(ler). Etiket yoksa veya net değilse [] ver — ASLA tahmin etme. (Yardımcı yönetmen / görüntü yönetmeni / müzik yönetmeni / yapım yönetmeni YÖNETMEN DEĞİLDİR.)
5. OYUNCULAR: jenerikte görünen GERÇEK oyuncu adları (gerçek insanlar; karakter/rol adları DEĞİL), en fazla 8, görünme sırasıyla. Besteci/müzik, kurgu, senaryo, görüntü yönetmeni, yapımcı gibi EKİP üyeleri OYUNCU DEĞİLDİR — cast'e koyma.
6. YAPIMCI: "PRODUCED BY / YAPIMCI / PRODUCER" yanındaki kişi(ler). Besteci/müzik (COMPOSER/MUSIC BY), kurgu, senaryo YAPIMCI DEĞİLDİR — koyma. "Executive/Associate/Line/Co-producer / Yürütücü / Ortak yapımcı" da GERÇEK yapımcı sayılmaz.

ÇIKTI: yalnız JSON: {"yonetmen": [...], "yapimci": [...], "oyuncular": [...]}

SATIRLAR:
%s
"""


def _deepseek_json(model, prompt, timeout=120):
    """DeepSeek (API) JSON yanıtı — model adı 'deepseek*' ise. Anahtar yoksa {} (graceful)."""
    try:
        from _deepseek import deepseek_text
    except Exception:
        return {}
    txt = deepseek_text(prompt=prompt + "\n\nYALNIZ geçerli JSON döndür.",
                        model=model, temperature=0, max_tokens=1200,
                        fmt={"type": "json_object"}, timeout=timeout)
    if not txt:
        return {}
    try:
        return json.loads(txt)
    except Exception:
        i = txt.find("{")
        if i >= 0:
            try:
                return json.JSONDecoder().raw_decode(txt[i:])[0]
            except Exception:
                pass
    return {}


def _ollama_json(model, prompt, schema, timeout=180):
    body = json.dumps({
        "model": model, "prompt": prompt, "format": schema, "stream": False,
        "options": {"temperature": 0, "num_ctx": 8192},
    }).encode("utf-8")
    req = urllib.request.Request(OLLAMA + "/api/generate", data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        resp = json.loads(r.read().decode("utf-8"))
    txt = resp.get("response", "")
    try:
        return json.loads(txt)
    except Exception:
        i = txt.find("{")
        if i >= 0:
            try:
                return json.JSONDecoder().raw_decode(txt[i:])[0]
            except Exception:
                pass
    return {}


def _guard(names, ocr_fold_tokens, title_f):
    """Anti-halüsinasyon: her ismin anlamlı tokenlarının TÜMÜ OCR metninde geçmeli.
    Aksi halde isim UYDURMA → atılır. Şirket/etiket/başlık da elenir."""
    out, seen = [], set()
    for nm in names or []:
        nm = (nm or "").strip()
        if not nm:
            continue
        tk = _toks(nm)
        if not tk:
            continue
        # TÜM anlamlı tokenlar OCR metninde olmalı (halüsinasyon kalkanı)
        if not all(t in ocr_fold_tokens for t in tk):
            continue
        if _fold(nm).strip() == title_f:  # film adının kendisi isim değil
            continue
        k = " ".join(tk)
        if k in seen:
            continue
        seen.add(k)
        out.append(nm)
    return out


def read_credits_from_text(lines, title="", model=None, *, dizi=False):
    model = model or DEFAULT_MODEL
    lines = [l.strip() for l in (lines or []) if l and l.strip()]
    text = "\n".join(lines)
    ocr_tokens = set(_toks(text))
    title_f = _fold(title).strip()
    out = {"yonetmen": [], "yapimci": [], "cast": [], "guven": "OKUNAMADI", "model": model}
    if not lines:
        out["hata"] = "bos_metin"
        return out
    try:
        if str(model).startswith("deepseek"):
            raw = _deepseek_json(model, PROMPT % text)   # API (GPU çakışmaz)
        else:
            raw = _ollama_json(model, PROMPT % text, SCHEMA)
    except Exception as e:
        out["hata"] = f"{type(e).__name__}: {e}"
        return out
    out["ham"] = raw
    yon = _guard(raw.get("yonetmen"), ocr_tokens, title_f)
    yap = _guard(raw.get("yapimci"), ocr_tokens, title_f)
    cast = _guard(raw.get("oyuncular"), ocr_tokens, title_f)
    if not dizi:
        cast = cast[:8]
    out["yonetmen"], out["yapimci"], out["cast"] = yon, yap, cast
    if cast or yon:
        out["guven"] = "OKUNDU (metin-rol-eşleme)"
    return out


def model_chain():
    """Model zinciri (10-film bench kararı 2026-06-08):
      override (MITAS_CREDIT_TEXT_MODEL) → gemma3:12b (YEREL primer; ~DeepSeek kalite, hızlı,
      deterministik temp0, mandata-uygun) → qwen3:8b (yedek).
    DeepSeek API'ı kalite-booster olarak OPT-IN: MITAS_CREDIT_TEXT_MODEL=deepseek-chat.
    (qwen3.6:35b bench'te boş döndü — zincire alınmadı.)"""
    envm = os.environ.get("MITAS_CREDIT_TEXT_MODEL", "").strip()
    if envm:
        return [m.strip() for m in envm.split(",") if m.strip()]
    return ["gemma3:12b", "qwen3:8b"]


def read_credits_auto(lines, title="", *, dizi=False):
    """Model zincirini sırayla dene; ilk OKUYAN'da dur (fallback yalnız boş/hata olunca)."""
    res = {"yonetmen": [], "yapimci": [], "cast": [], "guven": "OKUNAMADI"}
    for m in model_chain():
        res = read_credits_from_text(lines, title, m, dizi=dizi)
        if res.get("cast") or res.get("yonetmen"):
            break
    return res


def main():
    import argparse
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--ocr", required=True, help="OneOCR+GLM kunye.txt yolu")
    ap.add_argument("--title", default="")
    ap.add_argument("--model", default=None)
    ap.add_argument("--dizi", action="store_true")
    a = ap.parse_args()
    lines = open(a.ocr, encoding="utf-8", errors="ignore").read().splitlines()
    res = read_credits_from_text(lines, a.title, a.model, dizi=a.dizi)
    print(json.dumps(res, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
