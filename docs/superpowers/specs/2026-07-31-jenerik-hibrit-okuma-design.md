# Jenerik Hibrit Okuma — Tasarım Dokümanı

**Tarih:** 2026-07-31
**Karar mercii:** Çağatay
**Hazırlayan:** Claude (Fable) — konsey turları ve karşı-görüşler kayıtlı
**Durum:** Aşama 1 uygulandı · Aşama 2 koşuyor · Aşama 3-7 bekliyor

---

## 1. Problem

Sistem Windows'ta jenerik künyesini **OneOCR** ile okuyordu. Linux'a geçişte OneOCR
düştü ve yerini otomatik olarak **PaddleOCR** aldı (`scripts/_pipe_ocr.py:410` —
Linux'ta motor `MITAS_JENERIK_OCR_ENGINE`, varsayılan `paddle`; `_PaddleReadEngine`
satır 359 Paddle'ı OneOCR arayüzüne sarıyor).

Paddle, projenin kendi testlerinde OneOCR'ın **ciddi gerisinde**. Yani üretim şu an
sahibinin güvenmediği bir okuyucuyla 1825 filmin künyesini üretiyor.

**Bu tasarım Paddle'ın YERİNE geçecek** — yanına değil.

### Kabul ölçütü (Çağatay'ın kendi cümleleri)

> "ekranda bu isim varsa ben onu PDF'e yazayım"
> "gerisinde halüsinasyon olmasın ve isim atlamayalım, bize yeter"
> "dış bağımlılığı sadece fuzzy match kıvamına getirmek — sazan aksı değil Sezen Aksu"

İki sert şart: **(1) uydurma isim olmasın, (2) ekrandaki isim atlanmasın.**
Dış veritabanı yalnız **imla** düzeltmesi için; varlık kararı için DEĞİL.

> "uzaya roket fırlatmayacağız ama modellerden gerekli verimi alamayınca hybrid
> kurmam gerekti. yoksa bende karıştırmak istemem."

Hibrit bir tercih değil, mecburiyet. Sadelikten taviz bilinçli.

---

## 2. Mimari

```
FIGO → jenerik kare havuzu (havuz1)
  ├── Kol A "MESSİ"        : phash dedup + temsilci kare seçimi  → deepseek-ocr
  └── Kol B "İBRAHİMOVİC"  : adaptif-slit master PNG → 1100px bant → qwen8-vLLM
            ↓
      BİRLEŞİM (kesişim DEĞİL)
            ↓
      fark kümesi → PİKSEL TAHKİMİ
            ↓
      birleşik künye → gemma (rol eşleme) → QC1 → PDF
```

### 2.1 Neden birleşim, neden kesişim değil

Çağatay: *"asıl bu hibridin kazancı birbirlerinin görmediği şeyleri görmesi. İbra
Ahmet Dursun'u ekstra okur, Messi'den Melek Balkay gelir. bu sayede küme tamamlanır."*

Kesişim almak hibridin varlık sebebini yok eder. Kayan bir isim hiçbir tek karede
tam bulunmaz — yalnız master'ın yeniden kurduğu panoramada vardır. Bir flash kredi
dikişte kaybolur — yalnız karelerde vardır. Bu **girdi düzeyinde** farklardır,
okuyucudan bağımsız.

### 2.2 Model ataması ve neden iki AYRI aile

**Karar:** Kol A (frame) ← **deepseek-ocr** · Kol B (master) ← **qwen8-vLLM**

Turnuva verisi (8 film, KB-doğrulamalı tam-ad):

| Görev | deepseek | qwen8 | Fark |
|---|---|---|---|
| MASTER | 297 (Ollama, kuantize) | 283 (vLLM, tam ağırlık) | %95 — yok denecek kadar az; qwen8 3 filmde (POLİS, ÇAKAL, FAKİR) öne geçti |
| FRAME  | ŞEREFİM KB-isim **15**, ÇILGIN **63** | **5**, **56** | **büyük** |
| (elenen) | glm-ocr 215 (döngü patolojisi, 85 dk/film) · gemma-31 206 (40-80 sn/bant) | | |

Mantık: güçlü modeli farkın **büyük** olduğu kola koy (frame→deepseek), farkın
**küçük** olduğu kolu rakibe bırak (master→qwen8). Aynı ayrışmayı en az kalite
bedeliyle satın alır.

**Ayrışma zorunlu, ve bu teori değil — gözlenmiş.** Çağatay: bugün iki kolu da
deepseek okuduğu için **rodeo** vakasında ikisi *birden* çöktü ve
"Kubrick/Godfather" uydurmaları *iki kolda da* göründü. Motorlar ayrışınca biri
uydurduğunda öteki teyit vermez, Ronaldo farkı raporlar → **ortak kör nokta
yapısal olarak kapanır.**

Bağımsız destekleyici kanıt: Qwen3-VL-30B, Qwen3-VL-8B'nin hatalarını birebir
tekrarladı. **Ayrışma aileden gelir, boyuttan gelmez** — iki Qwen'i eşleştirip
"biri büyük, bağımsız olur" denemez.

**Kabul edilen bedel:** ÖNEMSİZ BİRİ tipi filmlerde qwen master kolunda ~%20 isim
kaybı (74→59). Ama o isimler frame kolunda deepseek'te var; **mix topluyor.**
Kol-seviyesi kayıp ≠ sistem-seviyesi kayıp — birleşim mimarisinin satın aldığı şey
tam olarak budur.

**Bayrakla seçilebilir (Çağatay):** `MASTER_GOZU=deepseek` (varsayılan, bugünkü
kanıtlı düzen) | `MASTER_GOZU=qwen8-vllm` (iki-motor çaprazı). İlk 20-30 filmde
bant/KONTROL oranları izlenir, kalıcı karar üretim verisiyle verilir.

### 2.3 Piksel tahkimi — iki aşamalı soru

Çağatay'ın formülasyonu: *"şurda şu pikseller arasında bir şey yazıyor mu? yazıyorsa
ne yazıyor?"* — farkında olmadan iki ayrı zorlukta soruya bölmüş:

| Soru | Zorluk | Kim cevaplar | Ne için |
|---|---|---|---|
| "Bu piksellerde yazı VAR MI?" | kolay | **PaddleOCR det-only** | **halüsinasyon vetosu** — halüsinasyonun arkasında piksel yoktur |
| "NE yazıyor?" | zor, modele bağlı | yalnız hakem o render'da yetkinse | imla/içerik ayrımı |

Kritik sonuç: **halüsinasyon vetosu için ikinci bir OKUMA modeline ihtiyaç yok.**
Bir metin dedektörünün "burada metin var mı" sorusuna cevap vermesi onun doğal işi,
ve hata modları bir LLM ile ortak değil. Paddle burada "üçüncü tanık" rolünde —
zayıflığı **rec**'te, **det**'te değil.

### 2.4 Tahkim hedefi izin TİPİNE göre

| Satırın kaynağı | Tahkim hedefi | Neden |
|---|---|---|
| kayan segmentten **yeniden kurulmuş** | master kırpımı | tam satır yalnız orada var; kaynak kareye göndermek onu ÖLDÜRÜR |
| ≥1 karede **bütün duran** | kaynak kare kırpımı | türev değil, kaynak kanıt |

Bu sınıflandırma **zaten diskte** — ama ilk yazdığım alan adları YANLIŞTI, canlı
koşuda düzeltildi (2026-07-31):

> **DÜZELTME.** `runs` / `strict_runs` / `strict_scroll_frac` / `kept_blocks`
> alanlarını gösterdim ve "üç gerçek filmde doğrulandı" dedim. O üç film
> `Database/` altındaydı ve **eski kompozitörün** (`db_compose_master`)
> manifest'ini taşıyordu. **İbrahimovic (2026-07-29'dan beri birincil kompozitör)
> TAMAMEN FARKLI şema yazıyor** ve o alanların hiçbiri yok.

