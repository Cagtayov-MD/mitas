#!/usr/bin/env python3
"""PILOT HAT — 5 film, 4 katman: havuz → deepseek-ocr → qwen-yapılandır → KB-doğrula.

Katman 1 HAVUZ (OCR'sız, det-kör'de de çalışır):
  dhash ardışık-dedup (statik kartın kopyaları düşer) → 40 tavanına linspace
  inceltme (TÜM aralık kapsanır — dünkü [:n] kuyruk-kesme bug'ı burada yok).
Katman 2 OKU: deepseek-ocr "Free OCR." sayfa sayfa; sayfalar arası fold-dedup.
Katman 3 YAPILANDIR: qwen3-vl'e GÖRÜNTÜSÜZ, dökümü metin olarak ver.
Katman 4 DOĞRULA: KB (mitas_people_index) fold-eşleşme + Paddle-track kesişimi
  → satır işaretleri: [KB] [2K] (iki kaynak) [!] (tek kaynak, insan baksın).
"""
from __future__ import annotations
import base64, difflib, json, sys, time, unicodedata, urllib.request
from pathlib import Path

import cv2
import numpy as np

OLLAMA = "http://127.0.0.1:11434/api/generate"
S = Path(__file__).resolve().parent
EX = Path("/home/cagatay/Ex_Frame")
OUT = S / "pilot"
FILMLER = ["gercek-yalanlar", "karadeniz", "20-bulusma", "mufreze", "hayat-agaci"]
HAVUZ_TAVAN = 40
DHASH_ESIK_TABAN = 24   # yalnız GERI-DUSUS: film-bazlı eşik türetilemezse

def film_esigi(farklar: list[int]) -> int:
    """Film-bazlı otomatik eşik (2026-07-30 kök-sebep ölçümü: sabit eşik yapısal
    yanlış — hayat-agaci fark-dili 6-25, gercek-yalanlar 0-112). 1D Otsu ile
    statik/değişim kümelerini ayır; ayrım zayıfsa p25+2'ye düş (agresif-ALMA:
    kart kaçırmaktansa fazla sayfa oku)."""
    if len(farklar) < 8:
        return DHASH_ESIK_TABAN
    f = np.array(sorted(farklar), dtype=np.float64)
    en_iyi_esik, en_iyi_var = None, -1.0
    for t in range(int(f.min()) + 1, int(f.max())):
        sol, sag = f[f <= t], f[f > t]
        if len(sol) < 3 or len(sag) < 3:
            continue
        arasi = len(sol) * len(sag) * (sol.mean() - sag.mean()) ** 2
        if arasi > en_iyi_var:
            en_iyi_var, en_iyi_esik = arasi, t
    if en_iyi_esik is None:
        return max(2, int(np.percentile(f, 25)) + 2)
    sol, sag = f[f <= en_iyi_esik], f[f > en_iyi_esik]
    ayrim = (sag.mean() - sol.mean()) / (f.std() + 1e-6)
    if ayrim < 0.8:                        # bimodallik zayıf → güvenli taraf
        return max(2, int(np.percentile(f, 25)) + 2)
    return int(en_iyi_esik)


def fold(s: str) -> str:
    s = unicodedata.normalize("NFKD", (s or "").lower())
    return "".join(c for c in s if not unicodedata.combining(c) and (c.isalnum() or c.isspace())).strip()


def dhash(im: np.ndarray, boyut: int = 16) -> int:
    g = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY) if im.ndim == 3 else im
    k = cv2.resize(g, (boyut + 1, boyut), interpolation=cv2.INTER_AREA)
    h = 0
    for satir in (k[:, 1:] > k[:, :-1]).astype(np.uint8):
        for b in satir:
            h = (h << 1) | int(b)
    return h


def hamming(a: int, b: int) -> int:
    return bin(a ^ b).count("1")


def ollama_iste(model: str, prompt: str, imgs: list[str] | None = None,
                num_predict: int = 2048, num_ctx: int = 8192, timeout: int = 900) -> str:
    gov: dict = {"model": model, "prompt": prompt, "stream": False,
                 "options": {"temperature": 0.0, "num_predict": num_predict, "num_ctx": num_ctx}}
    if imgs:
        gov["images"] = imgs
    req = urllib.request.Request(OLLAMA, data=json.dumps(gov).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read()).get("response", "")


