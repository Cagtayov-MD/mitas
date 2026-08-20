#!/usr/bin/env python3
"""PILOT HAT — 5 film, 4 katman: havuz → deepseek-ocr → qwen-yapılandır → KB-doğrula.

Katman 1 HAVUZ (OCR'sız, det-kör'de de çalışır): kareleri griye çevirip
  havuz.py'nin çift-sinyal gruplamasına (havuz_derle + ikinci_gecis) devreder
  — kopya-mantık Task 8'de söküldü, tavan YOK (bkz. havuz.py docstring'i).
Katman 2 OKU: deepseek-ocr "Free OCR." sayfa sayfa; sayfalar arası fold-dedup.
Katman 3 YAPILANDIR: qwen3-vl'e GÖRÜNTÜSÜZ, dökümü metin olarak ver.
Katman 4 DOĞRULA: KB (mitas_people_index) fold-eşleşme + Paddle-track kesişimi
  → satır işaretleri: [KB] [2K] (iki kaynak) [!] (tek kaynak, insan baksın).
"""
from __future__ import annotations
import base64, difflib, json, os, sys, time, unicodedata, urllib.request
from pathlib import Path

import cv2
import numpy as np

# NASH KULESI — havuz algoritmasinin TEK kopyasi orada (Faz 3 sokumu,
# 2026-08-14). Eskiden burada `import messi as havuz_mod` vardi; messi.py ve
# steve_nash.py kulenin src/havuz.py'sinin kopyasiydi. Kopya kalkti: kulede
# duzelen bir sey uretimde de duzelir, uretimde cikan bir kusur kulede de
# gorunur. Kule DISARIDAN calisir gibi degil, dogrudan modul olarak ithal
# edilir — venvs/ocr ile kule venv'i ayni numpy/opencv surumunde (2.3.5/5.0.0).
_NASH_SRC = str(Path(os.environ.get("MITAS_PROJECT_ROOT", "/opt/mitas"))
                / "Allstar" / "nash" / "src")
if _NASH_SRC not in sys.path:
    sys.path.insert(0, _NASH_SRC)
import secim as nash_secim

OLLAMA = os.environ.get("MITAS_OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/") + "/api/generate"
KB_DUCKDB = os.environ.get("MITAS_KB_DUCKDB", "/opt/mitas/Mitas_Files/MitaData/mitas.duckdb")
S = Path(__file__).resolve().parent
EX = Path("/home/cagatay/Ex_Frame")
OUT = S / "pilot"
FILMLER = ["gercek-yalanlar", "karadeniz", "20-bulusma", "mufreze", "hayat-agaci"]
SON_HAVUZ_ISTATISTIK: dict = {}


def fold(s: str) -> str:
    s = unicodedata.normalize("NFKD", (s or "").lower())
    return "".join(c for c in s if not unicodedata.combining(c) and (c.isalnum() or c.isspace())).strip()


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

def havuz_derle_dizin(kare_dizin: Path, desen: str = "*.png") -> tuple[list[Path], dict]:
    """Uretim yuzeyi — govde NASH KULESINE devredildi (Faz 3, 2026-08-14).

    Imza ve donus bicimi DEGISMEDI: (secilen yollar, istatistik sozlugu).
    Cagiranlar (_pipe_hibrit_okuma, _pipe_track_kunye, olcum_yatagi_faz2)
    tek satir bile degistirmedi.
    """
    return nash_secim.havuz_derle_dizin(kare_dizin, desen)


def havuz_derle(slug: str) -> list[Path]:
    secim, ist = havuz_derle_dizin(EX / f"{slug}-exit_frames", "exit_*.png")
    global SON_HAVUZ_ISTATISTIK
    SON_HAVUZ_ISTATISTIK = {k: ist.get(k) for k in
                            ("esik", "grup", "alarm", "sayfa", "ikinci_gecis_ek")}
    return secim


# ── Katman 2: deepseek-ocr sayfa sayfa ──────────────────────────────────────

def oku_deepseek(sayfalar: list[Path], cagri_timeout: int = 900) -> list[str]:
    satirlar: list[str] = []
    onceki: set[str] = set()
    for p in sayfalar:
        try:
            cevap = ollama_iste("deepseek-ocr:latest", "Free OCR.",
                                [base64.b64encode(p.read_bytes()).decode()], num_predict=2048,
                                timeout=cagri_timeout)
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
    con = duckdb.connect(KB_DUCKDB, read_only=True)
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
        (d / "messi.json").write_text(json.dumps(
            {"sayfalar": [p.name for p in sayfalar],
             "istatistik": SON_HAVUZ_ISTATISTIK}, ensure_ascii=False), encoding="utf-8")
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


# ── RONALDO ghost katmanı bağları (2026-07-30 spec) ─────────────────────────
import ronaldo as rn_mod


def oku_master(master_png: Path, out_dir: Path, bant_h: int = 1100, bindirme: int = 120,
               cagri_timeout: int = 900) -> list[str]:
    """İbrahimovic master'ını dikey bantlara bölüp deepseek'le okur (tek-okuyucu kararı)."""
    im = cv2.imread(str(master_png))
    if im is None:
        return []
    bant_dir = out_dir / "master_bantlar"
    bant_dir.mkdir(parents=True, exist_ok=True)
    yollar = []
    y, i = 0, 0
    H = im.shape[0]
    while y < H:
        bant = im[y:min(y + bant_h, H)]
        if bant.shape[0] >= 40:
            p = bant_dir / f"bant_{i:03d}.png"
            cv2.imwrite(str(p), bant)
            yollar.append(p)
            i += 1
        if y + bant_h >= H:
            break
        y += bant_h - bindirme
    return oku_deepseek(yollar, cagri_timeout=cagri_timeout)


def ronaldo_kos(slug: str, out_dir: Path, messi_dokum: list[str], master_dokum: list[str],
                kb: set[str], kb_tok: set[str], kare_toplam: int | None,
                messi_kare: int | None, ibra_kare: int | None) -> dict:
    """Ronaldo'yu koştur, gölge çıktıları yaz, manifest alanlarını döndür."""
    r = rn_mod.capraz(messi_dokum, master_dokum, kb, kb_tok,
                      kare_toplam=kare_toplam, messi_kare=messi_kare, ibra_kare=ibra_kare)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "ronaldo_kunye.txt").write_text("\n".join(r.birlesik) + "\n", encoding="utf-8")
    (out_dir / "ronaldo_fark.json").write_text(
        json.dumps({**r.fark, "confidence_band": r.band, **r.bayraklar},
                   ensure_ascii=False, indent=1), encoding="utf-8")
    return {"film": slug, "confidence_band": r.band, **r.bayraklar,
            "birlesik_n": len(r.birlesik)}