İbrahimovic manifest'inin gerçek şeması (`mode: "ibrahimovic"`):

| Alan | Örnek (BOZGUNCULAR 1955) | Ne verir |
|---|---|---|
| `sinif_sayimi` | `{"duraksama_bos": 31, "duraksama": 42}` | çift-sınıf sayımı — **kayan/statik ayrımı burada** |
| `scroll_dy_medyan` | `0.0` | medyan kayma; 0 = tamamen statik |
| `ciftler` | `[{"dy":0.0,"resp":0.0,"sinif":"duraksama_bos"}, …]` | **çift-başına sınıf — run'dan DAHA İNCE** |
| `segment` / `segment_kareler` | `4` / `[[0],[4],[16],[33],[34]]` | segment sınırları |
| `dissolve_kesme` | `4` | dissolve/kesme sayısı |
| `maske_kapsama` | `0.099` | metin-maskesi kapsaması |
| `durum` / `kare` / `size` | `"OK"` / `74` / `[636, 1920]` | — |

Yani sınıflandırıcı girdisi **`sinif_sayimi` + `scroll_dy_medyan` + `ciftler[].sinif`**.
Sinyal var, hatta çift düzeyinde olduğu için run düzeyinden iyi. Ama **iki manifest
şeması** dolaşımda (eski `db_compose_master` + yeni `ibrahimovic`) → okuyucu kod
İKİSİNİ de tanımak zorunda, yoksa eski hub'lardaki filmlerde sessizce `None` alır.

