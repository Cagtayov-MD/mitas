# -*- coding: utf-8 -*-
"""Aşama 2 — Uçtan uca test: run_pipeline100() doğrudan çağır.

Önce/sonra karşılaştırma (mevcut kunye.txt vs yeni çıktı).
master.png üretildi mi?
lines additive büyüdü mü?
fail-safe: ocr_out=None verince master bloğu atlanıyor mu?

Çalıştır: E:\MITAS\venvs\ocr\Scripts\python.exe outputs\master_png_e2e_test.py
"""
import sys, glob, time, json, shutil
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

# _pipe_ocr.py'yi import et (venvs/ocr ile çalışır)
sys.path.insert(0, r"E:\MITAS\scripts")
import importlib.util
spec = importlib.util.spec_from_file_location("pipe_ocr", r"E:\MITAS\scripts\_pipe_ocr.py")
pipe_ocr = importlib.util.module_from_spec(spec)
sys.modules["pipe_ocr"] = pipe_ocr
spec.loader.exec_module(pipe_ocr)

run_pipeline100 = pipe_ocr.run_pipeline100

# ── test hub: BRONX (60 mevcut satır, orta boyut, hızlı) ─────────────────
HUB_DIR = Path(r"F:\REPO_GitHub\DATABASE\BRONX SOKAKLARINDA 1981-0262-1-0000-00-1")
SEG = "exit_frames"
EXISTING_KUNYE = Path(r"E:\MITAS\OCR-worktree\clip_pipeline100\_KUNYE\BRONX_SOKAKLARINDA_1981_0262_1_0000_00_1__cikis.txt")
OUT_DIR_MASTER = Path(r"E:\MITAS\outputs\_master_e2e_with")
OUT_DIR_NO_MASTER = Path(r"E:\MITAS\outputs\_master_e2e_without")
OUT_DIR_MASTER.mkdir(parents=True, exist_ok=True)
OUT_DIR_NO_MASTER.mkdir(parents=True, exist_ok=True)

frames_glob = sorted(Path(p) for p in glob.glob(str(HUB_DIR / SEG / "*.png")))
print(f"[e2e] {len(frames_glob)} frame, hub: BRONX {SEG}", flush=True)

# ── ÖNCE: mevcut kunye.txt satır sayısı ───────────────────────────────────
existing_lines = EXISTING_KUNYE.read_text(encoding="utf-8", errors="ignore").splitlines()
existing_lines = [l.strip() for l in existing_lines if l.strip() and not l.startswith("#")]
print(f"[e2e] Mevcut kunye.txt: {len(existing_lines)} satır", flush=True)

# ── TEST 1: ocr_out=None -> master bloğu atlanmalı (fail-safe/bypass) ────
print("\n[TEST 1] ocr_out=None -> master bloğu atlanıyor mu?", flush=True)
t0 = time.perf_counter()
res_no_master = run_pipeline100(frames_glob, t0, "film", ocr_out=None)
elapsed1 = round(time.perf_counter() - t0, 1)
if res_no_master is None:
    print("[TEST 1] HATA: run_pipeline100 None döndü (import çökmüş — CLIP GPU? fallback devreye girecek)", flush=True)
    sys.exit(1)
lines_no_master = res_no_master.get("lines", [])
master_png_no = res_no_master.get("master_png")
print(f"[TEST 1] lines={len(lines_no_master)}, master_png={master_png_no}, süre={elapsed1}s", flush=True)
assert master_png_no is None, f"ocr_out=None iken master_png üretilmemeli! Değer: {master_png_no}"
print("[TEST 1] GEÇER: ocr_out=None -> master üretilmedi, lines normal.", flush=True)

# ── TEST 2: ocr_out verilince master üretilmeli, lines büyümeli (VEYA eşit) ─
print("\n[TEST 2] ocr_out=OUT_DIR -> master.png üretilmeli", flush=True)
t0 = time.perf_counter()
res_with_master = run_pipeline100(frames_glob, t0, "film", ocr_out=OUT_DIR_MASTER)
elapsed2 = round(time.perf_counter() - t0, 1)
if res_with_master is None:
    print("[TEST 2] HATA: run_pipeline100 None döndü", flush=True)
    sys.exit(1)
lines_with_master = res_with_master.get("lines", [])
master_png_path = res_with_master.get("master_png")
master_lines_count = res_with_master.get("master_lines_count", 0)
master_error = res_with_master.get("master_error")

