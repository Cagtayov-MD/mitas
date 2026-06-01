"""POC β — Bant-Bazlı Motion Füzyon Test Koşucusu.

Kullanım:
    python run_band_motion_test.py
    python run_band_motion_test.py --no-ocr  # sadece bant analizi

Çıktı: outputs/_poc_band_motion_20260530/<film>__<seg>/
"""

from __future__ import annotations

import json
import sys
import os
from datetime import datetime
from pathlib import Path
from time import perf_counter

# Windows console encoding duzeltme
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(PROJECT_ROOT))

FRAMES_BASE = PROJECT_ROOT / "outputs" / "_hakim_shadow_20films_20260529_1507" / "items"

# Sadece Son Metro closing çalıştır
DEFAULT_CASE = "1980_son_metro_end_credits__closing"
OUTPUT_TAG = "_poc_band_motion_20260530"


def _find_frames_dir(film_seg: str) -> Path | None:
    film, seg = film_seg.split("__", 1)
    c1 = FRAMES_BASE / f"{film}_end_credits" / "frames" / seg
    if c1.exists():
        return c1
    c2 = FRAMES_BASE / film / "frames" / seg
    if c2.exists():
        return c2
    # Doğrudan frames/ altına bak
    c3 = FRAMES_BASE / f"{film}_end_credits" / "frames"
    if c3.exists():
        return c3
    return None


def _load_frames(frames_dir: Path, max_frames: int | None = None) -> list[Path]:
    frames = sorted(frames_dir.glob("frame_*.png"), key=lambda p: int(p.stem.split("_")[-1]))
    if max_frames is not None:
        frames = frames[:max_frames]
    return frames


def _dummy_engine():
    class _Dummy:
        def recognize(self, image_path, *, strategy, timestamp_seconds=None):
            return []
    return _Dummy()


