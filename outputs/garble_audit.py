# -*- coding: utf-8 -*-
"""ONAYLI/KONTROL künye garble + kontaminasyon denetimi (DB'siz, yüksek-isabet).
Database/*/pdf/kunye_teslim.md + _DURUM.json okur; oyuncu/yönetmen/yapımcı bloklarını
çıkarır; near-dup (aynı kart varyantı), rol/kurum/cümle token'ı, cast↔crew kontaminasyonu,
başlık-parçası, garbled rol-etiketi sinyallerini bulur. Çıktı: kanıtlı tablo."""
from __future__ import annotations
import json, re, sys, unicodedata
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
DB = Path(r"E:\MITAS\Database")

def fold(s: str) -> str:
    s = (s or "").replace("ı","i").replace("İ","i").replace("ş","s").replace("Ş","s")
    s = s.replace("ğ","g").replace("Ğ","g").replace("ç","c").replace("Ç","c")
    s = s.replace("ö","o").replace("Ö","o").replace("ü","u").replace("Ü","u")
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c)).upper()
    s = re.sub(r"[^A-Z ]+"," ",s)
    return re.sub(r"\s+"," ",s).strip()

def lev(a: str, b: str) -> int:
    if a == b: return 0
    if not a: return len(b)
    if not b: return len(a)
    prev = list(range(len(b)+1))
    for i,ca in enumerate(a,1):
        cur=[i]
        for j,cb in enumerate(b,1):
            cur.append(min(prev[j]+1, cur[j-1]+1, prev[j-1]+(ca!=cb)))
        prev=cur
    return prev[-1]

def sim(a,b):
    a,b=fold(a),fold(b)
    m=max(len(a),len(b)) or 1
    return 1-lev(a,b)/m

# rol/kurum/cümle token blocklist (folded)
ROLE_INST = {
 "KUVVETLERI","SILAHLI","MUSTEREKEN","CEVIRDIGI","CEVIRME","TARAFINDAN","ORDU","ORDUSU",
 "DESIGNER","DIRECTOR","PRODUCER","EDITOR","OPERATOR","SENATORS","SENATOR","CHORUS","IORUS",
 "MAKEUP","MAKSUP","BASIGNER","FILMI","FILMHI","SANAK","PIIMIM","SOMR","ARSUANL","THEBAN",
 "PRODUCED","DIRECTED","SCREENPLAY","CAMERA","MUSIC","SOUND","COSTUME","COMPANY","STUDIO",
 "PICTURES","PRESENTS","STARRING",
}
# Türkçe fiil/cümle eki (isim olmaz)
VERB_SUFFIX = ("DIGI","DUGU","DIGINI","ERKEN","EREK","MEKTE","MAKTA","TIGI","TUGU","MISTIR","MUSTUR")
# garbled olabilecek rol-etiketi referansları (fuzzy)
ROLE_REF = ["DESIGNER","DIRECTOR","PRODUCER","EDITOR","OPERATOR","CAMERAMAN","SUPERVISOR","ASSISTANT","COMPOSER"]

def split_names(line: str):
    # "- Yönetmen: A, B, C" -> [A,B,C]
    if ":" in line: line = line.split(":",1)[1]
    parts = re.split(r"[,;]", line)
    return [p.strip(" -•\t") for p in parts if p.strip(" -•\t")]

def parse_md(md: Path):
    txt = md.read_text(encoding="utf-8", errors="ignore")
    title = ""
    m = re.search(r"^#\s*M[İI]TAS.*?•\s*(.+)$", txt, re.M)
    if m: title = m.group(1).strip()
    def block(header, stop):
        mm = re.search(rf"##\s*{header}\s*\n(.*?)(?:\n##\s*{stop}|\Z)", txt, re.S)
        return mm.group(1) if mm else ""
    cast = [x.strip(" -•\t") for x in block("Oyuncular","").splitlines() if x.strip(" -•\t")] if "## Oyuncular" in txt else []
    # crew block
    crew = block("Yap[ıi]m Ekibi","Ses")
    yon, yap = [], []
    for ln in crew.splitlines():
        lf = fold(ln)
        if lf.startswith("YONETMEN"): yon = split_names(ln)
        elif lf.startswith("YAPIMCI"): yap = split_names(ln)
    return title, cast, yon, yap

def looks_garble(name: str) -> str|None:
    """Yalnız YÜKSEK-İSABET sinyaller (gerçek isme kurt deme)."""
    f = fold(name)
    toks = f.split()
    if not toks: return None
    # cümle eki (CEVIRDIGI, HAZIRLANMISTIR)
    for t in toks:
        if any(t.endswith(s) and len(t)>5 for s in VERB_SUFFIX):
            return f"cümle/fiil-eki ({t})"
    # rol/kurum/çöp token (tam eşleşme blocklist)
    hit = [t for t in toks if t in ROLE_INST]
    if hit: return f"rol/kurum/çöp token ({','.join(hit)})"
    # fuzzy garbled rol etiketi (DIRECTON~DIRECTOR, PRODACERS~PRODUCER)
    for t in toks:
        if len(t)>=6:
            for r in ROLE_REF:
                if 0 < lev(t,r) <= 2:
                    return f"garbled rol-etiketi ({t}~{r})"
    return None

