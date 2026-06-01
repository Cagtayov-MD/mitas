"""20260531_2010 — KB film-ÇAPA demo (a): 10 filmi IMDB'de bul.
Strateji: film adi -> IMDB titles(primary/original) + akas(Turkce) ara -> tconst.
Sonra (sonraki adim) o filmin principals->names = beklenen kadro.
READ-ONLY. mitas.duckdb.
"""
import sys, re, json, importlib.util
from pathlib import Path
import duckdb
sys.stdout.reconfigure(encoding="utf-8")
spec=importlib.util.spec_from_file_location("fp",r"E:\MITAS\OCR-worktree\py\20260530_1744_full_pipeline.py"); fp=importlib.util.module_from_spec(spec); sys.modules["fp"]=fp; spec.loader.exec_module(fp)
DB=r"X:\DIGER\Mitas_Files\MitaData\mitas.duckdb"
con=duckdb.connect(DB, read_only=True)

def cols(t):
    try: return [r[0] for r in con.execute(f"DESCRIBE {t}").fetchall()]
    except Exception as e: return [f"ERR {e}"]
print("=== SEMA (kullanacagimiz tablolar) ===")
for t in ["imdb.titles","imdb.akas","imdb.principals","imdb.names","imdb.title_catalog","main.mitas_people_index"]:
    print(f"  {t}: {cols(t)}")

# --- film adindan baslik cikar (TIRE KORUNUR: X-MEN bozulmasin) ---
def title_of(name):
    stem=Path(name).stem
    m=re.search(r".*-\d-([A-Za-zÇĞİıÖŞÜçğıöşü].*)$", stem)
    t=(m.group(1) if m else stem)
    return t.replace("_"," ").strip()

def norm(s):
    s=(s or "").lower()
    for a,b in [("ı","i"),("i̇","i"),("ş","s"),("ğ","g"),("ç","c"),("ö","o"),("ü","u"),("'",""),("’",""),("-"," "),(":"," "),(".","")]:
        s=s.replace(a,b)
    # İ büyük -> i
    s=s.replace("İ","i").replace("I","i")
    return " ".join(s.split())

# 10 film (isim-parcasiyla metadata'dan bul)
WANT=["X-MEN","ANJELIK","JURASSIC","SON_METRO","DRAKULA","SENİN_HİKAYEN","YALAZA","DİRİLİŞ","BİZİM","KANSAS"]
meta=json.loads(Path(fp.META).read_text(encoding="utf-8"))
films=[]
for w in WANT:
    for it in meta:
        if w.replace("_","").upper() in Path(it["path"]).stem.replace("_","").upper():
            films.append((w, Path(it["path"]).name)); break

# DB tarafinda Turkce-katlama (fold) SQL ifadesi — norm() ile AYNI (tire/kesme dahil)
def FOLD(c):
    e=f"lower({c})"
    for a,b in [("ı","i"),("İ","i"),("ş","s"),("ğ","g"),("ç","c"),("ö","o"),("ü","u"),("i̇","i"),("'",""),("’",""),("-"," ")]:
        aa=a.replace("'","''"); bb=b.replace("'","''")   # SQL tek-tırnak kaçışı
        e=f"replace({e},'{aa}','{bb}')"
    return e

def year_of(name):
    m=re.search(r"(\d{4})-\d", Path(name).stem)
    return int(m.group(1)) if (m and 1900<=int(m.group(1))<=2026) else None

def keyword(nt):
    ws=[w for w in nt.split() if len(w)>=4]
    if ws: return max(ws,key=len)
    return nt  # kisa baslik (x men) -> tam nt ile ara, yil+exact siralar

print("\n=== FİLM-ÇAPA (IMDB'de ara — fold'lu) ===")
for w,name in films:
    t=title_of(name); nt=norm(t); key=keyword(nt); yr=year_of(name)
    print(f"\n[{w}] başlık='{t}' | norm='{nt}' | anahtar='{key}' | dosya-yıl={yr}")
    cands={}
    for r in con.execute(f"SELECT tconst,primaryTitle,originalTitle,startYear,titleType FROM imdb.titles WHERE {FOLD('primaryTitle')} LIKE ? OR {FOLD('originalTitle')} LIKE ? OR {FOLD('primaryTitle')} LIKE ? LIMIT 200",[f"%{nt}%",f"%{nt}%",f"%{key}%"]).fetchall():
        cands.setdefault(r[0],{"tc":r[0],"pt":r[1],"ot":r[2],"yr":r[3],"ty":r[4],"via":"titles","aka":None})
    for r in con.execute(f"SELECT a.tconst,a.title,a.region,t.primaryTitle,t.startYear,t.titleType FROM imdb.akas a JOIN imdb.titles t ON a.tconst=t.tconst WHERE {FOLD('a.title')} LIKE ? OR {FOLD('a.title')} LIKE ? LIMIT 200",[f"%{nt}%",f"%{key}%"]).fetchall():
        c=cands.setdefault(r[0],{"tc":r[0],"pt":r[3],"ot":None,"yr":r[4],"ty":r[5],"via":"akas","aka":r[1]})
        if not c.get("aka"): c["aka"]=r[1]
    def forms(c): return [f for f in [norm(c["pt"]),norm(c.get("ot") or ""),norm(c.get("aka") or "")] if f]
    def score(c):
        fs=forms(c); s=0
        if nt in fs: s+=100
        elif any(nt in f or f in nt for f in fs): s+=40
        elif any(key in f for f in fs): s+=15
        if c["ty"]=="movie": s+=10
        elif c["ty"] in ("tvSeries","tvMiniSeries"): s+=8
        if yr and c["yr"]:
            dy=abs(int(c["yr"])-yr)
            s += 50 if dy==0 else (25 if dy<=2 else (8 if dy<=5 else (-15 if dy>15 else 0)))
        return s
    ranked=[c for c in sorted(cands.values(),key=score,reverse=True) if score(c)>0][:3]
    if not ranked: print("   eşleşme YOK"); continue
    for c in ranked:
        ex="EXACT" if nt in forms(c) else "kısmi"
        print(f"   [{ex} s={score(c)}] {c['tc']} | {c['pt']} ({c['yr']},{c['ty']}) via={c['via']}"+(f" aka='{c['aka']}'" if c.get('aka') else ""))
con.close()
