# -*- coding: utf-8 -*-
"""
Bu script, bozuk LLM-uppercase zincirini (_102_ozet_prep -> ozout -> _102_apply_ozet)
DETERMINISTIK tr_upper ile DEGISTIRIR. Ozet buyuk-harfi ARTIK LLM ile yapilmaz;
kelime-yapistirma + noktasiz-I bozulmasinin kok cozumu budur.
"""
import sys, json, re, importlib.util, glob
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

# ── name_normalize yukle (render scriptindeki _load deseni) ─────────────────
PDFMITAS = Path(r"E:\MITAS\OCR-worktree\pdf-mitas")

def _load(n, p):
    s = importlib.util.spec_from_file_location(n, str(p))
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m

nn = _load("nn", PDFMITAS / "name_normalize.py")

# ── ozet_v4: tek_film_kunye.py:95-115 bire-bir kopya + ISIM-FARKINDA buyuk harf ──
def ozet_v4(ozet, names=(), tr_set=None):
    """v4 ozet: kurulum cumleler + SON cumle (spoiler) korunur, <=~64 kelime, TR-BUYUK.
    Buyuk harf nn.tr_upper_prose ile: yabanci cast/crew adlari ASCII (MASSIMO), Turkce isim İ.
    tr_set: ONCEDEN toplu hesaplanmis OTORITER Turk-isim kumesi (film-basi duckDB kilidini onler)."""
    if not ozet:
        return "—"
    ozet = re.sub(r'[?!"\[\]]', "", ozet)
    cumleler = [c.strip() for c in re.split(r"(?<=[.])\s+", ozet) if c.strip()]
    if len(cumleler) <= 1:
        return nn.tr_upper_prose(ozet, names, tr_set=tr_set)
    son = cumleler[-1]
    son_w = len(son.split())
    out, n = [], 0
    for c in cumleler[:-1]:
        w = len(c.split())
        if out and n + w + son_w > 64:
            break
        out.append(c)
        n += w
    if son not in out:
        out.append(son)
    return nn.tr_upper_prose(" ".join(out), names, tr_set=tr_set)

# ── yapiskik kelime tespiti ──────────────────────────────────────────────────
def yapiskik_kelime_var(s):
    """Ozet stringinde >=17 harf yapiskik buyuk-harf kelime var mi?"""
    if not s:
        return False
    for tok in s.split():
        temiz = re.sub(r'[^A-ZÇĞİŞÖÜ]', '', tok)
        if len(temiz) >= 17:
            return True
    return False

# ── ham ozetler: tum ozet_*.json chunklardan {trt: ozet} ────────────────────
CHUNKS_DIR = Path(r"E:\MITAS\_102_chunks")
ham = {}
_bozuk_chunks = []
for chunk_path in sorted(glob.glob(str(CHUNKS_DIR / "ozet_*.json"))):
    try:
        raw = open(chunk_path, encoding="utf-8").read()
        # curly quote'lari duz tirnak ile degistir (JSON-safe)
        raw = raw.replace('“', '"').replace('”', '"')
        raw = raw.replace('‘', "'").replace('’', "'")
        kayitlar = json.loads(raw)
        for r in kayitlar:
            trt = r.get("trt", "").strip()
            ozet_ham = (r.get("ozet") or "").strip()
            if trt and ozet_ham:
                ham[trt] = ozet_ham
    except Exception as e:
        _bozuk_chunks.append((chunk_path, str(e)))
        print(f"  UYARI: {chunk_path} okunamadi: {e}")

if _bozuk_chunks:
    print(f"Bozuk chunk sayisi: {len(_bozuk_chunks)}")
print(f"Ham ozet yuklendi: {len(ham)} film")

# ── master yukle ─────────────────────────────────────────────────────────────
MASTER_PATH = Path(r"E:\MITAS\_102_master_FIXED.json")
master = json.load(open(MASTER_PATH, encoding="utf-8"))
print(f"Master yuklendi: {len(master)} film")

# ── oncesi yapiskik sayim ─────────────────────────────────────────────────────
oncesi_yapiskik = sum(1 for v in master if yapiskik_kelime_var(v.get("ozet", "")))
print(f"\nONCESI yapiskik-kelime iceren film sayisi: {oncesi_yapiskik}")

