# -*- coding: utf-8 -*-
"""MITAS — isim karakter normalizasyonu (Türkçe koru / diğer dil ASCII).

KURAL (Çağatay, 2026-06-02):
  • Türkçe isimler  →  ç ğ ı İ ö ş ü KORUNUR.
  • Diğer diller    →  ASCII (aksanlar düşürülür: é→e, ñ→n, ø→o, ü(Almanca)→u ...).

Türkçe-mi kararı:
  1) Heuristik: ı/İ/ş/ğ içeriyorsa → Türkçe (kesin).  Yabancı aksan (é,ñ,ø,ä...) → değil.
     Saf ASCII → zaten değişmez (karar gereksiz).
  2) SADECE ç/ö/ü içeren isim BELİRSİZ (Türkçe de Almanca/Fransızca da olabilir) →
     "gerekirse" QWEN'e sorulur (Ollama). Qwen yoksa güvenli taraf = ASCII.

Kullanan: scripts/_pipe_pdf.py + py/20260601_kunye_to_pdf.py (cast + crew isimleri).
"""
from __future__ import annotations
import json
import unicodedata
import urllib.request

_SPECIAL = {
    "ø": "o", "Ø": "O", "ł": "l", "Ł": "L", "đ": "d", "Đ": "D", "þ": "th", "Þ": "Th",
    "ß": "ss", "æ": "ae", "Æ": "Ae", "œ": "oe", "Œ": "Oe", "ð": "d", "Ð": "D",
}
_TR_STRONG = set("ışğİıŞĞ")       # ı, ş, ğ, İ — güçlü Türkçe sinyali
_TR_AMBIG = set("çöüÇÖÜ")          # ç, ö, ü — Türkçe VEYA Almanca/Fransızca (belirsiz)

OLLAMA_URL = "http://127.0.0.1:11434/api/chat"
QWEN_MODEL = "qwen3:8b"            # hızlı metin modeli (ollama list'te mevcut)


def ascii_fold(s: str) -> str:
    """Aksanları düşürerek ASCII'ye indir (Türkçe dahil tüm özel harfler)."""
    out = []
    for ch in s:
        if ch in _SPECIAL:
            out.append(_SPECIAL[ch])
            continue
        dec = "".join(c for c in unicodedata.normalize("NFKD", ch) if not unicodedata.combining(c))
        out.append(dec if dec.isascii() else "")
    return "".join(out)


def classify(name: str) -> str:
    """'tr' (Türkçe, koru) | 'ascii' (yabancı, indir) | 'ask' (belirsiz → Qwen) | 'keep' (saf ASCII)."""
    if any(c in _TR_STRONG for c in name):
        return "tr"
    has_ambig = False
    for ch in name:
        if ch in _TR_AMBIG:
            has_ambig = True
        elif not ch.isascii() and unicodedata.category(ch).startswith("L"):
            return "ascii"  # yabancı aksan (é, ñ, ø, ä...) → kesin yabancı
    return "ask" if has_ambig else "keep"


def qwen_is_turkish(names: list[str], model: str = QWEN_MODEL, timeout: int = 60) -> dict[str, bool]:
    """Belirsiz isimleri Qwen'e (Ollama) sor. {isim: True/False}. Hata/yoksa boş döner."""
    names = [n for n in names if n]
    if not names:
        return {}
    listing = "\n".join(f"- {n}" for n in names)
    prompt = (
        "Görev: Aşağıdaki kişi isimlerinin her biri TÜRKÇE bir isim mi (bir Türk'ün ismi) "
        "yoksa yabancı bir isim mi? Sadece geçerli JSON döndür, açıklama yok. "
        'Biçim: {"İsim Soyisim": true, ...}  (true=Türkçe, false=yabancı). /no_think\n\n' + listing
    )
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "format": "json",
        "options": {"temperature": 0, "num_predict": 512},
    }).encode("utf-8")
    try:
        req = urllib.request.Request(OLLAMA_URL, data=body, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            resp = json.loads(r.read())
        content = (resp.get("message") or {}).get("content", "")
        data = json.loads(content)
        # anahtar eşleşmesini gevşet (fold)
        norm = {_fold(k): bool(v) for k, v in data.items()}
        return {n: norm.get(_fold(n), False) for n in names if _fold(n) in norm}
    except Exception:  # noqa: BLE001 - Qwen yoksa sessiz geç
        return {}


def _fold(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", (s or "").casefold()) if not unicodedata.combining(c)).strip()


def normalize_names(names, *, use_qwen: bool = True) -> list[str]:
    """İsim listesini kurala göre normalize et. Belirsizleri (sadece ç/ö/ü) Qwen'e sorar."""
    if not names:
        return names
    verdict: dict[str, str] = {n: classify(n) for n in names}
    ask = [n for n, v in verdict.items() if v == "ask"]
    qmap: dict[str, bool] = {}
    if ask and use_qwen:
        qmap = qwen_is_turkish(ask)
    out = []
    for n in names:
        v = verdict[n]
        if v == "tr" or v == "keep":
            out.append(n)                                   # Türkçe ya da saf ASCII → koru
        elif v == "ascii":
            out.append(ascii_fold(n))                       # yabancı aksan → ASCII
        else:  # 'ask'
            is_tr = qmap.get(n, False)                      # Qwen dönmediyse güvenli = yabancı
            out.append(n if is_tr else ascii_fold(n))
    return out


def normalize_crew(crew, *, use_qwen: bool = True):
    """crew = [(rol, [isim...])] → isimleri normalize et, rol etiketleri Türkçe sabit kalır."""
    flat = [nm for _, names in crew for nm in (names if isinstance(names, list) else [names])]
    mapping = dict(zip([_fold(x) for x in flat], normalize_names(flat, use_qwen=use_qwen)))
    out = []
    for role, names in crew:
        nl = names if isinstance(names, list) else [names]
        out.append((role, [mapping.get(_fold(x), x) for x in nl]))
    return out
