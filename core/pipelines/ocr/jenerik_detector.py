# -*- coding: utf-8 -*-
"""4-tip sağlam JENERİK (credit) başlangıç dedektörü.

Mevcut OpusCreditDetector'ın iki yapısal kusurunu düzeltir:
  (1) KARANLIK-ZEMİN SERT KAPISI yok → parlak/footage zemin üstü SABİT yazı yakalanır.
  (2) Arka-plan-hareketi ile yazı-hareketi AYRIŞTIRILIR → 4 tip net ayırt edilir:
        bg_static_text_static / bg_static_text_scroll /
        bg_moving_text_static / bg_moving_text_scroll  (+ "mixed" yarı-yarıya).

Kare-başına 3 sinyal:
  1. Yapısal-yazı varlığı  — tophat metin-maskesi (BG-agnostik) + CC + row-structure. (dark = küçük bonus, kapı değil)
  2. CLIP kredi-olasılığı   — open_clip SigLIP ViT-B/16 (opsiyonel; yoksa sezgisele düşer). "isim listesi mi" semantiği.
  3. Hareket               — yazı: dar-maske faz-kor; arka-plan: ters-maske faz-kor + gdiff yedeği.

Pencere değil KARE-bazlı credit_present (medyan-smooth) → koşular (runs) → giriş(ilk)/çıkış(son) bölge.
Hem KARE-KLASÖRÜ (Database/<film>/frames/giris|cikis) hem VİDEO girdisini AYNI çekirdekle işler.

cv2 Türkçe-İ tuzağı: imread/imwrite YOK → _cv2_imread (fromfile+imdecode).
Yeniden kullanılan primitifler: jenerik_primitifleri (_build_tophat_mask/_phase_corr/_gdiff/_masked_gray/_hann2d;
2026-07-30'a dek dynamic_credit_mosaic içindeydi), credit_detector (_row_structure_score/_cv2_imread).
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from statistics import median
from typing import Any, Optional

import cv2
import numpy as np

# E:\MITAS'ı path'e ekle (standalone import için) → core paketi
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from core.pipelines.ocr.jenerik_primitifleri import (  # noqa: E402
    _build_tophat_mask, _phase_corr, _gdiff, _masked_gray, _hann2d,
)
from core.pipelines.ocr.credit_detector import _row_structure_score, _cv2_imread  # noqa: E402


# --------------------------------------------------------------------------- #
# CLIP prompt kümeleri (clip_probe ile birebir; görsel kavram dile bağlı değil)
# --------------------------------------------------------------------------- #
CREDIT_PROMPTS = [
    "scrolling end credits of a film",
    "the closing credits of a movie listing cast and crew",
    "opening title credits with actor names",
    "a plain title card with names and text",
    "white text on a dark background, movie credits",
    "a list of names, film credits rolling on screen",
]
SCENE_PROMPTS = [
    "a scene from a film",
    "a movie still showing people",
    "an outdoor landscape in a movie",
    "actors performing in a film scene",
    "a film frame with a subtitle dialogue line at the bottom",
    "a movie scene with no credits",
]

# --------------------------------------------------------------------------- #
# Eşikler (H = kare yüksekliği; kareler NATİF çözünürlük, film-başına 600/854×480 değişir)
# DİKKAT: eski dynamic_credit_mosaic S_HI=0.8 ~6fps/natif içindi; burası fps≈2 + değişken H.
#         px'i H'e göre ifade et, H/480 ile ölçekle (Plan-ajanı düzeltmesi).
# --------------------------------------------------------------------------- #
ANALYZE_H = 480                 # video karelerini bu yüksekliğe indir (tophat KSIZE=25 ~480p'ye göre kalibre)
SMOOTH_K = 5                    # medyan-smooth penceresi (clip_probe ile aynı)
WRAP_CLIP_FRAC = 0.25           # |dy| > bu*H → faz-kor sarması, kırp
S_HI_FRAC = 0.010               # yazı scroll onay px = 0.010*H (~4.8px @480)
S_LO_FRAC = 0.004               # statiğe dön px = 0.004*H (~1.9px)
BG_THR_FRAC = 0.006             # arka-plan pan px = 0.006*H (~2.9px)
G_THR = 6.0                     # gdiff yönsüz arka-plan değişim eşiği (bg güvenilmezse OR-yedek)
BG_COVER_MIN = 0.40             # ters-maske kapsamı < bu → bg_reliable=False (yazı kareyi dolduruyor)
RESP_MIN = 0.15                 # faz-kor güveni tabanı (yön'e güvenmek için)
SIGN_CONSIST_MIN = 0.70         # koşu boyunca dy işaret-tutarlılığı tabanı
TEXT_DILATE_K = 9               # bg ekseni için metin maskesini bu kadar şişir, sonra ters al

# Füzyon
W_CLIP = 0.55
W_HEUR = 0.45
CLIP_ALLOW = 0.65               # clip >= bu → sezgisel zayıf olsa da kredi-var (yumuşak-kapı)
CLIP_KILL = 0.20                # clip < bu AND heur < HEUR_KILL → kredi-yok'a zorla
HEUR_KILL = 0.30
PRESENT_THR = 0.50              # credit_present eşiği

# Koşu (run) bulma + bölge geçerliliği
RUN_GAP = 3                     # koşu içi izinli boşluk (kare)
RUN_MINLEN = 6                  # min sürdürülen credit_present (kare) ≈ 3s @ fps2
RAW_MINLEN = 2                  # ham koşu min: kısa-güçlü adayları + near-miss için sınıflandır (1-kare gürültü hariç)
SHORT_STRONG_CS = 0.75          # kısa koşu (n<RUN_MINLEN) ANCAK medyan cs>=bu VE
SHORT_STRONG_MINCLIP = 0.85     #   koşunun HER karesi CLIP>=bu ise GEÇERLİ. min_clip (medyan değil!): gerçek
                                #   title-card her karede tekdüze-kredi; sahneden geçen diegetik tabela CLIP'i
                                #   kare-kare dalgalandırır (min düşer) → elenir. (14'DEN "WERTMAN HIGH SCHOOL"
                                #   tabelası min_clip=0.40 ELENİR; NAR BAĞI title min_clip=1.00 GEÇER.)
# BAŞLANGIÇ-KIRPMA + footage-FP kalkanı: koşu kenarındaki CLIP-footage sızıntısını at.
# CLIP yumuşak-kapısı (clip≥0.65) yazı-yapısı OLMAYAN footage'ı "present" yapabiliyor (KAOS çıkış:
# uçak/çöl footage cs0.55 ama n_blobs=0/row_struct=0; gerçek yazı 12 kare sonra). Başlangıç GERÇEK
# METİN-yapısı olan ilk kareye kırpılır; koşuda hiç gerçek-metin karesi yoksa = CLIP-only footage → geçersiz.
START_NBLOB = 2                 # gerçek-metin karesi: min blob (tek blob = footage gürültüsü, yetmez)
START_ROW = 0.30                # ve min row_struct (satır-yapısı)
# BAŞLANGIÇ-GERİ-ÇEKME (Çağatay kuralı 2026-06-20): GEÇ-başlama=krediyi-kaçır=YASAK; ERKEN=1-2sn-film=SERBEST.
# Bulunan start'tan, soluk erken-kredi (logo/overlay; cs ana-eşiğin altında ama footage'tan yüksek) varken
# GERİYE yürü + emniyet payı. Geç→doğru olur; biraz fazla footage görmek kabul. (KOVAN: kredi #147, start #154→geri)
BACK_LOW_CS = 0.30              # geri-yürüyüşte soluk-kredi eşiği (footage ~0.1-0.25 altında kalır)
BACK_GAP = 3                   # öğeler-arası izinli boşluk (siyah-kare); bu kadar ardışık footage → dur
BACK_CAP = 24                  # en fazla bu kadar kare geri (≈12s @ fps2) — kontrolsüz kaçışı önle
BACK_SAFETY = 2                # ilk-öğeden +bu kadar kare geri (≈1s film payı) — geç-başlamaya emniyet
MIN_TEXT_FRAMES = 3             # koşuda bu kadar gerçek-metin karesi yoksa → no_text_structure (footage FP)

# OCR-temelli başlangıç inceltme (asıl TOO_LATE fix; sezgisel geri-çekme YETMEZ — faint logo/yönetmen-kartı
# tek-öğe row_struct'ı düşük kalır, OCR ise GERÇEK metni okur). Çağatay kuralı: geç-başlama=YASAK, erken=SERBEST.
OCR_BACK_GAP = 4               # kartlar-arası izinli kredi-SİZ kare; bu kadar ardışık footage → sınır, dur
OCR_BACK_CAP = 120             # en fazla bu kadar kare geri (≈60s @ fps2); BACK_GAP zaten erken durdurur
OCR_SAFETY = 2                 # ilk kredi-karesinden +bu kadar geri (≈1s film payı)

# GİRİŞ jeneriği açılış köprü fix — flag MITAS_JENERIK_OPEN_BRIDGE (DEFAULT OFF). Dağınık-geç kredi
# kartları (studio/yönetmen) footage boşluklarıyla bölündüğünde, refine_end_ocr'ın kısa OCR_BACK_GAP=4
# (~2s @ fps2) kart-arası footage boşluğunu köprüleyemez → geç-kart bloğu pencere DIŞINDA kalır.
# OPEN_END_BACK_GAP (~100s @ fps2) bu boşlukları köprüler; OPEN_END_BACK_CAP (~200s) ~180s açılış
# kuyruğunu kapsar. OCR-kapılı (is_credit_text_line) → footage'ta yazı bulunmaz → köprü kurulmaz.
# Flag OFF → _apply_ocr_refine_end INERT (eski OCR_BACK_GAP=4/OCR_BACK_CAP=120 birebir korunur).
# Tuning env'leri: MITAS_JENERIK_OPEN_BACK_GAP / MITAS_JENERIK_OPEN_BACK_CAP (boş→default, or-guard'lı).
OPEN_END_BACK_GAP = int(os.environ.get("MITAS_JENERIK_OPEN_BACK_GAP", "200") or "200")   # ~100s @ fps2
OPEN_END_BACK_CAP = int(os.environ.get("MITAS_JENERIK_OPEN_BACK_CAP", "400") or "400")   # ~200s @ fps2: açılış kuyruğu
# NOT (2026-06-20, ÖLÇÜLDÜ→GERİ ALINDI): "sürdürülen yoğun-metin" kapısı (dense_count) denendi; dokulu
# footage'ı (CENGİZ çayır her karede ~24 sahte-blob) ve diegetik-yazıyı (ASRİ sessiz-film diyalog kartı =
# gerçekten yoğun yazı) AYIRAMADI + kısa gerçek kredileri kırdı (YERÇEKİMİ). Blob-istatistiği footage-doku/
# diegetik-yazı ile krediyi ayıramaz → gerçek çözüm OCR-tabanlı metin-doğrulama (okunabilir kelime var mı). KALDI.
RUN_ROWSTRUCT_MIN = 0.15        # koşu medyan row_struct < bu → (CLIP teyidi yoksa) dokulu-footage FP, düş
RUN_CLIP_RESCUE = 0.50          # ama koşu medyan clip >= bu ise yine de tut
STATIC_NBLOB_MIN = 3            # statik (hareketsiz) koşuda medyan n_blobs < bu → altyazı/tabela FP (CLIP teyidi yoksa düş)
MIXED_LO, MIXED_HI = 0.30, 0.70 # koşu içi text_moving kesri bu bantta → "mixed" (yarı-yarıya)

LOW_CONF = 0.55                 # güven < bu → insan denetimine işaretle (low_conf=True)


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, float(x)))


# --------------------------------------------------------------------------- #
# CLIP (lazy; open_clip/torch yoksa None → sezgisel füzyon)
# --------------------------------------------------------------------------- #
def load_clip(device: Optional[str] = None) -> Optional[dict]:
    """CLIP bağlamını yükle. open_clip/torch yoksa None döner (çağıran sezgisele düşer).

    Varsayılan model SigLIP ViT-B/16 (webli) — ViT-B/32'den +7 puan tespit (%92→%99), aynı hız.
    Eski modele dönmek için: MITAS_JENERIK_CLIP_MODEL=vitb32
    """
    try:
        import torch
        import open_clip
    except Exception:
        return None
    try:
        import threading
        dev = device or ("cuda" if torch.cuda.is_available() else "cpu")
        _model_key = os.environ.get("MITAS_JENERIK_CLIP_MODEL", "siglip").strip().lower()
        if _model_key == "vitb32":
            _model_id, _pretrained = "ViT-B-32", "laion2b_s34b_b79k"
        else:
            _model_id, _pretrained = "ViT-B-16-SigLIP", "webli"
        model, _, preprocess = open_clip.create_model_and_transforms(
            _model_id, pretrained=_pretrained)
        tok = open_clip.get_tokenizer(_model_id)
        model = model.to(dev).eval()
        ls = model.logit_scale.exp().item()

        @torch.no_grad()
        def _embed(prompts):
            t = tok(prompts).to(dev)
            e = model.encode_text(t).float()
            e = e / e.norm(dim=-1, keepdim=True)
            m = e.mean(0)
            return m / m.norm()

        return {"model": model, "preprocess": preprocess, "ls": ls,
                "cred_e": _embed(CREDIT_PROMPTS), "scene_e": _embed(SCENE_PROMPTS), "dev": dev,
                "model_id": _model_id,
                "lock": threading.Lock()}   # paralel giriş+çıkış için CLIP forward'ını serileştir (thread-güvenli)
    except Exception:
        return None


def _clip_scores(ctx: dict, frames_bgr: list[np.ndarray]) -> list[float]:
    """Her BGR kare için kredi-olasılığı (softmax[cred, scene][0])."""
    import torch
    from contextlib import nullcontext
    from PIL import Image
    model, pre, dev = ctx["model"], ctx["preprocess"], ctx["dev"]
    lock = ctx.get("lock") or nullcontext()   # paralel modda iki thread aynı modeli çağırırsa serileştir
    out: list[float] = []
    B = 64
    with torch.no_grad():
        for i in range(0, len(frames_bgr), B):
            batch = frames_bgr[i:i + B]
            # CPU preprocess lock DIŞINDA (paralel hazırlık); GPU'ya taşıma (.to) lock İÇİNDE —
            # aksi halde paralel giriş+çıkış iki 64'lük batch'i aynı anda VRAM'e koyup OOM riski yaratır.
            cpu_imgs = torch.stack([
                pre(Image.fromarray(cv2.cvtColor(f, cv2.COLOR_BGR2RGB))) for f in batch
            ])
            with lock:
                imgs = cpu_imgs.to(dev)
                ie = model.encode_image(imgs).float()
                ie = ie / ie.norm(dim=-1, keepdim=True)
                sc = torch.stack([ie @ ctx["cred_e"], ie @ ctx["scene_e"]], dim=1) * ctx["ls"]
                p = sc.softmax(dim=1)[:, 0].cpu().numpy()
            out.extend(float(x) for x in p)
    return out


# --------------------------------------------------------------------------- #
# Kare-başına sinyaller
# --------------------------------------------------------------------------- #
@dataclass
class FrameSig:
    idx: int
    n_blobs: int = 0
    text_ratio: float = 0.0
    row_struct: float = 0.0
    dark_ratio: float = 0.0
    heur: float = 0.0
    clip: Optional[float] = None
    credit_score: float = 0.0
    present: bool = False
    # hareket (kare i ile i-1 arası; i=0 → 0)
    text_dy: float = 0.0
    text_resp: float = 0.0
    bg_dx: float = 0.0
    bg_dy: float = 0.0
    bg_resp: float = 0.0
    bg_reliable: bool = True
    gdiff: float = 0.0


def _med_smooth(vals: list[float], k: int = SMOOTH_K) -> list[float]:
    if k <= 1 or len(vals) <= 1:
        return list(vals)
    h = k // 2
    out = []
    for i in range(len(vals)):
        out.append(float(np.median(vals[max(0, i - h):i + h + 1])))
    return out


def _prep_gray(frame: np.ndarray) -> np.ndarray:
    g = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if frame.ndim == 3 else frame
    return g


def score_sequence(frames_bgr: list[np.ndarray], *, clip_ctx: Optional[dict] = None) -> list[FrameSig]:
    """Kare dizisi → per-frame FrameSig listesi (sinyaller + füzyon + hareket + smooth)."""
    n = len(frames_bgr)
    if n == 0:
        return []
    H, W = frames_bgr[0].shape[:2]
    hann = _hann2d(H, W)
    S_LO = S_LO_FRAC * H
    wrap = WRAP_CLIP_FRAC

    grays: list[np.ndarray] = []
    masks: list[np.ndarray] = []
    sigs: list[FrameSig] = []

    # --- statik sinyaller ---
    for i, fr in enumerate(frames_bgr):
        g = _prep_gray(fr)
        grays.append(g)
        mask, n_blobs = _build_tophat_mask(g)
        masks.append(mask)
        total = g.shape[0] * g.shape[1]
        text_ratio = float(np.count_nonzero(mask)) / max(1, total)
        row_struct = float(_row_structure_score(mask, np))
        dark_ratio = float((g < 34).sum()) / max(1, total)
        heur = _clamp01(
            0.45 * min(1.0, n_blobs / 6.0)
            + 0.35 * min(1.0, text_ratio / 0.012)
            + 0.20 * row_struct
        ) + 0.05 * min(1.0, dark_ratio / 0.35)
        heur = _clamp01(heur)
        sigs.append(FrameSig(idx=i, n_blobs=int(n_blobs), text_ratio=text_ratio,
                             row_struct=row_struct, dark_ratio=dark_ratio, heur=heur))

    # --- CLIP (toplu) ---
    clip_probs: Optional[list[float]] = None
    if clip_ctx is not None:
        try:
            clip_probs = _clip_scores(clip_ctx, frames_bgr)
        except Exception:
            clip_probs = None

    # --- füzyon ---
    for i, s in enumerate(sigs):
        cp = clip_probs[i] if clip_probs is not None else None
        s.clip = cp
        if cp is not None:
            cs = W_CLIP * cp + W_HEUR * s.heur
            if cp >= CLIP_ALLOW:                       # yumuşak-kapı: CLIP güçlü → kredi-var
                cs = max(cs, 0.55)
            if cp < CLIP_KILL and s.heur < HEUR_KILL:  # yumuşak-kill: ikisi de zayıf → kredi-yok
                cs = min(cs, 0.20)
            s.credit_score = _clamp01(cs)
        else:
            s.credit_score = s.heur

    # --- hareket (yazı vs arka-plan ayrıştırması) ---
    # HIZ: hareket yalnız YAZI-VAR karelerde anlamlı (bg etiketi sadece credit-present koşularda
    # kullanılır; bu koşular zaten yazı içerir). Yazısız footage karelerinde ağır LK'yı ATLA.
    for i in range(1, n):
        m_union = cv2.bitwise_or(masks[i - 1], masks[i])
        s = sigs[i]
        if int((m_union > 0).sum()) < 20:
            continue
        # YAZI: dar maske bandında faz-kor
        g0 = _masked_gray(grays[i - 1], m_union)
        g1 = _masked_gray(grays[i], m_union)
        tdx, tdy, tresp = _phase_corr(g0, g1, hann)
        if abs(tdy) <= wrap * H and abs(tdx) <= wrap * W:
            s.text_dy, s.text_resp = float(tdy), float(tresp)
        # ARKA-PLAN HAREKETİ: full-frame faz-kor yüksek-kontrast SABİT yazıya kilitleniyor
        # (yazı %9 alanda bile cross-power'a hâkim, dx→0 yanlış 'bg sabit'); maske-sıfırlama da
        # statik-delik yaratıyor. ÇÖZÜM → yalnız YAZI-DIŞI bölgeden seyrek optik-akış (LK): metni
        # doğal olarak yok sayar, özelliksiz (siyah) zeminde özellik bulunamaz → bg sabit varsayılır.
        dil = cv2.dilate(m_union, np.ones((TEXT_DILATE_K, TEXT_DILATE_K), np.uint8))
        inv = cv2.bitwise_not(dil)
        cover = float((inv > 0).sum()) / max(1, inv.size)   # yazı-DIŞI alan oranı
        s.bg_reliable = cover >= BG_COVER_MIN
        if s.bg_reliable:
            pts = cv2.goodFeaturesToTrack(grays[i - 1], mask=inv, maxCorners=120,
                                          qualityLevel=0.05, minDistance=8, blockSize=7)
            if pts is not None and len(pts) >= 6:
                nxt, st, _err = cv2.calcOpticalFlowPyrLK(
                    grays[i - 1], grays[i], pts, None, winSize=(21, 21), maxLevel=2,
                    criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 20, 0.03))
                if nxt is not None and st is not None:
                    keep = st.ravel().astype(bool)
                    if int(keep.sum()) >= 6:
                        bdx = float(np.median(nxt[keep, 0, 0] - pts[keep, 0, 0]))
                        bdy = float(np.median(nxt[keep, 0, 1] - pts[keep, 0, 1]))
                        if abs(bdx) <= wrap * W and abs(bdy) <= wrap * H:
                            s.bg_dx, s.bg_dy = bdx, bdy
                            s.bg_resp = float(keep.sum()) / max(1, len(pts))  # izlenen-oran = güven
        s.gdiff = float(_gdiff(grays[i - 1], grays[i]))

    # --- smooth + present ---
    cs_sm = _med_smooth([s.credit_score for s in sigs])
    tdy_sm = _med_smooth([s.text_dy for s in sigs])
    bdx_sm = _med_smooth([s.bg_dx for s in sigs])
    bdy_sm = _med_smooth([s.bg_dy for s in sigs])
    gd_sm = _med_smooth([s.gdiff for s in sigs])
    for i, s in enumerate(sigs):
        s.credit_score = float(cs_sm[i])
        s.text_dy = float(tdy_sm[i])
        s.bg_dx = float(bdx_sm[i])
        s.bg_dy = float(bdy_sm[i])
        s.gdiff = float(gd_sm[i])
        s.present = s.credit_score >= PRESENT_THR
    return sigs


# --------------------------------------------------------------------------- #
# Koşu (run) bulma + 4-tip sınıflandırma
# --------------------------------------------------------------------------- #
def _runs_of(present: list[bool], gap: int = RUN_GAP, minlen: int = RUN_MINLEN) -> list[tuple[int, int]]:
    idx = [i for i, p in enumerate(present) if p]
    if not idx:
        return []
    runs = []
    cur = [idx[0]]
    for j in idx[1:]:
        if j - cur[-1] <= gap:
            cur.append(j)
        else:
            runs.append((cur[0], cur[-1]))
            cur = [j]
    runs.append((cur[0], cur[-1]))
    return [(a, b) for a, b in runs if b - a + 1 >= minlen]


def _classify_run(sigs: list[FrameSig], a: int, b: int, H: int) -> dict:
    """Koşuyu 4-tipe sınıflandır + geçerlilik (FP kalkanları) + güven.

    BAŞLANGIÇ-KIRPMA: start/end gerçek METİN-yapısı (n_blobs≥START_NBLOB & row_struct≥START_ROW) olan
    ilk/son kareye kırpılır → CLIP-footage sızıntısı atılır (KAOS 92→104). Koşuda yeterli gerçek-metin
    karesi yoksa = CLIP-only footage → geçersiz (no_text_structure).
    """
    text_idx = [i for i in range(a, b + 1)
                if sigs[i].n_blobs >= START_NBLOB and sigs[i].row_struct >= START_ROW]
    enough_text = len(text_idx) >= MIN_TEXT_FRAMES
    if enough_text:
        a, b = text_idx[0], text_idx[-1]   # gerçek-metin aralığına kırp (footage prefix/suffix at)
    run = sigs[a:b + 1]
    # BAŞLANGIÇ-GERİ-ÇEKME (Çağatay kuralı): geç-başlama=YASAK, erken=SERBEST. Rapor edilen start'ı ÖNCEKİ
    # kredi-ÖĞESİNE çek — öğeler-arası boşlukları (siyah kareler) GEÇ, BACK_GAP ardışık SAF-footage gelince dur.
    # Öğe = GERÇEK METİN-YAPISI (n_blobs+row_struct). cs/clip KULLANMA: CLIP footage'ı şişirir, geri-kaçırır.
    # Erken kredi-öğeleri (logo/başlık/isim) GÖRÜNÜR yazıdır → text-yapısı taşır; footage taşımaz. start_back
    # YALNIZ rapor; sınıflandırma [a,b]'de kalır.
    def _is_credit_elem(s):
        return s.n_blobs >= START_NBLOB and s.row_struct >= START_ROW
    start_back = a
    gap = 0
    i = a - 1
    while i >= 0 and (a - i) <= BACK_CAP:
        if _is_credit_elem(sigs[i]):
            start_back = i          # öğe bulundu → buraya kadar geri in
            gap = 0
        else:
            gap += 1
            if gap > BACK_GAP:      # BACK_GAP ardışık footage → kredi-sekansı bitti, dur
                break
        i -= 1
    start_back = max(0, start_back - BACK_SAFETY)   # +1s film emniyet payı
    S_HI = S_HI_FRAC * H
    S_LO = S_LO_FRAC * H
    BG_THR = BG_THR_FRAC * H

    med_cs = float(median([s.credit_score for s in run]))
    med_row = float(median([s.row_struct for s in run]))
    med_nblob = float(median([s.n_blobs for s in run]))
    clip_vals = [s.clip for s in run if s.clip is not None]
    med_clip = float(median(clip_vals)) if clip_vals else None
    min_clip = float(min(clip_vals)) if clip_vals else None   # koşunun EN ZAYIF karesi (tekdüzelik göstergesi)

    # --- yazı hareketi (işaret-oylama) ---
    text_dys = [s.text_dy for s in run]
    med_tdy = float(median(text_dys))
    signed = [1 if d > 0 else -1 for d in text_dys if abs(d) >= S_LO]
    consist = (max(signed.count(1), signed.count(-1)) / len(signed)) if signed else 0.0
    med_tresp = float(median([s.text_resp for s in run]))
    per_frame_moving = [abs(s.text_dy) >= S_HI for s in run]
    frac_moving = sum(per_frame_moving) / len(run)
    text_moving = (abs(med_tdy) >= S_HI and consist >= SIGN_CONSIST_MIN and med_tresp >= RESP_MIN)

    # --- arka-plan hareketi ---
    bg_rel = (sum(1 for s in run if s.bg_reliable) / len(run)) >= 0.5
    med_bdx = float(median([abs(s.bg_dx) for s in run]))
    med_bdy = float(median([abs(s.bg_dy) for s in run]))
    med_bresp = float(median([s.bg_resp for s in run]))
    med_gd = float(median([s.gdiff for s in run]))
    bg_dir = (max(med_bdx, med_bdy) >= BG_THR and med_bresp >= RESP_MIN and bg_rel)
    # gdiff yedeği yalnız bg GÜVENİLİR iken (yazı azınlıkta → gdiff arka-planı yansıtır,
    # yazı-hareketini değil); güvenilmezse uydurma bg-hareketi üretme.
    bg_moving = bool(bg_dir or (bg_rel and med_gd >= G_THR))

    # --- geçerlilik (FP kalkanları) ---
    valid = True
    reason = ""
    # #1 CLIP-only footage: gerçek metin-yapısı yok (KAOS uçak/çöl, ALTINCI/FIRINCININ footage'ı) → düş
    if not enough_text:
        valid, reason = False, "no_text_structure"
    # #2 dokulu footage: row_struct çok düşük → CLIP teyidi yoksa düş
    if valid and med_row < RUN_ROWSTRUCT_MIN and not (med_clip is not None and med_clip >= RUN_CLIP_RESCUE):
        valid, reason = False, "low_row_struct"
    # #3 statik tek-satır altyazı/tabela: hareketsiz + az blob → CLIP teyidi yoksa düş
    if valid and (not text_moving) and med_nblob < STATIC_NBLOB_MIN \
            and not (med_clip is not None and med_clip >= RUN_CLIP_RESCUE):
        valid, reason = False, "static_too_few_blobs"
    # #4 kısa koşu (n<RUN_MINLEN): normalde elenir AMA cs+CLIP ikisi de güçlüyse GEÇERLİ
    # (brief title-card kurtarma; footage-blip her iki eşiği birden geçemez). Aksi → near-miss adayı.
    too_short = (b - a + 1) < RUN_MINLEN
    if valid and too_short:
        # HER kare güçlü-kredi olmalı (tekdüzelik): gerçek title-card min_clip=1.0; diegetik tabela düşer
        strong = (med_cs >= SHORT_STRONG_CS and min_clip is not None and min_clip >= SHORT_STRONG_MINCLIP)
        if not strong:
            valid, reason = False, "too_short"

    # --- 4-tip etiket ---
    if MIXED_LO < frac_moving < MIXED_HI:
        quad = "mixed"
    elif text_moving and bg_moving:
        quad = "bg_moving_text_scroll"
    elif text_moving and not bg_moving:
        quad = "bg_static_text_scroll"
    elif (not text_moving) and bg_moving:
        quad = "bg_moving_text_static"
    else:
        quad = "bg_static_text_static"
    coarse = "scroll" if (text_moving or quad == "mixed") else "static"

    return {
        "start_frame": start_back, "end_frame": b, "n_frames": b - a + 1,
        "valid": valid, "invalid_reason": reason, "too_short": bool(too_short),
        "quad_type": quad, "type": coarse,
        "text_motion": bool(text_moving), "bg_motion": bool(bg_moving),
        "scroll_dy_px": round(med_tdy, 3), "sign_consistency": round(consist, 3),
        "frac_moving": round(frac_moving, 3),
        "confidence": round(med_cs, 4),
        "med_row_struct": round(med_row, 3), "med_n_blobs": round(med_nblob, 1),
        "med_clip": (round(med_clip, 3) if med_clip is not None else None),
        "min_clip": (round(min_clip, 3) if min_clip is not None else None),
        "low_conf": bool(med_cs < LOW_CONF),
    }


def _pick_run(runs_meta: list[dict], n_frames: int, prefer: str) -> Optional[dict]:
    """Birden çok geçerli koşudan birini seç: uzunluk + konum(prefer) + kalite."""
    valid = [r for r in runs_meta if r["valid"]]
    if not valid:
        return None

    def score(r: dict) -> float:
        length_w = r["n_frames"] / max(1, n_frames)
        if prefer == "first":
            pos_w = 1.0 - (r["start_frame"] / max(1, n_frames))
        elif prefer == "last":
            pos_w = r["end_frame"] / max(1, n_frames)
        else:
            pos_w = 0.5
        quality = r["confidence"]
        return 0.20 * length_w + 0.55 * pos_w + 0.25 * quality

    return max(valid, key=score)


def _select_region(runs_meta: list[dict], n_frames: int, prefer: str, *,
                   fps: float, window_start_sec: float) -> dict:
    """Geçerli koşuyu seç + NEAR-MISS ekle (seçilmemiş en güçlü kredi-bloğu).

    near_miss = "ne kaybediyoruz" görünürlüğü: koşu-yok/ret durumunda en güçlü reddedilen
    blok raporlanır. reason='too_short' ise kurtarılabilir kısa-title; düşük cs+clip ise
    gerçekten footage (kayıp yok). Sessiz düşürme yok.
    """
    chosen = _pick_run(runs_meta, n_frames, prefer)
    region = _region_dict(chosen, fps=fps, window_start_sec=window_start_sec)
    rejected = [r for r in runs_meta if not r["valid"]]
    if rejected:
        best = max(rejected, key=lambda r: (r["confidence"], r["n_frames"]))
        # "kurtarılabilir": too_short + HER karesi güçlü-kredi (min_clip yüksek) = gerçek title.
        # diegetik tabela/footage: med_clip yüksek olsa da min_clip düşer → "belirsiz".
        mn = best.get("min_clip")
        recoverable = (best["invalid_reason"] == "too_short" and mn is not None and mn >= SHORT_STRONG_MINCLIP)
        region["near_miss"] = {
            "start_frame": best["start_frame"], "end_frame": best["end_frame"],
            "n_frames": best["n_frames"], "quad_type": best["quad_type"],
            "confidence": best["confidence"], "med_clip": best["med_clip"], "min_clip": mn,
            "reason": best["invalid_reason"], "too_short": best.get("too_short", False),
            "recoverable": bool(recoverable),
            "start_sec": round(window_start_sec + best["start_frame"] / fps, 3),
        }
    else:
        region["near_miss"] = None
    return region


def _region_dict(r: Optional[dict], *, fps: float, window_start_sec: float) -> dict:
    """Seçilen koşu → çıktı bölgesi (geriye-uyumlu şema)."""
    if r is None:
        return {"found": False, "type": "none", "quad_type": "none",
                "start_sec": 0.0, "end_sec": 0.0, "start_frame": None, "end_frame": None,
                "bg_motion": False, "text_motion": False, "confidence": 0.0,
                "low_conf": True, "strategy": "jenerik_detect_v1"}
    sf, ef = r["start_frame"], r["end_frame"]
    return {
        "found": True, "type": r["type"], "quad_type": r["quad_type"],
        "start_sec": round(window_start_sec + sf / fps, 3),
        "end_sec": round(window_start_sec + (ef + 1) / fps, 3),
        "start_frame": int(sf), "end_frame": int(ef),
        "bg_motion": r["bg_motion"], "text_motion": r["text_motion"],
        "scroll_dy_px": r["scroll_dy_px"], "frac_moving": r["frac_moving"],
        "confidence": r["confidence"], "low_conf": r["low_conf"],
        "med_clip": r["med_clip"], "strategy": "jenerik_detect_v1",
    }


def analyze(frames_bgr: list[np.ndarray], *, clip_ctx: Optional[dict] = None) -> tuple[list[FrameSig], list[dict]]:
    """Çekirdek: kareler → (per-frame sigs, koşu-meta listesi)."""
    sigs = score_sequence(frames_bgr, clip_ctx=clip_ctx)
    if not sigs:
        return [], []
    H = frames_bgr[0].shape[0]
    runs = _runs_of([s.present for s in sigs], minlen=RAW_MINLEN)  # kısa koşuları da sınıflandır
    runs_meta = [_classify_run(sigs, a, b, H) for a, b in runs]
    return sigs, runs_meta


# --------------------------------------------------------------------------- #
# Kare-klasörü girdisi
# --------------------------------------------------------------------------- #
def _read_frame_dir(frame_dir: Path, *, analyze_h: int = 0) -> list[np.ndarray]:
    paths = sorted(Path(frame_dir).glob("*.png"))
    if not paths:
        paths = sorted(Path(frame_dir).glob("*.jpg"))
    frames = []
    for p in paths:
        img = _cv2_imread(p, cv2)
        if img is None:
            continue
        if analyze_h and img.shape[0] != analyze_h:
            sc = analyze_h / img.shape[0]
            img = cv2.resize(img, (max(1, int(img.shape[1] * sc)), analyze_h), interpolation=cv2.INTER_AREA)
        frames.append(img)
    return frames


def is_credit_text_line(s: str) -> bool:
    """OCR satırı kredi-ismi/rol/logo mu? footage'ta yazı yok → False (geri-çekme footage'a kaçmaz).
    Uzun cümle / nokta-bitiş = altyazı/diyalog/EPİLOG → kredi DEĞİL (KOVAN '...running her business
    successfully.' elenir; 'Written and directed by Blerta Basholli' (5 kelime) tutulur)."""
    t = (s or "").strip()
    if len(t) < 3:
        return False
    nonsp = [c for c in t if not c.isspace()]
    if not nonsp or (sum(c.isalpha() for c in nonsp) / len(nonsp)) < 0.5:   # rakam/sembol gürültü
        return False
    if sum(c.isalpha() for c in t) < 3:
        return False
    w = t.split()
    if len(w) >= 6 or t.rstrip().endswith("."):                            # cümle/altyazı/epilog
        return False
    return True


def refine_start_ocr(start_frame: int, lines_at, *, back_gap: int = OCR_BACK_GAP,
                     back_cap: int = OCR_BACK_CAP, safety: int = OCR_SAFETY) -> int:
    """start_frame'den GERİYE OCR ile yürü: kredi-satırı okudukça geri in (boşluk-toleranslı: kartlar-arası
    siyah kareleri geç); back_gap ardışık kredi-SİZ kare → footage/epilog-boşluğu = sınır, dur. footage'a
    kaçmaz (orada yazı yok). lines_at(idx)->list[str]. Döner: inceltilmiş start (≥0, yalnız ERKEN'e çeker)."""
    start = start_frame
    gap = 0
    i = start_frame - 1
    while i >= 0 and (start_frame - i) <= back_cap:
        try:
            has = any(is_credit_text_line(x) for x in lines_at(i))
        except Exception:
            has = False
        if has:
            start, gap = i, 0
        else:
            gap += 1
            if gap > back_gap:
                break
        i -= 1
    return max(0, start - safety)


def refine_end_ocr(end_frame: int, n_frames: int, lines_at, *, back_gap: int = OCR_BACK_GAP,
                   back_cap: int = OCR_BACK_CAP, safety: int = OCR_SAFETY) -> int:
    """GİRİŞ jeneriği için TERS yön: end_frame'den İLERİ OCR ile yürü — kredi-satırı okudukça ileri git
    (boşluk-toleranslı: kartlar-arası siyahları geç); back_gap ardışık kredi-SİZ kare → FİLM başladı = sınır,
    dur. lines_at(idx)->list[str]. Döner: inceltilmiş end (yalnız İLERİ'ye, ≤ n_frames-1, +safety film payı).
    Filmden sonrası = end+1 (kredinin son soluk karesini kaçırmamak için biraz filme taşar)."""
    end = end_frame
    gap = 0
    i = end_frame + 1
    while i < n_frames and (i - end_frame) <= back_cap:
        try:
            has = any(is_credit_text_line(x) for x in lines_at(i))
        except Exception:
            has = False
        if has:
            end, gap = i, 0
        else:
            gap += 1
            if gap > back_gap:
                break
        i += 1
    return min(n_frames - 1, end + safety)


# OCR-KALKAN (KN-2/3/4, Çağatay 2026-06-22): heuristik primitif (_build_tophat_mask) footage dokusunu
# sahte "metin satırı" sanıyor; FP-kalkanları aynı sahte sinyale bakıyor / CLIP-rescue ile bypass ediliyor
# → saf-footage giriş/çıkış FALSE_POSITIVE. Tek sağlam ayraç OCR-doğrulaması. Seçilen bölgenin ÇEKİRDEK
# karelerinde HİÇBİR kredi-satırı (is_credit_text_line) yoksa = footage → geçersiz kıl. KONSERVATİF:
# yalnız SIFIR kredi-satırında (N-eşiği YOK) → gerçek krediyi atma riski minimum.
# Flag MITAS_JENERIK_OCR_GATE: A/B sonucu default'u belirler. OFF iken kod tamamen INERT (davranış değişmez).
OCR_GATE_CORE_SAMPLES = 15      # çekirdek karelerden en fazla bu kadar (eşit-aralık) örnekle


def _ocr_gate_has_credit_text(region: dict, frames_bgr: list, lines_at,
                              *, max_samples: int = OCR_GATE_CORE_SAMPLES) -> bool:
    """Bölgenin start_frame..end_frame ÇEKİRDEĞİNDEN ≤max_samples kareyi eşit-aralık örnekle, lines_at
    cache'iyle OCR oku. HERHANGİ bir karede is_credit_text_line==True ise True (kredi var). frames
    geçersiz/boş ise GÜVENLİ taraf True (footage diye atma)."""
    sf = region.get("start_frame")
    ef = region.get("end_frame")
    if sf is None or ef is None:
        return True
    sf, ef = int(sf), int(ef)
    sf = max(0, min(sf, len(frames_bgr) - 1))
    ef = max(0, min(ef, len(frames_bgr) - 1))
    if ef < sf:
        return True
    span = ef - sf + 1
    if span <= max_samples:
        idxs = list(range(sf, ef + 1))
    else:
        step = (span - 1) / float(max_samples - 1)
        idxs = sorted({int(round(sf + i * step)) for i in range(max_samples)})
    for idx in idxs:
        try:
            if any(is_credit_text_line(x) for x in lines_at(idx)):
                return True
        except Exception:
            continue
    return False


def _ocr_gate_enabled() -> bool:
    # A/B SONUCU: default OFF (inert) bırakıldı (FP-küme footage'ında is_credit_text_line yine de
    # kredi-satırı buluyor → gate footage'ı temizlemiyor; bkz JENERIK_FIX_AB_2026-06-22.md). ON yapmak
    # için MITAS_JENERIK_OCR_GATE=1.
    return os.environ.get("MITAS_JENERIK_OCR_GATE", "").strip().lower() in ("1", "true", "on", "yes")


def _open_bridge_enabled() -> bool:
    """Açılış köprü flag: dağınık-geç kredi kartlarını (studio/yönetmen) köprülemek için büyük back_gap.
    DEFAULT OFF — MITAS_JENERIK_OPEN_BRIDGE=1 ile etkinleştir. Flag OFF iken _apply_ocr_refine_end INERT."""
    return os.environ.get("MITAS_JENERIK_OPEN_BRIDGE", "").strip().lower() in ("1", "true", "on", "yes")


def _apply_ocr_refine(region: dict, frames_bgr: list, ocr_read_fn, *,
                      fps: float, window_start_sec: float) -> dict:
    """Bölgenin start_frame'ini OCR-geriye ile inceltir (asıl TOO_LATE fix). ocr_read_fn(bgr)->satırlar.
    Yalnız ERKEN'e çeker; start_sec yeniden hesaplanır. ocr_read_fn None ise dokunmaz (sezgisel geri-çekme kalır).
    OCR-KALKAN (flag MITAS_JENERIK_OCR_GATE): çekirdekte HİÇ kredi-satırı yoksa bölgeyi geçersiz kıl (footage-FP)."""
    if ocr_read_fn is None or not region.get("found") or region.get("start_frame") is None:
        return region
    sf = int(region["start_frame"])
    cache: dict = {}

    def lines_at(idx):
        if idx not in cache:
            cache[idx] = ocr_read_fn(frames_bgr[idx]) or []
        return cache[idx]

    # OCR-KALKAN: refine'den ÖNCE çalışır; cache refine ile paylaşılır (ekstra OCR maliyeti küçük).
    if _ocr_gate_enabled() and not _ocr_gate_has_credit_text(region, frames_bgr, lines_at):
        region = dict(region)
        region["found"] = False
        region["invalid_reason"] = "no_credit_text_in_core"
        return region

    new_sf = refine_start_ocr(sf, lines_at)
    if new_sf < sf:
        region = dict(region)
        region["ocr_refined_from"] = sf
        region["start_frame"] = int(new_sf)
        region["start_sec"] = round(window_start_sec + new_sf / fps, 3)
    return region


def _apply_ocr_refine_end(region: dict, frames_bgr: list, ocr_read_fn, *,
                          fps: float, window_start_sec: float) -> dict:
    """GİRİŞ jeneriği: end_frame'i OCR-İLERİ ile inceltir (jenerik SONU = FİLM başı). ocr_read_fn(bgr)->satırlar.
    Yalnız İLERİ'ye taşır; end_sec yeniden hesaplanır; film_start_frame/sec eklenir (= end+1)."""
    if ocr_read_fn is None or not region.get("found") or region.get("end_frame") is None:
        return region
    ef = int(region["end_frame"])
    cache: dict = {}

    def lines_at(idx):
        if idx not in cache:
            cache[idx] = ocr_read_fn(frames_bgr[idx]) or []
        return cache[idx]

    # Köprü fix (MITAS_JENERIK_OPEN_BRIDGE): flag ON → geniş back_gap ile geç-bloklara köprü kur.
    # Flag OFF → mevcut çağrı (back_gap=OCR_BACK_GAP=4, back_cap=OCR_BACK_CAP=120) — tamamen INERT.
    if _open_bridge_enabled():
        new_ef = refine_end_ocr(ef, len(frames_bgr), lines_at,
                                back_gap=OPEN_END_BACK_GAP, back_cap=OPEN_END_BACK_CAP)
    else:
        new_ef = refine_end_ocr(ef, len(frames_bgr), lines_at)
    if new_ef > ef:
        region = dict(region)
        region["ocr_refined_end_from"] = ef
        region["end_frame"] = int(new_ef)
        region["end_sec"] = round(window_start_sec + (new_ef + 1) / fps, 3)
    # film başı = jenerik bitişinden hemen sonra (her durumda raporla)
    fsf = int(region["end_frame"]) + 1
    region = dict(region)
    region["film_start_frame"] = fsf
    region["film_start_sec"] = round(window_start_sec + fsf / fps, 3)
    return region


def detect_from_frames(frame_dir: str | Path, *, fps: float = 2.0, window_start_sec: float = 0.0,
                       prefer: str = "first", clip_ctx: Optional[dict] = None,
                       ocr_read_fn=None, return_debug: bool = False) -> dict:
    """Tek kare-klasörü → bölge dict. prefer='first' (giriş) / 'last' (çıkış).
    ocr_read_fn verilirse: çıkış→start OCR-geriye; giriş→end OCR-ileri (jenerik sonu=film başı)."""
    frames = _read_frame_dir(Path(frame_dir))
    if not frames:
        out = _region_dict(None, fps=fps, window_start_sec=window_start_sec)
        out["reason"] = "no_frames"
        return (out, [], []) if return_debug else out
    sigs, runs_meta = analyze(frames, clip_ctx=clip_ctx)
    out = _select_region(runs_meta, len(frames), prefer, fps=fps, window_start_sec=window_start_sec)
    out = _apply_ocr_refine(out, frames, ocr_read_fn, fps=fps, window_start_sec=window_start_sec)
    if prefer == "first":   # GİRİŞ: jeneriğin bittiği (film başladığı) anı da bul (ileri yürü)
        out = _apply_ocr_refine_end(out, frames, ocr_read_fn, fps=fps, window_start_sec=window_start_sec)
    return (out, sigs, runs_meta) if return_debug else out


def detect_film_frames(film_dir: str | Path, *, fps: float = 2.0,
                       clip_ctx: Optional[dict] = None, ocr_read_fn=None,
                       parallel: bool = False, ocr_factory=None) -> dict:
    """Bir film klasörü → {opening, closing} (frames/giris → ilk koşu, frames/cikis → son koşu).
    parallel=True: giriş+çıkış 2 thread'de eşzamanlı (bağımsız veri; CLIP lock'lu, OCR ayrı motor).
    ocr_factory() çağrılınca TAZE bir ocr_read_fn üretmeli (her thread kendi OneOCR motoru — thread-güvenli)."""
    fd = Path(film_dir)
    giris = fd / "frames" / "giris"
    cikis = fd / "frames" / "cikis"
    none_reg = lambda: _region_dict(None, fps=fps, window_start_sec=0.0)

    if parallel:
        import concurrent.futures
        ocr_g = ocr_factory() if ocr_factory else ocr_read_fn   # her thread KENDİ OCR motoru
        ocr_c = ocr_factory() if ocr_factory else ocr_read_fn
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
            fg = (ex.submit(detect_from_frames, giris, fps=fps, prefer="first", clip_ctx=clip_ctx, ocr_read_fn=ocr_g)
                  if giris.is_dir() else None)
            fc = (ex.submit(detect_from_frames, cikis, fps=fps, prefer="last", clip_ctx=clip_ctx, ocr_read_fn=ocr_c)
                  if cikis.is_dir() else None)
            opening = fg.result() if fg else none_reg()
            closing = fc.result() if fc else none_reg()
        return {"opening": opening, "closing": closing}

    opening = (detect_from_frames(giris, fps=fps, prefer="first", clip_ctx=clip_ctx, ocr_read_fn=ocr_read_fn)
               if giris.is_dir() else none_reg())
    closing = (detect_from_frames(cikis, fps=fps, prefer="last", clip_ctx=clip_ctx, ocr_read_fn=ocr_read_fn)
               if cikis.is_dir() else none_reg())
    return {"opening": opening, "closing": closing}


# --------------------------------------------------------------------------- #
# Video girdisi (aynı çekirdek; entegrasyon için)
# --------------------------------------------------------------------------- #
def _resize_h(fr: np.ndarray, analyze_h: int) -> np.ndarray:
    if analyze_h and fr.shape[0] != analyze_h:
        sc = analyze_h / fr.shape[0]
        fr = cv2.resize(fr, (max(1, int(fr.shape[1] * sc)), analyze_h), interpolation=cv2.INTER_AREA)
    return fr


def _sample_video_seek(cap: Any, t0: float, t1: float, fps: float, analyze_h: int = ANALYZE_H) -> list[np.ndarray]:
    """REFERANS (yavaş): kare-başına POS_MSEC seek. Yalnız hız/veri-kaybı doğrulaması için tutulur."""
    frames = []
    step = 1.0 / max(0.1, fps)
    t = float(t0)
    while t < float(t1):
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000.0)
        ok, fr = cap.read()
        if ok and fr is not None:
            frames.append(_resize_h(fr, analyze_h))
        t += step
    return frames


