# -*- coding: utf-8 -*-
"""PIPELINE v2 TEST — konuştuğumuz tam akış, adım adım, bozuk filmlerde.

1) OneOCR+GLM metni (kunye.txt) → METİN rol-eşleme (credit_text_read.read_credits_auto:
   gemma3:12b + qwen3:8b ensemble, think=False, prompt-fix, fuse+KB+garble+self-consistency)
2) QC KAPISI: yönetmen BOŞ  VEYA  cast<3 (oyuncuda soru)  → VL re-read tetikle. Değilse text-only.
3) VL RE-READ: qwen2.5vl:7b + gemma4:26b (kareler, prompt-fix, num_ctx=40960, think=False).
   Her modelin yönetmeninden, O MODELİN cast'inde de geçeni at (self-consistency: başrol-yönetmen).
4) TIEBREAK MERDİVENİ (çelişkiyi ATMA, ÇÖZ):
   a. ikisi AYNI → mutabakat (al)
   b. çelişki → KB-onaylı (IMDB director) olanı seç
   c. ikisi de KB-onaysız → PES, Kontrol (dürüst)
   VL yönetmeni metnin BOŞ alanını DOLDURUR (text'in güvenle okuduğunu EZMEZ).
5) ROUTE: yönetmen çözüldü → ONAYLI ; çözülemedi → KONTROL.

Ölçüt: text-only kaç yönetmen bulurdu vs FULL pipeline kaç buluyor + Kar Kraliçesi tiebreak ile kurtuluyor mu.
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
TXT=json.load(open(r"E:\MITAS\outputs\per_model_yon.json",encoding="utf-8"))

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

def vl_one(fid, model):
    """Bir VL modeli: yönetmen + cast; yönetmenden O MODELİN cast'inde geçeni at (self-consistency)."""
    b=base(fid); g=b+r"\frames\giris"; c=b+r"\frames\cikis"
    res=cv.read_credits(g if glob.os.path.isdir(g) else None,
                        c if glob.os.path.isdir(c) else None, models=[model], kb=KB)
    yon=res.get("yonetmen") or []; cast=res.get("cast") or []
    cf={fold(x) for x in cast}
    yon2=[y for y in yon if fold(y) not in cf]   # başrol-yönetmen ayıkla
    yon2=ctr._only_persons(yon2)                 # KESİN KURAL: gerçek İsim Soyisim
    return yon2, ctr._only_persons(cast)

def tiebreak(q, g, all_cast_fold):
    """Tam merdiven: a) mutabakat b) cross-cast self-consistency c) KB-onay d) pes."""
    # a) MUTABAKAT — gerçek oyuncu-yönetmen (Eastwood) burada hayatta kalır
    agree=[y for y in q if any(fold(y)==fold(x) for x in g)]
    if agree: return [agree[0]], "MUTABAKAT"
    # b) mutabakat yok → aday HERHANGİ cast'te (metin+qwen+gemma) ise BAŞROL → ELE (cross-cast)
    cands=[]
    for y in q+g:
        if not any(fold(y)==fold(x) for x in cands): cands.append(y)
    cands=[y for y in cands if fold(y) not in all_cast_fold]
    if not cands: return [], "PES (başrol-yönetmen, cross-cast elendi)"
    # c) hayatta kalanlar arasında KB-onaylı yönetmen (Kar Kraliçesi: Gates)
    kb_ok=[y for y in cands if KB.verify(y,"director")=="ONAY"]
    if len(kb_ok)==1: return kb_ok, "KB-tiebreak"
    if len(kb_ok)>1: return [], "PES (çoklu KB-yönetmen, belirsiz)"
    return [], "PES (mutabakat yok + KB onaysız)"

# --- TEST SETİ: 9 metin-çuvalladığı (VL hedefi) + 3 metin-başardığı (kontrol: VL'ye GİTMEMELİ) ---
abst=[]
for fid,rec in TAB.items():
    gt=rec.get("dogru_yonetmen") or []
    if not gt: continue
    if match(TXT.get(fid,{}).get("gemma3:12b") if isinstance(TXT.get(fid,{}).get("gemma3:12b"),list) else [],gt) \
       or match(TXT.get(fid,{}).get("qwen3:8b") if isinstance(TXT.get(fid,{}).get("qwen3:8b"),list) else [],gt): continue
    b=base(fid)
    if not b or not glob.os.path.isdir(b+r"\frames\giris"): continue
    abst.append(fid)
