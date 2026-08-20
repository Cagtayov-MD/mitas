# LeBron kulesi — canlı durum

**Son güncelleme:** 2026-08-20

LeBron artık tek kanonik master kompozitörüdür. 437 filmlik ölçümde `magic`
deney adıyla seçilen birleşik algoritma `src/derleyici.py` içine kalıcı olarak
taşındı; çalışma zamanında alias yoktur. Terfi öncesi motor yalnız
`arsiv/legacy_derleyici.py` altında karşılaştırma amacıyla saklanır.

## Giriş master üretim kuralı — üretime kilitli (2026-08-20)

Kobe/Sheriff'in `_sinif.json: mod=ardisik_aralik` sözleşmeli giriş havuzu
artık koşulsuz `src/giris_planlayici.py` içindeki `giris-text-only/v1` yoluna
gider. Bu bir config ayarı veya deney bayrağı değildir. Geri dönüş/fallback
olarak kayan kapanış kompozitörü kullanılmaz.

Motor yalnız Paddle ile pikselde doğrulanan yazılı kartları gruplar, aynı
karttan en sağlam tam kareyi bir kez seçer ve kartları zaman sırasıyla alt alta
koyar. Yazısız sahneler, geçiş görüntüleri ve diyalog altyazıları mastera
girmez; kaynak havuzdan hiçbir kare silinmez. Böylece girişte farklı statik
kartların aynı zeminde kaynatılması, yarım kırpılması ve kredi kaybı önlenir.

Kural kod, manifest ve testle görünürdür:

- `mode=lebron_giris_text_only`, `text_only=true`;
- `giris_plan.surum=giris-text-only/v1` ve seçilen kaynak kare haritası;
- tüm Paddle analizinin çökmesi `ARIZA(GIRIS_YAZI_ANALIZ)` olur;
- `tests/test_giris_planlayici.py` tam-kare, sıra, tekrar, fade, altyazı,
  boy-aşımı ve aktif derleyici yönlendirmesini kilitler.

Temiz gerçek kabul: LeBron `out/` sıfırlandıktan sonra 26 filmin giriş ve
çıkışı işlendi; **52/52 OKUNDU, 52/52 master**, ARIZA/METIN_YOK yok, toplam
1287,8 saniye. Bu kabul bozulmadan eşik değiştirilmez. Her davranış değişikliği
yeni plan sürümü + regresyonlar + aynı temiz toplu kabul kanıtını gerektirir.

## Çöküş kurtarma düzeltmesi (2026-08-19)

Çöküş kuralına giren masterlar (çok kare + tek kısa segment) artık
`temporal_chunk_stack` ile 12'lik zaman parçalarına bölünerek kurtarılır;
normal yol piksel olarak değişmez. Private Ollama satır-grounding
desteklemediğini beyan eder; kanıt zinciri `paddle_exact` ile bant başına
TEK model çağrısı üzerinden yürür, `image[[...]]` asla satır kanıtı olmaz.
Doğrulama: 17 yeni testle suite 180 passed; beş gerçek COKME girdisi izole
koşuda OKUNDU (VRAM/kalıntı kapıları içinde); 29-film parite yatağında
26/29 piksel-birebir, yalnız 3 çöküş filmi bilinçli farklı. Ölçüm kaydı:
`olcum/COKME_KURTARMA_DOGRULAMA_20260819.md`. Sheriff kabul yatağı yeni
pipeline hash'iyle henüz koşulmadı — sistem terfisi açık.

## Doğrulanmış durum

- CLI ve çıktı sözleşmesi değişmedi: `lebron tek/start`, `master.png`,
  `lebron.json`, `lebron.okuma.json`, `_TAMAM`.
- 29 gerçek kare havuzunda seçilmiş referansla **29/29 piksel-birebir master**,
  **29/29 `mode=lebron`** ve **29/29 manifest özeti paritesi** ölçüldü.
- Kompozitör, Paddle motoru ve `kutu_sayisi` artık aynı kanonik modülde;
  çalışma kodu deney modülüne veya emekli derleyiciye import yapmaz.
