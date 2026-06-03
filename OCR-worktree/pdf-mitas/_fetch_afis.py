# -*- coding: utf-8 -*-
"""Keysiz afis indirme PoC: IMDb Suggestion API -> Amazon CDN (boyut hilesi)."""
import json, re, urllib.request

OUT = r"E:\MITAS\OCR-worktree\pdf-mitas"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}


def fetch(url, binary=False):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=25) as r:
        return r.read() if binary else r.read().decode("utf-8", "replace")


def afis(query, save_as):
    j = json.loads(fetch(f"https://v3.sg.media-imdb.com/suggestion/x/{query}.json"))
    item = next((d for d in j.get("d", [])
                 if str(d.get("id", "")).startswith("tt") and d.get("i", {}).get("imageUrl")), None)
    if not item:
        print("BULUNAMADI:", query); return None
    img = item["i"]["imageUrl"]
    if "._V1_" in img:
        big = re.sub(r"(@+)\._V1_.*$", r"\1._V1_SX1000.jpg", img)
    else:
        big = re.sub(r"(@+)\.jpg$", r"\1._V1_SX1000.jpg", img)
    data = fetch(big, True)
    path = OUT + "\\" + save_as
    with open(path, "wb") as f:
        f.write(data)
    print(f"{item['id']}  {item['l']}  |  {len(data)} bytes  |  {save_as}")
    return path


afis("inception", "afis_inception.jpg")
print("bitti")
