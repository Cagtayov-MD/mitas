# Codex Görev Brief — MITAS v0.1 ASR Hazırlık Çalışması

> Hazırlayan: Claude (web oturumu), 2026-05-11
> Hedef: ASR v0.1 dikey dilim sprintine girmeden ÖNCE runtime ve venv temelini temizlemek
> Bu görev sprint kodu değildir. Sprint hazırlığıdır.
> Tahmini süre: 1-2 oturum

---

## 0. ÖNCE OKU (atlanamaz)

Aşağıdaki dosyalar **sırayla** okunur. Okunmadan paket kurulmaz, komut çalıştırılmaz.

1. `E:\MITAS\_proje_takip\00_BURADAN_BASLA.md`
2. `E:\MITAS\_proje_takip\01_PROJE_VIZYON.md` — özellikle §5 (prensipler)
3. `E:\MITAS\_proje_takip\02_CALISMA_DISIPLINI.md` — özellikle §5 (LLM protokolü)
4. `E:\MITAS\_proje_takip\03_GUNCEL_DURUM.md`
5. `E:\MITAS\_proje_takip\05_AKTIF_GOREV.md`
6. `E:\MITAS\_proje_takip\06_KARARLAR_GUNLUGU.md`

Okuma bitince geliştiriciye "okudum, hazırım" deyip onay bekle. **Kendi başına başlama.**

---

## 1. NE YAPACAKSIN — ÖZET

Bu görev v0.1 ASR pipeline'ını **yazmak değil**. Sprint öncesi runtime temelini sağlamlaştırmak. Altı adım:

1. Kararları `06_KARARLAR_GUNLUGU.md`'ye yazma
2. FFmpeg full-shared build kurulumu + PATH temizliği
3. Torchcodec decode testi (asr + alignment venv)
4. Yeni `denoise` venv kurulumu (DeepFilterNet için)
5. Alignment venv'de WhisperX word-level alignment smoke
6. faster-whisper large-v3 modelini indirme
7. Sprint öncesi checkpoint

Sıralama önemli; bağımlılık zincirine göre düzenlendi. Atlatma.

---

## 2. ÇALIŞMA DİSİPLİNİ (KISALTMA — TAM HALİ §0'DA OKUDUN)

- **Sormadan kodlamak yok.** Her adım öncesi "şunu çalıştıracağım, onay verir misin?" diye sor. İstisna sadece basit inspect komutları (`pip list`, `where ffmpeg`, dosya `view`).
- **Cümleyle anlat, kod bloğuyla değil.** Geliştirici komutu görmek istediğinde söyler.
- **Yes-man olma.** Bu brief'te bir şey yanlış görünüyorsa, **uygulamadan önce** geliştiriciye sor. "Şuradaki adımda şu risk var, doğrulayalım mı?" diyerek.
- **Acele yok.** Bir adım tıkanırsa zorla devam etme; geliştiriciye söyle.
- **Sistem temelini sarsma.** Bu brief dışında ek paket / venv / config değişikliği önermeden danış.
- **Aşama aşama.** Her adımdan sonra "bu doğrulandı mı?" kontrolü. Doğrulanmadan sonraki adıma geçilmez.
- **Her şey kayda.** Her adım sonunda ne yaptığını ve sonucunu yaz. Çıktılar `outputs/` ve `docs/` altında dosyaya düşer.
- **"Sonra çözeriz" yok.** Bu felsefe bu projede geçerli değil. Bir adım yarım kalırsa geliştirici ile karar alıp yeniden hizalanırsın, atlamazsın.

---

## 3. KIRMIZI HAT — DOKUNMAYACAKLARIN

Aşağıdakilere **kesinlikle** dokunmuyorsun. Hangi gerekçe gelirse gelsin.

### 3.1 asr venv'in korunan paketleri

`E:\MITAS\venvs\asr` içinde **şunlar değiştirilmez, downgrade edilmez, upgrade edilmez:**

