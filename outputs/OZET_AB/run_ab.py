# -*- coding: utf-8 -*-
"""Özet prompt A/B: ESKİ (ozet_film_OLD.txt) vs YENİ (core/api/prompts/ozet_film.txt).
Üretimle BİREBİR: yerel gemma4-31b (ollama), think=False, temp 0.0, num_predict=1500,
aynı transcript kırpma (_ozet_source_text) ve _latin_only kemeri.
Çıktı: outputs/OZET_AB/SONUC.md (yan yana, kelime sayılı)."""
import json
import time
import unicodedata
import urllib.request
from pathlib import Path

DB = Path(r"E:\MITAS\Database")
HERE = Path(r"E:\MITAS\outputs\OZET_AB")
OLD_PROMPT = (HERE / "ozet_film_OLD.txt").read_text(encoding="utf-8")
NEW_PROMPT = Path(r"E:\MITAS\core\api\prompts\ozet_film.txt").read_text(encoding="utf-8")

MODEL = "gemma4:26b"   # Çağatay: özeti 26b iyi yazıyor (31b'nin özet yeteneği yok); üretim default'u da bu
OLLAMA = "http://127.0.0.1:11434"
MAX_TOKENS = 1500
TIMEOUT = 90
MAX_SOURCE_CHARS = 60000

# (başlık, transcript yolu, süre)
FILMS = [
    ("X-MEN BAŞLANGIÇ WOLVERINE", r"X MEN BAŞLANGIÇ WOLVERINE 2009-9147-1-0000-90-1\asr\asr-2e4dca6a\run\transcript.txt", "107 dk"),
    ("FARGO",                      r"FARGO 1996-1042-1-0000-50-0\asr\asr-fed2b4c4\run\transcript.txt", "98 dk"),
    ("ALİTA SAVAŞ MELEĞİ",         r"ALİTA SAVAŞ MELEĞİ 2025-1241-1-0000-90-1\asr\asr-0867af09\run\transcript.txt", "122 dk"),
    ("FRANTZ",                     r"FRANTZ 2016-1188-1-0000-70-0 2\asr\asr-e4804a26\run\transcript.txt", "113 dk"),
    ("FLASHDANCE",                 r"FLASHDANCE 1983-0267-1-0000-00-1\asr\asr-8419874c\run\transcript.txt", "95 dk"),
    ("FRANKIE VE JOHNNY",          r"FRANKIE VE JOHNNY 2003-9107-1-0000-00-1\asr\asr-1dcb5c23\run\transcript.txt", "118 dk"),
    ("CEMİLE",                     r"CEMİLE 1998-0498-1-0000-00-1\asr\asr-5b4f1329\run\transcript.txt", "90 dk"),
]

_FOLD = str.maketrans({
    "à":"a","á":"a","â":"a","ã":"a","ä":"a","å":"a","ā":"a","ą":"a","À":"A","Á":"A","Â":"A","Ã":"A","Ä":"A","Å":"A","Ā":"A","Ą":"A",
    "è":"e","é":"e","ê":"e","ë":"e","ē":"e","ę":"e","ě":"e","È":"E","É":"E","Ê":"E","Ë":"E","Ē":"E","Ę":"E","Ě":"E",
    "ì":"i","í":"i","î":"i","ï":"i","ī":"i","Ì":"I","Í":"I","Î":"I","Ï":"I","Ī":"I",
    "ò":"o","ó":"o","ô":"o","õ":"o","ø":"o","ō":"o","Ò":"O","Ó":"O","Ô":"O","Õ":"O","Ø":"O","Ō":"O",
    "ù":"u","ú":"u","û":"u","ū":"u","Ù":"U","Ú":"U","Û":"U","Ū":"U",
    "ñ":"n","ń":"n","Ñ":"N","Ń":"N","ć":"c","č":"c","Ć":"C","Č":"C","ś":"s","š":"s","Ś":"S","Š":"S",
    "ź":"z","ż":"z","ž":"z","Ź":"Z","Ż":"Z","Ž":"Z","ý":"y","ÿ":"y","Ý":"Y","ł":"l","Ł":"L","đ":"d","Đ":"D",
    "ß":"ss","æ":"ae","Æ":"AE","œ":"oe","Œ":"OE",
})

def latin_only(s):
    return "".join(ch for ch in (s or "").translate(_FOLD)
                   if ch.isascii() or unicodedata.category(ch)[0] != "L" or "LATIN" in unicodedata.name(ch, ""))

def source_text(t):
    if len(t) <= MAX_SOURCE_CHARS:
        return t
    head = t[:25000]
    ms = max(0, len(t)//2 - 7500)
    mid = t[ms:ms+15000]
    tail = t[-20000:]
    return f"{head}\n\n[... orta bolumden secki ...]\n\n{mid}\n\n[... son bolum ...]\n\n{tail}"

def gemma(system, user):
    body = json.dumps({"model": MODEL, "system": system, "prompt": user,
                       "stream": False, "think": False,
                       "options": {"temperature": 0.0, "num_predict": MAX_TOKENS}}).encode("utf-8")
    req = urllib.request.Request(OLLAMA + "/api/generate", data=body,
                                 headers={"Content-Type": "application/json"}, method="POST")
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        out = json.loads(r.read().decode("utf-8"))
    return (out.get("response") or "").strip(), time.time()-t0

def wc(s):
    return len(s.split())

rows = []
for title, rel, dur in FILMS:
    p = DB / rel
    if not p.exists():
        print(f"YOK: {title}")
        continue
    tr = p.read_text(encoding="utf-8", errors="replace")
    user = f"Dosya: {title}\nSüre: {dur}\n\nTRANSKRİPT:\n{source_text(tr)}"
    print(f"[{title}] eski...", flush=True)
    old_raw, ot = gemma(OLD_PROMPT, user)
    old = latin_only(old_raw.strip())
    print(f"[{title}] yeni...", flush=True)
    new_raw, nt = gemma(NEW_PROMPT, user)
    new = latin_only(new_raw.strip())
    rows.append((title, old, wc(old), ot, new, wc(new), nt))
    print(f"  eski {wc(old)}k {ot:.1f}s | yeni {wc(new)}k {nt:.1f}s", flush=True)

lines = ["# Özet Prompt A/B — ESKİ vs YENİ", "",
         f"Model: `{MODEL}` (yerel, think=False, temp=0.0)  ·  {len(rows)} film", ""]
for title, old, ow, ot, new, nw, nt in rows:
    lines += [f"## {title}", "",
              f"**ESKİ** ({ow} kelime, {ot:.1f}s)", "", f"> {old}", "",
              f"**YENİ** ({nw} kelime, {nt:.1f}s)", "", f"> {new}", "", "---", ""]
(HERE / "SONUC.md").write_text("\n".join(lines), encoding="utf-8")
print("\nYAZILDI: outputs/OZET_AB/SONUC.md")