# ── OTORITER Turk-isim kumesi: TUM filmlerin cast/crew adlarini TEK duckDB sorgusuyla cek ──
# (film-basi baglanti, 314 ardisik connect'te ag-surucusu/eszamanli-batch yuzunden KILITLENIYOR
#  -> db_ok=False -> gevsek _is_tr_name -> 'Julia McKenzie' yanlis-Turk -> 'JULİA' kaliyordu.)
_all_names = sorted({nm for v in master for k in ("cast", "yonetmen", "yapimci")
                     for nm in (v.get(k) or []) if nm and str(nm).strip()})
TR_SET = None
for _try in range(5):                       # duckDB anlik kilitliyse birkac kez dene
    try:
        _ok, _trmap = nn._mitas_people_set(_all_names)
        if _ok:
            TR_SET = set(_trmap.keys())
            break
    except Exception as _e:
        print(f"  duckDB deneme {_try+1} hata: {_e}")
print(f"OTORITER Turk-isim kumesi: {'duckDB OK, ' + str(len(TR_SET)) + ' Turk isim' if TR_SET is not None else 'duckDB COKTU -> film-basi fallback (_is_tr_name)'} (toplam {len(_all_names)} benzersiz ad)")

# ── duzeltme ─────────────────────────────────────────────────────────────────
duzeltilen = 0
ham_yok_yapiskik = []
ham_yok_list = []

for v in master:
    trt = v.get("trt", "")
    if trt in ham:
        _names = (v.get("cast") or []) + (v.get("yonetmen") or []) + (v.get("yapimci") or [])
        yeni = ozet_v4(ham[trt], names=_names, tr_set=TR_SET)
        v["ozet"] = yeni
        duzeltilen += 1
    else:
        ham_yok_list.append(trt)
        if yapiskik_kelime_var(v.get("ozet", "")):
            ham_yok_yapiskik.append(trt)

print(f"Duzeltilen film: {duzeltilen}")
print(f"Ham ozeti OLMAYAN film: {len(ham_yok_list)}")

# ── sonrasi yapiskik sayim ────────────────────────────────────────────────────
sonrasi_yapiskik = sum(1 for v in master if yapiskik_kelime_var(v.get("ozet", "")))
print(f"SONRASI yapiskik-kelime iceren film sayisi: {sonrasi_yapiskik}")

# ── DAWN kontrol ─────────────────────────────────────────────────────────────
DAWN_TRT = "1991-0501-1-0000-00-1"
dawn_entry = next((v for v in master if v.get("trt") == DAWN_TRT), None)
if dawn_entry:
    dawn_ozet = dawn_entry.get("ozet", "")
    print(f"\nDAWN (1991-0501-1-0000-00-1) yeni ozeti (ilk 200 karakter):")
    print(dawn_ozet[:200])
else:
    print(f"\nDAWN ({DAWN_TRT}) master'da bulunamadi!")

# ── ham ozeti olmayan filmler ve yapiskik durumu ──────────────────────────────
print(f"\nHam ozeti OLMAYAN {len(ham_yok_list)} film listesi:")
for trt in ham_yok_list:
    flag = " [YAPISKIK]" if trt in ham_yok_yapiskik else ""
    print(f"  {trt}{flag}")

if ham_yok_yapiskik:
    print(f"\nHam ozeti olmayan filmlerden HALA yapiskik-kelime icerenlerin sayisi: {len(ham_yok_yapiskik)}")
    print("Bunlar DUZELTILEMIYOR (ham ozet yok):")
    for trt in ham_yok_yapiskik:
        print(f"  {trt}")
else:
    print(f"\nHam ozeti olmayan filmlerden yapiskik-kelime iceren: 0")

# ── DURUM KONTROLU ───────────────────────────────────────────────────────────
if sonrasi_yapiskik > len(ham_yok_yapiskik):
    gizli = sonrasi_yapiskik - len(ham_yok_yapiskik)
    print(f"\nUYARI: Ham ozeti OLAN filmlerden {gizli} tanesinde hala yapiskik-kelime var!")
    print("Beklenmedik durum - inceleme gerekli.")
else:
    print(f"\nDURUM: Ham ozeti olan filmler icin yapiskik-kelime bekleniyor: 0 - TAMAM")

# ── master geri yaz ──────────────────────────────────────────────────────────
json.dump(master, open(MASTER_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"\nMaster guncellendi: {MASTER_PATH}")
print("BITTI.")
