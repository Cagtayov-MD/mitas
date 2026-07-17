# -*- coding: utf-8 -*-
"""PIPELINE v2 — BAĞLANMIŞ akış (model-DIŞ, thrashing'siz), sorunlu filmlerde.

AKIŞ: OneOCR+GLM metin → qwen3:8b (text) → QC → (gerekirse) qwen2.5vl + gemma4 VL
      → tiebreak (mutabakat→cross-cast→KB) → cast-supplement → KESİN KURAL → ONAYLI/KONTROL

Model-DIŞ döngü (thrashing yok): Faz1 hepsi text(qwen3) · Faz2 gerekenler qwen2.5vl, sonra gemma4
· Faz3 birleştir (GPU yok). Kararlar kilitli: #2 sadece-kişi yapımcı, #3 cast-supplement, #4 2-model VL.
"""
import glob, json, sys, unicodedata
sys.path.insert(0, r"E:\MITAS\scripts")
import credit_text_read as ctr
import credit_video_read as cv
cv.NUM_CTX = 40960
cv.PROMPT = (
    "Bunlar bir film jeneriğinin ARDIŞIK kareleri (video). Kareler boyunca görünen yazıları "
    "birleştir. SADECE karelerde AÇIKÇA YAZAN isimleri kullan, UYDURMA; yoksa 'yok'.\n"
    "YÖNETMEN: şu kalıpların YANINDAKİ/ALTINDAKİ KİŞİ adı: 'DIRECTED BY', 'A <İSİM> FILM' "
    "(ör. 'A JOHN McTIERNAN FILM' -> John McTiernan), 'A FILM BY', 'YÖNETMEN', 'YÖNETEN', "
    "'REJİSÖR', 'UN FILM DE', 'EIN FILM VON', 'REGIE', 'RÉALISÉ PAR'. "
    "'ASSISTANT DIRECTOR / DIRECTOR OF PHOTOGRAPHY / ART DIRECTOR / MUSIC' YÖNETMEN DEĞİLDİR. Net değilse 'yok'.\n"
    "Çıktıyı tam olarak şu formatta ver:\n"
    "YÖNETMEN: <isim | yok>\nYAPIMCI: <Producer/Yapımcı yanındaki isim(ler) | yok>\n"
    "OYUNCULAR: <görünen başrol oyuncu adları, en fazla 8, virgülle | yok>"
)
raw=open(r"C:\Users\TRT03\AppData\Local\Temp\claude\E--MITAS\28d49f5c-3526-4e51-9e6a-307b0914ffde\tasks\w3tz88lbf.output",encoding="utf-8",errors="ignore").read()
TAB={r["id"]:r for r in json.loads(raw)["result"]["table"]}

def fold(s):
    s=(s or "")
    for a,b in (("İ","i"),("I","i"),("ı","i"),("Ş","s"),("ş","s"),("Ğ","g"),("ğ","g"),
                ("Ü","u"),("ü","u"),("Ö","o"),("ö","o"),("Ç","c"),("ç","c")):
        s=s.replace(a,b)
    return unicodedata.normalize("NFKD",s).encode("ascii","ignore").decode().lower().strip()
def match(yon, gt):
    if not yon or not gt: return False
    gf=[fold(g) for g in gt]
    for y in yon:
        yf=fold(y)
        for g in gf:
            tk=[t for t in g.split() if len(t)>2]
            if tk and (tk[-1] in yf or yf in g or g in yf): return True
    return False
def base(fid):
    b=glob.glob(rf"E:\MITAS\Database\evoArcadmin*{fid}*"); return b[0] if b else None
def ocr_lines(fid):
    p=glob.glob(rf"E:\MITAS\Database\evoArcadmin*{fid}*\ocr\ocr-*\kunye.txt")
    return open(p[0],encoding="utf-8",errors="ignore").read().splitlines() if p else None
KB=cv.KB()

# SORUNLU 9 (text-abstain hedefi) + 3 KONTROL (text-only kalmalı)
FIDS=[("1973-0173-1-0000-85-1","sorunlu"),("1978-0178-1-0000-40-1","sorunlu"),
      ("1982-0253-1-0000-00-1","sorunlu"),("1984-0246-1-0000-00-1","sorunlu"),
      ("1985-0254-1-0000-00-1","sorunlu"),("1986-0241-1-0000-00-1","sorunlu"),
      ("1987-0248-1-0000-00-1","sorunlu"),("1989-0363-1-0000-00-1","sorunlu"),
      ("1990-0393-1-0000-00-1","sorunlu"),
      ("1977-0211-1-0000-90-1","kontrol"),("1996-0254-1-0000-00-1","kontrol"),
      ("1991-0392-1-0000-00-1","kontrol")]

# ───────── FAZ 1: TEXT (qwen3-only, hepsi) ─────────
print("===== FAZ 1: TEXT (qwen3:8b, think=False) — hepsi =====",flush=True)
text={}
for fid,kind in FIDS:
    title=TAB[fid].get("tr",""); lines=ocr_lines(fid)
    r=ctr.read_credits_auto(lines,title) if lines else {"yonetmen":[],"cast":[]}
    text[fid]=(r.get("yonetmen") or [], r.get("cast") or [])
    need=(not text[fid][0]) or (len(text[fid][1])<3)
    print(f"  {title[:24]:<25} yön={text[fid][0]} cast={len(text[fid][1])} → {'VL gerek' if need else 'TEXT-ONLY'}",flush=True)

