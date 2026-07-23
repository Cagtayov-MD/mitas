#!/usr/bin/env python3
"""K1 kalibrasyonu (Görev M8, MITAS_Master_Dup_Kok_Sebep_Plani_v1.md).

Amaç: `ex_dup_siniflandirma.md`'deki A1 (statik-kart-tekrarı) filmlerinden
film-içi "aynı-kart" ve "farklı-kart" ÇİFTLERİNİ çıkarıp F1b'nin gri
bant-fark eşiklerini (F1B_GLOBAL_DIFF_GATE / F1B_BAND_DIFF_GATE) Ex-korpus
üzerinde YENİDEN KALİBRE etmek (F1>=0.95 hedefi, marjıyla raporlanır).

YÖNTEM (döngüsellikten kaçınmak için BAĞIMSIZ etiket kaynağı kullanılır --
piksel-farkını piksel-farkıyla etiketlemek veri sızıntısı olur):
  1. Her A1 filmi için manifest.json'daki KEPT (skip'siz) `kind=="static_page"`
     bloklarının TEMSİLCİ kaynak karesini ("src" alanı) `_prep()` ile (composer
     ile BİREBİR aynı önişleme -- db_compose_master.py'den SALT-OKUNUR import)
     yeniden oluşturur.
  2. Film-içi TÜM kart çiftleri için: gri bant-fark (`_f1b_gray_band_diff`),
     det-kutuları (`_f1b_det_boxes`, sayfa başına önbelleklenir), kutular
     eşleşiyorsa NCC (`_f1b_box_ncc`), eşleşmiyorsa/kutu-kapısı reddediyorsa
     REC (`_f1c_rec_text`) hesaplanır -- HEPSİ composer'ın F1b/F1c akışının
     birebir aynısı (SALT-OKUNUR import, kod tekrar YAZILMAZ).
  3. ETİKET (bağımsız oracle): REC metni doluysa (her iki kartta da >=1 gerçek
     kutu, conf>=0.6) -- normalize metin eşitse "ayni-kart", farklıysa
     "farkli-kart". Metin yoksa (iki kart da kutu bulunamadı/hayalet) etiket
     YOK -- bu çiftler ayrı bir "metinsiz" havuzunda toplanır, görsel
     doğrulama script'i (`--gorsel-ornek`) ile örneklem elle etiketlenir.
  4. `--esik-tara` ile global_fark eşiği üzerinde F1 taraması yapılır.

Çıktı: `data/master_dup/k1_kalibrasyon/ciftler.json` (ham çift listesi) +
konsolda etiket dağılımı + eşik-tarama tablosu.

CLI:
  kalibrasyon_k1.py --topla                 # tüm A1 filmlerini tara, ciftler.json yaz
  kalibrasyon_k1.py --esik-tara             # var olan ciftler.json'dan F1 eşik taraması
  kalibrasyon_k1.py --gorsel-ornek metinsiz --n 10   # metinsiz havuzdan görsel örnek kırpımı üret
"""
from __future__ import annotations

import argparse
import importlib.util
import itertools
import json
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
EX_FRAME_ROOT = Path("/home/cagatay/Ex_Frame")
EX_SUFFIX = "-exit_frames"
MASTER_EX_ROOT = PROJECT_ROOT / "data" / "master_ex"
OUT_DIR = PROJECT_ROOT / "data" / "master_dup" / "k1_kalibrasyon"
CIFTLER_PATH = OUT_DIR / "ciftler.json"

# ex_dup_siniflandirma.md "Film başına tek satır (30-örneklem)" tablosundaki
# Sınıf=A1 satırları (18 film) + "Ek çapraz-kontrol: imha-10" bölümünde A
# (statik-kart, scroll YOK) olarak görsel doğrulanan 4 film (sampiyon, duello,
# maudie, don-kisot). dogu-ekspresinde-cinayet KISMEN B-benzeri olduğu için
# (belirsiz, "net silinmiş örnek değil") kalibrasyon setine DAHIL EDİLMEDİ.
A1_FILMLER = [
    "hizli-silah", "boksorun-olumu", "affedilmeyenler", "kis-gelmeden",
    "ulysses-in-maceralari", "don-juan-in-maceralari", "muthis-gece",
    "genc-billy-young", "sevgili-james", "amelia-earhart",
    "aslan-yurekli-cavus", "ask-ruzgari", "secenekler", "hayat-bir-romandir",
    "hepsi-benim", "doberman-cetesi", "ask-sarkisi", "batiya-giden-yol",
    "sampiyon", "duello", "maudie", "don-kisot",
]

