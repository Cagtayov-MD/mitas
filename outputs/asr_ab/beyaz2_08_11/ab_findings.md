# beyaz2 08:00-11:00 ASR A/B Findings

## Sonuç

En iyi aday: `out_v7` (`v7_vad_merged_no_prompt`)

- VAD-guided merged chunks kullanıyor.
- `initial_prompt` yok.
- `language="tr"` kullanıyor.
- Code-switch korunuyor: `Dancing Bear`, `Ayılar dans ediyor`.
- Bilinen kötü tokenlar yok: `É`, `I don't know`, `Are the days`, prompt sızıntısı.
- Word overlap F1: `0.8814`
- Runtime: `32.733s`
- Model call count: `8`

## En Önemli Bulgular

1. `initial_prompt` bu klipte zararlı çıktı.
   - `v1`, `v2`, `v3`, `v5`, `v6` içinde prompt sızıntısı görüldü.
   - Model, "Konuklar Türkçe sohbet ediyor..." cümlesini gerçek konuşma gibi transcript'e yazdı.

2. VAD segmentlerini tek tek okutmak baseline'da hâlâ hata bırakıyor.
   - `out_v0` filtreye rağmen `Are the days` hallucination'ını korudu.

3. Fixed 28s window denemesi bu dedupe kuralıyla başarısız oldu.
   - `v3` ve `v5` çok fazla içerik düşürdü.
   - Sebep: faster-whisper bazı pencerelerde segmenti lokal `0.0` başlangıçlı büyük blok olarak döndürüyor; `segment.start < 2s` dedupe kuralı tüm pencereyi atabiliyor.

4. Full audio no-prompt (`v8`) güçlü ama v7 kadar güvenli değil.
   - Word F1: `0.8696`
   - Tek çağrı ve hızlı.
   - Ama bazı cümlelerde daha fazla anlam sapması/hallucination görüldü.

5. WhisperX (`v9`) çalıştı ve hızlıydı.
   - Word F1: `0.8783`
   - Runtime: `15.103s`
   - Code-switch korundu.
   - Ancak özel isim ve bazı ifadelerde sapma var: ör. `Natalie Blanchard` gibi.
   - Alignment venv'de torchcodec warning hâlâ görünüyor; bu varyant WAV'ı NumPy olarak verdiği için koşuyu bozmadı.

6. Selimc Turkish Turbo CT2 (`v10`) hızlı ama kalite olarak geride kaldı.
   - Model: `selimc/whisper-large-v3-turbo-turkish`
   - CT2 yolu: `E:\MITAS\models\asr\faster-whisper\selimc-whisper-large-v3-turbo-turkish-float16`
   - Strateji: `v7` ile aynı VAD-merged/no-prompt ayarı.
   - Word F1: `0.8037`
   - Runtime: `16.440s`
   - Bad token: `0`
   - Code-switch sayacı: `4`, ama `Dancing Bear` tarafında `Bear` yerine `Beer` yakalandı.
   - Örnek sapmalar: `kediydi` -> `tediydi`, `yavru` -> `yavrı`, `Daisy` -> `değzi`, `aksanım` -> `akşamın`.
   - Çıktılar yazıldıktan sonra native CUDA/CTranslate2 kapanışında abort görüldüğü için sadece bu deney varyantında `exit_after_write=True` kullanıldı.

7. Base OpenAI turbo CT2 (`v11`) hız için güçlü, ama kalite olarak `v7` altında.
   - İstenen `Systran/faster-whisper-large-v3-turbo` repo ID'si Hugging Face üzerinde `404` verdi.
   - Bunun yerine model kartında `openai/whisper-large-v3-turbo`dan CT2/float16 çevrildiği yazan `dropbox-dash/faster-whisper-large-v3-turbo` indirildi.
   - CT2 yolu: `E:\MITAS\models\asr\faster-whisper\large-v3-turbo`
   - Strateji: `v7` ile aynı VAD-merged/no-prompt ayarı.
   - Word F1: `0.8696`
   - Runtime: `14.055s`
   - Bad token: `0`
   - Code-switch sayacı: `4`, ama `Dancing Bear` ifadesi `Dancing Beer` olarak geldi.
   - Selimc `v10`dan belirgin daha temiz; bu, kalite düşüşünün önemli kısmının Türkçe fine-tune daralmasından geldiğini gösteriyor.

## Üretim İçin Öneri

İlk üretim adayı:

```text
VAD-guided merged chunks
language="tr"
initial_prompt=None
condition_on_previous_text=True
shared quality filter
```

Yani `v7` çizgisi.

WhisperX `v9` ayrıca "hızlı alternatif" olarak saklanmalı, ama ana üretim kararından önce daha fazla özel isim/code-switch testi gerekir.

Selimc Turkish Turbo `v10` bu Beyaz2 kesitinde ana aday yapılmamalı. Hız avantajı var, fakat gerçek yayın/code-switch kalitesi `v7` ve `v9` seviyesinin altında kaldı.

Base turbo `v11` hız kritik senaryolar için ikinci aday olabilir. Ancak ana kalite hedefinde hâlâ `v7` önde: `v11`, `Daisy/kediydi` gibi yerlerde Selimc'e göre toparlıyor ama `Dancing Bear` ve bazı anlam ifadelerinde `v7` kadar güvenilir değil.
