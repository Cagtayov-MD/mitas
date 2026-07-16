#!/bin/bash
# OneOCR-ikame smoke: (1) GERÇEK kod yolu — patch'li build_engine() → Paddle-adapter
#                     (2) GLM-oku yolu — ollama glm-ocr görüntü okuma
set -uo pipefail
LOG=/opt/mitas/kurulum/logs/12_ocr_smoke.log
exec > >(tee "$LOG") 2>&1
V=/opt/mitas/venvs/ocr/bin

echo "=== [0] sentetik görüntü ==="
"$V/python" -c "from PIL import Image,ImageDraw,ImageFont; i=Image.new('RGB',(700,130),'white'); d=ImageDraw.Draw(i); f=ImageFont.truetype('/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf',44); d.text((20,40),'YONETMEN AHMET YILMAZ',fill='black',font=f); i.save('/tmp/ptest.png'); print('OK')"

echo "=== [1] build_engine() → Paddle (GERÇEK kod yolu) ==="
cd /opt/mitas
set -a; source /opt/mitas/mitas.env; set +a
"$V/python" - <<'PYEOF'
import sys
sys.path.insert(0, "/opt/mitas")
sys.path.insert(0, "/opt/mitas/scripts")
from PIL import Image
import _pipe_ocr
eng, ad, hata = _pipe_ocr.build_engine()
print("motor:", ad, "| hata:", hata)
assert eng is not None, f"motor kurulamadi: {hata}"
out = eng.recognize_pil(Image.open("/tmp/ptest.png"))
print("PADDLE OKUDU:", repr(out.get("text","")[:120]))
assert "AHMET" in out.get("text","").upper(), "beklenen metin yok!"
print("PADDLE-YOL-OK")
PYEOF

echo "=== [2] GLM-oku yolu (ollama glm-ocr) ==="
export OLLAMA_HOST=127.0.0.1:11434
"$V/python" - <<'PYEOF'
import base64, json, urllib.request, time
b64 = base64.b64encode(open("/tmp/ptest.png","rb").read()).decode()
payload = {"model":"glm-ocr:latest","prompt":"Bu goruntudeki metni oldugu gibi oku.","images":[b64],"stream":False,"think":False,"options":{"temperature":0,"num_predict":80}}
req = urllib.request.Request("http://127.0.0.1:11434/api/generate", data=json.dumps(payload).encode(), headers={"Content-Type":"application/json"})
t=time.time()
resp = json.load(urllib.request.urlopen(req, timeout=300))
metin = (resp.get("response") or "").strip()
print("GLM-OCR OKUDU:", repr(metin[:160]), "| sure: %.1fs" % (time.time()-t))
assert "AHMET" in metin.upper(), "beklenen metin yok!"
print("GLM-YOL-OK")
PYEOF
echo "OCR-SMOKE-TAMAM"
