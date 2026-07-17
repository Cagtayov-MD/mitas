# GECE PROGRAMI — SABAH KARAR RAPORU (2026-07-06)

Talimat: "1-2-3 yap test et 3-5 filmde, sonra kontrollü şekilde 4'ü inşa et (konsey önerileriyle,
getiriyi hesapla), hepsi bitince 5 için SADECE PLAN — sabaha karar veririz."

---

## BÖLÜM A — HIZ 1-2-3: YAPILDI + CANLI KANIT

### #1 Havuz-paralel (CANLI, hakem-onaylı + v2 kök-kazı)
- Jenerik havuzları (`_jenerik_pool` + `giris_jenerik_havuzu`) artık omurgayı BLOKLAMIYOR.
- **Giriş-havuzu**: coz-sonrası Popen, OCR∥ASR ile örtüşür. Kanıt: SON BOLŞEVİK bekleme **0.0 sn**
  (kept=33 rep=16), KİNG bekleme **0.01 sn**, OPERA **0.02 sn** (eski seri maliyet ~35 sn/film).
- **Çıkış-havuzu v2**: ilk sürüm (OCR∥ASR penceresinde spawn) 2 filmde child'ı ANINDA öldürdü
  (0439+0289; stdout/stderr 0 bayt = commit-tükenmesi/error-1455 ailesi — paddle'lı child ASR'ın
  CUDA/commit TEPESİNE binmişti). **Kök-kazı fixi**: lansman ASR-toplama SONRASINA taşındı →
  LLM/v4/pdf kuyruğuyla (~250 sn pencere) örtüşür; gemma-resident+havuz birlikteliği eski seride
  zaten kanıtlıydı. KİNG kanıtı: iş 54.5 sn GÖLGEDE, 234 frame, bekleme 17 sn.
