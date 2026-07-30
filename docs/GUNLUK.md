# MITAS Proje Günlüğü

> Amaç: oturumlar arası süreklilik. Her Claude Code oturumu AÇILIŞTA son 2-3
> kaydı okur, KAPANIŞTA (veya önemli bir iş bitince) yeni kayıt ekler.
> Format: tarih + yapılan + öğrenilen/başarısız denemeler + bekleyen.
> En yeni kayıt EN ÜSTTE.

---

## 2026-07-30 (öğleden sonra) — TOPARLAMA: 17 Tem'den beri İLK uçtan uca Linux teslimi (YAĞMACILAR) + 5 kök fix

**Bağlam (Çağatay):** "Projeyi toparlayalım" — jenerik-başlangıç akışı finalde; 3-havuz
mimarisi + ASR aç/kapa öncesi pipeline denetimi istendi. 4 paralel keşif ajanı + kanıt
scriptleriyle denetlendi; FIGO'nun `_jenerik_pool.py:282`'ye bağlı olduğu canlı importla
teyit edildi. Sonra "önce 3 bug'ı temizle" → temizlik kazıdıkça derinleşti.

**ANA BULGU — Database'e 17 Tem'den beri üretim koşusu yazılmamıştı.** Kırık değil:
tüm çalışma kampanyaya (harness/, candidate_runs/) kaymış; 20 Tem'deki 100+
`flow_item_failed` = depo01 erişilemiyordu ("video bulunamadı"), pipeline suçsuz.
Kanıt koşusu: depo01/Film Kapanış'tan YAĞMACILAR (1970-0021-1-0000-90-1) 2 kez
uçtan uca koşuldu → hub + FIGO(found) + giriş havuzu(kept=65) + OCR cast=16 +
VL yönetmen=NATHAN JURAN (gerçekten doğru) + 341KB kunye.pdf + önizleme +
**qwen FINAL-QC Linux'ta İLK KEZ gerçek girdiyle koştu** (oyuncu=12, yön/yapımcı VAR).
Karar: Kontrol, tek neden "yönetmen VL-dolumu insan onayı" (meşru kapı).

**FIX'ler (hepsi TDD, commit'li):**
- b6960c4 video-VL 120sn kayması: `_pipe_video_vl` 600s sabitini kendisi varsayıyordu;
  pipeline artık `--win-start/--src-fps` iletiyor (dense deseni). Latent'ti (VIDEO_VL=0).
- c320ccdf **Path('') tuzağı**: `pdf_path=None` → `Path('')`=`Path('.')` DİZİN "var" →
  (1) surface: yedek arama atlanıp copy2('.') Errno 21; (2) export: md teslimi İPTAL +
  sahte .pdf yolu raporu. Fix: `.exists()` → `.is_file()` iki noktada.
