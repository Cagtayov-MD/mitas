# -*- coding: utf-8 -*-
"""GİRİŞ jeneriği YAZI-HAVUZU — 3. tip havuz (Çağatay, 2026-06-29).

AMAÇ (mevcut iki havuzdan AYRI):
  - "normal giriş-noktası tespiti" (giris_offset_detect.py) bitiş-noktası bulur, BİTİŞİK pencere üretir.
  - "çıkış jeneriği havuzu" (cikis_jenerik) yine BİTİŞİK pencere kopyasıdır.
  Bu araç ÜÇÜNCÜ bir mantık kurar: GİRİŞ noktası / pencere bulmaz. frames/giris/ içindeki HER kareyi
  OneOCR ile hızlı tarar ve YALNIZ "yazı olan (ALTYAZI HARİÇ)" kareleri havuza KOPYALAR. Yazısız
  (footage) kareler dışarıda kalır. Böylece — tıpkı çıkışta olduğu gibi — jenerik başlangıcından
  sonra araya giren footage boşlukları ATLANIR, ama SONRADAN köşede beliren ufak kredi (yönetmen/stüdyo
  kartı vb.) yakalanır. Sonra havuzda AYNI YAZIYI taşıyan kareler TEKE indirilir (dedup).

TASARIM KARARI (3 bağımsız Sonnet önerisi + tarafsız yüksek-eforlu Opus hakem, 2026-06-29):
  metin-varlığı = SALT OneOCR (kullanıcı hızı; paddle-ikincil marjinal → reddedildi).
  altyazı eleme = İKİ KATMAN, SATIR-bazında OR-survival (kareye >=1 meşru satır yeter):
     KATMAN-A konumsal: OneOCR satır bbox y-merkezi >= SUB_FRAC (alt-bant) → altyazı say.
     KATMAN-B metinsel: is_credit_text_line==False (>=6 kelime / nokta-bitiş / harf-oranı düşük) → kredi değil.
  dedup = metin-imzası PRIMARY (fold-sort-join kredi satırları) + dhash_hi(16x16) küme-İÇİ görsel tiebreak.
  RECALL: imread/OCR hatası → kare KOŞULSUZ havuza ("okunamadı > yanlış oku"). Footage (0 satır) → alınmaz.

ADDITIVE & STANDALONE: HİÇBİR üretim dosyasını değiştirmez. Kaynak frames/giris/ DOKUNULMAZ (yalnız KOPYALA).
Yalnız kendi çıktı klasörlerini yazar: frames/giris_jenerik/ (DOĞRUDAN azaltılmış havuz: yazı-var ∩ benzer-silinmiş;
kayan jenerik korunur) + frames/giris_jenerik_manifest.json. (Eski ayrı _dedup klasörü kaldırıldı.)

KOŞUM (ocr venv ŞART — paddle/oneocr orada):
  E:\\MITAS\\venvs\\ocr\\Scripts\\python.exe scripts/giris_jenerik_havuzu.py --film "ALİTA SAVAŞ MELEĞİ 2025-1241-1-0000-90-1"
  ...                                                                     --frames "Database/<film>/frames/giris"
  ...                                                                     --batch films.txt        (satır başına film adı)
  ...                                                                     --dump-dir DIR           (manifest'i ayrıca oraya da yaz)

Env-eşikler (hepsi makul varsayılan):
  MITAS_GIRIS_SUB_FRAC   = 0.82  altyazı alt-bant y-merkez eşiği (6-film offline ölçümle ayarlandı: alt-üçte-bir
                                 oyuncu kredisi 0.78-0.82'de kalır=KURTARILIR; gerçek altyazı y>=0.84 → elenir)
  MITAS_GIRIS_MIN_LINES  = 1     havuza alma için min meşru satır (sıkılaştırma: 2)
  MITAS_GIRIS_SCAN_CAP   = 0     0=TÜM kareler (geç köşe-yazısı için tam tarama); >0 ise ilk N kare
  MITAS_GIRIS_DEDUP_HAM  = 12    dhash_hi 256-bit görsel-birleştirme Hamming eşiği (statik kart ~0-6; farklı kart 20+)
  MITAS_GIRIS_DEDUP_HI   = 1     1=dhash_hi(16x16) | 0=dhash(8x8)
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import traceback
from datetime import datetime
from pathlib import Path

# ── stdout/stderr UTF-8 ───────────────────────────────────────────────────────
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

# ── proje kökü sys.path ────────────────────────────────────────────────────────
# Linux geçişi 2026-07-16: env varsa onu kullan (Windows'ta env yoksa eski davranış birebir).
PROJECT_ROOT = Path(os.environ.get("MITAS_PROJECT_ROOT") or r"E:\MITAS")
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))  # _pipe_ocr importu için

# is_credit_text_line saf-Python; ama jenerik_detector importu paddle yardımcılarını da kurar.
# giris_offset_detect.py ile parite (zararsız setdefault).
os.environ.setdefault("JENERIK_PADDLE_FAST_NO_DOC", "1")
os.environ.setdefault("MITAS_JENERIK_NONLATIN_NAMES", "1")
os.environ.setdefault("MITAS_JENERIK_LATIN_LC_NAMES", "1")

# ── yeniden kullanılan primitifler (teyit edilmiş) ─────────────────────────────
from core.pipelines.ocr.jenerik_detector import is_credit_text_line  # noqa: E402
from core.pipelines.ocr.jenerik_frame_pool_detector import (  # noqa: E402
    imread_unicode,
    list_images,
    natural_frame_no,
)
from core.pipelines.ocr.jenerik_oneocr_detector import oneocr_line_boxes  # noqa: E402  (4-köşe→eksen-hizalı box)
from _pipe_ocr import build_engine, fold  # noqa: E402

import cv2  # noqa: E402  (jenerik_oneocr_detector zaten getiriyor; dhash için)

TOOL_VERSION = "1.1"
POOL_DIRNAME = "giris_jenerik"            # ham=frames/giris, derlenmiş=frames/giris_jenerik (cikis_jenerik'e paralel)
DEDUP_DIRNAME = "giris_jenerik_dedup"
MANIFEST_NAME = "giris_jenerik_manifest.json"


# ── env yardımcıları ───────────────────────────────────────────────────────────
def _int_env(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (ValueError, TypeError):
        return default


def _float_env(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except (ValueError, TypeError):
        return default


def _bool_env(name: str, default: bool) -> bool:
    v = os.environ.get(name)
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "on", "yes")


def _get_params() -> dict:
    return {
        "SUB_FRAC":   _float_env("MITAS_GIRIS_SUB_FRAC", 0.82),
        "MIN_LINES":  _int_env("MITAS_GIRIS_MIN_LINES", 1),
        "SCAN_CAP":   _int_env("MITAS_GIRIS_SCAN_CAP", 0),
        "DEDUP_HAM":  _int_env("MITAS_GIRIS_DEDUP_HAM", 12),
        "DEDUP_HI":   _bool_env("MITAS_GIRIS_DEDUP_HI", True),
    }


# ── dHash (db_compose_master.py ile birebir; ufak → bağımlılık azaltmak için inline) ──
def _dhash(image, size: int = 8) -> int:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    gray = cv2.resize(gray, (size + 1, size))
    diff = gray[:, 1:] > gray[:, :-1]
    bits = 0
    for value in diff.flatten():
        bits = (bits << 1) | int(value)
    return bits


def _dhash_hi(image, size: int = 16) -> int:
    return _dhash(image, size=size)


def _hamming(a: int, b: int) -> int:
    return bin(a ^ b).count("1")


# ── OneOCR motoru (önbellekli) ─────────────────────────────────────────────────
_ENGINE_CACHE: dict = {}


def _get_engine() -> tuple[object, str, str | None]:
    if "eng" not in _ENGINE_CACHE:
        try:
            eng, kind, err = build_engine()
        except Exception as exc:  # noqa: BLE001
            eng, kind, err = None, "yok", f"{type(exc).__name__}: {exc}"
        _ENGINE_CACHE["eng"] = (eng, kind, err)
    return _ENGINE_CACHE["eng"]


# ── kredi-metni testi (yerel recall gevşetmesi; üretim is_credit_text_line DOKUNULMAZ) ──
def _is_credit_text(t: str) -> bool:
    """is_credit_text_line + YEREL nokta-bitiş gevşetmesi.

    Sahada bulundu (AŞK VE İNTİKAM/RED ROCK, 2026-06-29): OCR kısa isim/rol satırlarına
    sık YANLIŞ nokta ekliyor ("CHARLES LANG, JR." → "CHARLES LANG, JE.", "FRANK P.") →
    üretim is_credit_text_line nokta-bitişi cümle sanıp reddediyor → gerçek kredi düşüyor.
    YALNIZ 2-3 kelimelik nokta-biten satırda noktayı atıp tekrar test et (isim/rol kurtar).
    Tek-kelime nokta ('Evet.') ve >=4 kelimeli cümle (KOVAN epilog koruması) DOKUNULMAZ."""
    if is_credit_text_line(t):
        return True
    s = (t or "").strip()
    if s.endswith(".") and 2 <= len(s.split()) <= 3:
        return is_credit_text_line(s.rstrip(". "))
    return False


# ── tek kare kararı ────────────────────────────────────────────────────────────
def _classify_frame(path: Path, eng, params: dict) -> dict:
    """Bir kareyi sınıflandır → manifest satırı (kopyalama/dedup ÜST katmanda).

    decision: 'kept' | 'dropped_footage' | 'kept_error'
    reason:   'credit_line' | 'footage_no_text' | 'all_subtitle' | 'read_error_kept' | 'ocr_error_kept'
    """
    file = path.name
    fidx = natural_frame_no(path)

    bgr = imread_unicode(str(path))
    if bgr is None:
        # RECALL: okunamayan kare ASLA elenmez.
        return {
            "file": file, "frame_index": fidx, "decision": "kept_error",
            "reason": "read_error_kept", "credit_lines": [], "subtitle_lines": [],
            "lines_bbox": [], "sig": "", "_hash": None,
        }

    # Görsel imza (dedup için; OCR'dan bağımsız stabil sinyal). Hata → None (singleton kalır).
    try:
        fhash = _dhash_hi(bgr) if params["DEDUP_HI"] else _dhash(bgr)
    except Exception:
        fhash = None

    try:
        items = oneocr_line_boxes(eng, bgr)  # [((x0,y0,x1,y1), text), ...]
    except Exception:
        # RECALL: OCR hatası → kareyi havuza al.
        return {
            "file": file, "frame_index": fidx, "decision": "kept_error",
            "reason": "ocr_error_kept", "credit_lines": [], "subtitle_lines": [],
            "lines_bbox": [], "sig": "", "_hash": fhash,
        }

    H = bgr.shape[0]
    sub_frac = params["SUB_FRAC"]
    credit_lines: list[str] = []
    subtitle_lines: list[str] = []
    lines_bbox: list[dict] = []

    for box, text in items:
        y0, y1 = box[1], box[3]
        y_center_frac = ((y0 + y1) / 2.0) / max(1, H)
        in_sub_band = y_center_frac >= sub_frac
        is_cred = _is_credit_text(text)
        legit = bool(is_cred and not in_sub_band)   # meşru = kredi-metni VE alt-bant DIŞI
        lines_bbox.append({
            "text": text,
            "y_center_frac": round(float(y_center_frac), 4),
            "is_credit": bool(is_cred),
            "in_sub_band": bool(in_sub_band),
        })
        if legit:
            credit_lines.append(text)
        else:
            subtitle_lines.append(text)

    if len(credit_lines) >= params["MIN_LINES"]:
        sig = "|".join(sorted(fold(t) for t in credit_lines))
        return {
            "file": file, "frame_index": fidx, "decision": "kept",
            "reason": "credit_line", "credit_lines": credit_lines,
            "subtitle_lines": subtitle_lines, "lines_bbox": lines_bbox, "sig": sig,
            "_hash": fhash,
        }

    # satır var ama meşru yok → altyazı/footage-yazısı; hiç satır yok → footage
    reason = "all_subtitle" if items else "footage_no_text"
    return {
        "file": file, "frame_index": fidx, "decision": "dropped_footage",
        "reason": reason, "credit_lines": [], "subtitle_lines": subtitle_lines,
        "lines_bbox": lines_bbox, "sig": "", "_hash": fhash,
    }


# ── dedup: GÖRSEL-öncelikli (dHash) + TAM-İMZA VEYA-birleşimi sıralı kümeleme ──
#
# NEDEN görsel-öncelikli (sahada bulundu, ALİTA 2026-06-29): kalıcı bir kart OCR jitter'ı
# yüzünden her karede farklı okunur (CENTURY/CENTURV/CENTUR/CENTII...) → SALT metin-imzası
# dedup ÇÖKER (her kare ayrı imza). Kalıcı kart GÖRSEL olarak stabildir → dHash birleştirir.
# Footage-üstü stabil-metin (hareketli arka plan) ise dHash'i kaydırır ama metin sabit →
# TAM-İMZA birleştirir. Kayan jenerik (metin hareketli) → ikisi de değişir → hepsi TUTULUR.
# Gerçek farklı isimleri kaybetmemek için FUZZY eşleşme YOK (recall > mükemmel dedup).
# Anchor-relatif (küme ilk karesine kıyas): yavaş kayma farklı kartları zincirlemesin.
def _dedup_kept(kept: list[dict], src_paths: dict, params: dict) -> None:
    """kept (frame_index sırasında) üzerinde sıralı dedup; her satıra
    dedup_representative:bool + dedup_cluster_sig + dedup_cluster_id yaz."""
    ham_thr = params["DEDUP_HAM"]

    for e in kept:
        e["dedup_representative"] = False

    # frame_index None olabilir (dosya adında rakam yok) → None'ları sona koy, çökmeden (TypeError guard).
    ordered = sorted(kept, key=lambda e: (e.get("frame_index") is None, e.get("frame_index") or 0))

    clusters: list[dict] = []   # {anchor_hash, anchor_sig, members:[entry,...]}
    for e in ordered:
        h = e.get("_hash")
        sig = e.get("sig") or ""
        joined = False
        if clusters:
            last = clusters[-1]
            ah = last["anchor_hash"]
            asig = last["anchor_sig"]
            visual_match = (h is not None and ah is not None and _hamming(h, ah) <= ham_thr)
            sig_match = (sig != "" and sig == asig)
            if visual_match or sig_match:
                last["members"].append(e)
                joined = True
        if not joined:
            clusters.append({"anchor_hash": h, "anchor_sig": sig, "members": [e]})

    # küme başına TEK temsilci = ortadaki üye (fade-in/out kenar karelerini değil, oturmuş kartı seç).
    for cid, cl in enumerate(clusters):
        members = cl["members"]
        rep = members[len(members) // 2]
        for e in members:
            e["dedup_representative"] = (e is rep)
            e["dedup_cluster_id"] = cid
            e["dedup_cluster_sig"] = cl["anchor_sig"]


# ── tek dizin işle ─────────────────────────────────────────────────────────────
def _safe_clear_own_dir(d: Path) -> None:
    """SADECE bu aracın KENDİ çıktı klasörünü (giris_yazi / giris_yazi_dedup) temizle —
    idempotent yeniden-koşum için. Adı doğrula; başka hiçbir klasöre dokunma."""
    if d.name not in (POOL_DIRNAME, DEDUP_DIRNAME):
        raise RuntimeError(f"GÜVENLİK: araç-dışı klasör temizlenmeye çalışıldı: {d}")
    if d.exists():
        for p in d.iterdir():
            if p.is_file() and p.suffix.lower() == ".png":
                try:
                    p.unlink()
                except Exception:
                    pass


def process_giris(frames_dir: Path, dump_dir: Path | None = None) -> dict:
    """frames/giris dizinini işle → manifest dict döndür (+ disk'e yaz)."""
    import time as _time
    t0 = _time.perf_counter()
    params = _get_params()

    frames_dir = Path(frames_dir)
    film_dir = frames_dir.parent.parent       # Database/<film>/frames/giris → Database/<film>
    frames_parent = frames_dir.parent         # Database/<film>/frames
    pool_dir = frames_parent / POOL_DIRNAME
    dedup_dir = frames_parent / DEDUP_DIRNAME
    manifest_path = frames_parent / MANIFEST_NAME

    def _base_manifest(status: str, extra: dict | None = None) -> dict:
        m = {
            "film": film_dir.name,
            "tool_version": TOOL_VERSION,
            "ts": datetime.now().isoformat(timespec="seconds"),
            "frames_dir": str(frames_dir),
            "engine": "oneocr",
            "engine_error": None,
            "status": status,
            "params": params,
            "total_input_frames": 0,
            "total_kept": 0,
            "total_dropped_footage": 0,
            "total_dedup_representatives": 0,
            "pool_dir": str(pool_dir),
            "secs": round(_time.perf_counter() - t0, 3),
            "frames": [],
        }
        if extra:
            m.update(extra)
        return m

    if not frames_dir.exists():
        return _base_manifest("empty_giris", {"engine": "yok"})

    paths = list_images(frames_dir)
    if params["SCAN_CAP"] and params["SCAN_CAP"] > 0:
        paths = paths[: params["SCAN_CAP"]]
    if not paths:
        return _base_manifest("empty_giris", {"engine": "yok"})

    eng, kind, err = _get_engine()
    if eng is None:
        # OneOCR yok → paddle'a DÜŞME; net hata, sıfır kopya.
        return _base_manifest("engine_error", {"engine": "yok", "engine_error": err,
                                               "total_input_frames": len(paths)})

    # ── her kareyi sınıflandır ──
    rows: list[dict] = []
    for path in paths:
        try:
            rows.append(_classify_frame(path, eng, params))
        except Exception as exc:  # noqa: BLE001 — kare-bazlı hata asla çökme; RECALL
            rows.append({
                "file": path.name, "frame_index": natural_frame_no(path),
                "decision": "kept_error", "reason": "ocr_error_kept",
                "credit_lines": [], "subtitle_lines": [], "lines_bbox": [],
                "sig": "", "_err": f"{type(exc).__name__}: {exc}",
            })

    kept = [r for r in rows if r["decision"] in ("kept", "kept_error")]
    src_paths = {p.name: p for p in paths}

    # ── dedup ──
    _dedup_kept(kept, src_paths, params)

    # ── disk: havuz = DOĞRUDAN AZALTILMIŞ SET (Çağatay 2026-06-29) ──
    # giris_jenerik = yazı-var kareler ∩ benzer-silinmiş (yalnız dedup TEMSİLCİLERİ).
    # Kayan jenerik korunur (fuzzy-birleştirme yok → kayan kareler ayrı küme = hepsi temsilci).
    # Ayrı _dedup klasörü ARTIK YOK; varsa eski (obsolete) silinir.
    pool_dir.mkdir(parents=True, exist_ok=True)
    _safe_clear_own_dir(pool_dir)
    if dedup_dir.exists():                      # eski iki-klasör düzeninden kalan _dedup'ı temizle
        _safe_clear_own_dir(dedup_dir)
        try:
            dedup_dir.rmdir()
        except Exception:
            pass

    for r in kept:
        r["dedup_file"] = None
        if not r.get("dedup_representative"):
            r["pool_file"] = None              # benzer-kopya → havuza GİRMEZ (silindi)
            continue
        src = src_paths[r["file"]]
        dst = pool_dir / r["file"]
        try:
            shutil.copy2(src, dst)
            r["pool_file"] = f"{POOL_DIRNAME}/{r['file']}"   # havuzdaki azaltılmış temsilci
        except Exception as exc:  # noqa: BLE001
            r["pool_file"] = None
            r["_copy_err"] = f"{type(exc).__name__}: {exc}"

    n_kept = len(kept)                                            # yazı-var kare sayısı (azaltma öncesi)
    n_drop = sum(1 for r in rows if r["decision"] == "dropped_footage")
    n_reps = sum(1 for r in kept if r.get("dedup_representative"))  # = havuzdaki kare (azaltma sonrası)

    # iç görsel-imza (büyük int) manifest'e yazılmaz.
    for r in rows:
        r.pop("_hash", None)

    manifest = _base_manifest("ok", {
        "total_input_frames": len(paths),
        "total_kept": n_kept,
        "total_dropped_footage": n_drop,
        "total_dedup_representatives": n_reps,
        "frames": rows,
    })
    manifest["secs"] = round(_time.perf_counter() - t0, 3)

    # manifest yaz (film klasörü + opsiyonel dump-dir).
    try:
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as exc:  # noqa: BLE001
        print(f"[giris_yazi] manifest yazılamadı: {type(exc).__name__}: {exc}", file=sys.stderr)
    if dump_dir is not None:
        try:
            dump_dir.mkdir(parents=True, exist_ok=True)
            safe = "".join(ch if ch.isalnum() else "_" for ch in film_dir.name)[:64]
            (dump_dir / f"{safe}.json").write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except Exception:
            pass

    return manifest


# ── CLI çoklu-koşum yardımcıları ───────────────────────────────────────────────
def _summary(manifest: dict) -> dict:
    """stdout için kısa tek-satır özet (tam manifest diske yazıldı)."""
    return {
        "film": manifest.get("film"),
        "status": manifest.get("status"),
        "engine": manifest.get("engine"),
        "engine_error": manifest.get("engine_error"),
        "total_input_frames": manifest.get("total_input_frames"),
        "total_kept": manifest.get("total_kept"),
        "total_dropped_footage": manifest.get("total_dropped_footage"),
        "total_dedup_representatives": manifest.get("total_dedup_representatives"),
        "secs": manifest.get("secs"),
    }


def _process_film_name(film_name: str, dump_dir: Path | None = None) -> dict:
    giris = PROJECT_ROOT / "Database" / film_name / "frames" / "giris"
    try:
        m = process_giris(giris, dump_dir=dump_dir)
    except Exception as exc:  # noqa: BLE001
        m = {"film": film_name, "frames_dir": str(giris), "status": "error",
             "error": f"{type(exc).__name__}: {exc}", "traceback": traceback.format_exc()}
    m.setdefault("film", film_name)
    return m


def _process_frames_dir(frames_dir_str: str, dump_dir: Path | None = None) -> dict:
    try:
        return process_giris(Path(frames_dir_str), dump_dir=dump_dir)
    except Exception as exc:  # noqa: BLE001
        return {"frames_dir": frames_dir_str, "status": "error",
                "error": f"{type(exc).__name__}: {exc}", "traceback": traceback.format_exc()}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="GİRİŞ jeneriği yazı-havuzu (yazı-varlığı seçimi + aynı-yazı dedup).")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--film", help="Film adı (→ Database/<ad>/frames/giris)")
    g.add_argument("--frames", help="frames/giris dizini yolu")
    g.add_argument("--batch", help="Satır başına bir film adı içeren dosya")
    ap.add_argument("--dump-dir", help="Manifest'i ayrıca buraya <safe_film>.json yaz")
    ap.add_argument("--pool-name", default="giris_jenerik",
                    help="Havuz klasör adı (default giris_jenerik). cikis yedek için 'cikis_yazi'. "
                         "--frames ile birlikte herhangi bir kare dizinine uygulanabilir.")
    args = ap.parse_args(argv)
    dump_dir = Path(args.dump_dir) if args.dump_dir else None

    # Havuz adını override et (cikis_yazi yedek havuzu için yeniden-kullanım). Globaller derive edilir;
    # _safe_clear_own_dir guard'ı da bu adlara göre çalışır (araç-dışı klasör temizlenemez).
    global POOL_DIRNAME, DEDUP_DIRNAME, MANIFEST_NAME
    if args.pool_name and args.pool_name != POOL_DIRNAME:
        POOL_DIRNAME = args.pool_name
        DEDUP_DIRNAME = args.pool_name + "_dedup"
        MANIFEST_NAME = args.pool_name + "_manifest.json"

    if args.film:
        m = _process_film_name(args.film, dump_dir=dump_dir)
        print(json.dumps(_summary(m) if "status" in m and m.get("status") != "error" else m, ensure_ascii=False))
    elif args.frames:
        m = _process_frames_dir(args.frames, dump_dir=dump_dir)
        print(json.dumps(_summary(m) if m.get("status") not in (None, "error") else m, ensure_ascii=False))
    elif args.batch:
        names = [ln.strip() for ln in Path(args.batch).read_text(encoding="utf-8").splitlines() if ln.strip()]
        for name in names:
            try:
                m = _process_film_name(name, dump_dir=dump_dir)
                out = _summary(m) if m.get("status") not in (None, "error") else m
            except Exception as exc:  # noqa: BLE001 — batch asla çökmesin
                out = {"film": name, "status": "error", "error": f"{type(exc).__name__}: {exc}"}
            print(json.dumps(out, ensure_ascii=False), flush=True)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
