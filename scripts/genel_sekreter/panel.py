"""Genel Sekreter Web Paneli — accordion'lu KONTROL detayları.

Port 8898'de çalışır.
Her KONTROL film tıklanabilir → kök neden, pipeline izi, OCR çıktısı açılır.

Kullanım: python -m genel_sekreter panel
"""
from __future__ import annotations

import json
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from genel_sekreter.ajan_kontrol import analiz_kontrol
from genel_sekreter.ajan_performans import olcum_performans
from genel_sekreter.ajan_qc_dogrulama import spot_check
from genel_sekreter.config import RAPORLAR_DIR

PORT = 8898


def _durum_json() -> dict:
    try:
        kontrol = analiz_kontrol()
    except Exception as e:
        kontrol = {"error": str(e)}
    try:
        performans = olcum_performans()
    except Exception as e:
        performans = {"error": str(e)}
    try:
        onayli = spot_check(orneklem_pct=5)
    except Exception as e:
        onayli = {"error": str(e)}

    son_raporlar = []
    if RAPORLAR_DIR.is_dir():
        for f in sorted(RAPORLAR_DIR.glob("GS_*.md"), key=lambda x: x.stat().st_mtime, reverse=True)[:10]:
            son_raporlar.append({
                "ad": f.name,
                "tarih": time.strftime("%d.%m %H:%M", time.localtime(f.stat().st_mtime)),
            })

    return {
        "saat": time.strftime("%H:%M:%S"),
        "kontrol": kontrol,
        "performans": performans,
        "onayli": onayli,
        "son_raporlar": son_raporlar,
    }


# ── Kategori renkleri ──────────────────────────────────────────────────
KAT_RENK = {
    "JENERIK_KAYIP": "#f0883e",
    "OCR_HATA": "#f85149",
    "PARSE_HATA": "#d29922",
    "KB_EKSIK": "#8b949e",
    "QC_HATA": "#bc8cff",
    "DIGER": "#58a6ff",
}

