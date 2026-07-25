# MITAS Proje Günlüğü

> Amaç: oturumlar arası süreklilik. Her Claude Code oturumu AÇILIŞTA son 2-3
> kaydı okur, KAPANIŞTA (veya önemli bir iş bitince) yeni kayıt ekler.
> Format: tarih + yapılan + öğrenilen/başarısız denemeler + bekleyen.
> En yeni kayıt EN ÜSTTE.

---

## 2026-07-26 — KARAR: kredi-çıkarım standardı 3 fps (Çağatay onayı). Mod-hatası keşfi + kök fix

**PIPELINE STANDARDI (Çağatay, 2026-07-26):** Bundan sonra kredi/jenerik kare-çıkarımı
**3 fps**. Gerekçe DENEYLE kanıtlandı (casanova kaynaktan 12fps çıkarıldı): okunabilir
kredi jenerikleri ≤0.5 ekran/sn kayar; 3fps = ~%17 kare-arası kayma = yüksek-kalite
örtüşme, çözünürlükten bağımsız. Kredi penceresi kısa (60-90s) → 3fps ~200-270 kare/film,
ucuz. Adaptif optimal (statik 1-2fps, kayan 3-4fps). Değişim noktası: mitas_pipeline
`--fps` default 1.5→3.0 (üretim değişikliği — diğer aktif kampanyalar da çıkarım kullanıyor,
KOORDİNELİ uygulanmalı, bu oturumda dokunulmadı). Eski Ex_Frame ~1.25fps çekilmişti = kusur kaynağı.

**MOD-HATASI KEŞFİ (Çağatay QC uyarısı sonrası):** benimle-dans-et "sağlıklı" görünürken
kayan jenerik STATİK-sayfa derlenmiş (Çağatay yakaladı — ben bütünsel göz denetimi hiç
yapmamıştım). Bağımsız mod-denetimi (harness/master_dup/mod_denetim.py, metin-maskeli
kayma vs sınıflandırma): **137/427 mod-hatası**. K6 uygulanınca gerçek sağlık %86.4 DEĞİL
**%58.3 (249/427)** — dup metriği bu kusura KÖRDÜ.

**KÖK SEBEP:** split_runs scroll/static kararını TÜM-KARE faz-korelasyonuyla veriyor;
kredi koyu zemin üstünde kayınca arka plan domine → dy≈0 → statik. Fix: metin-maskeli karar.

**DÜRÜST DÜZELTME (deney sonrası):** 1.25fps ölçümlerim ALIASLI'ydı — casanova gerçekte
95px/sn (yavaş), 1.25fps'te bile %60 örtüşme. Yani "86 film Nyquist-doomed" FAZLA KARAMSARDI;
sınıflandırıcı fix'i 137'nin çoğunu kurtarabilir, %91 kaynak-yeniden-çıkarım OLMADAN mümkün olabilir.

**QC MİMARİSİ (Katman 0/1/2, [[master-dup-kalite-kontrol]]):** asıl metrik = SADAKAT
(ham-kare vs master text-recall), dup değil. Koşan: Aşama-1 sadakat harness, Aşama-2
sınıflandırıcı fix (master_ex_modfix'e, master_ex EZİLMEDEN). Sonuç ölçülünce gelecek.

## 2026-07-24 (öğle) — Master-PNG kampanyası BEKLEMEDE (Çağatay: token tasarrufu). Durum: %86.4

**Sayı:** Ex_Frame sağlık **369/427 = %86.4** (taban %62.8; hedef ≥%91, kalan 20 film).
Her şey commit'li (437dce8), bit-parite yeşil, ölçüm deterministik (iç-JSON, stdout değil —
saglik.py yalnız en-kötü-15 basar, stdout ayrıştırma TUZAK).

**Kapanan:** M10 Şerit-Atlası (konsey 4/4: dikiş-düzeyi rec doğrulama; +30 film; hizli-silah
0.93→0.026) + M10c korunan-kayıt taşıma (alt-aralık muafiyeti; flip 2→1).

