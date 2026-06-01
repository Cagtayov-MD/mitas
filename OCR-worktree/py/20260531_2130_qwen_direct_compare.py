"""20260531_2130 — qwen-DİREKT (tam) vs Paddle+KB head-to-head. DİRİLİŞ.
qwen master'ı tile-tile transkripsiyon eder (anti-halüsinasyon). Paddle transcript ile kıyas.
Çıktı: qwen_transcript.txt + compare raporu. READ-ONLY (KB yok).
"""
import sys, json, base64, glob, urllib.request, importlib.util
from pathlib import Path
import cv2, numpy as np
sys.stdout.reconfigure(encoding="utf-8")
spec=importlib.util.spec_from_file_location("fp",r"E:\MITAS\OCR-worktree\py\20260530_1744_full_pipeline.py"); fp=importlib.util.module_from_spec(spec); sys.modules["fp"]=fp; spec.loader.exec_module(fp)

TILE_H=1200; OVERLAP=100; TIMEOUT=180
PROMPT=("Transcribe the film-credit text in this image EXACTLY, top to bottom, one entry per line. "
        "Use '?' for unreadable characters. Do NOT guess, do NOT add names not visible. "
        "Preserve Turkish letters: ç ğ ı İ ö ş ü. Return JSON: {\"lines\":[\"...\",\"...\"]}")

def fold(s):
    s=(s or "").lower()
    for a,b in [("ı","i"),("İ","i"),("i̇","i"),("ş","s"),("ğ","g"),("ç","c"),("ö","o"),("ü","u"),("'",""),("-"," ")]:
        s=s.replace(a,b)
    return " ".join(s.split())

def qwen_read_tile(tile):
    ok,buf=cv2.imencode(".png",tile)
    if not ok: return []
    b64=base64.b64encode(buf.tobytes()).decode()
    pl={"model":fp.MODEL,"prompt":PROMPT,"stream":False,"format":"json","keep_alive":"15m","options":{"temperature":0},"images":[b64]}
    try:
        req=urllib.request.Request(fp.OLLAMA,json.dumps(pl).encode(),{"Content-Type":"application/json"})
        with urllib.request.urlopen(req,timeout=TIMEOUT) as r: raw=json.loads(r.read())
        resp=raw.get("response","{}"); resp=json.loads(resp) if isinstance(resp,str) else resp
        ls=resp.get("lines",[])
        return [x.strip() for x in ls if isinstance(x,str) and x.strip()]
    except Exception as e:
        print("   [qwen tile hata]",str(e)[:60]); return []

def qwen_master(path):
    img=fp.rd(path); H,W=img.shape[:2]; seen={}; order=[]
    y=0; step=TILE_H-OVERLAP; bi=0
    while y<H:
        tile=img[y:min(y+TILE_H,H),:]; bi+=1
        print(f"   qwen blok {bi} (y={y})...",flush=True)
        for ln in qwen_read_tile(tile):
            fk=fold(ln)
            if fk and fk not in seen: seen[fk]=ln; order.append(ln)
        y+=step
    return order

def main():
    import argparse; ap=argparse.ArgumentParser(); ap.add_argument("--film",default="DİRİLİŞ"); ap.add_argument("--seg",default="cikis"); a=ap.parse_args()
    fd=glob.glob(rf"E:\MITAS\OCR-worktree\tester_fiso\*{a.film}*")
    mp=Path(fd[0])/a.seg/"master.png"; print("master:",mp,flush=True)
    qlines=qwen_master(str(mp))
    outdir=Path(fd[0])/a.seg
    # qwen transcript yaz (tester_read'e, Paddle'ın yanına)
    rd_dir=Path(r"E:\MITAS\OCR-worktree\tester_read\DIRILIS")/a.seg; rd_dir.mkdir(parents=True,exist_ok=True)
    (rd_dir/"qwen_transcript.txt").write_text("\n".join(qlines),encoding="utf-8")
    # Paddle transcript oku
    pt=rd_dir/"transcript.txt"; plines=pt.read_text(encoding="utf-8").splitlines() if pt.exists() else []
    pf={fold(x) for x in plines}; qf={fold(x) for x in qlines}
    both=pf&qf; q_only=[x for x in qlines if fold(x) not in pf]; p_only=[x for x in plines if fold(x) not in qf]
    print("\n=== HEAD-TO-HEAD: qwen-direkt vs Paddle+KB ===")
    print(f"  Paddle satır: {len(plines)} | qwen satır: {len(qlines)} | ortak(fold): {len(both)}")
    print(f"  qwen'de VAR Paddle'da YOK: {len(q_only)} (qwen daha iyi-okuma ya da halüsinasyon)")
    print(f"  Paddle'da VAR qwen'de YOK: {len(p_only)} (qwen kaçırdı ya da Paddle fragmanı)")
    print("\n  --- qwen-only ilk 15 (gerçek isim mi, uydurma mı?) ---")
    for x in q_only[:15]: print("    +",x)
    print("\n  --- paddle-only ilk 15 (qwen mi kaçırdı, fragman mı?) ---")
    for x in p_only[:15]: print("    -",x)
    print(f"\n  qwen_transcript -> {rd_dir/'qwen_transcript.txt'}")
    json.dump({"paddle_n":len(plines),"qwen_n":len(qlines),"both":len(both),"q_only":q_only,"p_only":p_only},
              open(rd_dir/"compare.json","w",encoding="utf-8"),ensure_ascii=False,indent=2)

if __name__=="__main__": main()
