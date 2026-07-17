# -*- coding: utf-8 -*-
"""VL model kıyas — KÜNYE okuma, VIDEO modu (credit_video_read: kareler ardışık-video).
Aynı kareler, aynı prompt; tek değişen MODEL. Ham çıktıyı göster."""
import sys, io, os, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", write_through=True)
sys.path.insert(0, r"E:\MITAS\scripts")
import credit_video_read as cvr

FILMS = {
    "SILVERADO (İng, gerçek: Kevin Kline/Scott Glenn/Kevin Costner/Danny Glover; yön Lawrence Kasdan)":
        r"E:\MITAS\Database\evoArcadmin_COZUMLEMEV2S30_1985-0228-1-0000-00-1-SILVERADO",
    "ATTİLA MARCEL (Fr, yön Sylvain Chomet; Guillaume Gouix/Anne Le Ny)":
        r"E:\MITAS\Database\evoArcadmin__Z_MLEME10_2013-1015-1-0000-70-0-ATT_LA_MARCEL",
}
MODELS = ["qwen2.5vl:7b", "qwen3-vl:8b", "qwen3-vl:30b", "minicpm-v:latest"]

# kareleri önce hazırla (her film için cikis = son jenerik, yönetmen orada olur)
prepared = {}
for fname, hub in FILMS.items():
    cikis = cvr._even(cvr.list_frames(os.path.join(hub, "frames", "cikis")), 12)  # 12 kare = 16384 ctx'e sığar
    prepared[fname] = cikis
    print(f"[hazır] {fname.split('(')[0].strip()}: {len(cikis)} kare (cikis)", flush=True)

print("\n" + "="*78, flush=True)
# model-dış döngü: her model bir kez yüklenir (swap az)
for model in MODELS:
    print(f"\n############## MODEL: {model} ##############", flush=True)
    for fname, frames in prepared.items():
        t0 = time.perf_counter()
        try:
            out = cvr.read_segment(model, frames)
        except Exception as e:
            out = f"(HATA: {type(e).__name__}: {e})"
        dt = time.perf_counter() - t0
        print(f"\n--- {fname.split('(')[0].strip()} | {model} | {dt:.0f}s ---", flush=True)
        print((out or "(BOŞ)")[:900], flush=True)
print("\n=== BİTTİ ===", flush=True)