need_vl=[fid for fid,_ in FIDS if (not text[fid][0]) or (len(text[fid][1])<3)]

# ───────── FAZ 2: VL (model-dış: önce qwen2.5vl, sonra gemma4) ─────────
def vl_run(model):
    out={}
    for fid in need_vl:
        b=base(fid)
        if not b or not glob.os.path.isdir(b+r"\frames\giris"): out[fid]=([],[]); continue
        g=b+r"\frames\giris"; c=b+r"\frames\cikis"
        try:
            res=cv.read_credits(g, c if glob.os.path.isdir(c) else None, models=[model], kb=KB)
            yon=res.get("yonetmen") or []; cast=res.get("cast") or []
            cf={fold(x) for x in cast}
            yon=ctr._only_persons([y for y in yon if fold(y) not in cf])  # self-consistency + KESİN KURAL
            out[fid]=(yon, ctr._only_persons(cast))
        except Exception as e:
            out[fid]=([f"HATA:{type(e).__name__}"],[])
        print(f"    [{model}] {TAB[fid].get('tr','')[:22]:<23} yön={out[fid][0]}",flush=True)
    return out

vlq=vlg={}
if need_vl:
    print(f"\n===== FAZ 2: VL — {len(need_vl)} film =====",flush=True)
    print("  -- qwen2.5vl:7b --",flush=True); vlq=vl_run("qwen2.5vl:7b")
    print("  -- gemma4:26b --",flush=True);   vlg=vl_run("gemma4:26b")

# ───────── FAZ 3: BİRLEŞTİR (GPU yok) ─────────
def tiebreak(q,g,all_cast_fold):
    agree=[y for y in q if any(fold(y)==fold(x) for x in g)]
    if agree: return [agree[0]], "MUTABAKAT"
    cands=[]
    for y in q+g:
        if not any(fold(y)==fold(x) for x in cands): cands.append(y)
    cands=[y for y in cands if fold(y) not in all_cast_fold]
    if not cands: return [], "PES (başrol-yönetmen, cross-cast)"
    kb_ok=[y for y in cands if KB.verify(y,"director")=="ONAY"]
    if len(kb_ok)==1: return kb_ok, "KB-tiebreak"
    if len(kb_ok)>1: return [], "PES (çoklu KB)"
    return [], "PES (mutabakat/KB yok)"

print("\n\n===== FAZ 3: BİRLEŞTİR + SONUÇ =====",flush=True)
txt_hit=full_hit=onayli=kontrol=0
for fid,kind in FIDS:
    title=TAB[fid].get("tr",""); gt=TAB[fid].get("dogru_yonetmen") or []
    tyon,tcast=text[fid]
    if match(tyon,gt): txt_hit+=1
    print(f"\n┌─ {title}  [{kind}]  (GT: {', '.join(gt)})",flush=True)
    print(f"│ TEXT: yön={tyon} cast={len(tcast)}",flush=True)
    fin=tyon; cast=list(tcast); how="text-only"
    if fid in need_vl:
        q,qc=vlq.get(fid,([],[])); g,gc=vlg.get(fid,([],[]))
        all_cast_fold={fold(x) for x in (tcast+qc+gc)}
        vlyon,htb=tiebreak(q,g,all_cast_fold)
        print(f"│ VL: qwen2.5vl={q} | gemma4={g} → tiebreak: {htb} → {vlyon}",flush=True)
        if not tyon and vlyon: fin=vlyon; how=f"VL({htb})"
        # #3 cast-supplement: metin cast<3 → VL cast'ten ekle
        if len(tcast)<3:
            add=[]
            for nm in qc+gc:
                if not any(fold(nm)==fold(x) for x in cast+add): add.append(nm)
            cast=ctr._only_persons(cast+add)
            if add: print(f"│ cast-supplement (#3): +{len(add)} VL oyuncu → {len(cast)} kişi",flush=True)
    fin=ctr._only_persons(fin)
    ok=match(fin,gt)
    if ok: full_hit+=1
    route="ONAYLI" if fin else "KONTROL"
    onayli+=bool(fin); kontrol+=(not fin)
    print(f"│ FİNAL: yön={fin or '[]'} cast={len(cast)} → {route} [{how}] {'✓' if ok else ('·boş' if not fin else '✗')}",flush=True)

print("\n"+"="*60,flush=True)
print(f"TEXT-ONLY doğru yönetmen: {txt_hit}/{len(FIDS)}",flush=True)
print(f"FULL PIPELINE doğru yönetmen: {full_hit}/{len(FIDS)}  (+{full_hit-txt_hit} VL kurtarma)",flush=True)
print(f"VL çağrılan film: {len(need_vl)}  ·  Route: ONAYLI={onayli} KONTROL={kontrol}",flush=True)
