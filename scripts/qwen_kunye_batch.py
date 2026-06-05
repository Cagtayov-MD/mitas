# -*- coding: utf-8 -*-
"""COK-MODEL + COK-FILM kunye sinifllandirici olcum duzenegi (v2 sema).
Tek ornekle/tek modelle 'hazir' denmez -> model LISTESINI ayni film SETINDE kosar.
Her (model,film) icin dagilim + rol-kurtarma + YANLIS-DUSURME red-flag; sonunda
birlesik karsilastirma + MODEL-ANLASMAZLIGI (hangi satirda modeller ayrisiyor).
Kullanim: python qwen_kunye_batch.py "qwen3:8b,gemma4:e4b,gemma4:26b"
Cikti: E:\\MITAS\\_qwen_eval\\<model>\\<film>.json + ekrana ozet/tablolar."""
import json, urllib.request, sys, time, glob, os, re
from collections import Counter, defaultdict

sys.stdout.reconfigure(encoding="utf-8")

DB = r"E:\MITAS\Database"
MODELS = (sys.argv[1] if len(sys.argv) > 1 else "qwen3:8b").split(",")
CHUNK = 70

FILMS = [
    ("AHLAT_AGACI", "AHLAT_AGACI_son4dk_2"),
    ("YESIL_SOVALYE", "evoArcadmin_S_NEMA_F_LM4_2025-1274-1-0000-50-1-YE_L__VALYE"),
    ("MEHMED", "web_client_CAG1_2024-0007-0-0070-91-1-MEHMED_FET_HLER_SULTANI_2"),
    ("KAZANANLAR", "evoArcadmin_S_NEMA_F_LM4_2024-1266-1-0000-50-1-KAZANANLAR_KUL_B"),
    ("YALANCI_YALANCI", "evoArcadmin_COZUMLEMEV2S21_1997-0199-1-0000-00-1-YALANCI_YALANCI"),
]

ROLLER = ["oyuncu", "yonetmen", "yapimci", "yonetici yapimci", "senaryo", "goruntu yonetmeni",
          "muzik", "kurgu", "sanat", "kostum", "makyaj", "ses", "kurum", "diger",
          "seslendirme sanatcisi", "seslendirme yonetmeni", "ses kayit", "miksaj", "medya yonetimi", ""]
SCHEMA = {"type": "object", "properties": {"satirlar": {"type": "array", "items": {"type": "object",
    "properties": {"n": {"type": "integer"}, "etiket": {"type": "string", "enum": ["KADRO", "DUBLAJ", "UYARI", "ALTYAZI", "COP"]},
    "rol": {"type": "string", "enum": ROLLER}}, "required": ["n", "etiket", "rol"]}}}, "required": ["satirlar"]}

INSTR = """Asagidaki numarali film-jenerigi (kunye) satirlarini sinifla. Her satir icin {n, etiket, rol}.
etiket: KADRO(kunyede gercek kisi/kurum) | DUBLAJ(Turkce seslendirme ekibi) | UYARI(disclaimer/resmi beyan/tam cumle, kunye DEGIL) | ALTYAZI(diyalog/sarki sozu) | COP(bozuk OCR/anlamsiz VEYA sadece-rol-basligi isim yok)
rol (yalniz KADRO/DUBLAJ; digeri rol=""): KADRO=oyuncu,yonetmen,yapimci,yonetici yapimci,senaryo,goruntu yonetmeni,muzik,kurgu,sanat,kostum,makyaj,ses,kurum,diger ; DUBLAJ=seslendirme sanatcisi,seslendirme yonetmeni,ses kayit,miksaj,medya yonetimi,diger
KURALLAR:
1) Satir SADECE rol-basligiysa, isim YOKSA (PRODUCED BY, YONETMEN, OYUNCULAR, SENARYO, MUSIC BY, CAST...) -> COP.
2) Sirket/kurum/hizmet (catering,banka,sigorta,arac,nakliye,hukuk,trafik,otel,komisyon,post-prod sirketi) -> KADRO rol='kurum'. ASLA yapimci/yonetmen sayma.
3) Kisi adi ama rol net degilse -> rol='diger'. yapimci/yonetmeni TAHMIN ETME.
4) yonetmen/yapimci rolunu YALNIZ acik kanit (ismin hemen ustunde o baslik) varsa ver.
5) 'seslendirme yonetmeni' -> DUBLAJ, FILM yonetmeni DEGIL.
6) Disclaimer/resmi beyan ('...kabul ediyor','...olmadigindan...') -> UYARI.
7) Yeni isim UYDURMA; sadece etiketle.
/no_think

SATIRLAR:
"""

NAME_RE = re.compile(r"^[A-ZÇĞİÖŞÜ][a-zçğıöşü]+(?:\s+[A-ZÇĞİÖŞÜ][a-zçğıöşü]+){1,2}$")
def looks_name(t): return bool(NAME_RE.match(t.strip().title()))