### 2.5 Tahkim geçmezse: kabul + işaretle

Çağatay: *"nasılsa QC son faz değil kapı, ve işaretli bir satır kapıda
durdurulabilir; ama atılmış bir isim geri gelmez."*

İşaretleme **geçiş dönemi aleti**, kalıcı mimari değil. Sistem çalıştığını
gösterince kalkar. Ama şu an QC1 kendini ölçemediği için "işaretlemeye gerek
kalmadı"yı kanıtlayacak veri de yok → önce ölçüm, sonra sadeleştirme.

### 2.6 KB (isim veritabanı) rolü: yalnız imlacı

Çağatay: *"KB fuzzy match'i ben makyaj için tutuyorum. aslında karar mekanizması
olarak kullanmak niyetinde değilim. bazen fazla korumacı davrandığım için KB artık
karar mekanizmasına dönmüş ama aslında değil."*

| Karar | Kim verir | Eski hal |
|---|---|---|
| Bu isim **var mı?** | **piksel** | ❌ KB veriyordu (`ronaldo.py:165`) |
| Bu ismin **yazımı ne?** | fuzzy-match + KB | ✅ zaten böyle (`token_esle`) |

**Sökülecek:** `ronaldo.py:165` KB varlık kapısı.
**Korunacak:** `token_esle:47-49` — "iki token da KB'de ise birleştirme YOK" kilidi
(iki gerçek ismin yanlışlıkla birleşmesini engelliyor).

**KB'nin devrettiği rol → piksel adresi:** aynı adres = aynı kişi (iki kez okundu),
farklı adres = farklı kişi (benzer yazılsa bile). Çağatay'ın *"set amirini nasıl
doğrulayacağım ben?"* sorusunun cevabı: veritabanına karşı değil, **kendi pikseline
karşı.** Set amiri IMDb'de yok, Wiki'de yok, olmayacak — KB'ye dayanan her kural
KB'nin kör noktasını miras alır.

### 2.7 Yapısal filtreler tahkimden ÖNCE, mutlak veto

Şekil-tabanlı, KB'siz — o yüzden KB'yi çıkarınca hayatta kalıyorlar:

| Filtre | Yakaladığı | Neden künye olamaz |
|---|---|---|
| `[` / `(` ile başlıyor | `[Bir adam kapıdan giriyor]` | model sahneyi *anlatıyor* |
| `**` içeriyor | `**YÖNETMEN**` | ekranda yıldız yok — markdown'ı model ekledi |
| CJK oranı > %30 | `画面显示演员名单` | model Çince betimleme moduna kaydı |
| alfanümerik < %30 | `#@!x~ 3%$` | OCR bulamacı |

**Sıra kritik:** `**YÖNETMEN**` satırını hakeme sorarsan hakem piksellerde
"YÖNETMEN" görür ve **onaylar** → model artefaktı "piksel-teyitli" damgası yer.
Şekil filtresi olmadan tahkim, artefaktları *aklıyor*.

