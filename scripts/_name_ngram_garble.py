# -*- coding: utf-8 -*-
"""_name_ngram_garble.py — KB-BAĞIMSIZ leksikal isim-garble detektörü (FIX 4, 2026-06-22).

Sorun: well-formed-ASCII OCR garble'ı (DAMES DARREN, JJAME SBENREET, JEJULIEA BENNETT)
mevcut kapıların hepsine (VLM-prompt non-Latin sorar, _bad_chars not-ascii bakar, KB-imza
KB-yok filmde çalışmaz) görünmez. Bu modül gerçek-kişi-adı korpusunda (IMDb names ~15M)
eğitilmiş KARAKTER 3-GRAM olabilirlik modeliyle "isim gibi görünüyor ama akla yatkın değil"
dizileri yakalar — KB KAYDI GEREKTİRMEZ.

KULLANIM (route-only, SİLME DEĞİL): tek_film_kunye.py `cast_garble_lex` hesabında, gerçek
oyuncu adlarını leksikal-garble için tarar → mitas_pipeline garble→KONTROL yönlendirir.
Düşük skorlu (akla yatkın olmayan) token'i olan ad = suspect.

FAIL-SAFE: model dosyası yoksa / hata → looks_garble_ngram() False döner (regresyon yok).
Model bir kez `python _name_ngram_garble.py build` ile üretilir, JSON'a yazılır, pipeline
load eder (hızlı). Eşik kalibrasyonu `... calib` ile.
"""
from __future__ import annotations
import json
import math
import os
import sys
import unicodedata
from pathlib import Path

N = 3                       # trigram
_PAD = "^"                  # başlangıç sınır işareti
_END = "$"
MODEL_PATH = Path(os.environ.get(
    "MITAS_NGRAM_MODEL",
    str(Path(__file__).resolve().parent / "_name_ngram_model.json")))
# TIER AGREGASYON (2026-06-22, tarafsız-audit + 984-film teslim-kadro ölçümü sonrası):
# Bir AD garble-şüphesi sayılır ⇔ (tek token < SOLO=çok-bariz) VEYA (≥2 token < PAIR).
# NEDEN MIN DEĞİL: MIN agregasyonu TEK nadir-gerçek token'la (GUUSJE -4.08, OFOEGBU -4.06,
#   EGEDE -3.19) gerçek yabancı adı batırıyordu → yüksek FP. TIER: tek token ancak gerçek-nadir
#   aralığın ÖTESİNDE (<-4.3) ise tek başına flag; aksi halde KORROBORASYON (2 kötü token) ister.
# ÖLÇÜM (84-isim etiketli örnek / 985-film korpus):
#   MIN<-3.5 = %91 precision, %21.3 film-flag  →  TIER = %100 örnek-precision, %7.9 film-flag.
#   Yakalar: DRNALD HKSRLAKE, PRADECTION DESIGRWR, disclaimer/diyalog/rol-junk.
#   Korur: GUUSJE VAN TILBORGH, ANTHONY OFOEGBU, AUD EGEDE-NISSEN, LUKE ASKEW (gerçek-nadir).
# SINIRLAR (route-kolu açılmadan önce Faz-2 gerekir):
#   • DAMES DARREN(-1.89)/MEL BLANCE = kelime-benzeri → n-gram KÖR (FIX 1 stitch-frekans düzeltir).
#   • JJAME SBENREET(min -3.17, token'lar -2.91/-3.17) TIER'i geçer → İKİ-SİNYAL (n-gram+düşük
#     stitch-desteği) gerekir, Faz-2.  • Türkçe ad FP (DUYGU UYSAL): model IMDb-global, Türkçe
#     ortografi az temsil → Faz-2'de Türkçe-korpus augment + iki-sinyal.
SOLO_THRESHOLD = float(os.environ.get("MITAS_NGRAM_SOLO", "-4.3"))   # tek token bundan düşük → garble
PAIR_THRESHOLD = float(os.environ.get("MITAS_NGRAM_PAIR", "-3.2"))   # ≥2 token bundan düşük → garble
MIN_TOKEN_LEN = 4          # 'PYL','DON','HAL','J.' gibi kısa token'lar puanlanmaz (FP önler)


def _fold_upper(s: str) -> str:
    """Aksanı kaldır, A-Z'ye indir (Türkçe/diakritik → ASCII), büyük harf."""
    s = unicodedata.normalize("NFKD", str(s or ""))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s.upper()


def _tokens(name: str) -> list[str]:
    """Adı yalnız-harf (A-Z) token'lara böl; baş harf/kısa parça puanlama dışı."""
    out = []
    cur = []
    for c in _fold_upper(name):
        if "A" <= c <= "Z":
            cur.append(c)
        else:
            if cur:
                out.append("".join(cur)); cur = []
    if cur:
        out.append("".join(cur))
    return out


def _grams(token: str):
    """'^^TOKEN$' üzerinden trigram üret (n-1 başlangıç + 1 bitiş sınırı)."""
    s = _PAD * (N - 1) + token + _END
    for i in range(len(s) - N + 1):
        yield s[i:i + N]


# ───────────────────────── MODEL EĞİTİMİ ─────────────────────────
def build_model(names, n=N):
    counts: dict[str, int] = {}
    bigram: dict[str, int] = {}     # ilk n-1 karakterin sayacı (koşullu olasılık için)
    for nm in names:
        for tok in _tokens(nm):
            if len(tok) < 2:
                continue
            for g in _grams(tok):
                counts[g] = counts.get(g, 0) + 1
                bigram[g[:-1]] = bigram.get(g[:-1], 0) + 1
    return {"n": n, "counts": counts, "bigram": bigram,
            "vocab": 28,  # A-Z + ^ + $ yaklaşık
            "total": sum(counts.values())}


