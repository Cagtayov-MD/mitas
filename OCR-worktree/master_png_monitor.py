"""Master PNG monitör — production core'a DOKUNMAZ.
db_compose_master'ın compose fonksiyonlarını + 'master' dispatch'ini yeniden kullanır.

ÇIKTI (Çağatay 2026-06-29): master PNG'ler film KÖKÜNDE açıkta durur (alt-klasör YOK):
  Database/<film>/<TRT BAŞLIK> giris.png   ve   <TRT BAŞLIK> cikis.png
  Database/<film>/giris_reading_master_runaware.png (giriş paralel okuma master'ı)
  Database/<film>/reading_master_runaware.png       (çıkış paralel okuma master'ı)
KAYNAK: derlenmiş havuz tercih edilir — frames/giris_jenerik & frames/cikis_jenerik;
havuz klasörü yoksa (eski film) ham frames/giris & frames/cikis'e düşer. Havuz VARSA ve BOŞSA
(cold-open / yazı yok) master ÜRETİLMEZ (ham footage'a düşmez). Yeni master üretildiyse eski
master/ alt-klasörü SİLİNİR; üretilemediyse eski master/ KORUNUR ("kötü master yerine hiç").

  Tek film:   python master_png_monitor.py --once "<Database klasör adı VEYA tam yol>" [--base "<TRT BAŞLIK>"]
  Monitör:    python master_png_monitor.py            (Database'i izler, biten filmlere üretir)
"""
import sys, os, re, time, glob, json, types, shutil, importlib.util
from difflib import SequenceMatcher
from pathlib import Path

import numpy as np

_PR = os.environ.get("MITAS_PROJECT_ROOT", r"E:\MITAS")
sys.path.insert(0, str(Path(_PR) / "OCR-worktree"))
_spec = importlib.util.spec_from_file_location("dcmaster", str(Path(_PR) / "OCR-worktree" / "db_compose_master.py"))
dc = importlib.util.module_from_spec(_spec); sys.modules["dcmaster"] = dc; _spec.loader.exec_module(dc)

# GİRİŞ master motoru: crop-stack (Çağatay fikri 2026-06-29) — her kredi satırını kırp+alt alta diz,
# footage'sız temiz künye listesi. ÇIKIŞ slit-scan kalır. Yüklenemezse giriş eski slit'e düşer.
try:
    sys.path.insert(0, str(Path(_PR) / "scripts"))
    _cs_spec = importlib.util.spec_from_file_location("giris_cropstack", str(Path(_PR) / "scripts" / "giris_master_cropstack.py"))
    cs = importlib.util.module_from_spec(_cs_spec); sys.modules["giris_cropstack"] = cs
    _cs_spec.loader.exec_module(cs)
except Exception:
    cs = None

DB = Path(_PR) / "Database"
POLL_SEC = 60


# PROFİL AYRIM KİLİDİ (Çağatay 2026-07-11: "FİLM İÇİN AYRI DİZİ İÇİN AYRI PROFİL — %100").
# Hub adındaki TRT tip parseli hibrit-dy bayrağını ZORLAR — ortam değişkeni ne derse desin:
#   tip=1 (FİLM) → '0' (eski yol, bit-identik)   ·   tip=0 (DİZİ) → '1' (hibrit aktif)
# TRT kimliği yoksa (lab/test hub'ı) karar verilemez → mevcut değer korunur.
_TRT_TIP_RE = re.compile(r"\d{4}-\d{3,4}-(\d)-\d{3,4}-\d{2}-\d")


def _profil_dy_kilidi(film: Path) -> str:
    m = _TRT_TIP_RE.search(film.name)
    if m:
        dc.SLIT_DY_HYBRID = "0" if m.group(1) == "1" else "1"
    return dc.SLIT_DY_HYBRID