- Bağımsız hakem denetimi: "bloklayıcı yok, canlıya alınabilir"; 2 önerisi uygulandı
  (stdout pipe→dosya: 8KB pipe tamponu child'ı rehin tutuyordu; yedek-havuz çağrı-dalı düzeltildi).
- Kill-switch: `MITAS_POOL_PARALLEL=0` → birebir eski sıralı davranış.

### #2+#3 Afiş-önbellek + web-ısıtma (CANLI, tek mekanizma)
- `scripts/web_cache.py`: URL-düzeyi disk önbelleği (sha1-anahtar, atomik yazım, 6 saat TTL,
  yalnız başarılı yanıt) — kimlik/afiş KARAR MANTIĞI DEĞİŞMEDİ, yalnız HTTP yanıtı diskten döner.
- `scripts/web_isit.py`: coz-sonrası ateşle-unut; TMDB/OMDb/Wikipedia/IMDb-suggestion kimlik+afiş
  sorgularını boş pencerede indirir. 3 tüketici yamalı: poster_fetch, credit_qc_gates.web_identity
  (QC2-web), credit_identity.
- Kanıt: gerçek başlıkla ısıtma 1.6 sn/6 URL; sahte-api-key testi 8 ms'de cache'ten döndü
  (network'e gitmediğinin ispatı). Her yeni filmde `web_isit_started` olayı akıyor.
- Kill-switch: `MITAS_WEB_ISIT=0`, `MITAS_WEB_CACHE=0`.

### Onarım listesi (gece eklenenler)
- 1993-0439 SON BOLŞEVİK + 1995-0289 ÜÇ KURUŞLUK OPERA: cikis_jenerik BOŞ (v2-öncesi vaka) →
  havuz-backfill veya yeniden-koşu.
- 1998-0401 BLACKJACK: düzenleme-anı hibriti KAZARA v2-lansman kanıtı oldu — ASR-SONRASI spawn
  edilen havuz-child YAŞADI ve havuzu doldurdu (108 PNG + manifest diskte; yalnız telemetri olayı
  eksik, kalite tam). ASR-penceresinde ölen 0439/0289'un karşı-kanıtı.
- 0439 ayrıca: `_jenerik_detect --parallel` 360 sn TIMEOUT (01:57 uzun film; ffmpeg-trio çekişme
  şüphesi — tekrar ederse timeout artır/ayrıştır; fail-safe çalıştı, PDF çıktı).

---

## BÖLÜM B — HIZ #4 FİLM-PIPELINING: KONSEY + ÖLÇÜM HÜKMÜ

- 4-üyeli Opus konseyi (Yaratıcı ∥ Muhafazakâr → Eleştirmen → Sentezci) koştu; şartname:
  `outputs/KONSEY_SARTNAME_FILM_PIPELINING_2026-07-05.md` ("ÇÖZ-PREFETCH, DAR KESİM": yalnız
  deterministik çıkış-extract+ses front'a alınır; KAPI-0 ölçüm kapısı ZORUNLU, D=yapma canlı sonuç).
- **KAPI-0 ölçümü (`scripts/pipelining_olcum.py`, salt-okur)**: 108 dk'lık gerçek filmde
  çıkış-extract 2.9 sn + ses 6.7 sn − giriş 1.7 sn → **örtülebilir pay ~5 sn/film** (eşik 45-60 sn).
  Dünkü ffmpeg-trio paraleli + NVMe extract işini zaten bitirmiş; coz'un 99 sn medyanını DETECT yiyor.
- **HÜKÜM: D — şartname gereği İNŞA EDİLMEDİ** (5 sn için pipeline karmaşıklığı alınmaz).
  Getiri hesabı: ~5 sn/film ≈ 100-film dalgada ~8 dk — maliyetine değmez.
- Konseyin ölümsüz kazanımları (Stage-2'ye devredildi): kill-tree 2-slot fixi, telemetri-interleave
  analizi (dalga_takip filename-bazlı → uyumlu), sentinel+byte-özdeşlik test protokolü, kuyruk-verimi
  ölçüm metodolojisi (T = son-done − ilk-running; film-başı duvar DEĞİL).

---

## BÖLÜM C — HIZ #5 STAGE-2 ÖN-ÇALIŞMA (SADECE PLAN — KARAR SENİN)

### Ne yapılacak
28 Haziran onaylı verim-planının 3. aşaması, BUGÜNKÜ gerçeklerle güncellenmiş hali:
**faz-bölme + tek-GPU semaforu**. Film N'in saf-CPU kuyruğu (v4/özet-ağ/pdf/master-compose/export)
koşarken, film N+1'in GPU-fazı (coz+OCR∥ASR) başlar. GPU izni "VRAM gerçekten boş" bariyerinde
(ollama `/api/ps` yoklaması, uyku DEĞİL) el değiştirir; `BoundedSemaphore(1)` GPU'da her an tek film.

### Bugünkü ölçülü profil (bu gecenin 12 filmi, system_events):
| Faz | Medyan | GPU? |
|---|---|---|
| coz (detect dahil) | 99 sn | detect CLIP=GPU |
| OCR∥ASR penceresi | 266 sn | ASR=GPU |
| kuyruk (LLM+v4+özet+pdf) | 127 sn | yalnız LLM-rol ~25-40 sn GPU |
| pdf-sonrası (master+export+done) | 126 sn | CPU |

**Örtülebilir CPU-pencere ≈ 210-220 sn/film** (kuyruğun CPU kısmı + pdf-sonrası).

### Kazanç tahmini (dürüst)
- N+1'in GPU-fazı N'in ~220 sn CPU-penceresine bindirilir → kuyruk-verimi kazancı **~%25-35**
  (650 sn → **~430-480 sn efektif ≈ 7.2-8.0 dk/film**). **İstediğin 7-8 dk bandına GİDEN YOL BU.**
- 100-film dalga: ~18 saat → ~12-13.5 saat (**~4.5-6 saat tasarruf**).
- Not: 28 Haziran'ın +%35-50'sinden düşük çünkü ödülün bir kısmı zaten hasat edildi
  (duckdb-yerel, jdebug-off, shadow-VL-off, bu gecenin 1-2-3'ü).

### Avantajlar
- Tek büyük kalan hız-kaldıracı; film-başı DEĞİL kuyruk-verimi kazandırır (dalga saati düşer).
- Konsey şartnamesinin güvenlik iskeleti hazır (2-slot kill, telemetri, sentinel, pilot protokolü).
- Tamamı bayrak-kapılı tasarlanır: `MITAS_STAGE2=0` → birebir bugünkü davranış.

### Dezavantajlar / Riskler (bu gecenin YENİ kanıtlarıyla)
1. **COMMIT-TAVANI (en büyük risk, bu gece canlı kanıtlı):** tavan 186 GB, gece boyu kullanılabilir
   2-3 GB'a düştü; 2 havuz-child'ı spawn-anında öldü (1455 ailesi). N+1'in ASR'ı (whisper CUDA,
   büyük commit) N'in kuyruğuna binince aynı rejim. **ÖN-KOŞUL: pagefile'ı E:'ye taşı/büyüt
   (E: 108 GB boş; REBOOT gerekir — dalga arasında, senin onayınla) + commit-bariyeri
   (kullanılabilir-commit < eşik → örtüşme o film için atlanır, seri düşer).**
2. İki filmin süreçleri eşzamanlı → Zorla-Durdur/kill-tree 2-slot fixi ŞART (konsey çözümü hazır).
3. Karmaşıklık: faz-bölme mitas_pipeline'a dokunur; pilot + byte-özdeşlik kapıları şart
   (konsey protokolü aynen uygulanır: 5-film BASELINE/PILOT, kalite=byte-özdeş artefaktlar,
   kazanç ≥%10 değilse geri-al).
4. VL-fallback %59 filmde 26b yüklüyor (LRU 31b'yi atar) → model-takas trafiği örtüşmede artabilir;
   bariyer ollama /api/ps ile bunu görür ama verimi törpüleyebilir.

### Önerilen adım sırası (onaylarsan)
0. Pagefile→E: (reboot'lu, dalga bitince) + commit-bariyeri kodu.
1. Konsey Adım-1 güvenlik fixi (2-slot kill-tree; pipelining'siz de değerli).
2. Faz-bölme + semafor + VRAM-bariyeri (hepsi `MITAS_STAGE2` bayrağı altında, default 0).
3. 5-film pilot (BASELINE/PILOT, kuyruk-verimi + byte-özdeşlik + sıfır-1455 kapıları).
4. 20-film gözlem → default açma kararı.

### Alternatif (daha küçük, daha ucuz)
- **Detect-front**: coz'un 99 sn medyanının çoğu detect (CLIP-GPU). Detect'i N'in kuyruğundaki
  GPU-boşluğuna almak ~60-90 sn/film kazandırır; Stage-2'nin alt-kümesi, daha az yüzey.
  Stage-2'ye girmeden önce tek başına da denenebilir (konsey "Faz-2 adayı" dedi, ayrı VRAM ölçümü ister).

---

## BÖLÜM D — GECE OLAYLARI (bilgi)
- **Eşzamanlı yan-yük:** D:\testas `pilot10_xml_to_pdf.py` (senin ayrı XML→PDF pilotun, sabah
  07:11'den beri) tüm gece ~2.4 çekirdek + 7.9 GB commit tüketerek koştu (canlı ve üretken —
  DOKUNULMADI; 23:20'de MARTI PDF'i çıkardı). Geceki süre-ölçümleri ve commit-sıkışmaları
  (detect-timeout, 1.3-2.0 GB dipler) bu yan-yükün gölgesinde okunmalı; kuyruk-verimi kıyası
  pilot bitince/sessiz pencerede tekrarlanmalı.
- llama-server (23-25 GB commit) iki kez "LM Studio kalıntısı" sanılıp öldürüldü — ebeveyn analizi
  gösterdi: **ollama'nın kendi model-runner'ı** (resident gemma). Ders hafızaya yazıldı; bekçi düzeltildi.
- Commit-bekçisi kuruldu (uyarı: kullanılabilir < 3 GB). Pagefile D:'de, büyüme payı ~22 GB.
- Dalga kesintisiz aktı; her film PDF üretti (fail-safe'ler çalıştı).

## BÖLÜM E — TAM-v2 UÇTAN UCA KANIT (SON CÜCE 1998-0519, 23:21 yerel)
- Olay imzası: `status=not_found frame=0 (LLM/v4-örtüşük, iş 164.16 sn, ek bekleme 0.0 sn)`.
- 164 sn'lik çıkış-havuz işi TAMAMEN kuyruk gölgesinde koştu; omurga maliyeti 0.0 sn
  (eski seri düzende bu film +164 sn bekleyecekti). 0-frame = dedektörün meşru hükmü
  ("No persistent credit text cluster" — 20 sn'de OCR/ASR'ı biten kısa/sessiz malzeme).
- Yan-kanıt: pool_stderr'de onnx "bad allocation" izleri (VL-fallback 26b yüklemesi anında commit
  sıkışması) → BÖLÜM C'deki pagefile→E: ön-koşulunu güçlendirir.

## BÖLÜM F — 1-2-3 CANLI TEST SONUCU (dürüst okuma)

**Mekanizma-kanıtı (KESİN, film-başına yapısal kazanç):**
- Jenerik havuzları: eski seri maliyet ~90 sn/film (çıkış ~55 + giriş ~35, taban ölçümlü)
  → şimdi ek bekleme 0.0-21 sn (7 filmde ölçüldü; uzun-metrajda ~0). Net ~70-90 sn/film.
- PUNKTCHEN (104dk, temiz tam-v2): çıkış-havuz status=found 350 frame, iş 61 sn GÖLGEDE,
  ek bekleme 0.03 sn — dolu-havuz + uzun-metraj kesin kanıtı.
- Web-ısıtma: v4'ün TMDB/OMDb/Wiki beklemeleri cache-hit (8 ms ölçüldü) → ~20-40 sn/film
  (afiş+kimlik+QC2-web toplamı, filmden filme değişir).

**Kohort medyanı (YÖN doğru ama karışım-gürültülü, n küçük):**
değişim-öncesi 43 film medyan 665 sn → sonrası 4 film medyan 381 sn. UYARI: sonrası kohortu
ağırlıkla ASR'ı-anında-düşen (sessiz/bozuk-ses) hızlı-yol filmlerine denk geldi; 665→381 farkının
tamamı 1-2-3'e ATFEDİLEMEZ. Güvenilir rakam = mekanizma-kanıtı (~90-130 sn/film) + sabah sakin
pencerede daha büyük n ile medyan.

**Gece yeni bulgusu — PUNKTCHEN ASR-timeout:** Almanca film, large-v3 yolu 3600 sn duvara vurdu
(0 segment; PDF fail-safe ile çıktı, özet yok). Valve 31b+26b'yi tahliye ediyor (kod doğrulandı);
asıl şüpheli ASR penceresindeki commit-dibi (00:05'te 2.0 GB). Yeniden-koşu listesine eklendi (8.).
Bu vaka pagefile→E: ön-koşulunu bir kez daha güçlendiriyor: gece boyunca 1455-ailesinin vurduğu
3. bağımsız yol (havuz-child spawn ölümü, onnx bad-allocation, şimdi CT2/whisper sürünmesi).


---

## BÖLÜM G — KRİTİK GECE VAKASI: ASR KİTLESEL BELLEK-ÖLÜMÜ + SÜBAP-FIXİ (01:50)

**Tespit:** 05/07 20:31'den itibaren (benim gece değişikliklerimden ÖNCE başlamış) **ardışık 14+ filmde
ASR bellek hatasıyla öldü** — MemoryError(numpy) / mkl_malloc / CUDA-OOM / WinError-1455 (BLACKJACK'te
açık kanıt) / "CUDA driver insufficient" (PUNKTCHEN 3600sn). Sonuç: bu filmler PDF aldı ama
TRANSKRİPT/ÖZET YOK → tümü Kontrol + yeniden-koşu adayı. Kök: commit-tavanı (186 GB) akşamdan beri
doygun; film-başına en büyük tahsisçi whisper/CT2 ilk kurban.

**Gece uygulanan fix (kod, geri-alınabilir):** ASR-sübabı HER DİLE genelleştirildi
(`_pipe_asr.py` — resident gemma'nın ~24 GB commit'i whisper yüklenmeden önce boşaltılır; eskiden
yalnız yabancı-dil dalında ateşleniyordu, Türkçe-turbo yolu korumasızdı). Bedel: film başına ~56 sn
model-geri-yükleme; kazanç: transkript+özet hattı yaşar (kalite > hız). Kill-switch:
`MITAS_ASR_LLM_VALVE=0`.

**Sabah aksiyonları:**
1. **Yeniden-koşu kapsamı BÜYÜDÜ:** 20:31'den fix-anına kadarki tüm asr_failed filmleri
   (≈15-16 adet; GECE_FIXLER listesindeki 8 ile birleşik küme) — dalga bitince topluca.
2. **Pagefile→E: kararı artık ACİL önem taşıyor** — bu vaka 1455-ailesinin 4. bağımsız kurbanı;
   sübap semptomu hafifletir, tavanı yalnız pagefile büyütmesi kalıcı çözer.
3. Sübap-sonrası ilk filmlerin ASR başarısı bu raporun altına işlenecek (bekçi kuruldu).

**Fix-2 (02:05):** Çocuk-içi sübap YETMEDİ (PAMUK MARY yine 13.8 sn'de öldü — CT2/CUDA DLL'leri
sübap satırına gelemeden import-anında ölüyor). **EBEVEYN ÖN-SÜBABI** eklendi: mitas_pipeline
ASR-Popen'dan önce LLM'i tahliye eder + commit-boş ≥8 GB olana dek bekler (maks 90 sn, telemetrili
`asr_pre_valve` olayı). Kill-switch: `MITAS_ASR_PRE_VALVE=0`. Sınav: bir sonraki filmin ASR'ı.

**SONUÇ (02:40): KANAMA DURDU ✓** — Ön-sübap ilk sınavında LLM-tahliyesi commit-boş'u
1.5→27.6 GB'a çıkardı (bekleme 0 sn) ve BUZDAN GELEN SESLER **asr_completed, 175 segment** aldı —
20:31'den beri ilk başarılı transkript (15 film aradan sonra). Transkript/özet hattı geri geldi.
Bedel: film başına ~50-60 sn LLM geri-yükleme (Stage-2 kararına kadar kabul; pagefile→E: sonrası
sübap eşiği gevşetilebilir veya keep_alive geri açılır — sabah kararıyla).

**Gözlem (03:15):** Ön-sübap sonrası commit "nefes deseni"nde tek kalan sıkışma penceresi =
kuyruk fazındaki VL-fallback model-değişimi (26b↔31b churn, filmlerin ~%59'u; 10-15 dk 0.1-1 GB'a
inip film bitince 16+ GB'a dönüyor). Filmler bu pencereyi fail-safe'lerle atlatıyor; kalıcı çare
pagefile→E:. ASR fix-sonrası skor: 2/2 başarılı (BUZDAN 175, TACİZ 1401 segment).


---

## BÖLÜM H — GECE-SONU SAYILARI (11:55, DALGA BİTTİ)

- **Dalga tamamlandı:** worker 11:18'de "bekleyen öge kalmadı (processed=142)" ile temiz çıktı;
  takipçi toplamı 173 film. Karar: **Hazır 17 / Kontrol 156** + export/ONAYLI_KISI_TEYIT **34 PDF** (retro).
- **ASR skoru (ön-sübap sonrası):** 51 başarılı / 24 başarısız. Sabaha karşı (06:00-08:00,
  V2S8/S9 serisi) İKİNCİ bir bellek-fail kümesi oluştu — yine MemoryError/mkl_malloc/CUDA-OOM;
  ön-sübap 90 sn bekleyip pes edince spawn etti (fail-safe gereği). Kalıcı doygunluğun tek çözümü
  pagefile — gece boyunca 5 bağımsız kurban-yolu kanıtlandı.
- **Çıkış-havuz v2:** 57 sağlıklı / 15 şüpheli-boş (şüpheliler büyük ölçüde bellek-sıkışma
  pencereleriyle çakışıyor; yeniden-koşuda dolacak).
- **Kontrol 156'nın büyük payı transkriptsiz filmler** (iki kanama penceresi ≈ 40 film) —
  yeniden-koşuda özet gelince önemli kısmı Hazır/ONAYLI'ya dönecek.

## KARAR MASASI (sabah — öncelik sırasıyla)
1. **PAGEFILE→E: + REBOOT — TAM ŞİMDİ İDEAL** (dalga bitti, makine boş; E:'de 108 GB yer).
   Gece 5 kurban-yolu: havuz-child spawn ölümü ×2, onnx bad-alloc, whisper 3600sn-timeout,
   2 ASR kanama-kümesi (~40 film).
2. **YENİDEN-KOŞU DALGASI** (reboot SONRASI): ~40 ASR-kurbanı + GECE_FIXLER 8'lik liste
   (kesişim var; kesin küme asr_failed-taramasıyla çıkarılır — komut hazır).
3. **Stage-2 inşa kararı** (Bölüm C planı: ~%25-35 kuyruk-verim, 7-8 dk bandı).
4. **keep_alive politikası:** pagefile sonrası ön-sübap eşiği gevşetilebilir veya keep_alive
   15m'e geri dönülebilir (şu an her ASR öncesi tahliye = +50-60 sn/film).


---

## BÖLÜM I — KONTROL-MAHKEMESİ + KAÇAK-FIX PAKETİ (13:10)

**Mahkeme (156/156 film, ajan-başına-yargıç + desen-sentezi):**
- **KAÇAK 62 (%40)** / MEŞRU 58 (%37: framede-yok 26, okunamadı 24, alfabe 4, çelişki 4) / ALTYAPI 36 (%23).

**Uygulanan fix paketi (hepsi anayasa-uyumlu: PDF'e yeni isim SOKMAZ, yalnız haksız Kontrol'ü kaldırır):**
1. **FIX-D — CAST_CAP karar-dışı** (~20 film): görünürlük sinyali karara sızmıştı; artık yalnız uyarı.
2. **FIX-C — özet-yok karar-dışı** (~7 film): künyeden bağımsız (sessiz-film/ASR-arıza işi);
   ÖZET-KUYRUK uyarısına dönüştü. Kill: MITAS_OZET_KONTROL=1.
3. **FIX-1 — KİŞİ-TEYİT KB-kapsama-farkındalık** (~15 film): oran artık "KB'nin BİLDİĞİ kişiler"
   üzerinden de hesaplanıyor (bilinen≥2 & bilinen-oran≥0.75); eski TR filmlerinde KB-boşluğu
   kişi-teyidi haksız düşürüyordu.
4. **FIX-2a/b/c — etiket-var-eşleşmedi zinciri** (~16 film):
   (a) kombine-etiket matcher ("PRODUCED, WRITTEN & DIRECTED BY" 24-kr tavanına takılıyordu; ±48kr
   token-bazlı, yan-ünite/asistan/dublaj vetolu, birim-test 10/10);
   (b) füzyonda ÇİFT-EKRAN-İMZA dalı: tek-model+KB-yok aday, kunye VE dilim-korpusta harfiyen
   geçiyorsa "ORTA (ekran-çift-imza)" ile girer (fabrikasyon frenı korunur: uydurma dilimde geçemez);
   (c) rol-atfı GLOBAL-BAĞIŞIKLIK: çok-şapkalı kişi (yön+yapımcı+DoP aynı kişi) diğer kartlarının
   komşuluğu yüzünden düşmez; dublaj geniş-pencere kuralı AYNEN korundu.
**KANIT:** CENNETE GELDİK Mİ yönetmen='Carl Caldana' (ekran-çift-imza) ✓.
**REGRESYON:** TILSIMLI dublaj-freni boş ✓ / HALIFAX=Ken Cameron değişmedi ✓ / BUZDAN=DALE JOHNSON ✓.

**Ek altyapı onarımı:** ollama sabah ÇÖKMÜŞTÜ ve ÖKSÜZ runner'ı (ebeveyni ölü llama-server, 08:57'den
beri 23.5GB commit + ~21GB VRAM sahipsiz) hem sabah kanamasının hem yeni 500-hatalarının köküydü →
öksüz temizlendi (VRAM 21.6→1.1GB), ollama yeniden başlatıldı (depo 12 model tam).

**Beklenen sonuç:** 156 Kontrol → fixli yeniden-koşuda ~58 meşru + küçük artık (≈%60+ azalma);
Hazır+ONAYLI havuzu ~17+34'ten ~110+ bandına.


## BÖLÜM J — FİXLİ YENİDEN-KOŞU KURULUMU (14:05, Çağatay onayı: "fixle. başla.")
- **Pagefile→E: (64-128GB) + D:-pagefile kaldırma**: UAC-onaylı yükseltilmiş betik; onay sonrası 60sn'de reboot.
- **Kickoff (logon'da otomatik, tek-sefer):** scripts/yeniden_kosu_kickoff.py — asr_server'ı bekler,
  ollama'yı garanti eder, YENIDEN_KOSU_LISTESI.json'daki **98 filmi** (KAÇAK 62 + ALTYAPI 36;
  MEŞRU 58 bilinçli hariç) kuyruğa ekler + autostart. Log: YENIDEN_KOSU_KICKOFF.log.
- **Nöbetçi-daemon (kalıcı, LLM'siz):** scripts/nobetci_daemon.py — logon'da başlar, 5dk döngü:
  worker-ölüm canlandırma (login+run), ollama-diriltme + öksüz-runner temizliği, commit izleme.
  Log: NOBETCI.log. Durdurma: NOBETCI.stop dosyası. (Claude-oturum kopmalarından BAĞIMSIZ —
  "loop gece durdu" sorununun kalıcı yaması.)
- **Ollama-bekçisi pipeline'da da CANLI** (llm_preflight_recovered olayı; kill: MITAS_OLLAMA_BEKCI=0).
- Beklenti: 98 fixli koşu ≈ 10-11 saat → Kontrol 156 → ~60 bandı (MEŞRU'lar), Hazır+ONAYLI ~110+.


## BÖLÜM K — DERİN-DENETİM (Çağatay şüphesi doğrulandı) + KOŞU 131'E GENİŞLEDİ (16:10)
- **"framede-yok 26" ZAYIF hükümmüş:** havuz/metin envanteri → yalnız 3 GERÇEK-BOŞ; 4'ünde havuz
  DOLU metin SIFIR (13. SAVAŞÇI: 476 PNG / 0 kr kunye!); 19'unda binlerce karakter metin var
  (yargıç paketin dar kesitinde etiket görememiş). 22 aday koşuya eklendi.
- **"okunamadı 24" röntgeni 5 alt-sınıf:** (i) FR/DE ana-etiket sözlük-eksiği — "MISE EN SCENE"
  (BAŞKAN VE MARI'de yönetmen apaçık!), REALISATION, REGIA DI, CO-REGIE → SÖZLÜĞE EKLENDİ
  (_RSC_DIRF + _TRUE_DIR_RE); (ii) yalnız asistan/DoP kartları okunmuş, ana kart kaçmış
  (AYAK TAKIMI=Ken Loach!); (iii) gerçek ağır-garble (OSCAR 'HABY FACE BARCIMI', TAKKELİ
  'DIRECTAR') → K2-VL tanık adayı; (iv) aslında ALFABE-BOZUK (NAMUS DÜŞMANI=Arapça-translit,
  SİBİRYADAN-2=Kiril 'AMEHHAA 30HA', İŞARET DİREĞİ=pinyin+Japonca) → sınıf düzeltildi;
  (v) Türkçe kısmi-okunmuş (BEKLENEN BOMBA, UTANMAZ ADAM) → koşuya eklendi.
  Tam örnek listesi: outputs/DALGA_181/OKUNAMADI_ORNEKLERI.md
- **Kuyruk mekaniği dersi:** PUT /api/flow-queue F5-kuralı gereği partial/done statülerini KORUR
  (flip'ler sessizce geri alınıyordu, 2 tur kayıp) → resmî yol: replace-enqueue + force-PUT.
- **KOŞU ŞU AN: 131 film** (98 mahkeme + 33 derin-denetim), 131/131 force'lu, worker İLK filmi
  işliyor (TOPLU GÖSTERİLER 1991-0356). Tahmini süre ~13-15 saat.


## BÖLÜM L — KÖK-KAZI TURU (Çağatay: "İNCELE BUL ÇÖZ FİXLE") — 17:00
| Vaka | KÖK | FİX | KANIT |
|---|---|---|---|
| 13. SAVAŞÇI (476 PNG/0 kr) | OneOCR MOTORU hiç açılamamış (Code:6; MURPHY=1455, ÖRGÜT=access-viol — 3 film, bellek-cehennemi) | bellek kökü pagefile'la kalktı; 3'ü de koşuda | bucket=MOTOR_YOK taraması: yalnız 3 film |
| AYAK TAKIMI (Ken Loach) | jenerikte ETİKET HİÇ YOK (İngiliz-usulü yalın son-kart; 'DIRECTED' kelimesi filmde geçmiyor) | **FIX-A: ekran-teyitli KB-yönetmen dolumu** (yön-boş + kimlik-güçlü + KB-yönetmen tekil + isim ekran-verbatim; kill: MITAS_EKRAN_KB_YON=0) | teslim-md: **Yönetmen: KEN LOACH** ✓ |
| BAŞKAN VE MARI (MISE EN SCENE) | lexicon çok-dilliydi ama RESCUE kendi dar listesini kullanıyordu (kopukluk) + isim 5-token (tavan 4'tü) | rescue→lexicon TEK-KAYNAK bağlandı + sözlük 20+ dil/varyantla dolduruldu + token-tavan 4→6 (soy-bağlaçlı) | **Jean-Dominique de La ROCHEFOUCAULD** ✓; birim 8/8 |
| KÜÇÜK KAHRAMAN '0 kr' | BENİM envanter hatam (glob çift-hub'dan eskiyi almış) — gerçek kunye 2585B/GUVENILIR | envanter aracı düzeltilecek; film yine de koşuda | job-kıyası |
| YÜZYILIN CİNAYETİ | GERÇEK meşru-boş (ham-46 satırın tamamı tabela-çöpü) | fix gerekmez | ham döküm |
Sözlük genişlemesi: FR/DE/IT/ES/PT/NL/PL/CZ/HU/RO + RU/HI/AR-translit + bileşik kartlar
(STORY-SCREENPLAY-AND-DIRECTION, DIRECTED-&-PHOTOGRAPHED...) — hem DIRECTOR hem PRODUCER.
Bu fixler koşan 131-film dalgasına ANINDA yansıyor (her film taze süreç).