# ── Katman 1: havuz ─────────────────────────────────────────────────────────

def _yazi_var(gray: np.ndarray) -> bool:
    """Morfolojik metin-varlığı (OCR YOK — betikten bağımsız, Farsça dahil)."""
    try:
        import sys as _s
        if "/opt/mitas/OCR-worktree" not in _s.path:
            _s.path.insert(0, "/opt/mitas/OCR-worktree")
        import db_compose_master as _dc
        import types as _t
        a = _t.SimpleNamespace(tht=22, min_hold=5, polarity="auto")
        p = _dc.derive_params(gray.shape[0], gray.shape[1], a)
        return bool(_dc.has_text(_dc.text_mask(gray, p, a.polarity), p))
    except Exception:
        return True   # kapı çökerse KORU — "okunamadı > yanlış ele"


def _keskinlik(gray: np.ndarray) -> float:
    return float(cv2.Laplacian(gray, cv2.CV_32F).var())


def havuz_derle(slug: str) -> list[Path]:
    yollar = sorted((EX / f"{slug}-exit_frames").glob("exit_*.png"))
    # ÖN GEÇİŞ: tüm imzalar + ardışık farklar → film-bazlı eşik
    onbellek: list[tuple[Path, np.ndarray, int]] = []
    for p in yollar:
        im = cv2.imread(str(p))
        if im is not None:
            onbellek.append((p, cv2.cvtColor(im, cv2.COLOR_BGR2GRAY), dhash(im)))
    farklar = [hamming(onbellek[i][2], onbellek[i+1][2]) for i in range(len(onbellek)-1)]
    esik = film_esigi(farklar)
    kalan: list[Path] = []
    grup: list[tuple[Path, float]] = []    # aynı-içerik grubu: (yol, keskinlik)
    onceki_h: int | None = None

    def grubu_kapat():
        if grup:
            kalan.append(max(grup, key=lambda x: x[1])[0])   # en keskin temsilci
            grup.clear()

    for p, gray, h in onbellek:
        # Kapı kuralı (2026-07-30, hayat-agaci dersi 4→1): morfolojik maske de
        # düşük-kontrast betikte kör olabilir. TEK sinyalle eleme YOK:
        # "yazı gördüm" VEYA "içerik güçlü değişti" → kare aday olur.
        buyuk_degisim = onceki_h is not None and hamming(h, onceki_h) > 2 * esik
        if not _yazi_var(gray) and not buyuk_degisim and onceki_h is not None:
            continue                       # yazısız VE durağan → footage, ele
        if onceki_h is not None and hamming(h, onceki_h) <= esik:
            grup.append((p, _keskinlik(gray)))   # aynı kart — adayı biriktir
            continue
        grubu_kapat()
        onceki_h = h
        grup.append((p, _keskinlik(gray)))
    grubu_kapat()
    if len(kalan) > HAVUZ_TAVAN:          # linspace: BAŞ ve SON dahil tüm aralık
        idx = np.linspace(0, len(kalan) - 1, HAVUZ_TAVAN).round().astype(int)
        kalan = [kalan[i] for i in sorted(set(idx.tolist()))]
    return kalan


# ── Katman 2: deepseek-ocr sayfa sayfa ──────────────────────────────────────

def oku_deepseek(sayfalar: list[Path]) -> list[str]:
    satirlar: list[str] = []
    onceki: set[str] = set()
    for p in sayfalar:
        try:
            cevap = ollama_iste("deepseek-ocr:latest", "Free OCR.",
                                [base64.b64encode(p.read_bytes()).decode()], num_predict=2048)
        except Exception as e:
            print(f"    {p.name}: {type(e).__name__}", flush=True)
            continue
        yeni: set[str] = set()
        for ln in cevap.splitlines():
            ln = ln.strip().strip("`").lstrip("#").strip().strip("*").strip()
            f = fold(ln)
            if not ln or len(f) < 2:
                continue
            yeni.add(f)
            if f in onceki:
                continue
            if any(difflib.SequenceMatcher(None, f, o).ratio() >= 0.92 for o in onceki):
                continue
            satirlar.append(ln)
        onceki = yeni or onceki
    return satirlar


