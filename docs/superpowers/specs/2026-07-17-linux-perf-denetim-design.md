# MITAS Linux Performans Denetimi — Tasarım (2026-07-17)

## Amaç
Bare-metal Ubuntu'ya taşınan MITAS'ta **gereksiz bekleten/geciktiren** kod desenlerini
koşu yapmadan (statik denetim + hedefli mikro-ölçüm) bulmak, önceliklendirmek ve
düşük riskli olanları düzeltmek.

## Kapsam
Her şey: `core/`, `scripts/`, `harness/`, `model2/`, `webui/src`, `council_mcp/`,
`tools/` (kendi betikleri), `kurulum/`, systemd servisleri, `config/`, `mitas.env`.
**Hariç:** `venvs/`, `models/`, `node_modules/`, `Database/`, `Mitas_Files/`, cache'ler.

## Yöntem (onaylanan C yaklaşımı)
1. **Paralel Sonnet-agent taraması** — 7 bölge, her agent aynı kontrol listesiyle:
   sleep/polling, seri-paralellenebilir işler, subprocess israfı, Win/WSL kalıntıları
   (E:\ yolları, şişkin timeout, /mnt), I/O israfı, model/venv reload, GPU boşta bekletme,
   seri API çağrıları.
2. **Mikro-ölçümler (koşusuz)** — venv python başlatma süreleri, ağır import süreleri,
   disk/mount tipleri (NTFS kalıntısı?), CPU governor, GPU persistence, swap/bellek durumu.
3. **Doğrulama** — her agent bulgusu ana oturumda dosya açılarak teyit edilir
   (halüsinasyon eleme).
4. **Sınıflama** — P0/P1/P2 öncelik + düşük/orta/yüksek risk + tahmini kazanım.

## Çıktı ve düzeltme politikası (kullanıcı kararı)
- Rapor: `docs/` altına, dosya:satır referanslı.
- **Düşük riskli** bulgular doğrudan düzeltilir.
- Orta/yüksek riskli bulgular **sorun → sebep → çözüm önerisi** formatında onaya sunulur.

## Bölge → agent eşlemesi
| # | Bölge | İçerik |
|---|---|---|
| 1 | core/ | api, jobs, pipelines, observability (114 py) |
| 2 | scripts/ A | `_pipe_*.py`, `mitas_pipeline.py`, `mitas_roots.py` (sıcak yol) |
| 3 | scripts/ B | kalan ~200 betik |
| 4 | harness/ | 36 dosya (master_run, asama*, dense, montage) |
| 5 | model2/ + council_mcp/ | OCR MODEL2 + MCP sunucusu |
| 6 | webui/src | 77 dosya (UI + build konfig) |
| 7 | tools/ + kurulum/ + systemd + config | asr_ab, kurulum betikleri, servis tanımları |

## Başarı ölçütü
Somut, doğrulanmış, dosya:satır referanslı bulgu listesi; düşük riskliler uygulanmış;
kalanlar onay bekleyen net öneri kartları halinde.