- c320ccdf **fitz eksiği = "PDF render yok (md teslim)" kökü**: `_pipe_pdf` render bloğu
  `mp.build`'den ÖNCE `import fitz` yapıyor; venvs/asr'da PyMuPDF yoktu → TÜM Linux
  koşuları PDF'siz Kontrol'e düşüyordu (pdf_error kanıtı hub'da). PyMuPDF 1.28.0 kuruldu
  + requirements/asr.txt'e reportlab+PyMuPDF yazıldı.
- 936a12b `_make_pdf` özet-boşsa-panel-yok fix'i commit'lendi (ASR aç/kapa etkinleştirecek).
- a0268bd GUNLUK düzeltme: "giriş havuzu v5'ten beri üretilmemiş" YANILTICIYDI (sayım
  Database'e bakıyordu, koşular candidate_runs'taydı) + FIGO eski-ad artıkları temizlendi.

**Çevre kararları:** `Mitas Output/export/{KONTROL,ONAYLI}` 555 kilitliydi (13 Tem göç
artığı, Çağatay onayıyla 755) → Errno 13 çözüldü, YAĞMACILAR PDF'i KONTROL'e teslim
edildi. GPU çakışmadı (ollama TTL beklendi, Prensip 2).

**Bekleyen/bilinen:** (1) from-hub candidate re-OCR `No module named 'core'` ile
MOTOR_YOK üretip İYİ hub verisini gölgeliyor — ayrı iş çipi açıldı (EK_TAKS 29 Tem
MOTOR_YOK'u muhtemelen aynı kök). (2) İkinci koşu `YAĞMACILAR … 2` kardeş hub'ı
açtı (CLI'da reused-skip yok) — hangisi kalacak Çağatay kararı; PDF'li sağlam olan " 2".
(3) `export/KONTROL,ONAYLI`'da 0-bayt `.yazma_testi` dosyalarım kaldı (hook silmeme
izin vermiyor — elle silinebilir). (4) Test takımı baseline'ı 72 fail/11 error (benden
önce de; çoğu env-raporu + `fastapi`sız ocr-venv toplama hatası). (5) 4 test dosyası
commit'siz: test_kunye_cikar/test_ozet_kalite/test_ozet_v2_loop/test_deepseek_nvidia.
(6) SIRADA: ASR+özet aç/kapa (webui toggle; cu12 + killswitch testi önkoşul),
framehavuz'un hatta bağlanması (tasarım bekliyor).

## 2026-07-30 (gece) — Messi'nin 5 kayıp filmi teşhis edildi: 2 sahte kayıp, 3 gerçek (ortak desen: kayan kuyruk)

**Soru (Çağatay):** "Messi net olarak 'ben kaybettim' der mi? O 5 filmi bulabilir miyiz?"
**Cevap:** Motor kendisi DEMİYOR (alarm 5/5 sessiz — alarm yalnız kar-fırtınası
patolojisi için; içerik kaçırma referanssız bilinemez). Ama dış hakemle bulundu:
ham-kare Paddle taraması (kare→token haritası) + Messi yeniden-koşum (alarm/istatistik)
+ 5 paralel görsel-doğrulama ajanı (her kayıp token gerçek karede gözle kontrol).

**Hükümler (gözle doğrulanmış):**
- havaci 0.14 → SAHTE kayıp: kaybın ~%91'i Paddle garble (soamdmiser=Sound Mixer).
  Deepseek TEMİZ okuduğu için exact-token eşleşmiyor — iyi okuduğuna ceza. İçerik tam.
- sihirli-flut 0.643 → SAHTE: var_n=14, kayıp 5 = etiket/garble; seçim kusursuz;
  Messi Paddle'ın hiç göremediği krediyi bile okumuş (Resim Kayıt / HAYRI KOÇ).
- define-adasi 0.292 → GERÇEK SEÇİM KAYBI: kayan kuyruk 563-597 komple atlandı
  (Aaron Crippen, Barbara Lee, Christy Buskirk…). Otsu eşiği 41'e fırlamış →
  yavaş-kayan roll'da fark hep eşik-altı → dev grup, tek temsilci.
- tas-devri 0.229 → GERÇEK SEÇİM KAYBI: aynı desen (eşik 34), 186-198 orta bant
  atlandı (Arthur Pierson, Hoyt Curtin, Charles Nichols, Howard Hanson).
- rhum-bulvari 0.277 → KARIŞIK: çoğu Fransızca-garble artefaktı; 1 somut gerçek
  kayıp: AZZI/MORAND sayfası (562/564) — grup açıldı ama temsilcisiz kaldı.

**İki yapısal çıkarım (karar Çağatay'da):**
1. ÖLÇÜM: exact-token recall Messi'yi sistematik DÜŞÜK gösteriyor (deepseek temiz
   okur → Paddle-garble var-setiyle eşleşmez); adaptif kolu Paddle-Paddle şişkin.
   Fix adayı: edit-distance≤1 fuzzy veya KB-isim-tabanlı recall. 40-film tablosu
   bu düzeltmeyle yeniden okunmalı — fh muhtemelen gerçekte önde/başabaş.
2. MOTOR: tek gerçek zaaf deseni = kayan (rolling) kuyrukta yüksek Otsu eşiği +
   birikim kuralının yetmemesi. OCR'sız fix adayı: birikimli-kayma her kare-boyu
   katında zorunlu sayfa + "grup açıldıysa temsilcisiz kapanamaz" kuralı.
   İkinci-geçiş sigortası ateşlemiş (3-4 ek sayfa) ama rulo için yetersiz kalmış.

**Araçlar:** scratchpad/teshis_topla.py (sıralı GPU-güvenli toplayıcı),
teshis/OZET.json + film JSON'ları, workflow wf_36f2e539 (5 ajan, görsel kanıtlı).

---

## 2026-07-30 (akşam) — Tek-motor temizlik cerrahisi: text_layer + compose_hybrid söküldü, jenerik primitifleri taşındı

**Çağatay kararları:** (1) panoramik deneme (uret_ex + panoramic_composer) sadece
denendi — loş filmde eriyor, sunum-fazına ertelendi; (2) dynamic_credit_mosaic'in
5 canlı primitifi "aktif projenin köşesine, görevi yazılı" taşınacak (İbrahimovic
altına DEĞİL — bunlar dedektörün araçları); (3) text_layer_* ve compose_hybrid SİL.

**Yapılan (3 commit):**
- `03d4804` — `core/pipelines/ocr/jenerik_primitifleri.py` doğdu: _build_tophat_mask /
  _phase_corr / _gdiff / _masked_gray / _hann2d + CC sabitleri, görev/soy/tüketici
  docstring'de. jenerik_detector importu çevrildi; slitscan/ klasörü (mozaik
  prototipi + panorama + runner'lar, 1955 satır) silindi.
- `8cf7930a` — text_layer kümesi silindi (descroll, row_reconstruct, 2 CLI, 2 test,
  Windows yol_runner). Canlı dosyalarda 3 dikiş: credit_experiment hook'u
  status=removed; unified scroll-canvas dalı → A-fb emniyet ağı no_composite ile
  track-fallback'e düşer (scroll metni kaybolmaz); selector'ın ölü önerisi çıktı.
- `0fd31195` — pipeline100 görsel dalı söküldü (340→91 satır): compose_hybrid +
  line-mozaik yardımcıları + slitscan2 gitti; main() metin-only (stx.runs_of +
  stitch_kunye). _pipe_ocr e.1 bayrak bloğu + master_png çıktı anahtarları
  kaldırıldı. outputs/ altındaki 3 alternatif master-üretici/probe silindi.

**Doğrulama:** box_track+scene_router+police 17p/3s; messi+box+router 42p/1s;
frame_dedup 9p; jenerik_detector import+mask smoke; pl modül-yükleme smoke
(MITAS_PROJECT_ROOT ile cp/cl/stx zinciri). Yanlış-alarm dersi:
_pipe_shadow_vl'deki `dcm` = db_compose_master (V2 dosyası), dynamic_credit_mosaic
DEĞİL — VL hattı etkilenmedi.

**Bekleyen:** kapanış paketi — konsey kapanış cevabı sentezi (Nemotron ilk turu
dahil), 5 fh-kaybı filmi teşhisi (havaci, sihirli-flut, define-adasi, rhum-bulvari,
tas-devri), branş-bütünü final inceleme. uret_ex + panoramic_composer'ın kaderi
Çağatay'da (commitlenmemiş satırları duruyor, dokunulmadı).

---

## 2026-07-30 (öğle) — 3090'da YEREL ÖZET motoru: ölçüm yatağı + ilk tur (PARÇALAMA kazandı, TOPLAMA kaldı)

**İş (Çağatay siparişi):** Tam film transkriptinden 3-4 cümlelik spoiler'lı künye özetini
buluttan (DeepSeek/Gemini/Sonnet) 3090'a taşımak. Gerekçe: kota/maliyet + dış bağımlılık;
bulut hakem ve yedek olarak masada kalıyor.

**Kurulan — `harness/ozet_motor/`** (eval-harness-first):
- `eval/goldens.jsonl` — **136 film**, transkript + AYNI transkriptten üretilmiş **Sonnet referansı**
  (`_log.jsonl: ozet_completed`). Altın standart bedava geldi; ayrıca <800 kelime transkriptler
  elendi (bir filmde 4 kelime çıkmıştı = ASR başarısız, motor sınavı değil).
- `eval/graders.py` — 3 kova: B1 biçim (üretimin kendi `_ozet_kalite` kapısı), B2 dil
  (garble/İngilizce/tekrar/think-sızıntısı), B3 olgu (Sonnet'e karşı ad-isabeti + içerik).
- `motorlar.py` — arka uç soyut (Ollama|VLLM), şekil `tek_atis` | `cikar_ozetle`.
- `sunucu.sh` (vLLM :8101, VRAM kapılı), `kos.py`, `nobetci.sh` (VRAM tabanlı bekleyici).

**SONUÇ — Qwen3-8B FP16, 32k bağlam, 6 film (1.4k–13k kelime):**

| kol | kapı | dil | **ad-isabet** | ort sn | ort kelime |
|---|---|---|---|---|---|
| tek_atis | 3/6 | 3/6 | **0.36** | 13.4 | 175 |
| cikar_ozetle | 0/6 | 2/6 | **0.75** | 29.8 | 82 |

- **Parçalama olgu sadakatini GERÇEKTEN düzeltiyor:** ad-isabeti ölçülebilen **5 filmin 5'inde**
  de kazandı. En çarpıcısı KORKUNÇ GECE **0.00 → 0.75** (tek-atış ana karakteri komple ıskaladı).
  Bu, bake-off'un "B: kim-kime tersine" kovası — ve parçalama onu kapatıyor.
- **En uzun filmde (12.964 kelime) tek-atış ÇÖKTÜ: 744 kelime.** Parçalı 51 kelime verdi.
  Uzun filmde tek-atış seçenek değil.
- **Ama parçalı biçim kapısından 0/6 geçti** (71-125 kelime, sınır 65) ve çıktı "özet" değil
  **olay listesinin düzyazısı** — promptun yasakladığı yöntem/prosedür anlatımı.
- **TEŞHİS: darboğaz ÇIKARMA değil TOPLAMA.** 8B doğru olguları buluyor ama olay listesini
  40-60 kelimelik bir yaya SIKIŞTIRAMIYOR. Sıkıştırma kavrama ister.

**BAĞIMSIZ BULGU — üretim promptu altın-örneği SIZDIRIYOR (2/12 çıktı):** `ozet_film_v2.txt`'deki
Jean Picard örneği kopyalanıyor. En net vaka **AYI YOGİ** (çizgi film, piknik sepeti çalan ayı) →
*"Ancak Yogi, aslında bir sahte sabotajcı olarak kendini feda eder."* Model emin olamayınca örneği
şablon gibi dolduruyor. ÇİÇEK TAKSİ VL kaydındaki sahte-künye halüsinasyonuyla **aynı hastalık**.
Prompt şu an ÜRETİMDE CANLI — ayrı kalem olarak ele alınacak, henüz dokunulmadı.

**KONSEY (kırmızı takım; GLM + Nemotron cevapladı, Kimi kotasız, MiniMax düştü):** sığ onay değil,
gerçek hasar buldu — hepsi uygulandı:
1. **GERÇEK BUG:** son parça hem olay-döngüsünde hem `_FINAL_SORU`'da işleniyordu → çelişkili girdi.
2. Karakterden bölme repliği ortadan kesiyordu → **satır sınırından** bölme.
3. Parçalar arası coreference kopuğu (parçalamanın tek-atıştan DAHA KÖTÜ olabileceği tek yer) →
   transkriptten deterministik **kanonik kişi listesi** her parçaya taşınıyor. Bu düzeltme kendini
   ödedi: çıkarılan adlar Sonnet referanslarıyla birebir örtüşüyor (Waldo/Tornicraft/Beverly,
   Letizia/Laroş, Marc/Camille/Odile). Ad-isabetindeki 0.36→0.75 sıçraması büyük ölçüde bundan.
4. Final son 1/6 değil **son 1/3**'ten + "çelişirse bu doğrudur" etiketi (çerçeve-hikâyeli filmler).
5. Madde/token bütçesi parça uzunluğuna göre ölçekleniyor.
- REDDEDİLDİ: Nemotron'un "8B tek-atışa dön + LoRA eğit" önerisi — ölçmeden hüküm veriyor.

**BAŞARISIZ DENEMELER / ÖĞRENİLENLER (tekrarlanmasın):**
- **32B-AWQ 3090'da bıçak sırtı, 3 kez OOM.** Ölçülmüş reçete: `--gpu-memory-utilization 0.93
  --max-model-len 10240 --kv-cache-dtype fp8 --enforce-eager`. Sırasıyla çarpılan duvarlar:
  (a) 0.92 util + 16k → KV'ye 1.39 GiB kalıyor, 2.0 GiB gerekiyor; (b) 0.95 → masaüstü 1.3 GB
  tuttuğu için toplam bütçe aşılıyor (22.24 boş < 22.38 istek); (c) graph yakalama OOM →
  **`--enforce-eager` ZORUNLU** (vlm_sunucu.sh de aynı sebeple eager). Ağırlık yükü 19.42 GiB.
- **ollama sabit 4096 bağlam KULLANMIYOR** (0.32.0): modele göre 8192/32768 seçiyor. Ama üretim
  `_ozet_gemma_local` `num_ctx` HİÇ vermiyor → uzun filmde ollama'nın insafında. Harness açıkça veriyor.
- **Grader körlüğü:** Sonnet referansları künyede TAMAMI BÜYÜK HARF; Title-Case regex referansta
  hiç ad bulamıyordu → `ad_isabet` hep None. Düzeltildi: kanonik ad kümesi TRANSKRİPTTEN çıkarılıp
  iki tarafta da ASCII-katlanmış aranıyor.
- **İsim çıkarıcı cümle-başı tuzağı:** "Ben/Sen/Bana/Çok" ad sanılıyordu. Çözüm: bir sözcük ancak
  CÜMLE ORTASINDA ≥2 kez büyük harfle geçerse ad sayılır.
- **ASR aynı ismi birden çok yazıyor** (Letizia/Leticia, Jules/Jül, Waldo/Valdo). Şimdilik ikisi de
  modele veriliyor; ileride bulanık eşleştirmeyle birleştirme gerekebilir. NOT EDİLDİ, dokunulmadı.
- **GPU ÇAKIŞMASI:** aynı kartta 3 paralel Claude oturumu iş koşturdu; tur 3 kez kesildi.
  ⚠️ **`harness/kunye_kiyas/olc_pool.py` ARA KAYIT YAZMIYOR** (yalnız bitişte `olcum_son.json`),
  önbelleği süreç-içi RAM. Çağatay talimatıyla durduruldu → ~50 dk iş sıfırdan. **TUZAK:**
  `olcum_son.json` durdurulduktan sonra da 11:18'in dosyası kaldı → onu bekleyen oturum
  BASELINE ile eski dosyayı kıyaslayıp **sahte YEŞİL** okuyabilir. 11:18 sonucu
  `veri/olcum_son_11-18_YEDEK.json` olarak yedeklendi.

### EK TUR (öğleden sonra) — TOPLAYICI ekseni: biçim ÇÖZÜLDÜ, sadakat ÇÖZÜLMEDİ

Çağatay "hepsini dene, diğer akışları kesebilirsin" dedi. `toplayici_turu.py` yazıldı: kayıtlı olay
listelerinden (runs/*/results.json → `ara_urun`) YALNIZ son adım koşuluyor, çıkarma tekrarlanmıyor
→ kıyas adil (herkes aynı listeyi görür), ucuz (film başına tek çağrı, ~2.6k token), VRAM'i az.

| toplayıcı | kapı | dil | ad-isabet | ort kelime |
|---|---|---|---|---|
| qwen36-35b-test | **6/6** | 5/6 | 0.65 | 46 |
| qwen36-27b-test | 5/6 | 4/6 | 0.68 | 43 |
| gemma4:26b | 4/6 | **6/6** | 0.58 | 44 |
| mistral-small3.2 | 3/6 | 4/6 | 0.64 | 62 |
| 8B (kendi toplaması) | 0/6 | 2/6 | 0.75 | 82 |

**ÇÖZÜLEN:** toplama adımının BİÇİM tarafı yerelde bitti — 39-53 kelime, akıcı Türkçe, ~2 sn.
8B'nin 0/6'sına karşı 26-35B sınıfı 4-6/6. Notlardan özet yazmak, ham transkripti kavramaktan
KOLAY bir görev; bake-off'ta bu modellerin çuvalladığı iş bu değildi.

**ÇÖZÜLMEYEN — ve darboğaz YER DEĞİŞTİRDİ:** olgu sadakati. Gözle okuma vekil ölçütü yalanlıyor:
- HAYAT BİR ŞARKIDIR: 8B'nin FİNAL bloğu YANLIŞ (Camille'in depresyondan hastaneye kaldırılmasını
  final sanmış); iki toplayıcı da bunu sadakatle cilaladı.
- AYI YOGİ: final bloğunda ASR çöpü ("Korucu Simit Celis Don'un başkorucusu oldu") → cümleye çevrildi.
- KANDAHAR: iki toplayıcı da "Sonunda Ami ile kavuşur" dedi. "Ami" ASR gürültüsü.
→ **CİLALI ÇÖP, DAĞINIK ÇÖPTEN TEHLİKELİ.** 8B'nin 82 kelimelik dağınık çıktısı bozuk olduğunu belli
  ediyordu; 42 kelimelik akıcı künye özeti etmiyor. Kalite kapısı BİÇİME bakıyor, OLGUYA değil —
  B1/B2 kapısı bu hata sınıfını göremez. GLM'in "cascade hallucination" uyarısı çıktı düzeyinde teyitli.

**⚠ BENİM METODOLOJİ HATAM (kayda geçsin):** Konsey brifinginde olay listelerini ELLE ÖZETLEDİM ve
listede OLMAYAN olgular enjekte ettim — HAYAT BİR ŞARKIDIR için "Marc beyin tümöründen ölür" yazdım,
oysa 8B'nin notlarında "tümör"/"beyin" HİÇ GEÇMİYOR (filmin gerçek konusunu bildiğim için farkında
olmadan uydurdum). Dolayısıyla **"GLM 3/3 geçti → mimari doğrulandı" sonucu GEÇERSİZDİR**; GLM
temizlenmiş+kısmen uydurulmuş notlardan, yerel modeller ham notlardan çalıştı. CLAUDE.md'nin
"brifing özet değil GERÇEK içerik" kuralı tam da bunun için var — ihlal edildi, sonuç yanıltıcı oldu.
Bundan sonra konseye giden her veri parçası ham dosyadan KOPYALANACAK, elle yeniden yazılmayacak.

**32B-AWQ — VRAM DEĞİL, YAZILIM:** `RuntimeError: torch_call_dispatcher("aten::empty", ...)` —
vLLM 0.25.1 / torch AWQ çekirdeği uyuşmazlığı. Bellek reçetesi doğruydu (0.93 util + 10240 +
fp8 KV + enforce-eager ile ağırlık 19.42 GiB yüklendi), engel sürüm. **Beklemekle düzelmez.**

**BEKLEYEN (güncel):**
1. **Kaldıraç artık ÇIKARMA tarafında** — toplayıcıyı büyütmek işe yaramaz, o taraf çalışıyor.
   Adaylar: final turunu 8B yerine 26B'ye vermek (tek çağrı, ucuz), ASR gürültü süzgeci,
   "net değil" demeyi gerçekten öğretmek.
2. **B3 grader yetersiz** — ad-isabeti yanlış finali/uydurma olguyu görmüyor. Sadakat için
   gerçek hakem (farklı aile LLM-jüri, kalibreli) gerekiyor; şimdiki vekil YANILTIYOR.
3. Prompt altın-örneği sızıntısı — üretim `ozet_film_v2.txt` kalemi (2/12 çıktı; AYI YOGİ vakası).
4. 32B için vLLM/torch sürüm işi — ayrı kalem.
5. Tasarım kararı (hat içi / gece geçişi) hâlâ AÇIK.

---

## 2026-07-30 (gece 3b) — ÇİÇEK TAKSİ b001 (dizi): v5 çıkış tespiti + 30sn video-VL okuma

**İş (Çağatay siparişi):** depo01 DİZİLER/ÇİÇEK TAKSİ bölüm 001 (2001-9011, 61:29)
→ standart pipeline ile çıkış jeneriği başlangıcı → segmenti 30sn+5sn bindirmeli
parçalara kesip video olarak VL'e okutma ("okuduğun her şeyi yaz").

**Tespit:** havuz sözleşmesi kareler (son 600s@1.5fps, 900 kare) → `_jenerik_pool`
v5: **found, start_pos=716 → 59:26.4**, tip=statik, güven 1.00, motorun kendisi
(rescue yok), aday=2 seçilen=[721-811] kb=1.00 joint=1.77. Görsel teyit: c_0722
"TOFAŞ FIAT teşekkür" (gerçek ilk kart ~59:29; 716 pad'li üretim değeri). Dizi
profili diye özel bir şey GEREKMEDİ — Çağatay'ın dediği gibi normal prensip yetti.

**VL okuma:** `vlm_sunucu.sh` (Qwen3-VL-8B) + `_pipe_video_vl` PENCERE=30/BINDIRME=5
+ "her şeyi yaz" SORU'su — üretim koduna dokunulmadı, monkeypatch koşucu:
`filmtest/dizi_cikis_vl/CICEK_TAKSI_b001/vl_okuma_kosucu.py`. 6/6 parça okundu.
- Parça 0+2 TEMİZ kart-kart okuma: "1. bölümün sonu", TOFAŞ, yapım ULUSAL RADYO,
  konuk oyuncular(9), teknik ekip kartları; sponsor LOGO kartları dahil (Euro Flora,
  ÇAMLICA ÖMÜR HASTANESİ, Red WALKER...). Türkçe diakritik hataları az (EKSIOLGU).
- Parça 1 TEKRAR-DEJENERASYONU: kalan tüm ekip kartlarını tek blokta birleştirip
  aynı bloğu 7 "kare" diye 7 kez bastı (68s, 5.5KB) — içerik doğru, kare-ayrımı çöktü.
  Mevcut _dejenerasyon_filtresi satır-düzeyi olduğundan blok tekrarını YAKALAMIYOR.
- Parça 3/4 (siyah kuyruk): dürüst "[Ekran tamamen siyah.]".
- Parça 5 (2.7s siyah artık): **TAM SAHTE KÜNYE halüsinasyonu** — "KARAKTER FILM
  STUDIO - 2024", "YÖNETMEN ALİ KARABULUT"... SORU'daki etiket listesini şablon
  gibi doldurdu ("Sponsor", "Logo Üstü Yazı" başlıklarını aynen kullandı!). Siyah
  girdide davranış STOKASTİK (3/4 dürüst, 5 uydurdu) — kunye_cikar uydurma-süzgeci
  ihtiyacının kare-kanıtı. Kısa/boş kuyruk parçası VL'e HİÇ verilmemeli (ör. son
  parça <10s ve siyahsa atla) — ileride değerlendirilecek.

**Başarısız/öğrenilen:** (1) v5 CPU'da KOŞAMAZ — paddle oneDNN/PIR
`NotImplementedError` (PP-OCRv5_server_det); GPU şart. (2) CPU denemesi CV→
vlm_rescue'ya düşüp ollama kuyruğunda ASILI kaldı (paralel oturumun 19.4GB modeli
ollama'yı tutuyordu) — süreç öldürüldü. (3) GPU'yu paralel oturumla paylaşırken
monitörle beklemek işe yaradı (Prensip 2: kimsenin işi bozulmadı). (4) Dizi
ÇIKIŞINDA yönetmen/başrol kartı YOK (crew+konuk+sponsor) — ana künye muhtemelen
giriş jeneriğinde; dizi künyesi için giriş okuması gerekecek.

**Durum:** vLLM 8100'de AÇIK bırakıldı (kapat: `kurulum/vlm_sunucu.sh stop`).
Çıktılar: `filmtest/dizi_cikis_vl/CICEK_TAKSI_b001/` (jenerik_detection.json,
video_vl/video_vl_okuma.txt, parçalar).

**EK (aynı gece, r2/r3 + MODEL TURU):** Çağatay ayar+model karşılaştırması istedi.
- **r2** (20sn/5sn, maxtok 3500, rep 1.1, siyah-atlama): siyah parçalar 0 token'la
  elendi ✓ ama kare-kare istem YENİ dejenerasyon üretti (TOFAŞ kartına kilitlenip
  21 "kare" bastı, 123sn). **Kök sebep istem şekli**: statik kartta "her kareyi ayrı
  yaz" tekrarı GÖREV gereği zorluyor.
- **r3 = kart-tekil istem** ("her FARKLI kartı bir kez"): dejenerasyon SIFIR, 5 gerçek
  parça toplam ~35sn, temiz kart-kart çıktı. Koşucu: `vl_okuma_kosucu.py`
  (VL_SORU_MOD=kart varsayılan; üretim _pipe_video_vl'ye dokunulmadı).
- **MODEL TURU** (`model_turu.sh` v3; kart-istem, aynı 9 parça, GT=kareden gözle
  doğrulanmış 11 zor isim): **MiniCPM-V-4.5 8/11 TAM** (~37sn, 2.1k tok/parça) >
  30B-A3B-AWQ 5/11 (~74sn, yavaş) > InternVL3.5-8B 4/11 (hızlı ama ÖTAŞ/YAVID sınıfı
  ağır bozulma + markdown disiplinsizliği) > **mevcut 8B 3/11**. SÜLÜN/ŞENYUVA/NİHAN
  gibi Türkçe yazımları tek doğru yakalayan MiniCPM.
- **Donanım elemeleri (kesin):** Nemotron-Nano-12B-v2-VL-FP8 → modelopt SM89+ ister,
  3090=SM86, ÇALIŞMAZ. Kimi-VL-A3B bf16 31G sığmaz. Qwen3-VL-32B-AWQ ağırlık sığıyor
  ama KV'ye 0.16G kalıyor (video için ~2G lazım) → video işinde kullanılamaz.
- **Ops dersleri:** (1) vLLM turlarında stop sonrası VRAM salımı BEKLENMELİ (v1 turu
  ardışık OOM yedi). (2) Paralel oturumun ollama işi (qwen_toplu.py) model düşürüp geri
  yükleyerek ping-pong yapıyor — anlık boş VRAM görüp başlamak YETMEZ; süreç-yokluğu
  debounce'lu kapı gerekti (v3). Çağatay onayıyla paralel iş durdurulup tur araya girdi.
- **SIRADA:** MiniCPM-V-4.5 tek dizi/tek bölümde öne çıktı — motor kararı İÇİN DEĞİL
  (eval-harness-first: film yatağı + daha çok bölümle benchmark + konsey turu gerekir).

## 2026-07-30 (kapanış) — FIGO doğdu: temizlik + rename + net pipeline bağlama (92aee5e, 59379b3)

**Çağatay kararı:** "Jenerik bulma modelinin adı FIGO. Projede sadece bu iş
kalsın, net pipeline'a bağla — 'şurada da jenerik bulma var' karışıklığı bitsin."

**FIGO = `/opt/mitas/harness/kunye_kiyas/figo.py`** (eski credit_onset.py, git mv;
import edenler güncellendi: _jenerik_pool/olc_pool/hata_atlasi/det_isit).
Kimlik kartı: `docs/FIGO.md` (path'ler, zincir, skor, bayraklar, FIGO-olmayanlar).

**TEMİZLİK (tümü tüketicisiz doğrulandı, 12 dosya):** jenerik_start_eval +
jenerik_label_sheets (eski GT-etiketleme), test_gt/asama1_v2/apply_trim/
repool_all_hybrid (eski onset harness), phase2_vlm_rescue/phase3_verify_fix/
test_fullscan/test_resolution (eski VLM sürücüleri), batch_v5/_gecici_eski_kuru_
parite (artefakt). 17 ölçüm snapshot'ı → veri/arsiv_olcum/. SİLİNMEYENLER
(başka işlerin bağımlılığı — FIGO.md'de belgeli): jenerik_frame_pool_detector
(giriş-havuzu + FIGO-HATA fail-safe), jenerik_oneocr_detector, credit_start_vlm,
cikis_tail_scan/giris_trailing_trim.

**PİPELİNE NET BAĞLAMA:** `MITAS_JENERIK_METIN_KAPI=1` kök mitas.env + linux/
şablon (drift önlemi). Kredisizde eski CV DEVRALMAZ — FIGO son söz.
⚠️ OPERASYONEL: systemd mitas-asr env'i başlangıçta okur — METIN_KAPI'nin
canlı servise geçmesi için `systemctl restart mitas-asr` gerekir (Çağatay kararı).

**KAPILAR:** rename sonrası 110-film BİREBİR (104/%94.5/%97.3/kredi-yok 29/29,
hata-fark yok) + kredisiz duman: AMY → status=kredi_yok, engine=v5_kredi_yok,
havuz=0, CV KOŞMADI ✓. Codex-review borcu: Çağatay "GLM de olur, önemli değil"
dedi — GLM zaten 2 kod-turu yaptı, borç kapalı sayıldı.

## 2026-07-30 (akşam) — ŞÜPHE KATMANI indi (konsey-gardlı); zor-grup avı kapandı; FINAL koşu birebir

**Tetikleyen:** Çağatay: "zor grupta elimizden geleni yapalım, denemeden bırakmak
olmaz; sorun olduğunu BİLİRSEK gerekirse tüm havuzu alırız, yoksa isim kaçar PDF
şaşar" + "son kez tam koşu, bozmadığımızdan emin olalım" + skill eleştirisi.

**ŞÜPHE KATMANI (de4708b + 3f45c91 + 63f19f5):** Sonuc.suphe (davranış-NÖTR):
gec_riski (kazanan önünde birleşememiş + ≥%65 okunamaz komşu blok — İNİŞLİ ✓
yanıyor; KNUTE bilinen yanlış-pozitif, kabul), erken_riski (Latin kazanan + baş
%80 kart-değil — HARİKA yapısal olarak YAKALANMIYOR: footage markaları AQUAFINA/
VOLLEYBALL kart gibi okunuyor, dürüst sınır), parcalanma_riski (seyrek-kart
etiketi). Manifest v5.suphe + v5_izleme ŞÜPHE KUYRUĞU. MITAS_JENERIK_SUPHE_
GENIS_HAVUZ bayrağı (default KAPALI): açıkken gec_riski'nde havuz elenen-aday
başından, tavan 120 kare, YALNIZ kazanan varken (kredisizde asla — AMY dersi).
Mekanizma monkeypatch'le kanıtlı (853'e çekiyor, 120-tavan kesiyor). Dış konsey
(GLM+Nemotron) gardları: %65-70 eşik, kredi_var kilidi, Kiril muafiyeti.
110-film şüphe-ORANI ölçülmedi — ilk üretim koşularında v5_izleme gösterecek.

**ZOR-GRUP AVI SONUÇ:** HARİKA için scroll-dal içerik-çapası DENENDİ-ELENDİ
(HARİKA+İKİ_KAFADAR düzeldi AMA SEN_TOM+132/KAHRAMAN+90/KAPAN+84 GEÇ bozuldu —
seyrek-kart jenerikleri footage'dan ucuz sinyalle AYIRT EDİLEMİYOR: 'Sascha
Oliver Engl' 2-isim kartı vs 'SPEEDO/COACH' footage'ı satır/kart/rol'de özdeş;
geri alındı). YALNIZ: TV-bandı her karede kart=True, jenerik başı çöp — hiçbir
içerik sinyali ayırt etmiyor. Kalan 6 hata: 3 üretim (YALNIZ/HARİKA/İNİŞLİ —
hepsi dar-VLM sınıfı, İNİŞLİ artık ŞÜPHEDE GÖRÜNÜR), 3 simetrik-only (üretimde
doğru). OCR-tabanlı av resmen kapandı.

**FINAL KOŞU (Çağatay şartı) BİREBİR:** 104/110 %94.5 · üretim 107/110 %97.3 ·
kredi-yok 29/29 · hata-fark YOK — tüm deneme geri-alımları temiz kanıtlandı.
(İlk final denemesi 2 kez düştü: (1) göreli-yol sessiz-hata — olc_pool.py'yi
cwd'den çağırma, MUTLAK yol kullan + rc kontrol et; (2) SIGABRT — GPU'da paralel
oturum 23GB doluyken; paralel 6 ile temiz.)

**SKILL DİSİPLİNİ (Çağatay eleştirisi, hafızaya işlendi):** skill İÇERİĞİNİ
taklit etmek yetmez — Skill tool'uyla INVOKE et; kritik commit zincirinde
codex-review atlandı (bu oturumda 15+ commit codex-review'suz — borç olarak
kayıtlı). verification-before-completion yüklendi, Iron Law uygulandı.

**KONSEY DURUMU:** GLM aktif+değerli (2 kırmızı-takım turu tasarımı değiştirdi),
Nemotron aktif, Kimi 429-bakiye, MiniMax düzensiz, Gemini+GPT anahtarları VAR
ama son turlarda SESSİZ düşüyor (teşhis: anahtar_test.py — bekleyen iş),
Qwen anahtarı hiç girilmemiş.

## 2026-07-30 (öğlen) — HATA AVI: GELECEK düzeldi (%93.6→%94.5!), İNİŞLİ çözülemez sınıf, kalan-5 haritalandı

**Tetikleyen:** Çağatay: "İNİŞLİ'de jenerik çok net, neden çözmüyoruz? Kalan 5'e de bakalım."

**🎯 GELECEK_GÜNLER +91→+1 (390e04b): İLK GERÇEK DOĞRULUK ARTIŞI.** GT %93.6→%94.5
(104/110), üretim %96.4→%97.3 (107/110), kredi-yok 29/29, başka film oynamadı.
Yeni baseline sabit: olcum_BASELINE_9455.json (90a8d81). Kök: _kart_dizisi_geri_
genislet zinciri 743-733 arası 6'lık boşlukta (dissolve+n=3 ara kareler) kopuyordu
→ bosluk_tol 4→6 (tek parametre). Teşhis yöntemi: kare-kare kart_mi anatomisi
(672-763'te 27 kalifiye kart bulundu — ISABELLE HUPPERT...Produit par).

**İNİŞLİ +89 = ÇÖZÜLEMEZ SINIF (3 yol denendi, 3'ü veriyle elendi):**
(1) sınırsız nötr-köprüleme → AMY kredisizde SAHTE onset (28/29 kırmızı çizgi,
geri alındı; ayrıca KNUTE -129, HAYATIMIN -86 yeni hatalar). (2) tavanlı köprüleme
→ köprü-anatomi ölçümü İMKANSIZ dedi: İNİŞLİ'nin köprülenecek gap'i (nötr=12/14)
ile KNUTE'nin kesilecek gap'i (nötr=12/20) AYNI nötr değerde — sayaç ayıramaz.
(3) _gecis_icerik_onayi'ye AR ikinci-şansı (salt-ekleyici, ≥2 farklı AR-rol) →
zincir kapıya ULAŞIYOR (bosluk 14≤45 ✓) ama Farsça KIRMIZI KALİGRAFİ Paddle-AR'de
de OKUNMUYOR (kareler 'ابلاز/افد' kırıntı, roller_ar=[]) → içerik kanıtı üretilemez
→ geri alındı (YAGNI: hedefini ıskalayan kod kalmaz). İNİŞLİ 'okunamayan-kaligrafi
tek-yazı kart' sınıfı → dar-VLM adayı.

**KALAN-5 HARİTASI (Çağatay 'belki kolay fix' — cevap: HAYIR):**
- YALNIZ_SAVAŞÇI -190 + HARİKA -124 + KIZIL_HAYAT -63: AYNI SINIF = 'film-içi
  ekran-metni yapışması' (TV haber bandı 'LAURA NEWTON' / plaj grafikleri / MOULIN
  ROUGE neonları kutu üretip jeneriğe yapışıyor) — kampanyanın dar-VLM'e bıraktığı
  sınıf, kolay fix YOK. Yalnız ilk ikisi üretim hatası; KIZIL üretimde doğru.
- İKİ_KAFADAR -67 (dissolve bindirmesi) + TESS -37 (Fransızca epilog ara-yazısı):
  üretim ölçütünde ZATEN DOĞRU, simetrik-only.
ÖZET: üretim ölçütünde gerçek hatalar 3'e indi (YALNIZ/HARİKA/İNİŞLİ), üçü de
dar-VLM sınıfı. OCR-tabanlı kolay kazanımlar TÜKENDİ.

**Yan olay:** kalan-5 teşhisinde tek-süreç çoklu-model birikimi CUDA 700 çökmesi
verdi → film-başına izole süreç deseniyle çözüldü (GUNLUK'teki 'v5 GPU şart'
notunun kardeşi: uzun teşhis döngülerinde süreç-başına-film).

## 2026-07-30 (sabah 2) — Farsça tetik boşluğu KAPANDI (c2f131e); koşu-devam denemesi kırmızı çizgiden GERİ ALINDI

**1) FARSÇA TETİK FIX (c2f131e, TDD: RED→GREEN→kapı birebir):** Mercek-4 boşluğu
kapatıldı. `en_bos_kare` artık kırıntı-kareleri (alpha≥4-harf token'sız satırlar,
'<_ III1') boş sayıyor — SALT-GEVŞETME (tetiklenen vaka tetiklenmez olamaz;
oransal-eşik alternatifi küçük örneklemde sıkılaştırdığı için reddedildi).
RED: monkeypatch EN-rec→kırıntı, KANDAHAR kredi_yok'a düştü (2 varyant).
GREEN: fix sonrası bulundu (+5). 110-film kapısı BİREBİR 103/29-29.
Repro: scratchpad/farsca_tetik_repro.py (commit'lenmedi, tek seferlik).

**2) İNİŞLİ TEŞHİSİ (Çağatay 'jenerik çok net, neden çözmüyoruz'):** Kök sebep
DİL DEĞİL, GEOMETRİ — 917-937 arası kartlar TEK-yazı (Farsça kaligrafi tek
rol/isim) → credit_box `n>=2` kuralı jbayrak=False → koşu BÖLÜNDÜ → ilk parça
(853-915, GT 862'yi içeriyor!) SON_ERISIM'e takılıp elendi → +89 GEÇ. GELECEK
(+91) akraba sınıf ama farklı: tek-isim bölgesinde koşu HİÇ BAŞLAMIYOR.

**3) KOŞU-DEVAM FIX DENEMESİ → GERİ ALINDI (kırmızı çizgi çalıştı):** 'n=1
kareler koşuyu kesmesin (nötr)' fix'i İNİŞLİ'yi düzeltti (+89→-85 güvenli yön)
AMA 110-filmde: kredi-yok 28/29 (AMY'NİN_TALİHSİZLİKLERİ kredisizde SAHTE onset
1159 — nötr kareler sınırsız köprü kurup kutu-bölgesini sona bağladı), KNUTE
-129 ve HAYATIMIN_ERKEĞİ -86 yeni hatalar, genel %90.9. git checkout ile geri
alındı, baseline doğrulandı. DERS: nötr köprüleme TAVANSIZ olamaz — gelecekte
denenecekse nötr-sayaca üst sınır (ör. ≤8 örnek-indeks) + kredisiz-set ön-testi
şart. 'Tek-yazı kart koşu-bölünmesi' sınıfı (İNİŞLİ/GELECEK, 2 film) AÇIK.

## 2026-07-30 (sabah) — Fable taze-göz denetimi: ikinci-şans CANLI doğrulandı, 2 gedik kapatıldı, 1 gedik ayrı işe

**Tetikleyen:** Çağatay (model→Fable): "ikinci tur aktif mi? iyice bakın, eksik gedik kalmasın."

**İKİNCİ-ŞANS CANLI DOĞRULAMA (sayaçlı enstrümantasyon, 6 yabancı-alfabe film):**
EVET aktif ve kazanıyor — VANYA/MELEKLERİ: Kiril-RU 10 çağrı, kazanan roller
режисс/оператор (✓+7/-17). KANDAHAR: Arap-AR 10 çağrı, kazanan بازیگران/فیلمبردار
(✓+5). ARKADAŞIMIN: ikinci-şans yetmedi → scroll_kurtarma yakaladı (guven=0.35
insan-işaretli, ✓+8). YAKIN_PLAN: gerek kalmadı, jenerikteki İngilizce teknik
krediler Latin yolundan yetti (✓+8). İNİŞLİ ✗+89 = baseline'ın zaten bilinen hatası.
Sistem KATMANLI savunmayla çalışıyor. (Dünkü "Paddle-RU VANYA'yı çöp okuyor" gözlemim
de 2-karelik yanıltıcı örneklemmiş — 10-kare örneklemde RU rol-anahtarları yakalıyor.)

**TAZE-GÖZ DENETİMİ (4 salt-okur mercek):**
- Blast-radius ✓ TEMİZ: 10 paralel commit (havuz/pilot-hat, track_kunye ağacı)
  jenerik dosyalarına SIFIR temas; track_kunye↔kunye_kiyas kod bağı yok.
- Tesseract sızıntı ✓ TEMİZ: kod yolunda sıfır referans; tek artık olcum_tess.json
  → silindi. 7 jenerik kod dosyası working-tree'de HEAD ile birebir.
- Bayrak/env: (a-d) temiz (V5=1, METIN_KAPI default kapalı, OneOCR sökülü,
  review şubesi yerinde). (e) **GEDİK BULUNDU+KAPATILDI (b2b4b1b):** linux/mitas.env
  kurulum ŞABLONU V5 bayraklarını içermiyordu → taze re-provision üretimi v5
  SESSİZCE KAPALI tohumlardı (cp -n + kod default 0 + assert yok). Şablon hizalandı.
- İkinci-şans statik: **GERÇEK boşluk doğrulandı** — Arapça tetiği `en_bos_kare >=
  len-2` MUTLAK eşik, KANDAHAR tam sınırda (8+2/10, sıfır pay); ≥3 kırıntı-kare
  üreten bir Farsça film iki tetikten de kaçar → sessiz kredi_yok/cast kaybı.
  GT'de görünmüyor (yalnız 2 Farsça film, ikisi de sınırda geçiyor = aşırı-
  kalibrasyon). Davranış-değiştiren fix ölçümsüz inmez → AYRI İŞ çipi açıldı
  (oransal eşik + 110-film kapısı + sentetik 3-kırıntı repro).

**Durum:** Üretim motoru (tespit_v5 Paddle %93.6) sağlıklı, defter kapandı.
olcum_son.json commit'lenmedi (skorboard her koşuda ezilir; baseline ayrı sabit).

## 2026-07-30 (gece 4) — jenerik OKUMA motoru: Tesseract araştırması → 110-filmde DÜŞTÜ (%87.3<%93.6), hibrit yol

**Tetikleyen:** Çağatay "dil sorunu = Paddle rec yabancı-alfabede çöp okuyor; başka
OCR dene". Amaç: onset tespiti için okuma motorunu Paddle→? değiştirmek.

**OCR MOTOR KIYASI (yabancı-alfabe jenerik kareleri, izole test ortamı
`scratchpad/ocr_bench/`):** Tesseract (CPU, 100+ dil, kutu-crop'ta Kiril+Farsça
TUTARLI, rol-anahtar کارگردان yakalıyor, dürüst boş-dönüş), EasyOCR (gürültülü),
deepseek-ocr (ollama, iyi ama BOŞ karede halüsinasyon `Figura São Paulo`),
GLM-OCR (2.2GB ollama, Kiril mükemmel ama Farsça ÇÖP+döngü, 60s/kare → RED),
Surya (yeni sürüm docker-bağımlı, atlandı), Paddle (Kiril iyi, Farsça TUTARSIZ).
TÜM-KARE Tesseract footage-üstü jenerikte çöp; KUTU-CROP (Paddle det kutu→crop
3x→psm7) düzeltiyor. Kutu-maskeleme+tek-çağrı hız için denendi ama Kiril/Farsça
satır düzenini BOZDU (VANYA/YAKIN kayıp).

**KRİTİK SONUÇ — 15-film yanılttı, 110-film gerçeği gösterdi:**
- proto3 (tespit_v5 mimarisi + Tesseract kutu-crop, mimari korunur, sadece
  credit_content.satirlar* monkeypatch): 15-film ön koşu İYİMSER (yabancı-alfabe
  VANYA/MELEKLERİ/KANDAHAR düzeldi, Latin=Paddle eşit). AMA o 15 film YANLI
  örneklemdi (yabancı-alfabe + tespit_v5'in zaten yanlışları seçilmiş).
- **110-FİLM TAM: Tesseract %87.3 genel / %91.8 üretim — Paddle %93.6/%96.4'ten
  6 PUAN DÜŞÜK.** kredi-yok 29/29 KORUNDU (konseyin FP korkusu boş çıktı) ama
  kredi-VAR düştü (67/81 vs 74/81): ARKADAŞIMIN/ÖLDÜRME_ZAMANI(İt)/DOĞUM_GÜNÜN
  (Mac)/GENÇ_BILLY/KÜÇÜK_SİMBA "bulamadı" — Tesseract kutu-crop bu filmlerde
  Paddle'dan AZ okuyup jeneriği kaçırdı. Harness: `harness/kunye_kiyas/olc_tess.py`.

**DIŞ KONSEY (GLM/Nemotron/MiniMax; Kimi 429-bakiye):** mimari DOĞRU ama 3
bloklayıcı — (1) kredi-yok FP (Tesseract sahne-yazısı/altyazı→isim; gürültü filtresi
şart: confidence eşiği+tüm-büyük-harf ele+rakam-ağırlık ele), (2) onset erken kayma
(erken tabela), (3) dil-kapsamı (eng+tur Latin-Avrupa'yı bozar, çok-dil PSM'i bozar
→ dil-TESPİTİ statik, film başında). 110-film tek başına yetmez: kredisiz-çeşitlilik
(10-15) + Latin-Avrupa (5-8) seti şart. monkeypatch değil credit_content_v2 clean modül.

**İÇ KONSEY BAŞARISIZ:** `konsey_kod` skill'i HARD-CODED `dynamic_credit_mosaic.py`
(master-PNG) sorusu içeriyor, args göz ardı edildi → jenerik-onset için ALAKASIZ
çıktı (585k token boşa). Skill başka iş için yazılmış; jenerik-onset'e uymuyor.

**KESİN SONUÇ (Çağatay'ın QC'si yakaladı — PREMISE BAŞTAN YANLIŞMIŞ):** Tesseract
GEREKSİZ, İPTAL. Kanıt: (a) `olcum_son.json` — tespit_v5 (Paddle) VANYA/MELEKLERİ/
KANDAHAR/ARKADAŞIMIN'ı ZATEN DOĞRU buluyor (7 hatası: TESS/İKİ_KAFADAR/KIZIL_HAYAT/
HARİKA/YALNIZ_SAVAŞÇI/GELECEK/İNİŞLİ — hiçbiri yabancı-alfabe değil). (b) Paddle-RU
VANYA'yı ÇÖP okuyor (`['O H','дозфоди нон']`) AMA tespit_v5 yine DOĞRU buluyor →
**onset'i rec DEĞİL, credit_box KUTU-KOŞUSU + SCROLL buluyor (dilden bağımsız).**
Yani "Paddle yabancı-alfabede çöp → yabancı film yanlış → Tesseract lazım" premise'i
TEMELDEN YANLIŞTI: rec çöp OLSA DA onset doğru. tespit_v5 yabancı-alfabeyi zaten
hallediyor. 110-film Tesseract düşüşü (%87.3) = Tesseract DÜZELTMEDİ, BOZDU (mevcut
sistem zaten çalışıyordu). Ayrıca Paddle'ın satirlar_ar (Arapça ikinci-şans) Farsça'yı
DOĞRU okuyor (`بازيگران`) — kod BAŞTAN oradaydı. ⑤⑥⑦/Dalga 0-3 (Paddle) DEĞİŞMEDİ,
Tesseract üretime SIZMADI (credit_content/credit_onset temiz), izole scratchpad'de
kaldı. Temizlendi (olc_tess.py sil, Surya venv 5.1G sil, http server dur).

**KÖK HATA (ders):** premise'i (muhtemelen önceki-oturum özeti "dil=Paddle rec çöp")
DOĞRULAMADAN koca araştırma kurdum. `olcum_son.json`'a BAŞTAN bakıp "bu filmler zaten
doğru mu" deseydim tüm iş gereksizdi. GT-karar (eski `yanlis_kredi_var`) ile güncel
ölçümü karıştırdım. Bir oturum (5 OCR motor testi, izole venv, 2 konsey turu, model
indirme) olmayan sorunu çözdü. [[eval-harness-first]] + [[kirmizi-takim-degeri]]:
premise'i ilk adımda ölçümle doğrula. Yan-bulgu (acil değil): cop_desenli_mi Farsça
çöpünde False veriyor (<3 token) — Kiril-tetiği Farsça'ya uymuyor, ama en_bos_kare +
kutu+scroll zaten buluyor, onset'e etkisiz.

**BAŞARISIZ/ÖĞRENİLEN:** (1) 15-film YANLI örneklem yanılttı — küçük+seçili set
iyimser, tam GT gerçek ([[eval-harness-first]] dersi: örneklem çeşitli+rastgele
olmalı). (2) Tesseract tüm-kare footage-üstünde çöp, kutu-crop şart. (3) Kutu-
maskeleme hız için doğruluğu bozar. (4) `konsey_kod` skill'i jenerik-onset'e uymuyor.

**SIRADA:** Hibrit (Paddle + yabancı-alfabe Tesseract fallback) prototiple + 110-film
ölç — Paddle'ın kredi-var düşüşü olmadan yabancı-alfabe kazanılıyor mu. Tutarsa
gürültü filtresi + dil-tespiti + genişletilmiş kredisiz/Latin-Avrupa test (konsey
checklist), SONRA entegrasyon. Test ortamı `scratchpad/ocr_bench/` + Surya venv
duruyor (tekrar için). Paddle-baseline (tespit_v5) DEĞİŞMEDİ — jenerik-tek-motor
branch'i (Dalga 0-3 + ⑤⑥⑦) güvende.

## 2026-07-30 (gece 3) — jenerik: ⑤⑥⑦ + Dalga 3 (metin-kapı, bayraklı) + OneOCR Linux'ta ölü çıktı

**Devam:** Aynı tek-motor işi. Konsey turu (GLM/Kimi/Nemotron) Dalga 3'ü koşulsuz
boş havuzdan METİN-KAPILI karara çevirdi (kayıt: `docs/MITAS_Jenerik_Tek_Motor_Temizlik.md`).

**⑤⑥⑦ KEŞİF (4 paralel agent) — beklentimi çürüttü:**
- **⑥ HATA DEĞİL:** Kiril/Arap örneklem uyuşmazlığı ULAŞILAMAZ — `not core_roller`
  kapısı tetikleyici ile genişletmeyi mutual-exclusive yapıyor. "Sorun gibi görüneni
  çözme" tuzağı. Sadece savunmacı yorum (commit 60c666a, davranış değişmez).
- **⑤ Macarca:** gerçek ama tek film (DOĞUM_GÜNÜN) + kök kanıtsız (ana yol zaten
  toleranslı, yine yanlış-neg) + Yol A RİSKLİ (`_ROL_MACAR_ONEK` kapanış-\b yok →
  operation/render'a çarpar, GT'de görünmez FP). Yol A REDDEDİLDİ, sadece 2 yalan
  docstring düzeltildi (3b07b92).
- **⑦ İtalyanca baglam:** tek gerçek fix (ÖLDÜRME_ZAMANI), güvenli yön (onset'i
  erkene = asimetri güvenli). 6 çağrıya baglam eklendi (3501482). AMA 110-film
  ölçümünde SIFIR hareket — İtalyanca statik-kart senaryosu GT'de yok, etki yalnız
  üretimde teorik. Tuttum (regresyon yok + tutarlılık) ama GT-kanıtsız.

**DALGA 3 (305cfac + 1397d71) — metin-kapılı kredi_yok, BAYRAK ARKASINDA:**
`MITAS_JENERIK_METIN_KAPI` default KAPALI. Açıkken v5 kredi_yok → CV devralmaz,
`credit_box.kutu_serisi` det-only son %15'te jbayrak (credit-benzeri, altyazı/başlık
filtreli) arar. Metin yok→kredi_yok, metin var→review_kredi_yok+review_required
(insan kuyruğu). Doğrulandı: KANDAHAR (Farsça) bayrak açık → review (v5 kaçırdı ama
det buldu, SESSİZCE KAYBETMEDİ). Kritik guard'lar: result-None çökmesi önlendi,
VLM/trim'e `not metin_kapi_karari`, v5 HATA≠kredi_yok. kunye_stages'e review şubesi
(overall="review", pass/fail bozmayan 3. durum).

**ONEOCR LİNUX'TA ÖLÜ (Çağatay tespiti "oneocr ne alaka, Linux'tayız"):** `oneocr`
paketi (MS Windows OCR) Linux'ta YOK → `make_oneocr_engine()` ModuleNotFoundError.
Fallback her v5-kredi_yok filminde ateşleyip except'e düşüyor, errors.jsonl kirletiyordu;
v5 aktivasyonundan beri engine=oneocr TEK manifest üretmemiş. create_pool'dan söküldü
(davranış-nötr — zaten çöküyordu). Sökülen yol `make_oneocr_engine()` → `import oneocr`
DOĞRUDAN (Paddle wrapper YOK) → gerçekten ölü.
**DÜZELTME (Çağatay uyardı):** giriş havuzu alarmım YANLIŞTI. `giris_jenerik_havuzu.py`
`oneocr_line_boxes` ismini taşısa da `_get_engine()`→`build_engine()` (`_pipe_ocr.py:348
_PaddleReadEngine`) kullanıyor — Linux'ta PADDLE döner (kind=paddle, recognize_pil taklit,
2026-07-17'de Çağatay geçirmiş). Giriş havuzu Linux'ta ÇALIŞIYOR, çökmüyor. İki yol
FARKLI: create_pool make_oneocr_engine (ölü) vs giris build_engine (Paddle). Ayrı not:
v5-sonrası giris_jenerik_manifest = 0 (giriş havuzu v5'ten beri hiç üretilmemiş — ayrı konu).
> **DÜZELTME (2026-07-30):** Bu son cümle YANILTICI. Sayım `Database/` üzerinden
> yapılmıştı; oysa Linux'a geçişten (17 Tem) sonra `Database/`'e hiç üretim koşusu
> yazılmadı — koşular `candidate_runs/` ve `filmtest/` altına gitti. Gerçek durum:
> 28 Tem `candidate_runs/test_frame_vs_master` koşularında giris_jenerik havuzu
> ÜRETİLMİŞ (50 / 5 / 91 kare + manifest). Giriş havuzu Linux'ta çalışıyor.

**DATABASE:** ~103 film (07-28 yedeği 300, restore 197) Çağatay "geri alma" dedi — bırakıldı.

**BAŞARISIZ/ÖĞRENİLEN:**
- OneOCR gibi Windows-özel araçlar Linux geçişinde SESSİZCE ölü olabilir (try/except
  yutuyor) — VLM (ollama qwen3-vl) ve giris_jenerik OneOCR'ı da denetle.
- ⑦ dersi: "kağıt üstünde doğru + regresyon yok" ≠ "GT'de kazanç". Test seti bir
  senaryoyu içermiyorsa fix ölçülemez; tutmak yargı kararı.
- GPU: asılı bırakılan _jenerik_pool süreci (VLM'de 20 dk) GPU tutuyor — timeout
  sonrası pgrep+kill ile temizle.

**SIRADA (Çağatay kararı bekliyor):** Dalga 3 bayrak açma (`MITAS_JENERIK_METIN_KAPI=1`) —
konsey şartları: return-3 tüketici denetimi + kredi_yok filmlerin insan FN=0 doğrulaması.
30-film kuru koşu (METIN_KAPI_ESIK kalibrasyonu) YALNIZ bayrak açılırken anlamlı — bayrak
kapalıyken gereksiz (Çağatay uyardı: "amaçsız deney yok"), o ana ertelendi. Branch merge
(finishing-a-development-branch) Dalga 3 devreye alma kararından sonra.

## 2026-07-29 (gece 2) — jenerik TEK MOTOR: Dalga 0-1-2 indi (kapılar birebir), ARADA DATABASE BOŞALDI

**Tetikleyen:** Çağatay'ın kod incelemesi siparişi → 8 bulgu → tek-motor
sadeleştirme planı (Opus tasarım, Sonnet uygula). Plan `~/.claude/plans/
adaptive-leaping-globe.md`.

**İNEN İŞ (branch `jenerik-tek-motor`, 6 commit):**
- **Dalga 0** (7b0a46f): %93.6 baseline sabitlendi (commit'siz duruyordu, HEAD eski
  T4=88/110). Kapı: 110/103/%93.6/%96.4/kredi-yok 29/29.
- **Dalga 1** (4d1798b + 4503d15): `tespit()`(v3)/`tespit_v4()`/`credit_vlm.py`/
  `olc_gt.py`/`experiments/closing_credit_onset_vlm/`(+4 test) SÖKÜLDÜ — 19.698
  satır. ④ `tespit()` çökmesi yamayla değil SİLİNEREK çözüldü. ② `_scroll_kurtarma`
  güveni 1.0→`KURTARMA_GUVEN=0.35` (en zayıf kanıt en yüksek güveni raporluyordu).
  Kanarya ÖLDÜRME_ZAMANI (kb=0.67) bozulmadı, kurtarma-yolu tek film ARKADAŞIMIN.
- **Dalga 2** (01f66b5+8f57090+fc6bac3): CV artık TEMBEL (v5 kazanınca hiç koşmaz)
  → v5-kazanan 7 filmde süre 49s→14-18s (~%70). Manifest v5'in gerçek değerlerini
  taşıyor; yanıltıcı `confidence`/`detector`/`cv_start_pos` kaldırıldı (B1: v5 güveni
  78/78 sabit 1.0). `v5` alt-nesnesi HER koşuda yazılıyor → v5'in kredi_yok kararı
  artık görünür (⑧: bugüne dek CV sessizce eziyordu). `--segment giris` gardı.

**KAPI KANITLARI (hepsi kendim koşturdum, subagent raporuna güvenmedim):**
- Parite 12 film: v5-kazanan 7'de start_pos BİREBİR. v5-kredi_yok 5'te VLM açıkken
  fark VAR ama VLM(qwen3-vl) STOKASTİK — VLM/OneOCR kapatınca 5/5 çekirdek birebir.
- 110-film ana kapı Dalga 1 sonu + Dalga 2 sonu: BİREBİR 103/110, aynı 7 hata.
- credit_type enum ✓ (static_credit→60sn), AST ✓, v5_izleme ✓, --v4 reddi ✓.

**⚠️ DATABASE OLAYI (ben yapmadım, kanıtlı):** İş sırasında `/opt/mitas/Database`
BOŞALDI (300→197→0 film). Zaman çizgisi: 07-28 yedek 300, 07-29 06:30 yedek 197,
21:43 parite betiğim 12 klasörü VAR gördü, 21:53 Database mtime=boşalma anı. Benim
o penceredeki tek işim parite'ydi ve HEPSİ `ModuleNotFoundError: No module named
'core'` ile öldü (kabukta MITAS_PROJECT_ROOT yoktu → E:\MITAS'a düşüyor) — hiçbir
dosya işlemine ulaşamadan. İşaret eşzamanlı "dizin sadeleştirme" oturumunun
`git clean -fdx` riskine (Database .gitignore'lu) gidiyor ama KESİN sebep
doğrulanmadı. RESTORE: `/opt/yedek/mitas_db/son` (07-29 06:30, 197 film, hardlink)
→ rsync, 124G, çıkış=0, 197 klasör birebir, AEON FLUX cikis 720 kare tam. Çağatay
disk için Kademe-1 (~66G: QwenOmni/nemo/tts/locateanything) sildi.
**BEKLEYEN:** 07-28→07-29 arası ~103 film hiçbir yedekte YOK gibi — kurtarılabilir
olan `/opt/yedek/mitas_db/20260728_123617` (300 film). Çağatay kararına bırakıldı.

**BAŞARISIZ/ÇÜRÜTÜLEN (aynı çıkmaza iki kez girilmesin):**
- `olc_pool.py --film X` → `olcum_son.json`'u tek-film raporuyla EZER. Kullanma.
- Kurtarma-yolu imzası `joint=1.00` TEK BAŞINA yetmez — ÖLDÜRME_ZAMANI kb=0.67 ile
  tesadüfen 1.00 üretiyor. Gerçek imza `kb=1.00 ∧ joint=1.00` (normal `joint≥kb×1.245`).
- `Sonuc.guven` eşik kurmak için KULLANILAMAZ — 81 pozitiften 80'i 1.0.
- `scripts/*.py` kabuktan koşarken `source mitas.env` ŞART (yoksa import ölür +
  status:error manifesti → sessiz boş → SAHTE parite "aynı"). İlk parite bu yüzden
  1 saat kaybettirdi (subagent 335k token).
- v5_izleme küçük pürüz: pool_frames=0 "geç-çapa" diye işaretliyor (kredi_yok olmalı)
  — v5 manifestleri birikince kredi_yok kuyruğu düzeltir, Dalga 3'e bırakıldı.

**SIRADA:** Konsey kırmızı-takım (Dalga 3'ün "v5 kredi_yok'ta son söz = görünür
boşluk" kararı için — nerede patlar?) → Dalga 3 (OneOCR/VLM/trim sökümü, ölçüm
kapısı: 30 film kuru koşu, kredi_yok oranı %45'i aşarsa DUR). Kapsam dışı: ⑤ Macarca
diyakritik, ⑥ Kiril/Arapça örneklem kayması, ⑦ İtalyanca baglam — konsey sonrası
ayrı doğruluk dalgası (bunlar %93.6'yı gerçekten oynatabilecek tek kalem).

## 2026-07-30 (sabah) — PILOT HAT: dhash-havuz + deepseek-ocr + qwen-yapılandır + KB — Farsça İLK KEZ okundu

**Gecenin ikinci yarısı üç büyük bulguya çıktı:**
1. **pipeline100 Linux'ta HİÇ çalışmamıştı** (son başarı 06-Tem = Windows;
   Linux geçişi 16-Tem). 5 yol köprüsü + oneocr eksiği + DuckDB X:\ yolu —
   hepsi düzeltildi (`ea05d9c`, `8a55210`). Zincir dirildi: gercek-yalanlar
   232 satır GUVENILIR. KB (38 tablo) 14 gün sonra geri bağlandı.
2. **Tek-istek toplu-VLM deneyi (Çağatay sorusu):** 40 kare → qwen3-vl tek
   istekte KAPSAMDA kaybediyor (95 satır / 0.401), ama YAPIDA rakipsiz
   ("Harry — ARNOLD SCHWARZENEGGER"). Thinking tuzağı: num_predict 4096'nın
   tamamı düşünmeye gitti, response boş — 16384 şart. Ders: görüntüyü toplu
   verme; OKUMAYI sayfa-sayfa yap, YAPILANDIRMAYI metin-üzerinden toplu yap.
3. **VLM-OCR sayfa-sayfa kıyası:** deepseek-ocr ('Free OCR.' promptu) 14
   sayfayı 16 SANİYEDE okudu, temiz (EMILY SCHWEBER doğru); glm-ocr 4× yavaş
   + tekrar-şişmesi + prompt-eko hassasiyeti ("BOS yaz" ekleyince bozuldu).

**PILOT HAT (4 katman, 5 film, uçtan uca ~6 dk) — `harness/track_kunye/pilot_hat.py`:**
havuz(dhash ardışık-dedup + linspace-40; kuyruk-kesme bug'ı YOK) → deepseek-ocr
sayfa-sayfa → qwen3-vl'e dökümü METİN olarak yapılandırt (rol—isim eşleşme,
"GÖREV: İSİM,İSİM" kompaktlaması — satır sayısı yanıltıcı metrik çıktı, atlama
değil birleştirme) → KB(10M isim)+Paddle-track işaretleri: [KB]/[2K]/[!].
**hayat-agaci: FARSÇA İLK KEZ OKUNDU** — 2 aydır sıfır çıkaran filmden 19
satır (عکاسی مجموعه، سیمای جمهوری اسلامی ایران...), hepsi [!] = "okudum ama
doğrulayan yok, insan baksın" (tasarlandığı gibi). "Re-regording Mixers"
OCR hatası [!] ile doğru yakalandı. Çıktılar: outputs/pilot_hat_5film/.

**AÇIK KALEMLER:** (a) dhash-8 karlı/loş zeminde fazla agresif — hayat-agaci
havuzu 4 sayfaya düştü, dhash-16'ya geç; (b) deepseek yazısız karede SAHNE
BETİMLİYOR ("The image displays a ballroom...") — betimleme süzgeci gerek;
(c) KB 10M isim → [KB] işareti enflasyona açık, eşleşme sıkılaştırılmalı;
(d) GPU paylaşımı: qwen3-vl:30b 'Stopping'de takılıp GLM'i 5dk bekletti.

---

## 2026-07-29 (gece) — track_kunye: frame-first künye çıkarma kuruldu, ilk ölçümde sentetik master adaptifi geçti

**Tetikleyen:** Çağatay'ın tasarım sorusu ("çıkış jeneriğini en verimli nasıl
okuruz — tarafsız tasarla") + sipariş: "7 maddelik sistemi kur da görelim,
sentetik master'ı da dene, GLM/Kimi'ye danış, bana çalışan bir şey getir".

**Kurulan:** `harness/track_kunye/track_kunye.py` (~480 satır, üretime
DOKUNMAZ). Akış: her karede det+rec (db_compose_master F1b/F1c tembel
motorları — tek OCR kaynağı) → kare-içi ROW gruplama (y-bandı; kolonlar
x-sıralı `" | "` canon — rol|isim geometrisi bedavaya korunur) →
token-eşleşmeli kayma zinciri S_k → bölüm/kart sınırları (Jaccard<0.2 + dy
yok → yeni bölüm) → g=cy+S_k uzayında ROW-track kümeleme → komşu-track
garble-birleştirme (cuslodian/gustodian vakası) → bulanık-mode konsensüs
(stitch fikri) → çöp filtreleri (altyazı bandı 0.82H / watermark-ömrü /
tek-gözlem→düşük-güven) → çıktılar: kunye_track.txt + dusuk_guven.txt +
SENTETİK MASTER (her track'in en iyi kırpımı g-sırasında; düşük-güven ayrı
bölümde render — insan kararı) + manifest.

**İLK ÖLÇÜM (10 film, sadakat token-recall):** det-kör olmayan 7 filmde
ortalama: adaptif master 0.549 · trackTXT 0.524 · **sentetik master 0.653**.
karadeniz 0.204→0.643 (3×), mufreze 0.618→0.768, 20-bulusma 0.827→0.896
(adaptifin kazandığı filmde bile önde). Tek kayıp havaci (0.184 vs 0.285) —
loş-metin sınıfı, bilinen açık kalem. det-körlük kapısı 3 filmi doğru
işaretledi: hayat-agaci (ana=0, YALAN ÜRETMEDİ), kucuk-dev-adam, sihirli-flut
— son ikisinin 25-film kıyasındaki kötü sonuçlarının kök sebebi de böylece
bulundu (düşük det yoğunluğu sınıfı).

**ÖĞRENİLEN (önemli):** sentetik master recall'ı trackTXT'den YÜKSEK —
konsensüs doğru SATIRI seçiyor ama Paddle latin-mobile rec METNİ bozuk
("MIKE MINKLER, C.A.S." → "eminler ca s"); piksel bandı doğru olduğundan
yeniden-OCR daha iyi okuyor. Güçlü halka görsel seçim, zayıf halka rec metni.
İyileştirme adayları konseye soruldu (rec'i server modele çevirmek / ikinci
geçiş yeniden-OCR / karakter-düzeyi oylama).

**Konsey:** ask_council MCP koptu ("Connection closed") →
`council_mcp/konsey_dogrudan.py` ile iki tur arka planda: (1) tasarım sorusu
(A-uzamsal vs B-zamansal, mercekli), (2) track_kunye TAM KODU ile bug
avcılığı. Cevaplar gelince sentezlenecek.

**Bekleyen:** (1) konsey cevapları + fix turu; (2) havaci/loş-metin
kalibrasyonu; (3) det-kör sınıfa VLM tam-kare fallback (kapı hazır, çağrı
yok); (4) 40-film genişletme + QC turu (Çağatay: "sonra qc üzerinden tekrar
geçeriz"); (5) rec metni iyileştirme; (6) paodycullen-tipi garble-bitişik
tekrar (düşük öncelik).

---

## 2026-07-29 (devam) — dizin sadeleştirme turu: 3 MAYIN bulundu, temizlik ikinci plana düştü

**Tetikleyen:** Çağatay "proje çok dağınık, testler/scriptler/sonuçlar/pipeline/test
filmleri hep burada — temizleyip sadeleştirelim, sonra yer boşalt".

**Yapılan:** Yaklaşım A (karantina + kök sadeleştirme) seçildi; silme yetkisi Çağatay'da
kaldı ("Claude taşır, Çağatay siler"). Tasarım `docs/MITAS_Dizin_Sadelestirme_v1.md`.
Sonra 53 ajanlık kırmızı-takım doğrulama turu (16 aday × 3 mercek + 4 yapısal +
tamamlayıcılık eleştirmeni, 4.4 M token) açıldı.

**EN ÖNEMLİ BULGU — `git clean -fdx` bu repoda 1.1 TB siler.** `models/` 587 G,
`Mitas_Files/` 157 G, `Database/` 119 G (199 filmlik üretim çıktısı), `venvs/` 105 G,
`Mitas Output/`, `mitas.env` (API anahtarları), `CLAUDE.md` — hepsi `.gitignore`'lu
olduğu için `-x` kapsamında. `git clean -ndx` 1429 giriş listeliyor.
`.claude/hooks/mitas_guard.py:96` regex'i yalnız `rm|rmdir|shred|-delete` arıyor,
`git clean`'i **yakalamıyor**. Temizlikle ilgisi yok, ondan acil.

**İKİNCİ MAYIN — `git gc` üç benzersiz test dosyasını yok edecekti.** 3 packed yetim
commit'te `tests/test_regresyon_koruma.py`, `tests/test_credit_crosscheck_reachability.py`,
`tests/test_fr_soybaglac_yonetmen_gate.py` vardı — ne diskte, ne bir dalda/tag'de/remote'ta.
`kurtarma/e3320e7-regresyon-koruma`, `kurtarma/3ff10b2-golden-veri-kaybi`,
`kurtarma/9b7e90d` dalları açıldı. **BU DALLAR SİLİNMEZ.** Ayrıca `git prune` bir
düşürülmüş stash'i (2026-07-23) silecekti; yaması yedeklendi.

**ÜÇÜNCÜ MAYIN — ASR kill-switch API yolunda delik.** `ASR_KAPALI.flag`'i yalnız
`scripts/mitas_pipeline.py:2394` kontrol ediyor; `core/api/asr_server.py` bakmıyor ve
2026-07-29 11:24'te ASR'yi gerçekten başlattı (`asr_queued`→`asr_started`→`asr_failed`).
Onu durduran şey bir kontrol değil, `venvs/asr`'da `libcublas.so.12`'nin **olmaması** —
bir kaza. `venvs/alignment`'ta ve ollama cuda dizininde o kütüphane zaten var.
Çağatay'ın 2026-07-11 talimatı 18 gündür yarım uygulanıyormuş.

**BAŞARISIZ/ÇÜRÜTÜLEN VARSAYIMLARIM (aynı çıkmaza iki kez girilmesin):**
- "Kökte 48 giriş" → **57** (`ls -A`; gizli dosyalar sayılmamış)
- "206 G kazanılır" → **~38 G anında**. Tüm adaylar aynı ext4'te (`stat -c %d` → 66314);
  `mv` inode taşımaz, `df` değişmez. Kalan ~168 G Çağatay silene kadar diskte durur.
- "`__file__`/`parents[1]` tek merkezi fix" → **YANLIŞ.**
  `.claude/worktrees/musing-aryabhata-1d5189` **canlı** worktree ve orada `Database/`,
  `venvs/` yok; naif çözüm pipeline'ı boş ağaca yazdırır. **Çapa** (`Database` +
  `model_manifest.yaml`) ile yukarı tırmanmak zorunlu.
- "`_karantina/` güvenli bir hedef" → `.gitignore:112 /_*` ile ignore ediliyor;
  `git clean -fdx` karantinayı da siler. Ad `KARANTINA_2026-07-29/` olmalı.
- "pytest + smoke = doğrulama kapısı" → `tests/` altında taşınacak yollara **0 referans**;
  145 G venv/model taşınsa pytest aynen yeşil kalır. Gerçek kapı
  `kurulum/13_surum_denetimi.py` diff'i + `ollama show` roster'ı.
- "Her ölü venv'e tek referans Windows probe'u" → 8 adayın **5'inde çürütüldü**; ilk
  kanıt turu `kurulum/` ve `linux/` dizinlerini hiç taramamış.
- Aktif dal **`main` değil `jenerik-tek-motor`**.

**Kanıtla ayakta kalan temizlik:** ~17 G (`venvs/nemo` 6.2 G — RECORD sha256 denetimi
75.240 yol/0 kayıtsız/0 mismatch, `venvs/tts`+`models/tts` 5.6 G, `venvs/locateanything`
5.2 G, `hf-cache/` 2.3 M). Çağatay onayıyla eklenen: `models/QwenOmni` 49 G, 3 ollama
test modeli 54 G, eski candidate koşuları ~18 G → toplam ~138 G karantina adayı.
**`vllm_bench_20260718/claude_gt/` HARİÇ** — 31 film 313 dilim elle yargılı altın standart.

**Bekleyen:** Blok A planı hazır (`docs/superpowers/plans/2026-07-29-dizin-sadelestirme.md`)
— 3 mayın, TDD, veri taşınmıyor. Blok A yeşillenince Blok B (karantina taşıması) kendi
planına yazılacak; kritik girdisi "`E:\MITAS/` 10 dk cron sonrası geri geldi mi" sorusunun
cevabı. Kapsam dışı bırakılan hatalar: `models/lid` kırık symlink (dil tespiti çalışmıyor),
`asr_server.py:736` `Path("E:\\")` (prefetch Linux'ta sessizce ölü),
`kurulum/26_kapanis_pdf.py:26` hardcode (candidate izolasyonunu deliyor),
`venvs/asr` libcublas eksiği (**Görev 2'den önce düzeltilmemeli**).

**Disk durumu:** `/` %93 dolu, 139 G boş.

---

## 2026-07-29 — fork envanteri + 25-film 3-kollu motor kıyası: recall ayırıyor, dup ayırmıyor

**Tetikleyen:** Çağatay "master PNG'de sistem karışık, çok fazla fork var, en
güncel ve kaliteli model ne aşamada" dedi. Envanter + ölçüm yapıldı.

**Envanter bulgusu (en önemli):** Üretimde master PNG üreten TEK yol var —
`mitas_pipeline` → `master_png_monitor --once` → `db_compose_master.compose_slit`
/ `compose_reading_runaware`. Ve `MITAS_MASTER_V2` varsayılanı `"0"`
(db_compose_master.py:102); `mitas.env`'de de `_PROD_DEFAULTS`'ta da yok. Yani
**F1/F1b/F1c/F2/F3/F3b/F3c/F4/K1'in tamamı üretimde ölü** — bir ayın kök-sebep
fix'leri yalnız harness'te koşuyor (uret.py:104, uret_ex.py:176 açıyor).
`data/master_ex*` altındaki %86.4 sağlık üretimin değil harness'in rakamı.
İkinci sanılan canlı zincir (`_pipe_ocr.py` → `20260601_pipeline100.compose_hybrid`)
aslında `MITAS_MASTER_PNG` bayrağına bağlı ve o bayrak hiç set edilmiyor → uykuda.
Ölü fork sayısı ~35 (1 Haziran prototipleri, film-özel `compose_*` scriptleri,
`credit_mosaic_methods` yarışmasından 2 sıfır-referans motor, `dense_master.py`,
`jenerik_tek_png.py` — 4 dokümanda anlatılıyor, kodda çağıran yok).

**adaptif_slit'in gerçek aşaması:** `outputs/footage_pano427` (tek büyük yatak)
**üç sürümün karışımı** — koşu 07-26 09:18→10:13, v14 commit'i 09:33, v16 commit'i
10:16 → 371 film v14-öncesi, 56 film v14, **0 film v16**. Manifest şeması üç
sürümde de aynı olduğu için içerikten ayırt edilemiyor, yalnız zaman damgasından.

**25-film 3-kollu kıyas (yeni ölçüm, scratchpad):** A=üretim bugünkü hâli (V2=0),
B=üretim fix'li (V2=1), C=adaptif v16 (iyileştirme bayrakları kapalı).
Film seçimi: 6 bilinen-zor çapa + 19 hiç test edilmemiş taze film.

| kol | ort. metin-recall | dup>0.10 | medyan boy |
|---|---|---|---|
| A üretim bugün | 0.4575 | 6/24 | 3776 |
| B üretim fix'li | 0.5217 | 5/24 | 3735 |
| C adaptif v16 | **0.5888** | 5/24 | 5444 |

Film başına (fark≤0.02 berabere): C 11.5, B 5.0, A 2.5, 5 berabere.

**ÖĞRENİLEN — metrik seçimi:** `dup_oran` üç motoru AYIRT ETMİYOR (6/5/5, medyan
boylar bile yakın). Haftalardır optimize edilen metrik motor kararı için kör.
Ayıran tek şey `sadakat.py`'nin Katman-0 metin-recall'i — A→B +0.065, B→C +0.067.
Bundan sonra motor kıyaslarında birincil metrik recall, dup ikincil.

**Başarısız/açık kalanlar:** `hayat-agaci` üç kolda da recall 0.000 (Farsça rec
token üretmiyor — bilinen açık sınıf, hâlâ çözülmedi). `kuzeyde` üç kolda da
<0.09. `totoro`nun Ex_Frame karesi yok (24/25 ölçüldü). adaptif temiz süpürme
YAPMADI: 20-bulusma (−0.079) ve gecmisten-gelen (−0.070) üretim lehine.

**Yan bulgu (risk):** uret_ex.py'de commit'lenmemiş bir blok, untracked
`OCR-worktree/panoramic_composer.py`'yi sabit `/home/cagatay/Programlar/mitas/...`
yoluyla import ediyor (o yol /opt/mitas'a symlink — çalışıyor ama kırılgan) ve
her koşuda 4. bir kompozitör olarak `panoramic_master.png` üretiyor. Ayrıca
`master_png_monitor.py:29` `giris_master_cropstack`'i çıplak `except` ile
yüklüyor; korpusta 189 manifest cropstack, 157 textset — 07-29 koşusu textset'e
düşmüş, yani giriş master'ı ortama göre sessizce mod değiştiriyor.

**Görsel QC turu (Çağatay 3 film seçti) — metrikleri çürüten bulgular:**
- `hayat-agaci`: metriklerin TAMAMEN yanıldığı vaka. Üç kolda da recall 0.000
  (PP-OCR Farsça okumuyor), dup_oran ESKİ'ye 0.941 "sağlıksız" / adaptife 0.000
  "sağlıklı" diyor. GÖZLE tam tersi: ESKİ 8 sütun dolu okunaklı Farsça künye,
  V2 3 sütun (ciddi kayıp), adaptif TEK KART (480px). Adaptifin dup'ı 0 çünkü
  tekrar edecek içerik bırakmamış — boşluk, sağlık sanılıyor.
- `ozel-bir-anne`: V2 fix'leri GÖRÜNÜR BOZULMA üretiyor — dikey şeritlenme/
  hayalet (yüz jaluzi gibi çizgilenmiş, satırlar üst üste). recall 0.724 (V2=0)
  → 0.599 (V2=1). **"V2 kapısını üretimde aç" önerisi bu yüzden GERİ ÇEKİLDİ.**
- `gercek-yalanlar`: V2'nin recall galibiyeti (0.608 vs 0.580) SAHTE. Token
  kıyası: V2 420, adaptif 412 — fark ağırlıklı olarak aynı kelimenin OCR
  varyantı. Kuyruk işaretçileri (`mcfadden`,`simulator`,`flight`,`pennington`,
  `minkus`) adaptifte VAR, V2'de YOK. Yarıda kesilen adaptif değil, V2.

**hayat-agaci KÖK SEBEP (kanıtlı, Görev tamam):** 113 karenin 112 çifti de
`duraksama` (dy≈0, sıfır scroll, sıfır kesme) — kartlar sabit footage üstünde
durduğu için faz-korelasyonu değişimi görmüyor. v16 kart değişimini token
kimliğiyle ayırmaya çalışıyor ama Farsça'da OCR ateşlenmiyor: kare 0 → 0 kutu/
0 token, kare 20 → 2 kutu/1 token (`1521`), kare 49 → 3/2 (`cam`,`lol`), kare
80 → 2/0, kare 110 → 3/2 (`295jya`). Boş∩boş = "aynı kart" → yeni sayfa hiç
açılmıyor → 480px. **ÖNEMLİ:** planlanan fix "det-kutu-yerleşimi kimliği (det
yazıdan bağımsız)" bu filmde ÇALIŞMAZ — det'in kendisi ateşlenmiyor (6-10 satır
görünen kartta 0-3 kutu).

**BAŞARISIZ FIX ADAYLARI (tekrar denenmesin):**
1. *Kırmızı-kanal maskesi + piksel IoU.* Maske metni gerçekten izole ediyor
   (kapsama %1-4.5, Sobel'in yozlaşmış %70'ine karşı) AMA kimlik sinyali
   vermiyor: aynı-kart 20↔21 IoU=0.038, farklı-kart 49↔80 IoU=0.060 — ayrım
   yok, ters bile. Sebep: ince/antialiaslı kırmızı yazı kare-kare oynuyor.
2. *Kırmızı maske + 24-kovalı satır-yoğunluk profili korelasyonu.* Yakın
   çiftler ort=0.395, uzak çiftler ort=0.394 — sıfır ayrım.
Sonuç: bu sınıf için metinden-bağımsız kart-kimliği hâlâ ÇÖZÜLMEDİ; iki ucuz
aday tükendi, tasarım kararı gerekiyor (konsey turu adayı).

**UYGULANAN (Çağatay kararı, aynı oturum):**
- *adaptif üretime entegre edildi.* `master_png_monitor.gen_reading_master`
  ÇIKIŞ yolunda adaptif BİRİNCİL, V2 YEDEK. Bayrak `MITAS_MASTER_ADAPTIF`
  (varsayılan açık). `_compose_reading_seg`'e DOKUNULMADI — onu uret.py/
  uret_ex.py bit-parite için import ediyor; dispatch yalnız üretim giriş
  noktasında. `compose_adaptif`'e `ims=` parametresi eklendi (kareler diskten
  değil çağırandan gelir; Ex_Frame klasör düzenine bağımlılık kalktı).
- *Yedeğe düşme kuralı:* `segment==1` ve `kare>=20` ve `boy<=2×kare_h` → çökme
  sayılır, V2'ye düşülür ve SEBEP manifest'e `adaptif_yedek` olarak yazılır.
  Duman testi: hayat-agaci → yedeğe düştü (`cokme`, 113 kare/480px), karadeniz
  → adaptif 7318px/14 segment. Tembel import hatası YUTULMUYOR (giris_master_
  cropstack'in çıplak `except` deseni tekrarlanmadı).
- *23 ölü fork silindi* (commit, 25 dosya / 4749 satır). KALDIRILMADI çünkü
  gerçek bağımlılığı var: `20260601_slitscan2.py` (CANLI pipeline100),
  `20260530_2350_full_pipeline_v2.py`, `db_compose_standalone.py`. Gitignore'lu
  olduğu için git geçmişinde HİÇ olmayan `linemosaic`/`panorama` önce
  `arsiv/master-png-fosilleri` dalına alındı (`0a76963`).
- *Hatam:* silme commit'ini `scripts` pathspec'iyle attım, Çağatay'ın 6
  commit'lenmemiş dosyası içeri girdi (`mitas_pipeline`, `_jenerik_pool`,
  `_deepseek`, `karar_gunlugu`, `_pipe_dilim_vl`, `_pipe_video_vl`).
  `reset --soft` + `restore --staged` ile geri alındı, iş kaybı yok.
  **Ders: pathspec'e dizin verme, dosyaları tek tek say.**

**Bekleyen:** (1) 40-film V2↔adaptif kıyası — bu turda EŞİT BAYRAK şartı:
`MITAS_IYIL_*` dörtlüsü iki motorda ZIT varsayılana sahip (db_compose_master
`"1"`, adaptif_slit `"0"`), ilk 25-film kıyası V2 LEHİNE eğikti ve adaptif yine
kazandı; (2) yedeğe düşme oranı — 427'de kaç film çöküyor, manifest'teki
`adaptif_yedek` alanından toplanacak; (3) OCR kapsama taraması — kaç filmde det
neredeyse sıfır ateşleniyor (hayat-agaci sınıfı, Latin-dışı betik); (4) V2
kapısı `MITAS_MASTER_V2` hâlâ üretimde 0 — açma kararı ozel-bir-anne
şeritlenmesi yüzünden ASKIDA, önce şeritlenme taraması gerekiyor.

---

## 2026-07-26 (devam 5) — v16 token-kimlik: kart sınıfı büyük ölçüde kırıldı, 3 açık kaldı

**Çağatay düzeltmeleri (kalıcı):** (1) İş GELECEK filmler için TEK motor —
427 test yatağı, "bozulanda eskiye düşeriz" SAYILMAZ (hafıza:
master-png-motor-stratejisi); (2) kıyas görsellerinde ESKİ/YENİ etiketi BÜYÜK
olacak (outputs/kiyas_427 yeniden basıldı); (3) QC = master PNG'yi GERÇEKTEN
açıp okumak — küçültülmüş yapı bakışı yetmez ("ikisi de bok gibi" affedilmeyenler
vakası: ikisinin de kötü olduğunu söylemek görev).

**v15→v16 (commit 5a44aab):** geometrik kimlik vekillerinin tümü battı
(ölçümle: hayat-agaci kar yağışı komşu-fark 7-11k px ≈ kart farkı) → kimlik
BİRİNCİL kanıtı det+rec TOKEN kapsaması (yalnız duraksama-temsilcileri, tembel
motor). Token-yoklama ızgarası (düz istikrar eğrili parlak filmlerde aday
üretimi), az-token güvencesi (havaci 46-sayfa patlaması), kesme dalına
kimlik+metin kapıları (affedilmeyenler THE END ×5), metinsiz-sayfa filtresi.
**Tam-okuma kabul:** jetgiller 13/13 kart birebir ✓ (Jayne Barbera→telif),
totoro 27 segment içerik-zengin, beklenmedik tek THE END ✓, affedilmeyenler
gök-çöpü öldü (3 sayfa, ideal 1-2), benimle 2298 ✓ parti ✓ korunmuş.

**AÇIK 3 sınıf (motor hazır DEĞİL):** (a) gercek-yalanlar: 2 balo-kartı
(Pamela Easley/Thomas Fisher) küçük-dy mikro-slit'e yapıştı — scroll-append
sırasında segment-içi kart-geçişi körlüğü; fix adayı: küçük-dy appendlerde
token-süreklilik şartı; (b) hayat-agaci: Farsça rec token üretemiyor →
det-KUTU-YERLEŞİMİ kimliği (det yazıdan bağımsız); (c) havaci: loş metin
gray>110 ölçüm maskesine görünmez (106 'bos' çifti) → film-bazlı eşik
kalibrasyonu. Sonra: 14+kabul5 tam-okuma QC, 427 yeniden, konsey kırmızı-takım
(mimari artık kararlı olunca), OCR-recall toplu ölçüm.

---

## 2026-07-26 (devam 4) — 427-tam koşu + gerileme avı: adaptif'in haritası çıktı

**İş:** adaptif_slit 427 filmin TAMAMINA koşuldu (outputs/footage_pano427,
korpusa dokunulmadı) + parti kök-fix'i (v14, commit 4dfefe2): parlaklık-maskesi
kapsaması >0.25 olan filmlerde ölçüm mod_denetim'in Sobel kenar-maskeli grisine
geçer — parti 527→2355px tek geçiş TAM liste; 79 parlak-maskeli film yeni yolla
yeniden üretildi (umitsizlik %96-kapsama dahi tertemiz), 14 doğrulanmış filmin
çıktıları değişmedi. Yapısal triyaj (boy eski/yeni + dup_metrik + sınıf):
KAYIP-şüphesi 16, TEKRAR-şüphesi 23, PATLAMA 26, İYİLEŞEN 26 — şüpheliler gözle
ayıklandı ("yeni kısa" çoğu kez DOĞRU dedup çıkıyor; triyaj hüküm değil aday).

**GERÇEK gerileme sınıfı (gözle doğrulandı): STATİK-ZEMİN KARTLARI** — zemin
kartlar arasında hiç değişmiyor (jetgiller/totoro çizgi-film çerçevesi,
hayat-agaci karlı ağaç, havaci hangar), yalnız yazı değişiyor; içerik-NCC ve
kimlik-IoU zemine domine olup kartları "aynı" sayıyor → sayfalar yutuluyor.
Ters ucu affedilmeyenler: gök dokusu sahte-"farklı" verip boş sayfa çöpü.
PATLAMA sınıfı (mookie/mufreze) kayıp DEĞİL: sahne-kartı başına sayfa (içerik
tam, biçim şişkin). ESKİ kompozitör tam bu statik-kart sınıfında güçlü —
adaptif'in kazandığı yer scroll/footage/parlak-zemin.

**Tasarlanan sonraki fix (v15):** aynılık kararını NCC yerine PARLAKLIK-
NORMALİZE PİKSEL-FARKI ile ver: b'yi a'nın istatistiğine normalize et,
|fark|>eşik pikselleri say — fade→küçük fark (aynı), aynı-zeminde metin
değişimi→metin-boyu fark (farklı). Zemin paylaşımından bağımsız tek ayırıcı.

**Strateji (/goal ≥91 için):** motor zorlaması YOK — film başına (eski, yeni)
adaylarından sağlık-kapılarıyla (recall + dup + boy) İYİ olanı seçen SEÇİM
korpusu. Hiçbir film statükodan kötüye gidemez (seçimde eski de var); adaptif
kurtardıklarını ekler. v15 sonrası kart-sınıfı da adaptif'e açılabilir.

---

## 2026-07-26 (devam 3) — ADAPTİF SLIT kompozitörü (footage-üstü sınıf kırıldı)

**İş:** `harness/master_dup/adaptif_slit.py` (commit 2366ac2) — F3b sonrası bile
mod_hatasi=True kalan 13 film + benimle-dans-et için kareden bağımsız yeni
kompozitör. Çekirdek: kare-başı METİN-MASKELİ (gray>110) phaseCorrelate dy +
duraksama-atlama + satır-seçimli gerçek slit; kart/melez akışlar için Çağatay'ın
"panoramik foto modu" kuralları (duraksa→bekle, cut/dissolve→alta in yeni sayfa,
hareket→panorama) mimariye işlendi. 14 filmde 13 iterasyon GÖZLE doğrulamayla
(Çağatay talebi: "sürekli örnekleri göster gözle doğrulayalım yoksa patlıyoruz")
gelişti; her mekanizmanın gerekçesi = gözle yakalanmış somut bir kusur:
- dissolve bekçisi + siyahtan-kart tetiği (karadeniz açılış kartları kaybı),
- NCC fade-kapısı (beklenmedik-miras THE END ×4), istikrar YEREL-TEPE temsilci +
  düz-plato ORTA kare (kucuk-dev karışım-karesi), İÇERİK-kanıtlı aynılık
  (IoU 0.35 kuralı farklı-metin/aynı-yerleşim kartları yutuyordu — IoU konum
  ölçer içerik ölçmez), parlaklığa-uyarlanan KİMLİK maskesi (soluk↔parlak),
  küçük-dy sahte-scroll + scroll-süreklilik bekçileri (Frankenstein sayfa:
  üst yarı kart2 alt yarı kart3), yönlü yavaş-sürünme mikro-scroll'u.
**QC (footage_qc, üretim OCR ile):** 14 filmde ort. text_recall 0.337→0.400;
karadeniz +0.23, son-konser +0.22, aile-babasi +0.16, beklenmedik +0.40;
benimle/gercek −0.05 (eski tekrarlı sayfalar OCR'a çift şans veriyordu; görsel
içerik tam). aydaki-adam'ın kayıp 4 ismi (Dr. Wilmot, Prof. Stephens,
Prospector, Storekeeper) geri geldi; kucuk-dev kart2 tamamen kurtuldu.

**Öğrenilen / başarısız denemeler:** (a) dy'yi tüm-gri veya metin-piksel NCC ile
doğrulama İKİ kez de sağlıklı filmleri bozdu (footage zemini / 1px yuvarlama) —
geri alındı, teşhis-amaçlı tutuluyor; (b) sabit istikrar-eşiği (0.75) grenli
soluk kartları dissolve'la aynı banda düşürüyor — eşik değil ŞEKİL (yerel tepe)
ayırır; (c) "en dolu kare" temsilci seçimi karışım karesini seçer (iki kartın
pikseli toplanır) — temsilci geçişten EN UZAK kare olmalı.

**Bekleyen:** (1) parti kök-sebebi bulundu: parlak zemin gray>110 maskesini
domine ediyor, korelasyon statik zemine kilitleniyor (dy≈0 ölçülürken yazı
akıyor) → det-kutu maske fallback'i (maske-kapsama >%25 → det yolu) YAPILACAK;
(2) kucuk-dev soluk kart çifti (dup 0.167) + segment-sınırı blok örtüşmeleri
(aydaki/yaren) → OCR-kanıtlı dikiş-kırpma son geçişi; (3) 427-tam koşu arka
planda (outputs/footage_pano427) — bitince eski-vs-yeni metrik kıyas + gerileme
avı ("bir şeyi düzeltirken başka şey bozduk mu" — Çağatay talebi); (4) son-metro
885-kare yüksek-fps boy_asimi (45k tavanı) — ölçek/birleştirme kararı; (5)
kompozitöre entegrasyon kararı (hangi filmler adaptif yola düşer: mod_hatasi
imzası mı, her scroll mu) → konsey kırmızı-takım turu SONRA.

## 2026-07-26 (devam 2) — "Dikiş-tekrarı" kök-sebep fix'i (F3c): 195 aday, 27 düştü

**İş:** F3b'nin ÜSTÜNE, `db_compose_master.py`'ye F3c eklendi (MITAS_MASTER_V2 flag
altında): kayan jenerik öncesi TUTULAN İLK KART bir static_page olarak dondurulup
HEMEN ardından gelen scroll_slit'in AYNI içeriği baştan tekrar etmesi ("dikiş-
tekrarı", görsel kanıt: acemiler-cetesi 90px "Harry Spikes/LEE MARVIN..." kesik +
slit aynı metinle yine başlıyor). `_f3c_seam_dup_check`/`_f3c_align_static_in_slit`:
cv2.matchTemplate ile statik kartın TAMAMI slit'in üst bölgesinde hizalanır, hizalı
bölge F1c'nin det+rec altyapısıyla token-karşılaştırılır (>=%70 örtüşme -> düş).
Testler: `test_f3c_seam_fix.py` (21), `test_saglik_dikis.py` (5) — saf mantık +
gerçek-OCR birim + uçtan-uca sentetik + REGRESYON-KİLİDİ (aşağıya bkz). Ayrıntı:
`docs/MITAS_Master_Dup_Kok_Sebep_Plani_v1.md` "Görev M11".

**DIŞ KONSEY bug-avcılığı turu (GLM cevap verdi; Qwen hesap-erişim HTTP 403
"AccessDenied.Unpurchased" hatasıyla İKİ turda da başarısız, Kimi ikinci turda
boş/hatalı döndü — ikisi de bilinen/harici sorunlar, koddan bağımsız):
**GERÇEK BULGU, KABUL EDİLDİ VE UYGULANDI:** statik kartta yalnız 1-2 (jenerik)
token varsa, %70 oran kolayca (1/1, 2/2) tetiklenebilir — F3C_TOKEN_MIN_LEN=3
karakter filtresi "cast"/"director" gibi kelimeleri elemiyor. GERÇEK 427-film
koşusunda BUNUN 2 örneği ÇIKTI (son-yolculuk-1999-.../ufaklik, ikisi de TEK
token: "cast") — görsel doğrulama ikisinin de GERÇEK dikiş-tekrarı olduğunu
kanıtladı (aynı "CAST" başlığı birebir konum/yazı-tipiyle iki kez) AMA NCC'leri
de çok yüksekti (0.9508/0.9754) — yani doğru kararlar TESADÜFEN değil güçlü
piksel-kanıtıyla tutarlıydı, kod bunu ise HİÇ ZORUNLU KILMIYORDU. Tüm 27 düşenin
(token_sayısı, NCC) çifti ölçülüp desen doğrulandı: token<3 olan HER düşende
NCC>=0.90; NCC<0.85 olan HER düşende token>=3 (silverado, 3 token, NCC=0.5512
en düşük sınır). Yani gerçek veri bu iki değişkenin BAĞIMSIZ ayrışmadığını
gösterdi ama kod bunu garanti etmiyordu (şans eseri tutarlı). Fix: `F3C_NCC_
HIGH_CONFIDENCE=0.85` / `F3C_MIN_TOKENS_LOW_CONF=3` — NCC>=0.85 ise az-token
yeterli (mevcut 2 gerçek vaka gibi), NCC bunun altındaysa >=3 FARKLI token
şart. DOĞRULAMA: 427-film TAM yeniden üretim → **27 düşen BİREBİR AYNI KALDI**
(0 fark, ne kaybolan ne yeni eklenen) — yani bu fix mevcut sonuçları DEĞİŞTİRMEDİ,
yalnız gelecekteki "birkaç jenerik kelime + orta-NCC" senaryosuna karşı kapıyı
kapattı. 20-film regresyon + bit-parite bu düzeltme SONRASI da yeniden koşulup
YEŞİL. 2 yeni test eklendi (`test_tek_jenerik_token_zayif_ncc_ile_korunur`,
`test_tek_jenerik_token_yuksek_ncc_ile_dusurulur`).

**Diğer konsey bulguları (değerlendirildi, düşük öncelik/asılsız):** `slw != sw`
guard'ı ve NaN/dtype riski kod incelemesinde zaten ele alınmış bulundu (`not
np.isfinite(best_ncc)` guard'ı mevcut); `np.argmax` flat-index kırılganlığı
(yalnız `slw==sw` guard'ı gevşetilirse potansiyel gizli hata) kayda geçti ama
GÜNCEL kodda tetiklenmiyor, DOKUNULMADI (spekülatif/gelecek-riski, bu turun
kapsamı dışı).

**Öğrenilen (ders, İKİNCİ kez tekrarlanan bir hata): konseye context alanına
İLK seferinde yanlışlıkla "DIFF_PLACEHOLDER" string'i gönderildi (gerçek kod
GİTMEDİ) — F3b turunda AYNI hata bir kez daha yapılmıştı (GUNLUK 2026-07-26
devam kaydı). GLM/Kimi bunu fark edip tarif-metninden genel değerlendirme
yaptı (dürüstlük doğruydu), ikinci turda gerçek diff'le düzeltilip yeniden
soruldu. KURAL HATIRLATMASI: konsey brifingine kod YAPIŞTIRIRKEN, gönderilen
mesajı bir daha oku, placeholder/özet SIZMADIĞINDAN emin ol.

**KENDİ HATAMI YAKALADIĞIM an (rigor sürecinin işe yaradığı somut örnek):** İlk
uygulama "slit'in İLK (static_h+1 satır) bölgesi"ni sabit varsayımla kırpıyordu.
Görsel doğrulama adımında (Read tool, piksel inceleme) acemiler-cetesi'nin HÂLÂ
düzelmediği ortaya çıktı — static_h=90 iken tekrar GERÇEKTE y=283'te başlıyordu
(slitscan()'ın `seed_top` ham-kare oranlı, statik kart METİN BANDINA sıkı kırpılı —
ikisi FARKLI koordinat sistemi). Sabit-pencere varsayımı bunu SESSİZCE kaçırıyordu
(0 token, "KORU" -- tam da düzeltilmek istenen kusuru yeniden üretiyordu). Düzeltme:
cv2.matchTemplate tabanlı hiza-arama (frame_h sınırlı). Ayrıca NCC-eşiği de yanlış
kalibre edilmişti (0.85, TEK örnekten) — 24-film GERÇEK-VERİ kalibrasyonu
(`harness/master_dup/kalibrasyon_f3c_ncc.py`) bunu ÇÜRÜTTÜ: yasli-adamlar-toplulugu
token-oranı TAM 1.0 ama NCC yalnız 0.4811 (0.85 KAÇIRIRDI); NCC ile token-oranı ZAYIF
KORELE (birdy/tas-devri NCC=0.88-0.91 AMA oran=0.0-0.54) — NCC'yi 0.3'e (zayıf ön-
filtre) düşürüp asıl kararı token-oranına bıraktım. DERS: "çalışıyor" demeden önce
GERÇEK veride GÖRSEL doğrulama + çok-örnekli kalibrasyon şart — tek temiz örnek
(acemiler'in İLK NCC ölçümü 0.9486) yanıltıcı güven verebiliyor.

**Ayrıca bir yan-hata (itiraf, düzeltildi):** Doğrulama sırasında bir zamanlama
testinde `out_root=None` ile `uret_ex.process_film_ex` çağrıldı, YANLIŞLIKLA
`data/master_ex/acemiler-cetesi` (F3b-ÖNCESİ taban referansı, `fix_dogrula.py`'nin
"ESKI" karşılaştırması kullanıyor) ÜZERİNE YAZILDI. Git commit 437dce8'in (bu dosyayı
üreten tam commit, timestamp+"369/427" sayısıyla doğrulandı) db_compose_master.py
sürümüyle YENİDEN üretilip düzeltildi (runs=['S','S'] deseni + F4-atlas izi ile
tutarlılığı doğrulandı) — ama orijinal dosyanın byte-birebir YEDEĞİ yoktu, bu yüzden
%100 kanıtlanamaz (yalnız yapısal/mantıksal tutarlılık). Düşük-blast-radius (yalnız
1/427 film, yalnız gelecekteki fix_dogrula.py yeniden-koşularını etkiler, F3c işini
etkilemez) ama KAYDA GEÇMELİ. DERS: `uret_ex`/`uret` fonksiyonlarını ASLA `out_root`
açıkça scratch'e işaret etmeden çağırma.

**Sayı (`data/master_ex_modfix`, F3b ÜSTÜNE F3c, 427 film idempotent-yeniden-üretim):**
104 (h<250 taban, teşhis sayımı) → **89** kalan aday (15 düştü); 195 (h'siz TÜM aday) →
**175** kalan (27 toplam düştü, 27/427 film). 8-rastgele-örneklem (h<250, kalibrasyon-
setinden ayrı): 0 düştü/8 korundu (rastgele çekiliş — MUHAFAZAKARLIĞIN kanıtı), her
biri rec-kanıtlı, 3'ü görsel doğrulandı (guvercin-hirsizlari: yazar/yönetmen vs
oyuncu listesi; umudunu-kaybetme: epilog-altyazısı vs oyuncu listesi; col-kralicesi:
ekip vs oyuncu listesi AYNI çöl-fonu üstünde — yüksek-NCC/sıfır-token örneği, NCC
tek başına yeterli OLMADIĞININ kanıtı). Ek 2 DÜŞEN örnek görsel doğrulandı (james-ve-
dev-seftali, acemiler-cetesi). YANLIŞ-SİLME KONTROLÜ: van-gogh-sonsuzlugun-kapisinda
("Paul Gauguin, 1894." sahne-altyazısı KORUNDU, "Gauguin" ismi sonraki oyuncu
listesinde geçmesine RAĞMEN — farklı stil/hizasız, NCC=0.17<0.3). Regresyon: 195-
aday-DIŞI 20 rastgele filmde byte-birebir aynı (0 fark, hem yapısal hem ampirik).
Bit-parite (flag kapalı, SON_METRO): YEŞİL.

**dup_metrik/saglik.py körlük denetimi:** dup_metrik'in "blok şartı" (>=2 ARDIŞIK
şerit) küçük (<200px) dikiş-tekrarını gürültü sayıp ELİYORDU. `saglik.py`'ye
`dikis_tekrari_supheli_kontrol` eklendi — final PNG üzerinde composer kararına
GÜVENMEDEN bağımsız yeniden-denetim, K4-i (imha_imzasi) gibi SAĞLIĞI ETKİLEMEYEN
teşhis bayrağı (`--no-dikis-kontrolu` ile kapatılabilir).

**Bekleyen:** (1) `compose_slit`'in KENDİ card→scroll bitişikliği (F3c'nin dokunmadığı
AYRI kod yolu, passthrough'ta kullanılıyor) AYNI kusuru taşıyor mu — ÖLÇÜLMEDİ, emin
değilim, ayrı inceleme önerilir; (2) 89 kalan (h<250) + 175 kalan (h'siz) adayın
TAMAMI gerçek-ayrı-kart mı yoksa F3c'nin kaçırdığı ek dikiş-tekrarı mı içeriyor --
saglik.py'nin yeni sinyali bunu izleyecek ama tam-427 saglik.py koşusu bu oturumda
TAMAMLANMADI/sonucu henüz özetlenmedi; (3) data/master_ex/acemiler-cetesi'nin
restorasyonu %100 byte-doğrulanamadı (yukarı bkz).

## 2026-07-26 (devam) — Mod-hatası KÖK-SEBEP FIX'i uygulandı: 137→13 (F3b)

**İş:** Bir alt oturumda, aşağıdaki kayıttaki "Aşama-2 sınıflandırıcı fix" tamamlandı.
`OCR-worktree/db_compose_master.py`'e F3b eklendi (MITAS_MASTER_V2 flag arkasında):
`_text_masked_dy_series()` (estimate_offsets ile AYNI text_mask+11x11-dilate deseni,
her karede EK metin-maskeli dy/response) + `_f3b_text_masked_rescue()` (mod_denetim.py
ile TAM AYNI imza: kayan_oran>=0.35, monoton>=0.75, medyan|dy|>=F3_RUN_DY_FLOOR_PX/30px,
response>0.10, min 8 örnek). `_resolve_reading_runs()`'ta nihai "S" koşuları bu imzayla
yeniden sınanıp tutarsa "R"ye çevriliyor + bitişik "R" koşuları TEK run'a birleştiriliyor
(ayrı bulgu aşağıda). Commit'ler: 3dc9435 (fix+testler), 1990d16 (uret_ex --cikti-kok /
mod_denetim --kok, ayrı kök `data/master_ex_modfix/` — mevcut master_ex EZİLMEDİ).

**Sayı:** 427-film tam koşu: mod_hatası **137→13** (%90.5 azalma). 290 orijinal-sağlıklı
filmin **0'ı** yeni mod_hatası oldu (regresyon sinyali TEMİZ); 215'i byte+run birebir
aynı kaldı; **75'i değişti ama mod_hatasi=False kaldı** — bunlar mod_denetim'in kaba
40-örnekli tüm-film ölçümünün KAÇIRDIĞI ek gerçek mod-hatalarıydı (matematiksel doğrulama:
427 filmin TAMAMINDA yalnız S->R yükseltme + bitişik-R birleşme oldu, hiç R içeriği
kaybolmadı, zaman-çizelgesi kapsamı birebir korundu — 0 anomali). 5 film (acemiler-cetesi,
dogrucu-dudley, komiser-cordier-yuksek-guvenlik, babam-ve-ben, benimle-dans-et) GÖRSEL
doğrulandı: ghosting/tekrar kalktı, isimler tek sefer, ek içerik ortaya çıktı (ör.
dogrucu-dudley: 32 blok tekrarlı → 1 temiz şerit). solaris (gerçek-statik pilot) byte-
birebir DEĞİŞMEDİ. Bit-parite (flag kapalı) YEŞİL.

**ÖNEMLİ BULGU (dış konsey turu, GLM+Kimi bağımsız bug-avcılığı, Qwen 403-unpurchased):**
diff'i ilk seferinde placeholder-metniyle gönderdim (gerçek kod gitmedi) — Kimi bunu
DÜRÜSTÇE reddetti ("göremediğim kodu onaylayamam"), GLM bağlamdan genel değerlendirme
yaptı. İkisi de BAĞIMSIZ olarak aynı riski işaret etti: bitişik-R birleştirmesi yalnızca
bir çeviriden kaynaklanan bitişikliği mi hedefliyor, yoksa körü körüne HER bitişik R-R'yi
mi birleştiriyor? Yapısal ispat (raw_runs hiç bitişik-R-R üretemez) doğruydu ama "kemer-
ve-aski" gardı (merge yalnız en az bir taraf O geçişte çevrildiyse) yine de eklendi —
ucuz, zararsız, ileride başka bir F1/F2/F4 etkileşimi ispatı bozarsa koruma sağlıyor.

**Öğrenilen (ders):** (1) mod_denetim.py'nin 40-örnekli TÜM-FİLM alt-örneklemesi, uzun
filmlerde (>40 kare) ADIM-ARASI değil SEYREK-ARALIKLI dy ölçüyor (213 kareli karinca'da
ölçülen dy_medyan=116.9 ama GERÇEK ardışık-kare dy_medyan=23.2 — ~5x fark, tam da
213/40 örnekleme-aralığı oranı). Kalan 13'ün 8'i BUNDAN: gerçek/monoton kayma ama
ardışık-kare hızı 21-28px, F3_RUN_DY_FLOOR_PX=30 tabanının HEMEN altında kalıyor —
sonraki kalibrasyon adayı (taban veriyle yeniden ölçülebilir, ama bu oturumda
DOKUNULMADI — mevcut F3 mekanizmasının da paylaştığı established güvenlik marjı).
(2) 1'i örnek-sayısı (SLIT_HY_MIN_MEAS=8) tabanının altında kısa run (beklenmedik-miras).
(3) 3'ü (aydaki-adam, gercek-yalanlar, kucuk-dev-adam) mod_denetim'in BAĞIMSIZ Sobel-
gradyan maskesiyle benim text_mask (tophat/blackhat) arasında ayrışıyor — iki FARKLI
maskeleme yöntemi, beklenen sapma, hangisi "doğru" görsel incelemeyle netleşir. (4)
komiser-cordier-yuksek-guvenlik + babam-ve-ben görsel incelemesinde: künye SABİT bir
fotoğraf/sahne üstünde kayarken slit-scan metni temiz yakalıyor ama ARKA PLAN görseli
dikey olarak "döşeniyor" (fayans gibi tekrarlıyor) — içerik kaybı YOK, estetik artık ama
M4b'nin ("footage-üstü kayan künye") bahsettiği ayrı sınıfla örtüşüyor, bu oturumda
düzeltilmedi.

**Bilinçli kapsam kararı (Fable/Çağatay onayına açık):** Fix YALNIZ `split_runs_reading`
(mixed-mode karar) yolunu değiştiriyor; `split_runs` (strict_scroll_frac/passthrough
kapısı + compose_slit'in kendi iç R/S kararı) BİLEREK dokunulmadı — 137 filmin TAMAMI
zaten ssf<0.25 mixed-mode yolundaydı (ölçülmüş), yani split_runs_reading fix'i ölçülen
hedefe yeterliydi; split_runs'a AYNI tedaviyi uygulamak muhtemelen daha da iyi olurdu
(daha temiz tek-parça passthrough) ama 249 sağlıklı filmin ssf'ini de değiştirebilir —
regresyon yüzeyi daha geniş/az-sınanmış. Bilinçli olarak ERTELENDİ, ayrı karar/tur önerilir.

**Bekleyen:** (1) 30px taban kalibrasyonu (8 filmi daha kurtarabilir — veri-güdümlü ayrı
tur); (2) split_runs'ın kendisi de mi fixlensin (yukarıdaki kapsam kararı); (3) M4b
(footage-üstü döşeme) bu fix'le mi ele alınsın yoksa ayrı mı kalsın; (4) Katman-0/1
sadakat kabul-kapısı (aşağıdaki kayıt) bu fix'in çıktısını (master_ex_modfix) ölçmeli;
(5) 3 ayrışan-maskeli film (aydaki-adam vb.) görsel karar bekliyor.

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
