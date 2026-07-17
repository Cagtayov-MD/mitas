# -*- coding: utf-8 -*-
"""KISA KOŞU: metin modellerinin (gemma3:12b + qwen3:8b) İKİSİNİN DE çuvalladığı
(MATCH olmayan) filmleri VISION'a (qwen2.5vl:7b + gemma4:26b) ver. Vision yönetmeni
KAREDEN kurtarabiliyor mu? Prompt+think+num_ctx düzgün ayarlı."""
import glob, json, sys, unicodedata
sys.path.insert(0, r"E:\MITAS\scripts")
import credit_video_read as cv

# --- VISION ayarları (düzgün) ---
cv.NUM_CTX = 40960  # 36 kare > 16384 → HTTP 400 fix
# Prompt: yönetmen-etiket kalıpları ekli (metin tarafıyla aynı mantık). think=False zaten read_segment'te.
cv.PROMPT = (
    "Bunlar bir film jeneriğinin ARDIŞIK kareleri (video). Kareler boyunca görünen yazıları "
    "birleştir. SADECE karelerde AÇIKÇA YAZAN isimleri kullan, UYDURMA; yoksa 'yok'.\n"
    "YÖNETMEN: şu kalıpların YANINDAKİ/ALTINDAKİ KİŞİ adı: 'DIRECTED BY', 'A <İSİM> FILM' "
    "(ör. 'A JOHN McTIERNAN FILM' -> John McTiernan), 'A FILM BY', 'YÖNETMEN', 'YÖNETEN', "
    "'REJİSÖR', 'UN FILM DE', 'EIN FILM VON', 'REGIE', 'RÉALISÉ PAR'. "
    "'ASSISTANT DIRECTOR / DIRECTOR OF PHOTOGRAPHY / ART DIRECTOR / MUSIC' YÖNETMEN DEĞİLDİR. Net değilse 'yok'.\n"
    "Çıktıyı tam olarak şu formatta ver:\n"
    "YÖNETMEN: <isim | yok>\n"
    "YAPIMCI: <Producer/Yapımcı yanındaki isim(ler) | yok>\n"
    "OYUNCULAR: <görünen başrol oyuncu adları, en fazla 8, virgülle | yok>"
)

raw=open(r"C:\Users\TRT03\AppData\Local\Temp\claude\E--MITAS\28d49f5c-3526-4e51-9e6a-307b0914ffde\tasks\w3tz88lbf.output",encoding="utf-8",errors="ignore").read()
TAB={r["id"]:r for r in json.loads(raw)["result"]["table"]}
TXT=json.load(open(r"E:\MITAS\outputs\per_model_yon.json",encoding="utf-8"))  # gemma3 + qwen3 sonuçları

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

# --- metnin İKİSİNİN DE çuvalladığı + GT olan + karesi olan filmler ---
cand=[]
for fid,rec in TAB.items():
    gt=rec.get("dogru_yonetmen") or []
    if not gt: continue
    g3=classify(TXT.get(fid,{}).get("gemma3:12b"), gt)
    q8=classify(TXT.get(fid,{}).get("qwen3:8b"), gt)
    if g3=="MATCH" or q8=="MATCH": continue   # en az biri bulduysa atla
    b=base(fid)
    if not b or not glob.os.path.isdir(b+r"\frames\giris"): continue  # kare yoksa vision koşamaz
    cand.append((fid, rec.get("tr",""), ", ".join(gt), g3, q8))

cand=cand[:9]  # kısa koşu
print(f"=== Metnin ikisinin de çuvalladığı {len(cand)} film → VISION ===",flush=True)
print(f"{'FİLM':<24}{'GT':<18}{'qwen2.5vl':<22}{'gemma4:26b':<22}",flush=True)
print("-"*92,flush=True)
kb=cv.KB()
sv={"qwen2.5vl:7b":{"MATCH":0,"WRONG":0,"ABSTAIN":0},"gemma4:26b":{"MATCH":0,"WRONG":0,"ABSTAIN":0}}
rows={}
for model in ("qwen2.5vl:7b","gemma4:26b"):
    print(f"\n--- {model} koşuyor ---",flush=True)
    for fid,tr,gt,g3,q8 in cand:
        b=base(fid); g=b+r"\frames\giris"; c=b+r"\frames\cikis"
        try:
            yon=cv.read_credits(g, c if glob.os.path.isdir(c) else None, models=[model], kb=kb).get("yonetmen") or []
        except Exception as e: yon=[f"HATA:{type(e).__name__}"]
        cls=classify(yon, gt.split(", "))
        sv[model][cls]=sv[model].get(cls,0)+1
        rows.setdefault(fid,{})[model]=(yon,cls)
        fl="+" if cls=="MATCH" else ("X" if cls=="WRONG" else ".")
        print(f"  {fl} {tr[:22]:<23} {yon}",flush=True)

print("\n\n================ ÖZET: metnin kaçırdığını VISION kurtardı mı ================",flush=True)
print(f"{'FİLM':<22}{'GT':<16}{'qwen2.5vl':<24}{'gemma4:26b'}",flush=True)
print("-"*96,flush=True)
for fid,tr,gt,g3,q8 in cand:
    qv=rows.get(fid,{}).get("qwen2.5vl:7b",([],"-")); gv=rows.get(fid,{}).get("gemma4:26b",([],"-"))
    def cell(t): y,c=t; return f"{'+' if c=='MATCH' else ('X' if c=='WRONG' else '.')} {', '.join(y)[:20]}"
    print(f"{tr[:20]:<22}{gt[:15]:<16}{cell(qv):<24}{cell(gv)}",flush=True)
print("-"*96,flush=True)
for m in ("qwen2.5vl:7b","gemma4:26b"):
    c=sv[m]; tot=c['MATCH']+c['WRONG']+c['ABSTAIN']
    print(f"{m}: KURTARDI(MATCH)={c['MATCH']}/{tot}  YANLIŞ={c['WRONG']}  boş={c['ABSTAIN']}",flush=True)
print("\n(Metin bu filmlerde MATCH=0 idi; vision'ın MATCH'i = net kurtarma.)",flush=True)
