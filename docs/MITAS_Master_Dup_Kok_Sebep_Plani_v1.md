# Master PNG Duplikasyon Kök-Sebep Kampanyası (v1)

> **Uygulayıcı ajanlar için:** Görev-görev uygulanır (subagent-driven, Sonnet).
> Orkestratör (Fable) görevler arası inceler. Bu hat, jenerik-onset hattından
> BAĞIMSIZ penceredir: `harness/kunye_kiyas/*` dosyalarına DOKUNULMAZ
> (diğer oturum orada çalışıyor); bu hattın alanı `harness/master_dup/*` (yeni),
> `OCR-worktree/db_compose_master.py` (yalnız M4'te, FLAG arkasında) ve `docs/*`.

**Hedef:** `reading_master_runaware` master-PNG'lerindeki tekrar bloklarını
(VL modellerini thinking-döngüsüne kilitleyen kusur) kök sebebiyle çözmek.
Kabul: 112-film üretiminde dup-metriği eşik altı + içerik-koruma (benzersiz
OCR-satır recall ≥ legacy) + flag kapalıyken legacy bit-parite + Çağatay'ın
vereceği KÖR büyük test setinde doğrulama.

**Onaylı yaklaşım (Çağatay):** Teşhis-önce, flag-arkasında fix. Tasarım Fable,
uygulama Sonnet, GLM+Kimi kırmızı takım (M4 öncesi zorunlu tur; bu turda
üçü de erişilemedi — yeniden denenecek).

## Küresel Kısıtlar

- Python: `/opt/mitas/venvs/ocr/bin/python`. PaddleOCR stderr gürültüsü → `2>/dev/null`.
- `pkill -f` YASAK; PID-hedefli kill.
- `harness/kunye_kiyas/*` SALT-OKUNUR (paralel oturemin alanı). GT dosyaları değiştirilemez.
- Üretim dosyaları: `OCR-worktree/db_compose_master.py` M4'e kadar SALT-OKUNUR;
  M4'te yalnız `MITAS_MASTER_V2` flag'i arkasında değişir (flag kapalı = bit-parite).
  `scripts/mitas_pipeline.py` bu kampanyada HİÇ değişmez.
- Kaynak filmler: `harness/kunye_kiyas/veri/eslesme.tsv` (kaynak_dosya→hedef_klasör)
  + `dogrulama_sonuc.json` (onset GT) + `dislanan.json` (3 film hariç).
  smb: `/run/user/1000/gvfs/smb-share:server=depo01cifs.int.trt.net.tr,share=sas_h264/Film Kapanış/`
  (mount düşerse `gio mount smb://...` ile bekle-tekrarla; gio copy → yerel tmp → ffmpeg).
- Disk: parti-parti çalış (pencere karelerini üretim+ölçüm sonrası SİL; master+manifest+metrik kalır).
  Çıktı kökü: `/opt/mitas/data/master_dup/` (kareler `_pencere_tmp/`, kalıcılar `masters/<FİLM>/`).
- Commit: Türkçe, küçük, sık; yalnız kendi dosyalarını stage'le (`git add -A` YASAK).

## Tasarım özeti

Üretici akışı (db_compose_master.py:1002 `compose_reading_runaware`):
`strict_scroll_frac≥0.75` → `compose_slit` TAM passthrough; değilse karışık mod
(scroll koşuları slit, statik koşular sharpv-en-net "sayfa"; dedup SADECE ardışık
kart dHash ham≤2 + açılışta maske-IoU). Girdi: fps=1.5 native kareler (scroll'da
kare-arası dy≈75px).

Duplikasyon hipotezleri (atlasla kanıtlanacak):
- **H1** slit dy tahmin hatası → bitişik dilimlerde satır tekrarı (1.5fps'te dy büyük; kayma=büyük blok).
- **H2** ardışık-OLMAYAN kart tekrarı gardı yok (kart A → sahne → kart A yine girer).
- **H3** scroll koşusu statik sanılırsa her kare "sayfa" → devasa örtüşen tekrar.
- **H4** pencere yanlışsa (jenerik-dışı sahne) slit çığırından çıkar (600×36695 canavarlar).

---

### Görev M1: Dup-metriği `harness/master_dup/dup_metrik.py`

**Arayüz:** `olc(png_yolu) -> dict`:
`{"dup_oran": float 0..1, "blok_sayisi": int, "bloklar": [{"y1":..,"y2":..,"es_y1":..,"es_y2":..,"benzerlik":..}],
"boy": [W,H], "doku_kapsami": float}` + CLI `dup_metrik.py <png|klasör> [--esik 0.92] --json çıktı`.

Algoritma (tasarım kararları — uygulamada koru):
1. Gri + genişlik 400px'e normalize et. Şerit yüksekliği = metin-satır yüksekliği
   tahmini ×2 (satır yüksekliği: yatay kenar-yoğunluğu profili otokorelasyon tepesi;
   bulunamazsa 48px). Şeritler %50 örtüşmeli kaydırılır.
2. **Doku kapısı:** kenar-yoğunluğu tabanın altındaki şeritler (boş/karanlık ara
   bantlar) metrik DIŞI — yanlış-pozitifin ana kaynağı. `doku_kapsami` raporlanır.
3. Her dokulu şerit çifti (bitişik + UZAK, tüm çiftler; H yüksekse şerit dHash'iyle
   ön-eleme → yalnız yakın hash'li çiftlere NCC): normalize çapraz-korelasyon
   (dikey ±şerit/2 hizalama aramalı). Benzerlik ≥ eşik (varsayılan 0.92) = eş.
4. **Blok şartı:** tek şerit eşleşmesi SAYILMAZ (meşru tekrar: aynı rol başlığı,
   logo). ≥2 ARDIŞIK şerit aynı ofsetle eşleşirse duplikasyon bloğu. dup_oran =
   duplike şerit alanı / dokulu toplam alan.
5. Sentetik birim testleri (kod içinde üretilen görüntülerle): (a) temiz sahte-künye
   → dup_oran≈0; (b) aynı görüntünün alt alta 2 kopyası → ≈0.5; (c) %30'u
   tekrarlanmış → ≈0.3; (d) boş-siyah geniş bantlı temiz → ≈0 (doku kapısı kanıtı);
   (e) tek satır tekrarı (rol başlığı simülasyonu) → 0 (blok şartı kanıtı).

Adımlar: kod → testler yeşil → SON_METRO gerçek örneğinde koş (değer raporla,
yorumla) → commit `feat(master-dup): şerit-tabanlı dup-metriği + sentetik testler (M1)`.

### Görev M2: Aslına-sadık üretim harness'ı `harness/master_dup/uret.py`

**Arayüz:** `uret.py [--film AD_PARCASI] [--n N] [--paralel K]` → her film için
`/opt/mitas/data/master_dup/masters/<FİLM>/{reading_master.png, manifest.json, metrik.json}`
+ toplu `veri_ozet.json`.

1. Film listesi: eslesme.tsv ∩ dogrulama_sonuc(karar bilgisiyle) − dislanan;
   `gercek_onset==-1` filmler LİSTE DIŞI değil — onlar "kredisiz" kontrol grubu
   (pencere: son 240s; master yine üretilir, kusur davranışı gözlenir) ama ana
   küme kredi-var filmler (pencere: onset_saniye−15s → film sonu; onset_saniye =
   gercek_onset/2 çünkü GT 2fps kare numarası; kaynak süresinden mutlak zamana çevir:
   pencere_başı = süre − 600 + gercek_onset/2 − 15).
2. Çıkarım: gio copy → tmp mp4 → `ffmpeg -ss <pencere_başı> -i tmp -vf fps=1.5 -q:v 3
   c_%05d.png` (native çözünürlük, ÜRETİMLE AYNI). mp4 ve kareler iş bitince silinir.
3. Kompozisyon SADAKATİ: `OCR-worktree/master_png_monitor.py`'daki
   `_compose_reading_seg(frames, args)`'ı İMPORT ederek kullan; `args`'ı monitor'un
   argparse VARSAYILANLARINDAN programatik kur (kopyala-yapıştır değil —
   `parser.parse_args([])`). Böylece üretimle parametre birebir.
4. Her master için M1 metriği + manifest alanları (mode, strict_scroll_frac, runs,
   kept_blocks, size) kaydet.
5. Doğrulama: 3 pilot film (1 scroll-ağır, 1 kart-ağır, 1 kredisiz) uçtan uca;
   SON_METRO probe ile aynı parametrelerde yeniden üretim → mevcut
   `outputs/SON_METRO_master_probe_.../reading_master_runaware.png` ile boyut/manifest
   karşılaştır (sadakat kanıtı). Commit `feat(master-dup): üretim harness'ı (M2)`.

### Görev M3: 112-film duplikasyon atlası

1. `uret.py --paralel 3` ile tüm filmler (indirme ~30-60s/film; toplam birkaç saat,
   arka planda; ilerleme logu). smb kopması → bekle-tekrarla (havuz_kur deseni).
2. `atlas.py`: metrik+manifest birleştir → `veri_ozet.json` + `dup_atlasi.md`:
   dağılım (dup_oran histogramı), mod×kusur tablosu (passthrough-slit / karışık /
   canavar-boy), en kötü 15 film şerit-örnekli teşhis (hangi hipotez: H1 slit-tekrar
   ofset deseni / H2 uzak-kart eşleşmesi / H3 sayfa-örtüşmesi / H4 boy-anomalisi:
   H, beklenen-scroll-boyunun katı). Her kötü vaka için master'dan kanıt-kırpımı
   PNG'si (`kanit/` klasörü) — orkestratör ve Çağatay GÖZLE doğrulayabilsin.
3. ÖZET tablosu orkestratöre raporlanır (hipotez → film sayısı → önerilen fix yönü).
   Commit `feat(master-dup): 112-film duplikasyon atlası (M3)`.

### Görev M4: Kök-sebep fix'leri — FLAG arkasında (atlas kanıtı + konsey turu SONRASI)

KONSEY KARARI (2026-07-23, GLM tam katılım; Kimi 429, Qwen 403-unpurchased):
- KABUL: dHash uzak-kart aday kapısı ham≤2→≤4 (codec artefaktı); IoU≥0.5 yerine
  hizalı-XOR fark-bandı (yerel bant farkı → kart KORUNUR; silme yalnız
  metin-özdeşliğinde); F3 dy eşiği ≥30px (titreme/gate-weave bandı 0-15px ezilir);
  her distant-dup atlaması manifest'e denetlenebilir yazılır + harness'ta
  atlanan-blok OCR-özdeşlik denetimi; F2 kırpma yalnız NCC≥0.9 hizada ve
  segment-yarısı üst sınırıyla (dur-devam scroll koruması). H5 ertelemesi ONAYLI
  (güvenli yön notu: kart kabulünde sharpv kararlılığı).
- RED (hakem: Fable): composer içinde OCR-Levenshtein kapısı — üretim yoluna
  PaddleOCR bağımlılığı/maliyeti; GLM'in "üretimde zaten OCR var" varsayımı yanlış.
  Levenshtein-tarzı metin denetimi HARNESS tarafında (M5 skip-audit) yapılır.

F1b DÜZELTMESİ (2026-07-23 gece, orkestratör ölçümleri — M4 ilk turu H2'yi ÇÖZEMEDİ):
- Bulgu 1: v2 çıktıları legacy ile birebir aynıydı; sebep bayrak DEĞİL (provenance=1
  doğrulandı) — F1'in dHash aday kapısı GRENLİ donuk-sahne sayfalarında hiç
  tetiklenmiyor (film greni textmask-dHash'i ham≤4'ün çok ötesine savuruyor;
  BAŞKAN 16 sayfa, 0 aday).
- Bulgu 2: metin-yoğunluğu sınıf ayıramıyor (donuk 0.02-0.08 vs gerçek kart
  0.02-0.27 — örtüşüyor); "metinsizse NCC yeter" öncülü ÇÖKTÜ.
- Bulgu 3 (GÖRSEL KANIT, yp_P2_P4.png): YAKIN_PLAN'da farklı-altyazılı çiftin
  piksel farkı (global 0.013/bant 0.045), BAŞKAN'ın aynı-donuk çiftlerinin gren
  farkından (0.013-0.045/0.021-0.080) AYIRT EDİLEMEZ → salt-piksel kapısı
  imkânsız; ayrım sinyali METİN VARLIĞI.
- KARAR (GLM'in composer-içi OCR önerisine kısmi dönüş — det-only orta yol):
  F1b: gri faz-hizalı bant-fark ile piksel-benzer sayfa-çifti adayı bul
  (kalibre eşikler: global<0.06 VE maksbant<0.10; ölçüldü, marjlı) → sonra
  PaddleOCR TextDetection (det-only, ~0.02sn/sayfa, TEMBEL init, yalnız v2 +
  yalnız aday sayfalarda, sayfa-başına önbellek):
  (a) iki sayfada da det-kutusu 0 → SKIP (kaybolacak metin yok);
  (b) kutular varsa: kutu sayıları eşit + konumlar toleransta + HER kutu-bölgesi
      kırpımı NCC≥0.90 → özdeş-metin tekrarı, SKIP; aksi halde KORU.
  YAKIN_PLAN altyazı farkı (kutu içeriği farklı → NCC çöker) ve "Gün 1/Gün 2"
  (rakam kutusu NCC düşük) yapısal olarak korunur. Eski dHash+XOR yolu aynen
  kalır (temiz özdeş kartlar için).

F1c KARARI (2026-07-24 M4-sonu teşhisi): kalan direncin kök sebebi HAYALET
KUTULAR — det, donuk sayfalardaki doku/özne hareketini kutu sanıyor (skor
0.7-0.93, tek küçük kutu), sayfa "text" yoluna düşüyor, doku-NCC (0.29-0.69)
doğal olarak eşiği tutmuyor → KORU. Alan/skor filtresi RİSKLİ (YAKIN'ın gerçek
altyazı kutusu da küçük — filtre onu da öldürür, içerik kaybı). GÜVENLİ ayrım:
aday-çiftte tartışmalı kutulara REC — rec boş/`skor<0.6` → hayalet, yok say;
iki sayfa da gerçek-kutusuz kalırsa scene-skip; gerçek kutular kalırsa normalize
metin EŞİTLİĞİ şartıyla skip ("distant-dup-rec"), aksi KORU. Maliyet sınırlı:
yalnız piksel-benzer aday çiftlerinde. Ayrıca F2'nin hiç tetiklenmemesi
(ardışık slit-slit bloğu havuzda oluşmuyor) ve F3-kapsam bulgusu
(ŞEYTAN_RUHLU: split_runs/split_runs_reading etiket ayrışması — farklı
mekanizma) kayda geçti; H1/H3 artıkları M5 sonrası ayrı mini-karar.

ÖN KOŞUL: M3 atlası + GLM/Kimi kırmızı-takım turu (orkestratör açar; M3 kanıtı
brifinge girer). Muhtemel fix'ler (atlas neyi kanıtlarsa O uygulanır):
- H1 → slit dilim birleştirmede dy-doğrulamalı örtüşme kırpma (bindirmeyi NCC ile
  hizala-kes; dikiş manifest'e işlenir).
- H2 → global kart-dHash kaydı: yeni kart, ÖNCEKİ TÜM kartlarla ham≤eşik + maske-IoU
  çift kapısıyla karşılaştırılır; eşleşme "skip: distant-dup" (İÇERİK KESME RİSKİNE
  KARŞI: yalnız kart-modu bloklarına uygulanır, slit bölgelerine ASLA).
- H3 → koşu sınıflandırma düzeltmesi (dy kanıtı olan koşu sayfa moduna düşemez).
- H4 → pencere-sağlık kapısı: beklenen-boy üst sınırı (toplam_scroll_dy + kart_toplamı
  payı) aşılırsa manifest'e `size_anomaly` + slit'e sınır.
Hepsi `MITAS_MASTER_V2=1` arkasında; flag kapalı → M2 pilotlarında bit-parite testi
(`np.array_equal`). Her fix ayrı commit + 112'de metrik yeniden.

### Görev M4b: Footage-üstü kayan künye İMHASI — kompozisyon fix'i (KONSEY KARARI)

KEŞİF (2026-07-24, görsel kanıt + 112-tarama): kompozitör, künyesi footage üstünde
kayan filmlerde metni İMHA ediyor (BAŞKAN: zemin 16× sayfa, yazı 13px'e ezik;
sınıf ~8-17 film). Dedup bunu GERİ GETİRMEZ — kök kompozisyonda.
KONSEY (GLM tam katılım; Kimi 3× boş; Gemini/GPT/NVIDIA sunucu-restart bekliyor):
teşhis "Nyquist ihlali" — 1.5fps'te kare-arası kayma (75px+) satır yüksekliğini
aşıyor; satırlar kare-arası boşluğa DÜŞÜYOR → hiçbir piksel sihri geri getiremez.
A (medyan) parçalar; C (kutu-hasadı) tek başına satır kaçırır (örtüşme sıfır
olabilir); B tek başına dedektör, restoratör değil. KARAR (hakem: Fable, GLM'in
hibrit savunması kabul):
- **B-tespit**: OVERLAY_SCROLL koşu imzası = global kare-korelasyon yüksek (zemin
  durağan) + det-kutu bölgelerinde tutarlı kayan dy + ardışık karelerde kutu
  İÇERİĞİ farklı (rec). Üçü birden → tetik (yanlış-pozitif ≈ 0; mevcut düzgün
  masterlar KIRMIZI ÇİZGİ).
- **D-ROI yeniden çıkarım**: yalnız tetiklenen pencere + yalnız kutu-birleşke ROI,
  6-12fps yeniden decode (üretimde video elde; maliyet pencere-sınırlı).
- **Slit'i yüksek-fps ROI karelerle koştur** (dy 15-20px'e düşer, mevcut matematik
  çalışır); metin şeridi + zeminden TEK temsilci sayfa.
- **Fallback (kaynak erişilemezse): OCR kutu-hasadı metin-duvarı** — kutu
  kırpımlarının koordinat-sıralı istifi; görsel stil kaybolur ama künye OKUNUR
  (MITAS'ın asıl tüketicisi dilim→VL okuma olduğundan iş-değeri yüksek).
Uygulama F1c kapanışından SONRA (aynı dosya, sıralı); MITAS_MASTER_V2 bayrağı
altında, bit-parite korunarak.

### Görev M5: Kabul

(a) 112'de dup_oran medyanı ≈0 ve maksimum < 0.05 (eşik atlas dağılımına göre
kesinleşir, orkestratör onayı); (b) içerik-koruma: 20-film örnekleminde v2 master'ın
benzersiz OCR-satır kümesi (PaddleOCR rec, normalize) ⊇ legacy'nin %98'i — künye
kesilmedi kanıtı; (c) flag kapalı bit-parite; (d) 5 en-kötü vakada önce/sonra
gözle karşılaştırma PNG'leri; (e) VL spot-testi: eski kilitlenen tip (thinking-model)
3 filmde v2 master ile denenir — döngü yok beklentisi; (f) Çağatay'ın KÖR test seti
geldiğinde aynı ölçüm tekrarı.

### Görev M7: BÜYÜK KOŞU — Ex_Frame 427 film (/goal: sağlıklı-master ≥%91)

Çağatay direktifi (2026-07-24): korpus artık `/home/cagatay/Ex_Frame/*-exit_frames/`
(427 film; kareler JENERİK BAŞLANGICINDAN başlıyor — onset adımı YOK; ~1.25fps,
exit_%06d.png, 600×480). Hedef: filmlerin ≥%91'i SAĞLIKLI master üretsin.

**SAĞLIK TANIMI (ölçülebilir; taban koşusundan sonra kalibre edilip kilitlenir):**
bir master sağlıklıdır ⇔
1. üretim OK (status=OK, istisna yok, kept_blocks≥1);
2. dup_oran ≤ 0.10 (F1/F1b/F1c sonrası);
3. boy makul: 300px ≤ H ≤ 45000px (canavar/boş değil);
4. imha-imzası YOK (statik-sayfa alanı >%70 VE ≥2 cılız blok (h<25px) birlikteliği
   = footage-üstü kayan yazı ezilmesi şüphesi → sağlıksız);
5. doku_kapsami ≥ 0.05 (kapkara/boş master değil).

**Yol:** (1) uret_ex.py adaptörü — yerel kare klasörlerinden (indirme yok),
monitor-birebir args + MITAS_MASTER_V2=1; (2) saglik.py sınıflandırıcı + toplu
rapor; (3) TABAN koşusu 427'de → sağlık oranı + sağlıksızların sınıf dağılımı;
(4) en büyük sınıftan başlayarak kanıt-güdümlü düzeltme turları (F1c ayarı /
M4b-fallback OCR kutu-hasadı — Ex_Frame'de kaynak video YOK, D-ROI çıkarımı
uygulanamaz, fallback birincil kurtarıcı) → her turda tam yeniden ölçüm;
(5) ≥%91'de kabul + 112-sette regresyon kontrolü.
Not: 1.25fps, Nyquist açısından 1.5'ten de kötü — overlay sınıfı Ex_Frame'de
daha görünür olabilir; sağlık dağılımı bunu ölçecek.

### Görev M8: Ex sağlık turları — KONSEY KARARLARI (GLM+Nemotron, 2026-07-24)

Sınıflandırma (30-örneklem, görsel tanıklı): A1 statik-kart-tekrar ~63, A2 slit-tekrar
~41, C meşru-farklı-metin ~27, D metrik-FP ~5, B(imha) ~0. 51/135'te fix'ler hiç
tetiklenmemiş (gren aday-eşiklerini aşıyor). Konsey verdiktleri (ikisi de şartlı-kabul;
Kimi/MiniMax uzun-brifing zaman aşımı):

- **K1 (A1)**: aday eşikleri EX-korpusta yeniden kalibre (film-içi aynı/farklı çift
  setiyle, F1≥0.95 hedefli) + koşu-içi tüm-çift (hash ön-eleme + aday tavanı 50/koşu
  + rec-çağrı logu). GÜVENLİK HAKEM KARARI (GLM-Nemotron ihtilafı çözümü):
  rec-eşitlik yolu kalibre eşiklerle çalışır; 0-kutu SAHNE-birleştirme yolu ise
  yalnız ÇOK SIKI piksel-özdeşlikte (global_fark<0.02) — pikseller özdeşse det'in
  kaçırdığı silik metin bile tutulan kopyada birebir vardır → içerik-kaybı yolu
  matematiksel kapalı. rec düşük-güven/boş → DAİMA koru.
- **K2 (A2)**: (c) ama mutfak (b): dy düzeltmesi ÖNCE (slit-bbox kilitli, metin-satır
  profili/FFT periyot, kutu-maskeli); kırpma yalnız DİRENÇLİ artıklarda ve
  rec-Levenshtein≤2 + ≥2 ardışık + ikinci-kopya-atılır + düşük-güven→koru gardlarıyla.
  dy düzeltmeden slit-içi kırpma ASLA. EN SON uygulanır (en riskli).
- **K3 (C-muafiyeti)**: meşru ölçüm düzeltmesi — ama kanıt sıkı: iki karede de det≥1
  kutu + rec conf≥0.7 + normalize sonrası Levenshtein≥3 VEYA Jaccard≤0.7; manifest'e
  {text_a,text_b,protected} kaydı; ≥100 etiketli çiftlik recall≥0.9 testi ŞART.
- **K4**: (i) imha-imzası SAĞLIK formülünden ÇIKAR (Ex'te 6/6 FP) — teşhis bayrağı
  olarak kalır, sağlığı etkilemez; (ii) tek-kart istisnası: kept_blocks≤3 AND
  status=OK AND det-metin-var → boy kontrolü atlanır.
- Uygulama SIRASI: K4 → K1 → K3 → K2; her aşamada golden-set (30 film + ≥100 çift)
  yeniden koşulur, içerik-kaybı 0 şartı; toplam süre ≤1.5× mevcut; film başına
  health_report alanları (dup_pairs/protected_pairs/removed_pairs/rec_calls).
- K5 (opsiyonel güçlendirici, GLM): det/rec KARAR girdilerine hafif zamansal-medyan
  gren azaltma (kompozisyon pikselleri DEĞİŞMEZ, yalnız karar yolu) — K1 sonrası
  ölçülerek denenebilir.

### Görev M6: Kayıt

GUNLUK kaydı + bu doküman güncellemesi (konsey kararları, sayılar) + görev #12 kapanışı.