# ── Katman 3: qwen yapılandırma (metin → yapı) ──────────────────────────────

YAPI_PROMPT = """Aşağıda bir filmin çıkış jeneriğinden OCR ile çıkarılmış HAM döküm var.
Görevin bu dökümü YAPILANDIRMAK:
- Sırayı koru; hiçbir ismi ATMA, özetleme.
- Bariz OCR tekrarlarını (aynı satırın iki yazımı) TEKE indir.
- Rol/görev başlığı ile isim ayrıysa "GÖREV: İSİM" biçiminde eşleştir; oyuncu-karakter ise "KARAKTER — OYUNCU".
- Şüpheli/bozuk satırı olduğu gibi bırak ama sonuna (?) koy.
- SADECE yapılandırılmış listeyi yaz, yorum ekleme.

HAM DÖKÜM:
"""


def yapilandir(satirlar: list[str]) -> str:
    return ollama_iste("qwen3-vl:30b", YAPI_PROMPT + "\n".join(satirlar),
                       num_predict=16384, num_ctx=32768, timeout=1500)


# ── Katman 4: KB + Paddle-track doğrulama ───────────────────────────────────

def kb_yukle() -> set[str]:
    import duckdb
    con = duckdb.connect("/opt/mitas/Mitas_Files/MitaData/mitas.duckdb", read_only=True)
    adlar = {fold(r[0]) for r in con.execute(
        "SELECT DISTINCT name FROM main.mitas_people_index").fetchall() if r[0]}
    con.close()
    return adlar


def dogrula(yapili: str, slug: str, kb: set[str]) -> str:
    track_toks: set[str] = set()
    tk = S / "tkF" / slug / "kunye_track.txt"
    if tk.is_file():
        for l in tk.read_text(encoding="utf-8").splitlines():
            track_toks.update(fold(l.replace("|", " ")).split())
    cikti = []
    for ln in yapili.splitlines():
        ln = ln.rstrip()
        if not ln.strip():
            cikti.append(ln)
            continue
        f = fold(ln.split("—")[-1].split(":")[-1])
        isaret = []
        if f and f in kb:
            isaret.append("[KB]")
        toks = set(f.split())
        if toks and track_toks and len(toks & track_toks) / len(toks) >= 0.6:
            isaret.append("[2K]")
        if not isaret:
            isaret.append("[!]")
        cikti.append(f"{ln}  {' '.join(isaret)}")
    return "\n".join(cikti)


def main() -> int:
    OUT.mkdir(exist_ok=True)
    kb = kb_yukle()
    print(f"KB: {len(kb)} isim yüklendi", flush=True)
    dokumlar: dict[str, list[str]] = {}
    for slug in FILMLER:                      # önce TÜM deepseek (model takası 1 kez)
        t0 = time.time()
        sayfalar = havuz_derle(slug)
        d = OUT / slug
        d.mkdir(exist_ok=True)
        (d / "havuz.json").write_text(json.dumps([p.name for p in sayfalar]), encoding="utf-8")
        satirlar = oku_deepseek(sayfalar)
        (d / "deepseek_dokum.txt").write_text("\n".join(satirlar) + "\n", encoding="utf-8")
        dokumlar[slug] = satirlar
        print(f"[OKU] {slug:44s} havuz={len(sayfalar):3d} satir={len(satirlar):4d} {time.time()-t0:.0f}s", flush=True)
    for slug in FILMLER:                      # sonra TÜM qwen yapılandırma
        t0 = time.time()
        satirlar = dokumlar[slug]
        if not satirlar:
            print(f"[YAPI] {slug}: döküm boş — atlandı", flush=True)
            continue
        yapili = yapilandir(satirlar)
        final = dogrula(yapili, slug, kb)
        (OUT / slug / "kunye_final.txt").write_text(final + "\n", encoding="utf-8")
        n = len([l for l in final.splitlines() if l.strip()])
        tek = sum(1 for l in final.splitlines() if "[!]" in l)
        print(f"[YAPI] {slug:44s} final={n:4d} satir, tek-kaynak={tek:3d} {time.time()-t0:.0f}s", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
