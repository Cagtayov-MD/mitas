#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
gece_monitor.py — gece koşusunu İZLE (queue.json + system_events oku; auth gerekmez) + periyodik QC.

Çağatay'ın isteği: "çıktı üretti değil — isim doğru mu, her şey doğru mu, gerçekten çalıştı mı."
İlerlemeyi loglar, biten filmleri deterministik QC eder, takılma/bitiş tespit eder, bitince çıkar
(çıkış = ben bilgilendirilir → final görsel-QC + rapor).
"""
import json, os, subprocess, sys, time
from collections import Counter

sys.stdout.reconfigure(encoding="utf-8")
# Linux geçişi 2026-07-17: env-aware kök + MITAS_PDF_PYTHON (mitas.env) — Windows sabitleri kaldırıldı.
ROOT = os.environ.get("MITAS_PROJECT_ROOT") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QJ = os.path.join(ROOT, "outputs", "flow_queue", "queue.json")
EV = os.path.join(ROOT, "outputs", "system_events.jsonl")
LOG = os.path.join(ROOT, "outputs", "gece_monitor.log")
PY_PDF = os.environ.get("MITAS_PDF_PYTHON") or sys.executable
GECE_QC = os.path.join(ROOT, "scripts", "gece_qc.py")

def log(m):
    s = f'[{time.strftime("%H:%M:%S")}] {m}'
    print(s, flush=True)
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(s + "\n")
    except Exception:
        pass

def counts():
    try:
        its = json.load(open(QJ, encoding="utf-8")).get("items", [])
        return dict(Counter(i.get("status") for i in its)), len(its)
    except Exception:
        return {}, 0

def ev_count():
    try:
        with open(EV, encoding="utf-8") as f:
            return sum(1 for _ in f)
    except Exception:
        return 0

def main():
    log("=== GECE MONITOR başladı ===")
    last_ev = ev_count()
    last_change = time.time()
    last_qc = 0.0
    t0 = time.time()
    while True:
        time.sleep(120)
        c, tot = counts()
        ec = ev_count()
        done = c.get("done", 0) + c.get("partial", 0)
        fail = c.get("failed", 0)
        wait = c.get("waiting", 0)
        run = c.get("running", 0)
        if ec != last_ev:
            last_ev = ec
            last_change = time.time()
        idle = round((time.time() - last_change) / 60, 1)
        log(f"done={done} fail={fail} wait={wait} run={run} / {tot} | idle={idle}dk | sure={round((time.time()-t0)/60)}dk")
        # periyodik deterministik QC (GPU yok — koşuyla çakışmaz)
        if time.time() - last_qc > 1800:
            last_qc = time.time()
            try:
                subprocess.run([PY_PDF, GECE_QC, "--since", "2026-06-05"], timeout=900, capture_output=True)
                log("  ara-QC çalıştı → outputs/gece_rapor.md")
            except Exception as e:
                log(f"  ara-QC hata: {type(e).__name__}")
        if tot > 0 and wait == 0 and run == 0:
            log(f"=== KOŞU BİTTİ: done={done} fail={fail} / {tot} ===")
            break
        if idle > 45:
            log(f"=== {idle}dk yeni olay yok — bitti/takıldı varsayıp çıkılıyor ===")
            break
        if time.time() - t0 > 9 * 3600:
            log("=== 9 saat doldu — çıkılıyor ===")
            break
    log("=== MONITOR bitti ===")

if __name__ == "__main__":
    main()
