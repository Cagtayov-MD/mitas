# -*- coding: utf-8 -*-
"""Create the parallel end-credit frame pool for MITAS.

Input stays untouched:
  Database/<film>/frames/cikis

Output is always created:
  Database/<film>/frames/cikis_jenerik

The pool is intentionally separate from the normal OneOCR path.  OneOCR keeps
reading the original frame folders; GLM/VL/master debug jobs can read this
filtered pool.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import json
import os
import shutil
import sys
import time
from pathlib import Path


try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

# Linux geçişi 2026-07-16: env varsa onu kullan (Windows'ta env yoksa eski davranış birebir).
PROJECT_ROOT = Path(os.environ.get("MITAS_PROJECT_ROOT") or r"E:\MITAS")
sys.path.insert(0, str(PROJECT_ROOT))
os.environ.setdefault("JENERIK_PADDLE_FAST_NO_DOC", "1")

from core.pipelines.ocr.jenerik_frame_pool_detector import (  # noqa: E402
    DetectorConfig,
    detect_frame_dir,
    list_images,
)
import core.pipelines.ocr.jenerik_frame_pool_detector as _det  # noqa: E402  (footage-baş trim için paddle)


def _footage_trim_enabled() -> bool:
    # FOOTAGE-BAŞ TRIM (2026-07, KKF-Aşama1): detector start_pos'u gerçek krediden ÖNCE footage'a
    # anchor'layabiliyor (CV-metin-maskesi footage dokusuna takılıyor). Havuz baştan footage ile
    # dolunca reading-master/VL boşa okuyor. OCR ile (isim/keyword/iki-sütun) gerçek kredi bloğu
    # başlayana kadar baştaki footage kareleri kırp. ADDITIVE + FAIL-SAFE. Kapat: =0.
    return os.environ.get("MITAS_JENERIK_FOOTAGE_TRIM", "1").strip().lower() not in ("0", "false", "off", "no")


# NOT (_plain_credit, 2026-07 — DENENDİ, SÖKÜLDÜ): "koyu-zemin+parlak-yazı = kredi" parlaklık
# sinyali GT'de regresyon verdi (ort|hata| 64→114; DRAKULA ateşi / MARIE koyu kareleri kredi sandı).
# Ders: parlaklık footage'tan kredi ayırt edemiyor, semantik gerekiyor (VLM). Kod: git geçmişinde.


def _is_credit_frame(ocr, f: Path, cfg: DetectorConfig) -> bool | None:
    """Tek kare: gerçek kredi mi (isim-benzeri>=2 / anahtar-kelime / iki-sütun; altyazı-tabela-düzmetin DEĞİL).
    None = OCR hatası."""
    try:
        _, feat = _det.paddle_frame_score(ocr, f, cfg)
    except Exception:  # noqa: BLE001
        return None
    if not feat:
        return False
    is_credit = (int(feat.get("name_like_count", 0) or 0) >= 2
                 or int(feat.get("credit_keyword_count", 0) or 0) >= 1
                 or bool(feat.get("two_column_layout")))
    is_noise = bool(feat.get("subtitle_like") or feat.get("scene_sign_like") or feat.get("prose_like"))
    return bool(is_credit and not is_noise)


def _vlm_rescue_enabled() -> bool:
    # VLM-RESCUE (2026-07, KKF-Aşama1): CV detector NOT_FOUND (çok-dilli/Farsça kaçan CENNETİN) ya da
    # ŞÜPHELİ (çok-erken start_pos + dev havuz = footage-bloat/diegetik-erken-anchor SON_METRO) olduğunda
    # VLM sondan-tarama detector'ına (credit_start_vlm) sor. Ampirik: SON_METRO 12→766, CENNETİN nf→728.
    # Ortak-vaka CV+footage-trim'de kalır (hassas). Kapat: =0.
    return os.environ.get("MITAS_JENERIK_VLM_RESCUE", "1").strip().lower() not in ("0", "false", "off", "no")


def _trim_footage_head_v2(pool_frames: list[Path], cfg: DetectorConfig,
                          stride: int = 6, sustain: int = 2) -> int:
    """İLERİ footage-trim v2 (2026-07): CV anchor ÇOK ERKEN olabilir (footage-içi metne yapışır:
    ATTİLA CV=141 ama gerçek 539; MARIE CV=126 ama gerçek 585 → 400+ kare footage havuza girer).
    Eski v1'in max_scan=60'ı bunu göremezdi.

    v2: havuz başından STRIDE'lı, TAM-MENZİL ileri tara → ilk SÜRDÜRÜLEN kredi bölgesini bul
    (siyah kareler köprülenir, kredi sayılmaz) → sonra stride penceresinde kare-kare geri gelip
    ilk gerçek kredi karesini bul. Atılacak kare sayısını döndürür (0 = kırpma yok)."""
    if not _footage_trim_enabled():
        return 0
    ocr = _det._PADDLE_CACHE.get(cfg.ocr_lang)
    if ocr is None or not pool_frames:
        return 0
    n = len(pool_frames)
    hits = 0
    anchor = None
    for i in range(0, n, stride):
        f = pool_frames[i]
        if _blackish(f):
            continue                              # kart-arası siyah → köprüle (kredi de değil, footage da)
        c = _is_credit_frame(ocr, f, cfg)
        if c:
            hits += 1
            if hits >= sustain:
                anchor = i - stride * (sustain - 1)   # sürdürülen bloğun İLK örneği
                break
        else:
            hits = 0
    if anchor is None or anchor <= 0:
        return 0
    # İNCE: [anchor-stride, anchor+stride] kare-kare → ilk gerçek kredi karesi
    lo = max(0, anchor - stride)
    for j in range(lo, min(n, anchor + stride + 1)):
        if _blackish(pool_frames[j]):
            continue
        if _is_credit_frame(ocr, pool_frames[j], cfg):
            return j
    return max(0, anchor)


def _trim_footage_head(pool_frames: list[Path], cfg: DetectorConfig, max_scan: int = 60) -> int:
    """Baştaki footage karelerini OCR ile kırp; atılacak kare sayısını döndür (0 = kırpma yok).
    Baştan max_scan kareyi kare-kare tarar; gerçek kredi bloğu (ardışık 2 kredi karesi) başlayınca
    kredinin İLK karesine kırpar → YALAZA'da trim=1 (YÖNETMEN kartı KORUNUR). Küçük footage-baş
    (~%80 vaka) çözülür. FAIL-SAFE: paddle yok / ilk 60'ta net kredi yok → 0 (temiz havuz zaten
    ilk kareden kredi → 0; SON_METRO gibi diegetik-erken-anchor ekstremleri trim'le çözülmez → 0,
    ayrı ele alınır — KKF)."""
    if not _footage_trim_enabled():
        return 0
    ocr = _det._PADDLE_CACHE.get(cfg.ocr_lang)
    if ocr is None or not pool_frames:
        return 0
    hits = 0
    for i, f in enumerate(pool_frames[:max_scan]):
        c = _is_credit_frame(ocr, f, cfg)
        if c:
            hits += 1
            if hits >= 2:                    # ardışık 2 kredi karesi = gerçek kredi başladı
                return max(0, i - 1)         # ikilinin İLK karesinden başlat (baş krediyi kaybetme)
        elif c is False:
            hits = 0
    return 0


def _blackish(f: Path, mean_thr: float = 20.0, max_thr: float = 70.0) -> bool:
    """GERÇEKTEN boş siyah kare (kart-arası BOŞLUK) mu?

    KRİTİK: yalnız ORTALAMA parlaklığa bakmak YANLIŞ — siyah zeminde soluk beyaz yazılı kredi
    kareleri de düşük ortalamalıdır (BABAM: mean~3 ama yazı VAR). Ayrımı EN PARLAK piksel yapar:
    saf siyah → max ~0-30 ; yazılı siyah → max ~180-255. İkisi birlikte gerekir."""
    try:
        from PIL import Image
        import numpy as np
        g = np.asarray(Image.open(f).convert("L"))
        return float(g.mean()) < mean_thr and float(g.max()) < max_thr
    except Exception:  # noqa: BLE001
        return False


def _backward_extend_enabled() -> bool:
    return os.environ.get("MITAS_JENERIK_BACK_EXTEND", "1").strip().lower() not in ("0", "false", "off", "no")


def _backward_extend_credits(images: list[Path], start_pos: int, cfg: DetectorConfig,
                             max_back: int = 160, gap: int = 8) -> int:
    """GERİYE-GENİŞLETME (GPT 'earliest supported regime', 2026-07): CV anchor'ı GEÇ kalabiliyor —
    soluk/siyah-zeminli ilk kredi kartlarını kaçırıp ilk GÜÇLÜ kredide duruyor (BABAM: CV 449,
    gerçek 415 → 34 kare kredi KAYBI; DON_KİŞOT/ATTİLA/KULÜBE/CENNETİN de geç).

    Anchor'dan geriye yürü:
      - SİYAH kare (kart-arası boşluk)      → KÖPRÜLE (kredi rejimi sürüyor sayılır)
      - kredi karesi                        → en-erken adayı güncelle
      - footage (içerikli, kredi değil)     → gap kadar üst üste görülürse DUR
    Sonra BLANK-VETO: başlangıç siyah kareye denk geldiyse ileri kaydır (ilk gerçek kredi karesine).
    Kapat: MITAS_JENERIK_BACK_EXTEND=0"""
    if not _backward_extend_enabled() or start_pos is None or start_pos <= 0:
        return int(start_pos or 0)
    ocr = _det._PADDLE_CACHE.get(cfg.ocr_lang)
    if ocr is None:
        return int(start_pos)
    best = int(start_pos)
    foot_run = 0
    i = int(start_pos) - 1
    lo = max(0, int(start_pos) - max_back)
    while i >= lo:
        f = images[i]
        if _blackish(f):
            i -= 1                       # kart-arası siyah boşluk → köprüle, rejimi kırma
            continue
        c = _is_credit_frame(ocr, f, cfg)
        if c:
            best = i; foot_run = 0
        else:
            foot_run += 1
            if foot_run >= gap:
                break                    # sürdürülen footage → kredi rejimi burada başlamış
        i -= 1
    # BLANK-VETO: siyah kareden başlama (GPT: CENNETİN 725 fiziksel siyahtı) → ilk siyah-olmayana kaydır
    j = best
    while j < int(start_pos) and _blackish(images[j]):
        j += 1
    return int(j)


ACCEPT_STATUSES = {"already_in_credit"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def _append_jsonl(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def _safe_reset_pool(pool_dir: Path) -> None:
    resolved = pool_dir.resolve()
    # P-open (Linux, 2026-07): giriş jeneriği simetrik havuzu için giris_jenerik'e de izin ver.
    # cikis_jenerik = mevcut/varsayılan davranış (bit-identik); giris_jenerik = OneOCR'siz açılış havuzu.
    if resolved.name.lower() not in ("cikis_jenerik", "giris_jenerik"):
        raise ValueError(f"refusing to reset unexpected pool dir: {resolved}")
    if resolved.parent.name.lower() != "frames":
        raise ValueError(f"refusing to reset pool outside frames dir: {resolved}")
    if resolved.exists():
        shutil.rmtree(resolved)
    resolved.mkdir(parents=True, exist_ok=True)


def _accept_review_enabled() -> bool:
    # #1 fix (2026-06-27): review_boundary_ambiguous = detektör ONAYLI kredi-çapası buldu ama sınır
    # muğlak (postprocess promote_result_to_anchor confirmed-anchor üzerinden üretir → start_pos GEÇERLİ).
    # Eskiden BOŞ havuz → master-PNG/VL/GLM kaybı (ALİTA/JUMP'ta CANLI doğrulandı). DEFAULT ON; kapat =0.
    return os.environ.get("MITAS_JENERIK_POOL_ACCEPT_REVIEW", "1").strip().lower() not in ("0", "false", "off", "no")


def _accepted(status: str) -> bool:
    if status in ACCEPT_STATUSES or status.startswith("found"):
        return True
    # review_scene_text / review_low_confidence = kredi-kanıtı YOK → havuza ALMA (footage riski).
    # Yalnız review_boundary_ambiguous (onaylı çapa, muğlak sınır) → doldur.
    return status == "review_boundary_ambiguous" and _accept_review_enabled()


def _oneocr_fallback_enabled() -> bool:
    # B kararı (Çağatay 2026-06-27): paddle başarısızsa (not_found/review-scene/low-conf) OneOCR-detektörü
    # dene → non-Latin/FR'yi kurtarır. OneOCR ~80sn/film yavaş ama YALNIZ paddle-başarısızlarında koşar
    # (paddle hızını korur, sadece gerekli ~%20'de OneOCR). DEFAULT ON; kapat =0.
    return os.environ.get("MITAS_JENERIK_ONEOCR_FALLBACK", "1").strip().lower() not in ("0", "false", "off", "no")


def _v5_enabled() -> bool:
    # JENERİK-V5 (2026-07-23, %92 kampanyası — Çağatay kararı: "artık aktif jenerik başlangıç
    # bulma stratejimiz bu"). harness/kunye_kiyas/credit_onset.tespit_v5: 110-film doğrulanmış
    # GT'de %93.6 simetrik / %96.4 üretim-ölçütü / kredisiz-red 29/29. Açıkken eski dedektörün
    # yama yığını (oneocr-fallback / vlm-rescue / footage-trim / backward-extend) ATLANIR —
    # v5 kendi rafinelerini içerir, üstüne eski yamalar bindirilirse onset bozulur.
    # v5 kredi_yok/hata verirse ESKİ akışa birebir düşülür (fail-safe). Kapat: =0.
    return os.environ.get("MITAS_JENERIK_V5", "0").strip().lower() not in ("0", "false", "off", "no")


def _v5_detect(frames_dir: Path, images: list, debug_root: Path) -> int | None:
    """tespit_v5 → images-listesi İNDEKSİ (güvenlik payı düşülmüş) ya da None (→ eski akış).

    Güvenlik payı (MITAS_JENERIK_V5_PAD, varsayılan 10 kare): asimetri politikası
    (Çağatay 2026-07-23) — erken başlamak zararsız, geç kalmak cast'i kaybettirir."""
    sys.path.insert(0, str(PROJECT_ROOT / "harness" / "kunye_kiyas"))
    import credit_onset as _co
    r = _co.tespit_v5(str(frames_dir))
    if r.start_frame is None or int(r.start_frame) < 0:
        _append_jsonl(debug_root / "events.jsonl", {"ts": _now(), "stage": "v5_onset",
                      "sonuc": "kredi_yok", "yontem": r.yontem, "notlar": r.notlar})
        return None
    hedef = int(r.start_frame)
    idx = None
    for i, f in enumerate(images):
        if _co._kare_no(str(f)) == hedef:
            idx = i
            break
    if idx is None and images:  # dosya-adı eşleşmedi (beklenmez) → en yakın kare
        idx = min(range(len(images)), key=lambda i: abs(_co._kare_no(str(images[i])) - hedef))
    if idx is None:
        return None
    try:
        pad = max(0, int(os.environ.get("MITAS_JENERIK_V5_PAD", "10") or "10"))
    except ValueError:
        pad = 10
    son = max(0, idx - pad)
    _append_jsonl(debug_root / "events.jsonl", {"ts": _now(), "stage": "v5_onset",
                  "kare": hedef, "indeks": idx, "pad": pad, "final_indeks": son,
                  "yontem": r.yontem, "guven": r.guven, "notlar": r.notlar})
    return son


