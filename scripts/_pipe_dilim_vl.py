# -*- coding: utf-8 -*-
"""_pipe_dilim_vl.py — K2: dilimlenmiş reading-master parçalarını VL modele TRANSKRİBE ettir (GÖLGE).

MİMARİ HÜKMÜ (tarafsız Fable5+Opus4.8 paneli, 2026-07-03 — "B-temelli C"):
  * VL, master-parçalarını OKUYABİLİR ama OTORİTE DEĞİLDİR: piksel master'ındır, hüküm
    OneOCR-teyidinindir, VL yalnız TEYİTLİ aday üretir.
  * Prompt YAPILANDIRILMIŞ SORU DEĞİL ("yönetmen kim?" = doldurma baskısı → halüsinasyon);
    SATIR-SATIR TRANSKRİPSİYON istenir, rol-eşleme sonraki adımın işidir.
  * Çıktı GÖLGEDİR: karara bağlanmaz; ileride VL-transkript satırları da (OneOCR-dilim gibi)
    hayalet-kalkanı korpusuna ADAY-ÜRETİCİ değil DOĞRULAYICI katkı olarak değerlendirilebilir —
    o adım ayrı karar ister (VL-satırı piksel-teyit sayılır mı tartışması AÇIK, şimdilik HAYIR).
  * Pilot hedef kitle: OneOCR-dilim korpusu BOŞ/yetersiz kalan filmler (stilize font/düşük
    kontrast — OneOCR'ın kör sınıfı). Model: MITAS_DILIM_VL_MODEL (default qwen3vl:8b —
    E:\\QwenModels'da yerel gguf adayı mevcut; 35b-sınıfı gelirse env ile yükseltilir).

Kullanım (ollama'da VL modeli varken):
  python scripts/_pipe_dilim_vl.py --clip "E:\\MITAS\\Database\\<film>"      (gölge json üretir)
  python scripts/_pipe_dilim_vl.py --clip ... --model qwen2.5vl:7b
Çıktı: <film>/master_dilim/dilim_vl.json  {model, parts:[{part, transcript:[satırlar]}], ts}
FAIL-SAFE: model yok/ollama kapalı → tek satır JSON hata, dosya YAZILMAZ, exit 2 (dürüst).
Pipeline'a BAĞLI DEĞİL (karanlık-lansman); bağlanması ayrı talimat ister.
"""
from __future__ import annotations
import argparse
import base64
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

DILIM_DIRNAME = "master_dilim"
OUT_JSON = "dilim_vl.json"

_PROMPT = (
    "Bu görüntü bir film jeneriğinin bir bölümüdür. GÖREVİN: görüntüdeki TÜM yazıları "
    "satır satır, YUKARIDAN AŞAĞIYA transkribe etmek.\n"
    "KESİN KURALLAR:\n"
    "1. SADECE görüntüde AÇIKÇA OKUNAN metni yaz — tahmin ETME, tamamlamaya ÇALIŞMA, "
    "bilginden isim EKLEME.\n"
    "2. Bir satır bulanık/okunamıyorsa o satır için tam olarak: [okunamadı]\n"
    "3. Yorum, açıklama, rol-tahmini YOK — yalnız gördüğün metin.\n"
    "4. Her satırı yeni satıra yaz. Görüntüde hiç yazı yoksa tam olarak: [yazı yok]"
)


def _ollama_generate(base, model, prompt, image_b64, timeout=180):
    import urllib.request
    req = urllib.request.Request(
        base.rstrip("/") + "/api/generate",
        data=json.dumps({"model": model, "prompt": prompt, "images": [image_b64],
                         "stream": False, "think": False,
                         "options": {"temperature": 0}}).encode("utf-8"),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return (json.loads(r.read()).get("response") or "").strip()


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--clip", required=True)
    ap.add_argument("--model", default=os.environ.get("MITAS_DILIM_VL_MODEL", "qwen3vl:8b"))
    ap.add_argument("--timeout", type=int, default=int(os.environ.get("MITAS_DILIM_VL_TIMEOUT", "180") or 180))
    a = ap.parse_args()
    base = os.environ.get("MITAS_OLLAMA", "http://127.0.0.1:11434")
    md = Path(a.clip) / DILIM_DIRNAME
    parts = sorted(md.glob("*_p[0-9][0-9].png")) if md.is_dir() else []
    if not parts:
        print(json.dumps({"status": "dilim-yok"}, ensure_ascii=False))
        return 1
    out = {"model": a.model, "prompt_style": "transcribe-v1", "parts": [],
           "ts": datetime.now(timezone.utc).isoformat()}
    t0 = time.perf_counter()
    for p in parts:
        try:
            b64 = base64.b64encode(p.read_bytes()).decode("ascii")
            resp = _ollama_generate(base, a.model, _PROMPT, b64, timeout=a.timeout)
            lines = [l.strip() for l in resp.splitlines() if l.strip()]
            out["parts"].append({"part": p.name, "transcript": lines})
        except Exception as exc:  # noqa: BLE001
            # ilk parçada model-yok/sunucu-kapalı → dürüst çık, dosya yazma
            if not out["parts"]:
                print(json.dumps({"status": "vl_error", "error": f"{type(exc).__name__}: {exc}"[:200]},
                                 ensure_ascii=False))
                return 2
            out["parts"].append({"part": p.name, "error": f"{type(exc).__name__}: {exc}"[:200]})
    out["secs"] = round(time.perf_counter() - t0, 1)
    (md / OUT_JSON).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({"status": "ok", "parts": len(out["parts"]), "secs": out["secs"]},
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
