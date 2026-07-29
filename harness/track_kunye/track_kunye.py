#!/usr/bin/env python3
"""track_kunye — frame-first künye çıkarma (Çağatay siparişi, 2026-07-29).

FELSEFE: OCR kompozisyondan ÖNCE. Kareler diskte durur; birleştirme metin-uzayında
yapılır ve her hata düzeltilebilir. Aynı satırın 10-30 karelik tekrarı düşman değil
OYLAMA SİNYALİ'dir (stitch kanıtı: JAMES DARREN ×7, DAMES DARREN ×1'i yener).

BORÇLAR (fikir kaynağı — kod kopyalanmadı, mantık olgunlaştırıldı):
  * stitch (20260601_stitch.py): birikimli kayma S_k, g=cy+S_k, bulanık-mode oylama.
  * line_mosaic_run (20260601_pipeline100.py): ROW birimi (aynı kare y-bandı grubu),
    en-keskin-kare bant kırpımı, MININST geçiş-çöpü fikri.
  * crop-stack: SUB_FRAC=0.82 altyazı bandı, union-find geçişli fuzzy birleştirme.
  * adaptif_slit v16 çöküşü (hayat-agaci): det-körlük KAPISI şart — token yoksa
    karar verme, işaretle (VLM fallback).

AKIŞ:
  kareler → det+rec (kutu geometrili) → ROW'lar (kare içi y-band grubu, x-sıralı
  canon) → kayma zinciri (token-eşleşmeli dy medyanı) → bölüm (kart) sınırları →
  ROW-track kümeleme (g + fuzzy/içerme) → bulanık-mode konsensüs → çöp filtreleri
  (altyazı bandı / watermark-ömrü / tek-gözlem) → çıktılar:
    <out>/<slug>/kunye_track.txt      ana künye (sıralı, kolonlar " | ")
    <out>/<slug>/dusuk_guven.txt      elenen-ama-atılamayan satırlar (insan kararı)
    <out>/<slug>/reading_master.png   SENTETİK MASTER (sadakat.py ile ölçülebilsin
                                      diye üretimle aynı ad)
    <out>/<slug>/track_manifest.json  istatistik + çöp dağılımı + det-körlük durumu

ÜRETİME DOKUNMAZ: yalnız kendi çıktı köküne yazar. OCR-worktree salt import.
Koşum: /opt/mitas/venvs/ocr/bin/python track_kunye.py --slug X --cikti-kok DIR
       [--kare-dizini DIR] [--liste dosya]
"""
from __future__ import annotations

import argparse
import difflib
import json
import os
import sys
import time
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np

REPO = Path(os.environ.get("MITAS_PROJECT_ROOT", "/opt/mitas"))
sys.path.insert(0, str(REPO / "OCR-worktree"))
sys.path.insert(0, str(REPO))

import db_compose_master as dc  # tembel det/rec motorları (F1b/F1c) — tek OCR kaynağı
from core.pipelines.ocr.jenerik_detector import is_credit_text_line

EX_KARE_ROOT = Path("/home/cagatay/Ex_Frame")
EX_SUFFIX = "-exit_frames"

# ── ayarlar (env ile ezilebilir) ────────────────────────────────────────────
SUB_FRAC = float(os.environ.get("MITAS_TK_SUB_FRAC", "0.82"))    # altyazı bandı (crop-stack kanıtlı)
ROW_TOL_ORAN = float(os.environ.get("MITAS_TK_ROW_TOL", "0.6"))  # satır-h × bu = aynı row
FUZZY = float(os.environ.get("MITAS_TK_FUZZY", "0.78"))          # track eşleşme benzerliği
G_PENCERE_ORAN = float(os.environ.get("MITAS_TK_G_PEN", "0.75")) # satır-h × bu = g penceresi
MIN_TOKEN_ESLESME = 2      # kayma ölçümü için ortak token alt sınırı
KART_JACCARD = 0.2         # bunun altı + dy yok → yeni bölüm (kart geçişi)
WATERMARK_KAPSAMA = 0.6    # havuzun bu oranından fazlasında görünen statik kısa metin → logo
DET_KOR_MEDYAN = 4         # kare başına medyan det kutusu bunun altındaysa det-kör
MIN_GOZLEM_ANA = 2         # ana künyeye girmek için gözlem alt sınırı (tek-kare → düşük-güven)
BANT_PAD = 6
RENDER_W = 720

