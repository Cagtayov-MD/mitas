"""C — OCR-UZAYINDA DİKME + GÜVEN-KAPISI + BULANIK-MODE. Salt cache/ocr_pos üstünde (CLIP/OCR yok).
Birikimli kayma S_k ile global koordinat g=cy+S_k -> akanda fiziksel satır için g sabit -> g'ye göre kümele.
Küme içinde BULANIK-MODE: yakın okumaları grupla, en büyük grup=consensus, conf=grup/küme; en temiz üye=best.
GÜVEN-KAPISI: conf<thr olan satır (tekrarı yok=garble) ana künyeden düşer, 'düşük güven'e gider.
API: stitch_kunye(runs, ocr_pos, conf_thr) -> (main, low, medconf)
"""
import sys, json, unicodedata, difflib, os
from collections import Counter
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
VOWELS = set("aeıioöuüâîû")
# FIX 1 (2026-06-22): pick_best temsilcisini ÖNCE temiz okumalar arasında FREKANSLA seç.
# Tekrarlı-temiz (JAMES DARREN ×7) tek-seferlik garble'ı (DAMES DARREN ×1) yenmeli; eski
# kod garble()=0.0 beraberliğinde ilk-geleni alıp garble seçiyordu. AKTİF (default ON; AYI YOGİ
# canlı-kanıtlı + non-regresyon audit PASS). MITAS_STITCH_FREQVOTE=0 ile eski davranışa dönülür (kill-switch).
_FREQVOTE = os.environ.get("MITAS_STITCH_FREQVOTE", "1").strip().lower() in ("1", "true", "on", "yes")
# FIX 2 (2026-07-04): KOLON-KURTARMA — iki-kolon jenerikte (karakter | oyuncu YAN YANA, ayni y)
# kume icinde pick_best yalniz BUYUK grubu donduruyordu; ikinci kolon (SINIR CIZGISI: CHARLES
# BRONSON x24, Jeb Maynard x25'e karsi) TAMAMEN dusuyordu = gercek oyuncu ham kunyeye hic
# ulasmiyordu. Kurtarma: ayni kumede IKINCI (ve sonraki) buyuk+temiz+tekrarli gruplari da EK
# SATIR olarak emit et. SALT-EKLEYICI (mevcut satirlar AYNEN kalir; KEEP-ALL felsefesi:
# "gercek isim kaybolmaz"). Esikler: grup >= max(3, %35*kume) uye + temsilcisi garble=0.
# Tek-seferlik garble varyantlari (1 uye) esigi gecemez. MITAS_STITCH_COLRESCUE=0 kill-switch.
_COLRESCUE = os.environ.get("MITAS_STITCH_COLRESCUE", "1").strip().lower() in ("1", "true", "on", "yes")
def norm(s): return ''.join(c for c in unicodedata.normalize('NFKD', s.lower()) if not unicodedata.combining(c))
def tsim(a, b): return difflib.SequenceMatcher(None, a, b).ratio()
def cy(o): return (o[2]+o[3])/2.0
def garble(raw):
    t = raw.strip(); nonsp = sum(not c.isspace() for c in t); letters = sum(c.isalpha() for c in t)
    if nonsp == 0: return 9.0
    s = (1-letters/nonsp)*2.0
    for tk in t.split():
        ft = norm(tk)
        if len(ft) >= 4 and not any(c in VOWELS for c in ft): s += 1.0
    return s

def pick_best(readings):
    """bulanık-mode: yakın okumaları grupla; en büyük grup consensus; conf=grup/toplam; best=en temiz üye."""
    groups = []
    for raw in readings:
        f = norm(raw)
        hit = next((g for g in groups if tsim(f, g["rep"]) >= 0.80), None)
        if hit: hit["m"].append(raw)
        else: groups.append({"rep": f, "m": [raw]})
    groups.sort(key=lambda g: -len(g["m"]))
    top = groups[0]
    if _FREQVOTE:
        # FIX 1: ÖNCE temiz okumalar (garble==0.0) arasında en sık geçen yazımı seç →
        # garble bir temizi ASLA oylamada geçemez (clean-pool). Hata → eski davranışa düş.
        try:
            cnt = Counter(top["m"])
            clean = [r for r in top["m"] if garble(r) == 0.0]
            pool = clean or top["m"]
            best = min(pool, key=lambda r: (-cnt[r], garble(r), -len(r)))
        except Exception:
            best = min(top["m"], key=lambda r: (garble(r), -len(r)))
    else:
        best = min(top["m"], key=lambda r: (garble(r), -len(r)))
    return best, len(top["m"])/len(readings)


