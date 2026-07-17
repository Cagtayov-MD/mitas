# 08 · OneOCR İkamesi + Golden Kapısı

> Göçün tek "mimari" parçası. OneOCR Windows-only ve şu an **ham-OCR otoritesi** (künyenin
> LLM'e giden asıl kaynağı). İki yol var: geçici **köprü** (Faz 0) ve kalıcı **ikame** (Faz 1).
> Kalıcı ikame K1-GATE'ten geçmeden OneOCR kapatılmaz.

---

## OneOCR'ın rolü ve neden dikkatli

**Çağrı noktaları** ([02·E1](02_ENVANTER.md)):

| Yer | Rol |
|---|---|
| `scripts/_pipe_ocr.py:349-351` | **ham-OCR — künyenin ANA kaynağı** (`load_llm_lines_for_ocr` zinciri) |
| `core/pipelines/ocr/jenerik_oneocr_detector.py:50-52` | jenerik onset detektörü (Plan B) |
| `core/pipelines/ocr/credit_experiment.py:511-519,742` | credit deney motoru |
| `core/pipelines/ocr/simple.py:195-200` | basit OCR yolu |

**Neden native OneOCR seçilmişti:** çok-script (Latin / Fransızca-küçük-harf / Arapça / Kiril)
tek motorda temiz okuma. İkame bu kapsamı düşürürse yabancı-dil künyelerde cast/isim kaybı olur
→ "OCR-otorite kanunu" ihlali. Bu yüzden K1-GATE ölçüm işi, "kurdum çalışıyor" değil.

---

## Yol A — OneOCR Köprüsü (Faz 0, geçici)

**Amaç:** Pipeline'ın geri kalanını Linux'ta koştururken OneOCR'ı olduğu gibi bırak. Windows
host'ta küçük bir HTTP servisi OneOCR'ı sunar; Linux çağırır. Böylece Faz 0'da OCR değişkeni
sabit tutulur — yalnız OS değişir, çıktı birebir aynı kalır (temiz golden karşılaştırması).

**Windows host tarafı** (`oneocr_bridge.py`, Windows'ta venv/asr ile koşar):

```python
# oneocr_bridge.py — Windows host'ta: OneOCR'ı HTTP üstünden sunar (127.0.0.1:8790)
import io, oneocr, numpy as np
from fastapi import FastAPI, Request
from PIL import Image
app = FastAPI()
_eng = oneocr.OcrEngine()

@app.post("/ocr")
async def ocr(req: Request):
    raw = await req.body()
    img = np.array(Image.open(io.BytesIO(raw)).convert("RGB"))[:, :, ::-1]  # RGB->BGR
    res = _eng.recognize(img)          # OneOCR'ın mevcut API'siyle aynı çağrı
    return {"lines": [{"box": b, "text": t} for (b, t) in _oneocr_line_boxes(res)]}
# _oneocr_line_boxes: jenerik_oneocr_detector.py:55 ile AYNI kutu/metin çıkarımı
```

**Linux/pipeline tarafı** — çağrı noktalarına köprü-istemcisi tak (flag arkası):

```python
# core/pipelines/ocr/oneocr_client.py — köprü VEYA yerel oneocr seçer
import os, sys, io, requests, numpy as np
from PIL import Image
_BRIDGE = os.environ.get("MITAS_ONEOCR_BRIDGE")  # ör. http://<win-host>:8790

def oneocr_lines(image_bgr):
    if _BRIDGE:
        buf = io.BytesIO(); Image.fromarray(image_bgr[:, :, ::-1]).save(buf, "PNG")
        r = requests.post(_BRIDGE + "/ocr", data=buf.getvalue(), timeout=30)
        return [(tuple(d["box"]), d["text"]) for d in r.json()["lines"]]
    import oneocr                                    # Windows yerel yol (değişmeden)
    return _oneocr_line_boxes(oneocr.OcrEngine(), image_bgr)
```

`_pipe_ocr.py:349`, `jenerik_oneocr_detector.py:55`, `simple.py:195` bu istemciyi çağırır
(doğrudan `import oneocr` yerine). `MITAS_ONEOCR_BRIDGE` set ise köprü, değilse yerel.

**Faz 0 kapısı (köprü ile):** golden çıktı Windows-üretimiyle **byte-eşleşme** (OCR sabit,
yalnız OS değişti). Fark çıkarsa OS/env kaynaklı bir regresyon var demektir → köprü OCR'ı sabit
tuttuğu için farkı izole etmek kolay.

---

## Yol B — Kalıcı İkame (Faz 1)

**Amaç:** OneOCR'ı tamamen kaldır. GLM-OCR (öncelik) veya PaddleOCR ham-OCR otoritesi olur.

**Aday sırası:**
1. **GLM-OCR** — VLM-credit-OCR bench'ini kazanmıştı (hızlı/temiz). İlk aday.
2. **PaddleOCR** — zaten kurulu, deterministik, çok-script destekli. Yedek/ikinci-okuyucu.

## Çağatay ayrımı (2026-07-12, koddan doğrulandı) — ROL BAZLI İKAME

OneOCR iki AYRI rolde kullanılıyor; ikamesi de role göre BÖLÜNMELİ (tek motor değil):

| OneOCR rolü | Kod yeri | İkame | Neden |
|---|---|---|---|
| **ham-OCR OKUMA** (künye metni) | `_pipe_ocr.py:346` `build_engine()` (fallback) + pipeline100 primary | **GLM-OCR** (öncelik) | GLM-OCR `glm-ocr:latest` zaten opsiyonel 2. motor (`_pipe_ocr.py:66,817`); promote et |
| **jenerik OCR-refine / frame "jenerik mi"** | `_jenerik_detect.py:32` build_engine (OCR-refine) · `jenerik_frame_pool_detector.py` (Paddle) vs `jenerik_oneocr_detector.py` (Plan B) | **PaddleOCR** (hızlı) | frame-pool ZATEN Paddle; ana dedektör görsel/yapısal (OCR'sız); refine'ı OneOCR→Paddle çevir |

**Uygulama:** `build_engine()`'i tek OneOCR yerine **çağrı-bağlamına göre böl**: OCR-okuma yolunda GLM, jenerik-refine yolunda Paddle döndür (`MITAS_OCR_ENGINE` + ayrı `MITAS_JENERIK_OCR_ENGINE`). Golden'da ikisini de ayrı ölç (K1-GATE).

**Entegrasyon:** `oneocr_client.oneocr_lines()` içine üçüncü dal ekle (`MITAS_OCR_ENGINE=glm|paddle|oneocr`):

```python
_ENGINE = os.environ.get("MITAS_OCR_ENGINE", "oneocr")  # geçişte: oneocr -> glm
def raw_ocr_lines(image_bgr):
    if _ENGINE == "glm":    return _glm_ocr_lines(image_bgr)
    if _ENGINE == "paddle": return _paddle_ocr_lines(image_bgr)
    return oneocr_lines(image_bgr)   # köprü veya yerel
```
> Not: `_pipe_ocr.py` ham-OCR yolu artık `raw_ocr_lines` çağırır. Aynı `(box, text)` sözleşmesi
> korunur → aşağı akış (garble-kapısı, kimlik, LLM) değişmeden çalışır.

---

## K1-GATE — Golden Kapısı (BAĞLAYICI)

OneOCR kapatılmadan önce ikame şunları geçmeli. Ölçüm **örnek-bazlı**, tek film "tamam" demez
("çok-örnekli ölçüm" kuralı).

**Protokol:**
1. Golden setin (bkz. [09](09_DOGRULAMA_GERI_DONUS.md)) her filminde üç koşu: `oneocr` (köprü),
   `glm`, `paddle`.
2. Her koşunun **ham-OCR satırlarını** ve **nihai künye kararını** (cast listesi, isimler,
   yönetmen, ONAYLI/KONTROL) karşılaştır.
3. **Çok-script alt-küme** ayrı ölç: Fransızca-küçük-harf, Arapça, Kiril içeren filmler — ikame
   bunlarda kayıp veriyor mu?

**Geçme ölçütü:**
- [ ] İkame, golden künye kararında OneOCR ile **eşdeğer veya daha iyi** (net cast/isim kaybı yok).
- [ ] Çok-script kapsama düşmedi (alt-küme recall ≥ OneOCR).
- [ ] "OCR-otorite kanunu" korundu: ikame ne okursa o; gelen veri ezmiyor; okunamadı > yanlış-oku.
- [ ] Regresyon-golden ([09](09_DOGRULAMA_GERI_DONUS.md)) yeşil.

**Geçemezse:** OneOCR köprüsüyle devam (Yol A kalıcılaşır) → Branch A: "Linux ana + Windows
OneOCR servisi". Bu durumda Windows host emekli EDİLMEZ, küçük bir OneOCR servisi olarak kalır.
Karar tamamen bu ölçüme bağlı — şimdiden "OneOCR gidecek" varsayma, ÖLÇ.

---

## Öz-denetim

- Köprü (Faz 0, OCR sabit) ve ikame (Faz 1, OCR değişir) net ayrıldı — golden farkını izole eder.
- `(box, text)` sözleşmesi korunuyor → aşağı akış değişmez (davranış-nötr).
- K1-GATE örnek-bazlı + çok-script + OCR-otorite kuralıyla hizalı.
- Geçememe durumu Branch A'ya düşüş olarak tanımlı ([01·K1](01_KARARLAR_VE_KISITLAR.md) ile tutarlı).