# ── temel yardımcılar ───────────────────────────────────────────────────────

def fold(s: str) -> str:
    s = unicodedata.normalize("NFKD", (s or "").lower())
    return "".join(c for c in s if not unicodedata.combining(c) and (c.isalnum() or c.isspace())).strip()


def tokenlar(s: str) -> list[str]:
    return [t for t in fold(s).split() if len(t) >= 3]


_SESSIZ = set("bcdfghjklmnpqrstvwxyz")

def garble_skoru(s: str) -> float:
    """stitch'in garble sezgisi: harf-dışı oran + sesli-harfsiz uzun token cezası."""
    t = (s or "").strip()
    nonsp = sum(not c.isspace() for c in t)
    if nonsp == 0:
        return 9.0
    harf = sum(c.isalpha() for c in t)
    skor = (1 - harf / nonsp) * 2.0
    for tk in fold(t).split():
        if len(tk) >= 4 and all(c in _SESSIZ for c in tk):
            skor += 1.0
    return skor


def benzer(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, fold(a), fold(b)).ratio()


def icerme(a: str, b: str) -> bool:
    """kısa, uzunun alt-kümesi mi (kolonu eksik okunan row aynı track'e otursun)."""
    fa, fb = fold(a), fold(b)
    if not fa or not fb:
        return False
    kisa, uzun = (fa, fb) if len(fa) <= len(fb) else (fb, fa)
    return len(kisa) >= 6 and kisa in uzun


# ── veri yapıları ───────────────────────────────────────────────────────────

@dataclass
class Kutu:
    metin: str
    conf: float
    x0: float; y0: float; x1: float; y1: float

    @property
    def cy(self) -> float: return (self.y0 + self.y1) / 2.0
    @property
    def cx(self) -> float: return (self.x0 + self.x1) / 2.0
    @property
    def h(self) -> float: return self.y1 - self.y0


@dataclass
class Row:
    """Aynı karede aynı y-bandındaki kutular — kolon geometrisinin taşıyıcısı."""
    kare: int
    kutular: list[Kutu]

    @property
    def canon(self) -> str:
        return " | ".join(k.metin.strip() for k in sorted(self.kutular, key=lambda k: k.cx))
    @property
    def cy(self) -> float: return float(np.mean([k.cy for k in self.kutular]))
    @property
    def y0(self) -> float: return min(k.y0 for k in self.kutular)
    @property
    def y1(self) -> float: return max(k.y1 for k in self.kutular)
    @property
    def conf(self) -> float: return float(np.mean([k.conf for k in self.kutular]))


@dataclass
class Track:
    bolum: int
    g: float                      # bölüm-içi global koordinat (ilk gözlemin g'si, kayan ort.)
    gozlemler: list[Row] = field(default_factory=list)

    def ekle(self, row: Row, g_yeni: float) -> None:
        self.gozlemler.append(row)
        self.g = 0.8 * self.g + 0.2 * g_yeni   # hafif güncelle — drift'e direnç

    @property
    def kareler(self) -> set[int]:
        return {r.kare for r in self.gozlemler}


# ── 1) kare başına det+rec ──────────────────────────────────────────────────

def kare_oku(gray: np.ndarray) -> list[Kutu] | None:
    """det+rec; det BAŞARISIZ (None) ile 'kutu yok' (boş liste) AYRI anlamlar."""
    boxes = dc._f1b_det_boxes(gray)
    if boxes is None:
        return None
    if not boxes:
        return []
    sirali = dc._f1b_boxes_sorted(boxes)
    rec = dc._f1c_rec_boxes(gray, sirali)
    out = []
    for (text, conf), b in zip(rec, sirali):
        t = (text or "").strip()
        if not t:
            continue
        out.append(Kutu(t, float(conf), float(b[4]), float(b[5]), float(b[6]), float(b[7])))
    return out


def rowlari_kur(kare_idx: int, kutular: list[Kutu]) -> list[Row]:
    if not kutular:
        return []
    med_h = float(np.median([k.h for k in kutular]))
    tol = max(6.0, med_h * ROW_TOL_ORAN)
    rows: list[Row] = []
    for k in sorted(kutular, key=lambda k: k.cy):
        if rows and abs(k.cy - rows[-1].cy) <= tol:
            rows[-1].kutular.append(k)
        else:
            rows.append(Row(kare_idx, [k]))
    return rows


