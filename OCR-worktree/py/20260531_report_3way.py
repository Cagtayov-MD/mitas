"""tester_3way içindeki tamamlanmış compare.json'ları okuyup KARŞILAŞTIRMA RAPORU üretir.
Hem koşu sürerken (kısmi) hem bitince (tam) çalışır. Çıktı: tester_3way/_RAPOR.md + stdout.
"""
import sys, json
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
OUT = Path(r"E:\MITAS\OCR-worktree\tester_3way")

def fold(s):
    s=(s or "").lower()
    for a,b in [("ı","i"),("İ","i"),("i̇","i"),("ş","s"),("ğ","g"),("ç","c"),("ö","o"),("ü","u"),("'",""),("-"," ")]:
        s=s.replace(a,b)
    return " ".join(s.split())

recs=[]
for cj in sorted(OUT.glob("*/*/compare.json")):
    try: recs.append(json.loads(cj.read_text(encoding="utf-8")))
    except Exception: pass

L=[]
def p(s=""): L.append(s); print(s)

p(f"# 3-WAY OKUYUCU KARŞILAŞTIRMA RAPORU")
p(f"_Tamamlanan master: {len(recs)}_  (OneOCR / Paddle / qwen — ayrı ayrı + KB desteği)")
p("")
p("## 1) Sayı tablosu")
p("")
p("| film / seg | satır 1OCR | Paddle | qwen | TR-diac 1OCR | Padl | qwn | süre 1OCR | Padl | qwen | KB→1OCR | Padl |")
p("|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|")
def g(r,k,d=0): return r.get(k,d) if r.get(k,d) is not None else d
for r in recs:
    kb=r.get("kb",{})
    p(f"| {r['label']}/{r['seg']} | {g(r,'oneocr_n')} | {g(r,'paddle_n')} | {g(r,'qwen_n')} "
      f"| {g(r,'oneocr_tr')} | {g(r,'paddle_tr')} | {g(r,'qwen_tr')} "
      f"| {g(r,'oneocr_t')}s | {g(r,'paddle_t')}s | {g(r,'qwen_t')}s "
      f"| {kb.get('oneocr',{}).get('changed',0)} | {kb.get('paddle',{}).get('changed',0)} |")

def S(k): return sum(g(r,k) for r in recs)
p("")
p("## 2) Genel toplam")
p("")
p("| | OneOCR | Paddle | qwen |")
p("|---|--:|--:|--:|")
p(f"| toplam satır | {S('oneocr_n')} | {S('paddle_n')} | {S('qwen_n')} |")
p(f"| **TR-diakritik satır (ş/ğ/ı/İ)** | **{S('oneocr_tr')}** | **{S('paddle_tr')}** | **{S('qwen_tr')}** |")
p(f"| toplam süre (s) | {round(S('oneocr_t'),1)} | {round(S('paddle_t'),1)} | {round(S('qwen_t'),1)} |")
p(f"| KB-düzeltti satır | {sum(r.get('kb',{}).get('oneocr',{}).get('changed',0) for r in recs)} "
  f"| {sum(r.get('kb',{}).get('paddle',{}).get('changed',0) for r in recs)} "
  f"| {sum(r.get('kb',{}).get('qwen',{}).get('changed',0) for r in recs)} |")
nm=max(len(recs),1)
p(f"| ort. süre/master (s) | {round(S('oneocr_t')/nm,1)} | {round(S('paddle_t')/nm,1)} | {round(S('qwen_t')/nm,1)} |")

# 3) ikili örtüşme toplamı
p("")
p("## 3) Okuyucular ne kadar örtüşüyor (fold)")
p("")
def OS(k): return sum(r.get("overlap",{}).get(k,0) for r in recs)
p("| 1OCR∩Padl | 1OCR∩qwen | Padl∩qwen | 3'ü-ortak | yalnız-1OCR | yalnız-Padl | yalnız-qwen |")
p("|--:|--:|--:|--:|--:|--:|--:|")
p(f"| {OS('oneocr_paddle')} | {OS('oneocr_qwen')} | {OS('paddle_qwen')} | {OS('all3')} | {OS('oneocr_only')} | {OS('paddle_only')} | {OS('qwen_only')} |")

# 4) somut yan-yana örnek (en zengin cikis segmentini seç)
def seg_lines(label,seg,fn):
    f=OUT/label/seg/fn
    return f.read_text(encoding="utf-8").splitlines() if f.exists() else []

# örnek için: qwen_n en yüksek olan cikis
cand=[r for r in recs if r['seg']=='cikis' and g(r,'oneocr_n')>20]
if cand:
    ex=max(cand,key=lambda r:g(r,'oneocr_n'))
    lbl,sg=ex['label'],ex['seg']
    one=seg_lines(lbl,sg,"oneocr.txt"); pad=seg_lines(lbl,sg,"paddle.txt"); qwn=seg_lines(lbl,sg,"qwen.txt")
    padf={fold(x):x for x in pad}; qwnf={fold(x):x for x in qwn}
    p("")
    p(f"## 4) Somut yan-yana — {lbl}/{sg} (OneOCR'ın ilk 24 satırı; karşıtlarını fold ile eşledim)")
    p("")
    p("| # | OneOCR | Paddle (aynı satır) | qwen (aynı satır) |")
    p("|--:|---|---|---|")
    for i,t in enumerate(one[:24],1):
        fk=fold(t)
        pv=padf.get(fk,"—"); qv=qwnf.get(fk,"—")
        # kaçırma vurgusu
        p(f"| {i} | {t} | {pv} | {qv} |")

(OUT/"_RAPOR.md").write_text("\n".join(L),encoding="utf-8")
print(f"\n-> {OUT/'_RAPOR.md'}")
