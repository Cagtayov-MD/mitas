#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""enqueue_local_films.py — YEREL film dizinini flow-queue'ya PATH ile ekle (UPLOAD YOK).

KALICI ÇÖZÜM (2026-06-08): Tarayıcı yerel dosya YOLUNU göremez (sandbox) → 329 büyük filmi
upload etmeye çalışır → kopar (ClientDisconnect) + ad kaybolur + 186 GB boşa. asr_server
worker'ı ZATEN `sourcePath` (yerel yol) destekler (asr_server.py:378). Bu betik yerel dizini
doğrudan kuyruğa `sourcePath` öğeleri olarak yazar (atomik) + worker'ı başlatır. Upload yok,
TRT-adı korunur, GPU-serial, resumable (Database'de işlenmiş atlanır), UI ilerlemeyi gösterir.

KULLANIM:  python scripts/enqueue_local_films.py --dir "E:\\path\\to\\filmler" [--profile film]
           python scripts/enqueue_local_films.py --dir ... --replace   # mevcut kuyruğu sıfırla
"""
import argparse, glob, json, os, re, sys, urllib.request
from uuid import uuid4

# Linux geçişi 2026-07-16: kök env'den (yoksa eski Windows davranışı birebir).
QUEUE = os.path.join(os.environ.get("MITAS_PROJECT_ROOT") or r"E:\MITAS",
                     "outputs", "flow_queue", "queue.json")
API = "http://127.0.0.1:8787"
EXTS = ("mp4", "mxf", "mkv", "avi", "mov", "MP4", "MXF", "MKV")

def find_films(d, only_trt=True):
    fs = []
    for e in EXTS:
        fs += glob.glob(os.path.join(d, "*." + e))
    fs = sorted(set(fs))
    if only_trt:  # TRT-id'li gerçek filmler (junk atla)
        fs = [f for f in fs if re.search(r"\d{4}-\d{3,4}-\d-\d{3,4}", os.path.basename(f))]
    return fs

def _now_iso():
    # server _now_iso ile uyumlu (UTC ISO) — ama betikte basit tut
    import datetime
    return datetime.datetime.now(datetime.timezone.utc).isoformat()

def write_atomic(path, obj):
    tmp = path + ".tmp"
    open(tmp, "w", encoding="utf-8").write(json.dumps(obj, ensure_ascii=False, indent=2) + "\n")
    os.replace(tmp, path)

def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True, help="yerel film dizini")
    ap.add_argument("--profile", default="film")
    ap.add_argument("--replace", action="store_true", help="mevcut kuyruğu SIFIRLA (yoksa EKLE)")
    ap.add_argument("--no-start", action="store_true", help="worker'ı başlatma (sadece kuyruğa yaz)")
    ap.add_argument("--all", action="store_true", help="TRT-id filtresini KAPAT (tüm videolar)")
    a = ap.parse_args()
    if not os.path.isdir(a.dir):
        print(f"HATA: dizin yok: {a.dir}"); return 2
    films = find_films(a.dir, only_trt=not a.all)
    if not films:
        print(f"HATA: {a.dir} içinde film bulunamadı (TRT-id'li). --all ile tümünü dene."); return 2

    # mevcut kuyruk (EKLE modu) ya da sıfır (replace)
    state = {"id": "main", "updatedAt": _now_iso(), "bulkProfile": a.profile, "items": []}
    if not a.replace and os.path.exists(QUEUE):
        try:
            cur = json.load(open(QUEUE, encoding="utf-8"))
            if isinstance(cur, dict) and isinstance(cur.get("items"), list):
                state["items"] = cur["items"]
        except Exception:
            pass
    have = {it.get("sourcePath") for it in state["items"] if isinstance(it, dict)}
    added = 0
    for f in films:
        if f in have:
            continue
        state["items"].append({
            "id": f"local-{uuid4().hex[:12]}",
            "name": os.path.basename(f),
            "sourcePath": f,
            "status": "waiting",
            "profile": a.profile,
        })
        added += 1
    state["updatedAt"] = _now_iso()
    os.makedirs(os.path.dirname(QUEUE), exist_ok=True)
    write_atomic(QUEUE, state)
    print(f"✓ {added} film kuyruğa eklendi (path ile, upload YOK). Toplam öğe: {len(state['items'])}.")
    print(f"  dizin: {a.dir}  | profil: {a.profile}  | mod: {'REPLACE' if a.replace else 'EKLE'}")

    if not a.no_start:
        try:
            req = urllib.request.Request(API + "/api/flow-queue/run", method="POST",
                                         data=b"{}", headers={"Content-Type": "application/json"})
            r = urllib.request.urlopen(req, timeout=10)
            print(f"✓ worker başlatıldı (HTTP {r.status}). UI'de ilerleme görünür; GPU-serial işlenir.")
        except Exception as e:
            print(f"! worker başlatılamadı ({e}). UI'den 'Başlat' ya da: POST {API}/api/flow-queue/run")
    return 0

if __name__ == "__main__":
    sys.exit(main())
