# MITAS GENEL DEĞERLENDİRME — 2026-06-10

26 ajanlı çok-katmanlı denetim: 7 alt sistem paralel incelendi (ASR, OCR/jenerik, künye+QC, özet, sunucu/UI, kod kalitesi, mimari), 18 kritik/yüksek bulgu bağımsız ajanlarca çapraz doğrulandı, sonda kapsam eleştirmeni koştu. Toplam 68 sorun, 47 iyileştirme önerisi, 40 eklenti fikri.

---

## 1. GENEL DURUM

Sistem **çalışıyor ve olgunlaşmış**: uçtan uca akış (ÇÖZ → OCR∥ASR → künye-metin → VL-fallback → özet+PDF → v4 final → qwen-QC → ONAYLI/KONTROL) blok-bazlı fail-safe kurgulanmış, atomik JSON yazımı + watchdog + oto-retry ile dayanıklılık iyi, "yanlış > boş" disiplini kodda gerçekten uygulanıyor. Ölçülen hız: medyan ~450 sn/film (~8 film/saat, seri).

Ana zayıflık deseni: **güvenlik ağları tek tek sağlam ama aralarındaki dikişler açık.** Üç sistem aynı kararı üç farklı kuralla veriyor (kademe), yarım kalan iş sessizce kopyalanıyor (idempotency), tek-nokta arızalar (ollama, Gemini, disk) alarm üretmeden topluca Kontrol'e akıtıyor, ve üretim zincirinin regresyon testi fiilen sıfır.

---

## 2. EN KRİTİK SORUNLAR (çapraz doğrulanmış)

### S1. Disk tükenmesi — 500-film gece koşusu E:'yi doldurur ⚠️ EN ACİL
E:'de ~91 GB boş; Database hub'ı film başına ~425–790 MB bırakıyor (frames/ ~85MB + audio16k.wav ~169MB + _asr_16k.wav ~169MB) ve **hiç temizlenmiyor**. 500 film ≈ 210–350 GB ister → gece yarısı disk dolar, batch kırılır.
**Fix:** film-sonu hub temizliği (karar verildikten sonra frames+wav sil; kunye.txt/transcript/pdf/_DURUM kalsın) + worker'a film-öncesi "boş alan < 20GB → kuyruğu duraklat" kapısı. Bonus: audio16k.wav çift çıkarımı zaten gereksiz (auto-language film/dizi'de ÇÖZ'ün extract_audio'su hiç kullanılmıyor, `mitas_pipeline.py:656`).

### S2. ONAYLI kapısında ana_dil=TR ve MÜZİKAL kuralı YOK — kademe tutarsızlığı
KANUN'daki F1 (KESİN=ana_dil TR) ve D4 (müzikal dışlama) kuralları gece-nöbetçisi `fix_kunye.py:341-347`'de var ama **canlı pipeline'ın ONAYLI kararında yok** — iki sistem birbirinin kararını geri alabiliyor. Üç ayrı yerde üç ayrı kural seti (mitas_pipeline, fix_kunye, 102 batch'leri).
**Fix:** tek `kunye_tier.py` modülü — ONAYLI/KONTROL/SES_TEYIT kararı tek fonksiyonda, herkes onu çağırsın.

### S3. Idempotency kırığı: yarım kalan film `_2/_3` kopya klasör üretiyor
`mitas_pipeline.py:612-614` clip-id soneklemesi + `_DURUM.json` yalnız koşu SONUNDA yazılıyor. Kill/restart'ta base klasör _DURUM'suz kalır; reused-skip (`asr_server.py:633`) ve retry-sil (`asr_server.py:884`) **yalnız base'e bakar** → her yeniden deneme `<clip>_2/_3` açar = tam yeniden işleme + disk şişmesi + bayat kopyalar (teslim köklerinde YALANCI_YALANCI_2 örneği mevcut). 2026-06-06 denetiminin "D3 en sinsi risk" maddesi hâlâ açık.
**Fix:** koşu başında "running" durum dosyası yaz; varsa-yarımsa sil-ve-yeniden-kullan; reused-skip/retry glob ile `<clip>_*`'ı da kapsasın.

### S4. Restart orphan + çift-koşu: start_mitas yalnız uvicorn'u öldürüyor
In-flight `mitas_pipeline.py` alt-süreci yetim devam ediyor; startup reconcile aynı filmi ikinci kez başlatabiliyor → aynı GPU'da iki pipeline yarışı + eski-env'le biten orphan (GLM-timing vakasında yaşandı).
**Fix:** flow worker çocuk PID'ini diske yaz, start_mitas + startup handler PID ağacını taskkill /T ile temizlesin; veya "drain" modu (mevcut film bitince restart).

