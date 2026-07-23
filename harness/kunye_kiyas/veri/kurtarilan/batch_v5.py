#!/usr/bin/env python3
"""Tüm pool_frames klasörlerinde v5 koştur → tahminleri JSON'a yaz."""
import sys, glob, json, os, re, time
sys.path.insert(0, "/opt/mitas/harness/kunye_kiyas")
import credit_onset as co

S = "/tmp/claude-1000/-opt-mitas/1bd0cb57-0064-4841-b568-8555832193d6/scratchpad"
dizinler = sorted(glob.glob(f"{S}/pool_frames/*/"))
sonuc = []
for d in dizinler:
    ad = os.path.basename(d.rstrip("/"))
    yil = int((re.search(r"(\d{4})", ad) or ["0"])[0] or 0)
    n = len(glob.glob(d + "*.png"))
    if n < 50:
        continue
    t = time.time()
    try:
        r = co.tespit_v5(d)
        sonuc.append({"film": ad, "yil": yil, "kare": n,
                      "tahmin": r.start_frame, "yontem": r.yontem,
                      "guven": r.guven, "notlar": r.notlar, "sure": round(time.time() - t, 1)})
        print(f"[{yil}] {ad[:34]:<35} → {r.start_frame:>5} ({r.yontem}) {round(time.time()-t)}s", flush=True)
    except Exception as e:
        sonuc.append({"film": ad, "yil": yil, "kare": n, "tahmin": "HATA", "notlar": str(e)[:80]})
        print(f"[{yil}] {ad[:34]:<35} → HATA {str(e)[:40]}", flush=True)
    json.dump(sonuc, open(f"{S}/v5_tahminler.json", "w"), ensure_ascii=False, indent=1)
print(f"\nBİTTİ: {len(sonuc)} film → v5_tahminler.json")
