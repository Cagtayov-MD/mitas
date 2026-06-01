"""deepseek-ocr + glm-ocr DOĞAL PROMPT probe — tek tile (DİRİLİŞ çıkış üstü, bilinen içerik).
Hangi prompt çalışıyor + süre + ham çıktı. format=json YOK, think=false. Tam görsel + tek tile dene.
"""
import sys, json, time, base64, urllib.request, importlib.util
import numpy as np, cv2
sys.stdout.reconfigure(encoding="utf-8")
spec=importlib.util.spec_from_file_location("fp",r"E:\MITAS\OCR-worktree\py\20260530_1744_full_pipeline.py")
fp=importlib.util.module_from_spec(spec); sys.modules["fp"]=fp; spec.loader.exec_module(fp)
OLLAMA="http://localhost:11434/api/generate"
import glob
m=[x for x in glob.glob(r"E:\MITAS\OCR-worktree\tester_fiso\*DİRİLİŞ_ERTUĞRUL\cikis\master.png") if "0010" in x][0]
img=fp.rd(m); print("master:",img.shape,flush=True)
tile=img[0:1200,:]   # üst: YAPIMCI + kadro (bilinen)

def call(model, prompt, image, timeout=300, think=False):
    ok,buf=cv2.imencode(".png",image); b64=base64.b64encode(buf.tobytes()).decode()
    pl={"model":model,"prompt":prompt,"stream":False,"think":think,"keep_alive":"10m",
        "options":{"temperature":0},"images":[b64]}
    t0=time.time()
    try:
        req=urllib.request.Request(OLLAMA,json.dumps(pl).encode(),{"Content-Type":"application/json"})
        with urllib.request.urlopen(req,timeout=timeout) as r: raw=json.loads(r.read())
        return time.time()-t0, raw.get("response","")
    except Exception as e:
        return time.time()-t0, f"[HATA] {str(e)[:90]}"

TESTS=[
    ("deepseek-ocr:3b", "Free OCR."),
    ("deepseek-ocr:3b", "<|grounding|>Convert the document to markdown."),
    ("glm-ocr:latest",  "Recognize all the text in this image, one line per entry."),
    ("glm-ocr:latest",  "OCR"),
]
for model,prompt in TESTS:
    print(f"\n===== {model}  prompt={prompt!r} =====",flush=True)
    dt,resp=call(model,prompt,tile)
    print(f"  süre={dt:.1f}s  yanıt-uzunluk={len(resp)}",flush=True)
    print("  --- ham yanıt (ilk 600) ---",flush=True)
    print("  "+resp[:600].replace("\n","\n  "),flush=True)