def co_texts(readings, primary_best):
    """FIX 2 kolon-kurtarma: pick_best'in ATTIGI ikinci+ buyuk-temiz gruplari dondur.
    Ayni y-kumesinde birbirinden FARKLI (tsim<0.80 = ayri grup) iki metnin ikisi de cok
    tekrarli+temizse ikisi de GERCEK yazidir (iki kolon / cift kart) -> kaybetme.
    Dondurulen: [(metin, conf)] — primary haric, esik: >=max(3, %35*toplam) uye, garble=0."""
    try:
        groups = []
        for raw in readings:
            f = norm(raw)
            hit = next((g for g in groups if tsim(f, g["rep"]) >= 0.80), None)
            if hit: hit["m"].append(raw)
            else: groups.append({"rep": f, "m": [raw]})
        groups.sort(key=lambda g: -len(g["m"]))
        total = len(readings)
        min_n = max(3, int(total*0.35))
        out = []
        pb = norm(primary_best)
        for g in groups[1:]:
            if len(g["m"]) < min_n: break                       # sirali: ilk kucuk grupta dur
            cnt = Counter(g["m"])
            clean = [r for r in g["m"] if garble(r) == 0.0]
            if not clean: continue                              # temiz uyesi yok = garble grubu
            best = min(clean, key=lambda r: (-cnt[r], -len(r)))
            if tsim(norm(best), pb) >= 0.80: continue           # primary'nin varyanti (guvenlik)
            out.append((best, len(g["m"])/total))
        return out
    except Exception:                                            # FAIL-SAFE: kurtarma atlanir, ana akis BOZULMAZ
        return []