HTML_SAYFA = r"""<!doctype html><html lang="tr"><head><meta charset="utf-8">
<title>MITAS Genel Sekreter</title>
<style>
*{box-sizing:border-box}
body{font-family:system-ui,sans-serif;margin:0;background:#0d1117;color:#c9d1d9}
header{padding:12px 20px;background:#161b22;border-bottom:1px solid #30363d;display:flex;gap:20px;align-items:center;position:sticky;top:0;z-index:10}
h1{font-size:16px;margin:0;color:#e8c268}
.saat{font-size:12px;color:#8b949e}
main{padding:16px;display:flex;flex-direction:column;gap:12px}
.row{display:grid;grid-template-columns:1fr 1fr;gap:12px}
section{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:12px 16px}
h2{font-size:13px;letter-spacing:1px;margin:0 0 10px;color:#58a6ff}
.sayi{font-size:28px;font-weight:700;color:#fff}
.alt{font-size:11px;color:#8b949e;margin-top:4px}
table{width:100%;border-collapse:collapse;font-size:12px}
th{text-align:left;padding:4px 8px;color:#8b949e;border-bottom:1px solid #30363d}
td{padding:4px 8px;border-bottom:1px solid #21262d}
ul{list-style:none;margin:0;padding:0;font-size:12px}
li{padding:3px 0;border-bottom:1px solid #21262d}

/* Accordion */
.kontrol-liste{display:flex;flex-direction:column;gap:2px}
.film-card{background:#0d1117;border:1px solid #30363d;border-radius:6px;overflow:hidden}
.film-header{display:flex;align-items:center;gap:8px;padding:8px 12px;cursor:pointer;transition:background .15s}
.film-header:hover{background:#161b22}
.film-header .ok{color:#8b949e;font-size:10px;transition:transform .2s}
.film-card.acik .film-header .ok{transform:rotate(90deg)}
.film-header .title{flex:1;font-size:13px;font-weight:600;color:#e6edf3}
.film-header .trt{font-size:10px;color:#8b949e}
.film-header .badge{padding:2px 8px;border-radius:10px;font-size:10px;font-weight:600;white-space:nowrap}
.film-body{display:none;padding:8px 12px 12px;border-top:1px solid #30363d;font-size:12px}
.film-card.acik .film-body{display:block}
.kok{background:#f8514915;border-left:3px solid #f85149;padding:8px 12px;margin:8px 0;border-radius:0 4px 4px 0;color:#ffa198;font-size:13px;line-height:1.5}
.iz{background:#0d1117;border:1px solid #21262d;border-radius:4px;padding:8px;margin:8px 0;font-family:monospace;font-size:11px;max-height:200px;overflow-y:auto;line-height:1.6;white-space:pre-wrap;color:#8b949e}
.ocr-box{background:#161b22;border:1px solid #30363d;border-radius:4px;padding:8px;margin:8px 0;font-family:monospace;font-size:11px;max-height:150px;overflow-y:auto;white-space:pre-wrap;color:#d29922}
.neden-list{margin:6px 0}
.neden-list li{padding:2px 0;border:none;color:#c9d1d9}
.neden-list li::before{content:"→ ";color:#f85149}
.label{color:#8b949e;font-size:11px;margin-top:6px}
</style></head><body>
<header>
  <h1>🏛️ MITAS Genel Sekreter</h1>
  <span class="saat" id="saat">--:--:--</span>
  <span class="alt" id="summary_text"></span>
</header>
<main>
  <div class="row">
    <section>
      <h2>⚡ Performans</h2>
      <div id="perf_icerik"></div>
    </section>
    <section>
      <h2>📊 Neden Dağılımı</h2>
      <div id="neden_tablo"></div>
    </section>
  </div>

  <div class="row">
    <section>
      <h2>🔍 Sistemik Bulgular</h2>
      <ul id="bulgular"></ul>
    </section>
    <section>
      <h2>✅ ONAYLI QC</h2>
      <div class="sayi" id="onayli_sayi">--</div>
      <div class="alt" id="onayli_alt"></div>
      <div id="onayli_bulgular" style="margin-top:10px"></div>
    </section>
  </div>

  <section>
    <h2>📋 KONTROL Filmler <span id="kontrol_count" class="alt"></span></h2>
    <div class="kontrol-liste" id="kontrol_liste"></div>
  </section>
</main>

<script>
const KAT_RENK = """ + json.dumps(KAT_RENK) + r""";

async function guncelle() {
  try {
    const r = await fetch('/durum');
    const d = await r.json();
    document.getElementById('saat').textContent = d.saat;

    const k = d.kontrol;
    const p = d.performans;
    const o = d.onayli;

    // Summary
    document.getElementById('summary_text').textContent =
      `${k.toplam_film||0} film | ${k.toplam_kontrol||0} KONTROL | ${((k.toplam_film||0)-(k.toplam_kontrol||0))} ONAYLI`;

    // KONTROL count
    document.getElementById('kontrol_count').textContent =
      `(${k.toplam_kontrol||0} film — tıklayarak kök nedeni gör)`;

    // Neden tablo
    const ns = k.neden_siniflar || [];
    document.getElementById('neden_tablo').innerHTML =
      '<table><tr><th>Sınıf</th><th>Modül</th><th>Sayı</th><th>%</th></tr>' +
      ns.slice(0,10).map(n =>
        `<tr><td>${n.sinif}</td><td style="color:#8b949e;font-size:11px">${n.modul}</td><td style="color:#f85149;font-weight:600">${n.sayi}</td><td>${n.yuzde}%</td></tr>`
      ).join('') + '</table>';

    // Bulgular
    document.getElementById('bulgular').innerHTML =
      (k.sistemik_bulgular||[]).map(b => `<li>${b}</li>`).join('') ||
      '<li style="color:#3fb950">Sistemik bulgu yok</li>';

    // ONAYLI
    document.getElementById('onayli_sayi').textContent = o.toplam_onayli || 0;
    document.getElementById('onayli_alt').textContent =
      `${o.incelenen||0} incelendi, ${o.sorunlu||0} şüpheli`;
    document.getElementById('onayli_bulgular').innerHTML =
      (o.bulgular||[]).slice(0,5).map(b =>
        `<li>⚠ <b>${b.title||b.film}</b>: ${b.sorunlar.slice(0,2).join(', ')}</li>`
      ).join('') || '<li style="color:#3fb950">✅ Temiz</li>';

    // Performans
    const t = p.timing_ozet || {};
    document.getElementById('perf_icerik').innerHTML = `
      <table>
        <tr><td>Film</td><td><b>${t.film_sayisi||0}</b></td></tr>
        <tr><td>Ortalama</td><td><b>${t.toplam_ort_dk||'?'} dk</b></td></tr>
        <tr><td>Medyan</td><td>${t.toplam_medyan_dk||'?'} dk</td></tr>
        <tr><td>Min / Max</td><td>${t.toplam_min_dk||'?'} / ${t.toplam_max_dk||'?'} dk</td></tr>
        <tr><td>Toplam yük</td><td>${t.toplam_saat||'?'} saat</td></tr>
        <tr><td>Disk</td><td>${p.disk_bos_gb||'?'} GB boş</td></tr>
        <tr><td>GPU</td><td>${p.gpu ? '%'+p.gpu.vram_pct+' VRAM, %'+p.gpu.gpu_util_pct+' util' : 'N/A'}</td></tr>
      </table>
      ${p.kosucu ? `<div class="alt" style="margin-top:8px">Koşu: [${p.kosucu.son_n}/${p.kosucu.son_toplam}]</div>` : ''}
      ${(t.darbogaz_adaylari||[]).slice(0,3).map(d => `<div style="color:#d29922;margin-top:4px;font-size:11px">${d}</div>`).join('')}
      ${(p.uyarilar||[]).map(u => `<div style="color:#f85149;margin-top:4px;font-size:11px">${u}</div>`).join('')}
    `;

    // KONTROL film listesi (accordion)
    const fr = k.film_raporlari || [];
    document.getElementById('kontrol_liste').innerHTML = fr.map((f, i) => {
      const renk = KAT_RENK[f.kategori] || '#58a6ff';
      const izHtml = (f.pipeline_iz||[]).length
        ? `<div class="label">Pipeline İzi:</div><div class="iz">${f.pipeline_iz.join('\n')}</div>`
        : '';
      const ocrHtml = f.ocr_okundu
        ? `<div class="label">OCR Ne Okudu:</div><div class="ocr-box">${f.ocr_okundu.replace(/</g,'&lt;')}</div>`
        : '';
      const nedenHtml = (f.nedenler||[]).length
        ? `<div class="label">Tüm Nedenler:</div><ul class="neden-list">${f.nedenler.map(n=>'<li>'+n+'</li>').join('')}</ul>`
        : '';
      return `<div class="film-card" id="fc${i}">
        <div class="film-header" onclick="document.getElementById('fc${i}').classList.toggle('acik')">
          <span class="ok">▶</span>
          <span class="title">${f.title}</span>
          <span class="trt">${f.trt_id}</span>
          <span class="badge" style="background:${renk}22;color:${renk}">${f.kategori}</span>
          <span class="badge" style="background:#30363d;color:#8b949e">${f.kontrol_tip}</span>
          <span style="font-size:11px;color:#8b949e">${f.timing_toplam.toFixed(0)}sn</span>
        </div>
        <div class="film-body">
          <div class="kok">🔍 <b>Kök Neden:</b> ${f.kok}</div>
          ${nedenHtml}
          ${ocrHtml}
          ${izHtml}
        </div>
      </div>`;
    }).join('');

  } catch(e) { console.error(e); }
}
guncelle();
setInterval(guncelle, 30000);
</script></body></html>"""


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path in ("/", "/gs"):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML_SAYFA.encode("utf-8"))
        elif self.path == "/durum":
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            data = json.dumps(_durum_json(), ensure_ascii=False, default=str)
            self.wfile.write(data.encode("utf-8"))
        elif self.path.startswith("/rapor/"):
            rapor_yolu = RAPORLAR_DIR / self.path[7:]
            if rapor_yolu.is_file():
                self.send_response(200)
                self.send_header("Content-Type", "text/markdown; charset=utf-8")
                self.end_headers()
                self.wfile.write(rapor_yolu.read_bytes())
            else:
                self.send_error(404)
        else:
            self.send_error(404)

    def log_message(self, format, *args):
        pass


def baslat_panel(port: int = PORT):
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"Genel Sekreter Paneli: http://127.0.0.1:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nPanel durduruldu.")
        server.shutdown()