def make_args():
    """db_compose_master argparse defaultları (master modu)."""
    return types.SimpleNamespace(
        mode="master", seg=None, hash_names=False, overwrite=True, flat_out=None,
        deinterlace=False, no_card_split=False, card_same_thr=6, card_min_hold=5,
        reading_opening_frames=10, reading_card_min_hold=3, reading_opening_min_hold=2,
        reading_card_same_thr=7, reading_early_split_frames=45,
        polarity="auto", no_dedup=False, luma_key=False, text_only=False, debug=False,
        flip=False, tht=22, min_hold=5, cut_resp=0.05)


def _compose_seg(frames, args):
    """process_film 'master' dispatch replikası (slit kanonik + seçim)."""
    if not frames:
        return None, {"frames": 0}
    first = dc.first_readable(frames)
    if first is None:
        return None, {"frames": len(frames), "err": "no readable frame"}
    h, w = first.shape[:2]
    if args.deinterlace:
        h = dc.deinterlace(first).shape[0]
    p = dc.derive_params(h, w, args)
    runs = dc.split_runs(frames, p, args)
    s = sum(int(r[1]) - int(r[0]) + 1 for r in runs if r[2] == "S")
    r_ = sum(int(r[1]) - int(r[0]) + 1 for r in runs if r[2] == "R")
    scroll_frac = r_ / max(1, s + r_)
    slit_master, _, _ = dc.compose_slit(frames, p, args)
    canon, mode = dc.select_master(slit_master)  # mosaic retired 2026-06-28 (slit-only)
    return canon, {"frames": len(frames), "mode": mode, "scroll_frac": round(scroll_frac, 3),
                   "size": ([int(canon.shape[1]), int(canon.shape[0])] if canon is not None else None)}


def _compose_reading_seg(frames, args):
    """Kanonik master'a dokunmadan, kapsayıcı okuma master'ı üret."""
    if not frames:
        return None, {"frames": 0, "status": "no_frames"}
    first = dc.first_readable(frames)
    if first is None:
        return None, {"frames": len(frames), "status": "error", "err": "no readable frame"}
    h, w = first.shape[:2]
    if args.deinterlace:
        h = dc.deinterlace(first).shape[0]
    p = dc.derive_params(h, w, args)
    master, manifest, _ = dc.compose_reading_runaware(frames, p, args)
    info = {
        "frames": len(frames),
        "mode": manifest.get("mode", "reading_runaware"),
        "status": manifest.get("status"),
        "size": manifest.get("size"),
        "runs": manifest.get("runs"),
        "strict_scroll_frac": manifest.get("strict_scroll_frac"),
        "kept_blocks": manifest.get("kept_blocks"),
    }
    return master, info | {"manifest": manifest}


# --- adaptif_slit entegrasyonu (2026-07-29, Çağatay kararı) ----------------- #
# ÇIKIŞ okuma-master'ının BİRİNCİL kompozitörü artık harness/master_dup/adaptif_slit.
# Gerekçe (25-film 3-kollu kıyas, aynı filmler + aynı metrik): metin-recall
# adaptif 0.589 · V2 0.522 · V2-kapalı 0.457. Görsel QC'de adaptif, V2'nin
# kaçırdığı künye KUYRUĞUNU taşıyor (gercek-yalanlar: mcfadden/simulator/
# pennington token'ları adaptifte VAR, V2'de YOK) ve blokları tekrarlamıyor.
# V2 (compose_reading_runaware) YEDEK olarak durur — adaptif ÇÖKERSE ona düşülür.
# Çökme tanımı hayat-agaci vakasından: 113 kareden tek kart / 480px üretmişti.
# Sebebi kompozitör DEĞİL, OCR kapsaması: Farsça karelerde det 0-3 kutu buluyor
# (normal filmde 19-35), dolayısıyla kart-kimliği sinyalinin girdisi yok.
ADAPTIF_KOK = Path(_PR) / "harness" / "master_dup"
ADAPTIF_COKME_MIN_KARE = 20   # bu kadar KAREDEN tek kart çıkıyorsa çökmedir
_ADAPTIF_MOD = None