### S5. Ollama tek-nokta arızası → sessiz toplu bozulma
Künye-metin (qwen3) + VL-fallback (qwen2.5vl/gemma4) + qwen final-QC hepsi 11434'e bağlı. Servis ölürse her film "fail-safe" atlanır ama sonuç = **tüm batch zayıf künyeyle Kontrol'e akar, hiçbir alarm yok**, sabaha kadar kimse fark etmez.
**Fix:** flow worker'a batch sağlık kapısı ("ardışık N film Kontrol/failed → kuyruğu durdur + healthcheck + alarm eventi") + watchdog'a 11434 healthcheck + ollama-restart adımı.

### S6. Özet zinciri fiilen tek-ayak: Gemini 429 "billing" substring tuzağı
Anthropic+DeepSeek kredisiz → zincir Gemini free-tier'a yaslanıyor; `_gemini.py` 429 gövdesindeki "billing/quota" kelimesini **KALICI hata** sayıp retry'ı iptal ediyor. Büyük batch'te rate-limit → placeholder özet kaskadı → qwen-QC "özet yok" → zincirleme Kontrol yağmuru.
**Fix:** 429'u her zaman geçici say, yanıttaki retryDelay'i oku, tur-backoff'unu ≥60s yap; api_status.json'u zincir-öncesi okuyup ölü sağlayıcıyı atla.

### S7. Üretim zinciri test kapsamı fiilen sıfır + CI ölü
Güncel künye zincirinin (mitas_pipeline → tek_film_kunye → credit_*) regresyon testi yok; ci.yml bayat ve git remote olmadığı için **hiç koşmuyor**. "43/43 sorunlu" tipi sürprizlerin kök nedeni bu.
**Fix:** 10-15 filmlik golden-set (OCR metni+XML → beklenen yön/cast/yapımcı) ile LLM'siz deterministik katmanı pytest'e bağla; remote yoksa pre-commit/pre-push hook'una taşı.

### S8. Künye QC'de kalan sızıntı delikleri (doğrulanmış)
- **Yapımcı-garble** (ÇANAKKALE/C3 sınıfı): KB yapımcı boşken QC2 temizliği no-op, final kapıda deterministik garble kontrolü yok → hâlâ sızabilir.
- **QC2-web title-only kilit**: TMDB çapası yıl yokken salt başlıkla kilitleniyor → remake/aynı-ad filmde yanlış-film kimliği ONAYLI'ya taşınabilir. Fix: kilit için ≥1 bağımsız örtüşme şartı (OCR yönetmen veya cast ismi).
- **'—' placeholder** yönetmen kırmızı-çizgi kapısını deldiriyor (yön+yapımcı ikisi boşken).
- **Çift-yönetmen** tüm yollarda 1'e kırpılıyor; **seri/üçleme** karışması (KRAL OİDİPUS) için mekanizma yok — film-özel-KB cross-check (STRATEJI_KUNYE_SABAH Aşama 1) ikisini de kapsamalı.

### S9. API fiilen LAN'a açık + sembolik kimlik doğrulama
Şifre kapısı "_61 ile biten her şey"; vite `host: true` ile 5173 proxy'si tüm API'yi (dosya-sistemi gezgini dahil) LAN'a açıyor. Kurum ağında risk.
**Fix:** gerçek parola karşılaştırması (MITAS_ACCESS_SECRET zaten var) + host:true'yu kaldır/kısıtla.

### S10. Üretim kodu commit'siz çalışıyor (stale-tree bombası)
`tek_film_kunye.py` working-tree'de +21 satır (FIX-1 credit-cümle filtresi + ozet cap değişikliği) — üretimde CANLI ama git'te yok. Koşu ortasında herhangi bir git işlemi davranışı sessizce değiştirir.
**Fix:** doğrula ve commit'le (bilinen stale-working-tree tuzağının tam tarifi).

---

## 3. ALT SİSTEM KARNESİ