- `torch==2.11.0+cu126`
- `torchaudio==2.11.0+cu126`
- `numpy==2.2.6`
- `faster-whisper==1.2.1`
- `ctranslate2==4.7.1`
- `silero-vad==6.2.1`
- `pyannote-audio==4.0.4`
- `onnxruntime==1.23.2`

DeepFilterNet asr venv'de pip check'i kırmızıya düşürüyor olabilir; bunu çözmek için **asr venv'de hiçbir şey değiştirmiyorsun.** Çözüm yeni `denoise` venv (Adım 4'te).

### 3.2 Diğer venv'lere bulaşma yok

Bu görev kapsamında dokunabileceğin venv'ler:
- `asr` (yalnızca inspect ve test — paket değişimi yok)
- `alignment` (yalnızca inspect ve test — paket değişimi yok)
- `denoise` (YENİ kuracaksın)

**Aşağıdaki venv'lere hiçbir paket ekleme / kaldırma / upgrade yapma:**
- `stt` (legacy, korunuyor)
- `core`, `ocr`, `face`, `visual`, `audio`, `tag`

### 3.3 Üretim pipeline kodu yazma

- `core/pipelines/asr/` veya benzeri bir klasör **henüz açılmaz.** O v0.1 sprint kapsamı, bu brief'in değil.
- Sprint dosya yapısı kararı geliştiriciye ait (bkz. `05_AKTIF_GOREV.md` §3.4). Senden bu kararı vermeni beklemiyoruz.

### 3.4 Schema değişikliği yok

- `core/schemas/` altındaki Pydantic modellerine dokunulmaz.
- `schemas/` altındaki JSON Schema dosyalarına dokunulmaz.
- `scripts/export_json_schema.py` yeniden koşturulmaz.

### 3.5 Plan ve uygulama dökümanları değiştirilemez

- `MITAS_Master_Plan_Denetimli_v5.md` — bu dosyaya satır eklenmez, çıkarılmaz.
- `MITAS_Uygulama_Plani_v1.md` — aynı.
- Yeni karar her zaman `_proje_takip/06_KARARLAR_GUNLUGU.md`'ye düşer.

### 3.6 Mevcut test dosyalarına dokunma

- `tests/` altındaki 47 test dosyası değiştirilmez. Yeni smoke testleri eklenebilir; mevcut testler yerinde kalır.

### 3.7 `.gitignore` ve disk düzeni

