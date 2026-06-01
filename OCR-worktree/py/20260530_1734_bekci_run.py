"""20260530_1734 — BEKÇİ koşumu (göz = qwen2.5vl), makinede VAR olan karelerle.
Orijinal _llm_eye_discriminate ground-truth'u ocr_50films yollarına bakıyordu (bu makinede yok).
Burada GT = bu oturumda GÖZLE doğruladığım, mevcut kareler. Ayrıca 3 diziyi ffmpeg'le örnekleyip
göz'e sokuyoruz (etiketsiz — qwen ne diyor görelim).
"""
import sys, json, base64, time, subprocess, urllib.request
from pathlib import Path

OLLAMA = "http://localhost:11434/api/generate"
FFMPEG = r"E:\MITAS\tools\ffmpeg-shared\ffmpeg-8.1.1-full_build-shared\bin\ffmpeg.exe"
META   = r"E:\MITAS\_jenerik_analysis\dense5_metadata.json"
MODEL  = sys.argv[1] if len(sys.argv) > 1 else "qwen2.5vl:7b"
OUT    = Path(r"E:\MITAS\OCR-worktree\out\bekci_20260530_1734"); OUT.mkdir(parents=True, exist_ok=True)

PROMPT = (
    "You are inspecting ONE still frame from an old film/TV. Decide whether it shows "
    "CREDITS/TITLE/CAPTION text or ordinary footage. Reply ONE JSON object, keys EXACTLY:\n"
    '  "has_text": true/false,\n'
    '  "text_color": "bright"|"dark"|"none",\n'
    '  "background": "solid"|"footage" (solid=plain/black backdrop; footage=live scene),\n'
    '  "is_credit": true/false (true if part of a credits/title/caption sequence; false if plain footage with NO overlaid text).\n'
    "JSON only."
)

YT = r"E:\MITAS\OCR-worktree\out\yol_test_20260530_1645"
AN = r"E:\MITAS\outputs\ocr_4films_boxtrack_20260523\items\anjelik_ve_sultan_1968_end_credits\frames"
# (yol, ground-truth, açıklama) — hepsi bu oturumda GÖZLE doğrulandı
GT = [
    (rf"{YT}\22_yabandan_giris\frames\f_00100.png", dict(has_text=True, text_color="bright", background="solid", is_credit=True), "yabandan 'A DRAWING...' siyah-zemin kart"),
    (rf"{YT}\22_yabandan_giris\frames\f_00400.png", dict(has_text=False, text_color="none", background="footage", is_credit=False), "yabandan SAF FILM (manzara)"),
    (rf"{YT}\15_pilkington_giris\frames\f_00150.png", dict(has_text=True, text_color="bright", background="footage", is_credit=True), "pilkington 'with GARY...' sokak ustu"),
    (rf"{AN}\frame_00750.png", dict(has_text=True, text_color="bright", background="footage", is_credit=True), "anjelik scroll / oynayan deniz"),
    (rf"{AN}\frame_00060.png", dict(has_text=False, text_color="none", background="footage", is_credit=False), "anjelik SAF FILM (kadin yuzu)"),
]

# eklenen 3 dizi (etiketsiz): idx -> jenerik anlari (saniye, etiket)
DIZI = {
    50: ("dirilis_ertugrul", [(640, "giris_main"), (700, "giris_main2"), (8320, "cikis"), (8360, "cikis2")]),
    51: ("bizim_evin",       [(15, "giris"), (55, "giris2"), (1440, "son_check"), (1465, "son_check2")]),
    52: ("beni_boyle_sev",   [(15, "giris"), (55, "giris2"), (6420, "cikis"), (6465, "cikis2")]),
}

def ask(path):
    payload = {"model": MODEL, "prompt": PROMPT, "stream": False, "format": "json",
               "keep_alive": "10m", "options": {"temperature": 0},
               "images": [base64.b64encode(Path(path).read_bytes()).decode()]}
    req = urllib.request.Request(OLLAMA, json.dumps(payload).encode(), {"Content-Type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=600) as r:
        return json.loads(json.loads(r.read()).get("response", "{}")), time.time()-t0

def grab(video, t, outp):
    subprocess.run([FFMPEG, "-y", "-ss", str(t), "-i", video, "-frames:v", "1", "-q:v", "2", str(outp)],
                   capture_output=True)
    return outp.exists()

def main():
    try: sys.stdout.reconfigure(encoding="utf-8")
    except Exception: pass
    meta = {int(it["idx"]): it["path"] for it in json.loads(Path(META).read_text(encoding="utf-8"))}
    print(f"MODEL={MODEL}\n{'='*90}\n[1] GROUND-TRUTH (bekçi doğruluk)")
    hits = 0; n = 0
    for path, gt, desc in GT:
        if not Path(path).exists(): print(f"  [YOK] {desc}"); continue
        n += 1
        try: pred, dt = ask(path)
        except Exception as e: print(f"  [HATA] {desc}: {e}"); continue
        ok = str(pred.get("is_credit")).lower() == str(gt["is_credit"]).lower()
        hits += ok
        print(f"  [{'✓' if ok else '✗'}] {desc}: is_credit GT={gt['is_credit']} PRED={pred.get('is_credit')} "
              f"| bg={pred.get('background')} text={pred.get('text_color')} ({dt:.0f}s)")
    print(f"\n  BEKÇİ doğruluk (is_credit) = {hits}/{n}")

    print(f"\n{'='*90}\n[2] EKLENEN 3 DİZİ (etiketsiz — göz ne diyor)")
    dizi_out = []
    for idx, (name, shots) in DIZI.items():
        video = meta[idx]; print(f"\n  --- {name} (idx {idx}) ---  video_ok={Path(video).exists()}")
        for t, tag in shots:
            outp = OUT / f"{idx}_{name}_{tag}_{t}s.png"
            if not grab(video, t, outp): print(f"    [grab YOK] {tag} {t}s"); continue
            try: pred, dt = ask(outp)
            except Exception as e: print(f"    [HATA] {tag}: {e}"); continue
            print(f"    {tag:12} {t:5}s -> is_credit={pred.get('is_credit')} has_text={pred.get('has_text')} "
                  f"bg={pred.get('background')} color={pred.get('text_color')}")
            dizi_out.append(dict(idx=idx, name=name, tag=tag, t=t, png=str(outp), pred=pred))
    (OUT/"_dizi.json").write_text(json.dumps(dizi_out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nOUT -> {OUT}  (dizi kareleri + _dizi.json)")

if __name__ == "__main__":
    main()