abst=abst[:9]
controls=["1977-0211-1-0000-90-1","1996-0254-1-0000-00-1","1991-0392-1-0000-00-1"]  # Star Wars, Kırık Ok, Lisede Panik
TESTS=[(f,"ABSTAIN-hedef") for f in abst]+[(f,"KONTROL-çapa") for f in controls if f in TAB]

txt_hit=full_hit=onayli=kontrol=vl_calls=0
print(f"==== PIPELINE v2 TEST — {len(TESTS)} film, adım adım ====\n",flush=True)
for fid,kind in TESTS:
    rec=TAB[fid]; title=rec.get("tr",""); gt=rec.get("dogru_yonetmen") or []
    print(f"┌─ {title}  [{kind}]   (GT yönetmen: {', '.join(gt)})",flush=True)
    lines=ocr_lines(fid)
    # 1) METİN
    t=ctr.read_credits_auto(lines, title) if lines else {"yonetmen":[],"cast":[]}
    tyon=t.get("yonetmen") or []; tcast=t.get("cast") or []
    print(f"│ 1) METİN (OneOCR+GLM→qwen ens.): yön={tyon}  cast={len(tcast)} kişi",flush=True)
    if match(tyon,gt): txt_hit+=1
    # 2) QC
    need = (not tyon) or (len(tcast)<3)
    why = "yönetmen BOŞ" if not tyon else (f"cast<3 ({len(tcast)})" if len(tcast)<3 else "")
    fin=tyon; how="text-only"
    if not need:
        print(f"│ 2) QC: yönetmen var + cast yeterli → TEXT-ONLY (VL'ye gitmez)",flush=True)
    else:
        print(f"│ 2) QC: {why} → VL RE-READ tetiklendi",flush=True)
        vl_calls+=1
        # 3) VL iki model (yön + cast)
        q,qc=vl_one(fid,"qwen2.5vl:7b"); g,gc=vl_one(fid,"gemma4:26b")
        print(f"│ 3) VL: qwen2.5vl→{q} | gemma4→{g}",flush=True)
        # cross-cast self-consistency için: metin cast + iki VL cast birleşimi
        all_cast_fold={fold(x) for x in (tcast+qc+gc)}
        # 4) tiebreak (tam merdiven: mutabakat → cross-cast → KB → pes)
        vlyon,htb=tiebreak(q,g,all_cast_fold)
        print(f"│ 4) TIEBREAK: {htb} → {vlyon}",flush=True)
        # 5) VL DOLDURUR (text boşsa)
        if not tyon and vlyon:
            fin=vlyon; how=f"VL({htb})"
        elif tyon:
            fin=tyon; how="text (VL cast için çağrıldı)"
        else:
            fin=[]; how=f"VL-{htb}"
    # QC SON SÜZGEÇ (KESİN KURAL): final yönetmen de gerçek İsim Soyisim olmalı
    fin=ctr._only_persons(fin)
    # ROUTE
    ok=match(fin,gt)
    if fin: route="ONAYLI"; onayli+=1
    else: route="KONTROL"; kontrol+=1
    if ok: full_hit+=1
    print(f"│ 5) FİNAL: {fin or '[]'}  → {route}  [{how}]  {'✓ GT eşleşti' if ok else ('· boş→Kontrol' if not fin else '✗ GT tutmadı')}",flush=True)
    print(f"└────────────────────────────────────────────────\n",flush=True)

print("="*60,flush=True)
print(f"TEXT-ONLY doğru yönetmen: {txt_hit}/{len(TESTS)}",flush=True)
print(f"FULL PIPELINE doğru yönetmen: {full_hit}/{len(TESTS)}   (+{full_hit-txt_hit} kurtarma)",flush=True)
print(f"VL çağrısı: {vl_calls} film (ötekiler text-only, hızlı)",flush=True)
print(f"Route: ONAYLI={onayli}  KONTROL={kontrol}",flush=True)
