"""deepseek-ocr:3b okuyucu testi — AYNI ALİTA havuzu. OCR-uzmanı (piksel->ham metin).
Karşılaştırma: yazım kalitesi (gemma bs=1'de Christoph Waltz ✓ ama Eva/Macherella bozuktu).
"""
import sys, os, json, glob, base64, urllib.request, time

POOL_DIR = r"E:\MITAS\Database\ALİTA SAVAŞ MELEĞİ 2025-1241-1-0000-90-1\vl_pool"
MODEL = os.environ.get("DS_MODEL", "deepseek-ocr:3b")
PROMPT = "Read ALL text in this image exactly as written, line by line. Output only the text, nothing else."


def b64(p):
    return base64.b64encode(open(p, "rb").read()).decode()


def call(frame):
    body = {"model": MODEL,
            "messages": [{"role": "user", "content": PROMPT, "images": [b64(frame)]}],
            "stream": False, "options": {"temperature": 0, "num_predict": 2048}}
    req = urllib.request.Request("http://localhost:11434/api/chat", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    r = json.loads(urllib.request.urlopen(req, timeout=300).read())
    return r.get("message", {}).get("content", "")


if __name__ == "__main__":
    frames = sorted(glob.glob(os.path.join(POOL_DIR, "*.png")))
    print(f"MODEL={MODEL}  HAVUZ={len(frames)} gorsel\n", flush=True)
    t0 = time.time()
    allnames = set()
    for i, f in enumerate(frames):
        try:
            txt = call(f)
        except Exception as e:
            print(f"[{i:02d}] {os.path.basename(f)} HATA: {repr(e)[:90]}", flush=True)
            continue
        kind = "scroll" if "scroll" in os.path.basename(f) else "card"
        lines = [ln.strip() for ln in txt.splitlines() if ln.strip()]
        print(f"[{i:02d}] {os.path.basename(f)} ({kind}) {len(lines)} satir:", flush=True)
        for ln in lines[:25]:
            print(f"      {ln}", flush=True)
            # 2+ kelimeli, harf-agirlikli satirlari aday-isim say
            w = ln.split()
            if 2 <= len(w) <= 5 and sum(c.isalpha() for c in ln) >= len(ln) * 0.6:
                allnames.add(ln)
        print(flush=True)
    print(f"=== {MODEL}: {len(frames)} gorsel, {round(time.time()-t0,1)}s, ~{len(allnames)} aday-isim satiri ===")
    json.dump(sorted(allnames), open(r"E:\MITAS\outputs\deepseek_ocr_result.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