def _check_success(lines: list[dict]) -> dict:
    """Başarı ölçütü: hem kadro adı hem şarkı adı var mı?"""
    texts = [ln.get("text", "").upper() for ln in lines]
    full = " | ".join(texts)

    kadro_hits = [t for t in ["DENEUVE", "DEPARDIEU", "FERREOL", "FERRЁOL", "FERRÉOL"] if t in full or any(t in tt for tt in texts)]
    sarki_hits = [t for t in ["CHANSONS", "BEI MIR", "PRIERE", "CANTIQUE", "MON AMANT"] if t in full or any(t in tt for tt in texts)]

    return {
        "kadro_found": kadro_hits,
        "sarki_found": sarki_hits,
        "success": len(kadro_hits) > 0 and len(sarki_hits) > 0,
    }


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-ocr", action="store_true")
    parser.add_argument("--max-frames", type=int, default=None)
    parser.add_argument("--K", type=int, default=8)
    parser.add_argument("--static-eps", type=float, default=1.5)
    args = parser.parse_args()

    output_base = PROJECT_ROOT / "outputs" / OUTPUT_TAG
    output_base.mkdir(parents=True, exist_ok=True)
    print(f"[BandMotion] Cikti: {output_base}")

    # Paddle engine
    if args.no_ocr:
        print("[BandMotion] --no-ocr modu")
        paddle_engine = _dummy_engine()
    else:
        print("[BandMotion] PaddleOCR baslatiliyor...")
        t_init = perf_counter()
        try:
            from core.pipelines.ocr.credit_experiment import PaddleOcrEngine
            paddle_engine = PaddleOcrEngine()
            print(f"[BandMotion] PaddleOCR hazir ({(perf_counter()-t_init):.1f}s). Device: {paddle_engine.device}")
        except Exception as e:
            print(f"[HATA] PaddleOCR: {e}", file=sys.stderr)
            sys.exit(1)

    from core.pipelines.ocr.poc_band_motion.band_motion import run_band_motion

    case = DEFAULT_CASE
    print(f"\n{'='*60}")
    print(f"[BandMotion] Case: {case}")

    frames_dir = _find_frames_dir(case)
    if frames_dir is None:
        print(f"[HATA] Frame dizini bulunamadi: {case}", file=sys.stderr)
        sys.exit(1)

    frames = _load_frames(frames_dir, args.max_frames)
    print(f"[BandMotion] {len(frames)} frame yuklendi: {frames_dir}")

    case_out = output_base / case
    case_out.mkdir(parents=True, exist_ok=True)

    t_run = perf_counter()
    result = run_band_motion(
        frames,
        output_dir=case_out,
        paddle_engine=paddle_engine,
        K=args.K,
        static_eps=args.static_eps,
    )
    elapsed = perf_counter() - t_run

    # Başarı kontrolü
    success_check = _check_success(result.all_lines)

    # Bant özeti
    band_summary = [
        f"Band {b['band_idx']} y={b['y0']}-{b['y1']}: {b['label']} |dy|_med={b.get('dy_median_abs',0):.2f}"
        for b in result.band_infos
    ]

    # Satır örneği
    sample_lines = [ln.get("text", "") for ln in result.all_lines[:20]]

    # RESULT.md yaz
    result_md = f"""# POC β Sonuç — Bant-Bazlı Motion Füzyon

**Tarih:** 2026-05-30
**Film/Segment:** {case}
**Toplam frame:** {len(frames)}
**K (bant sayısı):** {args.K}
**static_eps:** {args.static_eps}
**Toplam süre:** {elapsed:.1f}s

## Bant Sınıflandırması

```
{chr(10).join(band_summary)}
```

## Başarı Ölçütü

- **Kadro adı bulundu:** {success_check['kadro_found']}
- **Şarkı adı bulundu:** {success_check['sarki_found']}
- **BAŞARI (ikisi birden):** {'EVET ✓' if success_check['success'] else 'HAYIR ✗'}

## Üretilen Satır Sayısı

- Bu POC: **{len(result.all_lines)} satır**
- A (boxtracking) referans: 16 satır (sadece kadro)
- B (slitscan) referans: 50 satır (sadece şarkı)

## İlk 20 Satır (Örnek)

```
{chr(10).join(f'{i+1}. {t}' for i, t in enumerate(sample_lines))}
```

## Tüm Satırlar (kaynak etiketli)

```json
{json.dumps([{'text': ln.get('text'), 'source': ln.get('source')} for ln in result.all_lines], ensure_ascii=False, indent=2)}
```

## Dürüst Değerlendirme

{"POC hedefine ulaştı: hem statik kadro hem akan şarkı aynı çıktıda toplandı." if success_check['success'] else "POC henüz tam başarıya ulaşamadı. Eksikler aşağıda açıklandı."}

### Yöntemin Güçlü Yönleri
- Bant bazında ayrı slit-scan + statik kırpıntı mantığı uygulandı.
- Tek Paddle GPU oturumu kullanıldı (Ollama yok).

### Pürüzler / İyileştirme Noktaları
- 60px bantlarda faz-korelasyon gürültülü; daha büyük stride veya temporal smoothing gerekebilir.
- 'unknown' bantlar statik fallback ile işleniyor; bu bazı scroll bantları kaçırabilir.
- Bant sınıfı zaman içinde değişebilir (bazı bantlar önce static sonra scroll); bunu yakalamak için zamana göre segmentasyon gerekir.

## Dosyalar

- `bands_debug.json`: Her bant dy serisi ve sınıf kararı
- `static_band*.png`: Statik bant kırpıntıları
- `scroll_band*_panorama.png`: Scroll bant panoramaları
- `lines.json`: Birleşik OCR çıktısı
"""

    result_path = case_out / "RESULT.md"
    result_path.write_text(result_md, encoding="utf-8")

    print(f"\n{'='*60}")
    print(f"[BandMotion] TAMAM -- {elapsed:.1f}s | satir: {len(result.all_lines)}")
    print(f"[BandMotion] Basari: {success_check}")
    print(f"[BandMotion] RESULT.md: {result_path}")
    print(f"[BandMotion] lines.json: {result.lines_path}")
    print(f"[BandMotion] bands_debug.json: {result.bands_debug_path}")


if __name__ == "__main__":
    main()
