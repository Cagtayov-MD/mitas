"""VLM ŞAMPİYONASI — tüm görü modelleri (+sonradan 2 model daha) okuyucu olarak yarışsın.
Aynı master'ı her modele tile-tile transkripsiyon ettirir; OneOCR + Paddle-tr baseline'ı da tabloya koyar.
Ölçü: satır / TR-diakritik(ş/ğ/ı/İ) / süre.  READ-ONLY. Fidelity prompt (uydurma yok, ? kullan).

Kullanım:
  python 20260601_vlm_shootout.py --film DIRILIS --seg cikis
  python 20260601_vlm_shootout.py --film DIRILIS --seg cikis --models "qwen3-vl:30b,minicpm-v:latest"
"""
import sys, json, time, base64, urllib.request, importlib.util, argparse
from pathlib import Path
import numpy as np, cv2
sys.stdout.reconfigure(encoding="utf-8")

# read_3way'i yeniden kullan (read_oneocr, read_paddle, fold, tr_count, find_dir, FILMS)
spec=importlib.util.spec_from_file_location("rw", r"E:\MITAS\OCR-worktree\py\20260531_2330_read_3way.py")
rw=importlib.util.module_from_spec(spec); sys.modules["rw"]=rw; spec.loader.exec_module(rw)
fold=rw.fold; OLLAMA=rw.OLLAMA

OUT=Path(r"E:\MITAS\OCR-worktree\tester_shootout")

# Test edilecek görü modelleri (Ollama'da kurulu olanlar). +2 model gelince buraya eklenecek.
DEFAULT_MODELS=[
    # — ADANMIŞ OCR modelleri (kullanıcının eklediği +2; OCR'a özel, en güçlü aday) —
    "deepseek-ocr:3b",     # DeepSeek-OCR, 3.3B F16
    "glm-ocr:latest",      # GLM-OCR, 1.1B F16
    # — genel görü-LLM'ler —
    "qwen2.5vl:7b",        # mevcut baseline (küçük)
    "qwen3-vl:30b",        # yeni nesil, büyük
    "qwen3.6:35b-a3b",     # Qwen3.5-MoE vision
    "llama3.2-vision:11b",
    "minicpm-v:latest",
    # "gemma4:26b",   # ELENDİ: gerçek isim (kadro) kaçırıyor + en yavaş
    # "gemma4:e4b",   # ELENDİ (gemma ailesi)
    "moondream:latest",
]

QWEN_TILE, QWEN_OV, TIMEOUT = 1200, 100, 300
PROMPT=("Transcribe the film-credit text in this image EXACTLY, top to bottom, one entry per line. "
        "Use '?' for unreadable characters. Do NOT guess, do NOT add names not visible. "
        "Preserve Turkish letters: ç ğ ı İ ö ş ü. Return JSON: {\"lines\":[\"...\",\"...\"]}")

import re
def extract_lines(text):
    """Model yanıtından satırları SAĞLAM çıkar: <think> temizle, varsa JSON {"lines":[...]} parse et,
    yoksa düz satırlara böl (markdown/önsöz çöpünü ele). Thinking + OCR + chat modellerin hepsiyle çalışır."""
    if not text: return []
    text=re.sub(r"<think>.*?</think>","",text,flags=re.S|re.I).strip()
    # JSON bloğu var mı?
    m=re.search(r"\{.*\"lines\".*\}",text,flags=re.S)
    if m:
        try:
            obj=json.loads(m.group(0))
            if isinstance(obj.get("lines"),list):
                return [str(x).strip() for x in obj["lines"] if str(x).strip()]
        except Exception: pass
    # düz satır fallback
    out=[]
    for ln in text.splitlines():
        t=ln.strip().strip("`").strip("-*•").strip()
        if not t or t in ("{","}","[","]") or t.lower().startswith(("here","sure","```","json")): continue
        if t.startswith('"') and t.endswith('",'): t=t[1:-2]
        out.append(t)
    return out

