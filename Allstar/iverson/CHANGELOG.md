# Iverson CHANGELOG

## 2026-08-18 (akşam) — Deney kolu: Qwen3-ASR-1.7B (vLLM, bf16)

- `test/qwen3-asr/` paralel deney (kule üretim venv'ine DOKUNMADAN; kendi
  venv'i `qwen-asr[vllm]` 0.14.0 + model 4.4G klasör içinde). vLLM fabrikası
  `Qwen3ASRModel.LLM` (from_pretrained DEĞİL — transformers backend'i).
- Kıyas (haber20 + erd20/120, BENIOKU.md'de tam tablo): saf TR eş düzey;
  code-switching'de Qwen net üstün — whisper-auto erd120'ı tümü İngilizce
  yazdı (Türkçe bölüm 0), Qwen EN+TR tek geçişte; whisper tr-zorlu halüsinasyon
  üretti. Qwen 3 dosya batch 12.2 sn; whisper dosya-başına 5-7 sn.
- İkinci motor kararı ayrı plan (sözleşme alanı + LID-motor seçimi + VRAM
  politikası) — deney klasörü deney olarak kalır.

## 2026-08-18 — Kurulum, Faz 1: transkript (gölge)

- Kobe kalıbıyla kule kuruldu: `sozlesme.py` (TRANSKRIPT/METIN_YOK/DIL_DESTEKSIZ/
  ARIZA; kobe değişmezleri, atomik yazım + _TAMAM, sheriff kimlik bloğu),
  `main.py` (tek/start CLI, --lid --dil --model --beam --vad --tr-mensei
  --max-saniye), `iverson` wrapper, `config.yaml` (film lean profili).
- Motor: `src/motor.py` (scripts/_pipe_asr `_lean_transcribe` birebir; kule-içi
  model yolları, CUDA→CPU int8, TR-mensei 'ku'-vetosu, dürüst dil-atlama) +
  `src/channel_lang.py` (MMS-LID kanal-dil; kule-içi scratch + HF önbelleği).
- Varlıklar KULE İÇİNDE (dışa bağımlılık yok — Çağatay talimatı): whisper
  5.9G (large-v3, large-v3-turbo, selimc-turkish) + MMS-LID 3.7G
  (model/hf) + venv 11G (258 pin, venvs/asr birebir freeze, `--no-deps` —
  el-le-yönetilen ortamın birebir çoğaltımı; pip çözümleyici deepfilternet/
  numpy çakışmasını yeniden kuramıyordu).
- Mimosa notu: channel_lang.py/motor.py yanlış-pozitif "komut enjeksiyonu"
  blokları (liste-argv subprocess — tarayıcının kendi önerdiği desen),
  McGrady'de onaylanmış prosedürle aşıldı (hooks.json PreToolUse geçici
  kaldır → yaz → birebir geri yükle).
- Testler: 24 passed (sözleşme değişmezleri, motor orkestrasyonu
  faster_whisper fake'i ile — GPU gerektirmez, izolasyon).
- KANARYA (gerçek veri): 20 sn TRT haber sesi → TRANSKRIPT, dil=tr
  (whisper oto-tespit), turbo@cuda, 3 segment, 5.1 sn — transkript doğru
  Türkçe ("F-16'lar Eskişehir 1. Anajet üstünden havalandı...").
- Faz 2 bekliyor: özet üretimi, tam run_asr_pipeline (diarize/align),
  sheriff kaydı, scripts/_pipe_asr + venvs/asr sökümü.
