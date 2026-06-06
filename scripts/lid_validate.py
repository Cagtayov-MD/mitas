#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""lid_validate.py - MMS-LID kanal-dil tespiti (_channel_lang) dogrulama harness'i.

GUNCEL mimari: _channel_lang.detect(video, stream, channel) -> MMS-LID (facebook/mms-lid-1024).
Whisper YOK - eski large-v3 LID Kurtce/Azerice'yi fa/tr saniyordu; MMS gocu commit c5017efc4c.
Production cagrisi birebir: scripts/_pipe_asr.py:65  ->  cl.detect(str(lid_src), s, c)

Her ANCHOR film icin stream 0'in tum kanallarini tespit eder, select_summary ile ozet kanalini
secer, secilen dili BEKLENEN ile karsilastirir -> PASS / FAIL / WARN / SKIP(kaynak yok).
Kaynak yoksa SESSIZCE GECMEZ - SKIP isaretler (bayat-artefakt tuzagina dusmemek icin).
Cikti: outputs/lid_validate_report.json + ekran tablosu. Exit = FAIL sayisi.

Kos:  venvs\\asr\\Scripts\\python.exe scripts\\lid_validate.py
"""
import sys, os, glob, json
from pathlib import Path

sys.path.insert(0, r"E:\MITAS\scripts")
sys.stdout.reconfigure(encoding="utf-8")
import _channel_lang as cl

# Kisa klipler (WIKITONGUES, *_son4dk) production'in 130s+ ornek programini asar ->
# erken noktalar ekle ki en az 2 ornek dussun (yalniz HARNESS; production SAMPLES'a dokunmaz).
cl.SAMPLES = [20, 60, 130, 300, 480, 700, 950]
cl.EXTRA_SAMPLES = [40, 90, 190, 360, 540]

DB_ROOTS = [r"E:\MITAS\Database", r"F:\REPO_GitHub\DATABASE"]
OUT = Path(r"E:\MITAS\outputs\lid_validate_report.json")
VIDEO_EXT = (".mp4", ".mkv", ".avi", ".mov", ".ts", ".m4v", ".mpg", ".wmv")

# (beklenen_dil, etiket, glob_deseni, not). "yabanci" diller (ku/ar) icin tr'ye dusmek HARD-FAIL.
# "SILENT" = ses yok -> got None bekle (filmler-arasi kontaminasyon guard'i: onceki dil sizmamali).
ANCHORS = [
    ("az",     "WIKITONGUES Galib - Azerice konusma", "*Galib*Azerbaijani*", "net az konusma ornegi"),
    ("tr",     "Onlar hem hekim hem anne - Turkce",   "*Onlar_hem_hekim*",   "tr regresyon kontrolu"),
    ("tr",     "CANLI SERUVEN - Turkce",              "*CANLI_SERUVEN*",     "tr ikinci ornek"),
    ("SILENT", "AHLAT son4dk jenerik klibi (video-only)", "*AHLAT_AGACI_son4dk*", "no-audio guard: sesi soyulmus klip->null; AHLAT FILMI sessiz DEGIL, bu klip ses soyulmus"),
    ("ku",     "ALTIN YUMRUK - Kurtce",               "*ALTIN_YUMRUK*",      "ku: whisper ceviremez->ASR atla; tr DEGIL"),
    ("ar",     "DERT BENDE - Arapca dublaj",          "*1973-0174*DERT*",    "ar; yabanci, tr DEGIL"),
]
FOREIGN = {"ku", "ar"}   # bunlar icin: got==beklenen=PASS, got=tr=HARD-FAIL, got=None/diger-yabanci=WARN


def find_source(pat):
    """DB koklerinde deseni ara; gercek source'u dondur (.mitas_playback. preview'i atla)."""
    for root in DB_ROOTS:
        for inner in (os.path.join(pat, "source", "*.*"), os.path.join(pat, "*.*")):
            for h in sorted(glob.glob(os.path.join(root, inner))):
                low = h.lower()
                if low.endswith(VIDEO_EXT) and ".mitas_playback." not in low:
                    return h
    return None


def classify(expected, got):
    if expected == "SILENT":
        return "PASS" if got is None else "FAIL"   # ses yok -> dil SIZMAMALI (kontaminasyon guard)
    if got == expected:
        return "PASS"
    if expected in FOREIGN:
        if got == "tr":
            return "FAIL"          # en tehlikeli: yabanciyi tr sanmak
        return "WARN"              # yabanci ama tam degil / null -> kabul edilebilir (tr DEGIL)
    return "FAIL"                  # tr/az beklenen, tutmadi


def main():
    rows, fails = [], 0
    print("[MMS-LID dogrulama] motor=_channel_lang (facebook/mms-lid-1024)\n", flush=True)
    for expected, label, pat, note in ANCHORS:
        video = find_source(pat)
        if not video:
            rows.append({"label": label, "expected": expected, "status": "SKIP",
                         "got": None, "reason": "kaynak yok", "note": note, "pattern": pat})
            print(f"  SKIP -  {label}\n          beklenen={expected}  kaynak yok ({pat})\n", flush=True)
            continue
        streams = cl.audio_streams(video)
        nch = streams[0] if streams else 1
        units = [cl.detect(video, 0, c) for c in range(nch)]   # stream 0 (cok-stream dupe)
        sel, reason = cl.select_summary(units)
        got = sel.get("language")
        status = classify(expected, got)
        if status == "FAIL":
            fails += 1
        conf = sel.get("confidence")
        rows.append({"label": label, "expected": expected, "got": got, "status": status,
                     "confidence": conf, "select_reason": reason, "note": note,
                     "source": os.path.basename(video),
                     "channels": [{"c": u["channel"], "lang": u["language"], "conf": u["confidence"],
                                   "role": u["role"], "votes": u.get("votes")} for u in units]})
        mark = {"PASS": "PASS ✓", "FAIL": "FAIL ✗", "WARN": "WARN ?", "SKIP": "SKIP -"}[status]
        print(f"  {mark}  {label}", flush=True)
        print(f"          beklenen={expected}  secilen={got}  conf={conf}  | {reason}", flush=True)
        for u in units:
            print(f"          c{u['channel']}: {str(u['language']):4} conf {u['confidence']:.2f} "
                  f"{u['role']:13} votes={u.get('votes')}", flush=True)
        print(flush=True)
    summary = {
        "engine": "facebook/mms-lid-1024 (_channel_lang.detect)",
        "n_anchors": len(ANCHORS),
        "passed": sum(1 for r in rows if r["status"] == "PASS"),
        "failed": fails,
        "warned": sum(1 for r in rows if r["status"] == "WARN"),
        "skipped": sum(1 for r in rows if r["status"] == "SKIP"),
        "rows": rows,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"OZET: {summary['passed']} PASS / {summary['failed']} FAIL / "
          f"{summary['warned']} WARN / {summary['skipped']} SKIP  -> {OUT}", flush=True)
    print("LID_VALIDATE_DONE", flush=True)
    sys.exit(fails)


if __name__ == "__main__":
    main()
