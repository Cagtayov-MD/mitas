# Kobe — eksikler listesi

> **Yeni hat notu (2026-08-17):** `Allstar/sheriff` yolu için aktif Kobe kodu
> Allstar dışı Python modülü kullanmaz. Aşağıdaki `scripts/` maddeleri emekli
> hattın tarihsel geçiş kayıtlarıdır; Sheriff bağımlılığı değildir.

> 2026-08-13 itibarıyla, koddan doğrulanmış durum. Her madde: **ne eksik ·
> neden önemli · nereye bakılacak · kaba maliyet**.
> Kararların gerekçesi `DURUM.md`, mimarî `KATALOG.md`.

---

# ÇIKIŞ (kapanış jeneriği)

## Yapıldı ✅

| | Kanıt |
|---|---|
| Motor kuleye taşındı, `figo` adı silindi | `src/motor.py` 1325 satır, commit `3577c8b9` |
| Kendi çalışma zamanı (paddle 3.3.1 + CUDA, 167 pin) | `venv/`, `venv_kur.sh` |
| Sözleşme — `Girdi`/`Cikti`/`ariza`, atomik yazım + `_TAMAM` | `sozlesme.py` |
| CLI — `tek` / `start`, idempotent toplu kuyruk | `main.py`, `kobe` |
| Artefakt — kare havuzu + sessiz klip, onset−10 sn | `--uret kare\|klip` |
| Bölüm ayrımı — `out/<film>/cikis/` | `--bolum` |
| Ölçüm yatağı — 120 film + GT, kule içinde | `olcum/`, `havuz/` (28 GB) |
| **E1 — üretim sözleşmeye bağlı** (kobe CLI alt-süreç, A/B birebir) | `scripts/_jenerik_pool.py:_kobe_karari_al` |
| **Üç ölçüm kapısı, sapma sıfır** — %94.5 / %97.3 / 29-29 | `raporlar/olcum_*.json` |
| Golden kanarya (tek film, saniyeler) | `golden/tek_film.json` |
| 69 test | `tests/` |
| Belgeler | `KATALOG.md`, `README.md`, `CHANGELOG.md`, `DURUM.md` |

## Eksik ❌

### E1 — ✅ YAPILDI (2026-08-17) — üretim hattı kuleyi KULE olarak kullanıyor

