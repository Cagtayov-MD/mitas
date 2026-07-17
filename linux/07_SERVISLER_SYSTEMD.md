# 07 · Servisler → systemd

> `start_mitas.ps1` + Windows-logon autostart + ollama + watchdog'lar → systemd birimleri.
> systemd, göçün en somut kazançlarından biri: `Restart=always`, cgroup bellek limitleri,
> reboot-autostart, `journalctl` log — llama-server kilit sınıfı burada büyük ölçüde çözülür.

**Servis haritası (Windows → Linux):**

| Windows | Port/rol | systemd birimi |
|---|---|---|
| `start_mitas.ps1` → uvicorn asr_server | 8787 | `mitas-asr.service` |
| `start_mitas.ps1` → uvicorn tedial `--factory` | 8765 | `mitas-tedial.service` |
| ollama.exe serve | 11434 | `ollama.service` (resmi kurulum) |
| WebUI Vite dev | 5173 | `mitas-webui.service` (veya prod build + nginx) |
| `startup_mitas_all.ps1` (logon autostart) | — | `WantedBy=multi-user.target` (hepsi) |
| watchdog/nöbetçi ps1 | — | `Restart=always` + `nobetci_daemon.py` |

---

## Ortak env dosyası

Tüm birimler `mitas.env`'i yükler (Görev 1, [05](05_KOD_DEGISIKLIKLERI.md)):

```
EnvironmentFile=/opt/mitas/mitas.env
```

`mitas.env` ayrıca `start_mitas.ps1:22-107`'deki tüm QC2/perf default'larını içerir
([05](05_KOD_DEGISIKLIKLERI.md) Görev 8) + API anahtarları (`ANTHROPIC_API_KEY`, `MITAS_TMDB`,
`MITAS_DEEPSEEK`, `MITAS_GEMINI`, ...). Windows'ta bunlar "User env"di; Linux'ta bu dosyada.

> **Güvenlik:** API anahtarları içeren `mitas.env` `chmod 600`, sahibi servis kullanıcısı.

---

## `mitas-asr.service`

```ini
# /etc/systemd/system/mitas-asr.service
[Unit]
Description=MITAS ASR + ozet servisi (uvicorn asr_server:app, 8787)
After=network-online.target ollama.service
Wants=network-online.target

[Service]
Type=simple
User=mitas
WorkingDirectory=/opt/mitas
EnvironmentFile=/opt/mitas/mitas.env
ExecStart=/opt/mitas/venvs/asr/bin/python -m uvicorn core.api.asr_server:app \
          --host 127.0.0.1 --port 8787
Restart=always
RestartSec=3
# cgroup bellek emniyeti (opsiyonel; ASR-sübap zaten commit-boş bekliyor):
# MemoryMax=  (RAM bol, gerekirse)
StandardOutput=append:/opt/mitas/outputs/svc_8787.log
StandardError=append:/opt/mitas/outputs/svc_8787.err.log

[Install]
WantedBy=multi-user.target
```

## `mitas-tedial.service`

```ini
# /etc/systemd/system/mitas-tedial.service
[Unit]
Description=MITAS Tedial servisi (uvicorn tedial.app:create_app --factory, 8765)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=mitas
WorkingDirectory=/opt/mitas
EnvironmentFile=/opt/mitas/mitas.env
ExecStart=/opt/mitas/venvs/asr/bin/python -m uvicorn core.api.tedial.app:create_app \
          --factory --host 127.0.0.1 --port 8765
Restart=always
RestartSec=3
StandardOutput=append:/opt/mitas/outputs/svc_8765.log
StandardError=append:/opt/mitas/outputs/svc_8765.err.log

[Install]
WantedBy=multi-user.target
```

> **Dikkat (ps1'deki kural):** 8765 ASLA asr_server ile açılmaz, 8787 ASLA tedial ile. İki ayrı
> birim bunu yapısal olarak garanti eder — Windows'taki port-çakışma/zombi temizliği artık
> gereksiz (systemd tek örnek tutar).

## `ollama.service`

Resmi Linux kurulumu zaten systemd servisi getirir:

```bash
curl -fsSL https://ollama.com/install.sh | sh   # ollama.service kurar
sudo systemctl edit ollama                        # override: model yolu + keep-alive
```
```ini
# override.conf
[Service]
Environment=OLLAMA_MODELS=/data/mitas/models/ollama
Environment=OLLAMA_KEEP_ALIVE=15m
Environment=OLLAMA_HOST=127.0.0.1:11434
```

> `OLLAMA_KEEP_ALIVE=15m` = start_mitas.ps1'deki hız-modu default'u. `-1` (sınırsız) YASAK
> (proje yapma-listesi). ASR-LLM sübabı VRAM'i korur.

## `mitas-webui.service`

Geliştirme (Vite dev, 5173):
```ini
# /etc/systemd/system/mitas-webui.service
[Unit]
Description=MITAS WebUI (Vite dev, 5173)
After=network-online.target
[Service]
Type=simple
User=mitas
WorkingDirectory=/opt/mitas/webui
ExecStart=/usr/bin/pnpm dev --host --port 5173
Restart=always
[Install]
WantedBy=multi-user.target
```
> Üretim için: `pnpm build` + nginx/statik sunum daha stabil (opsiyonel, cutover sonrası).

## Watchdog / nöbetçi

`nobetci_daemon.py` zaten Python (taşınabilir). ps1 watchdog'ları yerine:

```ini
# /etc/systemd/system/mitas-nobetci.service
[Service]
Type=simple
User=mitas
WorkingDirectory=/opt/mitas
EnvironmentFile=/opt/mitas/mitas.env
ExecStart=/opt/mitas/venvs/core/bin/python scripts/nobetci_daemon.py
Restart=always
RestartSec=10
[Install]
WantedBy=multi-user.target
```
Periyodik (gece batch vb.) işler için systemd **timer** kullan (cron yerine, log entegrasyonu için).

---

## Kurulum + doğrulama

```bash
sudo cp linux/units/*.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now ollama mitas-asr mitas-tedial mitas-webui mitas-nobetci
# doğrula:
systemctl status mitas-asr mitas-tedial          # active (running)
curl -s http://127.0.0.1:8787/health             # asr_server sağlık
curl -s http://127.0.0.1:8765/tedial             # tedial
systemctl show mitas-asr | grep -i MITAS_QC2     # env yüklendi mi
journalctl -u mitas-asr -n 50                     # log
```

**Reboot testi (KAPI 2):** `sudo reboot` → makine açılınca tüm servisler kendiliğinden `active`.

## Öz-denetim

- `start_mitas.ps1`'in yaptığı her şey karşılandı: env yükleme (EnvironmentFile), iki ayrı app
  (iki birim), port-tekliği (systemd tek örnek), autostart (WantedBy), restart (Restart=always).
- ollama keep-alive=15m ve model yolu ps1/03 ile tutarlı.
- Port-app eşleşme kuralı (8787=asr, 8765=tedial) yapısal olarak garanti.