def est_delta(A, B):
    cand = []
    for a in A:
        if not a[0]: continue
        for b in B:
            if b[0] and abs(len(a[0])-len(b[0])) <= 2 and tsim(a[0], b[0]) >= 0.80:
                cand.append(cy(a)-cy(b))
    if not cand: return None
    cand.sort(); return cand[len(cand)//2]

def line_spacing(run_obs):
    gaps = []
    for obs in run_obs:
        ys = sorted(cy(o) for o in obs)
        gaps += [ys[i+1]-ys[i] for i in range(len(ys)-1) if 5 < ys[i+1]-ys[i] < 200]
    if not gaps: return 40.0
    gaps.sort(); return gaps[len(gaps)//2]

def stitch_run(run_obs):
    nf = len(run_obs)
    deltas = [est_delta(run_obs[k], run_obs[k+1]) for k in range(nf-1)]
    valid = [d for d in deltas if d is not None and abs(d) < 200]
    gmed = sorted(valid)[len(valid)//2] if valid else 0.0
    deltas = [d if (d is not None and abs(d) < 200) else gmed for d in deltas]
    S = [0.0]*nf
    for k in range(1, nf): S[k] = S[k-1]+deltas[k-1]
    L = line_spacing(run_obs)
    items = []
    for k in range(nf):
        for o in run_obs[k]:
            if o[0]: items.append((cy(o)+S[k], o[1]))
    if not items: return [], gmed, L, 0.0
    items.sort(key=lambda x: x[0])
    tol = max(8.0, L*0.45)
    clusters = [[items[0]]]
    for it in items[1:]:                                          # KÜME-GENİŞLİĞİ sınırı (baştan <=tol) — tek-bağ zincirini önler
        (clusters[-1].append(it) if it[0]-clusters[-1][0][0] <= tol else clusters.append([it]))
    out = []
    rescue = []
    for cl in clusters:
        reads = [c[1] for c in cl]
        best, conf = pick_best(reads)
        out.append([cl[0][0], best, len(cl), conf])
        if _COLRESCUE:                                          # FIX 2: atilan ikinci kolonu topla (emit asagida)
            for eb, ec in co_texts(reads, best):
                rescue.append([cl[0][0], eb, len(cl), ec])
    out.sort(key=lambda x: x[0])
    merged = []
    for o in out:
        if merged and tsim(norm(o[1]), norm(merged[-1][1])) >= 0.88:
            merged[-1][2] += o[2]; merged[-1][3] = max(merged[-1][3], o[3]); continue
        merged.append(o)
    confs = [o[3] for o in merged]                              # medconf ANA satirlardan (OFF ile ozdes)
    mc = sorted(confs)[len(confs)//2] if confs else 0.0
    # FIX 2 emit: merge-zinciri BITTIKTEN sonra ekle -> ana satirlar OFF ile BIREBIR kalir
    # (extras merge'e girseydi komsuyu yutabilirdi = salt-ekleyici ihlali). Var-olanla >=0.88
    # benzesen extra ATILIR (ayni ismin yazim-varyanti cift olusturmasin); kalanlar anchor
    # g'sinin hemen arkasina girer (LLM ayni blokta gorur).
    for r in rescue:
        if any(tsim(norm(r[1]), norm(m[1])) >= 0.88 for m in merged):
            continue
        pos = 0
        for i, m in enumerate(merged):
            if m[0] <= r[0]: pos = i + 1
            else: break
        merged.insert(pos, [r[0] + 0.001, r[1], r[2], r[3]])
    return merged, gmed, L, mc

def dedup_static(run_obs):
    groups = []
    for obs in run_obs:
        for o in obs:
            if not o[0]: continue
            hit = next((g for g in groups if tsim(o[0], g["f"]) >= 0.82), None)
            (hit["r"].append(o[1]) if hit else groups.append({"f": o[0], "r": [o[1]]}))
    return [pick_best(g["r"])[0] for g in groups]

def runs_of(idx):
    runs = [[idx[0]]]
    for j in idx[1:]:
        (runs[-1].append(j) if j-runs[-1][-1] <= 3 else runs.append([j]))
    return runs

def stitch_kunye(runs, ocr_pos, conf_thr=0.34):
    """KEEP-ALL: tüm dikilen satırları SIRAYLA döndür (hiç DROP yok -> gerçek isim kaybolmaz).
    low = sadece düşük-güven ALT KÜMESİ (işaretleme/rapor için); ana künyeden ÇIKARILMAZ."""
    lines = []; low = []; confs = []
    for run in runs:
        run_obs = [ocr_pos[i] for i in run]
        if len(run) >= 8:
            st, gmed, L, mc = stitch_run(run_obs)
            if abs(gmed) > max(3, L*0.3):                 # AKAN -> dik (per-frame garble -> tek temiz okuma)
                confs.append(mc)
                for o in st:                               # o = [g, best, n, conf, x]
                    lines.append(o[1])                     # HEPSİ ana künyede (DROP yok)
                    if o[3] < conf_thr: low.append(o[1])   # düşük-güven sadece işaretlenir
                continue
        lines += dedup_static(run_obs)                     # statik -> güvenilir
    return lines, low, (sorted(confs)[len(confs)//2] if confs else 1.0)

if __name__ == "__main__":
    CACHE = Path(r"E:\MITAS\OCR-worktree\clip_pipeline100\_CACHE")
    KUN = Path(r"E:\MITAS\OCR-worktree\clip_pipeline100\_KUNYE")
    for sub in sys.argv[1:]:
        s = norm(sub)
        for cj in sorted(CACHE.glob("*.json")):
            if s not in norm(cj.stem): continue
            c = json.loads(cj.read_text(encoding="utf-8")); idx = c["idx"]
            if not idx: continue
            op = {int(k): v for k, v in c["ocr_pos"].items()}
            kp = KUN/f"{cj.stem}.txt"
            old = len([l for l in kp.read_text(encoding="utf-8", errors="ignore").splitlines() if l.strip() and not l.startswith("#")]) if kp.exists() else 0
            main, low, mc = stitch_kunye(runs_of(idx), op)
            print(f"\n===== {cj.stem} =====")
            print(f"  ESKİ={old}  ->  GATE ana={len(main)}  düşük-güven={len(low)}  | medconf={mc:.2f}")
            print("  --- ana künye (ilk 28) ---")
            for l in main[:28]: print("    ", l)
            if low:
                print("  --- atılan düşük-güven (ilk 8) ---")
                for l in low[:8]: print("    ✗", l)
