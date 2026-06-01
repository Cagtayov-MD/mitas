"""15-FİLM (29 master) TAM ŞAMPİYONA — 5 model, model-dışta/master-içte (her model 1 kez yüklenir).
Modeller: qwen2.5vl:7b, gemma4:26b, qwen3.6:35b-a3b (std prompt) + deepseek-ocr (Free OCR.) + glm-ocr (OCR).
OneOCR/Paddle baseline = tester_3way kayıtlı txt'lerden (tekrar koşulmaz). Incremental _PROGRESS.json.
Çıktı: tester_shootout15/<model>/<film>_<seg>.txt + _PROGRESS.json + _TABLO15.md
"""
import sys, json, time, base64, urllib.request, importlib.util
from pathlib import Path
import numpy as np, cv2
sys.stdout.reconfigure(encoding="utf-8")
spec=importlib.util.spec_from_file_location("rw", r"E:\MITAS\OCR-worktree\py\20260531_2330_read_3way.py")
rw=importlib.util.module_from_spec(spec); sys.modules["rw"]=rw; spec.loader.exec_module(rw)
fp=rw.fp; fold=rw.fold; OLLAMA=rw.OLLAMA
TESTER_IN=rw.TESTER_IN; TESTER_3WAY=Path(r"E:\MITAS\OCR-worktree\tester_3way")
OUT=Path(r"E:\MITAS\OCR-worktree\tester_shootout15"); OUT.mkdir(parents=True, exist_ok=True)

QTILE, QOV, TIMEOUT = 1200, 100, 300
TR_MARK=set("şŞğĞıİ")
def tr_count(L): return sum(1 for t in L if any(c in TR_MARK for c in t))

STD=("Transcribe the film-credit text in this image EXACTLY, top to bottom, one entry per line. "
     "Use '?' for unreadable characters. Do NOT guess, do NOT add names not visible. "
     "Preserve Turkish letters: ç ğ ı İ ö ş ü. Return JSON: {\"lines\":[\"...\",\"...\"]}")

MODELS=[
    {"name":"glm-ocr:latest",   "prompt":"OCR",        "mode":"plain"},   # hızlı, baştan
    # {"name":"deepseek-ocr:3b", "prompt":"Free OCR.", "mode":"plain"},  # ÇIKARILDI: 16 dk/master, üretimde kullanılamaz
    # {"name":"gemma4:26b",      "prompt":STD,          "mode":"json"},  # ELENDİ: %69 kapsama + gerçek isim (kadro) kaçırıyor + en yavaş
    {"name":"qwen2.5vl:7b",     "prompt":STD,          "mode":"json"},
    {"name":"qwen3.6:35b-a3b",  "prompt":STD,          "mode":"json"},
]

import re
def parse_json(text):
    if not text: return []
    text=re.sub(r"<think>.*?</think>","",text,flags=re.S|re.I).strip()
    m=re.search(r"\{.*\"lines\".*\}",text,flags=re.S)
    if m:
        try:
            obj=json.loads(m.group(0))
            if isinstance(obj.get("lines"),list): return [str(x).strip() for x in obj["lines"] if str(x).strip()]
        except Exception: pass
    out=[]
    for ln in text.splitlines():
        t=ln.strip().strip("`").strip("-*•").strip()
        if not t or t in ("{","}","[","]") or t.lower().startswith(("here","sure","```","json")): continue
        if t.startswith('"') and t.endswith('",'): t=t[1:-2]
        out.append(t)
    return out
def parse_plain(text):
    if not text: return []
    text=re.sub(r"<think>.*?</think>","",text,flags=re.S|re.I)
    text=re.sub(r"<\|[^|]*\|>","",text)          # deepseek grounding etiketleri (<|ref|>,<|det|>)
    text=re.sub(r"\[\[[\d,\s]*\]\]","",text)      # koordinat blokları
    out=[]
    for ln in text.splitlines():
        t=ln.strip().strip("`").strip("#").strip("-*•").strip()
        if len(t)>=2: out.append(t)
    return out

def call(model, prompt, b64, think=False):
    pl={"model":model,"prompt":prompt,"stream":False,"think":think,"keep_alive":"40m",
        "options":{"temperature":0},"images":[b64]}
    req=urllib.request.Request(OLLAMA,json.dumps(pl).encode(),{"Content-Type":"application/json"})
    with urllib.request.urlopen(req,timeout=TIMEOUT) as r: return json.loads(r.read()).get("response","")