def create_pool(
    *,
    frames_dir: Path,
    pool_dir: Path,
    debug_root: Path,
    cfg: DetectorConfig,
    debug_sheet: bool,
) -> dict:
    started = time.perf_counter()
    detector_dir = debug_root / "detector"
    result = detect_frame_dir(frames_dir, detector_dir, cfg, debug_sheet)
    images = list_images(frames_dir)
    engine_used = "paddle"

    # JENERİK-V5 birincil yol (bayraklı): başarılıysa start_pos'u geçersiz kılar,
    # eski yama yığını atlanır; None dönerse (kredi_yok/hata) eski akış birebir sürer.
    v5_start = None
    if _v5_enabled():
        try:
            v5_start = _v5_detect(frames_dir, images, debug_root)
        except Exception as exc:  # noqa: BLE001 — v5 hatası pipeline'ı bozmaz, eski akışa düşer
            _append_jsonl(debug_root / "errors.jsonl",
                          {"ts": _now(), "stage": "v5_onset", "error": f"{type(exc).__name__}: {exc}"})

    # OneOCR FALLBACK: paddle kredi-başlangıcı bulamadıysa OneOCR-detektörü dene (non-Latin/FR kurtarır).
    if v5_start is None and not _accepted(result.status) and _oneocr_fallback_enabled():
        os.environ.setdefault("MITAS_JENERIK_LATIN_LC_NAMES", "1")
        os.environ.setdefault("MITAS_JENERIK_NONLATIN_NAMES", "1")
        try:
            from core.pipelines.ocr.jenerik_oneocr_detector import detect_frame_dir_oneocr
            oc = detect_frame_dir_oneocr(frames_dir, debug_root / "detector_oneocr", cfg)
            if _accepted(oc.status):
                result = oc
                engine_used = "oneocr"
        except Exception as exc:  # noqa: BLE001 — fallback hatası pipeline'ı bozmaz
            _append_jsonl(debug_root / "errors.jsonl",
                          {"ts": _now(), "stage": "oneocr_fallback", "error": f"{type(exc).__name__}: {exc}"})

    copied: list[dict] = []
    status = result.status
    start_pos = result.start_pos
    if v5_start is not None:
        # v5 onset otoritesi devralır; eski CV sonucu manifest'te teşhis olarak kalır.
        start_pos = int(v5_start)
        status = "found"
        engine_used = "v5_onset"
    # VLM-RESCUE: CV başarısız (not_found) ya da şüpheli (çok-erken start + dev havuz = footage-bloat)
    vlm_used = False
    _accepted_cv = _accepted(status)
    # ŞÜPHE (v2, GT-kalibre): "dev havuz VE başı gerçek-kredi-kartı DEĞİL" → CV footage'a yapışmış olabilir.
    # Eski eşik (start < 0.15n) ATTİLA'yı 8 kareyle kaçırıyordu (CV=141, eşik=135). Yeni ölçüt içerik-tabanlı:
    #   - havuz > 450 kare (yarıdan fazlası) VE
    #   - başlangıç karesi _plain_credit DEĞİL (koyu-zemin+yazı olsaydı gerçek kredi kartıdır → dokunma)
    # Böylece ATTİLA (baş=otobüs sahnesi) → VLM'e gider; BABAM (baş=siyah+yazı kart) → VLM'e GİTMEZ (CV+trim doğru).
    def _bright(f):
        try:
            from PIL import Image
            import numpy as np
            return float(np.asarray(Image.open(f).convert("L")).mean())
        except Exception:  # noqa: BLE001
            return 0.0
    _suspicious = (engine_used != "v5_onset"
                   and start_pos is not None and len(images) > 0
                   and (len(images) - int(start_pos)) > 450
                   and _bright(images[int(start_pos)]) > 50.0)
    if engine_used != "v5_onset" and _vlm_rescue_enabled() and (not _accepted_cv or _suspicious):
        try:
            import credit_start_vlm as _cvlm
            vr = _cvlm.detect(frames_dir)
            _append_jsonl(debug_root / "events.jsonl", {"ts": _now(), "stage": "vlm_rescue",
                          "trigger": "not_found" if not _accepted_cv else "suspicious",
                          "cv_start": start_pos, "vlm": {k: v for k, v in vr.items() if k != "labels"}})
            if vr.get("status") in ("found", "left_censored") and vr.get("start_frame") is not None:
                start_pos = int(vr["start_frame"]); status = "found"; engine_used = "vlm_rescue"; vlm_used = True
        except Exception as exc:  # noqa: BLE001 — rescue hatası pipeline'ı bozmaz
            _append_jsonl(debug_root / "errors.jsonl",
                          {"ts": _now(), "stage": "vlm_rescue", "error": f"{type(exc).__name__}: {exc}"})
    # İKİ-YÖNLÜ ANCHOR DÜZELTME (2026-07, GPT-GT ile kalibre):
    #  1) İLERİ footage-trim  → anchor ÇOK ERKEN ise (footage-metnine yapışmış: ATTİLA 141/gerçek 539,
    #                            MARIE 126/gerçek 585) ilk SÜRDÜRÜLEN krediye kadar ilerlet.
    #  2) GERİYE-genişletme    → anchor ÇOK GEÇ ise (soluk/siyah-zeminli ilk kartları kaçırmış:
    #                            BABAM 447/gerçek 415) siyah boşlukları köprüleyip en-erken krediye çek.
    # SIRA ÖNEMLİ: önce ileri (footage'tan çık), sonra geri (rejimin başına in).
    cv_start_before = start_pos
    footage_trimmed = 0
    back_extended = 0
    # v5 yolunda anchor-düzeltme yamaları ÇALIŞMAZ: v5 onset'i içerik/hareket-rafineli,
    # üstüne footage-trim bindirmek "geç kalma" (cast kaybı) riski doğurur.
    if engine_used != "v5_onset" and start_pos is not None and 0 <= int(start_pos) < len(images) and (_accepted(status) or vlm_used):
        fwd = _trim_footage_head_v2(images[int(start_pos):], cfg)
        if fwd > 0:
            footage_trimmed = fwd
            start_pos = int(start_pos) + fwd
        _ext = _backward_extend_credits(images, int(start_pos), cfg)
        if _ext < int(start_pos):
            back_extended = int(start_pos) - _ext
            start_pos = _ext
        if footage_trimmed or back_extended:
            _append_jsonl(debug_root / "events.jsonl", {"ts": _now(), "stage": "anchor_fix",
                          "cv_start": cv_start_before, "fwd_trim": footage_trimmed,
                          "back_extend": back_extended, "final_start": start_pos})

    will_fill = (start_pos is not None and 0 <= int(start_pos) < len(images)
                 and (_accepted(status) or vlm_used))
    preserved_existing = False
    if will_fill:
        # Yeni kareler dolduracağız → bayat kareleri temizle, sonra doldur.
        _safe_reset_pool(pool_dir)
        for source in images[int(start_pos):]:
            target = pool_dir / source.name
            shutil.copy2(source, target)
            copied.append({"source": str(source), "target": str(target), "file": source.name})
    else:
        # Bu koşuda kredi-başlangıcı YOK. ÖNCEKİ başarılı havuzu YOK ETME — flaky/tekrar koşum
        # iyi havuzu silip master'ı kaybetmesin (2026-06-29). Havuz yoksa boş oluştur (dizin-var invariantı).
        preserved_existing = bool(pool_dir.is_dir() and list(pool_dir.glob("*.png")))
        pool_dir.mkdir(parents=True, exist_ok=True)

    manifest = {
        "status": status,
        "engine": engine_used,
        "accepted": bool(copied),
        "preserved_existing_pool": preserved_existing,
        "input_frames": len(images),
        "pool_frames": len(copied),
        "footage_head_trimmed": footage_trimmed,
        "source_frames_dir": str(frames_dir),
        "pool_dir": str(pool_dir),
        "start_pos": start_pos,
        "start_file": (copied[0]["file"] if copied else result.start_file),
        "vlm_rescued": vlm_used,
        "back_extended": back_extended,
        "cv_start_pos": result.start_pos,
        "first_text_pos": result.first_text_pos,
        "first_text_file": result.first_text_file,
        "confidence": result.confidence,
        "credit_type": result.credit_type,
        "reason": result.reason,
        "copied_files": copied,
        "detector": asdict(result),
        "duration_sec": round(time.perf_counter() - started, 3),
        "ts": _now(),
    }

    frames_manifest = frames_dir.parent / "jenerik_detection.json"
    _write_json(frames_manifest, manifest)
    _write_json(debug_root / "pool" / "manifest.json", manifest)
    _append_jsonl(debug_root / "events.jsonl", {
        "ts": _now(),
        "stage": "pool",
        "status": status,
        "input_frames": len(images),
        "pool_frames": len(copied),
        "start_file": result.start_file,
        "first_text_file": result.first_text_file,
    })
    return manifest


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build MITAS parallel jenerik frame pool")
    parser.add_argument("--frames", required=True, help="Database/<film>/frames/cikis")
    parser.add_argument("--pool", required=True, help="Database/<film>/frames/cikis_jenerik")
    parser.add_argument("--debug-root", required=True, help="Database/<film>/jenerik_debug")
    parser.add_argument("--debug-sheet", action="store_true")
    parser.add_argument("--max-width", type=int, default=DetectorConfig.max_width)
    parser.add_argument("--text-threshold", type=float, default=DetectorConfig.text_threshold)
    parser.add_argument("--soft-threshold", type=float, default=DetectorConfig.soft_threshold)
    parser.add_argument("--lookahead", type=int, default=DetectorConfig.lookahead)
    parser.add_argument("--min-hits", type=int, default=DetectorConfig.min_hits)
    parser.add_argument("--preroll-frames", type=int, default=DetectorConfig.preroll_frames)
    parser.add_argument("--ocr-mode", choices=["none", "paddle"], default="paddle")
    parser.add_argument("--ocr-stride", type=int, default=8)
    parser.add_argument("--ocr-lang", default=DetectorConfig.ocr_lang)
    parser.add_argument("--sustain-window", type=int, default=DetectorConfig.sustain_window)
    parser.add_argument("--sustain-hits", type=int, default=DetectorConfig.sustain_hits)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    cfg = DetectorConfig(
        max_width=args.max_width,
        text_threshold=args.text_threshold,
        soft_threshold=args.soft_threshold,
        lookahead=args.lookahead,
        min_hits=args.min_hits,
        preroll_frames=args.preroll_frames,
        ocr_mode=args.ocr_mode,
        ocr_stride=args.ocr_stride,
        ocr_lang=args.ocr_lang,
        sustain_window=args.sustain_window,
        sustain_hits=args.sustain_hits,
    )
    debug_root = Path(args.debug_root)
    try:
        manifest = create_pool(
            frames_dir=Path(args.frames),
            pool_dir=Path(args.pool),
            debug_root=debug_root,
            cfg=cfg,
            debug_sheet=args.debug_sheet,
        )
        print(json.dumps(manifest, ensure_ascii=False))
        return 0
    except Exception as exc:  # noqa: BLE001 - fail-safe caller logs and continues
        err = {
            "ts": _now(),
            "stage": "pool",
            "status": "error",
            "error": f"{type(exc).__name__}: {exc}",
        }
        _append_jsonl(debug_root / "errors.jsonl", err)
        print(json.dumps(err, ensure_ascii=False))
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
