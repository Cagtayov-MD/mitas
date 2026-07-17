# -*- coding: utf-8 -*-
"""qwen3-vl:30b'yi aynı 9 filmde (metnin ikisinin de çuvalladığı) koş, qwen2.5vl + gemma4 ile kıyasla.
Prompt+think+num_ctx düzgün ayarlı. Soru: vision'ın '3' nesli, 2.5'ten iyi mi?"""
import glob, json, sys, unicodedata
sys.path.insert(0, r"E:\MITAS\scripts")
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
TXT=json.load(open(r"E:\MITAS\outputs\per_model_yon.json",encoding="utf-8"))

def fold(s):
    s=(s or "")
    for a,b in (("İ","i"),("I","i"),("ı","i"),("Ş","s"),("ş","s"),("Ğ","g"),("ğ","g"),
                ("Ü","u"),("ü","u"),("Ö","o"),("ö","o"),("Ç","c"),("ç","c")):
        s=s.replace(a,b)
    return unicodedata.normalize("NFKD",s).encode("ascii","ignore").decode().lower().strip()
def classify(got, gt):
    if not isinstance(got,list) or not got: return "ABSTAIN"
    if not gt: return "GT-YOK"
    gf=[fold(g) for g in gt]
    for y in got:
        yf=fold(y)
        for g in gf:
            tk=[t for t in g.split() if len(t)>2]
            if tk and (tk[-1] in yf or yf in g or g in yf): return "MATCH"
    return "WRONG"
def base(fid):
    b=glob.glob(rf"E:\MITAS\Database\evoArcadmin*{fid}*"); return b[0] if b else None

# önceki sonuçlar (qwen2.5vl / gemma4) — kıyas için
PREV={
 "AĞLIYORUM":(".","."),"MUHTEŞEM WALDO PEPPER":("X Redford","."),"SESSİZ ÖLÜM":("✓","✓"),
 "GERÇEK HAYAT":("✓","✓"),"ASİ":("✓","✓"),"KAR KRALİÇESİ":("✓","X Randall"),
 "UZAYDAKİ SIR":("✓","✓"),"UŞAKLARIN ZAMANI":("✓","✓"),"ÖNCE AĞLARSIN":("✓","✓"),
}

cand=[]
for fid,rec in TAB.items():
    gt=rec.get("dogru_yonetmen") or []
    if not gt: continue
    if classify(TXT.get(fid,{}).get("gemma3:12b"),gt)=="MATCH" or classify(TXT.get(fid,{}).get("qwen3:8b"),gt)=="MATCH": continue
    b=base(fid)
    if not b or not glob.os.path.isdir(b+r"\frames\giris"): continue
    cand.append((fid, rec.get("tr",""), ", ".join(gt)))
cand=cand[:9]

kb=cv.KB()
print(f"--- qwen3-vl:30b, {len(cand)} film (metnin ikisinin de çuvalladığı) ---",flush=True)
sv={"MATCH":0,"WRONG":0,"ABSTAIN":0}
rows={}
for fid,tr,gt in cand:
    b=base(fid); g=b+r"\frames\giris"; c=b+r"\frames\cikis"
    try:
        yon=cv.read_credits(g, c if glob.os.path.isdir(c) else None, models=["qwen3-vl:30b"], kb=kb).get("yonetmen") or []
    except Exception as e: yon=[f"HATA:{type(e).__name__}"]
    cls=classify(yon, gt.split(", "))
    sv[cls]=sv.get(cls,0)+1; rows[tr]=(yon,cls)
    fl="+" if cls=="MATCH" else ("X" if cls=="WRONG" else ".")
    print(f"  {fl} {tr[:22]:<23} {yon}",flush=True)

print("\n========= 3'LÜ KIYAS (metin bu 9 filmde 0 bulmuştu) =========",flush=True)
print(f"{'FİLM':<22}{'GT':<16}{'qwen2.5vl':<12}{'gemma4:26b':<14}{'qwen3-vl:30b'}",flush=True)
print("-"*92,flush=True)
for fid,tr,gt in cand:
    q25,g4=PREV.get(tr,("?","?"))
    y,c=rows.get(tr,([],"-")); q3=("+ " if c=="MATCH" else ("X " if c=="WRONG" else ". "))+", ".join(y)[:16]
    print(f"{tr[:20]:<22}{gt[:15]:<16}{q25:<12}{g4:<14}{q3}",flush=True)
print("-"*92,flush=True)
print(f"qwen3-vl:30b: MATCH={sv['MATCH']}/9  WRONG={sv['WRONG']}  boş={sv['ABSTAIN']}",flush=True)
print("qwen2.5vl:7b=7/9 · gemma4:26b=6/9 (önceki). qwen3-vl bunları geçti mi?",flush=True)