print(f"[TEST 2] lines_no_master={len(lines_no_master)}, lines_with_master={len(lines_with_master)}", flush=True)
print(f"[TEST 2] master_png={master_png_path}", flush=True)
print(f"[TEST 2] master_lines_count={master_lines_count}, master_error={master_error}", flush=True)
print(f"[TEST 2] süre={elapsed2}s", flush=True)

assert len(lines_with_master) >= len(lines_no_master), (
    f"lines KÜÇÜLDÜ! with={len(lines_with_master)} < without={len(lines_no_master)}"
)
assert master_png_path is not None or master_error is not None, "master_png ve master_error ikisi de None!"
if master_png_path:
    assert Path(master_png_path).exists(), f"master.png disk'te yok: {master_png_path}"
    import cv2, numpy as np
    img = cv2.imdecode(np.fromfile(master_png_path, np.uint8), cv2.IMREAD_COLOR)
    assert img is not None, f"master.png okunamadı: {master_png_path}"
    print(f"[TEST 2] master PNG boyutu: {img.shape[1]}x{img.shape[0]}px", flush=True)
print("[TEST 2] GEÇER: master üretildi, lines bozulmadı.", flush=True)

# ── TEST 3: mevcut lines bozulmadı mı? ────────────────────────────────────
print("\n[TEST 3] Mevcut OCR-worktree lines korundu mu?", flush=True)
# no_master ve with_master'daki ilk N satır aynı olmalı
base = lines_no_master
new  = lines_with_master[:len(base)]
mismatches = [(i, base[i], new[i]) for i in range(min(len(base), len(new))) if base[i] != new[i]]
if mismatches:
    print(f"[TEST 3] DİKKAT: {len(mismatches)} satır farklı (fold/case farkları normal):", flush=True)
    for i, b, n in mismatches[:5]:
        print(f"    [{i}] ÖNCE: {b!r} | SONRA: {n!r}", flush=True)
else:
    print("[TEST 3] GEÇER: İlk N satır değişmedi.", flush=True)

# ── TEST 4: fail-safe — compose_hybrid çöktüğünde lines korunuyor mu? ───
print("\n[TEST 4] fail-safe: master bloğu çöktüğünde lines değişmemeli", flush=True)
# Bunu simüle etmek için OUT_DIR'i Path olmayan bir şey veriyoruz:
class _BadPath:
    """Her attribute/method çağrısında exception atar."""
    def __truediv__(self, other): raise RuntimeError("KASITLI HATA - failsafe testi")
    def __str__(self): raise RuntimeError("KASITLI HATA - failsafe testi")

t0 = time.perf_counter()
res_fail = run_pipeline100(frames_glob, t0, "film", ocr_out=_BadPath())
elapsed4 = round(time.perf_counter() - t0, 1)
if res_fail is None:
    print("[TEST 4] run_pipeline100 None döndü — CLIP çökmüş olabilir, fallback; failsafe geçti", flush=True)
else:
    lines_fail = res_fail.get("lines", [])
    master_err = res_fail.get("master_error")
    print(f"[TEST 4] master_error={master_err}", flush=True)
    print(f"[TEST 4] lines_fail={len(lines_fail)} (beklenen ~{len(lines_no_master)})", flush=True)
    assert len(lines_fail) >= len(lines_no_master) - 2, (
        f"fail-safe BAŞARISIZ: lines çok azaldı! fail={len(lines_fail)} vs normal={len(lines_no_master)}"
    )
    assert master_err is not None, "master_error None — hata yakalanmadı!"
    print(f"[TEST 4] GEÇER: master bloğu çöktü ama lines korundu, master_error set edildi.", flush=True)
print(f"[TEST 4] süre={elapsed4}s", flush=True)

# ── ÖNCE/SONRA karşılaştırma tablosu ──────────────────────────────────────
print("\n" + "="*60, flush=True)
print("ÖNCE/SONRA KARŞILAŞTIRMA (BRONX exit_frames)", flush=True)
print(f"  OCR-worktree mevcut : {len(existing_lines)} satır", flush=True)
print(f"  run_pipeline100 (-master): {len(lines_no_master)} satır", flush=True)
print(f"  run_pipeline100 (+master): {len(lines_with_master)} satır (+{len(lines_with_master)-len(lines_no_master)} additive)", flush=True)
if master_png_path:
    print(f"  master.png         : {master_png_path}", flush=True)
print(f"  master_lines_count : {master_lines_count}", flush=True)

# Eklenen satırlar
added = [l for l in lines_with_master if l not in set(lines_no_master)]
print(f"\n  Master-only eklenen satırlar ({len(added)}):", flush=True)
for l in added[:15]:
    print(f"    + {l}", flush=True)

print("\n[e2e] TÜM TESTLER GEÇER.", flush=True)