# ── 2) kayma zinciri + bölüm sınırları ──────────────────────────────────────

def kayma_ve_bolumler(kare_rows: list[list[Row]]) -> tuple[list[float], list[int]]:
    """Ardışık kareler arasında token-eşleşmeli dy medyanı → S_k zinciri.
    Eşleşme yoksa VE içerik koptuysa yeni bölüm (kart geçişi). S bölüm başında sıfırlanır.
    dy işareti: satır bir SONRAKİ karede yukarı kayar (cy küçülür) → dy=önceki−sonraki>0,
    g = cy + S sabit kalır (stitch ile aynı uzlaşım)."""
    n = len(kare_rows)
    S = [0.0] * n
    bolum = [0] * n
    for i in range(1, n):
        onceki = {}
        for r in kare_rows[i - 1]:
            for t in tokenlar(r.canon):
                onceki.setdefault(t, []).append(r.cy)
        farklar = []
        ortak = 0
        for r in kare_rows[i]:
            for t in tokenlar(r.canon):
                if t in onceki:
                    ortak += 1
                    farklar.append(min(onceki[t], key=lambda cy: abs(cy - r.cy)) - r.cy)
        a_tok = {t for r in kare_rows[i - 1] for t in tokenlar(r.canon)}
        b_tok = {t for r in kare_rows[i] for t in tokenlar(r.canon)}
        birlesim = a_tok | b_tok
        jac = (len(a_tok & b_tok) / len(birlesim)) if birlesim else 1.0
        if ortak >= MIN_TOKEN_ESLESME and farklar:
            dy = float(np.median(farklar))
            S[i] = S[i - 1] + dy
            bolum[i] = bolum[i - 1]
        elif jac >= KART_JACCARD or (not a_tok and not b_tok):
            # içerik benzer ama eşleşme sayısı az (soluk kare) VEYA iki taraf da boş
            # (det-kör film) → bölümü KORU, kaymayı dondur. Det-kör filmde sahte
            # bölüm patlaması olmaz; kapı zaten manifest'te işaretlenir.
            S[i] = S[i - 1]
            bolum[i] = bolum[i - 1]
        else:
            S[i] = 0.0
            bolum[i] = bolum[i - 1] + 1
    return S, bolum


# ── 3) ROW-track kümeleme ───────────────────────────────────────────────────

def tracklari_kur(kare_rows: list[list[Row]], S: list[float], bolum: list[int]) -> list[Track]:
    tum_h = [k.h for rows in kare_rows for r in rows for k in r.kutular]
    med_h = float(np.median(tum_h)) if tum_h else 18.0
    g_pen = max(8.0, med_h * G_PENCERE_ORAN)
    tracks: list[Track] = []
    for i, rows in enumerate(kare_rows):
        for r in rows:
            g = r.cy + S[i]
            aday, aday_puan = None, 0.0
            for t in tracks:
                if t.bolum != bolum[i] or abs(t.g - g) > g_pen:
                    continue
                son = t.gozlemler[-1].canon
                puan = benzer(son, r.canon)
                if puan >= FUZZY or icerme(son, r.canon):
                    if puan > aday_puan:
                        aday, aday_puan = t, puan
            if aday is None:
                tracks.append(Track(bolum[i], g, [r]))
            else:
                aday.ekle(r, g)
    return komsu_birlestir(tracks, g_pen)


def komsu_birlestir(tracks: list[Track], g_pen: float) -> list[Track]:
    """İkinci geçiş: g-komşusu track'lerin garble-varyant kopyalarını birleştir.
    (kanıt: gercek-yalanlar'da 'cuslodian' ve 'gustodian' iki ayrı track oldu —
    ikisi de CUSTODIAN'ın bozuk okuması, birbirlerine benzerlikleri eşik-altı
    ama KONSENSÜS metinleri karşılaştırılınca yakınlık görünür)."""
    tracks = sorted(tracks, key=lambda t: (t.bolum, t.g))
    out: list[Track] = []
    for t in tracks:
        m_t, _, _ = konsensus(t)
        hedef = None
        for o in reversed(out):
            if o.bolum != t.bolum or (t.g - o.g) > 1.6 * g_pen:
                break
            m_o, _, _ = konsensus(o)
            if benzer(m_o, m_t) >= 0.66 or icerme(m_o, m_t):
                hedef = o
                break
        if hedef is None:
            out.append(t)
        else:
            for r in t.gozlemler:
                hedef.ekle(r, t.g)
    return out


