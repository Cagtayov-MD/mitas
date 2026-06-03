# -*- coding: utf-8 -*-
"""Keysiz dizi afis testi: 'bizim evin halleri' IMDb Suggestion API."""
import json, re, urllib.request, urllib.parse

OUT = r"E:\MITAS\OCR-worktree\pdf-mitas"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}


def fetch(url, b=False):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=25) as r:
        return r.read() if b else r.read().decode("utf-8", "replace")


q = "bizim evin halleri"
enc = urllib.parse.quote(q)
j = json.loads(fetch(f"https://v3.sg.media-imdb.com/suggestion/x/{enc}.json"))
res = j.get("d", [])
print("sorgu:", q, "| sonuc:", len(res))
for d in res:
    has = "AFİŞ" if d.get("i", {}).get("imageUrl") else "yok"
    print(f"  {str(d.get('id','?')):12} | {str(d.get('q','?')):12} | {str(d.get('y','?')):6} | {has:5} | {d.get('l','')}")

cand = next((d for d in res if str(d.get("id", "")).startswith("tt") and d.get("i", {}).get("imageUrl")), None)
if cand:
    img = cand["i"]["imageUrl"]
    big = re.sub(r"(@+)\._V1_.*$", r"\1._V1_SX1000.jpg", img) if "._V1_" in img \
        else re.sub(r"(@+)\.jpg$", r"\1._V1_SX1000.jpg", img)
    data = fetch(big, True)
    with open(OUT + r"\afis_bizimevinhalleri.jpg", "wb") as f:
        f.write(data)
    print("\nİNDİRİLDİ:", cand["id"], "|", cand.get("l"), "|", cand.get("y"), "|", len(data), "bytes")
else:
    print("\nAFİŞ YOK — bu sorgudan görsel dönmedi (fallback gerekir)")