def _sample_video(cap: Any, t0: float, t1: float, fps: float, analyze_h: int = ANALYZE_H) -> list[np.ndarray]:
    """HIZLI: pencereye TEK seek + ardışık grab(); her stride-inci kareyi retrieve.
    Kare-başına seek YOK → uzun videoda ~seek-sayısı kadar hızlanma. Aynı kareleri verir
    (stride = native/fps), veri kaybı yok — _jenerik_speedcheck.py ile doğrulandı.
    """
    native = float(cap.get(cv2.CAP_PROP_FPS) or 25.0)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    stride = max(1, int(round(native / max(0.1, fps))))
    f0 = max(0, int(float(t0) * native))
    f1 = int(float(t1) * native) if t1 else (total or f0 + 10 ** 9)
    if total:
        f1 = min(f1, total)
    if f0 > 0:
        cap.set(cv2.CAP_PROP_POS_FRAMES, float(f0))   # TEK seek (kare-başına değil)
    frames: list[np.ndarray] = []
    rel = 0
    while f0 + rel < f1:
        if not cap.grab():               # decode-skip: retrieve etmeden ilerle
            break
        if rel % stride == 0:
            ok, fr = cap.retrieve()
            if ok and fr is not None:
                frames.append(_resize_h(fr, analyze_h))
        rel += 1
    return frames


