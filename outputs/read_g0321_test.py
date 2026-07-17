"""g_0321.png (yönetmen karesi: 'A NIKI CARO FILM') — OneOCR vs glm-ocr doğrudan okuma testi.
Soru: kare elimizde, neden 'NIKI CARO'yu okuyamadık? + crop/büyütme yardım eder mi?
"""
import sys, os, json, base64, urllib.request
sys.path.insert(0, r"E:\MITAS\scripts")
sys.path.insert(0, r"E:\MITAS")
import cv2

IMG = r"E:\MITAS\Database\3\frames\giris\g_0321.png"


def glm_read(path, model="glm-ocr:latest"):
    b64 = base64.b64encode(open(path, "rb").read()).decode()
    body = {"model": model,
            "messages": [{"role": "user",
                          "content": "Read ALL text in this image exactly as written. Output only the text.",
                          "images": [b64]}],
            "stream": False, "options": {"temperature": 0, "num_predict": 1024}}
    req = urllib.request.Request("http://localhost:11434/api/chat", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    r = json.loads(urllib.request.urlopen(req, timeout=180).read())
    return r.get("message", {}).get("content", "")


def oneocr_read(bgr):
    try:
        from PIL import Image
        from _pipe_ocr import build_engine
        eng, kind, err = build_engine()
        if eng is None:
            return f"(OneOCR motoru yok: {err})"
        res = eng.recognize_pil(Image.fromarray(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)))
        lines = []
        for ln in (res.get("lines") or []):
            t = (ln.get("text") if isinstance(ln, dict) else str(ln)).strip()
            if t:
                lines.append(t)
        if not lines:
            lines = [x.strip() for x in (res.get("text") or "").splitlines() if x.strip()]
        return "\n".join(lines) if lines else "(BOŞ)"
    except Exception as e:
        return f"(OneOCR hata: {type(e).__name__}: {e})"


if __name__ == "__main__":
    img = cv2.imdecode(__import__("numpy").fromfile(IMG, dtype="uint8"), cv2.IMREAD_COLOR)
    h, w = img.shape[:2]
    print(f"görsel: {w}x{h}\n")

    print("=== 1) OneOCR — TAM kare ===")
    print(oneocr_read(img))
    print("\n=== 2) glm-ocr — TAM kare ===")
    print(glm_read(IMG))

    # alt-sol çeyrek (yazının olduğu yer) crop + 2x büyüt
    crop = img[int(h * 0.62):, :int(w * 0.55)]
    crop2 = cv2.resize(crop, (crop.shape[1] * 2, crop.shape[0] * 2), interpolation=cv2.INTER_CUBIC)
    cpath = r"E:\MITAS\outputs\_g0321_crop2x.png"
    cv2.imencode(".png", crop2)[1].tofile(cpath)
    print(f"\n=== 3) OneOCR — alt-sol crop 2x ({crop2.shape[1]}x{crop2.shape[0]}) ===")
    print(oneocr_read(crop2))
    print("\n=== 4) glm-ocr — alt-sol crop 2x ===")
    print(glm_read(cpath))
