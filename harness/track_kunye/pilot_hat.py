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
DHASH_ESIK = 6


def fold(s: str) -> str:
    s = unicodedata.normalize("NFKD", (s or "").lower())
    return "".join(c for c in s if not unicodedata.combining(c) and (c.isalnum() or c.isspace())).strip()


def dhash(im: np.ndarray, boyut: int = 8) -> int:
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

def havuz_derle(slug: str) -> list[Path]:
    yollar = sorted((EX / f"{slug}-exit_frames").glob("exit_*.png"))
    kalan: list[Path] = []
    onceki_h: int | None = None
    for p in yollar:
        im = cv2.imread(str(p))
        if im is None:
            continue
        h = dhash(im)
        if onceki_h is not None and hamming(h, onceki_h) <= DHASH_ESIK:
            continue                      # statik kopya / neredeyse özdeş
        onceki_h = h
        kalan.append(p)
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
