#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
smoke_ollama_only.py
gemma3:12b ve gemma4:26b (referans) karşılaştırmalı smoke test
3 film x 2 model = 6 çalışma
"""
import base64, glob, io, json, os, re, sys, time, unicodedata, urllib.request
from pathlib import Path
from PIL import Image

OUTPUT_DIR = r"E:\MITAS\outputs\model_test"
OLLAMA_BASE = "http://127.0.0.1:11434"
FRAME_W = 640
BUDGET = 10

PROMPT = (
    "Bunlar bir film jeneriğinin ARDIŞIK kareleri (video). Kareler boyunca görünen yazıları "
    "birleştirerek şunları bul. SADECE karelerde AÇIKÇA YAZAN isimleri kullan, uydurma; yoksa 'yok'. "
    "Çıktıyı tam olarak şu formatta ver:\n"
    "YÖNETMEN: <Director/Yöneten/Rejisör yanındaki isim | yok>\n"
    "YAPIMCI: <Producer/Yapımcı/Executive Producer yanındaki isim(ler) | yok>\n"
    "OYUNCULAR: <görünen başrol oyuncu adları, en fazla 8, virgülle | yok>"
)

GOLD = {
    "DRAKULA": {
        "yonetmen": ["Terence Fisher"],
        "oyuncular": ["Peter Cushing", "Martita Hunt", "Yvonne Monlaur", "David Peel"]
    },
    "ATTILA": {
        "yonetmen": ["Sylvain Chomet"],
        "oyuncular": ["Guillaume Gouix", "Anne Le Ny", "Bernadette Lafont"]
    },
    "YALAZA": {
        "yonetmen": [],
        "oyuncular": []
    }
}

TEST_FILMS = [
    {
        "id": "DRAKULA",
        "label": "DRAKULA'NIN GELİNLERİ (1960)",
        "folders": [
            r"E:\MITAS\Database\evoArcadmin_COZUMLEMEV2S17_1960-0046-1-0000-00-1-DRAKULA_NIN_GEL_NLER\frames\giris",
            r"E:\MITAS\Database\evoArcadmin_COZUMLEMEV2S17_1960-0046-1-0000-00-1-DRAKULA_NIN_GEL_NLER\frames\cikis",
        ]
    },
    {
        "id": "ATTILA",
        "label": "ATTİLA MARCEL (2013)",
        "folders": [
            r"E:\MITAS\Database\evoArcadmin_S_NEMA_F_LM4_2013-1015-1-0000-70-1-ATT_LA_MARCEL\frames\giris",
            r"E:\MITAS\Database\evoArcadmin_S_NEMA_F_LM4_2013-1015-1-0000-70-1-ATT_LA_MARCEL\frames\cikis",
        ]
    },
    {
        "id": "YALAZA",
        "label": "YALAZA (Türkçe-isim testi)",
        "folders": [
            r"E:\MITAS\Database\web_client_dad_2017-0019-0-0001-90-1-YALAZA\frames\giris",
        ]
    },
]

def fold(s):
    s = s or ""
    for a, b in (("İ","i"),("I","i"),("ı","i"),("Ş","s"),("ş","s"),
                 ("Ğ","g"),("ğ","g"),("Ü","u"),("ü","u"),
                 ("Ö","o"),("ö","o"),("Ç","c"),("ç","c")):
        s = s.replace(a, b)
    s = unicodedata.normalize("NFKD", s).encode("ascii","ignore").decode().lower()
    return re.sub(r"\s+", " ", s).strip()

def score(text, names):
    ft = fold(text)
    hits = sum(1 for n in names if fold(n) in ft)
    return hits, len(names)

def sample_frames(folders, budget):
    all_frames = []
    for folder in folders:
        if os.path.exists(folder):
            frames = sorted(glob.glob(os.path.join(folder, "*.png"))) or \
                     sorted(glob.glob(os.path.join(folder, "*.jpg")))
            all_frames.extend(frames)
    if not all_frames:
        return []
    step = max(1, len(all_frames) // budget)
    return all_frames[::step][:budget]

def to_b64(path, w=FRAME_W):
    img = Image.open(path).convert("RGB")
    ww, hh = img.size
    if ww > w:
        img = img.resize((w, int(hh*w/ww)), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return base64.b64encode(buf.getvalue()).decode()

def call_model(model, frames, prompt, timeout=300):
    images = []
    for f in frames:
        try:
            images.append(to_b64(f))
        except Exception as e:
            print(f"    [kare hata: {e}]")
    if not images:
        return "[kare yok]", 0.0
    payload = json.dumps({
        "model": model,
        "messages": [{"role":"user","content":prompt,"images":images}],
        "stream": False,
        "options": {"num_ctx":8192,"num_predict":600,"temperature":0,"think":False}
    }).encode("utf-8")
    req = urllib.request.Request(OLLAMA_BASE+"/api/chat", data=payload,
                                  headers={"Content-Type":"application/json"})
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = json.loads(r.read())
        elapsed = time.time()-t0
        text = raw.get("message",{}).get("content","") or raw.get("response","")
        return text.strip(), elapsed
    except Exception as e:
        return f"[HATA:{e}]", time.time()-t0


MODELS = [
    ("gemma3:12b",  "gemma3:12b (YENİ, 8.1GB)"),
    ("gemma4:26b",  "gemma4:26b (REFERANS, 17GB)"),
]

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    all_results = []

    for model_tag, model_label in MODELS:
        print(f"\n{'='*60}")
        print(f"MODEL: {model_label}")
        print(f"{'='*60}")
        model_res = {"model": model_tag, "label": model_label, "durum": "OK", "filmler": []}

        for film in TEST_FILMS:
            frames = sample_frames(film["folders"], BUDGET)
            if not frames:
                print(f"  {film['id']}: KARE YOK")
                model_res["filmler"].append({"id":film["id"],"durum":"KARE_YOK"})
                continue

            print(f"\n  [{film['id']}] {len(frames)} kare gönderiliyor...", flush=True)
            text, elapsed = call_model(model_tag, frames, PROMPT)
            print(f"  Süre: {elapsed:.1f}s")
            print(f"  Çıktı:\n{text}")

            gold = GOLD.get(film["id"],{})
            hy, ty = score(text, gold.get("yonetmen",[]))
            ho, to_ = score(text, gold.get("oyuncular",[]))
            has_tr = any(c in text for c in "İıŞşĞğÜüÖöÇç")
            print(f"  Skor — Yönetmen:{hy}/{ty} Oyuncu:{ho}/{to_} TR-karakter:{has_tr}")

            model_res["filmler"].append({
                "id": film["id"], "label": film["label"],
                "kare_sayisi": len(frames), "sure_sn": round(elapsed,1),
                "cikti": text,
                "hit_yonetmen": f"{hy}/{ty}", "hit_oyuncu": f"{ho}/{to_}",
                "turkce_karakter": has_tr,
            })

        all_results.append(model_res)

    # Kaydet
    out_j = os.path.join(OUTPUT_DIR, "ollama_smoke.json")
    with open(out_j, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)

    out_t = os.path.join(OUTPUT_DIR, "ollama_smoke.txt")
    lines = ["MITAS OLLAMA SMOKE TEST (gemma3:12b vs gemma4:26b)", "="*60, ""]
    for r in all_results:
        lines.append(f"=== {r['label']} ===")
        for film in r.get("filmler",[]):
            if "hit_oyuncu" in film:
                lines.append(
                    f"  [{film['id']:8s}] Yönetmen:{film['hit_yonetmen']:4s} "
                    f"Oyuncu:{film['hit_oyuncu']:4s} "
                    f"TR:{str(film['turkce_karakter']):5s} "
                    f"Süre:{film['sure_sn']}s"
                )
                lines.append(f"    Çıktı: {film['cikti'][:300]}")
        lines.append("")
    with open(out_t, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"\n\nJSON: {out_j}")
    print(f"TXT:  {out_t}")

if __name__ == "__main__":
    main()