def detect_from_video(video: str | Path, *, fps: float = 2.0, open_search_min: float = 12.0,
                      close_search_min: float = 15.0, clip_ctx: Optional[dict] = None,
                      ocr_read_fn=None, parallel: bool = False, ocr_factory=None) -> dict:
    """Video → {opening, closing}. İlk N dk giriş, son N dk çıkış koşusu. ocr_read_fn verilirse:
    giriş→end OCR-İLERİ (film başı), çıkış→start OCR-GERİYE (örneklenen ANALYZE_H karelerde).
    parallel=True: giriş+çıkış 2 thread (her biri KENDİ VideoCapture + OCR motoru; CLIP lock'lu)."""
    probe = cv2.VideoCapture(str(video))
    if not probe.isOpened():
        no = _region_dict(None, fps=fps, window_start_sec=0.0)
        no["reason"] = "video_not_opened"
        return {"opening": dict(no), "closing": dict(no)}
    nfps = float(probe.get(cv2.CAP_PROP_FPS) or 25.0)
    total = int(probe.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    dur = total / nfps if total > 0 else 0.0
    probe.release()
    open_end = min(open_search_min * 60.0, dur) if dur > 0 else open_search_min * 60.0
    close_start = max(0.0, dur - close_search_min * 60.0) if dur > 0 else 0.0
    close_end = dur if dur > 0 else close_start + close_search_min * 60.0

    def _opening(ocr_fn):
        cap = cv2.VideoCapture(str(video))
        of = _sample_video(cap, 0.0, open_end, fps); cap.release()
        _, oruns = analyze(of, clip_ctx=clip_ctx)
        op = _select_region(oruns, len(of), "first", fps=fps, window_start_sec=0.0)
        op = _apply_ocr_refine(op, of, ocr_fn, fps=fps, window_start_sec=0.0)
        op = _apply_ocr_refine_end(op, of, ocr_fn, fps=fps, window_start_sec=0.0)   # GİRİŞ: film başı
        return op

    def _closing(ocr_fn):
        cap = cv2.VideoCapture(str(video))
        cf = _sample_video(cap, close_start, close_end, fps); cap.release()
        _, cruns = analyze(cf, clip_ctx=clip_ctx)
        cl = _select_region(cruns, len(cf), "last", fps=fps, window_start_sec=close_start)
        cl = _apply_ocr_refine(cl, cf, ocr_fn, fps=fps, window_start_sec=close_start)
        return cl

    if parallel:
        import concurrent.futures
        ocr_o = ocr_factory() if ocr_factory else ocr_read_fn   # her thread KENDİ OneOCR motoru
        ocr_c = ocr_factory() if ocr_factory else ocr_read_fn
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
            fo = ex.submit(_opening, ocr_o); fc = ex.submit(_closing, ocr_c)
            return {"opening": fo.result(), "closing": fc.result()}
    return {"opening": _opening(ocr_read_fn), "closing": _closing(ocr_read_fn)}