REC_CONF_ESIK = 0.6  # F1C_REC_CONF_GATE ile aynı (composer sabiti)


# --------------------------------------------------------------------------- #
# composer/uret zinciri (SALT-OKUNUR import)
# --------------------------------------------------------------------------- #
_URET_MOD = None


def _uret_mod():
    global _URET_MOD
    if _URET_MOD is None:
        uret_path = Path(__file__).resolve().parent / "uret.py"
        spec = importlib.util.spec_from_file_location("uret_core_k1kalib", str(uret_path))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _URET_MOD = mod
    return _URET_MOD


def _load_json(path: Path) -> dict | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _frames_for(slug: str) -> list[str]:
    d = EX_FRAME_ROOT / f"{slug}{EX_SUFFIX}"
    return sorted(str(p) for p in d.glob("exit_*.png"))


# --------------------------------------------------------------------------- #
# Film başına kart-çiftleri toplama
# --------------------------------------------------------------------------- #
def collect_film_pairs(slug: str) -> list[dict]:
    uret = _uret_mod()
    dc = uret._dc()
    manifest = _load_json(MASTER_EX_ROOT / slug / "manifest.json")
    if manifest is None:
        return []
    blocks = manifest.get("blocks") or []
    kept_static = [
        b for b in blocks
        if isinstance(b, dict) and b.get("kind") == "static_page" and "skip" not in b and b.get("src")
    ]
    if len(kept_static) < 2:
        return []
    # Maliyet sınırı (K1'in kendi "aday tavanı" mantığının kalibrasyon script'ine
    # yansıması): çok kartlı filmlerde (ör. uzun oyuncu listesi) C(n,2) patlamasını
    # sınırla -- büyük filmlerde bile temsilci bir örneklem yeterli, tüm korpus
    # zaten 22 filmden geliyor (≥50/≥50 hedefi için tek filmin domine etmesi
    # istenmiyor).
    KART_TAVANI = 25
    if len(kept_static) > KART_TAVANI:
        kept_static = kept_static[:KART_TAVANI]

    frames = _frames_for(slug)
    if not frames:
        return []
    frames_dir = EX_FRAME_ROOT / f"{slug}{EX_SUFFIX}"

    first = dc.first_readable(frames)
    if first is None:
        return []
    h, w = first.shape[:2]
    args = uret.build_args()
    if args.deinterlace:
        h = dc.deinterlace(first).shape[0]
    p = dc.derive_params(h, w, args)

    # Her kept-static kart için tam-kare gri (composer'daki full_gray ile BİREBİR).
    grays: dict[int, "object"] = {}
    for idx, b in enumerate(kept_static):
        frame_path = frames_dir / b["src"]
        if not frame_path.is_file():
            continue
        image = dc._prep(str(frame_path), p, args)
        if image is None:
            continue
        import cv2
        grays[idx] = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    boxes_cache: dict[int, list | None] = {}
    rec_cache: dict[int, list] = {}

    def boxes_for(idx: int):
        # RETRY (systematic-debugging bulgusu, bkz. saglik.py det_metin_var()
        # docstring'i): paylaşılan PaddleOCR det motoru ara sıra AYNI görüntüde
        # bile None dönüyor (sessizce yutulan istisna) -- 3 deneme, İLK başarı
        # kabul edilir (motor metni VARKEN kaçırıyor, YOKKEN uydurmuyor -- güvenli
        # yön). Kalibrasyon verisinin "metinsiz" havuzunu şişirmemesi için şart.
        if idx not in boxes_cache:
            boxes = None
            for _ in range(3):
                boxes = dc._f1b_det_boxes(grays[idx])
                if boxes:
                    break
            boxes_cache[idx] = boxes
        return boxes_cache[idx]

    def rec_for(idx: int, boxes_sorted: list):
        if idx not in rec_cache:
            rec_cache[idx] = dc._f1c_rec_boxes(grays[idx], boxes_sorted)
        return rec_cache[idx]

    pairs = []
    for i, j in itertools.combinations(sorted(grays.keys()), 2):
        gi, gj = grays[i], grays[j]
        if gi.shape != gj.shape:
            continue  # farklı boy -- composer'da da karşılaştırılmaz (shape guard)
        diff = dc._f1b_gray_band_diff(gi, gj)
        if diff is None:
            continue
        rec = {"global_fark": diff["global_fark"], "max_band_fark": diff["max_band_fark"],
               "response": diff["response"]}
        boxes_i, boxes_j = boxes_for(i), boxes_for(j)
        rec["det_kutu_i"] = len(boxes_i) if boxes_i is not None else None
        rec["det_kutu_j"] = len(boxes_j) if boxes_j is not None else None
        real_i, real_j = [], []
        ncc = None
        if boxes_i and boxes_j:
            if dc._f1b_boxes_match(boxes_i, boxes_j):
                ncc = dc._f1b_box_ncc(gi, gj, boxes_i, boxes_j)
            bi_sorted, bj_sorted = dc._f1b_boxes_sorted(boxes_i), dc._f1b_boxes_sorted(boxes_j)
            rec_i = rec_for(i, bi_sorted)
            rec_j = rec_for(j, bj_sorted)
            real_i = [norm for norm, score in rec_i if norm and score >= REC_CONF_ESIK]
            real_j = [norm for norm, score in rec_j if norm and score >= REC_CONF_ESIK]
        rec["ncc"] = ncc
        rec["metin_i"] = " ".join(real_i)
        rec["metin_j"] = " ".join(real_j)

        # ETİKET (bağımsız oracle -- REC metni, piksel-farkı DEĞİL).
        if real_i and real_j:
            etiket = "ayni-kart" if real_i == real_j else "farkli-kart"
        else:
            etiket = None  # metinsiz -- gorsel dogrulama havuzu
        rec.update({
            "film": slug, "i": i, "j": j,
            "src_i": kept_static[i]["src"], "src_j": kept_static[j]["src"],
            "etiket": etiket,
        })
        pairs.append(rec)
    return pairs


