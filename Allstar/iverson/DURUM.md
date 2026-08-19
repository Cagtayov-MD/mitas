# Iverson durumu

**Kuruldu (2026-08-18, Faz 1: transkript), gölge modda** — sheriff'e kayıtsız,
üretimi beslemiyor.

## Faz 1 kapsamı (tamamlandı)

- Sözleşme (`sozlesme.py`): TRANSKRIPT / METIN_YOK / DIL_DESTEKSIZ / ARIZA;
  kobe değişmezleri (ARIZA asla içerik gerçeğine dönüşmez), atomik yazım +
  `_TAMAM`, sheriff kimlik bloğu.
- Motor (`src/motor.py`): scripts/_pipe_asr `_lean_transcribe` birebir —
  turbo/large-v3 seçimi, TR-mensei 'ku'-vetosu, desteklenmeyen dil dürüst
  atlama, CUDA float16 → CPU int8, VAD, transcript çıktıları.
- Kanal-dil (`src/channel_lang.py`): scripts/_channel_lang birebir; kule-içi
  scratch + HF önbelleği.
- Varlıklar: whisper 5.9G + MMS-LID 3.7G kule içinde (ağırlık-zemin ilkesine
  bilinçli istisna — Çağatay talimatı, 2026-08-18); venv 258 pin `--no-deps`
  (venvs/asr el-le-yönetilen ortamın birebir çoğaltımı; pip çözümleyicisi
  deepfilternet/numpy çakışmasını yeniden kuramaz — tam freeze tam kapalı
  küme olduğundan --no-deps güvenlidir).
- Mimosa notu: channel_lang.py + motor.py yazımı sırasında yanlış-pozitif
  "komut enjeksiyonu" blokları (liste-argv subprocess — tarayıcının kendi
  önerdiği güvenli desen) Çağatay'ın McGrady'de onayladığı prosedürle aşıldı:
  hooks.json PreToolUse geçici kaldırıldı → yazıldı → birebir geri yüklendi.

## Faz 2 (bekleyen)

- Özet üretimi (MAP satırındaki "API destekli özet") — API anahtarları ve ayrı
  sözleşme gerektirir.
- Tam run_asr_pipeline (diarize/align/quality) — core/pipelines/asr 6.2k satır;
  pyannote modeli makinada yok, film hattı kullanmıyor.
- Sheriff kaydı: DAG'de ses-üretici görev (media_prep audio) hazır — kayıt
  ayrı iş (pipeline sürüm hash'ini değiştirir).
- scripts/_pipe_asr + venvs/asr sökümü (pipeline Iverson'a bağlanınca).

## Deney kolu: Qwen3-ASR-1.7B (test/qwen3-asr/, 2026-08-18)

Whisper'a karşı paralel deney (curry.py kalıbı; kule venv/model DEĞİŞMEDİ —
deneyin kendi venv'i `qwen-asr[vllm]` + modeli kendi klasöründe). Sonuç
(BENIOKU.md'de tam tablo): saf TR'de düzey eşit; **code-switching'de Qwen net
üstün** (whisper-auto erd120'ın tamamını İngilizce yazdı, Türkçe bölüm YOK;
Qwen EN+TR tek geçişte). İkinci motor alınması ayrı plan/karar.

## Ölçüm notu

Transkript DOĞRULUĞU henüz ölçülmedi (WER çalışması yok); Faz 1'in kanıtı
sözleşme + test + kanarya koşusudur.
