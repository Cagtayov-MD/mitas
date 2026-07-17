"""Çoklu OCR/VL model taraması — AYNI ALİTA havuzunun ANLAMLI tiles'ında.
Soru: deepseek gibi sürpriz okuyan başka küçük model var mı? Footage'da uyduruyor mu?
"""
import sys, os, json, base64, urllib.request, time

POOL_DIR = r"E:\MITAS\Database\ALİTA SAVAŞ MELEĞİ 2025-1241-1-0000-90-1\vl_pool"
# anlamlı alt-küme: kadro + crew + tablo-crew + müzik + 2 footage (uydurma kontrolü)
TILES = ["scroll_0014.png", "scroll_0015.png", "scroll_0013.png", "scroll_0020.png",
         "card_0000.png", "card_0004.png"]
MODELS = os.environ.get("SWEEP_MODELS",
                        "glm-ocr:latest,minicpm-v:latest,llama3.2-vision:11b,gemma4:12b,moondream:latest").split(",")
PROMPT = "Read ALL text in this image exactly as written, line by line. Output only the text, nothing else."


def b64(p):
    return base64.b64encode(open(p, "rb").read()).decode()


def call(model, frame):
    body = {"model": model,
            "messages": [{"role": "user", "content": PROMPT, "images": [b64(frame)]}],
            "stream": False, "options": {"temperature": 0, "num_predict": 2048}}
    req = urllib.request.Request("http://localhost:11434/api/chat", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    r = json.loads(urllib.request.urlopen(req, timeout=300).read())
    return r.get("message", {}).get("content", "")


def is_halluc(txt):
    low = txt.lower()
    return any(s in low for s in ("you are a", "helpful assistant", "<|im", "i'm sorry", "as an ai"))


if __name__ == "__main__":
    for model in MODELS:
        model = model.strip()
        if not model:
            continue
        print(f"\n{'='*70}\nMODEL: {model}\n{'='*70}", flush=True)
        t0, hcount = time.time(), 0
        for tf in TILES:
            fp = os.path.join(POOL_DIR, tf)
            if not os.path.isfile(fp):
                continue
            try:
                txt = call(model, fp)
            except Exception as e:
                print(f"  [{tf}] HATA: {repr(e)[:90]}", flush=True)
                continue
            h = is_halluc(txt)
            hcount += 1 if h else 0
            lines = [ln.strip() for ln in txt.splitlines() if ln.strip()]
            tag = " <<< UYDURMA/CHATBOT" if h else ""
            print(f"  [{tf}] {len(lines)} satir{tag}:", flush=True)
            for ln in lines[:14]:
                print(f"      {ln[:120]}", flush=True)
        print(f"  --> {model}: {round(time.time()-t0,1)}s, {hcount}/{len(TILES)} tile uydurma", flush=True)