def _adaptif_acik() -> bool:
    return os.environ.get("MITAS_MASTER_ADAPTIF", "1").strip().lower() not in ("0", "false", "off", "no")


def _adaptif_modul():
    """Tembel import — hata YUTULMAZ, çağırana yükselir.
    (Yukarıdaki `cs` bloğunun çıplak `except: cs = None` deseni üretimde giriş
    master'ını sessizce mod değiştirmişti: korpusta 189 manifest cropstack,
    157 textset. Aynı hatayı burada tekrarlama — sebep log'a yazılır.)"""
    global _ADAPTIF_MOD
    if _ADAPTIF_MOD is None:
        if str(ADAPTIF_KOK) not in sys.path:
            sys.path.insert(0, str(ADAPTIF_KOK))
        import ibrahimovic as adaptif_slit
        _ADAPTIF_MOD = adaptif_slit
    return _ADAPTIF_MOD


def _adaptif_cokmus(manifest: dict, kare_sayisi: int, kare_h: int) -> bool:
    """Kart-kimliği körlüğü yüzünden master'ın tek karta çökmesi.
    KARE şartı, gerçekten kısa (az kareli) tek-kart jeneriklerini muaf tutar —
    örn. supheli-zafer 480px üretir ama kare sayısı düşüktür, çökme değildir."""
    if manifest.get("segment") != 1 or kare_sayisi < ADAPTIF_COKME_MIN_KARE:
        return False
    boy = (manifest.get("size") or [None, None])[1]
    return bool(boy) and kare_h > 0 and boy <= 2 * kare_h


def _compose_reading_seg_adaptif(frames):
    """Birincil kompozitör. Kapalı/başarısız/çökmüş → (None, sebep); çağıran V2'ye düşer."""
    if not _adaptif_acik():
        return None, {"adaptif": "kapali"}
    try:
        ad = _adaptif_modul()
        ims = [im for im in (dc.rd_cached(f) for f in frames) if im is not None]
        if len(ims) < 2:
            return None, {"adaptif": "kare_yok", "yuklenen": len(ims)}
        master, manifest = ad.compose_adaptif("uretim", ims=ims)
        if master is None:
            return None, {"adaptif": "cikti_yok", "durum": manifest.get("durum")}
        if _adaptif_cokmus(manifest, len(ims), ims[0].shape[0]):
            return None, {"adaptif": "cokme", "segment": manifest.get("segment"),
                          "size": manifest.get("size"), "kare": len(ims)}
        info = {
            "frames": len(ims),
            "mode": "adaptif_slit",
            "status": manifest.get("durum"),
            "size": manifest.get("size"),
            "kept_blocks": manifest.get("segment"),
            "olcum_yolu": manifest.get("olcum_yolu"),
        }
        return master, info | {"manifest": manifest}
    except Exception as exc:
        print(f"[adaptif] HATA -> V2 yedegine dusuluyor: {type(exc).__name__}: {exc}",
              file=sys.stderr, flush=True)
        return None, {"adaptif": "hata", "hata": f"{type(exc).__name__}: {exc}"}