### 2.8 Arka plan metni: QC'de elenir, otomatik sınıflandırıcı YOK

Çağatay: *"tek kelime ya da sayılar isim değildir, bunlar QC'de elenir. QC zaten
bunun için var. çöpü evden atmak için."*

"Künye biçiminde mi" diye yargılayan bir katman kurmuyoruz — daha ucuz, daha az
kırılgan. Ölçülmemiş dar kalıntı: iki kelimeli harf-only arka plan metni
("BERBER SALONU", "ATATÜRK CADDESİ"). Şimdi çözülmüyor, **ölçülüyor**.

### 2.9 Video-VL kolu: eskalasyon (anahtarlanabilir)

`scripts/_pipe_video_vl.py` zaten var (pipeline satır ~3980, default kapalı):
FIGO `start_pos` → sessiz 60sn+5sn bindirmeli mp4 parçaları → vLLM `video_url`.
Verimli sürümü `filmtest/dizi_cikis_vl/CICEK_TAKSI_b001/vl_okuma_kosucu.py`
(20 sn pencere, kart-tekil istem, siyah ön-filtre, MAXTOK 3500).

Model turu (tek dizi bölümü, statik kart, 384×288): **MiniCPM-V-4.5 8/11** (~37 sn)
> Qwen3-VL-30B-A3B-AWQ 5/11 (~74 sn) > InternVL3.5-8B 4/11 > Qwen3-VL-8B 3/11.

**37 sn = tek jenerik dizisinin TAMAMI** (9 parçadan 5'i gerçek, 4'ü siyah-filtreli:
6.0+8.1+8.5+8.6+6.0). Film başına. 1825 filmde ≈ 19 saat.

**Yeri: eskalasyon.** Tetikleyici **zaten hesaplanıyor ama atıl** —
`common_blind` (coverage<0.15), `band=red`, `structural_anchor_missing` yalnız
`log_event` basıyor (pipeline 4153-4163), hiçbir şey onlara göre dallanmıyor.
Merdiven: anlaşma→bitti · ayrışma→tahkim · **iki kol da kör→video.**

`MITAS_VIDEO_VL_MODE=eskalasyon` (varsayılan) | `daima`. Çağatay: *"bu ikisi de
olabilir, zamanla netleştireceğiz."*

**Neden "beklediğim kadar iyi sonuç vermedi" ile çelişmiyor:** her filmde koşarsa
ortalama kazancı küçük görünür (kolay filmler zaten çözülmüş, ortalamayı aşağı
çeker). Yalnız hiçbir şeyin çalışmadığı filmlerde koşarsa kazancı **değerin
tamamı** olur. Kolay filmlerde üçüncü olan araç, imkânsız filmlerde birinci olabilir;
ortalama tam olarak bunu saklar.

### 2.10 İz sürme: bbox baştan

**Çağatay kararı.** Ben kademeli gitmeyi önerdim (yalnız kaynak dosya → sonra bbox);
o bbox'ın baştan kurulmasını seçti. **Seçimi benimkinden iyi ve sebebini kaçırmışım:**

> Dedektör kutuları **bedava bir "atlanan isim" dedektörü** veriyor. Kutu var +
> eşleşen okuma satırı YOK = okuyucunun kaçırdığı yazı. Yani ikinci şart (*isim
> atlamayalım*) için, pahalı kör insan-GT'ye ek olarak **her filmde ve üretimde de
> çalışan** otomatik ikinci sinyal doğuyor. Ben bbox'ı yalnız tahkim hassasiyeti
> olarak değerlendirmiştim.

Kaynak: `harness/kunye_kiyas/credit_box.py` → `kutu_analiz()`, film başına
`_det_cache.json` önbellekli.

**Kutu ↔ satır eşleştirme katmanı** (yeni, en riskli parça): kutuları y sırasına diz,
okuyucu satırlarıyla sıra-hizala. `N==M` → 1:1 · okuyucu birleştirmiş (1:k) →
birleşik bbox + `birlesik` bayrağı · okuyucu bölmüş (k:1) → `bolunmus` ·
**eşleşmeyen kutu → atlanan-isim adayı** · eşleşmeyen satır → halüsinasyon adayı,
tahkime gider. Birim testi `harness/track_kunye/senaryo.py` sentetik kareleriyle.