def read_vlm(model, img, think=False):
    H=img.shape[0]; seen={}; order=[]; step=QWEN_TILE-QWEN_OV; y=0; bi=0; errs=0
    while y<H:
        tile=img[y:min(y+QWEN_TILE,H),:]; bi+=1
        if tile.shape[0]<20: break
        ok,buf=cv2.imencode(".png",tile)
        if not ok: y+=step; continue
        b64=base64.b64encode(buf.tobytes()).decode()
        # format=json YOK (thinking modelleri boğuyordu), think=false (hız), sağlam ayrıştır
        pl={"model":model,"prompt":PROMPT,"stream":False,"think":think,"keep_alive":"10m",
            "options":{"temperature":0},"images":[b64]}
        try:
            req=urllib.request.Request(OLLAMA,json.dumps(pl).encode(),{"Content-Type":"application/json"})
            with urllib.request.urlopen(req,timeout=TIMEOUT) as r: raw=json.loads(r.read())
            for t in extract_lines(raw.get("response","")):
                fk=fold(t)
                if fk and fk not in seen: seen[fk]=t; order.append(t)
        except Exception as e:
            errs+=1
            if errs<=2: print(f"     [{model} blok{bi}] {str(e)[:70]}",flush=True)
        y+=step
    return order, errs

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--film",default="DIRILIS"); ap.add_argument("--seg",default="cikis")
    ap.add_argument("--models",default=None,help="virgülle ayrılmış model listesi (yoksa DEFAULT_MODELS)")
    a=ap.parse_args()
    models=[m.strip() for m in a.models.split(",")] if a.models else DEFAULT_MODELS

    # master bul (FILMS tablosundan etiketle, yoksa substring)
    sub=None
    for label,s in rw.FILMS:
        if a.film.upper() in label: sub=s; break
    d=rw.find_dir(sub) if sub else rw.find_dir(a.film)
    if d is None: print("film bulunamadı:",a.film); return
    mp=d/a.seg/"master.png"
    if not mp.exists(): print("master yok:",mp); return
    img=rw.fp.rd(str(mp)); H,W=img.shape[:2]
    print(f"=== ŞAMPİYONA — {a.film}/{a.seg}  ({W}x{H})  master={mp.name} ===",flush=True)
    od=OUT/f"{a.film}_{a.seg}"; od.mkdir(parents=True,exist_ok=True)

    rows=[]
    # baseline: OneOCR + Paddle-tr
    t0=time.time(); one=rw.read_oneocr(img); dt=time.time()-t0
    rows.append(("OneOCR",len(one),rw.tr_count(one),round(dt,1),0)); (od/"OneOCR.txt").write_text("\n".join(one),encoding="utf-8")
    print(f"  OneOCR: {len(one)} satır, TR={rw.tr_count(one)}, {dt:.1f}s",flush=True)
    t0=time.time(); pad=rw.read_paddle(str(mp)); dt=time.time()-t0
    rows.append(("Paddle-tr",len(pad),rw.tr_count(pad),round(dt,1),0)); (od/"Paddle-tr.txt").write_text("\n".join(pad),encoding="utf-8")
    print(f"  Paddle-tr: {len(pad)} satır, TR={rw.tr_count(pad)}, {dt:.1f}s",flush=True)

    # VLM'ler
    for model in models:
        print(f"  [{model}] okuyor...",flush=True)
        t0=time.time(); lines,errs=read_vlm(model,img); dt=time.time()-t0
        rows.append((model,len(lines),rw.tr_count(lines),round(dt,1),errs))
        safe=model.replace(":","_").replace("/","_"); (od/f"{safe}.txt").write_text("\n".join(lines),encoding="utf-8")
        print(f"     -> {len(lines)} satır, TR-diac={rw.tr_count(lines)}, {dt:.1f}s, hata={errs}",flush=True)

    # tablo
    rows.sort(key=lambda r:-r[1])
    L=[f"# VLM ŞAMPİYONASI — {a.film}/{a.seg}  ({W}x{H})","",
       "| okuyucu | satır | TR-diac(ş/ğ/ı/İ) | süre(s) | hata |","|---|--:|--:|--:|--:|"]
    for name,n,tr,dt,errs in rows: L.append(f"| {name} | {n} | {tr} | {dt} | {errs} |")
    txt="\n".join(L); print("\n"+txt,flush=True)
    (od/"_TABLO.md").write_text(txt,encoding="utf-8")
    json.dump([{"reader":n,"lines":ln,"tr":tr,"sec":dt,"err":e} for n,ln,tr,dt,e in rows],
              open(od/"_TABLO.json","w",encoding="utf-8"),ensure_ascii=False,indent=2)
    print(f"\n-> {od/'_TABLO.md'}",flush=True)

if __name__=="__main__": main()