def save_model(model, path=MODEL_PATH):
    Path(path).write_text(json.dumps(model, ensure_ascii=False), encoding="utf-8")


_CACHE = {"model": None, "path": None}


def load_model(path=MODEL_PATH):
    p = str(path)
    if _CACHE["model"] is not None and _CACHE["path"] == p:
        return _CACHE["model"]
    try:
        m = json.loads(Path(path).read_text(encoding="utf-8"))
        _CACHE["model"] = m; _CACHE["path"] = p
        return m
    except Exception:
        return None


# ───────────────────────── SKORLAMA ─────────────────────────
def score_token(token, model, k=0.5):
    """Token'in ortalama koşullu trigram log-olasılığı (add-k smoothing). Yüksek = akla yatkın."""
    counts = model["counts"]; bigram = model["bigram"]; vocab = model.get("vocab", 28)
    lp = 0.0; ngr = 0
    for g in _grams(token):
        c = counts.get(g, 0)
        ctx = bigram.get(g[:-1], 0)
        p = (c + k) / (ctx + k * vocab)
        lp += math.log(p); ngr += 1
    return (lp / ngr) if ngr else 0.0


def _token_scores(name, model=None):
    """Adın puanlanabilir (len>=MIN_TOKEN_LEN) token'larının skor listesi."""
    model = model or load_model()
    if not model:
        return []
    return [score_token(t, model) for t in _tokens(name) if len(t) >= MIN_TOKEN_LEN]


def score_name(name, model=None):
    """TELEMETRİ: adın EN KÖTÜ token skoru (gözlem/log için). None = puanlanamaz/model yok."""
    ts = _token_scores(name, model)
    return min(ts) if ts else None


def looks_garble_ngram(name, model=None, solo=None, pair=None):
    """TIER kararı: (tek token < SOLO) VEYA (≥2 token < PAIR) → garble-şüphesi.
    FAIL-SAFE: model yoksa/hata → False (garble değil; regresyon yok)."""
    try:
        ts = _token_scores(name, model)
        if not ts:
            return False
        s = SOLO_THRESHOLD if solo is None else solo
        p = PAIR_THRESHOLD if pair is None else pair
        return any(x < s for x in ts) or sum(1 for x in ts if x < p) >= 2
    except Exception:
        return False


# ───────────────────────── CLI: build / calib / score ─────────────────────────
def _iter_imdb_names(limit=None):
    import duckdb
    db = os.environ.get("MITAS_IMDB_DUCKDB", r"Y:\DIGER\Mitas_Files\IMDB\db\imdb.duckdb")
    con = duckdb.connect(db, read_only=True)
    q = "SELECT primaryName FROM names WHERE primaryName IS NOT NULL"
    if limit:
        q += f" USING SAMPLE {int(limit)} ROWS"
    cur = con.execute(q)
    while True:
        rows = cur.fetchmany(50000)
        if not rows:
            break
        for r in rows:
            yield r[0]
    con.close()


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    cmd = sys.argv[1] if len(sys.argv) > 1 else "calib"
    if cmd == "build":
        limit = int(sys.argv[2]) if len(sys.argv) > 2 else 2_000_000
        print(f"IMDb names'ten ~{limit} örnekle model kuruluyor...")
        m = build_model(_iter_imdb_names(limit))
        save_model(m)
        print(f"model: {len(m['counts'])} trigram, total={m['total']}, → {MODEL_PATH}")
    elif cmd == "calib":
        m = load_model()
        if not m:
            print("MODEL YOK — önce: python _name_ngram_garble.py build"); return
        real = ["JAMES DARREN", "JULIE BENNETT", "JEAN VANDER PYL", "J. PAT O'MALLEY",
                "MEL BLANC", "HAL SMITH", "DON MESSICK", "DAWS BUTLER", "GREGORY PECK",
                "ROBERT REDFORD", "NURI BILGE CEYLAN", "MARVIN J. MCINTYRE", "JOHN SANTUCCI"]
        garb = ["DAMES DARREN", "JJAME SBENREET", "JEJULIEA BENNETT", "MEL BLANCE",
                "DONSMESSICK", "GEORCE STOAD ALRRDED", "LEONARDO SEVERINI", "RDGER MQSTEY"]
        print(f"TIER: SOLO={SOLO_THRESHOLD}  PAIR={PAIR_THRESHOLD}")
        print("=== GERÇEK adlar (garble=False OLMALI) ===")
        for n in real:
            print(f"  min={score_name(n, m):7.2f}  garble={looks_garble_ngram(n, m)!s:5}  {n}")
        print("=== GARBLE adlar (mümkünse garble=True; DAMES/JJAME kelime-benzeri kaçabilir) ===")
        for n in garb:
            print(f"  min={score_name(n, m):7.2f}  garble={looks_garble_ngram(n, m)!s:5}  {n}")
        # FP ölçümü: rastgele gerçek adlardan kaçı yanlışça garble işaretlenir?
        import itertools
        samp = list(itertools.islice(_iter_imdb_names(20000), 20000))
        fp = sum(1 for n in samp if looks_garble_ngram(n, m))
        scored = sum(1 for n in samp if score_name(n, m) is not None)
        print(f"\nFP (20k rastgele IMDb adı): {fp}/{scored} puanlanan = {100*fp/max(1,scored):.2f}%")
    elif cmd == "score":
        m = load_model()
        for n in sys.argv[2:]:
            print(f"  {score_name(n, m):8.2f}  garble={looks_garble_ngram(n, m)}  {n}")


if __name__ == "__main__":
    main()