report = []
for hub in sorted(DB.glob("*/")):
    md = hub/"pdf"/"kunye_teslim.md"
    dur = hub/"_DURUM.json"
    if not md.exists(): continue
    karar = "?"
    title2 = ""
    if dur.exists():
        try:
            dd = json.load(open(dur, encoding="utf-8"))
            karar = dd.get("karar","?"); title2 = dd.get("title","")
        except Exception: pass
    title, cast, yon, yap = parse_md(md)
    title = title or title2
    flags = []
    all_entries = [("oyuncu",c) for c in cast] + [("yönetmen",y) for y in yon] + [("yapımcı",p) for p in yap]
    # 1) garble/role/inst per entry
    for role, nm in all_entries:
        g = looks_garble(nm)
        if g: flags.append(("HIGH", f"[{role}] '{nm}' → {g}"))
    # 2) near-dup. Aynı token-sayısı + her token benzer ama eşit değil = GARBLE varyantı (yüksek isabet).
    #    Farklı token-sayısı (alt-küme) = JR/SR veya tekrar olası (DÜŞÜK isabet, ayrı işaretle).
    seen_pairs=set()
    for i in range(len(all_entries)):
        for j in range(i+1,len(all_entries)):
            a,b = all_entries[i][1], all_entries[j][1]
            fa,fb = fold(a),fold(b)
            if fa==fb: continue
            s = sim(a,b)
            if s<0.6 or s>0.97 or min(len(fa),len(fb))<5: continue
            key=tuple(sorted([fa,fb]))
            if key in seen_pairs: continue
            seen_pairs.add(key)
            ta,tb=fa.split(),fb.split()
            if len(ta)==len(tb) and len(ta)>=1 and all(0<lev(x,y)<=max(2,len(x)//2) for x,y in zip(ta,tb)):
                flags.append(("HIGH", f"garble-varyant ({s:.0%}): '{a}' ≈ '{b}'"))
            else:
                flags.append(("LOW", f"olası tekrar/JR-SR ({s:.0%}): '{a}' ≈ '{b}'"))
    # 3) cast↔crew kontaminasyon
    cast_f = {fold(c) for c in cast}
    for role,lst in (("yönetmen",yon),("yapımcı",yap)):
        for nm in lst:
            if fold(nm) in cast_f:
                flags.append(("HIGH", f"cast↔{role} kontaminasyon: '{nm}'"))
    # 4) başlık parçası
    tf = fold(title)
    for role,nm in all_entries:
        nf=fold(nm)
        if nf and (sim(nf,tf)>=0.6 or (len(nf)>=5 and any(sim(nf,w)>=0.7 for w in tf.split() if len(w)>=5))):
            flags.append(("HIGH", f"başlık-parçası: [{role}] '{nm}' ≈ '{title}'"))
    high = [m for lv,m in flags if lv=="HIGH"]
    low  = [m for lv,m in flags if lv=="LOW"]
    if high or low:
        report.append((karar, title or hub.name, high, low))

# çıktı: ONAYLI önce, HIGH sinyali olanlar üstte
order = {"Hazır":0,"Kontrol":1,"?":2}
report.sort(key=lambda r:(order.get(r[0],3), -len(r[2]), r[1]))
on = [r for r in report if r[0]=="Hazır"]
ko = [r for r in report if r[0]!="Hazır"]
on_bad = [r for r in on if r[2]]
print(f"=== TARANAN: {sum(1 for _ in DB.glob('*/pdf/kunye_teslim.md'))} künye ===")
print(f"=== ONAYLI'da KESİN bozuk (HIGH sinyal): {len(on_bad)}/5 ===\n")
print("################ ONAYLI (export'ta — 'ayıp' kapsamı) ################")
for karar,title,high,low in on:
    tag = "🔴 KESİN BOZUK" if high else ("🟡 şüpheli" if low else "temiz")
    print(f"\n● [{karar}] {title}   {tag}")
    for m in high: print(f"    ✗ {m}")
    for m in low:  print(f"    ? {m}")
print("\n\n################ KONTROL (zaten ayrılmış — doğru yakalananlar) ################")
for karar,title,high,low in ko:
    print(f"\n○ [{karar}] {title}  (HIGH={len(high)}, şüpheli={len(low)})")
    for m in (high+low)[:4]: print(f"    - {m}")
    if len(high+low)>4: print(f"    ... +{len(high+low)-4} daha")
