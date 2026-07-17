# -*- coding: utf-8 -*-
"""QC2 GERÇEK ÖLÇÜM — son batch çıktısını laf değil sayıyla denetler.
Her hub: yönetmen-garble? özet-bok? afiş-yatay/yok? tier ne?
"""
import os, re, json, glob, io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

DB = r"E:\MITAS\Database"
AFIS = r"E:\MITAS\_102_afis_cache"
N = 50  # son kaç film

# --- yardımcılar ---
CREDIT_WORDS = ("BASED ON", "CREATED", "CHARACTERS", "ADAPTED", "WRITTEN BY",
                "SCREENPLAY", "STORY BY", "FROM THE NOVEL", "PRODUCED BY",
                "A FILM BY", "DIRECTED BY")
SUMMARY_BAD = ("—", "placeholder", "Bu kopya", "transkript çıkarılamadı",
               "desteklenmeyen dil", "bulunamadı")

def parse_md(md_path):
    txt = open(md_path, encoding="utf-8").read() if os.path.exists(md_path) else ""
    yon = re.search(r"Yönetmen:\s*(.+)", txt)
    yon = yon.group(1).strip() if yon else ""
    # özet bloğu
    m = re.search(r"## Özet\s*\n(.+)", txt, re.S)
    ozet = (m.group(1).strip() if m else "")
    return yon, ozet, txt

def yon_garble(yon):
    if not yon or yon == "—":
        return "BOŞ"
    u = yon.upper()
    if any(w in u for w in CREDIT_WORDS):
        return "CREDIT-CÜMLE"      # "BASED ON THE POPEYE..."
    if len(yon) > 45:
        return "ÇOK-UZUN"
    # 4+ isim → muhtemelen garble/crew karışmış
    parts = [p for p in re.split(r"[,;]", yon) if p.strip()]
    if len(parts) >= 4:
        return "4+İSİM"
    return ""

def ozet_garble(ozet):
    if not ozet:
        return "YOK"
    first = ozet.split("\n")[0].strip()
    if any(b.lower() in ozet.lower() for b in SUMMARY_BAD) and len(first) < 30:
        return "PLACEHOLDER"
    wc = len(re.findall(r"\w+", ozet))
    if wc < 20:
        return f"KISA({wc}k)"
    return ""

def afis_durum(trt):
    if not trt or trt == "—":
        return "?"
    p = os.path.join(AFIS, trt.replace("/", "_") + ".jpg")
    cands = glob.glob(os.path.join(AFIS, "*" + (trt.split("-")[-1] if "-" in trt else trt) + "*"))
    path = p if os.path.exists(p) else (cands[0] if cands else None)
    if not path or not os.path.exists(path):
        return "YOK"
    try:
        from PIL import Image
        w, h = Image.open(path).size
        return "DİKEY-OK" if h > w * 1.15 else f"YATAY({w}x{h})"
    except Exception:
        return "okunamadı"

# --- topla ---
durums = sorted(glob.glob(os.path.join(DB, "*", "_DURUM.json")),
                key=os.path.getmtime, reverse=True)[:N]

rows = []
for d in durums:
    try:
        j = json.load(open(d, encoding="utf-8"))
    except Exception:
        continue
    hub = os.path.dirname(d)
    title = j.get("title", "?")
    karar = j.get("karar", "?")
    trt = j.get("trt_id", "")
    md = os.path.join(hub, "pdf", "kunye_teslim.md")
    yon, ozet, _ = parse_md(md)
    rows.append({
        "title": title, "karar": karar,
        "yon_flag": yon_garble(yon), "yon": yon[:50],
        "ozet_flag": ozet_garble(ozet),
        "afis": afis_durum(trt),
    })

# --- rapor ---
print(f"=== SON {len(rows)} FİLM — QC2 GERÇEK ÖLÇÜM ===\n")
yg = [r for r in rows if r["yon_flag"] and r["yon_flag"] != "BOŞ"]
yb = [r for r in rows if r["yon_flag"] == "BOŞ"]
og = [r for r in rows if r["ozet_flag"]]
ay = [r for r in rows if r["afis"].startswith("YATAY")]
an = [r for r in rows if r["afis"] == "YOK"]

print(f"YÖNETMEN garble (credit-cümle/uzun/4+isim): {len(yg)}/{len(rows)}")
for r in yg:
    print(f"   ✗ {r['title'][:30]:30} [{r['yon_flag']}] {r['yon']}  → {r['karar']}")
print(f"\nYÖNETMEN boş: {len(yb)}/{len(rows)}")

print(f"\nÖZET bozuk/yok/kısa: {len(og)}/{len(rows)}")
for r in og:
    print(f"   ✗ {r['title'][:30]:30} [{r['ozet_flag']}]  → {r['karar']}")

print(f"\nAFİŞ yatay (frame-grab şüphesi): {len(ay)}/{len(rows)}")
for r in ay:
    print(f"   ✗ {r['title'][:30]:30} {r['afis']}  → {r['karar']}")
print(f"AFİŞ yok: {len(an)}/{len(rows)}")

# karar dağılımı
from collections import Counter
kc = Counter(r["karar"] for r in rows)
print(f"\nKARAR DAĞILIMI: {dict(kc)}")

# en kritik: garble AMA Hazır/Onaylı geçmiş olanlar
sizan = [r for r in rows if (r["yon_flag"] and r["yon_flag"] != "BOŞ" or r["ozet_flag"] or r["afis"].startswith("YATAY"))
         and r["karar"] in ("Hazır", "Hazir", "Onayli", "Onaylı")]
print(f"\n🔴 SIZAN (bozuk AMA Hazır/Onaylı): {len(sizan)}/{len(rows)}")
for r in sizan:
    print(f"   {r['title'][:30]:30} yon={r['yon_flag']} ozet={r['ozet_flag']} afis={r['afis']} → {r['karar']}")
