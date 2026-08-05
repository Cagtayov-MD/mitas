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
PROJECT_ROOT = Path(os.environ.get("MITAS_PROJECT_ROOT") or "/opt/mitas")
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

# Dalga 3 metin-kapı eşiği: son %15 karede jbayrak (credit-benzeri kutu) oranı >= bu
# → review_required (insan kuyruğu); altındaysa kredi_yok (bugünkü gibi red).
METIN_KAPI_ESIK = 0.30


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


def _metin_kapi_enabled() -> bool:
    # Dalga 3 (konsey kararı 2026-07-29): v5 kredi_yok derse CV DEVRALMAZ; credit_box
    # det-only metin taraması son %15'te credit-benzeri kutu arar. DEFAULT KAPALI —
    # üretim davranışı Çağatay onayı + return-3 denetimi + insan FN=0 doğrulaması
    # olmadan değişmesin. Aç: MITAS_JENERIK_METIN_KAPI=1.
    return os.environ.get("MITAS_JENERIK_METIN_KAPI", "0").strip().lower() not in ("0", "false", "off", "no")


def _v5_enabled() -> bool:
    # JENERİK-V5 (2026-07-23, %92 kampanyası — Çağatay kararı: "artık aktif jenerik başlangıç
    # bulma stratejimiz bu"). FIGO = harness/kunye_kiyas/figo.tespit_v5: 110-film doğrulanmış
    # GT'de %93.6 simetrik / %96.4 üretim-ölçütü / kredisiz-red 29/29. Açıkken eski dedektörün
    # yama yığını (oneocr-fallback / vlm-rescue / footage-trim / backward-extend) ATLANIR —
    # v5 kendi rafinelerini içerir, üstüne eski yamalar bindirilirse onset bozulur.
    # v5 kredi_yok/hata verirse ESKİ akışa birebir düşülür (fail-safe). Kapat: =0.
    return os.environ.get("MITAS_JENERIK_V5", "0").strip().lower() not in ("0", "false", "off", "no")


def _suphe_genis_havuz_enabled() -> bool:
    # ŞÜPHE KATMANI — GENİŞ-HAVUZ bayrağı (2026-07-30, konsey GLM+Nemotron kırmızı-
    # takım gardlı; Çağatay: "tespit edemesek bile şüpheyi bilelim; gerekirse tüm
    # havuzu alırız, isim kaçarsa PDF şaşar"). Açıkken VE v5 KAZANDIYSA (kredisizde
    # ASLA — konsey kırmızı çizgisi: AMY sınıfında sahte havuz doldurma yasak) VE
    # credit_onset.Sonuc.suphe içinde "gec_riski" varsa, havuzu elenen komşu
    # adayın BAŞINA (suphe_geri_kare) çeker — tavan en fazla 120 kare (asimetri
    # politikası, erken≤120). DEFAULT KAPALI — yalnız ÖLÇÜM/bilgi amaçlı; üretim
    # davranışı Çağatay onayı olmadan değişmesin. Aç: =1.
    return os.environ.get("MITAS_JENERIK_SUPHE_GENIS_HAVUZ", "0").strip().lower() not in ("0", "false", "off", "no")