`scripts/_jenerik_pool.py` artık `import motor` YAPMAZ: `_kobe_karari_al()`
`kobe tek --kareler ... --film-id ...` alt-sürecini koşar ve kararı kulenin
sözleşmesinden (`out/<id>/cikis/kobe.json`) okur. Sözleşme, `_TAMAM` kuyruğu ve
sürüm dondurma (kendi 167-pin venv'i) üretimde devrede. ARIZA → CV fail-safe
korundu. Doğrulama: 3 gerçek filmde (1 BULUNDU + 2 KREDI_YOK→CV) eski/yeni
manifest **birebir aynı**; golden kanarya aynı karar (kare 1133). Kobe tarafında
`main.py` kanıt telemetrisi genişledi (tip/scroll/suphe/... — manifest'in `v5`
alt-nesnesi bunlardan beslenir; karar alanları değişmedi) + 1 yeni test
(70/70). Kalan bağ: `MITAS_JENERIK_V5` env bayrağı hâlâ pool tarafında —
yönlendirme sorumluluğu orkestratörde, bilinçli.

---

### E2 — ✅ YAPILDI (2026-08-17) — `src/cikis/` + `src/ortak/` ayrımı

Kararlaştırılan yapı kuruldu: `src/cikis/motor.py` (DONMUŞ — **dosyaya sıfır
diff**, `git mv` ile yalnız taşındı), `src/ortak/kutu.py` + `src/ortak/
icerik.py` (aletler), `src/giris/` yerinde. `motor.py`'nin `kutu`/`icerik`
importları fonksiyon-içi tembel olduğu için yol ayarları ÇAĞIRAN tarafta
çözüldü (`main.py`, `olcum/*.py`, `tests/`) — donmuş dosyaya tek satır
girmedi. `test_izolasyon.py` yeni yapıya bağlandı + yapıyı kilitleyen
bekçi (`test_yapi_kilitli`) eklendi — 71/71.

**Kapı:** `olc_pool.py --paralel 8` → kapsam 110, genel **104/110 = %94.5**,
üretim **107/110 = %97.3**, kredi-yok **29/29**, eksik 5 — **sapma sıfır**,
hata listesi bilinen 6 filmle birebir (`raporlar/olcum_E2.json`).
Golden kanarya: BULUNDU, kare 1133, en.

---

### E3 — `kutu.py` / `icerik.py` kopya borcu 🟡

İkisi de `harness/kunye_kiyas/` altındaki asıllarının **kopyası**. Aslını
üretim okuyucusu kullanıyor (`scripts/_pipe_hibrit_okuma.py:111`).

**Neden önemli:** Rol sözlüğüne veya kutu mantığına yapılan bir düzeltme
yalnız bir kopyaya girer; diğeri sessizce eskir.

**Nereye:** okuma kulesi kurulduğunda kapanacak. `harness/kunye_kiyas/`
tamamen silinecek.

**Maliyet:** okuma kulesine bağlı, tek başına yapılmaz.

---

### E4 — ✅ YAPILDI (2026-08-17) — Database hardlink görünümü

`main.py:_database_gorunumu()` — girdi `Database/<Film>/...` altındaysa karar
`Database/<Film>/kobe_<bolum>.json`'a **hardlink**'lenir (aynı inode — testle
kanıtlandı). İsim bölümlü: spec §4.6 (`kobe.json`) bölüm yapısından önce
yazılmıştı; iki bölüm aynı adla birbirini ezerdi. Database DIŞINDAN çağrılınca
(ölçüm, havuz, test) hiçbir şey yazılmaz. Best-effort: link atılamazsa karar
yine yazılıdır, kanıta not düşülür. Tekrar koşuda görünüm taze inode'a taşınır.

---

### E5 — `%94.5` Ollama KAPALIYKEN ölçüldü 🟠

Kobe'nin dil yönlendiricisi Ollama'ya HTTP ile bağlanıyor (`src/cikis/motor.py`
~699). Erişilemezse `except Exception: continue` → hiç oy toplanmaz → **her
film için `'en'`**. Ölçüm 12:43'te yapıldı, Ollama 12:21'de durmuştu.

**Neden önemli:** Üretim Ollama açık koşacak. O zaman skor **~%93.6** (GUNLUK
2026-08-11: Farsça film 'ar'a geçiyor, onset 28 kare erkene kayıyor — üretim
ölçütünün içinde). Yani **üretimdeki gerçek sayı ölçülmedi.**

**Nereye:** `systemctl start ollama` + `olc_pool.py --paralel 8` → yeni
referans. İki sayı da kaydedilmeli (yönlendirici açık/kapalı).

**Maliyet:** düşük (~140 sn + ollama başlatma). **Ama dikkat:** mevcut tüm
kapılar Ollama kapalı varsayıyor; yeni referans alınırsa `DURUM.md` ve
`README.md` güncellenmeli.

---

### E6 — 🟡 YARISI YAPILDI (2026-08-17) — işçi tazeleme var, CLI toplu paralel yok

`olc_pool.py`: `Pool(paralel, maxtasksperchild=25)` kondu — kapı yeniden
koşuldu, **sapma sıfır** (aynı %94.5 / %97.3 / 29-29). Görev başına davranış
değişmez (spawn zaten izole); yalnız işçi ömrü tazelenir.

**Kalan:** `main.py:toplu()` hâlâ tek süreç sıralı. Paralel havuz ayrı tasarım
ister (işçi başına Paddle VRAM payı — tek 3090'ta kaç işçi güvenli ölçülmeden
eklenmez). Üretim şu an `toplu`yu kullanmıyor (E1 pool üzerinden gidiyor);
acelesi yok.

---

### E7 — CPU/GPU kaynak bölüşümü ölçülmedi 🟢

Spec §4.7 hedefi: Kobe CPU'da geniş paralel, okuma kulesi GPU'da → "CPU GPU
boş kalmaz". Kobe'nin yükü ağırlıkla detection-only olduğu için CPU'ya uygun
görünüyor, **ama ölçülmedi**. Kayan-nokta farkı det kutusunu oynatabilir.

**Nereye:** 110 filmlik yatakta CPU koşusu, sapma sıfır kontrolü.

**Maliyet:** orta (CPU'da 2-4 kat yavaş).

---

### E8 — `--uret` üretim hattına bağlı değil 🟡

`--uret kare|klip` çalışıyor ama `scripts/_jenerik_pool.py` bunu kullanmıyor;
üretim kendi havuzunu kendi kuruyor (kareleri `frames/cikis`'ten
`cikis_jenerik`'e kendisi kopyalıyor). E1 bağlandı ama `--uret` çağrılmıyor —
iki yol paralel yaşıyor. Üretimin Kobe artefaktını (`--uret kare`) kullanmaya
geçmesi ayrı bir karar: davranış eşdeğerliği (kopyalama =
`kare_havuzu_yaz`) ölçülmeden/onaysız yapılmaz.

---

### E10 — metin-kapı `credit_box` import'u çözülmüyor 🔴 *(E1 sırasında bulundu)*

`scripts/_jenerik_pool.py` metin-kapı dalı `import credit_box` yapıyor; modül
`harness/kunye_kiyas/credit_box.py`'ta ve pool'un koştuğu bağlamda
sys.path'e HİÇ eklenmiyor → ModuleNotFoundError → `except` yutuyor →
`oran=0.0` → hep `kredi_yok`. Yani `MITAS_JENERIK_METIN_KAPI=1` açık olsa da
**son-%15 kutu taraması fiilen hiç koşmuyor**, `review_kredi_yok` insan
kuyruğu hiç tetiklenmiyor (doğrulandı: 2026-08-17, venvs/ocr bağlamında
import denendi → ModuleNotFoundError).

**Neden önemli:** sessiz arıza sınıfı — bayrak açık görünüyor, etkisi yok.
README'nin "insan kuyruğu" vaadi bugün boş.

**Nereye:** import öncesi `sys.path.insert(0, PROJECT_ROOT/"harness"/"kunye_kiyas")`
(desen: `_pipe_hibrit_okuma.py:110-111`). Ama dikkat: bu, kredi_yok filmlerde
davranışı DEĞİŞTİRİR (bazıları review kuyruğuna düşer) — pool'daki kural
gereği Çağatay onayı + ölçüm olmadan açılmamalı. E3 (kutu/icerik kopya
borcu) kapanırken `credit_box` da okuma kulesine giderse kökten çözülür.

---

### E9 — 6 bilinen hata (dar-VLM sınıfı) 🟢 bilinçli

`YALNIZ_SAVAŞÇI` −190 · `HARİKA_KÖPEK_5` −124 · `İNİŞLİ_ÇIKIŞLI` +89 ·
`İKİ_KAFADAR` / `KIZIL_HAYAT` / `TESS` (üretim ölçütünde doğru).
Çözüm yolu dar-VLM — ayrı proje, bu kulenin kapsamı dışında.

---

# GİRİŞ (giriş jeneriği)

## Yapıldı ✅ — 2026-08-13, commit `41bc799f`

| | Kanıt |
|---|---|
| Klasör ayrımı — `out/<film>/giris/` | `sozlesme.py`, `BOLUMLER` |
| Sözleşmede `bolum` + `bitis_kare`/`bitis_sn` (yalnız giriş doldurur) | `test_bolum.py` |
| **G1** `src/giris/sinir.py` — (a) sınır, `detect_from_frames` ÇAĞRILIR | gerçek koşu, güven 0.754 / 0.761 |
| **G1** `src/giris/havuz.py` — (b) havuz, `giris_jenerik_havuzu.py` stratejisi | 480 tarandı → 231 elendi → 75 temsilci |
| **G2** Giriş kare çıkarımı — `ss=0`, `length=240` | `main.py:kare_cikar()` |
| **G3** Giriş artefaktları — klip `bitis_sn`'de biter, kare = havuz seçimi | `klip.mp4` 21.000 sn (ffprobe), 75 PNG |
| **G4** `main.py` yönlendiricisi giriş bloğuna gidiyor | eski `ARIZA(BOLUM_HAZIR_DEGIL)` kaldırıldı |
| Çok-seçimli CLI — `--bolum giris,cikis --uret kare,klip` | `test_main_akis.py` |
| **Çıkış-giriş izolasyonu kodda kilitli** | `test_izolasyon.py` — 7 test, ihlal enjekte edilip doğrulandı |
| Güven kapısı **görünür** — sabit pencereye düşüş `kanit.sinir_kaynagi`'na yazılır | `sinir.py`, sessiz tahmin yok |

> **Giriş artık iş yapıyor.** Uçtan uca doğrulandı: iki farklı gerçek film,
> biri mp4 üretti biri kare havuzu. **Ama doğruluğu ölçülmedi** — aşağıya bak.

## Eksik ❌

### G5 — 🟡 GT 36/50 Filme ULAŞTI (2026-08-17, ikinci tur)

Çağatay `veri/gt.json`'ı doldurdu (depo_3006 yatağının 10 filminden 8'i;
BELALI_SEVGİLİ + KAPANMAMIŞ boş bekliyor). İlk ölçüm kayıtlı:
`veri/olcum_giris_son.json` — jenerik-var 8/8 bulundu; başlangıç politikası
gereği yalnız geç-başlangıç hatası sayılır (0 adet); bitiş 8/8 erken
(bkz. G10). Örnek büyütme sürüyor: test_film_vl'den 40 film daha yatağa
alınıyor — GT dolduruldukça ölçüm büyür.

**Yatak tarifi (kararlaştırıldı):** 15 film — `filmtest/depo_3006/` altındaki
**tam** filmlerden (`filmtest/test_film_vl/` altındakiler VL deneylerinden
kalma **parça** dosyalar, film değil). İlk **240 sn**, fps 2 → 480 kare/film.
GT'yi Çağatay verir: motorun önerdiği sınırın etrafındaki kareler gösterilir,
~30 sn/film.

---

### G6 — 🟡 YATAK + SCRIPT KURULDU (2026-08-17), GT bekliyor — ölçüm KOŞMADI

`olcum/giris/` artık boş değil:
- `yatak_kur.sh` — 10 TAM film × ilk 240 sn × fps 2 → `havuz/giris/`
  (tarif 15 filmdi; `depo_3006/`'da 10 TAM film var — fark kayıtlı, yatak
  idempotent, film eklendikçe büyür)
- `gt_topla.py` — motor TEKLİF eder (sinir.bul + bakılacak kare listeleri),
  `veri/gt_taslak.json` yazar; GT ÜRETMEZ (döngüsel olur)
- `olc_giris.py` — `veri/gt.json` YOKSA KOŞMAZ; iki uçlu sapma (başlangıç
  VE bitiş) + red doğruluğu raporlar; **kırmızı çizgi bilinçli YOK** —
  dağılım görülünce Çağatay ile konur
- `veri/gt_taslak.json` — 10 filmlik teklif seti ÜRETİLDİ (95 sn)

**Kalan:** `gt.json` insan doğrulaması (= G5) gelmeden hiçbir sayı yok.

**Dikkat — metrik şekli farklı:** çıkışta "onset sapması ±N kare"; girişte
sınır iki uçlu (`start` + `end`), yani iki sapma ölçülür. Çıkışın asimetrik
politikası (erken ≤120 / geç ≤20) girişe **doğrudan kopyalanamaz** —
girişte geç kalmak jeneriğin başını, erken kalmak film sahnesini alır.

---

### G7 — ✅ YAPILDI (2026-08-17) — giriş karar demiri `golden/giris_tek_film.json`

KOBRA giriş kararı demirlendi (BULUNDU, bas=0, bit=41 / 21.0 sn, güven 0.754,
kaynak=tespit) — 2026-08-13 gerçek-koşu kaydıyla uyumlu. Yeniden doğrulama
komutu `golden/BENIOKU.md`'de. **KARAR demiridir, doğruluk demiri DEĞİL** —
doğruluk G5/G6'ya bağlıdır (bilinçli ayrım dosyada yazılı).

---

### G8 — Uyarlanır pencere taşınmadı 🟡 *(uygulama sırasında ortaya çıktı)*

Kobe giriş penceresini **sabit 240 sn** çıkarıyor. Üretim hattı daha akıllısını
yapıyordu (`mitas_pipeline.py:1985-1990`): güven yeterliyse pencereyi
`end_sec+5`'e kadar **genişletiyor** (tavan 720 sn).

**Neden önemli:** gerçek koşuda SİLAHLAR_KONUŞUYOR'un kredi kareleri **476.
kareye** (≈238 sn) kadar yayıldı — yani 240 sn penceresinin ucuna dayandı.
Uzun jenerikli bir filmde pencere kesecek ve **kimse fark etmeyecek**.

**Yapılacak:** iki geçiş — önce sınır, sınır geniş çıkarsa pencereyi büyütüp
kareyi yeniden çıkar. G6 (ölçüm yatağı) kurulmadan bunun kazandırdığı
ölçülemez, o yüzden sonra.

---

### G9 — Havuz/sınır birim testi YOK 🟢 *(bilinçli)*

Doğrulama gerçek koşuya dayanıyor. Kapsam daraltması gereği ağır mock'lu test
yazılmadı. `test_izolasyon.py` yapıyı koruyor ama **mantığı** korumuyor —
havuz eşiği yanlış değişirse test yakalamaz, ancak G6 yakalar.

---

### G10 — ✅ ÇOĞUNLUKLA ÇÖZÜLDÜ (2026-08-17 akşam) — BİTİŞ ŞELALESİ

GT 36'ya çıkınca iki Çağatay fikri sınandı (18/18 eğitim-sınav): sağdan-sola
yoğun-blok kuralı (W30/K12) + çıkış motorunun TERS dizinde koşması. İkisi
birleşti (ŞELALE: ters-motor → kural → sinir) ve `src/giris/bitis.py` +
`main.py:_ters_bitis` olarak uygulandı (izolasyon korunur: giriş bloğu motor
import etmez, aday main'den enjekte). Üretim yoluyla 36 film: ort|Δ| 131.8→
**57.0**, medyan →**~19**, çok-erken 20→**0**, ±60 →**29/36**; kaynak:
ters-motor 17 / kural 19. Ayrıntı: `olcum/giris/bitis_kalibrasyonu.md`.

**Kalan borç:** 7 film >60 GEÇ (izci-sınıfı — jenerik sonrası yoğun isimli
metin). Çözüm yolu içerik-sınıf ayıracı (kredi-TARZI vs diyalog-üstü yazı);
GT büyüdükçe yeniden değerlendirilir.

---

# Önerilen sıra — güncel

| Sıra | İş | Neden bu sırada |
|---|---|---|
| 1 | ~~**E1** — üretim hattını sözleşmeye bağla~~ ✅ 2026-08-17 | Yapıldı — A/B birebir, kanarya tuttu |
| 2 | ~~**E2** — `src/cikis/` + `src/ortak/` ayrımı~~ ✅ 2026-08-17 | Yapıldı — motor.py'ye sıfır diff, kapı %94.5 sapma sıfır |
| 3 | **G5** — giriş GT'si (G6 altyapı hazır, gt_topla.py teklifleri üretti) | **Girişin doğruluğu bilinmiyor.** Bundan sonrası ölçüsüz gider |
| 4 | ~~**G8** — uyarlanır pencere~~ ⏸ | **ERTALENDİ:** GT (G5) gelmeden kazanç ölçülemez — ölçüsüz davranış değişimi prensip dışı |
| 5 | ~~**E5** — Ollama açıkken referans ölçüm~~ ⏸ | **ERTALENDİ:** ollama.service'i açmayı gerektirir (sistem durumu; başka oturumların kapıları buna bağlı) — Çağatay zamanlaması |
| 6 | ~~G7 + E4 + E6~~ ✅ 2026-08-17 | Kanarya (giriş demiri) + hardlink görünümü + işçi tazeleme yapıldı; E6'in CLI-toplu yarısı açık |
| 7 | **E7** — CPU/GPU bölüşümü | ⏸ saatler sürer, saf optimizasyon — en son |
| — | **E10** — metin-kapı credit_box (E1'de bulunan) | Çağatay kararı gerekli: davranış değişimi + E3'e bağlı |

## Değişmezler — her adımda geçerli

1. **`src/cikis/motor.py`'ye dokunulmaz.** Çıkışın %94.5'i ona bağlı.
2. **Çıkış girişin işine karışmaz.** Karar mantıkları birleşmez; ortak olan
   yalnız aletlerdir (`kutu.py`, `icerik.py`). `test_izolasyon.py` kilitler.
3. **Çıkışa dokunan iş** `olc_pool.py --paralel 8` → **%94.5 sapma sıfır**
   ile doğrulanır. *Yalnız çıkışa dokunulduğunda* — giriş işi bu kapıya tabi
   değil (Çağatay, 2026-08-13: *"ölçüm şu an yapılacak iş değil"*).
