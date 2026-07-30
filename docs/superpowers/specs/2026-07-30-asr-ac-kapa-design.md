# ASR + Özet Aç/Kapa — Tasarım (2026-07-30, Çağatay onaylı)

## Amaç
Tek bir anahtar: Çağatay test kliplerinde ASR'siz çalışır (GPU/süre israfı yok),
normal sürece dönünce açar. Kapalıyken PDF **temiz** üretilir (placeholder ÖZET
paneli olmadan). Karar süreci: film-bazlı seçenek değerlendirildi, Çağatay "bir
tane bir şey ekle, ben açıp kapatayım" diye sadeleştirdi — TEK GLOBAL ANAHTAR.

## Mekanizma
- **Durum kaynağı:** `outputs/flow_queue/queue.json` üst-düzey `asrEnabled: bool`
  (varsayılan `true`). Emsal: `bulkProfile` aynı yerde yaşıyor.
  DİKKAT: `put_flow_queue` state'i sıfırdan kurar (asr_server.py:433) — alan
  oraya AÇIKÇA eklenir, yoksa sessizce düşer (bu oturumda kanıtlandı).
- **UI:** FlowQueuePanel başlığına (bulkProfile seçicisinin yanı) `switch.tsx`
  ile "ASR + Özet" anahtarı. GET /api/flow-queue'dan okur, değişimde mevcut
  `saveFlowQueueServerState` PUT'una `asrEnabled` eklenir. Başka UI yok.
- **Worker (kuyruk yolu):** iş spawn edilirken state'ten `asrEnabled` okunur;
  `false` ise cmd'ye `--no-asr` eklenir (asr_server.py:920 bölgesi).
- **Tek-dosya yolu** (`/api/pipeline/run` → `_run_pipeline_job`): aynı state
  dosyasından okur — tek otorite, Tedial yolu da bedavaya kapsanır.
- **Pipeline:** `--no-asr` mevcut; TEK EK — `args.no_asr` iken `ozet = ""`
  (mitas_pipeline.py:3048 placeholder yerine) → `_make_pdf.py:278` paneli atlar
  (936a12b'de commit'li). v4-final aynı `build()`'den geçtiği için ikisi de kapanır.

## ASR_KAPALI.flag'in kaderi
Dosya SİLİNİR (anahtarı ezerdi). Mekanizma kodda KALIR = acil global kill
(test/ölçüm kampanyası, 11 Tem amacı). Öncelik: flag varsa her şeyi ezer →
anahtar → varsayılan açık. API-guard `asr_kapali_mi()` flag-bazlı kalır
(anahtar STT-only endpoint'leri 409'lamaz — anahtar KÜNYE pipeline'ının ASR
adımını yönetir, canlı STT ayrı kullanım).

## Testler (TDD)
1. `put_flow_queue` `asrEnabled`i korur; eski payload (alansız) → true.
2. Worker/tek-dosya cmd kurulumu: false → `--no-asr` var; true/eksik → yok.
3. `_make_pdf.build`: `ozet=""` → sayfa metninde "ÖZET" yok; dolu → var
   (fitz ile gerçek PDF metni okunarak).
4. `test_asr_killswitch.py` yeni sözleşme: "dosya var olmalı" assert'i kalkar;
   flag VARSA no_asr zorlanır, YOKSA zorlanmaz.

## Doğrulama
- Anahtar kapalı → kuyruktan film → PDF panelsiz + `--no-asr` kanıtı logda.
- Anahtar açık → `--asr-max-seconds 120` kısa koşu → transcript üretildi
  (CUDA yükü bugün kanıtlandı: ctranslate2 4.7.1 model float16 yüklüyor;
  29 Tem'deki libcublas.so.12 engeli artık yok).
- `mitas-asr` systemd servisi yeniden başlatılır (asr_server.py değişiyor).

## Kapsam dışı (YAGNI)
Film-bazlı override, ayarlar sayfası, özet-web zincirinin otomasyonu,
ASR-only endpoint davranış değişikliği.