def _v5_detect(frames_dir: Path, images: list, debug_root: Path, kuru: bool = False) -> dict:
    """tespit_v5 çağırır; TÜM teşhis bilgisini bir sözlükte döndürür — hem
    create_pool'un start_pos kararı (final_indeks) hem de manifest'in YENİ `v5`
    alt-nesnesi (Dalga 2) BURADAN besleniyor. `final_indeks` None ise (kredi_yok
    ya da dosya-eşleşme başarısız) → eski akışa (CV) düşülür.

    Güvenlik payı (MITAS_JENERIK_V5_PAD, varsayılan 10 kare): asimetri politikası
    (Çağatay 2026-07-23) — erken başlamak zararsız, geç kalmak cast'i kaybettirir.

    `kuru=True` (--kuru dry-run): events.jsonl'e HİÇBİR ŞEY yazılmaz — dönüş
    değeri (dolayısıyla manifest) değişmez, yalnız yan-etki (dosya yazımı) atlanır."""
    try:
        pad = max(0, int(os.environ.get("MITAS_JENERIK_V5_PAD", "10") or "10"))
    except ValueError:
        pad = 10
    sys.path.insert(0, str(PROJECT_ROOT / "harness" / "kunye_kiyas"))
    import figo as _co
    r = _co.tespit_v5(str(frames_dir))
    if r.start_frame is None or int(r.start_frame) < 0:
        if not kuru:
            _append_jsonl(debug_root / "events.jsonl", {"ts": _now(), "stage": "v5_onset",
                          "sonuc": "kredi_yok", "yontem": r.yontem, "notlar": r.notlar})
        return {"final_indeks": None, "raw_indeks": None, "sonuc": r, "pad": pad}
    hedef = int(r.start_frame)
    idx = None
    for i, f in enumerate(images):
        if _co._kare_no(str(f)) == hedef:
            idx = i
            break
    if idx is None and images:  # dosya-adı eşleşmedi (beklenmez) → en yakın kare
        idx = min(range(len(images)), key=lambda i: abs(_co._kare_no(str(images[i])) - hedef))
    if idx is None:
        return {"final_indeks": None, "raw_indeks": None, "sonuc": r, "pad": pad}
    son = max(0, idx - pad)

    # ŞÜPHE KATMANI — GENİŞ-HAVUZ (2026-07-30, DEFAULT KAPALI, bkz.
    # _suphe_genis_havuz_enabled). Buradayız = v5 KAZANDI (r.start_frame >= 0,
    # yukarıdaki erken-return'ler AMY sınıfı kredisiz filmleri zaten eledi —
    # konsey kırmızı çizgisi: sahte havuz doldurma yalnız v5 gerçekten
    # kazandığında mümkün). gec_riski ateşlediyse havuzu elenen komşu adayın
    # BAŞINA (suphe_geri_kare) çek — tavan `son`dan en fazla 120 kare geriye
    # (asimetri politikası erken≤120).
    if (_suphe_genis_havuz_enabled() and "gec_riski" in (r.suphe or [])
            and r.suphe_geri_kare is not None and int(r.suphe_geri_kare) >= 0):
        geri_kare = int(r.suphe_geri_kare)
        geri_idx = None
        for i, f in enumerate(images):
            if _co._kare_no(str(f)) == geri_kare:
                geri_idx = i
                break
        if geri_idx is None and images:
            geri_idx = min(range(len(images)), key=lambda i: abs(_co._kare_no(str(images[i])) - geri_kare))
        if geri_idx is not None and geri_idx < son:
            tavan = max(0, son - 120)
            yeni_son = max(geri_idx, tavan)
            if yeni_son < son:
                if not kuru:
                    _append_jsonl(debug_root / "events.jsonl", {"ts": _now(), "stage": "suphe_genis_havuz",
                                  "eski": son, "yeni": yeni_son})
                son = yeni_son

    if not kuru:
        _append_jsonl(debug_root / "events.jsonl", {"ts": _now(), "stage": "v5_onset",
                      "kare": hedef, "indeks": idx, "pad": pad, "final_indeks": son,
                      "yontem": r.yontem, "guven": r.guven, "notlar": r.notlar})
    return {"final_indeks": son, "raw_indeks": idx, "sonuc": r, "pad": pad}