**KALDIĞI YER / devam planı:** (1) tek gerçek flip: daha-kotusu-olamaz dup=0.1032 (0.003 sınır-üstü —
incele); (2) kalan 53 dup-ihlali: sınır bandı 0.10-0.14'te ~15 film + dirençliler → plan M10-O1
(X-T imzalı dar sınıflandırıcı, konsey gardlarıyla) SON tur adayı; boy-6/doku-1/üretim-1 küçük işler;
(3) M5 kabul: VL-kilidi spot-testi + kör doğrulama + skip-audit tam tarama; (4) M4b üretim-tarafı
(1.5fps overlay onarımı) ayrı iş. Araç notu: konsey_dogrudan.py (tam kadro, MCP-restart'sız);
kapanis_kaniti.py İÇ-JSON'a çevrilmeli (stdout-parser hatası ders oldu). det-kararsızlık görevi
(task_84752ed4) Çağatay'da ayrı oturumda.

## 2026-07-24 (akşam) — Kapanış PDF: NIM'e devir + sıkı QC → 1082 doğrulanmış teslim

**İş:** 1475 benzersiz kapanış filmi → künye PDF. Token krizi sonrası okuma+kimlik+özet
NVIDIA NIM'e devredildi (Claude token=0): VLM=llama-4-maverick (kare→transkript),
LLM=maverick (kimlik+özet+kadro). Otonom hat: 25 hasat → 28 filtre → 29 NIM → 27 birleştir
→ 26 PDF, orkestratör 30_kapanis_zincir.sh (nohup+cron nöbetçi, token'dan bağımsız biter).

**Sıkı QC (Fable, basımdan ÖNCE kapı):** 1278 ham PDF → makine taraması 0 format-kusuru;
bilinen-film bilgi karşılaştırması 14/15 doğru. YAKALANAN: kimlik katmanı güven=yuksek dese
de halüsinasyon üretebiliyor (SINEMA_TEZGAHI→sahte "THE SALE"; ANNA KARENINA/CEVIZ Kiril-translit;
DERSU UZALA translit kadro→Kurosawa patch'i). Eklenen kalıcı filtreler (27): okuma-kanıtı
zorunluluğu (kanıtsız title-guess oyuncu-dolgusu YAPILMAZ), bozuk-metin dedektörü (sesli-harfsiz
parça/çift-baş), Latin-saflık, şirket→kişi, dublaj-kadro, fuzzy yazım düzeltme.

**Sonuç:** 1082 yüksek-güven PDF teslim (export/KAPANIS_PDF_20260724, 0 kusur). 392 film manuel:
199 okuma-kanıtsız-kimlik-tahmini (kaliteden ödün vermemek için geri çekildi), 156 oyuncu<3,
23 jenerik-okunamadı, 8 yönetmen-yok, 6 sahte-kimlik. Liste: _TESLIM_RAPORU.md.

**Öğrenilen:** (1) LLM kimlik güveni ölçüt DEĞİL — okuma-kanıtı korroborasyonu şart. (2) Teslim
kapısı basımdan ÖNCE, koda gömülü olmalı ([[teslim-kalite-kapisi]]). (3) Özet PDF'i engellemesin
— çekirdek künye (yön+≥3 oyuncu) esas. Runbook: filmtest/kapanis_hasat/README_KAPANIS.md.

**Bekleyen:** 392 manuel film — famous olanlara patch, okunamayanlara geniş-pencere re-hasat;
Çağatay kararı: identity-tier'ı (199) spot-check riskiyle salıvermek mi, patch mi.

---

## 2026-07-24 (öğleden sonra) — ACİL: Film Kapanış → 1691 künye PDF hattı (NIM'e devir)

**İş:** depo01 "Film Kapanış" (1691 tam film) → künye (yönetmen/yapımcı/ilk 8) + afiş + özet PDF.
Hat: 25 (hasat: son 600s+ilk 245s kare, TAMAM 1691/1691) → 28 (paddle metin-filtre, ~30 kare/film)
→ 29 (NIM Maverick: okuma+kimlik+özet — Claude token=0) → 27 (birleştir+fuzzy yazım düzeltme+patch)
→ 26 (PDF, afiş cache→IMDb). Bekçi: 30_kapanis_zincir.sh (nohup, oturumdan bağımsız; _DUR ile durur).
Rehber: filmtest/kapanis_hasat/README_KAPANIS.md. Durum: 65+ PDF export'ta, NIM tam koşu sürüyor.

**Öğrenilen:** vLLM GPU'yu tutunca paddle CUDA-OOM (vlm durduruldu; v5 hattan çıkarıldı — okuma işi
onset hassasiyeti istemiyor); 32 paralel Sonnet API hız sınırı + oturum limiti yedi (NIM'e devir bundan);
tr_upper_prose yabancı adlarda İ üretiyor (RİPPER vakası — özetlerde yabancı adlar BÜYÜK-ASCII yazılır);
Sonnet okuması 149 filmde altın-standart olarak duruyor. Fable = sadece hakem (tablo tarama + patch).

**Bekleyen:** NIM koşusu bitince tablo QC turu (Fable), şüpheli/bayraklı filmler, POROROCA-sınıfı
okunamayanlar, TEYZEM-tipi çok parçalılarda kardeş künye kontrolü.

---

## 2026-07-24 (gece) — İLK BÜYÜK VL KOŞUSU: test_film 40 film, çıkış+giriş jenerik → Qwen3-VL-8B

**İş:** Yeni süreç — test_film'deki 40 MP4 filmde v5 ile jenerik başlangıcı bul → 60s+5s
bindirmeli sessiz parçalar → vLLM Qwen3-VL-8B (video_url) ham transkript. Pilot(3)→onay→tümü.
Gece Çağatay talimatıyla eklendi: ilk-240s GİRİŞ okuması + süre×piksel taraması + QA/kök-sebep.
Yeni: `kurulum/22_testfilm_video_vl.py` (ASCII slug — file:// boşluk fix'i; mitas.env yükleme +
v5 assert; checkpoint/resume; artımlı rapor), `kurulum/23_testfilm_giris_vl.py` (245s giriş
klibi → aynı hat), `vlm_sunucu.sh`'a 2 geriye-uyumlu env düğmesi (GPU_UTIL, MAX_PIXELS).

**Sonuç:** ÇIKIŞ 40/40 rc=0 (172 parça, motor: 34 v5 / 3 rescue / 3 paddle), GİRİŞ 40/40 rc=0
(200 parça). QA (36 ajan + 26 kare-doğrulama): 10 iyi/20 orta/10 kötü. **Yönetmen: çıkışta 19
(≥4'ü UYDURMA), girişle 30/40 GERÇEK** (Ray Enright, Louis Malle, Truffaut, Resnais, Majidi,
Orhan Elmas…). Raporlar: `outputs/SABAH_RAPORU_20260724.md` (ana analiz),
`TESTFILM_VL_RAPOR_20260723.md` (çıkış), `TESTFILM_GIRIS_VL_RAPOR_20260724.md` (giriş).

**Öğrenilen (kritik):** (1) vlm_rescue 3 filmde v5'in DOĞRU "kredi yok" kararını bozup sahte
künye üretti (KIZGIN_SİLAH "John Ford", DERT_BENDE "Bollywood künyesi") → fallback iptali
önerildi (konsey GLM aynı yönde). (2) Model boş/footage karesine ŞABLON künye uyduruyor —
"Directed by John Ford" 3 filmde uydurma; jenerik-sonrası parçalar çöp sayılmalı. (3) Sweep
(27 ölçüm): sınır süre değil süre×yoğunluk — yoğun kayan jenerikte 90s+ dejenerasyon duvarı
(tekrar 0.95), 30-45s en sadık; statikte 120s bile temiz; `max_pixels` video girdisinde ETKİSİZ
(işlemci ~12k tokene oto-sığdırıyor); 2500 çıktı tavanı meşru metni kırpıyor → 3500 önerisi;
dinamik pencere önerisi: credit_type=scroll→30-40s, statik→60s. (4) Operasyon: vLLM 0.85'te
KV-cache'e takılıyor (alt sınır ~0.885); pgrep öz-eşleşmesi gece zincirini 20 dk kilitledi
(kural: `[2]2_testfilm` deseni). (5) VL yönetmen alanı teyitsiz KULLANILMAZ (≥%21 uydurma) —
çift-kaynak (giriş+çıkış) teyidi şart.

**R2 eki (aynı sabah, Çağatay onayıyla):** en kötü 10 film 30s+3500 profiliyle yeniden koşuldu
(`kurulum/24_r2_kotu10.py`; run-1 korunarak `video_vl_r2/`). Sonuç: 5 büyük kazanım (+%46…+%136
benzersiz içerik; PRODUTTORI-döngüsü 0), 2 kalite kazanımı (CENNETİN_RENGİ artık GERÇEK Farsça
okuyor; MAKSİM zincir 28→1), 2 nötr-pozitif, 1 direnç (POROROCA — okunabilirlik tabanı,
kare-tabanlı sonda adayı). 15s sondası: +%40 içerik ama 2× GPU — standart 30s, 15s istisnalara.
UYARI_İŞARETİ dersi: "Siegel" gitti "John Carpenter" geldi → ünlü-isim önseli pencereyle
çözülmüyor, çift-kaynak teyit şart. Rapor §8'e işlendi.

**R3 (öğle):** Kova-1 profili kalan 27 filme uygulandı (27/27) + 10 filme giriş-300s (10/10).
vLLM koşu ortasında dış etkiyle düştü → R3-bekçisi otomatik toparladı (bekleme molası dahil).
Giriş-300s: HAL BARWOOD (UYARI_İŞARETİ — 300s fix kanıtı) + KEVIN REYNOLDS (MONTE_KRİSTO)
GERÇEK kazanç; 5 uydurma yakalandı (jenerik-dışı bölge konfabülasyonu; "John Ford" 4. kez,
kare-kanıtlı). Kural kesinleşti: kart-kanıtlı okuma kazanır, jenerik-dışı bölge çöp,
"John Ford" bilinen-halüsinasyon kara listesinde. Konsey performans turu (GLM): eşzamanlılık +
CUDA-graphs + erken-durdurma Tier-1; fps-ön-örnekleme yeni fikir; quantize + repetition_penalty
tuzak uyarısı. Kimi 2 turda da 3 denemede düştü — anahtar/endpoint bakımı gerek.

**Kova-3 (öğleden sonra):** `harness/kunye_kiyas/kunye_cikar.py` yazıldı (24 test; deterministik,
LLM'siz) → 40 film kunye.json + `outputs/TESTFILM_KUNYE_20260724.json`. Yönetmen: 7 guvenli +
21 tek_kaynak + 7 celiskili + 3 supheli + 2 yok; 90 oyuncu kaydı. 8-film ajan-doğrulaması →
düzeltmelerle 8/8 (Truffaut "DIRECTION DE PRODUCTION" tuzağından kurtarıldı). Kritik tasarım
dersi: aday sıralaması ERKEN-GÖRÜLME ile (tekrar sayısı uydurma döngülerinde anti-sinyal).
v2 backlog: ikincil-alan kontaminasyonu, düz oyuncu listeleri, etiketsiz/Farsça kartlar.

**Sondalar (akşamüstü):** (1) POROROCA 512×288 "okunmaz" sınıfı → **30b tek-kare ~%85-90
OKUDU** (zoom-gözle teyit; 8B@1M bozdu — "30b fark yaratmaz" ön-tahmini ölçümle çürüdü).
(2) MAVZER + Kol D → **fps ön-örnekleme (video @0.4fps) kazandı**: prompt 12k→2.5k, doğal
çözünürlük, temiz okuma (konsey fikri deneysel doğrulandı). (3) GLM kolu (Çağatay talebi):
glm-ocr aynı karelerde dejeneratif döngü ("nəmərən"×80) — mikro-punto sınıfında ELENDİ.
Motor seçim tablosu rapora işlendi (§11): varsayılan=fps-ön-örneklemeli video;
mikro-punto=30b-kare (tek kanıtlı); boş bölge=okuma. NOT: bu bulgular 1691-film Kapanış
kampanyasının "POROROCA-sınıfı okunamayanlar" bekleyenine doğrudan aktarılabilir.

**Bekleyen:** fps-ön-örneklemenin _pipe_video_vl'ye env-opsiyonlu eklenmesi + R4 doğrulama
(onay); performans paketi (eşzamanlılık+erken-durdurma+CUDA-graphs); Kova 2 non-Latin yaması;
kunye v2 backlog; celiskili 7 filmin insan kararı; Kimi endpoint bakımı.

---

## 2026-07-24 — Master-PNG kampanyası: dedup fix'leri sahada, Nyquist keşfi, Ex_Frame büyük koşusu başladı

**Hat:** master-PNG penceresi (fork). /goal: Ex_Frame 427'de sağlıklı-master ≥%91 (tam yetki).

**Teşhis→fix zinciri (hepsi MITAS_MASTER_V2 bayrağı arkasında, flag kapalı=bit-parite):**
M1 dup-metriği + M2 aslına-sadık harness (SON_METRO bit-parite kanıtı) + M3 112-film
kusur dökümü (H2 uzak-kart baskın, 60 film) → F1 (3-kapılı uzak-kart dedup) →
**F1b** (gren dHash'i kör ediyor keşfi; gri bant-fark + det kapısı; 165 birleşme,
içerik kaybı 0, >0.10 film 36→31) → **F1c** (hayalet-kutu rec hakemi; 112 doğrulama
koşusu sürüyor). F2/F3 yazıldı ama havuzda hiç tetiklenmedi (dürüst kayıt).

**BÜYÜK KEŞİF (görsel kanıtlı, GLM-Nyquist çerçevesi):** footage-üstü kayan künye
sınıfında (~8-17 film) kompozitör metni İMHA ediyor — 1.5fps'te kare-arası kayma
satır yüksekliğini aşınca satırlar örnekleme boşluğuna düşüyor; BAŞKAN_VE_MARI:
zemin 16× sayfa, yazı 13px'e ezik. Dedup bunu geri getiremez. M4b kararı:
overlay-tespit + pencere-hedefli 6-12fps ROI yeniden çıkarım (kaynak eldeyken);
kaynak yoksa (Ex_Frame!) OCR kutu-hasadı "metin duvarı" fallback.
Salt-piksel dedup kapısının imkânsızlığı ÖLÇÜLDÜ: YAKIN_PLAN farklı-altyazı çifti
farkı < BAŞKAN gren gürültüsü (yp_P2_P4.png kanıtı).

**Görsel rapor (Çağatay'a):** claude.ai/code/artifact/c9db78a9-0c53-4e64-8755-23f52b48337a

**Konsey altyapısı:** Kimi kök sebep bulundu-düzeltildi (thinking 180sn timeout aşımı +
boş-str TimeoutException 429-koşulunu ıskalıyor; timeout 420 + timeout'ta k2.6 yedeği,
2fcbf40). Qwen Çağatay talimatıyla DEVRE DIŞI (.env'de yorumlu). Nemotron+MiniMax+
Gemini+GPT kayıtlı ama ÇALIŞAN sunucu süreci eski — restart'a kadar katılamazlar;
çözüm: sonraki turlar doğrudan-çağrı (konsey_dogrudan.py).

**Koşan:** F1c 112-doğrulama (~43/112); M7 Ex_Frame taban koşusu (adaptör+sağlık
sınıflandırıcı+427 ölçüm). Sırada: taban ihlal dağılımı → kanıt-güdümlü turlar
(muhtemel ana kaldıraç: M4b-fallback kutu-hasadı) → ≥%91 → M5 kabul + kayıt.

## 2026-07-23 (gece, 2. giriş) — NVIDIA canlı doğrulama + MiniMax-M3 konsey üyesi

**İş:** Çağatay nvapi- anahtarını girdi (anahtar_gir --uye nvidia) → canlı testler: (1) Nemotron
Ultra chat ✓, (2) MiniMax-M3 chat ✓, (3) DeepSeek NVIDIA yedek-ucu ✓ ("CALISIYOR" cevabı,
harness/env.sh'ın kendi source deseniyle). Anahtar mitas.env'e de kopyalandı (transcript'e
yazılmadan, sed ile). **MiniMax-M3 7. konsey üyesi yapıldı** (Çağatay kararı: "Qwen genelde
sorunlu, Gemini şimdilik yok — elde ciddi alternatifler olsun"): providers/minimax.py, Nemotron'la
AYNI NVIDIA_API_KEY'i paylaşır (tek anahtar iki üye açar), MINIMAX_MODEL ile override.
Konsey artık: gemini, qwen, glm, gpt, kimi, nemotron, minimax.

**Öğrenilen/DÜZELTİLEN:** NVIDIA katalogunda deepseek-v3.2 YOK (web aramasının verdiği slug
yanlıştı) — /models canlı teyidi: deepseek-v4-pro (amiral) + deepseek-v4-flash (hızlı).
Fallback varsayılanı v4-pro yapıldı; özette 90sn timeout sorun olursa
MITAS_DEEPSEEK_NVIDIA_MODEL=deepseek-ai/deepseek-v4-flash. DERS: katalog slug'ları web
kaynağından değil /models ucundan teyit edilir. Kalan tek varsayım-riski kapandı.

**Bekleyen:** shell mitas.env'i OTOMATİK yüklemiyor (sadece harness/env.sh source ediyor) —
pipeline'ı env.sh dışından çağıran bir yol varsa NVIDIA_API_KEY oraya ulaşmaz; ilk gerçek
özet koşusunda doğrula. anahtar_test çıktısındaki "★ MAX" işaretinin anlamına bakılmadı (kozmetik).

---

## 2026-07-23 (gece) — NVIDIA Build entegrasyonu: konsey'e Nemotron + DeepSeek yedek ucu

**İş:** Çağatay build.nvidia.com'a kayıt olup nvapi- anahtarı aldı (ücretsiz katman: kredi yok,
~40 istek/dk/model rate-limit, 140 model tek OpenAI-uyumlu uçtan: integrate.api.nvidia.com/v1).
İki ekleme yapıldı: (1) **Konsey 6. üye:** `council_mcp/providers/nemotron.py`
(nvidia/nemotron-3-ultra-550b-a55b — 550B hibrit Mamba-Transformer MoE, 1M bağlam; mevcut 5 üyeyle
mimari akrabalığı yok = farklı kör nokta). server.py + .env.example + anahtar_gir/anahtar_test'e
`--uye nvidia` eklendi. (2) **DeepSeek yedek ucu:** `scripts/_deepseek.py` — DeepSeek bugün özet
zincirinin BİRİNCİL motoru yapılmıştı; resmi uç düşerse özet gemma-yerel'e düşüyordu (bake-off:
yerel güvenilmez). Artık birincil uç başarısızsa (402/kota/denemeler tükendi) NVIDIA'daki
deepseek-ai/deepseek-v3.2'ye otomatik geçer. TDD: `tests/test_deepseek_nvidia_fallback.py`
7 test + mevcut 25 özet testi YEŞİL. Davranış korundu: hiç anahtar yoksa sessiz None.

**Elenen adaylar (gerekçeli):** TencentDB-Agent-Memory (çoklu-ajan paylaşımlı hafıza — MITAS'ta
karşılığı yok), code-review-graph (27K+ dosya monorepo aracı; MITAS ~1.7K py dosyası),
OmniRoute (council_mcp zaten aynı işi disiplinli yapıyor). MiniMax-M3/Inkling/diffusiongemma
konsey adaylığı ertelendi (sinyal seyrelmesi + Preview-etiketi riski) — MiniMax-M3 LM Arena
~1491 ile güçlü, Çağatay isterse aynı NVIDIA anahtarıyla 5 dk'da eklenir.

**Bekleyen:** (1) Anahtar girişi: `python3 council_mcp/anahtar_gir.py --uye nvidia` +
`anahtar_test.py --uye nvidia`; mitas.env'de `#NVIDIA_API_KEY=` satırını doldur (placeholder hazır).
(2) Canlı doğrulama: NVIDIA'daki deepseek model slug'ı (deepseek-ai/deepseek-v3.2 varsayıldı)
anahtar_test /models listesinden teyit edilmeli — yanlışsa MITAS_DEEPSEEK_NVIDIA_MODEL ile düzelt.
(3) Aday (benchmark ister, kurulmadı): nemotron-ocr-v2 — PaddleOCR/py3.14 boşluğuna API alternatifi;
kutu-koordinatı dönüp dönmediği + Türkçe jenerik isabeti test edilmeden karar yok (eval-harness-first).

---

## 2026-07-23 (akşam) — Ex_Frame exit-frame jenerik kesimi: 487 film, 30 Sonnet ajanı (master PNG verisi)

**İş:** `/home/cagatay/Ex_Frame/*-exit_frames/` — 487 film × ~600 kare (son 8dk, exit_%06d.png,
~1.25fps, 288k kare/54GB). Her film için kapanış-jeneriği başlangıç karesini bulup öncesindeki
FİLM SAHNESİ karelerini kalıcı sildik (master PNG yalnız jenerikten kurulmalı). Çağatay kararları:
tümü (önce pilot) + doğrudan rm + kesim=kapanış-bloğu ilk karesi (SON/THE END/ithaf/logo dahil).

**Neden vizyon:** MITAS `credit_onset.py` v4/v5 PaddleOCR gerektiriyor, py3.14'te kurulu değil
→ deterministik dedektör kullanılamadı. Jenerik sık footage ÜSTÜNE akıyor (siyah-kare heuristiği
patlar). Çözüm: **montaj-tabanlı Sonnet vizyon**. Araçlar: `harness/kunye_kiyas/exit_kesim/montaj.py`
(etiketli kontakt-sayfa: kaba→ince) + `kes.py` (gardlı silici: guven<0.60 / onset<=ilk / bayrak /
<8 kare kalır → SİLMEZ, flag'ler; her kesimde audit-şerit + manifest.jsonl).

**Sonuç (doğrulandı):** 10-film pilot %100 doğru (footage-üstü künye dahil) → onay → 30 paralel
Sonnet ajanı, 16'lık batch. **427 film KESİLDİ (193.122 kare silindi), integrity 427/427 tam**
(kalan kare=manifest, ilk-kalan==onset). Kesilmedi (güvenli, tümü duruyor): 43 jenerik_yok/tut_hepsi
(kredi 8dk penceresi dışında ya da ön-jenerikli eski film), 14 cok_az_jenerik (SON sadece son ~5
karede, <8 gard), 1 anomali (tapilacak-yalanlar = iki film birleşmiş → GUNLUK veri-hijyeni deseni),
2 atlandı (oyuncu, iyi-geceler-iyi-sanslar = kaynak tamamen siyah/bozuk). Sadece 1 düşük-güven
kesim (kaptan-january 0.65). Elle-ikinci-tur listesi: `outputs/exit_kesim/elle_inceleme.txt`.

**Öğrenilen:** (1) Montaj kontakt-sayfa + ajan = 600 kareyi tek tek okumadan ~2-3 görselde frame-doğru
onset. (2) Gard tasarımı (min-kare + bayrak) yanlış-kesimi sıfırladı; flag=güvenli. (3) 43 jenerik_yok
üretim sinyali: bu filmlerin kapanış künyesi 8dk exit-penceresinde YOK — daha geniş pencere ya da
giriş-jeneriği gerekebilir. **Kapanış (Çağatay kararı):** kesilemeyen 60 film "havuz zaten yeterli"
denerek KOMPLE SİLİNDİ (35.506 kare; log: `outputs/exit_kesim/silinen_60_klasor.log`). Ex_Frame'de
artık yalnız **427 kesilmiş film** var — hepsi master-PNG başlangıcına hizalı. Bekleyen yok.

---

## 2026-07-23 (akşamüstü) — %92 kampanyası: T4 doğrulandı+commit'lendi (88/110), T6 koşuyor

**Rewind olayı:** Çağatay yanlışlıkla rewind yaptı — HİÇBİR İŞ KAYBOLMADI (tüm commit'ler +
T4'ün diskteki kodu sağlam; tam yedek: ~/mitas_yedek_rewind_152202/). Master PNG çalışması
ayrı FORK oturumuna alındı; bu oturum jenerik-başlangıç hattı.

**T4 (hareket-otoriteli onset) doğrulandı ve commit'lendi (4e0818b):** 84→**88/110 (%80.0)**,
kredisiz 28/29 korundu. Kazanılan: MESLEĞE_DÖNÜŞ(+320), DİPTEKİLER(+203), KARAVAN(+182), "6"(+155).
Tasarım plandan bilinçli saptı: geri-birleştirme scroll-tip şartı OLMADAN her kazanan koşuda
denenir (dört hedefin scroll_oran'ı 0.07-0.24 çıktı — ölçüm planı çürüttü); güvenlik kısa-boşluk
(~45 örnek-kare) + rol-keyword içerik kapısından. Kalıntı risk: kapı geniş _ROL kullanıyor
('produc' logo-riski) — T6'da _ROL_CEKIRDEK'e geçirilecek.

**Veri-hijyeni bulgusu (ÜRETİM İÇİN ÖNEMLİ):** Film Kapanış'ta aynı TRT-id FARKLI film içeriği
taşıyabiliyor (görsel teyit: DİLEK_AĞACI dosyasında Coppola kapanışı, INNISFREE'de TV dizisi).
Asıl kopyalar '30062026SAYFA' batch önekinde. 5 film oradan kurtarıldı (5/5 arşiv-uyum),
3 film dışlandı (veri/dislanan.json). Kare-sayısı paritesi İÇERİK paritesi DEĞİL.

**Perf:** det-önbelleği (_det_cache.json) + olc_pool --paralel 8 → tam 110-film ölçümü ~2 dk
(eskiden ~30 dk). Isıtıcı: veri/det_isit.py.

**T6 (6 alt-adım):** 88→92/110. Kazanılan: SEN_TOM(Almanca sözlük), ÖLDÜRME(İtalyanca
nokta-lider+küçük-harf), TAKTİKLER(seyrek-yol ≥2-çekirdek-rol), ARKADAŞIMIN(scroll-kurtarma).
Kalan engel sınıfları teşhisli: Kiril/Farsça OCR, tek-isim kart dizisi, şirket-kalıbı FP.

**Politika kararı (Çağatay, 13ba2fc):** Restorasyon/TRT-ekleme kartları KÜNYE SAYILMAZ —
orijinal jenerik esas. TAKKELİ GT 588→905 düzeltildi (Kazakça restorasyon kartıydı).

**2. tur (konsey-GLM kırmızı-takım sonrası, 5 alt-adım):** 92→**99/110 (%90.0)**, kredisiz
**29/29** (tek FP DÖNÜŞÜ de düştü — şirket-kalıbı gardı: corporation/pictures/released-by
satırları isim sayılmaz). Kazanılan: VANYA+MELEKLERİ (ikinci-şans KİRİL rec — en-rec çöpü
sezilince lang='ru' yeniden okuma; homoglif çözümü), DOĞUM(Macarca sözlük), ROBOCOP+PARDAYYAN
(kazanan-koşuya bitişik kart-dizisi geri-genişletme — tek_genis'in elediği tek-isim kartları).
GERİ ALINAN: kf-tabanlı scroll-erken gardı (tüm-kare farkı gerçek-scroll'u sahne-bandından
ayıramıyor; 11 film bozdu → revert; DOĞRU yol kutu-MASKELİ zemin farkı). BUG BULUNDU:
_ROL'deki 'produc' \b(...)\b yüzünden HİÇ eşleşmiyormuş (producer/production yakalanmıyor).

**Mini-tur 3:** produc-regex bug'ı düzeltildi (\b(...)\b önek-alternatifleri hiç eşleşmiyordu)
→ KÜÇÜK_SİMBA (+1). Kutu-maskeli zemin-hareketi KALİBRE EDİLEMEDİ (karşı-örnek KAHRAMAN_
UZAYLILAR: gerçek jenerik animasyonlu zemin ÜSTÜNDE başlıyor — salt piksel-hareketi "sahne mi
kredi mi"yi çözemez, geri alındı). CJK hipotezi çürütüldü (İNİŞLİ'deki metin OCR gürültüsü).

**ASİMETRİ POLİTİKASI (Çağatay):** erken KABUL (fazla kare zararsız), geç KABUL EDİLEMEZ
(cast atlanır). olc_pool'a ÜRETİM skoru eklendi (erken≤120/geç≤20, 0eb5f58). Görsel hata
raporu: outputs/jenerik_hata_raporu/rapor.html.

**FİNAL TUR + T8 → KAMPANYA KAPANDI ✅: 103/110 = %93.6 simetrik, ÜRETİM %96.4 (106/110),
kredisiz 29/29.** Kazanımlar: PRENSESİN (producer+isim köprü kapısı), KANDAHAR (Arapça/Farsça
ikinci-şans: kredi_yok→+5), YÜREKTEN (şirket-budaması). Kritik gard: yabancı-alfabe yoluyla
kazanılan koşuda Latin ileri-budama ÇALIŞMAZ (yabanci_yol bayrağı — KANDAHAR/ARKADAŞIMIN
regresyonunun kök-sebep düzeltmesi). T8: GLM kod-avı gardları indi ('y-sesli' ölçülen
regresyonla geri alındı — dürüst ret). ×2 ölçüm deterministik + bağımsız doğrulama birebir.
Kalan 7: 5 kabul-edilebilir-erken (TV-bandı/epilog/tabela sınıfı) + 2 geç (GELECEK +91
yapısal boşluk, İNİŞLİ +89). Kalıcı çözüm adayı: dar-VLM (ayrı karar).

**ÜRETİM AKTİVASYONU (Çağatay: "artık aktif stratejimiz bu", d757ecc):** tespit_v5,
_jenerik_pool.py'de bayraklı birincil yol olarak ÜRETİMDE (MITAS_JENERIK_V5=1, mitas.env).
v5 başarılıysa start_pos otoritesi + eski yama yığını atlanır; kredi_yok/hata → eski akış
birebir (fail-safe). Güvenlik payı PAD=10 kare (asimetri politikası). Smoke: 13. SAVAŞÇI
kopyasında v5=319 vs eski-CV=318 (çapraz-doğrulama), bayrak-kapalı davranış birebir.
GitHub'a push edildi (main).

**Bekleyen:** 
açılış-jeneriği tasarımı; Qwen için Alibaba Model Studio aktivasyonu (Çağatay).

## 2026-07-23 (öğleden sonra) — testas özet stratejisi MITAS'a entegre edildi (v2, flag arkasında)

**Talep (Çağatay):** MITAS künye-özeti (System A) "gereksiz uzun/dağınık, salak salak anlatıyor";
testas'ın prompt+stratejisi "tam istenen format". İki sistem birebir incelendi.

**Kök bulgu:** Prompt'lar AKRABA (aynı Jean-Picard altın örneği, aynı yasaklar). Fark prompt
metni DEĞİL, prompt'u saran 3 mekanizma: (1) MITAS prompt aşırı-reçeteli (135 satır, 5-adım
zorunlu YAPI + "Sabit cümle sayısı YOK" → model uzatıyor), (2) kontrol döngüsü yok (ilk
boş-olmayan çıktıyı körlemesine kabul), (3) kalite kapısı/onarım yok. → Rambling'i öldüren 1+3.

**Yapılan (MITAS_OZET_V2=1 flag arkasında; legacy birebir korundu, Prensip 2):**
- `scripts/_ozet_kalite.py` — testas pdf_auditor/pilot10 gate+repair BİREBİR portu (17 golden test).
- `core/api/prompts/ozet_film_v2.txt` — yalın prompt (legacy'nin ~%42'si) + 2-satır ASR önsözü.
- `mitas_pipeline._generate_ozet_v2` — sağlayıcı-içi 3-deneme öz-düzeltme + kapı + onarım (8 test).
- Girdi (ASR transkripti) ve model zinciri (gemini→sonnet→gemma, bake-off kazananı) DEĞİŞMEDİ.
- `.gitignore`: `!scripts/_ozet_kalite.py` — `scripts/_*` yeni modülü yutuyordu (dağıtımda
  kaybolurdu; git-status'ta görünmemesinden yakalandı).

**Konsey (kırmızı takım, GLM):** KABUL → ASR'de twist-kaybı riski gerçek (Sixth Sense senaryosu:
2 saat gürültü frekansı tek-replik twist'i bastırır) → v2 prompt'a "frekansı betimlemeyle doldurma,
dönümü merkeze koy" satırı eklendi. RED → "kelime limitini 45-75'e genişlet"; kullanıcının şikayeti
TAM DA uzunluk + testas'ın 32-65'i zaten kullanıcı-onaylı (konseyi geçtim). Qwen HTTP 401
(geçersiz anahtar — council_mcp/.env'de düzeltilmeli), Kimi 429 (aşırı yük) → tur TEK üyeli.

**A/B eval SONUCU (6 çeşitli film, aynı ASR, eski vs v2):** v2 AÇIK ARA kazandı. Ortalama
uzunluk eski 73 → v2 55 kelime; kapı-geçme eski 3/6 → v2 6/6. Eski 3 filmde 65-kelime sınırını
aştı (71/83/92 kl — "salak salak uzatıyor"un tam kanıtı), v2 hepsini 52-59'a çekti. GLM'in "twist
kaybolur" korkusu ÇÜRÜDÜ: HALIFAX (whodunit) + ÜÇ RENK MAVİ (aldatma reveal) twist'leri v2'de
merkeze geldi — eklenen "dönümü merkeze koy" satırı çalışıyor. AEON FLUX'ta isim farkı (Aeon/Catherine
vs Ion/Una) = ASR belirsizliği, prompt kusuru değil. Yan bulgu: koşuda gemini 429 (kota) → zincir
Sonnet'e düştü, çıktı geldi (dayanıklılık OK ama gemini kotası üretimde de dolabilir).

**Bağımsız inceleme:** codex CLI kurulu DEĞİL → CLAUDE.md'nin eşleştirdiği dış konsey kod-avı
yapıldı (GLM; Qwen 401/Kimi 429 düştü). GLM 4 bulgu: (1) "produced_any ölü kod" YANLIŞ POZİTİF —
konseye sadeleştirilmiş kod verdiğimden (gerçekte satır 1442'de var; ders: brifingde GERÇEK kod ver);
(2) enforce ValueError→çıktı kaybı: MITAS'ta kelime-bazlı + URL yok + placeholder-by-design (testas
felsefesi) → bug değil; (3) birikimsiz feedback→osilasyon: GERÇEK, KABUL → feedback birikimli yapıldı
(testas orijinaliyle de hizalandı); (4) best ilk-gelen-kazanır: kasıtlı tasarım. 25/25 test hâlâ yeşil.

**PROMOTE YAPILDI (Çağatay onayı "aç"):** mitas.env satır 97-98'e `MITAS_OZET_V2=1` +
`MITAS_OZET_DEEPSEEK=1` eklendi. Ayrıca Çağatay talebi "testas hangi API'yi kullanıyorsa MITAS da
onu kullansın (DeepSeek)" → `_ozet_chain`'e MITAS_OZET_DEEPSEEK flag'i eklendi, DeepSeek zincirin
BAŞINA (birincil). Üretim zinciri artık: **deepseek → gemini → sonnet → gemma-local**.

**Uçtan-uca doğrulama (v2+DeepSeek, 2 yeni film):** SON YARIŞ 47 kl / ROBOCOP 50 kl, ikisi de
kapı GEÇTİ, **Türkçe temiz ve doğal** (Çağatay'ın özel isteği), twist korundu (ROBOCOP: Cable=Alex
Murphy reveal). DeepSeek HIZLI (2.7-3.1s) ve gemini'nin 429 kota sorununu yaşamıyor. 25/25 test yeşil.

**Açık kalem:** Qwen konsey anahtarı council_mcp/.env'de kırık (401) — konsey tek-üyeli (GLM).
Kanıt dosyaları: scratchpad/ab_sonuc.txt (6-film eski-vs-v2), scratchpad/dogrula_deepseek.py.

---

## 2026-07-23 — Reboot veri kaybı KURTARILDI; %92 kampanyası planlandı, Sonnet'e devredildi

**Olay:** Sistem 11:24'te yeniden başladı → /tmp scratchpad SİLİNDİ (119-film GT,
tahminler, tüm kareler). Ders: kritik veri artık REPO'da tutuluyor.

**Kurtarma:**
- 119-film doğrulanmış GT + v5 tahminleri workflow journal'ından
  (`~/.claude/.../wf_aac18f35-fac/journal.jsonl`) bit kaybısız kurtarıldı →
  `harness/kunye_kiyas/veri/{dogrulama_sonuc,v5_tahminler}.json`. Bozuk "_" kaydı
  düşüldü → taban **87/118 = %73.7** (kredi-var 56/87 ≈ %64, kredi-yok 30/31 = %96.8).
- pool_cek_cikar.sh / batch_v5.py / gt_duzeltilmis (8 film + YILDIZ=46) transcript'ten kurtarıldı.
- **Kaynak taşınmış:** 30.06 klasörü boşaltılmış; filmler `Film Kapanış` içine
  `evoArcadmin_<parti>_<id>-<AD>.mp4` adıyla gitmiş. 115/118 tam id eşleşti
  (YOK: SAKLI_GERÇEKLER, RIGOLETTO, 300_SPARTALI).
- **Parite kanıtı:** OPERADAKİ_HAYALET yeniden indirildi → süre 5460s, kare 1201,
  v5=1161 — kayıtla BİREBİR. GT yeni indirmelerde geçerli.
- Kareler artık kalıcı diske iniyor: `/opt/mitas/data/jenerik_havuz/pool_frames/`
  (`veri/havuz_kur.sh`, hata filmleri önce; log: `veri/havuz_kur.log`).

**Konsey (2 tur kırmızı-takım; GLM taşıdı, Kimi her turda 429/Moonshot, Qwen 401):**
GLM "Motion-Gated Onset" önerdi; hakemlik sentezi: scroll-tip koşuda onset otoritesi
HAREKET, statik kartta İÇERİK çapası (epilog gardıyla). Tur-2 kazanımları: 2fps
aliasing gardı (dy max_shift'e yapışırsa scroll say), epilog ayırıcısı=yapısal düzen
(noktalama), SON_ERISIM gevşetmesinde çekirdek-rol beyaz listesi, split-screen ROI (YAGNI).

**Plan → Sonnet:** `docs/MITAS_Jenerik_92_Iyilestirme_Plani_v1.md` (8 görev:
ölçüm harness'ı, kapı-teşhisi, hata atlası, scroll-onset, statik içerik-çapası,
kaçırılan-kurtarma, kabul, kayıt). T1+T2 Sonnet subagent'ları başlatıldı.

**Bekleyen:** indirme ~115 film (saatler); T3 atlası indirme ilerledikçe;
kırmızı çizgi kredi-yok ≥30/31; Kimi tekrar denenecek (görüş eksik kaldı).

## 2026-07-20 (akşam) — Dilim-vs-video testi kuruldu, jenerik-başı tespitinde DURDU

**Karar (Çağatay):** Yol A (kare OCR) sistemden çekilecek; Yol B (havuz→master→dilim→VL)
ve Yol C (start_pos'tan 1'er dk sessiz klip→VL) eşzamanlı koşup 4 sonuç + referans
üretecek, tek PDF'te kıyaslanacak. ASR/QC/PDF-üretimi yok.

**Yapılan:**
- Kaynak: `smb://depo01cifs.int.trt.net.tr/sas_h264/Film Kapanış` (2398 film).
  Mount "denied" verdi; **`gio copy` FUSE'u atlayıp çözdü (57 MB/s)**. GVFS FUSE yolu
  ffmpeg ile KULLANILAMAZ (ffprobe "error reading header", dd açamıyor, cat 100MB→1.1MB).
  Retry şart (GVFS kararsız). 18 film indirildi (13.2 GB).
- Deterministik seçim (tohum 20260720), yapım-id dedup → 20 film; 2'si elendi → **18 film**.
- **Katman A referansı**: 41 agent'lı workflow (2.5M token, 23 dk) — her film için web
  araştırması + bağımsız skeptik doğrulama. 484 isim, ort. 26.9/film. Sentez hükmü:
  *precision ölçülebilir, recall ölçülemez* (referans kapsamı jeneriğin çok altında).
- **`harness/kunye_kiyas/isim_normalize.py`** yazıldı (55 golden test + 6333 çift gerçek
  veri sınaması, 0 yanlış birleştirme / 0 yanlış ayırma).
- **Model benchmark** (5 model × 5 film, 13 çıkış dilimi): kazanan **`qwen36-27b-test`**
  (recall %54.1, tekrar %1.7, kaçış %0, 0 kesik, 497s). `glm-ocr` recall %50.4 ama **6× hızlı** (83s).
  `qwen2.5vl:7b` %52.6. `gemma4:26b` %26.3 (tekrar %77). **`qwen3-vl:8b` %0.8 — kullanılamaz.**

**Öğrenilen / çürüyenler:**
- **`qwen3-vl:8b` (ollama) THINKING DÖNGÜSÜNE giriyor**: 16384 token üretiyor, hepsi
  `thinking` alanına, `response` boş. Tetikleyici thinking metninde yakalandı:
  *"Wait, but in the user's image, is there a duplicate"* — **master PNG'nin duplikasyon
  kusuru modeli kilitliyor**. think=False / /no_think / system mesajı / num_predict
  4096→8192→16384 hiçbiri durdurmadı. vLLM `Qwen3-VL-8B-Instruct` varyantı thinking
  yapmıyor ama **yönetmen uyduruyor** ("A FILM BY ALFRED HITCHCOCK" — film Michael Curtiz'in)
  ve frequency_penalty'siz 672 satır/654 tekrar dejenerasyon veriyor.
- **XML teknik alanları GÜVENİLMEZ**: "HD" dediği 6 filmden 3'ü gerçekte 512×288; codec
  hepsinde yanlış (MPEG2 diyor, gerçek h264). Sadece SÜRE alanı doğru. `sas_h264` düşük
  bitrate proxy tutuyor, XML kaynak master'ı anlatıyor.
- **Okunabilirlik endişesi YERSİZ**: 512×288'de bile kart jenerik ve kayan jenerik
  (Türkçe ĞŞİÜÇÖ dahil) net okunuyor — gözle doğrulandı.
- Ölçüm metodolojisi hatam: jenerik satırları görev etiketi + ismi BİRLİKTE taşıyor
  ("1. Yönetmen Yardımcısı / 1st AD MEHMET GEZMEN"); tam-satır eşleştirme bunu kaçırıyordu.
  `metinde_gecer_mi()` eklendi → SONSUZ AŞK recall 0/26 → 16/26.
- Yanlış karşılaştırma yaptım: üretimdeki "LALELER" (1988) ile benim "LALE SOKAĞI" (1957)
  farklı filmler. **18 filmimin HİÇBİRİ üretim Database'inde yok** (TRT-id kesişimi = 0).
- Master seçimi DOĞRU: `master_png_dilimle.py` varsayılanı `reading_master_runaware`
  (Çağatay'ın düzelttiği). Kanonik `<ad> cikis.png` 3 katmanlı dHash dedup uyguluyor ve
  uzun kayan künyeyi kesiyor. 8 filmin 5'inde ikisi AYNI — çünkü `strict_scroll_frac≥0.75`
  olunca reading, kanoniğe passthrough yapıyor (`db_compose_master.py:1012`).

**DURDURAN SORUN — jenerik başlangıcı tespiti:**
- 7 filmden 3'ü başarısız: LALE SOKAĞI (havuz 887/900, master 600×36695),
  DÖNÜŞÜ OLMAYAN NEHİR (829/900, 600×57781), ANNA KARENINA (havuz 0, stage1 fail).
- Debug kayıtları: **iki katman da çöküyor**. PaddleOCR CV üçünde de `cv_start=None`;
  VLM-rescue (qwen3-vl:30b, 170 çağrı) devreye giriyor ama ikisinde "jenerik en baştan
  başlıyor" diyor (start_frame=13 / left_censored 0), birinde `not_sustained_credit`.
- Çürütülen hipotez: rescue thinking-bugından ölü DEĞİL — `credit_start_vlm.py:88`
  `txt = content or thinking` ile korunmuş. Ama `num_predict=64` şüpheli kaldı.
- **ÜRETİMDE DE VAR ama görünmüyor**: 274 kayıtta `not_found` 47 (%17), havuz=0 olan
  54 film (%20). Bunların **%98'inde `kunye.txt` yine de üretilmiş** — çünkü künyeyi
  Yol A üretiyor. Yol A çekilince bu hata ilk kez görünür hale geliyor.

**Bekleyen:**
- **ÖNCELİK: jenerik başlangıcı tespiti çalışması.** Mevcut yaklaşım tamamen OCR-tabanlı
  ("bu karede yazı var mı"); eski/düşük kontrastlı filmlerde çöküyor. Kullanılmayan
  sinyaller: sahne-kesme yoğunluğu, hareket düzeni (dikey kayma), zemin siyaha dönüşü,
  yazı bölge/aralık düzenliliği, ses/müzik geçişi.
- Master PNG duplikasyon kusuru (SANTA FE'de aynı blok 2 kez; VL kilitleyen tetikleyici).
- `DERİN KUYU` tüm modellerde 0/15 recall — model mi okuyamıyor, referans mı uyuşmuyor?
- Yol C (video klip) hattı hiç koşulmadı.
- Çağatay onayı bekleyen: Yol A deaktivasyonunun test SONRASINA ertelenmesi önerisi.

---

## 2026-07-20 — Video-hibrit router kalibrasyonu → ölçüm kusuru bulundu

**Yapılan:**
- HYBRID_DEVIR_NOTU §4-adım-1 kalibrasyonu yürütüldü (28 film, manifest sinyalleri
  `kunye51_20260714/Database/` altında bulundu). Araçlar: `router_kalibrasyon.py`,
  `router_kiyas.py`, `router_sinyal_v2.py`, `router_loocv.py`,
  `router_kos_sonra_devret.py`, `gt_yanlilik_denetimi.py`,
  `masterpng_kayip_denetimi.py` (hepsi vllm_bench_20260718/, salt-okuma)
- Rapor: `docs/MITAS_Video_Hibrit_Kalibrasyon_v1.md`
- **Adım-2 (router modülü) DURDURULDU** — gerekçe aşağıda

**Öğrenilen / çürüyenler:**
- **Devir notunun ana hipotezi çürüdü:** `strict_scroll_frac` video-uygunluğu
  ayrıştırmıyor (GÜZEL_BİR_ÖLÜM scroll=0.881 → video 1.000; FRANNY scroll=0.063
  → 0.720). En güçlü korelasyon −0.445. A-priori router LOOCV %74 (+0.663 recall,
  2.0× hız) — kural 21/23 fold'da stabil ama karar verdirecek güçte değil.
- **ASIL BULGU — ölçüm dairesel:** `claude_gt`'nin 313 diliminin TAMAMI
  `reading_master_runaware_p*.png` kaynaklı, yani GT master-PNG okunarak
  üretilmiş. Video PNG'nin kaybettiğini okuyunca metrik "uydurma" yazıyor.
  Kanıt: KULÜBE (Rancho Notorious) — GT'nin iki `[okunamadı]` satırını video
  MARLENE DIETRICH / ARTHUR KENNEDY / MEL FERRER diye doldurmuş, satır hizasında.
  "Uydurma" havuzunun %98.7'si isim-formunda, sadece %1.3'ü teknik gürültü.
  → Notun "%24.7 uydurma" hükmü büyük ölçüde ölçüm hatası.
- **Master-PNG kayıp denetimi (Çağatay'ın seçimi):** video'nun 2096 isminin
  680'i (%32.4) hiçbir master-PNG modelinde yok. Üç popülasyon ayrıldı:
  (a) GERÇEK KAYIP — BEYAZ_BİZON'da master-PNG YALNIZ ekip bloğunu içeriyor,
      oyuncu kartı (Dino De Laurentiis, Jack Warden, Clint Walker, Slim Pickens)
      komple kayıp; iki model birebir aynı ekip listesini okuyarak doğruladı.
      Bu film GT'siz 4 filmden biri olduğu için kayıp benchmark'a hiç yansımamıştı.
  (b) GERÇEK UYDURMA — BABAM (390-isim duvarı), DAĞ_ADAMLARI'nda video gerçekten
      uyduruyor (CRAN T. HESTON = CHARLTON HESTON bozulmuşu). Uydurma
      yoğun/kayan jeneriğe özgü, kart-jenerikte değil.
  (c) METRİK ARTEFAKTI — CENNETTE'de İspanyol NO-DO başlıkları isim sanılmış.
- **İki kayıp mekanizması:** blok düşürme (DÜNYANIN 16, CENNETTE 12, JURASSIC 11
  blok düşmüş) VE kırpma taşması (KULÜBE'de 54/54 blok tutulmuş ama satır kesilmiş).
- **Konsey:** kırmızı-takım turu açıldı, YALNIZ GLM cevapladı (Qwen HTTP 401
  anahtar hatası, Kimi HTTP 429 bakiye bitmiş — ikisi de düzeltilmeli).
  GLM "a-priori router kurma, koş-sonra-devret'e geç" dedi; yönü doğru
  (süre iddiası tuttu: 1.52×, post-hoc sinyaller a-priori'den güçlü:
  video_sn ↔ Δrecall −0.664 vs −0.445) ama gerekçesi yanlıştı — %14 uydurmayı
  veri kabul edip metriğin geçerliliğini sorgulamadı.

**Bekleyen:**
- Bağımsız GT (6-8 filmde ham video karelerinden, master-PNG'den DEĞİL) —
  bunsuz ne kayıp oranı ne uydurma oranı sayısallaştırılabilir. PAHALI, onay ister.
- 680 PNG-dışı adayın (a)/(b)/(c) otomatik sınıflandırması yapılmadı.
- Master-PNG kırpma/blok-düşürme kusurunun kök sebebi (`_credit_detect.py`,
  `compose_motion_state_credits.py`) araştırılmadı.
- Router: bağımsız GT sonrası tekrar. Mevcut kanıt koş-sonra-devret'i işaret ediyor.
- Konsey anahtarları: Qwen (Alibaba hesap), Kimi (bakiye).

---

## 2026-07-19 — Ekosistem kurulumu + yönetim modeli

**Yapılan:**
- Skill ekosistemi kuruldu: ~385 skill / 75 agent / 260 command (14 marketplace,
  symlink ile `~/.claude/` altına). Rehber PDF: `docs/rehber/MITAS_Skill_Rehberi.pdf`
- `council_mcp` Linux'a taşındı (.venv yeniden), MCP olarak bağlandı (`council`)
- `providers/kimi.py` yazıldı (Kimi K3); Qwen/GLM'e model-override eklendi
- Yönetim modeli tartışılıp `CLAUDE.md`'ye yazıldı (133 satır): görev dağılımı,
  dış-konsey otonomisi, soru modları, mercek ataması, eskalasyon zinciri
- İlk otonom konsey turu: GLM'e mekanizma tasarımı soruldu — 3 önerisi
  (brifing formatı, sistematik-vs-istisna ayrımı, mercek ataması) deftere girdi
- Kalıcı hafıza başlatıldı (user profili, geri bildirimler, proje durumu)

**Öğrenilen / başarısız:**
- Qwen API: Alibaba hesabında ödeme sorunu → kod değil hesap meselesi
- Çağatay'ın ilk Kimi anahtarı sohbete yapıştırıldı → İPTAL edilip yenilenecek
- Marketplace dizinleri bir kez sessizce silindi (muhtemelen paralel oturumun
  /reload-plugins'i) — broken symlink çıkarsa kaynağa bak

**Ek (aynı gün, devam):**
- Guard hook'ları kuruldu ve CANLI DOĞRULANDI: kilitli-dosya onayı
  (mitas_roots.py, model_manifest.yaml, MITAS_KUNYE_KURALLARI.md, CLAUDE.md),
  .env okuma engeli, üretim-verisi silme engeli (`.claude/hooks/mitas_guard.py`)
- SessionStart hook: GUNLUK son kaydı her oturum açılışında otomatik yüklenir
- 4 MITAS-özel skill yazıldı (`.claude/skills/`): mitas-durum, mitas-benchmark,
  mitas-kunye-qc, mitas-konsey-kaydi. (film-ekle fikri Çağatay tarafından
  reddedildi — o MITAS otomasyonunun işi)

**Ek (aynı gün, devam 2):**
- Gerçek OCR-agent testi: `visual-analysis-ocr` agent'i AHLAT_AĞACI panorama
  görselinde çalıştırıldı — kalite çok iyi ama maliyet yüksek (~108K token,
  ~6dk/görsel). Prensip 2 uzantısı eklendi: maliyetli deneyler önce Çağatay
  onayı gerektirir (CLAUDE.md).
- `model_manifest.yaml`'a Claude-Vision-OCR resmi aday olarak eklendi.
- Konsey ilk GERÇEK kullanımı: yerel VLM fine-tune yol haritası için 2 turlu
  kırmızı-takım/açık-tur. 1. tur YANLIŞ ölçekle (400 dosya) brifing edildi,
  GLM "fine-tune'a girme" dedi. Gerçek ölçek (~2.000 film + 8-10K dizi +
  belgesel/müzik, sürekli büyüyen) ortaya çıkınca 2. tur açıldı, GLM fikrini
  TAMAMEN DEĞİŞTİRDİ: hibrit yaklaşım (yerel taslak + Claude hedefli
  düzeltme) onaylandı, fine-tune kararı veri birikene kadar ertelendi.
  Bkz. `docs/KONSEY_KARARLARI.md`, `docs/MITAS_VLM_Finetuning_Kunye_OCR_Plan_v1.md`.
  DERS: brifing kalitesi kararı doğrudan etkiliyor — yanlış ölçek yanlış
  tavsiyeye yol açtı.

**Ek (aynı gün, devam 3):**
- Konsey kapsamı genişletildi: sadece mimari/strateji değil, artık **kod
  incelemesi/bug avcılığı** için de kullanılıyor (`codex-review`'e ek).
  GLM/Qwen/Kimi'nin kod yeteneği de aktif kullanılacak. Mercek ataması: GLM
  güvenlik, Qwen performans, Kimi edge-case avcısı. CLAUDE.md güncellendi —
  "rutin hata teşhisi" (konsey dışı) ile "proaktif kod incelemesi" (konsey
  içi) net ayrıldı, karıştırılmasın diye özellikle işaretlendi.

**Bekleyen:**
- [ ] Kimi yeni anahtar → `/opt/mitas/council_mcp/.env` (Çağatay, işyerinde)
- [ ] Alibaba ödeme sorunu HÂLÂ ÇÖZÜLMEDİ (Çağatay) — Qwen 2 turdur cevap veremiyor
- [ ] Hibrit OCR hattı için pilot parti (10-20 film) — gerçek maliyet/kalite ölçümü
- [ ] Yeni skill'lerin ilk gerçek koşuda test edilmesi (özellikle mitas-kunye-qc)
- [ ] ~5-10K (taslak,düzeltme) çifti birikince: fine-tune kararını gerçek veriyle ver
- [ ] ~2 hafta sonra: konsey etki değerlendirmesi (karar kayıtlarından)