- `cache/`, `venvs/`, `models/` zaten gitignore'da. Yeni `venvs/denoise` klasörü oluşturulduğunda bu kuralın korunduğundan emin ol.
- Yeni dizinler kök dışında açılırsa (örn. `E:\tools\ffmpeg-shared\`) geliştiriciye doğru konumu sor.

---

## 4. YAPILACAKLAR (SIRALI ADIMLAR)

Her adımda: önce sor → uygula → sonucu doğrula → kayda al. Her adım sonunda commit.

---

### 4.1 ADIM 1 — Kararları yazma

**Amaç:** `_proje_takip/06_KARARLAR_GUNLUGU.md`'ye altı yeni karar girişi açmak.

**Eklenecek kararlar** (dosyadaki şablonu kullanarak):

- **2026-05-11 / 3 — asr venv ana ASR/STT runtime**
  - Karar: ASR pipeline'ının ana runtime'ı `E:\MITAS\venvs\asr` olur. stt venv legacy olarak korunur ama primary değildir.
- **2026-05-11 / 4 — WhisperX alignment venv'de kalır**
  - Karar: WhisperX asr venv'e eklenmez. `E:\MITAS\venvs\alignment` venv'inde kalır. asr pipeline ona subprocess üzerinden konuşur.
- **2026-05-11 / 5 — M16 Subprocess sleeve pattern**
  - Karar: Dependency çatışması olan modüller (denoise, alignment, ileride muhtemelen başkaları) ayrı venv'lerde yaşar; ana ASR runtime onlara dosya/JSON tabanlı subprocess çağrısıyla konuşur. Bu MITAS için kalıcı mimari desendir.
- **2026-05-11 / 6 — FFmpeg full-shared geçişi**
  - Karar: Gyan static FFmpeg yerine full-shared build kurulur. Torchcodec native decode bu geçişle anlamlı çalışır hale gelir.
- **2026-05-11 / 7 — DeepFilterNet için ayrı denoise venv**
  - Karar: DeepFilterNet asr venv'den ayrılır. Yeni `E:\MITAS\venvs\denoise` venv'inde numpy<2 ile yaşar. asr pipeline çağrıyı subprocess sleeve ile yapar.
- **2026-05-11 / 8 — large-v3 cache stratejisinin uygulanması**
  - Karar: `MITAS_ASR_Model_Cache_NoInternet_Strategy_v1.md` dokümanındaki strateji uygulanır. Model `models/asr/faster-whisper/` altına çekilir, sonraki çağrılarda internet trafiği oluşmaz.

Her giriş için: karar / gerekçe / referans / durum alanları doldurulur.

**Açık konular bölümünde** (`§ Açık (karar bekleyen) konular`):
- O1 askıdaki (demo backend venv stratejisi) öyle kalsın.
- O3 (pyannote v0.1 sprintine giriyor mu) için not ekle: "Torchcodec sorunu hazırlık çalışmasında çözüldüğünde yeniden değerlendirilecek (bkz. 2026-05-11 / 6)."

**Doğrulama:** Geliştirici dosyayı gözden geçirir, "tamam" der.

**Çıktı:** Güncellenmiş `06_KARARLAR_GUNLUGU.md`.
**Commit mesajı:** `proje_takip: kararlar günlüğü +6 (FFmpeg/denoise/alignment/large-v3)`

---

### 4.2 ADIM 2 — FFmpeg full-shared build kurulumu

**Amaç:** Gyan static build yerine full-shared build kurmak; avutil / avcodec / avformat shared DLL'lerinin PATH'te görünmesini sağlamak (torchcodec'in beklediği yapı).

**Yapılacak:**

1. Mevcut FFmpeg konumunu tespit et: `where ffmpeg`, `ffmpeg -version`. Sonucu raporla.
2. Gyan'ın **shared** sürümünü indir: https://www.gyan.dev/ffmpeg/builds/ → `ffmpeg-release-full-shared` linki. Versiyon: mevcut static ile aynı majör (8.x), shared flavor.
3. Yeni FFmpeg'i temiz bir dizine aç. Önerilen: `E:\tools\ffmpeg-shared\`. **Geliştiriciye konum onayı sor.**
4. Eski FFmpeg'in PATH girişini çıkar. Yeni `bin/` dizinini PATH'e ekle. **User PATH mi sistem PATH mi olduğunu geliştiriciye sor.**
5. Yeni shell aç. Şu üçünü doğrula:
   - `where ffmpeg` → tek satır, yeni konumu döner.
   - `ffmpeg -version` → shared lib bayrakları görünür (`--enable-shared`).
   - `where avutil-*.dll` veya benzeri komutla shared DLL'lerin PATH'ten erişilebildiği doğrulanır.

**Doğrulama:** Geliştirici yukarıdaki üç komutu kendi terminalinde koşar, sonuçları paylaşır.

**Risk:** Eski FFmpeg PATH'ten temizlenmeden yeni shell açılırsa iki ffmpeg yarışır. Bu adım yarım bırakılmaz.

**Çıktı:** `outputs/ffmpeg_shared_install_report.json` — eski konum, yeni konum, versiyon, build flavor, PATH durumu, shared DLL listesi.

**Commit mesajı:** `infra: ffmpeg full-shared geçişi tamam`

---

### 4.3 ADIM 3 — Torchcodec decode testi

**Amaç:** Adım 2'de kurulan shared FFmpeg ile torchcodec'in iki venv'de de native decode yapabildiğini doğrulamak.

**Yapılacak:**

1. Geliştiriciden 5-10 saniyelik bir test wav al (TRT olmasına gerek yok; net konuşma içeren herhangi bir wav). Konum: `samples/torchcodec_smoke.wav`.
2. asr venv'de minik bir Python betiği çalıştır: `torchcodec.decoders.AudioDecoder` ile wav decode et, shape ve sample_rate yazdır. Kesin API'yı torchcodec 0.11.1 dokümanından doğrula.
3. Aynı testi alignment venv'de tekrarla.
4. Hata varsa **dur, raporla.** Onaysız downgrade/upgrade yapma.

**Doğrulama:** İki venv'de de hata yok, decode çalışıyor, shape ve sample_rate doğru yazdırılıyor.

**Çıktı:**
- `outputs/torchcodec_smoke_asr.json`
- `outputs/torchcodec_smoke_alignment.json`

Her dosya: import durumu, decode başarısı, shape, sample_rate, çalışma süresi.

**Commit mesajı:** `infra: torchcodec decode smoke yeşil (asr + alignment)`

---

### 4.4 ADIM 4 — Denoise venv kurulumu

**Amaç:** DeepFilterNet'in numpy<2 ile yaşadığı izole bir venv açmak. asr venv'e dokunmadan dependency çatışmasını çözmek.

**Yapılacak:**

1. Python sürümünü seç. DeepFilterNet 0.5.6 en stabil olarak Python 3.10 veya 3.11. **Geliştiriciye hangisi olsun diye sor.**
2. `E:\MITAS\venvs\denoise` venv'i oluştur.
3. Kurulum sırası:
   - `numpy<2.0` (özellikle 1.26.x)
   - DeepFilterNet'in talep ettiği torch (sürüm seçiminden önce **mutlaka raporla**, geliştirici onaylasın)
   - `deepfilternet==0.5.6`
   - `soundfile`, gerekiyorsa `librosa`
4. Kurulum sonrası:
   - `pip freeze` → `locks/denoise.freeze.txt`
   - inspect JSON → `locks/denoise.inspect.json` (mevcut `scripts/inspect_model_envs.py` veya `scripts/lock_and_check_envs.py` kullan; yeni script yazma)
   - `pip check` → temiz çıkış doğrula
5. Smoke: gürültülü bir wav (geliştirici verir veya synthetic gürültü inject) → denoised wav döner. Çalışma süresi raporlanır.

**Doğrulama:** Geliştirici denoised wav'ı inceler (dinler veya spektrumla kontrol eder).

**Çıktı:**
- `locks/denoise.freeze.txt`
- `locks/denoise.inspect.json`
- `outputs/denoise_venv_install_report.json`
- `outputs/denoise_smoke_report.json`

**Commit mesajı:** `infra: denoise venv kuruldu, DeepFilterNet smoke yeşil`

---

### 4.5 ADIM 5 — Alignment venv WhisperX smoke

**Amaç:** Alignment venv'inde WhisperX'in word-level alignment ürettiğini doğrulamak. Subprocess sleeve IPC kontratını prova etmek.

**Yapılacak:**

1. Test wav + faster-whisper'dan üretilmiş segment-level transcript JSON'u hazırla. Transcript asr venv'de küçük bir wrapper ile üretilebilir.
2. Alignment venv'de WhisperX'i import et, word-level alignment koştur.
3. Çıktı JSON: her segment için word-level start/end ile.
4. IPC kontrat prototipi:
   - Input: wav path + segments JSON path (argv veya stdin)
   - Output: aligned JSON (stdout veya path)
   - Bu script `scripts/alignment_subprocess.py` olarak konur.
   - **Önemli:** Bu script production kodu değil, sadece v0.1 sprintinde baz alınacak bir prototip. Sade tut, fancy abstraction yok.

**Doğrulama:** Word-level timestamp'ler segment sınırlarını aşmaz, drift makul.

**Çıktı:**
- `outputs/alignment_whisperx_smoke.json` — başarı, word sayısı, ortalama drift, çalışma süresi
- `scripts/alignment_subprocess.py` — IPC prototipi

**Commit mesajı:** `infra: alignment venv WhisperX word-level smoke yeşil + ipc prototype`

---

### 4.6 ADIM 6 — large-v3 modelini indirme

**Amaç:** faster-whisper large-v3 modelini `models/asr/faster-whisper/` altına yerleştirmek; sonraki transcribe çağrılarında internet trafiği oluşmadığını garantilemek.

**Yapılacak:**

1. `docs/MITAS_ASR_Model_Cache_NoInternet_Strategy_v1.md` dokümanını oku, stratejiye uy. Stratejide belirsizlik varsa **geliştiriciye sor.**
2. Modeli indir. Hedef konum: stratejinin söylediği yer (muhtemelen `models/asr/faster-whisper/large-v3/`).
3. asr venv'de mini offline smoke:
   - 10-30 saniyelik wav alınır
   - `WhisperModel("large-v3", device="cuda", download_root="<path>")` veya stratejinin önerdiği şekilde lokal path'ten yüklenir
   - **Network monitor:** Yükleme sırasında ağ trafiği olmadığı doğrulanır (Windows Resource Monitor veya `netstat` / Process Monitor).
4. Transcribe çıktısı log'a yazılır. Bu kalite testi değil, "model lokal yüklenip çalışıyor mu" doğrulamasıdır.

**Doğrulama:** Model lokalden yükleniyor, ağ trafiği yok, transcribe sonuç dönüyor.

**Çıktı:**
- `outputs/large_v3_download_report.json` — model boyutu, hash (varsa), indirme süresi, lokal path
- `outputs/large_v3_offline_smoke.json` — transcribe başarı, çalışma süresi, network trafiği durumu

**Commit mesajı:** `infra: large-v3 model cache + offline transcribe smoke yeşil`

---

### 4.7 ADIM 7 — Sprint öncesi checkpoint

**Amaç:** Önceki altı adım yeşilse v0.1 sprintine geçilebilir durumdadır; bu durumu kayda al.

**Yapılacak:**

1. `_proje_takip/03_GUNCEL_DURUM.md` güncellenir:
   - §3 venv envanteri tablosuna `denoise` satırı eklenir.
   - §4 Sistem araçları'nda FFmpeg satırı "shared build" olarak güncellenir.
   - §10 Şimdiki adım netleştirilir: "v0.1 ASR pipeline kodlamaya hazır."
2. `_proje_takip/05_AKTIF_GOREV.md` güncellenir:
   - §3 açık kararlar (3.1, 3.2 vb.) ✅ işaretlenir.
   - §4.1 sprint öncesi adımlar ✅ işaretlenir.
3. Bir sprint hazırlık raporu yaz: `docs/SPRINT_PRE_4_ASR_V0_1_PREP_DONE.md`
   - Bu brief'in nasıl uygulandığını, hangi sürpriz çıktığını, hangi karar revize edildiğini içerir.
   - Diğer SPRINT_*_DONE.md dosyalarının formatına benzer tut.

**Doğrulama:** Geliştirici checkpoint dosyalarını inceler, "tamam" der.

**Çıktı:** Güncellenmiş takip dosyaları + sprint hazırlık raporu.

**Commit mesajı:** `proje_takip: v0.1 hazırlık tamam, sprint kodlamaya hazır`

---

## 5. ÜRETİLECEK ÇIKTILAR (TOPLU LİSTE)

Bu görev bittiğinde aşağıdaki dosyalar mevcut olmalı:

**Lock dosyaları:**
- `locks/denoise.freeze.txt`
- `locks/denoise.inspect.json`

**Outputs (audit kaydı):**
- `outputs/ffmpeg_shared_install_report.json`
- `outputs/torchcodec_smoke_asr.json`
- `outputs/torchcodec_smoke_alignment.json`
- `outputs/denoise_venv_install_report.json`
- `outputs/denoise_smoke_report.json`
- `outputs/alignment_whisperx_smoke.json`
- `outputs/large_v3_download_report.json`
- `outputs/large_v3_offline_smoke.json`

**Scripts:**
- `scripts/alignment_subprocess.py` (IPC prototipi)

**Docs:**
- `docs/SPRINT_PRE_4_ASR_V0_1_PREP_DONE.md`

**Takip dosyaları (güncellenmiş):**
- `_proje_takip/03_GUNCEL_DURUM.md`
- `_proje_takip/05_AKTIF_GOREV.md`
- `_proje_takip/06_KARARLAR_GUNLUGU.md`

**Yeni venv:**
- `E:\MITAS\venvs\denoise\`

**Yeni model cache:**
- `E:\MITAS\models\asr\faster-whisper\large-v3\` (veya strateji dokümanının önerdiği path)

---

## 6. BİTİRME KRİTERİ

Görev "tamam" sayılır ancak ve ancak:

- [ ] Yedi adım da hatasız geçmiş, çıktı dosyaları üretilmiş.
- [ ] asr venv'in `pip freeze`'i bu görev öncesinden 1:1 aynı. Manuel kontrol edilir (`diff` yap).
- [ ] Yeni denoise venv'in kendi lock dosyaları var.
- [ ] FFmpeg shared build PATH'te tek görünüyor; eski static PATH'ten kalkmış.
- [ ] Torchcodec asr ve alignment venv'inde hatasız decode yapıyor.
- [ ] large-v3 modeli lokalde mevcut; transcribe sırasında ağ trafiği yok.
- [ ] Kararlar Günlüğü'nde altı yeni karar yer alıyor.
- [ ] Sprint hazırlık raporu yazılmış.
- [ ] Geliştirici bütününe "tamam" demiş.

Yukarıdakilerden biri tutmazsa görev kapanmaz. **"Çoğunlukla çalışıyor" kabul değildir.**

---

## 7. TIKANDIĞINDA NE YAPARSIN

`02_CALISMA_DISIPLINI.md §2` der: "Bir kavşakta tıkanıldıysa 10-15 dakika çekil, sonra dön. Israrla aynı duvara vurmak zaman kaybıdır."

Sen LLM olarak yürüyüşe çıkamazsın, ama:

1. **Dur.** Aynı komutu farklı flag'lerle 5+ kez denemek tıkanmadır.
2. **Geliştiriciye net biçimde sor.** Hata mesajı, son komut, beklenen sonuç, gerçek sonuç. Tahmin yürütme.
3. **Plan dışı çözüm önerme.** Eğer çözüm bu brief'in dışına çıkıyorsa, **uygulamadan önce** geliştirici onayı al. Onay alınca Kararlar Günlüğü'ne ek bir karar girişi düşür.
4. **Geri çekilme kabul et.** Eğer bir adım gerçekten çalışmıyorsa, o adımı yarım bırakmak yerine geliştirici ile yeni karar al.

Hatırlatma: **"sonra çözeriz" felsefesi bu projede yok.** Bir kaçınma planı önerme.

---

## 8. SON HATIRLATMA

- Bu brief'i hazırlayan: Claude (web).
- Dayanağı: `_proje_takip/` klasörü + master plan v5.
- Brief'in dışına çıkmak için: geliştirici onayı + Kararlar Günlüğü kaydı şart.

Hoş geldin Codex. İlk işin: §0'daki altı dosyayı oku. Sonra geliştiriciye "okudum, hazırım" de. Sonra Adım 1'e ne zaman başlamak istediğini sor.

İyi çalışmalar.