def _v5_manifest_alt_nesne(v5_start: int | None, v5_info: dict | None,
                            v5_hata_bilgi: str | None, segment_v5_uygun: bool) -> dict:
    """Manifest'in YENİ `v5` alt-nesnesi (Dalga 2, Adım5) — HER ZAMAN yazılır,
    v5 BAŞARISIZ olduğunda (kredi_yok) da. Bugüne dek v5'in kredi_yok kararı CV
    tarafından sessizce eziliyordu; bu alt-nesne onu artık görünür kılıyor.

    `karar` dört değerden biri — şemanın (found/kredi_yok/hata) ÜSTÜNE bilinçli
    bir 4. durum eklendi: "atlandi" (v5 hiç ÇAĞRILMADI — segment=giris ya da
    MITAS_JENERIK_V5 kapalı). Bunu "kredi_yok" sayıp gizlemek dürüst olmazdı —
    v5_izleme.py'nin Dalga-3 kuyruğu tam olarak "v5 denedi ve reddetti" filmlerini
    hedefliyor, segment=giris rotalaması ise bir FİLM ÖZELLİĞİ değil, kasıtlı
    motor seçimi (bkz. create_pool segment gardı)."""
    if v5_hata_bilgi is not None:
        return {"karar": "hata", "notlar": v5_hata_bilgi}
    if v5_info is None:
        sebep = ("segment=giris — v5 hiç çağrılmadı (SON_ERISIM açılış penceresinde anlamsız)"
                 if not segment_v5_uygun else "MITAS_JENERIK_V5 kapalı (env)")
        return {"karar": "atlandi", "notlar": sebep}
    r = v5_info["sonuc"]
    kare = int(r.start_frame) if (r.start_frame is not None and int(r.start_frame) >= 0) else None
    return {
        "karar": "found" if v5_start is not None else "kredi_yok",
        "kare": kare,
        "indeks": v5_info["raw_indeks"],
        "pad": v5_info["pad"],
        "yontem": r.yontem,
        "tip": r.tip,
        "scroll_orani": r.scroll_orani,
        "ardisik_scroll": r.ardisik_scroll,
        "son_capa": r.son_capa,
        "aday_sayisi": r.aday_sayisi,
        "notlar": r.notlar,
        "suphe": r.suphe,
    }


