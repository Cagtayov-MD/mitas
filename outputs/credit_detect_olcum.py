# -*- coding: utf-8 -*-
"""8 yabanci filmde MITAS_CREDIT_DETECT (OpusCreditDetector) olcumu.
Detector'i her filmde calistir, bulundugu GIRIS/CIKIS penceresini SABIT pencereyle (head=180s, tail=240s) kiyasla.
SABIT pencere kredileri kacirdi mi? -> opening.end_sec>180 veya closing.start_sec < dur-240 ise EVET."""
import subprocess, json, os, sys, time
sys.stdout.reconfigure(encoding="utf-8")
PY = r"E:\MITAS\venvs\ocr\Scripts\python.exe"
DET = r"E:\MITAS\scripts\_credit_detect.py"
VID = r"W:\23.05 öncesi FİLMLER\104"
HEAD, TAIL = 180.0, 240.0
FILMS = [
 ("ANNEM",               "evoArcadmin_ÇÖZÜMLEME11_2015-1082-1-0000-50-1-ANNEM.mp4"),
 ("KARAYİP 2",           "evoArcadmin_ÇÖZÜMLEME11_2015-1088-1-0000-90-1-KARAYİP_KORSANLARI-2-ÖLÜ_ADAMIN_SANDIĞI.mp4"),
 ("AKIL OYUNLARI",       "evoArcadmin_ÇÖZÜMLEME11_2017-1043-1-0000-90-1-AKIL_OYUNLARI.mp4"),
 ("MUTLU LAZZARO",       "evoArcadmin_ÇÖZÜMLEME11_2018-1133-1-0000-71-0-MUTLU_LAZZARO.mp4"),
 ("GÖREVİMİZ TEHLİKE 6", "evoArcadmin_ÇÖZÜMLEME11_2018-1199-1-0000-90-1-GÖREVİMİZ_TEHLİKE_6_YANSIMALAR.mp4"),
 ("6,5 METRE",           "evoArcadmin_ÇÖZÜMLEME11_2019-1039-1-0000-56-1-6,5_METRE.mp4"),
 ("ARAMIZDAKİ SÖZLER",   "evoArcadmin_ÇÖZÜMLEME11_2022-1137-1-0000-90-1-ARAMIZDAKİ_SÖZLER.mp4"),
 ("SEKİZ DAĞ",           "evoArcadmin_ÇÖZÜMLEME11_2022-1192-1-0000-71-0-SEKİZ_DAĞ.mp4"),
]

def dur_of(path):
    try:
        import cv2
        c = cv2.VideoCapture(path); f = c.get(cv2.CAP_PROP_FPS) or 25; n = c.get(cv2.CAP_PROP_FRAME_COUNT) or 0
        c.release(); return float(n)/max(f,1)
    except Exception:
        return 0.0

results = []
for name, fn in FILMS:
    path = os.path.join(VID, fn)
    rec = {"film": name, "exists": os.path.exists(path)}
    if not rec["exists"]:
        results.append(rec); print(name, "VIDEO YOK", flush=True); continue
    dur = dur_of(path); rec["dur_sec"] = round(dur, 1)
    t0 = time.time()
    try:
        r = subprocess.run([PY, DET, "--video", path], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=900)
        j = None
        for ln in reversed((r.stdout or "").splitlines()):
            ln = ln.strip()
            if ln.startswith("{"):
                try: j = json.loads(ln); break
                except Exception: pass
        rec["detect"] = j
        rec["stderr_tail"] = (r.stderr or "")[-400:]
    except Exception as e:
        rec["error"] = f"{type(e).__name__}: {e}"
    rec["sure_sn"] = round(time.time() - t0, 1)
    # SABIT pencere kacirma analizi
    if rec.get("detect"):
        op = rec["detect"].get("opening") or {}; cl = rec["detect"].get("closing") or {}
        rec["sabit_giris_kacirdi"] = bool(op.get("found") and (op.get("end_sec") or 0) > HEAD)
        rec["sabit_cikis_kacirdi"] = bool(cl.get("found") and dur and (cl.get("start_sec") or 0) < (dur - TAIL))
    results.append(rec)
    print(name, "BİTTİ", rec.get("sure_sn"), "sn", flush=True)
    json.dump(results, open(r"E:\MITAS\outputs\credit_detect_olcum.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)

print("\n===== ÖZET TABLO =====", flush=True)
print(f"{'FİLM':<22}{'SÜRE':>7} | {'GİRİŞ tespit':<26}{'conf':>6} | {'ÇIKIŞ tespit':<26}{'conf':>6} | sabit-kaçırdı")
for x in results:
    d = x.get("detect") or {}; op = d.get("opening") or {}; cl = d.get("closing") or {}
    dur = x.get("dur_sec") or 0
    gi = f"{op.get('start_sec')}-{op.get('end_sec')}s {op.get('type')}" if op.get("found") else "BULUNAMADI"
    ci = f"{cl.get('start_sec')}-{cl.get('end_sec')}s {cl.get('type')}" if cl.get("found") else "BULUNAMADI"
    kac = []
    if x.get("sabit_giris_kacirdi"): kac.append("GİRİŞ")
    if x.get("sabit_cikis_kacirdi"): kac.append("ÇIKIŞ")
    print(f"{x['film']:<22}{dur:>6.0f}s | {gi:<26}{op.get('confidence','-'):>6} | {ci:<26}{cl.get('confidence','-'):>6} | {','.join(kac) or '-'}")
print("\nJSON: E:\\MITAS\\outputs\\credit_detect_olcum.json")