**Uygulama biçimi: JSONL yan dosya**, tam `list[dict]` refactor DEĞİL.
`master_dilim_oku.py:61-84` deseni: TXT kanonik yüzey **aynen kalır**, JSONL additive.
Tam refactor'ün ölçülen maliyeti: `ronaldo.py`'de 7 fonksiyon kırılır, **sert çökme**
`ronaldo.py:151` `varyantlar.setdefault(es, [])` → `unhashable type: 'dict'`,
`pilot_hat.py:233` json anahtar-str kısıtı, ve 20+ test.

**Master kolunda ek zorunluluk:** `pilot_hat.py:201-222` bant y-ofsetini atıyor
(`y` yalnız döngü değişkeni) → `(bant_dosyasi, bant_y0)` çifti taşınmak ZORUNDA.

---

## 3. Ölçüm — çünkü mimari ölçümsüz koşulamaz

Üç bulgu bunu zorunlu kıldı:

**3.1 Mevcut metriğin referansı, değiştirmek istediğimiz motorun kendisi.**
`taze_pilot.py:53-64` `referans_cikar()` yer doğrusunu **PaddleOCR taramasından**
üretiyor; `metrik.py:8-30` F1'i ona karşı hesaplıyor. Yani "Ronaldo F1 = 0.875" =
"Paddle ile %87.5 uyuşuyor". Paddle'ın kaçırdığı gerçek ismi bulan kol precision'da
**cezalandırılıyor**. GUNLUK'teki `vahsi-afrika` "metrik tuzağı" bunun kanıtı.
→ Geçmiş F1'ler çöpe atılmıyor ama **yeniden etiketleniyor**: "Paddle ile uyuşma
oranı". Göreli kıyas kısmen geçerli; mutlak kalite iddiası geçersiz.

**3.2 QC1 kendi başarısını görmüyordu.** `mitas_pipeline.py:2960-2971` — ilk denemede
geçen film yalnız `dbg.emit()` basıyordu (per-film trace, `system_events.jsonl`'e
gitmiyor). Ampirik: 33 filmden 16'sı RED'e girmiş, kalan **17 film sıfır olay** →
başarı oranının **paydası yoktu**. `_qc1_failed` bayrağı hiçbir artefakta
yazılmıyordu: bellekte doğuyor, karara etki ediyor (satır 3392), süreç bitince
kayboluyor. **→ Aşama 1'de kapatıldı.**

**3.3 Model benchmark'ının kapsamı tek örnek.** MiniCPM 8/11 turu TEK dizi
bölümünde koştu, skorlama ELLE, makine-okunur GT yok. Dokümanın kendi uyarısı:
*"Motor kararı İÇİN YETERLİ DEĞİL."*

### 3.4 Metrik — beş sınıf, KB'ye dayanmaz

| Sınıf | Anlam |
|---|---|
| **Tam** | birebir |
| **İmla-kurtarılabilir** | yalnız diakritik/büyük-küçük → `fold_tr` çökertir, KB düzeltir → **bedava** |
| **Bozuk** | onarılamaz |
| **Uydurma** | ekranda yok → **şart 1 ihlali** |
| **Kayıp** | ekranda var, hiçbir kolda yok → **şart 2 ihlali** |