# ── 4) bulanık-mode konsensüs ───────────────────────────────────────────────

def konsensus(t: Track) -> tuple[str, float, Row]:
    """(metin, güven, en_iyi_row). Güven = kazanan grubun oy oranı × ort conf."""
    okumalar = [r.canon for r in t.gozlemler]
    gruplar: list[list[int]] = []
    for i, o in enumerate(okumalar):
        for g in gruplar:
            if benzer(okumalar[g[0]], o) >= 0.8:
                g.append(i)
                break
        else:
            gruplar.append([i])
    kazanan = max(gruplar, key=len)
    uyeler = [t.gozlemler[i] for i in kazanan]
    en_iyi = max(uyeler, key=lambda r: (r.conf, -garble_skoru(r.canon)))
    # temsilci metin: kazanan grupta EN SIK ham okuma; eşitlikte en temizi
    sayim = Counter(t.gozlemler[i].canon for i in kazanan)
    en_sik_n = sayim.most_common(1)[0][1]
    temsil = min((c for c, n in sayim.items() if n == en_sik_n), key=garble_skoru)
    guven = (len(kazanan) / len(okumalar)) * float(np.mean([r.conf for r in uyeler]))
    return temsil, guven, en_iyi


# ── 5) çöp filtreleri ───────────────────────────────────────────────────────

def siniflandir(t: Track, metin: str, guven: float, H: int, havuz_n: int) -> str:
    """'ana' | 'dusuk' | 'cop:<neden>'"""
    med_cy = float(np.median([r.cy for r in t.gozlemler]))
    tekil = fold(metin)
    # altyazı bandı: alt %18'de VE kredi-deseni değil → çöp (crop-stack kanıtlı eşik)
    if med_cy >= SUB_FRAC * H and not is_credit_text_line(metin.replace(" | ", " ")):
        return "cop:altyazi_bandi"
    # watermark/logo: havuzun >%60'ında görünen, kaymayan, kısa metin
    if len(t.kareler) >= WATERMARK_KAPSAMA * havuz_n and len(tekil) <= 24:
        g_std = float(np.std([r.cy for r in t.gozlemler]))
        if g_std < 4.0:
            return "cop:watermark"
    # düz cümle / sahne yazısı deseni (uzun, nokta bitişli, düşük harf oranı)
    if not is_credit_text_line(metin.replace(" | ", " ")) and len(metin.split()) >= 6:
        return "dusuk"
    # tek-gözlem: gerçek olabilir (yönetmen kartı!) — atma, insan görsün
    if len(t.gozlemler) < MIN_GOZLEM_ANA:
        return "dusuk" if guven < 0.75 else "ana"
    if guven < 0.35:
        return "dusuk"
    return "ana"


# ── 6) sentetik master render ───────────────────────────────────────────────