def read_model(spec_, img):
    H=img.shape[0]; seen={}; order=[]; step=QTILE-QOV; y=0; errs=0
    parse=parse_plain if spec_["mode"]=="plain" else parse_json
    while y<H:
        tile=img[y:min(y+QTILE,H),:]
        if tile.shape[0]<20: break
        ok,buf=cv2.imencode(".png",tile)
        if not ok: y+=step; continue
        b64=base64.b64encode(buf.tobytes()).decode()
        try:
            for t in parse(call(spec_["name"],spec_["prompt"],b64)):
                fk=fold(t)
                if fk and fk not in seen: seen[fk]=t; order.append(t)
        except Exception:
            errs+=1
        y+=step
    return order, errs

# master listesi (read_3way.FILMS)
masters=[]
for label,sub in rw.FILMS:
    d=rw.find_dir(sub)
    if not d: continue
    for seg in ("giris","cikis"):
        mp=d/seg/"master.png"
        if mp.exists(): masters.append((label,seg,mp))
print(f"=== 15-FİLM ŞAMPİYONA: {len(masters)} master × {len(MODELS)} model ===",flush=True)

prog_path=OUT/"_PROGRESS.json"
prog=json.loads(prog_path.read_text(encoding="utf-8")) if prog_path.exists() else []
done={(r["model"],r["label"],r["seg"]) for r in prog}

for spec_ in MODELS:
    mdir=OUT/spec_["name"].replace(":","_").replace("/","_"); mdir.mkdir(parents=True,exist_ok=True)
    print(f"\n##### MODEL: {spec_['name']} #####",flush=True)
    for label,seg,mp in masters:
        if (spec_["name"],label,seg) in done:
            print(f"  [{label}/{seg}] atlandı (zaten var)",flush=True); continue
        img=fp.rd(str(mp))
        t0=time.time(); lines,errs=read_model(spec_,img); dt=round(time.time()-t0,1)
        (mdir/f"{label}_{seg}.txt").write_text("\n".join(lines),encoding="utf-8")
        rec={"model":spec_["name"],"label":label,"seg":seg,"lines":len(lines),"tr":tr_count(lines),"sec":dt,"err":errs}
        prog.append(rec); prog_path.write_text(json.dumps(prog,ensure_ascii=False,indent=2),encoding="utf-8")
        print(f"  [{label}/{seg}] satır={len(lines)} TR={tr_count(lines)} {dt}s err={errs}",flush=True)

# ── AGREGAT ───────────────────────────────────────────────────────────────────
def baseline(reader, label, seg):
    f=TESTER_3WAY/label/seg/f"{reader}.txt"
    L=[x for x in f.read_text(encoding="utf-8").splitlines() if x.strip()] if f.exists() else []
    return len(L), tr_count(L)

names=[m["name"] for m in MODELS]
tot={n:{"lines":0,"tr":0,"sec":0.0,"err":0,"n":0} for n in names}
for r in prog:
    if r["model"] in tot:
        t=tot[r["model"]]; t["lines"]+=r["lines"]; t["tr"]+=r["tr"]; t["sec"]+=r["sec"]; t["err"]+=r["err"]; t["n"]+=1
# baselines
bl={"OneOCR":{"lines":0,"tr":0},"Paddle-tr":{"lines":0,"tr":0}}
for label,seg,mp in masters:
    for rd_,key in [("oneocr","OneOCR"),("paddle","Paddle-tr")]:
        n,tr=baseline(rd_,label,seg); bl[key]["lines"]+=n; bl[key]["tr"]+=tr

L=["# 15-FİLM TAM ŞAMPİYONA — AGREGAT", f"_{len(masters)} master_",""]
L.append("| okuyucu | toplam satır | TR-diakritik | toplam süre | ort/master | hata |")
L.append("|---|--:|--:|--:|--:|--:|")
L.append(f"| OneOCR (baseline) | {bl['OneOCR']['lines']} | {bl['OneOCR']['tr']} | — | — | — |")
L.append(f"| Paddle-tr (baseline) | {bl['Paddle-tr']['lines']} | {bl['Paddle-tr']['tr']} | — | — | — |")
for n in names:
    t=tot[n]; avg=round(t["sec"]/max(t["n"],1),1)
    L.append(f"| {n} | {t['lines']} | {t['tr']} | {round(t['sec'])}s | {avg}s | {t['err']} |")
(OUT/"_TABLO15.md").write_text("\n".join(L),encoding="utf-8")
print("\n"+"\n".join(L),flush=True)
print(f"\n-> {OUT/'_TABLO15.md'}",flush=True)