**"KB-doğrulamalı tam-ad" metriği REDDEDİLDİ.** Konseyin dört üyesi bağımsız olarak
aynı sonuca vardı: metrik, silik yazıyı okuyamayıp yerine **tanıdık bir isim
uyduran** modeli ödüllendiriyor (KB'de var → puan), **set amirini doğru okuyan**
modeli cezalandırıyor (KB'de yok → sıfır). Yani Çağatay'ın kuralının tam tersi.
8 filmde 14 puanlık fark (297–283) bu yanlılıkla açıklanabilecek büyüklükte.

**Kayıp'ı iki bağımsız kaynak ölçer:** kör-mod insan GT (4 film, altın standart) +
eşleşmeyen dedektör kutusu (15 filmin hepsinde, otomatik). 4 kör filmde ikisi
çapraz doğrulanır; örtüşürse kutu-sinyali vekil olur, örtüşmezse yalnız uyarı kalır.
(`mod_denetim.py`'nin dersi: her metriğin kör noktası var, bağımsız ikinci sinyal şart.)

### 3.5 Ölçüm yatağı

`depo01/Film Kapanış` → 1751 mp4 → **1388 tekil** (363 mükerrer ayıklandı) →
347 kontamine çıkarıldı → **1235 temiz havuz** → **15 film**, tohum `20260731`
(tekrar-üretilebilir). Üreteç: `outputs/olcum_yatagi/yatak_sec.py`.

Hepsi ffprobe ile doğrulandı: h264, 25 fps, 13–105 dk, 512×288 – 854×480.
Çeşitlilik kendiliğinden geldi: **1955→2021** (eski/stilize font + düşük çözünürlük
stres vakaları dahil).

"Rastgele mi katmanlı mı" çatışması: **rastgele seç, sonradan sınıflandır.**
Kayan/statik ayrımını master manifest'in `runs`/`strict_runs` (S/R) zaten veriyor →
sınıf dağılımı bedava öğrenilir; bir sınıf boşsa 2-3 film eklenir.

**Baseline aynı 15 filmde, ESKİ yolla.** Tarihsel üretim sayılarıyla (33 film)
kıyaslamak elmayla armut: yeni mimari QC1'in *girdi dağılımını* değiştiriyor, aynı
kural farklı false-positive üretir. (Bu uyarı konseyden geldi — gerçek katkı.)

**Tek geçişte üç iş:** tam pipeline `--no-asr` ile → (a) yatak (kareler+havuz+master),
(b) Aşama 1'in gerçek-film kapısı, (c) baseline künye. ASR kesildi: künye ölçümüne
katkısı sıfır, film başına en pahalı adım. Koşucu: `scripts/olcum_yatagi_kos.sh`.

---

## 4. Reddedilenler ve sebepleri

| Ne | Neden reddedildi |
|---|---|
| **deepseek grounding istemi** (bbox için) | Repo genelinde `"grounding"` araması **sıfır sonuç** — bu modun projede hiç denendiğine kanıt yok, koordinat ölçeği bilinmiyor, ve aynı modelin farklı istem modunda okuma kalitesi değişirse tüm kıyas geçersizleşir |
| **Paddle-türevli otomatik GT** | Referans = değiştirmek istediğimiz motor (§3.1) |
| **KB-doğrulamalı tam-ad metriği** | Uydurmayı ödüllendiriyor, doğru okumayı cezalandırıyor (§3.4) |
| **"KB'de yoksa tam eşleşme şart"** (benim önerim) | KB'nin göremediği kitleye en katı davranıyor — kanıtın en zayıf olduğu yerde kuralı sertleştiriyordu. Set amiri argümanı öldürdü |
| **"Tahkim daima kaynak kareye"** (konsey önerisi) | Kayan satırı öldürür — tam satır yalnız master'da; hakeme *parça* göstermek olur |
| **Otomatik künye-şekli sınıflandırıcısı** | Çağatay: QC çöpü elemek için var (§2.8) |
| **glm-ocr / gemma-31 okuma kolunda** | 215 (döngü patolojisi, 85 dk/film) · 206 (40-80 sn/bant) |
| **İki Qwen eşleştirmesi** | 30B, 8B'nin hatalarını tekrarladı — ayrışma aileden gelir, boyuttan gelmez |

---

## 5. Konsey turları — katkı ve hata kaydı

**Üç tur açıldı.** İlk ikisinde 4 üyeden 3'ü bakiye hatasıyla düştü (GLM `code 1113`
余额不足, Kimi `insufficient balance`, MiniMax boş) — tek cevaplayan Nemotron.
Üçüncü turda 5 üye aktifti (anahtarlar ayrı bir işte düzeltildi).

**Gerçek katkılar:**
- KB metriğinin yanlılığı — dört üye bağımsız olarak buldu, tasarımı değiştirdi
- "Elmayla armut" uyarısı → baseline aynı 15 filmde eski yolla ölçülüyor
- Runtime/kuantizasyon karışması (confounding) — GLM bunu kısmen çürüttü: üretimde de
  deepseek Ollama'da, qwen8 vLLM'de koşacaksa turnuva **üretimin birebir provası**,
  karışmış deney değil. Karşı-görüş kayda değer ve haklı
- VRAM eş-yerleşim uyarısı (2-5 dk/film takas tahmini vs Çağatay'ın 1 dk'sı)

**Nemotron'un ikinci turunda fabrikasyon:**
- *"Benim testim (RTX 3090, deepseek-ocr:latest)"* diye latency tablosu sundu —
  bu makineye erişimi yok, **tablo uydurma**
- *"pilot_hat.py:15-18'de grounding prompt yorum satırı var"* — kontrol edildi,
  o satırlar `from __future__` ve import'lar. **Yanlış**
- Önerdiği yama var olmayan değişkenler kullanıyor (`slug`, `satirlar`, `klasor`)
- İstatistiği (`σ≈2.5`, `n≈24`, "ortalama 52 satır") kaynaksız

**Benim hatam (kayda geçiyor):** Model ataması turunda konseye **yanlış öncül**
verdim — frame farkını "başabaş" (9/17–9/17) diye sundum, o **ekran-gerçeği**
metriğiydi; KB-isim metriğinde **15'e 5**. Doğru sayılarla aynı mantık Çağatay'ın
atamasını veriyor. Beş üyenin cevabı kısmen bu hatalı zemine oturuyor.
Ayrıca sıra hatası: Çağatay kararını gerekçesiyle vermişti, ben gerekçesini
sormadan konseye "sahibi şunu diyor, ben tersini" diye gittim. Yön kararı Çağatay'ın;
konsey kör nokta için, karara itiraz üretmek için değil.

---

## 6. Aşamalar ve durum

| # | Aşama | Film? | Durum |
|---|---|---|---|
| 1 | QC1 ölçülebilirliği (log + yapısal alan + sayaç) | ❌ | **BİTTİ** — 4 yeni olay kind'ı, `scripts/qc1_olcum.py`, `karar_gunlugu.py` Linux fix'i. 33/33 test geçti |
| 2 | Yatak kurulumu + iz sürme (bbox) | ✅ | **KOŞUYOR** (pilot: film 1) |
| 3 | Yer doğrusu (11 aday-yargılama + 4 kör transkripsiyon) | ✅ | bekliyor — Çağatay'ın işi, makbuzlu listeler hazırlanacak |
| 4 | Baseline + kol × model matrisi | ✅ | ayrı GPU onayı gerekiyor |
| 5 | Birleştirme politikası (model maliyeti SIFIR — replay) | ❌ | bekliyor |
| 6 | Tahkim ölçümü (2×2 + "kararsız" oranı) | ✅ | bekliyor |
| 7 | Asıl sorular (birleşim tamamlıyor mu, kör noktalar ayrık mı) | ✅ | bekliyor |

**Aşama 5'te düzeltilecek bilinen kusurlar:** `garble_mi` asimetrisi (şu an yalnız
İbra-only'ye koşuyor, `ronaldo.py:156`; Messi satırları omurga sayılıp denetimsiz
geçiyor) · KB varlık kapısı (`ronaldo.py:165`) sökülecek · `guven_bandi` sonradan
reddedilen satırları sayıyor, tahkim sonrası yeniden hesap · `metrik.py` dejenere
referansta anlamsız.

---

## 7. Bilinen taban

Hiçbir birleştirme politikası "iki kol da görmediyse" vakasını çözemez.
`bayraklar()` bunu zaten ölçüyor (`common_blind`, coverage < 0.15) ve dürüstçe
*"içerik-tamlık garantisi YOK"* diyor.

Birleştirme **"okunanı düşürmem"** garantisi verebilir; **"ekranda olanı
kaçırmam"** garantisi veremez. O ikincisi havuz/render işi — FIGO, İbrahimovic ve
Messi'nin kendi kalitesi. Ayrı cephe.