| Alt sistem | Durum | En önemli açık |
|---|---|---|
| ASR | 🟢 Sağlam | Lean modda kalite/confidence sinyali sıfır (avg_logprob atılıyor); LID çökerse sessiz 'tr' varsayımı; transcript iterasyon-içi crash'te sıfır çıktı (kademeli flush yok) |
| OCR/jenerik | 🟢 Katmanlı, disiplinli | Üretim fiilen TEK-MOTOR (GLM default kapalı — kapatma nedeni kalite değil zamanlamaydı); stroke_px okunabilirlik kapısı koda hiç bağlanmamış; dizi "tam kadro" 8-cast tavanına takılı |
| Künye+QC | 🟡 Çok katmanlı ama dikişler açık | S2/S8 — kademe tutarsızlığı + garble/yanlış-film sızıntı delikleri |
| Özet | 🟡 Mimari iyi, tek-ayak | S6 + spoiler-final zorunlu ama transcript-grounding doğrulaması yok (HIRSIZ sınıfı) + kazanan sağlayıcı loglanmıyor (event hep "Sonnet" diyor) |
| Sunucu/UI | 🟡 Tek-operatör için tutarlı | S4/S9 + PUT /api/flow-queue tam-değiştirme (başka kaynağın öğesi sessizce silinir) + ilerleme yüzdesi sentetik |
| Kod/repo | 🔴 En zayıf alan | S7/S10 + 85 env değişkeni (29'u dokümansız) + 218 dosyada hardcoded path + 10 farklı fold()/tr_upper kopyası + kök README yok, 139 scratch girdisi |
| Mimari | 🟡 Seri tasarım bilinçli | S1/S3/S4/S5 + aşama-bazlı resume yok (clip.json modules.status yazılıyor ama HİÇ okunmuyor) |

---

## 4. GELİŞTİRME ÖNERİLERİ (öncelik sırasıyla)

**Hemen (1-2 gün, gece koşularını güvenceye alır):**
1. Hub temizliği + disk kapısı (S1)
2. Gemini 429 fix + sağlayıcı-atla (S6)
3. Batch sağlık kapısı + ollama healthcheck (S5)
4. FIX-1 + tek_film_kunye commit (S10)
5. clip_id resume-veya-sil (S3)

**Kısa vade (1-2 hafta):**
6. `kunye_tier.py` — tek kademe-karar modülü (S2)
7. Yapımcı-garble final son-kemeri + QC2 ikinci-çapa şartı (S8)
8. Orphan-kill / drain modu (S4)
9. Künye golden-set regresyon testi + pre-commit (S7)
10. Lean ASR'a kalite kapısı: evaluate_segment zaten hazır (`core/pipelines/asr/quality.py`), `_pipe_asr` döngüsüne takmak ek maliyet sıfır — ASR güveni KESIN/KONTROL kararına girsin (şu an kademe ASR tarafına kör)
11. Aşama-bazlı resume: "ocr=done ise atla, asr'den devam" — 62 saatlik batch'te kesinti maliyetini çökertir
12. Otomatik gece yedeği: export ONAYLI/KONTROL + _DURUM'ları G:'ye robocopy (G:'de 730GB boş; onaylı PDF'lerdeki insan-QC emeği şu an yalnız E:'de)
13. GLM ikinci motoru zamanlama-güvenli geri getir (düşük kare tavanı + timeout) veya hafif PaddleOCR — tek-motor drift kapanır
14. ENV_VARS.md + SCRIPT_INVENTORY.md güncelle, kök README.md yaz (mimari bilgi şu an repoda değil, asistan memory'sinde yaşıyor)

**Orta vade:**
15. CPU/GPU pipelining: film N'in ASR'ı koşarken film N+1'in ffmpeg+OneOCR'ını önden hazırla — 2-paralel revert'inin güvenli alternatifi, ~%20-30 hız
16. v4 çift-render israfını kaldır (film/dizi'de ilk render zaten eziliyor, ~50-100s/film)
17. fold()/tr_upper ailesini tek kanonik modüle indir; path sabitlerini `_paths.py`'a topla
18. Film timeout'u süreye orantılı (sabit 4 saat yerine ffprobe×katsayı)
19. Gerçek ilerleme telemetrisi + stall göstergesi (yüzde şu an sentetik)
20. system_events tarihli arşiv rotasyonu (şu an 5MB'da eski yedek SİLİNİYOR — uzun batch'te veri kaybı)

---

## 5. EKLENEBİLECEK YENİ YETENEKLER

**Ürün değeri en yüksek (kör noktalar — hiçbir alt sistemde yok):**
- **SRT/VTT zaman-kodlu altyazı çıktısı**: repo'da tek .srt üreticisi yok; timestamps lean çıktıda zaten var — ASR ürünlerinin sektörde birincil teslim formu bir dönüştürücü kadar uzakta
- **Makine-okur künye teslimi (MAM round-trip)**: tek teslim artefaktı insan-okur PDF; kadro/özet/dil metadata'sının XML sidecar/JSON olarak Tedial-arşive geri-yazımı yok — arşiv ürünü için asıl değer noktası
- **Transkript-içi arama/keşif**: Database'de yüzlerce transcript+OCR birikti, duckDB erişilebilir — "bu replik/isim hangi filmde" sorusunu yanıtlayan indeks yok
- **İşlem geçmişi + istatistik paneli**: ONAYLI/KONTROL oranı, aşama-süre persentilleri, başarısızlık dağılımı — veri zaten system_events+_DURUM'da, sadece agregasyon+UI sekmesi gerek
- **Bildirim kanalı**: batch bitti / failed eşiği aşıldı / worker düştü → Telegram/e-posta/toast (watchdog'a eklemek en ucuz yol)

**Künye kalitesini büyütecekler:**
- Üst-billing doğrulama kapısı (TMDB principals ilk-5 ↔ PDF cast; başrol eksikse uyarı)
- Export-sonrası sürekli nöbet: garble_audit.py'yi zamanlanmış göreve bağla, her gece ONAYLI'yı tara
- Yüz tanıma: planı zaten yazılmış rafta duruyor (`docs/MITAS_v0_4_Face_Recognition_Plan_Final.md`) — OCR-garble vakalarında doğal ikinci kanıt kanalı
- Jenerik sınır tespiti: OCR penceresi sabit 180s baş+240s son; geç-jenerikli filmde kadro pencere dışında kalıyor — CLIP skorlu dinamik pencere
- Kanal-logo tespiti + ekrandan bölüm-no okuma (bölüm şu an yalnız dosya-adı regex'i)
- Hotword/özel sözlük: XML başlık+oyuncu adlarını faster-whisper hotwords'e ver → özel-isim doğruluğu

**Özet kalitesi:**
- Özet güven skoru / final-grounding: son cümledeki iddiaların transcript-tail örtüşmesi; düşükse "final doğrulanamadı" → KONTROL (HIRSIZ dersi production'a iner)
- ozet_film.txt'e spoiler istisnası: "transcript finali vermiyorsa kesin hüküm uydurma"
- TÜR/dönem tespiti yan-ürünü (özet çağrısına JSON yan-alan — TÜR dolgusu KB'siz çözülür) + içerik uyarıları (yayın-kuşağı planlaması için)
- Gemini Batch API / context-caching (500-film koşusunda kota baskısını düşürür)

**Teknik medya-QC sınıfı (arşiv-standart, hiç yok):**
- Sahne tespiti, siyah/donmuş kare, ses kaybı, loudness (EBU R128); `tools/audfprint` repo'da duruyor ama hiçbir akışa bağlı değil (müzikal/dublaj tespitinde kullanılabilirdi)

---

## 6. KÖR NOKTALAR (kapsam eleştirmeninden)

1. **Üç paralel teslim kökü**: `dagitim\`, `teslimat\`, `Mitas Output\export` yan yana dolu — kanonik hangisi belirsiz, bayat kümeden yanlış teslim riski. Tek kanonik kök seç, diğerlerini ARŞİV olarak işaretle/dondur.
2. **Tedial alt sistemi (8765)** bu denetimde fiilen incelenmedi; bilinen açık bug duruyor (bayat cookie'de "Bağlan" login göstermeden sekiyor) + şifre-rotasyon kırılganlığı.
3. **Çeviri (MT) katmanı görünmez**: `core\pipelines\translate\` + `/api/translate/segments` endpoint'i + venvs\translate var ama canlı mı ölü mü belirsiz — karar verilip ya akışa bağlanmalı ya emekli edilmeli.
4. **model2\ (panorama-first) + BoxTracking/SlitScan POC mirası** sahipsiz; karşılaştırma kararı (`docs\MITAS_OCR_MODELS_Comparison_Plan.md`) açık mı kapalı mı belirsiz.
5. **core\jobs + schemas\ + benchmark altyapısı**: flow-queue'dan ayrı ikinci (eski) iş mimarisi — bugün yalnız Tedial kullanıyor; ölü/canlı haritası çıkarılmalı.

---

*Denetim künyesi: 26 ajan, 557 araç çağrısı, ~25 dk; kritik/yüksek bulguların tamamı bağımsız çürütme-ajanlarınca koda karşı doğrulandı (3'ünün severity'si düşürüldü, hiçbiri çürümedi).*
