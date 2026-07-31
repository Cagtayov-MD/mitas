#!/usr/bin/env python3
"""Toplu koşu canlı izleme paneli — bağımsız, girişsiz, salt-okunur.

Kaynaklar: export/ONAYLI, export/KONTROL, özel-tür klasörü (mtime sıralı),
outputs/toplu_kosu/kosucu.log kuyruğu, disk boşluğu.
Kullanım: python3 scripts/toplu_izleme.py  (port 8899; / = panel, /durum = JSON)
"""
from __future__ import annotations

import json
import os
import shutil
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

KOK = Path(os.environ.get("MITAS_PROJECT_ROOT", "/opt/mitas"))
CIKTI = KOK / "Mitas Output"
KLASORLER = {
    "onayli": CIKTI / "export" / "ONAYLI",
    "kontrol": CIKTI / "export" / "KONTROL",
    "ozel": CIKTI / "muzikal_animasyon_belgesel",
}
LOG = KOK / "outputs" / "toplu_kosu" / "kosucu.log"


def _dosyalar(d: Path, n: int = 40):
    if not d.is_dir():
        return []
    ds = sorted((p for p in d.iterdir() if p.is_file()),
                key=lambda p: p.stat().st_mtime, reverse=True)[:n]
    return [{"ad": p.name, "zaman": time.strftime("%H:%M", time.localtime(p.stat().st_mtime)),
             "gun": time.strftime("%d.%m", time.localtime(p.stat().st_mtime))} for p in ds]


def durum() -> dict:
    d = {"kuyruk": {}, "sayilar": {}, "log": [], "disk_bos_gb": 0, "saat": time.strftime("%H:%M:%S")}
    for ad, yol in KLASORLER.items():
        d["kuyruk"][ad] = _dosyalar(yol)
        d["sayilar"][ad] = sum(1 for p in yol.iterdir() if p.is_file()) if yol.is_dir() else 0
    if LOG.is_file():
        satirlar = LOG.read_text(encoding="utf-8", errors="replace").splitlines()
        d["log"] = satirlar[-8:]
        d["islenen"] = sum(1 for s in satirlar if s.startswith("--- ["))
        d["atlanan"] = sum(1 for s in satirlar if s.startswith("ATLA"))
    d["disk_bos_gb"] = round(shutil.disk_usage(str(KOK)).free / 1e9)
    return d


SAYFA = """<!doctype html><html lang="tr"><head><meta charset="utf-8">
<title>MİTAS Toplu Koşu</title><style>
body{font-family:system-ui,sans-serif;margin:0;background:#10141c;color:#dde3ee}
header{padding:10px 16px;background:#1a2130;display:flex;gap:18px;align-items:baseline;flex-wrap:wrap}
h1{font-size:15px;margin:0;color:#e8c268}.roz{font-size:12px;color:#93a0b8}
.sayi{font-weight:700;color:#fff}
main{display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px;padding:10px 14px}
section{background:#161c28;border-radius:8px;padding:8px 10px;min-height:120px}
h2{font-size:12px;letter-spacing:1px;margin:2px 0 8px}
.onayli h2{color:#5fd68a}.kontrol h2{color:#e9b04e}.ozel h2{color:#7db4e8}
ul{list-style:none;margin:0;padding:0;font-size:12px}
li{padding:3px 4px;border-bottom:1px solid #202839;display:flex;justify-content:space-between;gap:8px}
li span.z{color:#6c7a94;white-space:nowrap}
pre{background:#0c0f16;border-radius:8px;margin:0 14px 14px;padding:10px;font-size:11px;
color:#9fb0c8;overflow-x:auto;white-space:pre-wrap}
.yeni{animation:parla 2.5s ease-out}
@keyframes parla{from{background:#2b3b2b}to{background:transparent}}
</style></head><body>
<header><h1>MİTAS TOPLU KOŞU</h1>
<span class="roz">ONAYLI <span class="sayi" id="n_on">-</span></span>
<span class="roz">KONTROL <span class="sayi" id="n_ko">-</span></span>
<span class="roz">ÖZEL-TÜR <span class="sayi" id="n_oz">-</span></span>
<span class="roz">işlenen <span class="sayi" id="n_is">-</span> · atlanan <span class="sayi" id="n_at">-</span></span>
<span class="roz">disk <span class="sayi" id="n_di">-</span> GB</span>
<span class="roz" id="saat"></span></header>
<main>
<section class="onayli"><h2>✔ ONAYLI'YA DÜŞENLER</h2><ul id="l_on"></ul></section>
<section class="kontrol"><h2>⚠ KONTROL'E DÜŞENLER</h2><ul id="l_ko"></ul></section>
<section class="ozel"><h2>◆ ÖZEL TÜR</h2><ul id="l_oz"></ul></section>
</main>
<pre id="log"></pre>
<script>
let onceki = new Set();
async function tazele(){
  try{
    const r = await fetch('/durum'); const d = await r.json();
    for (const [k, el, sk] of [["onayli","l_on","n_on"],["kontrol","l_ko","n_ko"],["ozel","l_oz","n_oz"]]){
      document.getElementById(sk).textContent = d.sayilar[k];
      const ul = document.getElementById(el); ul.innerHTML = "";
      for (const f of d.kuyruk[k]){
        const li = document.createElement("li");
        const anahtar = k + "|" + f.ad;
        if (onceki.size && !onceki.has(anahtar)) li.className = "yeni";
        onceki.add(anahtar);
        li.innerHTML = `<span>${f.ad}</span><span class="z">${f.gun} ${f.zaman}</span>`;
        ul.appendChild(li);
      }
    }
    document.getElementById("n_is").textContent = d.islenen ?? "-";
    document.getElementById("n_at").textContent = d.atlanan ?? "-";
    document.getElementById("n_di").textContent = d.disk_bos_gb;
    document.getElementById("saat").textContent = "güncelleme " + d.saat;
    document.getElementById("log").textContent = (d.log || []).join("\\n");
  }catch(e){ document.getElementById("saat").textContent = "sunucuya erişilemiyor"; }
}
tazele(); setInterval(tazele, 10000);
</script></body></html>"""


class Istek(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith("/durum"):
            veri = json.dumps(durum(), ensure_ascii=False).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
        else:
            veri = SAYFA.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(veri)))
        self.end_headers()
        self.wfile.write(veri)

    def log_message(self, *a):  # erişim logu sessiz
        pass


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", 8899), Istek).serve_forever()
