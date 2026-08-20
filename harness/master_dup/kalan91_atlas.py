#!/usr/bin/env python3
"""Kalan-91 taze atlası (Görev M9, docs/MITAS_Master_Dup_Kok_Sebep_Plani_v1.md
M7/M8 takibi). SALT-ANALİZ -- hiçbir üretim/composer/harness-ölçüm dosyası
BURADAN değiştirilmez; yalnız data/master_ex/*'i (manifest.json/metrik.json/
reading_master.png, zaten üretilmiş) okur + data/master_ex/_kalan91/ altına
tanık-kırpım PNG'leri yazar.

Amaç: `saglik.py`'nin `dup_oran_yuksek` ihlaliyle işaretlediği filmleri ESKİ
ex_dup_siniflandirma.md etiketlerine (135-havuz, K1/K3 fix'lerinden ÖNCE)
GÜVENMEDEN, güncel manifest+metrik kanıtıyla YENİDEN sınıflandırır:

  S1 -- kayan-liste pencere-örtüşmesi (slit/scroll kaynaklı, K2 alanı):
        metrik.json'un en büyük "es" (tekrar) bloğu manifest'te kind=
        "scroll_slit" olan bir kept-bloğa düşüyor.
  S2 -- gerçek özdeş içerik ama rec-eşitliği hiç ONAYLANAMAMIŞ: iki taraf da
        kind="static_page" VE bu filmde distant-dup* (F1/F1b/F1c) türünden
        HİÇBİR skip izi yok -- aday hiç ateşlenmemiş (H2/F1b kapsam sorunu).
  S3 -- muhtemelen meşru-farklı-metin ama K3/F1c kanıt-şartına (rec_kanit,
        conf<0.7 vb.) takılmış: iki taraf da static_page VE filmde rec_kanit
        (F1c makinesi ateşlenmiş) izi VAR -- ama bu ÖZEL çift skip edilmemiş.
  S4 -- diğer/belirsiz (çok az kept-blok / boy-kaynaklı / metrik-FP şüphesi).

Otomatik sinyal TÜM 91 için çıkarılır (bu script); görsel doğrulama (25
örneklem) ayrı bir adım -- bu script witness PNG'lerini üretir, YORUMU
orkestratör/Sonnet Read ile yapar (görsel-yorumlama kod-dışı).

CLI:
  kalan91_atlas.py --dup-json <sagliksiz_liste.json> --out cikti.json
                    --witness-n 25 --witness-dir data/master_ex/_kalan91
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import random
import sys
from pathlib import Path

import numpy as np
from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MASTER_EX = PROJECT_ROOT / "data" / "master_ex"
HERE = Path(__file__).resolve().parent

sys.path.insert(0, str(HERE))
import uret  # noqa: E402  -- build_args/_monitor/_dc (SALT-OKUNUR erişim, saglik.py ile aynı desen)

DISTANT_DUP_TYPES = ("distant-dup", "distant-dup-text", "distant-dup-scene", "distant-dup-rec")


def _load_json(path: Path) -> dict | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def kept_block_ranges(manifest: dict, sep_px: int) -> list[dict]:
    """Kept (skip'siz) bloklar için kümülatif y-aralığı + kind + src + orijinal
    manifest-indeksi (skip_audit._kept_block_index_map ile AYNI sayaç kuralı:
    yalnız 'h' VE 'skip' yok olan girdiler sayılır)."""
    y = 0
    out = []
    idx = 0
    for b in manifest.get("blocks") or []:
        if not isinstance(b, dict) or "skip" in b or b.get("h") is None:
            continue
        h = int(b["h"])
        out.append({"idx": idx, "y0": y, "y1": y + h, "h": h,
                    "kind": b.get("kind"), "src": b.get("src")})
        y += h + sep_px
        idx += 1
    return out


def which_kept_block(y: float, ranges: list[dict]) -> dict | None:
    for r in ranges:
        if r["y0"] <= y < r["y1"]:
            return r
    if not ranges:
        return None
    return min(ranges, key=lambda r: min(abs(r["y0"] - y), abs(r["y1"] - y)))


def has_any_skip_trace(manifest: dict) -> bool:
    return any(
        isinstance(b, dict) and b.get("skip") in DISTANT_DUP_TYPES
        for b in manifest.get("blocks") or []
    )


def has_rec_machinery_trace(manifest: dict) -> bool:
    return any(isinstance(b, dict) and b.get("rec_kanit") for b in manifest.get("blocks") or [])


def top_dup_blocks(metrik: dict, n: int = 5) -> list[dict]:
    """Yalnız TANIK-KIRPIMI seçimi için (ex_dup_siniflandirma.md yöntemiyle
    TUTARLI): benzerlik + alan ağırlıklı en büyük tekrar blokları. Sınıflandırma
    KARARI artık bu fonksiyonu KULLANMIYOR (bkz. `kind_area_fractions` -- tüm
    bloklar üzerinden piksel-kapsama ağırlıklı, tekil-blok seçiminin gözden
    kaçırdığı S1/S2 karışık filmleri doğru bölüştürür)."""
    bloklar = metrik.get("bloklar") or []

    def score(b):
        area = max(0, b.get("y2", 0) - b.get("y1", 0))
        return b.get("benzerlik", 0.0) * 0.4 + min(area, 2000) / 2000.0 * 0.6

    return sorted(bloklar, key=score, reverse=True)[:n]


def kind_area_fractions(metrik: dict, ranges: list[dict]) -> dict:
    """TÜM metrik.bloklar üzerinden (yalnız en büyük 5 değil) piksel-kapsama
    ağırlıklı kind dağılımı: "es" (yalnız tekrar/sonraki taraf, dup_metrik'in
    kendi muhasebesiyle TUTARLI) y-aralığı hangi kept-bloğun (static_page/
    scroll_slit) üstüne düşüyorsa o kind'e 1 satır-piksel yazılır (aynı y iki
    kez sayılmaz -- boolean OR ile kapsama). Bu, tek-en-büyük-blok seçiminin
    kaçırdığı KARIŞIK (hem slit hem static tekrarı olan) filmlerde S1 payını
    gizlemez.

    KENDİNE-EŞLEŞME AYRIMI (görsel örneklem bulgusu, tarzan-kaciyor): bazı
    "tekrar" blokları AYNI kept-bloğun (src_idx==es_idx) İÇİNDE, kaydırılmış
    bir ofsette kendisiyle eşleşiyor -- composer'ın H2 uzak-kart gardının
    kapsamı DIŞINDA (kart-arası değil, kart-İÇİ) bir durum; görsel doğrulamada
    bu türden bir örnek FARKLI metin içeriyordu (dup_metrik'in tekrarlayan
    yerleşim/alt-çizgi deseni üzerinde YANLIŞ-POZİTİFİ). Bu yüzden "cross"
    (src_idx!=es_idx, gerçek kart-arası tekrar -- H2/F1c'nin hedef aldığı alan)
    ile "self" (aynı blok içi, muhtemelen metrik-YP) ayrı raporlanır;
    SINIFLANDIRMA yalnız "cross" kapsamasına göre yapılır."""
    boy = metrik.get("boy") or [0, 0]
    h = int(boy[1]) if len(boy) == 2 else 0
    if h <= 0 or not ranges:
        return {"static": 0, "slit": 0, "other": 0, "total": 0, "self": 0, "cross": 0}
    kind_at_y = np.zeros(h, dtype=np.uint8)  # 0=gap/none, 1=static_page, 2=scroll_slit, 3=diğer
    idx_at_y = np.full(h, -1, dtype=np.int32)
    for r in ranges:
        code = 1 if r["kind"] == "static_page" else (2 if r["kind"] == "scroll_slit" else 3)
        y0, y1 = max(0, r["y0"]), min(h, r["y1"])
        if y1 > y0:
            kind_at_y[y0:y1] = code
            idx_at_y[y0:y1] = r["idx"]
    covered = np.zeros(h, dtype=bool)
    self_covered = np.zeros(h, dtype=bool)
    for b in metrik.get("bloklar") or []:
        if b.get("korunan_disi_birakildi"):
            continue  # K3: protected-çift muafiyeti -- dup_oran hesabına zaten girmiyor
        y0, y1 = int(b.get("es_y1", 0)), int(b.get("es_y2", 0))
        y0, y1 = max(0, y0), min(h, y1)
        if y1 <= y0:
            continue
        covered[y0:y1] = True
        src_r = which_kept_block((b.get("y1", 0) + b.get("y2", 0)) / 2.0, ranges)
        es_r = which_kept_block((b.get("es_y1", 0) + b.get("es_y2", 0)) / 2.0, ranges)
        if src_r and es_r and src_r["idx"] == es_r["idx"]:
            self_covered[y0:y1] = True
    total = int(covered.sum())
    if total == 0:
        return {"static": 0, "slit": 0, "other": 0, "total": 0, "self": 0, "cross": 0}
    cross_mask = covered & ~self_covered
    static_n = int(((kind_at_y == 1) & cross_mask).sum())
    slit_n = int(((kind_at_y == 2) & cross_mask).sum())
    self_n = int(self_covered.sum())
    cross_n = int(cross_mask.sum())
    other_n = cross_n - static_n - slit_n
    return {"static": static_n, "slit": slit_n, "other": other_n, "total": total,
            "self": self_n, "cross": cross_n}


def classify_film(slug: str, sep_px: int) -> dict:
    fdir = MASTER_EX / slug
    manifest = _load_json(fdir / "manifest.json") or {}
    metrik = _load_json(fdir / "metrik.json") or {}
    ranges = kept_block_ranges(manifest, sep_px)
    dups = top_dup_blocks(metrik, n=5)  # yalnız witness-kırpımı/örnek-çift raporlama için

    skip_trace = has_any_skip_trace(manifest)
    rec_trace = has_rec_machinery_trace(manifest)
    fractions = kind_area_fractions(metrik, ranges)

    pairs = []
    for d in dups:
        src_r = which_kept_block((d.get("y1", 0) + d.get("y2", 0)) / 2.0, ranges)
        es_r = which_kept_block((d.get("es_y1", 0) + d.get("es_y2", 0)) / 2.0, ranges)
        if not src_r or not es_r:
            continue
        pairs.append({
            "src_idx": src_r["idx"], "es_idx": es_r["idx"],
            "src_kind": src_r["kind"], "es_kind": es_r["kind"],
            "src_src": src_r["src"], "es_src": es_r["src"],
            "benzerlik": d.get("benzerlik"),
            "y1": d.get("y1"), "y2": d.get("y2"),
            "es_y1": d.get("es_y1"), "es_y2": d.get("es_y2"),
        })

    kept_n = len(ranges)
    total = fractions["total"]
    cross = fractions["cross"]
    self_n = fractions["self"]
    self_frac_of_total = (self_n / total) if total else 0.0
    # SINIFLANDIRMA yalnız CROSS (kart-arası) kapsama üzerinden -- self
    # (aynı-blok-içi, metrik-YP şüpheli) payı sınıfı SAPTIRMASIN.
    slit_frac = fractions["slit"] / cross if cross else 0.0
    static_frac = fractions["static"] / cross if cross else 0.0

    # S1: tekrarın YARISINDAN FAZLASI (veya statik-payından açıkça baskın)
    # scroll_slit kind'li bloklara düşüyor -- kayan-liste/pencere-örtüşmesi
    # asıl kaynak. S1/S2-S3 KARIŞIK olabilir (bir filmde her ikisi de olabilir)
    # -- burada BASKIN (>%50 piksel-kapsama) sınıf raporlanır, gerçek dağılım
    # `fractions` alanında saklı kalır (rapor tablosunda "karışık" olarak ayrıca
    # sayılabilir).
    if cross == 0:
        if total > 0 and self_frac_of_total >= 0.9:
            sinif = "S4-kendine-eslesme"
            gerekce = (f"tekrar-kapsamasının %{self_frac_of_total*100:.0f}'i AYNI kept-bloğun kendisiyle "
                       "eşleşmesi (src_idx==es_idx) -- kart-arası değil, muhtemelen dup_metrik'in tekrarlayan "
                       "yerleşim/alt-çizgi deseni üzerindeki YANLIŞ-POZİTİFİ (görsel örneklemde tarzan-kaciyor "
                       "bunun FARKLI metin içerdiğini doğruladı)")
        elif kept_n <= 2:
            sinif, gerekce = "S4-az-blok", f"kept_blocks={kept_n} -- çok az blok, tekrar kapsaması ölçülemedi (muhtemelen metrik-FP/boy-kaynaklı)"
        else:
            sinif, gerekce = "S4", "dup_oran eşik-üstü ama es-blokların hiçbiri kept-aralığıyla eşleşmedi (kırık indeksleme/boy-anomalisi şüphesi)"
    elif slit_frac >= 0.5:
        sinif = "S1"
        gerekce = f"kart-arası tekrar-kapsamasının %{slit_frac*100:.0f}'i scroll_slit bloklara düşüyor (pencere/kayma örtüşmesi, K2 alanı)"
    elif static_frac > 0:
        if rec_trace:
            sinif = "S3"
            gerekce = f"kart-arası tekrar-kapsamasının %{static_frac*100:.0f}'i static_page VE filmde F1c rec-hakemi (rec_kanit) izi var -- kanıt-şartına takılmış olabilir"
        elif skip_trace:
            sinif = "S3b"
            gerekce = f"kart-arası tekrar-kapsamasının %{static_frac*100:.0f}'i static_page VE filmde F1/F1b skip izi var (rec_kanit yok) -- piksel/kutu kapısına takılmış olabilir"
        else:
            sinif = "S2"
            gerekce = f"kart-arası tekrar-kapsamasının %{static_frac*100:.0f}'i static_page VE filmde HİÇBİR distant-dup* izi yok -- aday hiç ateşlenmemiş"
    else:
        sinif = "S4"
        gerekce = "kart-arası tekrar kapsaması ne static_page ne scroll_slit'e baskın düşüyor -- belirsiz"

    return {
        "film": slug,
        "sinif": sinif,
        "gerekce": gerekce,
        "kept_blocks": kept_n,
        "dup_oran": (metrik or {}).get("dup_oran"),
        "kind_fractions": {"static_frac": round(static_frac, 3), "slit_frac": round(slit_frac, 3),
                           "other_frac": round(1 - static_frac - slit_frac, 3) if cross else 0.0,
                           "self_frac_of_total": round(self_frac_of_total, 3),
                           "karisik": bool(cross and min(static_frac, slit_frac) >= 0.2)},
        "skip_trace_var": skip_trace,
        "rec_trace_var": rec_trace,
        "pairs": pairs,
    }


# --------------------------------------------------------------------------- #
# Tanık kırpımı (kaynak/tekrar yan yana PNG) -- ex_dup_siniflandirma.md
# yöntemiyle TUTARLI: reading_master.png'den en büyük dup-blok y-aralığı +
# eş y-aralığı kırpılıp yan yana birleştirilir.
# --------------------------------------------------------------------------- #
def witness_crop(slug: str, out_dir: Path, sep_px: int, pad: int = 12) -> str | None:
    fdir = MASTER_EX / slug
    manifest = _load_json(fdir / "manifest.json") or {}
    metrik = _load_json(fdir / "metrik.json") or {}
    png_path = fdir / "reading_master.png"
    if not png_path.is_file():
        return None
    ranges = kept_block_ranges(manifest, sep_px)
    dups = top_dup_blocks(metrik, n=10)
    if not dups:
        return None
    # CROSS-blok (src_idx != es_idx) tercih edilir -- kendine-eşleşen (aynı
    # blok içi, muhtemelen metrik-YP) adaylar witness için YANILTICI (bkz.
    # tarzan-kaciyor görsel bulgusu); yalnız cross yoksa self'e düşülür.
    d = None
    for cand in dups:
        src_r = which_kept_block((cand.get("y1", 0) + cand.get("y2", 0)) / 2.0, ranges)
        es_r = which_kept_block((cand.get("es_y1", 0) + cand.get("es_y2", 0)) / 2.0, ranges)
        if src_r and es_r and src_r["idx"] != es_r["idx"]:
            d = cand
            break
    if d is None:
        d = dups[0]
    im = np.array(Image.open(png_path).convert("RGB"))
    h, w = im.shape[:2]

    def crop(y1, y2):
        y1c = max(0, int(y1) - pad)
        y2c = min(h, int(y2) + pad)
        if y2c <= y1c:
            return None
        return im[y1c:y2c, :]

    a = crop(d.get("y1", 0), d.get("y2", 0))
    b = crop(d.get("es_y1", 0), d.get("es_y2", 0))
    if a is None or b is None:
        return None
    gap = np.full((a.shape[0] if a.shape[0] == b.shape[0] else max(a.shape[0], b.shape[0]), 16, 3), 255, dtype=np.uint8)
    th = max(a.shape[0], b.shape[0])

    def pad_h(arr):
        if arr.shape[0] == th:
            return arr
        extra = np.full((th - arr.shape[0], arr.shape[1], 3), 200, dtype=np.uint8)
        return np.vstack([arr, extra])

    combo = np.hstack([pad_h(a), gap, pad_h(b)])
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{slug}_witness.png"
    Image.fromarray(combo).save(out_path)
    return str(out_path)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dup-json", type=Path, required=True, help="sagliksiz (dup_oran_yuksek) film listesi JSON")
    ap.add_argument("--out", type=Path, default=None, help="sınıflandırma sonucu JSON")
    ap.add_argument("--witness-n", type=int, default=25)
    ap.add_argument("--witness-dir", type=Path, default=MASTER_EX / "_kalan91")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args(argv)

    dc = uret._dc()
    sep_px = dc.SEP_PX

    films = json.loads(args.dup_json.read_text(encoding="utf-8"))
    sonuclar = [classify_film(slug, sep_px) for slug in films]

    dagilim: dict[str, int] = {}
    for s in sonuclar:
        dagilim[s["sinif"]] = dagilim.get(s["sinif"], 0) + 1

    # Görsel örneklem: her sınıftan orantılı + en az birkaç tane, toplam witness_n
    random.seed(args.seed)
    by_sinif: dict[str, list[str]] = {}
    for s in sonuclar:
        by_sinif.setdefault(s["sinif"], []).append(s["film"])
    for lst in by_sinif.values():
        random.shuffle(lst)

    secim: list[str] = []
    siniflar = sorted(by_sinif.keys(), key=lambda k: -dagilim[k])
    quota = {k: max(1, round(args.witness_n * dagilim[k] / len(sonuclar))) for k in siniflar}
    for k in siniflar:
        secim.extend(by_sinif[k][: quota[k]])
    secim = secim[: args.witness_n]

    witness_paths = {}
    for slug in secim:
        p = witness_crop(slug, args.witness_dir, sep_px)
        if p:
            witness_paths[slug] = p

    out = {
        "n": len(sonuclar),
        "dagilim": dagilim,
        "witness_secilen": secim,
        "witness_yollari": witness_paths,
        "sonuclar": sonuclar,
    }
    print(f"n={len(sonuclar)}  dagilim={json.dumps(dagilim, ensure_ascii=False)}")
    print(f"witness: {len(witness_paths)} PNG -> {args.witness_dir}")
    if args.out:
        args.out.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"-> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
