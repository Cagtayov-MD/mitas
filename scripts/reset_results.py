#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""reset_results.py — E:\\filmtest\\aaaa filmlerinin ÖNCEKİ SONUÇLARINI (Database türetilmiş veri +
DUZELTILMIS_44) re-run öncesi temizler. KAYNAK filmlere (E:\\filmtest\\aaaa) DOKUNMAZ.
Kalıcı silmez → aynı diskte _RESET_TEMIZLE'ye TAŞIR (geri alınabilir; Çağatay sonra boşaltıp diski açar).
DRY-RUN varsayılan; uygulamak için: ... reset_results.py --apply"""
import os, re, sys, glob, shutil
sys.stdout.reconfigure(encoding="utf-8")

DRY = "--apply" not in sys.argv
SRC_FILMS = r"E:\filmtest\aaaa"
DB = r"E:\MITAS\Database"
DEST_OUT = r"E:\MITAS\Mitas Output\DUZELTILMIS_44"
RESET = r"E:\MITAS\_RESET_TEMIZLE"
TRT = re.compile(r"(\d{4}-\d{3,4}-\d-\d{4}-\d{2}-\d)")

film_ids = set()
for pat in ("*.mp4", "*.MP4", "*.mxf", "*.MXF"):
    for f in glob.glob(os.path.join(SRC_FILMS, pat)):
        m = TRT.search(os.path.basename(f))
        if m:
            film_ids.add(m.group(1))
print(f"E:\\filmtest\\aaaa kaynak film (TRT-id'li): {len(film_ids)}")

def dsize(p):
    t = 0
    for r, _, fs in os.walk(p):
        for fn in fs:
            try:
                t += os.path.getsize(os.path.join(r, fn))
            except Exception:
                pass
    return t

targets = []
for d in glob.glob(os.path.join(DB, "*")):
    if not os.path.isdir(d):
        continue
    m = TRT.search(os.path.basename(d))
    if m and m.group(1) in film_ids:
        targets.append(d)

print(f"\n=== Eşleşen Database klibi (TAŞINACAK): {len(targets)} ===")
tot = 0
for d in sorted(targets):
    sz = dsize(d); tot += sz
    print(f"  {sz/1e6:8.0f} MB  {os.path.basename(d)}")
if os.path.isdir(DEST_OUT):
    sz = dsize(DEST_OUT); tot += sz
    print(f"  {sz/1e6:8.0f} MB  [Mitas Output/DUZELTILMIS_44]")
print(f"\nTOPLAM: {tot/1e9:.2f} GB  →  {RESET}")

# eşleşmeyen ama yakın-zamanlı klipler (sınır görünürlüğü — bunlara DOKUNULMAZ)
unmatched = [os.path.basename(d) for d in glob.glob(os.path.join(DB, "*"))
             if os.path.isdir(d) and not (TRT.search(os.path.basename(d)) and TRT.search(os.path.basename(d)).group(1) in film_ids)]
print(f"\n(DOKUNULMAYAN diğer Database klibi: {len(unmatched)} — ör: {', '.join(sorted(unmatched)[:5])}…)")

if DRY:
    print("\n>>> DRY-RUN — hiçbir şey taşınmadı. Uygulamak için: --apply")
else:
    os.makedirs(RESET, exist_ok=True)
    moved = 0
    for d in targets:
        dst = os.path.join(RESET, os.path.basename(d))
        if os.path.exists(dst):
            dst = dst + "_dup"
        shutil.move(d, dst); moved += 1
    if os.path.isdir(DEST_OUT):
        shutil.move(DEST_OUT, os.path.join(RESET, "DUZELTILMIS_44"))
        moved += 1
    print(f"\n>>> TAŞINDI: {moved} öğe → {RESET}  (geri alınabilir; diski açmak için bu klasörü SEN sil)")
print("RESET_DONE")
