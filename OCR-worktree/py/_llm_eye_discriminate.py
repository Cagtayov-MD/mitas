"""LLM-EYE deneyi — KARAR 3'ün 'bekçi'si: jenerik mi / film footage mı?

Yerel görsel-LLM'e (Ollama) tek kare verip 4 yargı sorar ve GROUND TRUTH ile karşılaştırır:
  has_text   : karede overlaid jenerik/başlık/altyazı yazısı var mı?
  text_color : yazı parlak (beyaz/açık) mı, koyu mu, yok mu?
  background : zemin düz/tek-renk/siyah mı yoksa canlı film footage'ı mı?
  is_credit  : bu kare bir JENERİK/başlık/altyazı dizisi mi, yoksa düz film footage mı? (BEKÇİ kararı)

Ollama HTTP API (stdlib urllib; harici bağımlılık yok). format=json ile geçerli JSON zorlanır.
"""
import argparse, base64, json, time, urllib.request
from pathlib import Path

OLLAMA = "http://localhost:11434/api/generate"

PROMPT = (
    "You are inspecting ONE still frame taken from an old film. "
    "Your job: decide whether it shows CREDITS / TITLE / CAPTION text, or ordinary film footage. "
    "Reply with a SINGLE JSON object, keys EXACTLY:\n"
    '  "has_text": true/false  (is there any overlaid title/credit/caption TEXT visible),\n'
    '  "text_color": "bright" | "dark" | "none"  (bright = white/light letters; none = no text),\n'
    '  "background": "solid" | "footage"  (solid = plain single color or black backdrop; '
    'footage = a live filmed scene with people/landscape/objects),\n'
    '  "is_credit": true/false  (true if this frame is part of a credits/title/caption sequence; '
    "false if it is ordinary film footage with NO overlaid text).\n"
    "JSON only, no commentary."
)

BASE = r"E:/MITAS/outputs/ocr_50films_aaaa_v21_paddle_20260525/items"
TESTS = [
    (f"{BASE}/1968_anjelik_ve_sultan_end_credits/frames/opening/frame_00060.png",
     dict(has_text=True, text_color="bright", background="footage", is_credit=True),
     "anjelik giris-yazisi / oynayan deniz"),
    (f"{BASE}/1968_anjelik_ve_sultan_end_credits/frames/opening/frame_00750.png",
     dict(has_text=False, text_color="none", background="footage", is_credit=False),
     "anjelik SAF FILM (adam yuzu)"),
    (f"{BASE}/2014_yabandan_gelen_adam_end_credits/frames/closing/frame_01300.png",
     dict(has_text=True, text_color="bright", background="footage", is_credit=True),
     "yabandan jenerik footage ustunde"),
    (f"{BASE}/2014_yabandan_gelen_adam_end_credits/frames/closing/frame_00800.png",
     dict(has_text=False, text_color="none", background="footage", is_credit=False),
     "yabandan SAF FILM (bagiran adam)"),
    (f"{BASE}/2003_franny_nİn_ayaklari_end_credits/frames/closing/frame_00400.png",
     dict(has_text=False, text_color="none", background="footage", is_credit=False),
     "franny SAF FILM (cizgi kus/gokyuzu)"),
    (f"{BASE}/2003_franny_nİn_ayaklari_end_credits/frames/closing/frame_01400.png",
     dict(has_text=False, text_color="none", background="footage", is_credit=False),
     "franny SAF FILM (yasli adam+kiz)"),
    (f"{BASE}/2000_x_men_end_credits/frames/closing/frame_01500.png",
     dict(has_text=True, text_color="bright", background="solid", is_credit=True),
     "x-men siyah-bg scroll jenerik"),
    (f"{BASE}/1980_son_metro_end_credits/frames/opening/frame_00200.png",
     dict(has_text=True, text_color="bright", background="solid", is_credit=True),
     "son_metro statik kirmizi kart"),
]


def ask(model, img_path):
    b = Path(img_path).read_bytes()
    payload = {
        "model": model,
        "prompt": PROMPT,
        "images": [base64.b64encode(b).decode()],
        "stream": False,
        "format": "json",
        "options": {"temperature": 0},
    }
    req = urllib.request.Request(OLLAMA, data=json.dumps(payload).encode(),
                                headers={"Content-Type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=600) as r:
        resp = json.loads(r.read())
    return resp.get("response", ""), time.time() - t0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="qwen2.5vl:7b")
    args = ap.parse_args()
    print(f"MODEL = {args.model}\n" + "=" * 100)
    fields = ["is_credit", "has_text", "text_color", "background"]
    hits = {f: 0 for f in fields}
    n = 0
    rows = []
    for path, gt, desc in TESTS:
        if not Path(path).exists():
            print(f"[YOK] {path}")
            continue
        n += 1
        try:
            raw, dt = ask(args.model, path)
            pred = json.loads(raw)
        except Exception as e:
            print(f"[HATA] {desc}: {e}")
            rows.append((desc, gt, {"error": str(e)[:40]}, {}))
            continue
        m = {}
        for f in fields:
            ok = str(pred.get(f)).lower() == str(gt[f]).lower()
            m[f] = ok
            if ok:
                hits[f] += 1
        rows.append((desc, gt, pred, m))
        gate = "✓" if m.get("is_credit") else "✗"
        print(f"[{gate} bekci] {desc}  ({dt:.1f}s)")
        print(f"    GT  : {gt}")
        print(f"    PRED: {{'has_text': {pred.get('has_text')}, 'text_color': {pred.get('text_color')!r}, "
              f"'background': {pred.get('background')!r}, 'is_credit': {pred.get('is_credit')}}}")
        print(f"    eşleşme: " + "  ".join(f"{f}={'✓' if m[f] else '✗'}" for f in fields))
    print("=" * 100)
    print(f"n={n} kare")
    for f in fields:
        print(f"  {f:11}: {hits[f]}/{n}  ({100*hits[f]//max(1,n)}%)")
    print(f"\nBEKÇİ (is_credit) doğruluk = {hits['is_credit']}/{n}  ← jenerik↔film ayrımı")


if __name__ == "__main__":
    main()
