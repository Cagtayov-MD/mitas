#!/usr/bin/env python3
"""track_kunye — frame-first künye çıkarma (Çağatay siparişi, 2026-07-29).

FELSEFE: OCR kompozisyondan ÖNCE. Kareler diskte durur; birleştirme metin-uzayında
yapılır ve her hata düzeltilebilir. Aynı satırın 10-30 karelik tekrarı düşman değil
OYLAMA SİNYALİ'dir (stitch kanıtı: JAMES DARREN ×7, DAMES DARREN ×1'i yener).

BORÇLAR (fikir kaynağı — kod kopyalanmadı, mantık olgunlaştırıldı):
  * stitch (20260601_stitch.py): birikimli kayma S_k, g=cy+S_k, bulanık-mode oylama.
  * line_mosaic_run (eski pipeline100 görsel dalı; 2026-07-30 söküldü): ROW birimi (aynı kare y-bandı grubu),
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

def kayma_ve_bolumler(kare_rows: list[list[Row]], ekran_h: int = 480) -> tuple[list[float], list[int]]:
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
            # GLM Bug-2 fix'i: dissolve anında iki kartın token'ları çapraz eşleşip
            # dy medyanını sıçratabilir (200px) → S bozulur, track'ler kırılır.
            # Fiziksel scroll adımı kare yüksekliğinin ~yarısını aşamaz → aşan
            # ölçüm gürültüdür, kaymayı DONDUR (bölüm korunur).
            if abs(dy) > 0.5 * ekran_h:
                S[i] = S[i - 1]
            else:
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
            if benzer(m_o, m_t) >= 0.85 or icerme(m_o, m_t):
                hedef = o
                break
        if hedef is None:
            out.append(t)
        else:
            # GLM Bug-4 fix'i: hedefin g'si KAYMASIN — yeni track'in g'siyle
            # beslemek hedefi 20-30px sürükleyip sonraki eşleşmeleri kırıyordu.
            for r in t.gozlemler:
                hedef.ekle(r, hedef.g)
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
    # temsilci metin (GLM Bug-1 fix'i, 2026-07-30): TEMİZLİK birincil, conf ikincil,
    # frekans yalnız eşitlik bozucu. Eski kural "en sık ham okuma" idi — Paddle bir
    # ismi TUTARLI yanlış okuyunca (10× "eminler ca s", 2× "mike minkler") çoğunluk
    # bozuk metni kazandırıyordu; en temiz okuma elimizdeyken metne yansımıyordu.
    sayim = Counter(t.gozlemler[i].canon for i in kazanan)
    conf_ort = {c: float(np.mean([r.conf for r in uyeler if r.canon == c])) for c in sayim}
    en_az_garble = min(garble_skoru(c) for c in sayim)
    adaylar = [c for c in sayim if garble_skoru(c) <= en_az_garble + 0.75]
    temsil = max(adaylar, key=lambda c: (conf_ort[c], sayim[c], len(c)))
    guven = (len(kazanan) / len(okumalar)) * float(np.mean([r.conf for r in uyeler]))
    return temsil, guven, en_iyi


# ── 5) çöp filtreleri ───────────────────────────────────────────────────────

def watermark_metinleri(tracks: list[Track], konsensuslar: dict[int, str]) -> set[str]:
    """GLM Bug-3'ün sağlamlaştırılmışı: track'ler bölüm-İÇİ yaşadığı için eski
    track-bazlı kapsama kuralı hem neredeyse hiç tetiklenmiyor hem de uzun tek-kart
    filmde GERÇEK kartı silme riski taşıyordu. Yeni sinyal: aynı fold-metin 3+
    FARKLI bölümde track açmışsa (kart bölüm sınırını aşamaz, logo aşar) ve kısa
    ve konumu oynamıyorsa → watermark."""
    metin_bolumleri: dict[str, set[int]] = {}
    metin_cy_std: dict[str, list[float]] = {}
    for i, t in enumerate(tracks):
        m = fold(konsensuslar.get(i, ""))
        if not m or len(m) > 24:
            continue
        metin_bolumleri.setdefault(m, set()).add(t.bolum)
        metin_cy_std.setdefault(m, []).extend(r.cy for r in t.gozlemler)
    return {m for m, bl in metin_bolumleri.items()
            if len(bl) >= 3 and float(np.std(metin_cy_std[m])) < 8.0}


def siniflandir(t: Track, metin: str, guven: float, H: int,
                med_conf_film: float, wm_metinler: set[str]) -> str:
    """'ana' | 'dusuk' | 'cop:<neden>'. Güven eşikleri film medyan conf'una
    ORANTILI (GLM Bug-5: sabit 0.75/0.35 loş filmi — havaci — komple düşük-güvene
    boğuyordu; parlak filmde ise gürültüye fazla cömertti)."""
    med_cy = float(np.median([r.cy for r in t.gozlemler]))
    if med_cy >= SUB_FRAC * H and not is_credit_text_line(metin.replace(" | ", " ")):
        return "cop:altyazi_bandi"
    if fold(metin) in wm_metinler:
        return "cop:watermark"
    if not is_credit_text_line(metin.replace(" | ", " ")) and len(metin.split()) >= 6:
        return "dusuk"
    esik_tek = min(0.75, max(0.30, med_conf_film * 1.1))
    esik_cok = min(0.35, max(0.15, med_conf_film * 0.6))
    if len(t.gozlemler) < MIN_GOZLEM_ANA:
        return "dusuk" if guven < esik_tek else "ana"
    if guven < esik_cok:
        return "dusuk"
    return "ana"


# ── 6) sentetik master render ───────────────────────────────────────────────

def _bant_al(row: Row, imgs: dict[int, np.ndarray],
             kare_x: dict[int, tuple[int, int]] | None = None) -> np.ndarray | None:
    """Row bandı: yalnız YAZININ x-aralığı (footage kesilir) + kutu-dışı karartma.
    (Çağatay QC'si 2026-07-29: tam-genişlik bant footage-üstü filmde okunmaz
    duvar ördü — mufreze 21577px. Yazı-dışı %25 parlaklığa düşürülür ki bağlam
    görünsün ama yazı öne çıksın; VL girdisi olarak da okunur kalsın.)"""
    im = imgs.get(row.kare)
    if im is None:
        return None
    H, W = im.shape[:2]
    y0 = max(0, int(row.y0) - BANT_PAD)
    y1 = min(H, int(row.y1) + BANT_PAD)
    # x-aralığı: yalnız bu row değil, o KAREDEKİ TÜM yazının kapladığı sütun
    # (2026-07-30: dar row-kırpımı kare-OCR'ın kaçırdığı yan yazıyı da kesiyordu;
    # kare-genel sütun kaçağı bantta tutar, footage kenarları yine kesilir).
    kx = (kare_x or {}).get(row.kare)
    rx0 = int(min(k.x0 for k in row.kutular)); rx1 = int(max(k.x1 for k in row.kutular))
    if kx is not None:
        rx0, rx1 = min(rx0, kx[0]), max(rx1, kx[1])
    marj = max(2 * BANT_PAD, int(0.06 * W))
    x0 = max(0, rx0 - marj)
    x1 = min(W, rx1 + marj)
    if y1 - y0 < 8 or x1 - x0 < 16:
        return None
    b = im[y0:y1, x0:x1].copy()
    # KARARTMA YOK (2026-07-30 regresyon dersi): kutu-dışı karartma, kare-OCR'ın
    # KAÇIRDIGI yazıyı mühürlüyordu — karadeniz sentetik recall 0.643->0.164.
    # x-kırpım footage'ın çoğunu zaten atıyor; bant HAM kalır ki kaçan yazı hem
    # insan gözüne hem ikinci-geçiş OCR'a açık kalsın ("okunamadı > yanlış oku").
    # sabit kanvas genişliğine SOL hizalı yerleştir (ölçek yalnız taşarsa)
    if b.shape[1] > RENDER_W:
        b = cv2.resize(b, (RENDER_W, max(1, int(b.shape[0] * RENDER_W / b.shape[1]))),
                       interpolation=cv2.INTER_AREA)
    kanvas = np.zeros((b.shape[0], RENDER_W, 3), np.uint8)
    kanvas[:, :b.shape[1]] = b
    return kanvas


def _bolum_cizgisi() -> np.ndarray:
    g = np.zeros((7, RENDER_W, 3), np.uint8)
    g[3, :] = (70, 70, 70)
    return g


def _ayrac(metin: str) -> np.ndarray:
    g = np.full((30, RENDER_W, 3), (36, 36, 36), np.uint8)
    cv2.putText(g, metin, (10, 21), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (130, 190, 255), 1, cv2.LINE_AA)
    return g


def render(siralı_ana: list[tuple[Track, str, Row]], imgs: dict[int, np.ndarray],
           kare_x: dict[int, tuple[int, int]] | None = None,
           dusukler: list[tuple[Track, str, Row]] | None = None) -> np.ndarray | None:
    """Tek dosya: ana satırlar + ayraçla DÜŞÜK GÜVEN bölümü (2026-07-30: düşük
    bölümünü ayrı dosyaya almak hem QC'yi iki dosyaya bölüyor hem sadakat kıyasını
    adaletsiz kılıyordu — adaptif master her şeyi tek gövdede taşıyor). Bölüm
    sınırında ince çizgi; bant araları 3px."""
    bantlar: list[np.ndarray] = []
    onceki_bolum = None
    for t, _m, row in siralı_ana:
        if onceki_bolum is not None and t.bolum != onceki_bolum:
            bantlar.append(_bolum_cizgisi())
        onceki_bolum = t.bolum
        b = _bant_al(row, imgs, kare_x)
        if b is not None:
            bantlar.append(b)
            bantlar.append(np.zeros((3, RENDER_W, 3), np.uint8))
    if dusukler:
        bantlar.append(_ayrac(f"--- DUSUK GUVEN ({len(dusukler)}) - insan karari ---"))
        for _t, _m, row in dusukler:
            b = _bant_al(row, imgs, kare_x)
            if b is not None:
                bantlar.append(b)
                bantlar.append(np.zeros((3, RENDER_W, 3), np.uint8))
    if not bantlar:
        return None
    return np.vstack(bantlar)




# ── 7) KARE-ALBÜMÜ render (Çağatay önerisi, 2026-07-30) ─────────────────────
# Satır-kesme render'ı kart yapısını öldürüyor ve kesim lekesi bırakıyordu.
# Bu mod TAM KARELERİ dizer: statik bölümden EN ZENGİN tek kare, scroll
# bölümünden S-uzayında örtüşmesiz pencere temsilcileri ("benzer kare eleme"
# dhash'le değil ölçülmüş kaymayla — aynı içerik = yakın S). Kesim yok →
# leke yok; 480px doğal sayfalar → VL'e dilimlemeden verilebilir.

def album_kareleri(kare_rows: list[list[Row]], S: list[float], bolum: list[int],
                   ekran_h: int) -> list[int]:
    from collections import defaultdict
    bolum_kareleri: dict[int, list[int]] = defaultdict(list)
    for i, rows in enumerate(kare_rows):
        if rows:
            bolum_kareleri[bolum[i]].append(i)

    def zenginlik(i: int) -> float:
        toks = sum(len(tokenlar(r.canon)) for r in kare_rows[i])
        conf = float(np.mean([r.conf for r in kare_rows[i]])) if kare_rows[i] else 0.0
        return toks * (0.5 + conf)

    secim: list[int] = []
    for b in sorted(bolum_kareleri):
        idxler = bolum_kareleri[b]
        s_vals = [S[i] for i in idxler]
        aralik = max(s_vals) - min(s_vals)
        if aralik < 0.35 * ekran_h:
            secim.append(max(idxler, key=zenginlik))          # statik kart: tek temsilci
            continue
        # scroll: S-aralığını %85 ekran adımlı pencerelere böl, pencere başına
        # hedefe en yakın S'li kareler arasından en zenginini al
        hedef = min(s_vals)
        adim = 0.85 * ekran_h
        while hedef <= max(s_vals) + 1:
            yakinlar = sorted(idxler, key=lambda i: abs(S[i] - hedef))[:3]
            secim.append(max(yakinlar, key=zenginlik))
            hedef += adim
    gorulen: set[int] = set()
    return [i for i in sorted(secim) if not (i in gorulen or gorulen.add(i))]


def album_render(secim: list[int], imgs: dict[int, np.ndarray]) -> np.ndarray | None:
    parcalar: list[np.ndarray] = []
    W = None
    for i in secim:
        im = imgs.get(i)
        if im is None:
            continue
        if W is None:
            W = im.shape[1]
        if im.shape[1] != W:
            im = cv2.resize(im, (W, int(im.shape[0] * W / im.shape[1])), interpolation=cv2.INTER_AREA)
        parcalar.append(im)
        parcalar.append(np.full((6, W, 3), (80, 80, 80), np.uint8))
    if not parcalar:
        return None
    return np.vstack(parcalar[:-1])

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

    S, bolum = kayma_ve_bolumler(kare_rows, H)
    tracks = tracklari_kur(kare_rows, S, bolum)
    man["bolum"] = int(max(bolum) + 1) if bolum else 0
    man["track"] = len(tracks)

    tum_conf = [k.conf for rows in kare_rows for r in rows for k in r.kutular]
    med_conf_film = float(np.median(tum_conf)) if tum_conf else 0.0
    man["medyan_conf"] = round(med_conf_film, 3)

    konsensuslar = {i: konsensus(t)[0] for i, t in enumerate(tracks)}
    wm = watermark_metinleri(tracks, konsensuslar)

    ana, dusuk, cop = [], [], Counter()
    for t in tracks:
        metin, guven, en_iyi = konsensus(t)
        sinif = siniflandir(t, metin, guven, H, med_conf_film, wm)
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

    kare_x = {}
    for i, rows in enumerate(kare_rows):
        ks = [k for r in rows for k in r.kutular]
        if ks:
            kare_x[i] = (int(min(k.x0 for k in ks)), int(max(k.x1 for k in ks)))
    secim = album_kareleri(kare_rows, S, bolum, H)
    apng = album_render(secim, imgs)
    if apng is not None:
        cv2.imwrite(str(out / "reading_master.png"), apng)   # BİRİNCİL görsel: kare albümü
    man["album_kare"] = len(secim)
    png = render([(t, m, r) for t, m, r, _ in ana], imgs, kare_x,
                 dusukler=[(t, m, r) for t, m, r, _ in dusuk])
    if png is not None:
        cv2.imwrite(str(out / "satir_master.png"), png)       # ikincil: satır görünümü

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
