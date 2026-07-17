import os
import sys

sys.path.insert(0, "/opt/atlas/src")
os.environ.setdefault("ATLAS_OCR_ENGINE", "paddle")

import numpy as np
from PIL import Image, ImageDraw, ImageFont
import cv2

img = Image.new("RGB", (700, 130), "white")
d = ImageDraw.Draw(img)
try:
    f = ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf", 44)
except Exception:
    f = ImageFont.load_default()
d.text((20, 40), "YONETMEN AHMET YILMAZ", fill="black", font=f)
img_bgr = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)

from atlas.ocr.kj_ocr import KjOCR

eng = KjOCR()
results = eng.read(img_bgr)
print("BACKEND:", eng._backend)
print("SONUCLAR:", [(r.text, round(r.conf, 3)) for r in results])
assert eng._backend == "paddle", "Linux'ta paddle fallback beklenir"
assert any("AHMET" in r.text.upper() or "YILMAZ" in r.text.upper() for r in results), "metin okunamadi"
print("KAPI_F_SMOKE_OK")
