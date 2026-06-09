#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
credit_video_read.py — Jenerik (künye) okuma: VİDEO baş+son + 2-model ensemble + KB-fusion.

NEDEN bu yaklasim (2026-06-04, E:\\filmtest\\aaaa 12-film dogrulamasi):
  - Jenerik karelerini tek "master PNG"ye DİKMEK yerine, kareleri DOĞRUDAN
    bir VLM'e ARDIŞIK DİZİ (video semantigi, ollama /api/chat images[]) olarak veriyoruz.
    Stitch katmani kayipliydi (XMEN basligi düsüyor, AHLAT smear); video onu atlar.
  - BAŞ+SON ornekleme: uzun jenerikte yonetmen/yapimci/cast "billing" jeneriğin
    BAŞINDA (cast+producer) ve bazen SONUNDA (kapanis "Directed by" karti) olur;
    ortadaki dev crew scroll bizim icin gereksiz. Ilk END_WIN + son END_WIN kareye
    yogun ornek, ortayi atla. (JURASSIC yonetmeni basta, XMEN yonetmeni sonda -> ikisi de yakalandi.)
  - 2-MODEL ENSEMBLE: gemma4:26b (EN IYI tek model: 12-film 8/12 dogru, 0 yanlis, ~17GB rahat sigar)
    + qwen2.5vl:7b (kapsam + bol cast; nadiren yanlis/gurultulu). Tamamlayicilar; KB+mutabakat birlestirir.
    (qwen3-vl:30b denendi: 5/12 + 23GB'de sinirda/bazen bos -> gemma4:26b ile degistirildi. gemma4:e4b elendi: halusinasyon.)
  - KB-FUSION: imdb.duckdb meslekleriyle NET rol-uyumsuzlugunu REDDET (ornek: senaristi
    "yapimci" diye okumayi keser). 0-kayitta REDDETME (Turkce/varyant olabilir) -> XML'e birak.
  - CELISKI COZUMU: iki model farkli yonetmen derse, KB-onaylananı sec; ikisi de onaysiz/celiskili
    ise "okunamadi" (DURUST CEKIMSERLIK -> yanlis cikti ASLA). 12-film: ensemble 9/12 dogru, 0 yanlis.

OPS DERSLERI:
  - Video coklu-kare /api/chat'te `think=False` SART (think=True yogun karede over-think->BOS).
    (Tek master PNG /api/generate'de TAM TERSI: think=True gerekiyordu — bu modul video-only.)
  - VRAM: gemma4:26b ~17GB (24GB'de RAHAT, guvenilir); qwen2.5vl:7b ~6GB; (qwen3-vl:30b ~23GB sinirda idi).
  - Yonetmen/yapimci coğu PRODUKSIYON filminde XML'de zaten otoriter (role_reconcile); bu modul
    onun TAMAMLAYICISI ve XML'siz/yabanci filmler + CAST icin birincil.

Kullanim (CLI test):
  python scripts/credit_video_read.py --giris <giris_frames_dir> --cikis <cikis_frames_dir>
  python scripts/credit_video_read.py --film-dir <tester/.../<film>>   # altinda giris/ cikis/ frames

Bagimlilik: stdlib + Pillow + duckdb (KB opsiyonel). Ollama yerel 11434.
"""
import argparse
import base64
import glob
import io
import json
import os
import re
import sys
import time
import unicodedata

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _ollama import ollama_chat as _ollama_chat  # noqa: E402  merkezi retry/timeout

# ------------------------- yapilandirma -------------------------
OLLAMA_HOST = os.environ.get("MITAS_OLLAMA", "http://127.0.0.1:11434")
OLLAMA_CHAT = OLLAMA_HOST + "/api/chat"  # geriye-donuk uyum (ollama_up'ta kullanilmaz)
MODELS = os.environ.get("MITAS_CREDIT_MODELS", "gemma4:26b,qwen2.5vl:7b").split(",")
IMDB_DUCKDB = os.environ.get("MITAS_IMDB_DUCKDB", r"Y:\DIGER\Mitas_Files\IMDB\db\imdb.duckdb")

BUDGET = 36          # segment basina VLM'e gidecek kare sayisi
LONG_THR = 1500      # bu kareden uzun segment = "uzun jenerik" -> bas+son modu
END_WIN = 900        # uzun jenerikte bas ve sondan alinacak pencere (kare)
FRAME_W = 640        # kare genisligi (kucult; metin okunur kalir, token/VRAM duser)
NUM_CTX = 16384
NUM_PREDICT = 1000

PROMPT = (
    "Bunlar bir film jeneriğinin ARDIŞIK kareleri (video). Kareler boyunca görünen yazıları "
    "birleştirerek şunları bul. SADECE karelerde AÇIKÇA YAZAN isimleri kullan, uydurma; yoksa 'yok'. "
    "Çıktıyı tam olarak şu formatta ver:\n"
    "YÖNETMEN: <Director/Yöneten/Rejisör yanındaki isim | yok>\n"
    "YAPIMCI: <Producer/Yapımcı/Executive Producer yanındaki isim(ler) | yok>\n"
    "OYUNCULAR: <görünen başrol oyuncu adları, en fazla 8, virgülle | yok>"
)
ABSTAIN_TOKENS = {"yok", "okunamadi", "", "-", "none", "n/a"}

# ------------------------- yardimcilar -------------------------
def fold(s):
    """Turkce-duyarli ASCII katlama (eslestirme/dedup icin)."""
    s = s or ""
    for a, b in (("İ", "i"), ("I", "i"), ("ı", "i"), ("Ş", "s"), ("ş", "s"),
                 ("Ğ", "g"), ("ğ", "g"), ("Ü", "u"), ("ü", "u"),
                 ("Ö", "o"), ("ö", "o"), ("Ç", "c"), ("ç", "c")):
        s = s.replace(a, b)
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", " ", s).strip()

def is_abstain(v):
    s = re.sub(r"^[^a-z0-9]+|[^a-z0-9]+$", "", fold(v))   # <NAME>, <yok>, ":" gibi kenar işaretlerini soy
    return s in ABSTAIN_TOKENS or s == "" or s in {"isim", "name", "ad"}

# prompt-echo / rol-başlık çöpü: model bazen prompt format metnini ("Producer/Yapımcı/... yanındaki isim")
# isim sanıp yazıyor -> bunları ele
_ROLE_HEAD_WORDS = {"yapimci", "yapim", "producer", "produced", "production", "executive",
                    "yonetmen", "yoneten", "rejisor", "director", "directed", "direction",
                    "oyuncular", "oyuncu", "cast", "starring", "isim", "isimler", "name"}
def _is_junk(name):
    if any(ch in name for ch in "<>|"):
        return True
    f = fold(name)
    if any(w in f for w in ("yanindaki", "isimler", "veya", " yok")):
        return True
    toks = f.split()
    if not toks:
        return True
    if toks[0] in _ROLE_HEAD_WORDS or all(t in _ROLE_HEAD_WORDS for t in toks):
        return True
    return False

def split_names(v):
    if is_abstain(v):
        return []
    parts = re.split(r"[,/|]| ve ", v)
    return [p.strip() for p in parts if p.strip() and not is_abstain(p) and not _is_junk(p)]

def parse_field(text, key):
    for line in (text or "").splitlines():
        if fold(line).startswith(fold(key)):
            return line.split(":", 1)[1].strip() if ":" in line else ""
    return ""

# ------------------------- kare ornekleme (BAŞ+SON) -------------------------
def _even(pool, k):
    if len(pool) <= k:
        return pool
    return [pool[round(i * (len(pool) - 1) / (k - 1))] for i in range(k)]

def sample_basson(frames, budget=BUDGET, long_thr=LONG_THR, end_win=END_WIN):
    """Uzun jenerik -> ilk end_win + son end_win pencereye yogun ornek (orta atlanir).
    Kisa jenerik -> tum segmenti esit ornekle."""
    n = len(frames)
    if n > long_thr:
        h = budget // 2
        return _even(frames[:end_win], h) + _even(frames[-end_win:], budget - h)
    return _even(frames, budget)

def list_frames(d):
    # f_*: tester/batch · g_*/c_*: production (extract_window giris/cikis) · *.jpg: ffmpeg
    return sorted(glob.glob(os.path.join(d, "f_*.png")) + glob.glob(os.path.join(d, "g_*.png"))
                  + glob.glob(os.path.join(d, "c_*.png")) + glob.glob(os.path.join(d, "*.jpg")))

# ------------------------- VLM cagrisi -------------------------
def _encode(path):
    from PIL import Image
    im = Image.open(path).convert("RGB")
    if im.width > FRAME_W:
        im = im.resize((FRAME_W, round(im.height * FRAME_W / im.width)))
    buf = io.BytesIO()
    im.save(buf, format="JPEG", quality=85)
    return base64.b64encode(buf.getvalue()).decode()

def read_segment(model, frames):
    """Bir kare dizisini video-tag olarak VLM'e ver, ham cevabi dondur. think=False (video icin SART).
    _ollama.ollama_chat uzerinden (retry+timeout merkezi). Basarisizsa bos string."""
    msgs = [{"role": "user", "content": PROMPT, "images": [_encode(f) for f in frames]}]
    # VL örnekleme env-ayarlı (default = mevcut 0.1/0.9). MITAS_VL_TEMP=0 + MITAS_VL_TOPP=1 → tam greedy.
    import os as _os
    _vl_temp = float(_os.environ.get("MITAS_VL_TEMP", "0"))    # greedy default (2026-06-09): yönetmen deterministik
    _vl_topp = float(_os.environ.get("MITAS_VL_TOPP", "1"))
    resp = _ollama_chat(
        model=model,
        messages=msgs,
        timeout=900,
        host=OLLAMA_HOST,
        think=False,
        keep_alive="10m",
        options={"temperature": _vl_temp, "top_p": _vl_topp, "num_ctx": NUM_CTX,
                 "num_predict": NUM_PREDICT, "repeat_penalty": 1.3, "repeat_last_n": 256},
    )
    if resp is None:
        return ""
    return (resp.get("message", {}).get("content") or "").strip()

# ------------------------- KB (imdb.duckdb) -------------------------
class KB:
    """imdb.duckdb meslek dogrulamasi. Yoksa zarafetle devre disi (her sey 'kayit-yok' = reddetme)."""
    def __init__(self, path=IMDB_DUCKDB):
        self.con = None
        try:
            import duckdb
            if os.path.exists(path):
                self.con = duckdb.connect(path, read_only=True)
        except Exception:
            self.con = None

    def verify(self, name, role):
        """ONAY / RED / kayit-yok / meslek-bos. NET uyumsuzlukta RED; aksi halde gecir (XML'e birak)."""
        if not self.con:
            return "kayit-yok"
        try:
            rows = self.con.execute(
                "SELECT primaryProfession FROM names "
                "WHERE UPPER(strip_accents(primaryName))=UPPER(strip_accents(?))", [name]).fetchall()
        except Exception:
            return "?"
        if not rows:
            return "kayit-yok"
        profs = set()
        for (p,) in rows:
            if p:
                profs.update(x.strip() for x in str(p).split(","))
        if not profs:
            return "meslek-bos"
        if role in profs or (role == "producer" and "director" in profs):
            return "ONAY"
        return "RED"

# ------------------------- FUSION (ensemble + KB + celiski) -------------------------
def _dedup(seq):
    out = []
    for x in seq:
        if not any(fold(x) == fold(y) for y in out):
            out.append(x)
    return out

def fuse(model_outputs, kb):
    """
    model_outputs: {model: {"giris": text, "cikis": text}}
    Donus: {"yonetmen":[...], "yapimci":[...], "cast":[...], "guven": "...", "ayrinti": {...}}
    Yonetmen mantigi:
      - Her modelin (giris∪cikis) yonetmen adaylarini topla, KB-RED olanlari at.
      - Modeller arasi mutabakat (ayni isim >=2 model) -> YUKSEK guven.
      - Tek model + KB-ONAY -> al. Celiski (farkli isimler) -> KB-ONAY olani tercih;
        hicbiri KB-ONAY degilse OKUNAMADI (dürüst cekimserlik).
    """
    per_model_dir = {}
    prod_all, cast_all = [], []
    for model, segs in model_outputs.items():
        d = []
        for seg_text in segs.values():
            for nm in split_names(parse_field(seg_text, "YÖNETMEN")):
                if kb.verify(nm, "director") != "RED":
                    d.append(nm)
            for nm in split_names(parse_field(seg_text, "YAPIMCI")):
                if kb.verify(nm, "producer") != "RED":
                    prod_all.append(nm)
            for nm in split_names(parse_field(seg_text, "OYUNCULAR")):
                if len(nm.split()) >= 2:           # tek-token karakter adlarini ele
                    cast_all.append(nm)
        per_model_dir[model] = _dedup(d)

    # yonetmen: mutabakat -> KB-onay -> celiski coz
    flat = [n for lst in per_model_dir.values() for n in lst]
    yonetmen, guven = [], "OKUNAMADI"
    if flat:
        # mutabakat: birden cok modelde gecen
        agreed = [n for n in _dedup(flat)
                  if sum(1 for lst in per_model_dir.values() if any(fold(n) == fold(x) for x in lst)) >= 2]
        if agreed:
            yonetmen, guven = agreed, "YUKSEK (mutabakat)"
        else:
            kb_ok = [n for n in _dedup(flat) if kb.verify(n, "director") == "ONAY"]
            if kb_ok:
                yonetmen, guven = kb_ok, "ORTA (KB-onay)"
            elif len(_dedup(flat)) == 1:
                yonetmen, guven = _dedup(flat), "DUSUK (tek okuma)"
            else:
                yonetmen, guven = [], "OKUNAMADI (celiski)"

    yapimci = _dedup(prod_all)
    cast = _dedup(cast_all)[:8]
    return {"yonetmen": yonetmen, "yapimci": yapimci, "cast": cast, "guven": guven,
            "ayrinti": {m: lst for m, lst in per_model_dir.items()}}

# ------------------------- ANA GIRIS -------------------------
def read_credits(giris_dir=None, cikis_dir=None, models=None, kb=None):
    models = models or MODELS
    kb = kb or KB()
    # kareleri segment basina BIR KEZ ornekle
    seg_frames = {}
    for seg, d in (("giris", giris_dir), ("cikis", cikis_dir)):
        if d and os.path.isdir(d):
            fr = sample_basson(list_frames(d))
            if fr:
                seg_frames[seg] = fr
    # MODEL DISTA dongu: film basina her model 1 kez yuklenir (gemma<->7b swap'ini azaltir)
    outputs = {m: {} for m in models}
    for m in models:
        for seg, fr in seg_frames.items():
            try:
                outputs[m][seg] = read_segment(m, fr)
            except Exception as e:
                outputs[m][seg] = ""
                sys.stderr.write(f"[uyari] {m}/{seg}: {type(e).__name__} {e}\n")
    result = fuse(outputs, kb)
    result["ham"] = outputs
    return result

def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="Jenerik video baş+son + ensemble + KB okuma")
    ap.add_argument("--giris"); ap.add_argument("--cikis")
    ap.add_argument("--film-dir", help="altinda giris/frames ve cikis/frames olan film klasoru")
    ap.add_argument("--models", default=None, help="virgullu model listesi")
    args = ap.parse_args()
    g, c = args.giris, args.cikis
    if args.film_dir:
        g = g or os.path.join(args.film_dir, "giris", "frames")
        c = c or os.path.join(args.film_dir, "cikis", "frames")
    models = args.models.split(",") if args.models else None
    res = read_credits(g, c, models=models)
    print("YÖNETMEN :", res["yonetmen"] or "okunamadı", f"  [{res['guven']}]")
    print("YAPIMCI  :", res["yapimci"] or "okunamadı")
    print("OYUNCULAR:", ", ".join(res["cast"]) or "okunamadı")
    print("ayrıntı  :", json.dumps(res["ayrinti"], ensure_ascii=False))

if __name__ == "__main__":
    main()