def topla(*, devam: bool = True) -> None:
    """Film film TOPLAR ve HER filmden sonra diske YAZAR (kısmi ilerleme
    güvenliği -- GPU çekişmesi/kesinti riskine karşı; --devam ile daha önce
    işlenmiş filmler ATLANIR, kaldığı yerden sürer)."""
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    all_pairs: list[dict] = []
    islenen: set[str] = set()
    if devam and CIFTLER_PATH.is_file():
        try:
            all_pairs = json.loads(CIFTLER_PATH.read_text(encoding="utf-8"))
            islenen = {x["film"] for x in all_pairs}
            print(f"[devam] {len(islenen)} film önceki koşudan yüklendi: {sorted(islenen)}", flush=True)
        except Exception:
            all_pairs = []

    for slug in A1_FILMLER:
        if slug in islenen:
            print(f"  [{slug}] atlandı (--devam, zaten işlenmiş)", flush=True)
            continue
        t0 = time.time()
        try:
            pairs = collect_film_pairs(slug)
        except Exception as exc:  # noqa: BLE001
            print(f"  [{slug}] HATA: {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
            continue
        print(f"  [{slug}] {len(pairs)} çift "
              f"(ayni={sum(1 for x in pairs if x['etiket']=='ayni-kart')}, "
              f"farkli={sum(1 for x in pairs if x['etiket']=='farkli-kart')}, "
              f"metinsiz={sum(1 for x in pairs if x['etiket'] is None)}) "
              f"[{time.time()-t0:.1f}s]", flush=True)
        all_pairs.extend(pairs)
        # HER FİLMDEN SONRA yaz -- kesinti/uzun-GPU-çekişmesi riskine karşı kısmi
        # ilerleme kaybolmasın (systematic-debugging bulgusu: paylaşılan GPU %90+
        # doluyken tek koşu çok yavaşlayabiliyor).
        CIFTLER_PATH.write_text(json.dumps(all_pairs, ensure_ascii=False, indent=1), encoding="utf-8")

    ayni = sum(1 for x in all_pairs if x["etiket"] == "ayni-kart")
    farkli = sum(1 for x in all_pairs if x["etiket"] == "farkli-kart")
    metinsiz = sum(1 for x in all_pairs if x["etiket"] is None)
    print(f"\nTOPLAM: {len(all_pairs)} çift -- ayni-kart={ayni} farkli-kart={farkli} metinsiz={metinsiz}", flush=True)
    print(f"-> {CIFTLER_PATH}", flush=True)


# --------------------------------------------------------------------------- #
# Eşik taraması
# --------------------------------------------------------------------------- #
def f1_score(pairs: list[dict], global_esik: float, band_esik: float) -> dict:
    """'aday' (skip önerisi) = global_fark<global_esik VE max_band_fark<band_esik.
    Pozitif sınıf = ayni-kart (skip DOĞRU olurdu). TP/FP/FN hesaplanır."""
    tp = fp = fn = tn = 0
    for x in pairs:
        etiket = x["etiket"]
        if etiket is None:
            continue
        aday = x["global_fark"] < global_esik and x["max_band_fark"] < band_esik
        if etiket == "ayni-kart":
            if aday:
                tp += 1
            else:
                fn += 1
        else:
            if aday:
                fp += 1
            else:
                tn += 1
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return {"global_esik": global_esik, "band_esik": band_esik, "tp": tp, "fp": fp,
            "fn": fn, "tn": tn, "precision": round(precision, 4), "recall": round(recall, 4),
            "f1": round(f1, 4)}


def esik_tara() -> None:
    pairs = json.loads(CIFTLER_PATH.read_text(encoding="utf-8"))
    labeled = [x for x in pairs if x["etiket"] is not None]
    print(f"Etiketli çift sayısı: {len(labeled)} "
          f"(ayni={sum(1 for x in labeled if x['etiket']=='ayni-kart')}, "
          f"farkli={sum(1 for x in labeled if x['etiket']=='farkli-kart')})")

    global_vals = sorted({round(x["global_fark"], 4) for x in labeled})
    band_vals = sorted({round(x["max_band_fark"], 4) for x in labeled})
    best = None
    sonuclar = []
    for ge in global_vals + [0.06, 0.08, 0.10, 0.12, 0.15, 0.20]:
        for be in band_vals + [0.10, 0.15, 0.20, 0.25, 0.30]:
            r = f1_score(labeled, ge, be)
            sonuclar.append(r)
            if best is None or (r["f1"], r["recall"]) > (best["f1"], best["recall"]):
                best = r
    sonuclar.sort(key=lambda r: (-r["f1"], -r["recall"]))
    print("\nEn iyi 10 eşik kombinasyonu (F1'e göre):")
    for r in sonuclar[:10]:
        print(f"  global<{r['global_esik']:.4f} band<{r['band_esik']:.4f} "
              f"-> P={r['precision']:.4f} R={r['recall']:.4f} F1={r['f1']:.4f} "
              f"(tp={r['tp']} fp={r['fp']} fn={r['fn']} tn={r['tn']})")
    print("\n>>> ÖNERİLEN (en yüksek F1):", json.dumps(best, ensure_ascii=False))


def gorsel_ornek(havuz: str, n: int) -> None:
    """Metinsiz (etiket=None) havuzdan örneklem: kart-crop'ları yan yana PNG'ye
    yazar (görsel doğrulama için) -- data/master_dup/k1_kalibrasyon/gorsel/."""
    import cv2
    import numpy as np

    pairs = json.loads(CIFTLER_PATH.read_text(encoding="utf-8"))
    if havuz == "metinsiz":
        pool = [x for x in pairs if x["etiket"] is None]
        pool.sort(key=lambda x: x["global_fark"])
    else:
        raise SystemExit(f"bilinmeyen havuz: {havuz}")

    gorsel_dir = OUT_DIR / "gorsel"
    gorsel_dir.mkdir(parents=True, exist_ok=True)
    secim = pool[:n] + pool[-n:] if len(pool) > 2 * n else pool
    for k, x in enumerate(secim):
        frames_dir = EX_FRAME_ROOT / f"{x['film']}{EX_SUFFIX}"
        pi = cv2.imread(str(frames_dir / x["src_i"]))
        pj = cv2.imread(str(frames_dir / x["src_j"]))
        if pi is None or pj is None:
            continue
        h = max(pi.shape[0], pj.shape[0])
        w = pi.shape[1] + pj.shape[1] + 8
        canvas = np.zeros((h, w, 3), np.uint8)
        canvas[: pi.shape[0], : pi.shape[1]] = pi
        canvas[: pj.shape[0], pi.shape[1] + 8:] = pj
        out_path = gorsel_dir / f"{k:02d}_{x['film']}_{x['i']}_{x['j']}_gf{x['global_fark']:.3f}.png"
        cv2.imwrite(str(out_path), canvas)
        print(out_path)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--topla", action="store_true")
    ap.add_argument("--esik-tara", action="store_true")
    ap.add_argument("--gorsel-ornek", default=None, help="havuz adı (ör. metinsiz)")
    ap.add_argument("--n", type=int, default=10)
    args = ap.parse_args(argv)

    if args.topla:
        topla()
    if args.esik_tara:
        esik_tara()
    if args.gorsel_ornek:
        gorsel_ornek(args.gorsel_ornek, args.n)
    if not (args.topla or args.esik_tara or args.gorsel_ornek):
        print("Hiçbir işlem seçilmedi (--topla / --esik-tara / --gorsel-ornek)", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