def create_pool(
    *,
    frames_dir: Path,
    pool_dir: Path,
    debug_root: Path,
    cfg: DetectorConfig,
    debug_sheet: bool,
    segment: str = "cikis",
    kuru: bool = False,
) -> dict:
    started = time.perf_counter()
    detector_dir = debug_root / "detector"
    images = list_images(frames_dir)
    engine_used = "paddle"

    # harness/kunye_kiyas sys.path'e ekli olsun garanti et (FIGO _v5_detect
    # içinde zaten ekliyor ama metin-kapı dalı v5 hiç çağrılmadan da credit_box'a
    # ihtiyaç duyabilir — idempotent, yinelenen insert zararsız).
    sys.path.insert(0, str(PROJECT_ROOT / "harness" / "kunye_kiyas"))

    # SEGMENT GARDI (Dalga 2, 2026-07-29): --segment giris → v5 HİÇ ÇAĞRILMAZ,
    # CV bugünkü gibi (birebir) koşar. Sebep: v5'in SON_ERISIM=0.82 kuralı "aday
    # dizinin son %18'ine ulaşmalı" diyor — açılış penceresinde (270 kare, ilk
    # 4 dk) anlamsız (ölçüldü: 270 karelik giriş penceresinde v5 kare 135/181
    # döndürüyor). Bu bir RET değil, doğru motora yönlendirme — giriş havuzu
    # bugünkü gibi dolmaya devam etmeli. `--segment cikis` (varsayılan) v5 birincil.
    segment_v5_uygun = (segment != "giris")

    # JENERİK-V5 birincil yol + TEMBEL CV (Dalga 2): v5 ÖNCE denenir; yalnız v5
    # BAŞARISIZ (kredi_yok/hata) olursa YA DA segment=giris ise CV koşar. v5
    # başarılıysa `result` HİÇ OLUŞMAZ — CV'nin maliyeti (ölçüldü: ~17.4sn/film,
    # v5 ~5.2sn) tamamen atlanır (bugüne dek v5 açıkken bile HER filmde koşuyordu).
    v5_start: int | None = None
    v5_info: dict | None = None
    v5_hata_bilgi: str | None = None
    if segment_v5_uygun and _v5_enabled():
        try:
            v5_info = _v5_detect(frames_dir, images, debug_root, kuru=kuru)
            v5_start = v5_info["final_indeks"]
        except Exception as exc:  # noqa: BLE001 — v5 hatası pipeline'ı bozmaz, CV'ye düşülür (fail-safe)
            v5_hata_bilgi = f"{type(exc).__name__}: {exc}"
            if not kuru:
                _append_jsonl(debug_root / "errors.jsonl",
                              {"ts": _now(), "stage": "v5_onset", "error": v5_hata_bilgi})

    # v5 kazanmadıysa (kredi_yok/hata) YA DA segment=giris (v5 hiç denenmedi) →
    # eski CV dedektörünü ŞİMDİ çalıştır (öncesinde v5-öncelikli akışta EN BAŞTA
    # koşuyordu — tembel-CV bunu yalnız gerekince koşar hale getiriyor).
    result = None
    review_required = False
    metin_kapi_karari = False          # metin-kapı bu koşuda karar verdiyse True (VLM/trim/CV baypas)

    if v5_start is not None:
        # v5 onset otoritesi devralır; `result` hiç oluşmadı (tembel CV) — eski CV
        # teşhisi (cv_start_pos/detector/...) bu koşuda YOK, `v5` alt-nesnesi var.
        status = "found"
        start_pos = int(v5_start)
        engine_used = "v5_onset"
    elif (_metin_kapi_enabled() and segment_v5_uygun and v5_hata_bilgi is None
          and v5_info is not None):
        # Dalga 3 (konsey 2026-07-29): v5 KREDİ_YOK dedi — HATA DEĞİL, v5 GERÇEKTEN
        # ÇAĞRILDI (v5_info dolu) ve çıkış segmenti. Eski akışta bu durum CV'ye
        # sessizce düşerdi; metin-kapı bunun yerine CV'yi DEVREYE SOKMAZ — credit_box
        # det-only ile son %15 karede credit-benzeri kutu var mı diye ucuz bir tarama
        # yapar. v5 hata verdiyse (v5_hata_bilgi) YA DA v5 hiç çağrılmadıysa
        # (v5_info None — segment=giris ya da MITAS_JENERIK_V5 kapalı) BU DALA
        # GİRİLMEZ → CV fallback bugünkü gibi korunur (hata/atlandı ≠ kredi_yok).
        metin_kapi_karari = True
        engine_used = "v5_kredi_yok"
        start_pos = None
        oran = 0.0
        son_kareler: list[str] = []
        try:
            son_bas = int(len(images) * 0.85)
            son_kareler = [str(f) for f in images[son_bas:]]
            if son_kareler:
                import credit_box as _cb
                jbayrak, _say = _cb.kutu_serisi(son_kareler, stride=2)
                import numpy as _np
                oran = float(_np.mean(jbayrak)) if len(jbayrak) else 0.0
        except Exception as exc:  # noqa: BLE001 — metin-kapı hatası pipeline'ı bozmaz, kredi_yok'a düş
            oran = 0.0
            if not kuru:
                _append_jsonl(debug_root / "errors.jsonl",
                              {"ts": _now(), "stage": "metin_kapi", "error": f"{type(exc).__name__}: {exc}"})
        if oran >= METIN_KAPI_ESIK:
            status = "review_kredi_yok"
            review_required = True
        else:
            status = "kredi_yok"
        if not kuru:
            _append_jsonl(debug_root / "events.jsonl", {"ts": _now(), "stage": "metin_kapi",
                          "jbayrak_oran": round(oran, 3), "esik": METIN_KAPI_ESIK,
                          "sonuc": status, "son_kare_sayisi": len(son_kareler)})
    else:
        # BUGÜNKÜ DAVRANIŞ: bayrak kapalı VEYA v5 hata VEYA v5 hiç çağrılmadı
        # (segment=giris / MITAS_JENERIK_V5 kapalı) → CV devralır.
        result = detect_frame_dir(frames_dir, detector_dir, cfg, debug_sheet)
        # OneOCR fallback SÖKÜLDÜ (2026-07-30, Çağatay: "oneocr ne alaka, Linux'tayız").
        # `oneocr` paketi (Microsoft Windows OCR) Linux'ta YOK: make_oneocr_engine() →
        # ModuleNotFoundError. Fallback her v5-kredi_yok filminde ateşleyip except'e
        # düşüyor, errors.jsonl'i kirletiyordu; v5 aktivasyonundan (2026-07-23) beri
        # engine=oneocr TEK manifest üretmemiş — Linux'ta ölü kod, davranış-nötr söküm.
        # (jenerik_oneocr_detector.py SİLİNMEDİ — giris_jenerik_havuzu.py:76 hâlâ
        # oneocr_line_boxes import ediyor; o da Linux'ta çöküyor olabilir, AYRI iş.)
        status = result.status
        start_pos = result.start_pos

    copied: list[dict] = []
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
    _suspicious = (engine_used != "v5_onset" and not metin_kapi_karari
                   and start_pos is not None and len(images) > 0
                   and (len(images) - int(start_pos)) > 450
                   and _bright(images[int(start_pos)]) > 50.0)
    if (engine_used != "v5_onset" and not metin_kapi_karari
            and _vlm_rescue_enabled() and (not _accepted_cv or _suspicious)):
        try:
            import credit_start_vlm as _cvlm
            vr = _cvlm.detect(frames_dir)
            if not kuru:
                _append_jsonl(debug_root / "events.jsonl", {"ts": _now(), "stage": "vlm_rescue",
                              "trigger": "not_found" if not _accepted_cv else "suspicious",
                              "cv_start": start_pos, "vlm": {k: v for k, v in vr.items() if k != "labels"}})
            if vr.get("status") in ("found", "left_censored") and vr.get("start_frame") is not None:
                start_pos = int(vr["start_frame"]); status = "found"; engine_used = "vlm_rescue"; vlm_used = True
        except Exception as exc:  # noqa: BLE001 — rescue hatası pipeline'ı bozmaz
            if not kuru:
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
    # üstüne footage-trim bindirmek "geç kalma" (cast kaybı) riski doğurur. metin-kapı
    # yolunda da ÇALIŞMAZ (start_pos zaten None, ama niyet açık kalsın diye gard eklendi).
    if (engine_used != "v5_onset" and not metin_kapi_karari
            and start_pos is not None and 0 <= int(start_pos) < len(images)
            and (_accepted(status) or vlm_used)):
        fwd = _trim_footage_head_v2(images[int(start_pos):], cfg)
        if fwd > 0:
            footage_trimmed = fwd
            start_pos = int(start_pos) + fwd
        _ext = _backward_extend_credits(images, int(start_pos), cfg)
        if _ext < int(start_pos):
            back_extended = int(start_pos) - _ext
            start_pos = _ext
        if (footage_trimmed or back_extended) and not kuru:
            _append_jsonl(debug_root / "events.jsonl", {"ts": _now(), "stage": "anchor_fix",
                          "cv_start": cv_start_before, "fwd_trim": footage_trimmed,
                          "back_extend": back_extended, "final_start": start_pos})

    will_fill = (start_pos is not None and 0 <= int(start_pos) < len(images)
                 and (_accepted(status) or vlm_used))
    preserved_existing = False
    if will_fill:
        # Yeni kareler dolduracağız → bayat kareleri temizle, sonra doldur.
        # --kuru: shutil.copy2/_safe_reset_pool ATLANIR (üretim Database'ini
        # kirletmesin) — `copied` yine de dolar ki pool_frames/start_file
        # manifest'te gerçekçi kalsın (Adım 1).
        if not kuru:
            _safe_reset_pool(pool_dir)
        for source in images[int(start_pos):]:
            target = pool_dir / source.name
            if not kuru:
                shutil.copy2(source, target)
            copied.append({"source": str(source), "target": str(target), "file": source.name})
    else:
        # Bu koşuda kredi-başlangıcı YOK. ÖNCEKİ başarılı havuzu YOK ETME — flaky/tekrar koşum
        # iyi havuzu silip master'ı kaybetmesin (2026-06-29). Havuz yoksa boş oluştur (dizin-var invariantı).
        # (is_dir/glob salt-okur, --kuru'da da çalışır — yalnız mkdir yan-etkisi atlanır.)
        preserved_existing = bool(pool_dir.is_dir() and list(pool_dir.glob("*.png")))
        if not kuru:
            pool_dir.mkdir(parents=True, exist_ok=True)

    # Dalga 2, Adım5 manifest şeması: v5 kazandıysa CV hiç koşmadı → cv_start_pos/
    # first_text_pos/first_text_file/confidence/detector ALANLARI YAZILMAZ (değer
    # yok); credit_type/reason v5'in kendi teşhisinden (v5.tip/v5.notlar) gelir.
    # CV devraldıysa (result != None) bugünkü gibi yazılır — sözleşme korunur
    # (kurulum/25_r3_kalan.py:pencere_sec "scroll" in credit_type → 30sn testi).
    # Dalga 3: metin-kapı yolunda (result None, v5_kazandi False) credit_type="none"
    # (scroll/static değil — v5 zaten kredi_yok dedi), reason v5'in kredi_yok
    # teşhisinin notlarından (v5_info["sonuc"].notlar) gelir.
    v5_kazandi = (engine_used == "v5_onset")
    if v5_kazandi and v5_info is not None:
        _credit_type = {"scroll": "scroll_credit", "statik": "static_credit"}.get(v5_info["sonuc"].tip, "none")
        _reason = v5_info["sonuc"].notlar
    elif metin_kapi_karari:
        _credit_type = "none"
        _reason = (v5_info["sonuc"].notlar if v5_info is not None else None)
    else:
        _credit_type = (result.credit_type if result is not None else None)
        _reason = (result.reason if result is not None else None)
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
        "start_file": (copied[0]["file"] if copied else (result.start_file if result is not None else None)),
        "vlm_rescued": vlm_used,
        "back_extended": back_extended,
        "credit_type": _credit_type,
        "reason": _reason,
        "review_required": review_required,
        "v5": _v5_manifest_alt_nesne(v5_start, v5_info, v5_hata_bilgi, segment_v5_uygun),
        "copied_files": copied,
        "duration_sec": round(time.perf_counter() - started, 3),
        "ts": _now(),
    }
    if not v5_kazandi and result is not None:
        # CV (paddle/oneocr/vlm_rescue) devraldı → eski teşhis alanları bugünkü gibi.
        manifest["cv_start_pos"] = result.start_pos
        manifest["first_text_pos"] = result.first_text_pos
        manifest["first_text_file"] = result.first_text_file
        manifest["confidence"] = result.confidence
        manifest["detector"] = asdict(result)

    if not kuru:
        frames_manifest = frames_dir.parent / "jenerik_detection.json"
        _write_json(frames_manifest, manifest)
        _write_json(debug_root / "pool" / "manifest.json", manifest)
        _append_jsonl(debug_root / "events.jsonl", {
            "ts": _now(),
            "stage": "pool",
            "status": status,
            "input_frames": len(images),
            "pool_frames": len(copied),
            "start_file": (result.start_file if result is not None else None),
            "first_text_file": (result.first_text_file if result is not None else None),
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
    parser.add_argument("--segment", choices=["cikis", "giris"], default="cikis",
                        help="cikis (varsayılan): v5 birincil + tembel CV. "
                             "giris: v5 HİÇ ÇAĞRILMAZ, CV bugünkü gibi koşar "
                             "(v5'in SON_ERISIM kuralı açılış penceresinde anlamsız).")
    parser.add_argument("--kuru", action="store_true",
                        help="Dry-run: shutil.copy2/_safe_reset_pool atlanır, "
                             "jenerik_detection.json / debug_root/pool/manifest.json / "
                             "events.jsonl / errors.jsonl YAZILMAZ — manifest yalnız stdout'a basılır.")
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
            segment=args.segment,
            kuru=args.kuru,
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
        if not args.kuru:
            _append_jsonl(debug_root / "errors.jsonl", err)
        print(json.dumps(err, ensure_ascii=False))
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