def _semantic_giris_groups(film: Path, frames: list[str], *, min_frames: int = 2):
    """Manifest OCR imzalarıyla görsel olarak aynı yerleşimli farklı kartları ayır."""
    path = film / "frames" / "giris_jenerik_manifest.json"
    if not path.is_file():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []

    signatures = {
        str(row.get("file")): str(row.get("sig") or "").strip()
        for row in (payload.get("frames") or [])
        if str(row.get("decision") or "").startswith("kept") and row.get("file")
    }

    def normalize(text: str) -> str:
        return " ".join(
            "".join(ch.casefold() if ch.isalnum() else " " for ch in text).split()
        )

    def similar(first: str, second: str) -> bool:
        if not first or not second:
            return True
        if first in second or second in first:
            return True
        ratio = SequenceMatcher(None, first, second).ratio()
        left, right = set(first.split()), set(second.split())
        union = left | right
        jaccard = (len(left & right) / len(union)) if union else 1.0
        return ratio >= 0.68 or jaccard >= 0.6

    groups = []
    current = []
    current_sig = ""
    for frame in frames:
        sig = normalize(signatures.get(Path(frame).name, ""))
        if current and sig and current_sig and not similar(current_sig, sig):
            if len(current) >= min_frames:
                groups.append(current)
            current = []
            current_sig = ""
        current.append(frame)
        if sig:
            current_sig = sig
    if len(current) >= min_frames:
        groups.append(current)
    return groups


def _compose_giris_reading_seg(film: Path, frames: list[str], args):
    """Run-aware giriş master'ı; aynı yerleşimli kart kaybında OCR-imza kurtarması."""
    baseline, info = _compose_reading_seg(frames, args)
    manifest = info.get("manifest") or {}
    semantic_groups = _semantic_giris_groups(film, frames)
    baseline_blocks = int(info.get("kept_blocks") or 0)
    scroll_frac = float(info.get("strict_scroll_frac") or 0.0)
    if (
        baseline is None
        or scroll_frac >= 0.5
        or len(semantic_groups) <= baseline_blocks
    ):
        return baseline, info

    blocks = []
    group_manifest = []
    for group_index, group_frames in enumerate(semantic_groups):
        group_master, group_info = _compose_reading_seg(group_frames, args)
        if group_master is None:
            continue
        blocks.append(group_master)
        group_manifest.append({
            "group": group_index,
            "frames": len(group_frames),
            "src_first": Path(group_frames[0]).name,
            "src_last": Path(group_frames[-1]).name,
            "size": [int(group_master.shape[1]), int(group_master.shape[0])],
            "kept_blocks": group_info.get("kept_blocks"),
        })
    if len(blocks) <= baseline_blocks:
        return baseline, info

    max_width = max(block.shape[1] for block in blocks)
    normalized = [
        np.pad(block, ((0, 0), (0, max_width - block.shape[1]), (0, 0)))
        if block.shape[1] < max_width else block
        for block in blocks
    ]
    separator = np.zeros((2, max_width, 3), np.uint8)
    stacked = []
    for block in normalized:
        stacked.extend((block, separator))
    master = np.vstack(stacked[:-1])
    rescue_manifest = {
        "mode": "reading_runaware_semantic_rescue",
        "status": "OK",
        "frames": len(frames),
        "size": [int(master.shape[1]), int(master.shape[0])],
        "kept_blocks": sum(int(item.get("kept_blocks") or 0) for item in group_manifest),
        "strict_scroll_frac": scroll_frac,
        "semantic_groups": group_manifest,
        "baseline": {
            "mode": manifest.get("mode"),
            "size": manifest.get("size"),
            "kept_blocks": baseline_blocks,
        },
    }
    return master, {
        "frames": len(frames),
        "mode": rescue_manifest["mode"],
        "status": "OK",
        "size": rescue_manifest["size"],
        "runs": manifest.get("runs"),
        "strict_scroll_frac": scroll_frac,
        "kept_blocks": rescue_manifest["kept_blocks"],
        "manifest": rescue_manifest,
    }


def _delivery_base(film: Path, base_override: str | None = None) -> str:
    """Kök teslim ad-tabanı '<TRT> <BAŞLIK>' (master PNG'ler bununla adlandırılır).
    Öncelik: açık --base > kök *.pdf stem > kök *.txt (teknik/_ hariç) stem > klasör adı."""
    if base_override:
        return base_override.strip()
    pdfs = sorted(film.glob("*.pdf"))
    if pdfs:
        return pdfs[0].stem
    txts = [t for t in sorted(film.glob("*.txt"))
            if not t.stem.endswith("_teknik") and not t.name.startswith("_")]
    if txts:
        return txts[0].stem
    return film.name