def render(siralı_ana: list[tuple[Track, str, Row]], dusukler: list[tuple[Track, str, Row]],
           imgs: dict[int, np.ndarray]) -> np.ndarray | None:
    bantlar: list[np.ndarray] = []

    def bant_al(row: Row) -> np.ndarray | None:
        im = imgs.get(row.kare)
        if im is None:
            return None
        H, W = im.shape[:2]
        y0 = max(0, int(row.y0) - BANT_PAD)
        y1 = min(H, int(row.y1) + BANT_PAD)
        if y1 - y0 < 8:
            return None
        b = im[y0:y1, :]
        if W != RENDER_W:
            b = cv2.resize(b, (RENDER_W, max(1, int(b.shape[0] * RENDER_W / W))),
                           interpolation=cv2.INTER_AREA)
        return b

    def ayrac(metin: str) -> np.ndarray:
        g = np.full((34, RENDER_W, 3), (40, 40, 40), np.uint8)
        cv2.putText(g, metin, (10, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (140, 200, 255), 1, cv2.LINE_AA)
        return g

    for _t, _m, row in siralı_ana:
        b = bant_al(row)
        if b is not None:
            bantlar.append(b)
    if dusukler:
        bantlar.append(ayrac(f"--- DUSUK GUVEN ({len(dusukler)}) — insan karari ---"))
        for _t, _m, row in dusukler:
            b = bant_al(row)
            if b is not None:
                bantlar.append(b)
    if not bantlar:
        return None
    return np.vstack(bantlar)


# ── ana akış ────────────────────────────────────────────────────────────────

def calistir(slug: str, cikti_kok: Path, kare_dizini: str | None = None) -> dict:
    t0 = time.time()
    d = Path(kare_dizini) if kare_dizini else EX_KARE_ROOT / f"{slug}{EX_SUFFIX}"
    yollar = sorted(d.glob("exit_*.png")) or sorted(d.glob("*.png"))
    out = cikti_kok / slug
    out.mkdir(parents=True, exist_ok=True)
    man: dict = {"slug": slug, "mode": "track_kunye", "kare": len(yollar)}
    if len(yollar) < 2:
        man["durum"] = "kare_yok"
        (out / "track_manifest.json").write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")
        return man

    imgs: dict[int, np.ndarray] = {}
    kare_rows: list[list[Row]] = []
    det_sayilari: list[int] = []
    det_basarisiz = 0
    H = 480
    for i, p in enumerate(yollar):
        im = cv2.imread(str(p))
        if im is None:
            kare_rows.append([])
            continue
        H = im.shape[0]
        imgs[i] = im
        kutular = kare_oku(cv2.cvtColor(im, cv2.COLOR_BGR2GRAY))
        if kutular is None:
            det_basarisiz += 1
            kare_rows.append([])
            continue
        det_sayilari.append(len(kutular))
        kare_rows.append(rowlari_kur(i, kutular))

    med_det = float(np.median(det_sayilari)) if det_sayilari else 0.0
    man["det_medyan_kutu"] = med_det
    man["det_basarisiz_kare"] = det_basarisiz
    man["det_kor"] = bool(med_det < DET_KOR_MEDYAN)   # VLM-fallback işareti

    S, bolum = kayma_ve_bolumler(kare_rows)
    tracks = tracklari_kur(kare_rows, S, bolum)
    man["bolum"] = int(max(bolum) + 1) if bolum else 0
    man["track"] = len(tracks)

    ana, dusuk, cop = [], [], Counter()
    havuz_n = len(yollar)
    for t in tracks:
        metin, guven, en_iyi = konsensus(t)
        sinif = siniflandir(t, metin, guven, H, havuz_n)
        if sinif == "ana":
            ana.append((t, metin, en_iyi, guven))
        elif sinif == "dusuk":
            dusuk.append((t, metin, en_iyi, guven))
        else:
            cop[sinif.split(":", 1)[1]] += 1

    sira = lambda kayit: (kayit[0].bolum, kayit[0].g)
    ana.sort(key=sira)
    dusuk.sort(key=sira)

    (out / "kunye_track.txt").write_text(
        "\n".join(m for _t, m, _r, _g in ana) + "\n", encoding="utf-8")
    (out / "dusuk_guven.txt").write_text(
        "\n".join(f"{m}\t(guven={g:.2f}, gozlem={len(t.gozlemler)})" for t, m, _r, g in dusuk) + "\n",
        encoding="utf-8")

    png = render([(t, m, r) for t, m, r, _ in ana], [(t, m, r) for t, m, r, _ in dusuk], imgs)
    if png is not None:
        cv2.imwrite(str(out / "reading_master.png"), png)

    man.update({
        "durum": "OK", "ana_satir": len(ana), "dusuk_guven": len(dusuk),
        "cop": dict(cop), "master_boy": None if png is None else int(png.shape[0]),
        "sure_s": round(time.time() - t0, 2),
    })
    (out / "track_manifest.json").write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")
    return man


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--slug")
    g.add_argument("--liste", help="satır başına slug")
    ap.add_argument("--cikti-kok", required=True)
    ap.add_argument("--kare-dizini")
    args = ap.parse_args(argv)
    kok = Path(args.cikti_kok)
    sluglar = [args.slug] if args.slug else [
        s.strip() for s in Path(args.liste).read_text().splitlines() if s.strip()]
    for s in sluglar:
        m = calistir(s, kok, args.kare_dizini)
        print(f"{s:44s} {m.get('durum','?'):8s} ana={m.get('ana_satir','-'):>4} "
              f"dusuk={m.get('dusuk_guven','-'):>3} cop={m.get('cop',{})} "
              f"bolum={m.get('bolum','-')} det_kor={m.get('det_kor','-')} {m.get('sure_s','-')}s",
              flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