- Bozuk YAML `ARIZA(YAPILANDIRMA)` olur. Yeniden koşu eski `_TAMAM`, metin ve
  proof paketini geçerli bırakmaz. Toplu komut denenen bütün işler ARIZA ise
  sıfırdan farklı çıkar.
- Proof şeması `mitas.okuma/v2` olarak geriye uyumludur; master satırları RLE
  layout haritasıyla kaynak karelere bağlanır.

## Okuyucu ve süreç sahipliği

LeBron ortak 11434 servisine bağlanmaz. `model_kur.sh`, ağ kullanmadan yerel
Ollama 0.32.0 çalışma zamanını ve DeepSeek-OCR GGUF bloblarını SHA-256
kilitleriyle kuleye kopyalar. Ana blob:

`sha256:3a18673ff291a1d8de94d490877127899356d33a18028d5f3945bf245c11b02c`

Her CLI toplu koşusunda rastgele loopback portunda tek özel süreç açılır:

- `OLLAMA_NO_CLOUD=1`, tek yüklü model, tek paralel istek;
- `bubblewrap` ile özel `.ollama` durumu; kullanıcı `~/.ollama` değişmez;
- 90 sn ısıtma ve 30 sn sıcak bant tavanı;
- `temperature=0`, `num_predict=2048`, `num_ctx=8192`;
- loglar scratch dosyasına, stdout/stderr PIPE'a değil;
- normal bitiş, hata, Ctrl-C ve Sheriff iptalinde create-time doğrulamalı alt
  süreç temizliği.

Eski HF/Transformers ağırlığı kabul süreci bitene kadar geri dönüş malzemesi
olarak korunur, fakat aktif okuyucu onu yüklemez.

## Bellek sırası ve gerçek ölçüm

Kompozisyon ve bütün bantların Paddle kutu sayımı önce tamamlanır. Paddle
referansları/cache'i bırakıldıktan sonra özel GGUF süreci yüklenir.
`cag_output07` gerçek uçtan uca ölçümü:

- Paddle sonrası kalıntı: **338 MiB** (kapı ≤512 MiB);
- Ollama süreç-ağacı tepe VRAM: **8660 MiB** (kapı ≤9216 MiB);
- ısıtma: **22.50 sn**;
- en uzun sıcak bant: **18.36 sn** (kapı ≤30 sn);
- 18 bant, iki geçişli proof ile 36 çağrı, toplam **112.6 sn**;
- bitişte LeBron/Ollama/llama alt süreci kalmadı.

Sheriff rezervasyonu ölçülen tepe +1 GiB değerinin 512 MiB yukarı
yuvarlanmasıyla **9728 MiB** olarak ayarlandı. `max_deepseek_jobs=1` ve OOM
exclusive retry korunur.

## Değişmez kurallar

- Aktif kod `src/derleyici.py` dışındaki kompozitörü çağırmaz.
- `mod=ardisik_aralik` giriş havuzu daima `giris-text-only/v1` yoluna gider;
  config/CLI kaçış anahtarı ve kayan-kapanış fallback'i eklenmez.
- Giriş planlayıcısının eşik/gruplama değişikliği sürüm artırımı, hedefli
  regresyon ve 52 görevlik temiz kabul yenilenmeden üretime alınmaz.
- Tarihî `magic` adı yalnız eski ölçüm/karar raporlarında referans olabilir.
- Yeni Hugging Face indirmesi veya ağ erişimi yapılmaz.
- Paddle ayarları ve sürümü master piksel sadakati ölçülmeden değiştirilmez.
- Motora dokunan değişiklik 29-havuz terfi paritesini yeniden koşmalıdır.

## Açık kabul işi

LeBron birim/regresyon ve gerçek GPU kapıları geçti. Bütün sistem terfisi,
Sheriff üzerinden 29 videonun giriş/çıkış koşusu ve LeBron–Nash–Jordan ayrıntılı
kabul raporu tamamlandığında kapanacaktır.