def _textset_from_manifest(manifest: Path, raw: Path):
    """Azaltılmış havuz manifestinden TAM yazı-setini (kept kareler) ham frames/<seg>'ten derle.
    Slit-scan master YOĞUNLUK ister; azaltılmış set master'ı eksik üretir."""
    try:
        mj = json.loads(manifest.read_text(encoding="utf-8"))
        kept = [r.get("file") for r in (mj.get("frames") or [])
                if str(r.get("decision", "")).startswith("kept")]
        fs = [str(raw / f) for f in kept if f and (raw / f).exists()]
        return sorted(fs, key=dc.nat_sort_key) if fs else None
    except Exception:
        return None


def _seg_source(film: Path, seg: str):
    """(frames_listesi, kaynak_etiketi). Master kaynak seçimi (Çağatay 2026-06-29).

    YALNIZ derlenmiş jenerik havuzundan üret: giris_jenerik azaltılmış+manifestli → TAM yazı-seti
    (giris_textset); cikis_jenerik bütün-pencere+manifestsiz → doğrudan. Havuz BOŞ/yok → BOŞ liste
    (master ÜRETİLMEZ = "kötü master yerine hiç"). Ham frames'e VE çıkış-yedek havuzuna (cikis_yazi)
    DÜŞÜLMEZ: ham=footage-master, cikis_yazi=çıkış-sonu sahne-yazısı/epilog → ikisi de SAHTE master üretir
    (GLENN MILLER tabela / SOĞUK SUYA 'FIN' kanıtı, 2026-06-29). cikis_yazi yedek havuzu yalnız VL içindir."""
    raw = film / "frames" / seg
    pool = film / "frames" / f"{seg}_jenerik"
    pool_fs = sorted(glob.glob(str(pool / "*.png")), key=dc.nat_sort_key) if pool.is_dir() else []
    if not pool_fs:
        return [], seg
    # AŞAMA-2v2 (2026-07-17): çıkışta adaptif-yoğun KARDEŞ havuz varsa onu tercih et
    # (üretici: scripts/_jenerik_dense.py — 1.5fps'te scroll dy≈75px 'cut' sanılıp
    # smear/collapse üretiyordu). Dense yalnız havuz doluyken ve SCROLL ölçülünce var;
    # kill-switch MITAS_MASTER_DENSE=0 tercihi de kapatır → havuz davranışı birebir.
    if seg == "cikis" and os.environ.get("MITAS_MASTER_DENSE", "1").strip().lower() not in ("0", "false", "off", "no"):
        dense = film / "frames" / f"{seg}_jenerik_dense"
        if dense.is_dir():
            dense_fs = sorted(glob.glob(str(dense / "*.png")), key=dc.nat_sort_key)
            if len(dense_fs) >= 5:
                return dense_fs, f"{seg}_jenerik_dense"
    man = film / "frames" / f"{seg}_jenerik_manifest.json"
    if man.exists() and raw.is_dir():
        ts = _textset_from_manifest(man, raw)
        if ts:
            return ts, f"{seg}_textset"
    return pool_fs, f"{seg}_jenerik"