def call(numbered, model):
    opts = {"temperature": 0, "repeat_penalty": 1.3, "num_ctx": 8192, "num_predict": 3584}
    payload = {"model": model, "prompt": INSTR + numbered, "stream": False, "format": SCHEMA, "options": opts}
    if "qwen" in model.lower():   # qwen3 thinking modeli; gemma'da think alani gereksiz
        payload["think"] = False
    req = urllib.request.Request("http://localhost:11434/api/generate",
        data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"})
    return json.loads(json.load(urllib.request.urlopen(req, timeout=300)).get("response", "{}"))


def classify(lines, model):
    items = []
    for c in range(0, len(lines), CHUNK):
        numbered = "\n".join(f"{c+i+1}. {l}" for i, l in enumerate(lines[c:c + CHUNK]))
        try:
            items.extend(call(numbered, model).get("satirlar", []))
        except Exception as e:
            print(f"      chunk {c+1}: HATA {type(e).__name__}: {str(e)[:60]}", flush=True)
    return {it["n"]: it for it in items if isinstance(it, dict) and "n" in it}


# --- film satirlarini bir kez yukle ---
films_lines = {}
for label, sub in FILMS:
    hits = glob.glob(os.path.join(DB, sub, "ocr", "**", "kunye.txt"), recursive=True)
    films_lines[label] = [l for l in open(hits[0], encoding="utf-8").read().splitlines() if l.strip()] if hits else None

results = {}   # (model,label) -> by_n
rows = []      # (model,label,satir,kadro,oyuncu,yon_yap,uyari,cop,redflag)
T0 = time.time()
for model in MODELS:
    outdir = os.path.join(r"E:\MITAS\_qwen_eval", re.sub(r"[^A-Za-z0-9._-]+", "_", model))
    os.makedirs(outdir, exist_ok=True)
    print(f"\n{'#'*70}\n# MODEL: {model}\n{'#'*70}", flush=True)
    for label, sub in FILMS:
        lines = films_lines[label]
        if not lines:
            print(f"[{label}] kunye.txt YOK — atlandi", flush=True); continue
        t = time.time()
        print(f"\n[{label}] {len(lines)} satir...", flush=True)
        by_n = classify(lines, model)
        results[(model, label)] = by_n
        json.dump({"model": model, "film": label, "items": list(by_n.values())},
                  open(os.path.join(outdir, label + ".json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        ed = Counter(it["etiket"] for it in by_n.values())
        rd = Counter(it.get("rol") for it in by_n.values() if it.get("rol"))
        yon_yap = sum(1 for it in by_n.values() if it["etiket"] == "KADRO" and it.get("rol") in ("yonetmen", "yapimci", "yonetici yapimci"))
        falsedrop = [(n, lines[n-1]) for n, it in by_n.items() if it["etiket"] in ("UYARI", "ALTYAZI") and looks_name(lines[n-1])]
        print(f"  etiket={dict(ed)} | rol={dict(rd.most_common(5))} | {time.time()-t:.0f}s", flush=True)
        print(f"  KADRO={ed.get('KADRO',0)} oyuncu={rd.get('oyuncu',0)} yon+yap={yon_yap} UYARI={ed.get('UYARI',0)} COP={ed.get('COP',0)}", flush=True)
        if falsedrop:
            print(f"  ⚠ RED FLAG yanlis-dusurme ({len(falsedrop)}): " + " || ".join(f"{n}:{x}" for n, x in falsedrop[:5]), flush=True)
        rows.append((model, label, len(lines), ed.get("KADRO", 0), rd.get("oyuncu", 0), yon_yap, ed.get("UYARI", 0), ed.get("COP", 0), len(falsedrop)))

# --- BIRLESIK KARSILASTIRMA ---
print(f"\n{'='*78}\nBIRLESIK TABLO | toplam {time.time()-T0:.0f}s")
print(f"{'model':<16}{'film':<16}{'satir':>6}{'KADRO':>6}{'oyun':>5}{'y+y':>4}{'UYARI':>6}{'COP':>5}{'redfl':>6}")
for r in rows:
    print(f"{r[0]:<16}{r[1]:<16}{r[2]:>6}{r[3]:>6}{r[4]:>5}{r[5]:>4}{r[6]:>6}{r[7]:>5}{r[8]:>6}")

# --- MODEL ANLASMAZLIGI (her filmde modeller etikette ne kadar ayrisiyor) ---
print(f"\n{'='*78}\nMODEL ANLASMAZLIGI (ayni satirda farkli etiket -> zor/belirsiz satir)")
for label, sub in FILMS:
    lines = films_lines[label]
    if not lines: continue
    present = [m for m in MODELS if (m, label) in results]
    if len(present) < 2: continue
    disagree = []
    for n in range(1, len(lines) + 1):
        ets = {m: results[(m, label)].get(n, {}).get("etiket") for m in present}
        vals = [v for v in ets.values() if v]
        if len(set(vals)) > 1:
            disagree.append((n, ets))
    print(f"\n[{label}] {len(disagree)}/{len(lines)} satirda anlasmazlik")
    for n, ets in disagree[:8]:
        print(f"   {n:>3} {lines[n-1][:40]:<40} " + " ".join(f"{m.split(':')[0][:7]}={ets[m]}" for m in present))