def gen_master(film: Path, base_override: str | None = None) -> dict:
    _profil_dy_kilidi(film)   # FİLM→hibrit-0 / DİZİ→hibrit-1 (profil ayrımı %100)
    base = _delivery_base(film, base_override)
    args = make_args()
    res = {"film": film.name, "base": base}
    produced = False

    # GİRİŞ: CROP-STACK (footage'sız temiz künye listesi). Kaynak: YALNIZ giris_jenerik havuzu
    # (azaltılmış yazı-kareleri). Havuz boş/yok → giriş master ÜRETİLMEZ; ham frames/giris'e
    # DÜŞÜLMEZ (ham=footage → SAHTE master). Çıkış _seg_source ile aynı "kötü master yerine hiç"
    # kuralı (2026-06-29). cs yüklenemediyse eski slit'e düş.
    giris_out = film / f"{base} giris.png"
    if cs is not None:
        gsrc = film / "frames" / "giris_jenerik"
        ginfo = {"source": "giris_cropstack", "status": "no_frames"}
        if gsrc.is_dir() and glob.glob(str(gsrc / "*.png")):
            try:
                r = cs.build(gsrc, giris_out)
                ginfo = {"source": "giris_cropstack", "status": r.get("status"),
                         "lines": r.get("lines"), "size": r.get("size")}
                if r.get("status") == "ok":
                    ginfo["path"] = str(giris_out)
                    produced = True
            except Exception as e:  # noqa: BLE001
                ginfo = {"source": "giris_cropstack", "status": "error", "error": f"{type(e).__name__}: {e}"}
        res["giris"] = ginfo
    else:
        frames, src = _seg_source(film, "giris")
        canon, info = _compose_seg(frames, args)
        info["source"] = src
        if canon is not None:
            dc.wr(giris_out, canon); info["path"] = str(giris_out); produced = True
        res["giris"] = info

    # ÇIKIŞ: slit-scan (mevcut, GOOD — DOKUNULMADI).
    frames, src = _seg_source(film, "cikis")
    canon, info = _compose_seg(frames, args)
    info["source"] = src
    if canon is not None:
        cout = film / f"{base} cikis.png"
        dc.wr(cout, canon)
        info["path"] = str(cout)
        produced = True
    res["cikis"] = info

    # PARALEL OKUMA MASTER'LARI: kanonik giris/cikis PNG'lerinin yerine geçmez;
    # aynı run-aware motorunu iki jenerik havuzunda da ayrı adlarla üretir.
    giris_reading = gen_reading_master(
        film, base_override, seg="giris"
    )["giris_reading_master_runaware"]
    cikis_reading = gen_reading_master(
        film, base_override, seg="cikis"
    )["reading_master_runaware"]
    res["giris_reading_master_runaware"] = giris_reading
    res["reading_master_runaware"] = cikis_reading

    res["produced"] = produced
    # provenance manifest (kökte, base adlı)
    try:
        (film / f"{base} master_manifest.json").write_text(
            json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    except Exception:
        pass
    # ESKİ master/ alt-klasörünü kaldır — YALNIZ yeni master üretildiyse ("kötü yerine hiç" korunur).
    if produced:
        old = film / "master"
        if old.is_dir():
            try:
                shutil.rmtree(old)
            except Exception:
                pass
    return res


def gen_reading_master(
    film: Path,
    base_override: str | None = None,
    *,
    seg: str = "cikis",
    write_manifest: bool = True,
) -> dict:
    if seg not in {"giris", "cikis"}:
        raise ValueError(f"unsupported reading-master segment: {seg!r}")
    _profil_dy_kilidi(film)   # FİLM→hibrit-0 / DİZİ→hibrit-1 (profil ayrımı %100)
    base = _delivery_base(film, base_override)
    args = make_args()
    frames, src = _seg_source(film, seg)
    if seg == "giris":
        # Giriş havuzu kart tabanlı ve seyrektir. Çıkıştaki 45-karelik koruma
        # sınırı burada geç kartları (örn. screenplay/director) aynı uzun statik
        # gruba yutup tek medoid karta indirebiliyor. Girişin tamamında yalnız
        # güçlü iç metin-yerleşimi sıçramalarında bölmeye izin ver.
        args.reading_early_split_frames = len(frames)
    key = "giris_reading_master_runaware" if seg == "giris" else "reading_master_runaware"
    stem = key
    out = film / f"{stem}.png"
    man_out = film / f"{stem}_manifest.json"
    if seg == "giris":
        master, info = _compose_giris_reading_seg(film, frames, args)
    else:
        # ÇIKIŞ: İBRAHİMOVİC tek motor (Çağatay 2026-07-30: "V2 artık gereksiz").
        # 40-film üçlü kıyas kanıtı: V2 ort. 0.469 (sonuncu, 2 filmde ~boş master).
        # Üretemezse YEDEK YOK — sebep manifest'e yazılır, eski dosya korunur
        # ("kötü master yerine hiç"). Not: GİRİŞ akışı bu karardan bağımsız.
        master, info = _compose_reading_seg_adaptif(frames)
        if master is None:
            info = {"status": "ibrahimovic_uretemedi", "mode": "ibrahimovic",
                    "frames": len(frames), "sebep": info}
    manifest = info.pop("manifest", None)
    info["source"] = src
    info["segment"] = seg
    info["base"] = base
    if master is not None:
        dc.wr(out, master)
        info["path"] = str(out)
    elif seg == "cikis" and info.get("status") == "ibrahimovic_uretemedi":
        pass   # V2-emeklilik: üretilemeyen turda ESKİ çıkış master'ı korunur
    elif out.exists():
        try:
            out.unlink()
        except Exception:
            pass
    if write_manifest:
        payload = manifest if isinstance(manifest, dict) else info
        try:
            man_out.write_text(json.dumps(payload | {"source": src, "base": base}, ensure_ascii=False, indent=1),
                               encoding="utf-8")
        except Exception:
            pass
    return {"film": film.name, "base": base, key: info}


def _has_frames(film: Path) -> bool:
    return bool(glob.glob(str(film / "frames" / "giris" / "*.png")) or
               glob.glob(str(film / "frames" / "cikis" / "*.png")))


def _ready(film: Path) -> bool:
    # kareler var + işleme ilerlemiş (ocr veya pdf çıktısı) -> kareler artık final
    return _has_frames(film) and ((film / "ocr").exists() or (film / "pdf").exists())


def _done(film: Path) -> bool:
    # kökte herhangi bir '<base> giris.png' / '<base> cikis.png' üretilmiş mi
    return bool(glob.glob(str(film / "* giris.png")) or glob.glob(str(film / "* cikis.png")))


def monitor():
    print(f"[master-monitor] başladı, {DB} izleniyor (poll {POLL_SEC}s). Ctrl-C ile dur.", flush=True)
    seen = set()
    while True:
        for film in sorted(DB.iterdir()):
            if not film.is_dir() or film.name in seen:
                continue
            if _done(film):
                seen.add(film.name)
                continue
            if _ready(film):
                try:
                    r = gen_master(film)
                    seen.add(film.name)
                    sz = {k: r[k].get("size") for k in ("giris", "cikis") if isinstance(r.get(k), dict)}
                    print(f"[master] OK {film.name} -> {sz}", flush=True)
                except Exception as e:
                    print(f"[master] HATA {film.name}: {repr(e)[:140]}", flush=True)
        time.sleep(POLL_SEC)


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    if len(sys.argv) > 2 and sys.argv[1] == "--once":
        # arg: tam yol VEYA Database altindaki klasor adi (pipeline tam clip_dir yolu gecer)
        _arg = sys.argv[2]
        _film = Path(_arg) if os.path.isabs(_arg) else (DB / _arg)
        _base = None
        if "--base" in sys.argv:
            try:
                _base = sys.argv[sys.argv.index("--base") + 1]
            except Exception:
                _base = None
        if "--reading-only" in sys.argv:
            _seg = "cikis"
            if "--seg" in sys.argv:
                try:
                    _seg = sys.argv[sys.argv.index("--seg") + 1]
                except Exception:
                    _seg = "cikis"
            print(json.dumps(
                gen_reading_master(_film, _base, seg=_seg),
                ensure_ascii=False,
                indent=1,
            ))
        else:
            print(json.dumps(gen_master(_film, _base), ensure_ascii=False, indent=1))
    else:
        monitor()
