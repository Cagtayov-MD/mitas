# Allstar / NASH kulesi — tasarım

**Tarih:** 2026-08-14 · **Tasarım:** Opus · **Talimat:** Çağatay —
*"nash.py'yi bir kule haline getireceğiz… Nash'in tüm işini tek bir kuleye
hapsedeceğiz, artık orada yaşayacak. Bu kule haricinde Nash'e dair hiçbir eri
dışarıda kalamayacak."*

---

## 1. Nash bugün ne? (koddan doğrulanmış)

`harness/track_kunye/steve_nash.py` (245 satır) — **saf kare-havuzu seçici.**
Gri kareler girer, temsilci kare **indeksleri** çıkar. Model yok, disk I/O yok.

Kendi docstring'indeki kısıt: *"Modele gidecek karede Sharpen, Contrast, Deblur,
Binarizasyon YOK."* Yalnız filtreleme, gruplama, temsilci seçme.

Akış: 16×16 algısal imza (dHash) → ardışık hamming farkı → film-başına Otsu
eşiği → çift-sinyalli gruplama (ardışık fark **veya** grup açılışına birikim) →
dev grupları 20'de böl → grup başına medyan-keskinlikteki kare (`std < 3.0` ise
içeriksiz, atılır) → `ikinci_gecis` delta-enerji sigortası (sürünen scroll'u
yakalar) → ALARM kurtarması.

`messi.py` 6 satırlık takma ad (`from steve_nash import *`). Pipeline'daki
**"MESSİ" = Nash.**

### 1.1 Çıktısını kim okuyor → DeepSeek, Qwen değil

| Katman | Yer | Model | Üretimde? |
|---|---|---|---|
| Dizinden havuz | `pilot_hat.py:49` `havuz_derle_dizin` | — | ✅ |
| Kareleri **oku** | `pilot_hat.py:79` `oku_deepseek` | `deepseek-ocr:latest`, istem `"Free OCR."` | ✅ |
| Metni yapılandır | `pilot_hat.py:120` `yapilandir` | `qwen3-vl:30b`, **görüntüsüz** | ❌ **ölü kod** |

Üretim betiği `_pipe_track_kunye.py` katman 3'ü hiç çağırmıyor. Qwen yalnız
`pilot_hat.main()` içindeki 5 filmlik pilotta koşmuş.

### 1.2 Nash'in bugünkü ayak izi — 5 tüketici

| Tüketici | Ne | Sınıf |
|---|---|---|
| `scripts/_pipe_hibrit_okuma.py:258,276` | **ANA üretim okuma yolu** (`mitas_pipeline.py:2408`; Paddle yalnız kill-switch) | 🔴 canlı |
| `scripts/_pipe_track_kunye.py:176,182` | gölge 3-kol (çıkış + giriş) | gölge |
| `scripts/olcum_yatagi_faz2.py:138` | ölçüm yatağı Kol A | ölçüm |
| `harness/track_kunye/taze_pilot.py:88` | pilot | harness |
| `harness/track_kunye/pilot_hat.py` | sahibi/sarmalayıcı | harness |

Testler: `tests/test_pipe_track_kunye.py`, `tests/test_track_kunye_giris.py`,
`harness/track_kunye/test_messi.py`, `test_steve_nash.py`,
`test_pilot_hat_uretim.py`, `test_pilot_hat_ronaldo.py`.

> **Kritik:** *"hiçbir eri dışarıda kalmayacak"* kuralı, üretimin **ana okuma
> yoluna** dokunmayı gerektiriyor. Bu Prensip 2 alanıdır — bu yüzden geçiş
> kapılı ve fazlıdır (§5).

### 1.3 Kulede olması gereken ama Nash'in kendi dosyasında OLMAYAN parçalar

Nash'in "eri" yalnız `steve_nash.py` değil. Üretimde ona bitişik yaşayan ve
her biri **gerçek bir üretim kazasından** doğmuş katmanlar:

| Parça | Yer | Doğduğu kaza |
|---|---|---|
| Sayfa tavanı + düzgün-adım örnekleme | `_pipe_track_kunye.ornekle`, `_pipe_hibrit_okuma:257-279` | maliyet |
| **Son kare zorla dahil** | `_pipe_track_kunye.py:96` | © / "SON" kartı düzgün-adımda hiç seçilmiyordu |
| **Son 12 ham kare zorla** (giriş) | `_pipe_hibrit_okuma.py:264-270` | ALİE, 2026-07-31: yönetmen kartı 1632 satırın hiçbirine girmedi → QC1 RED |
| Sayfalar arası fold-dedup (difflib ≥0.92) | `pilot_hat.oku_deepseek` | tekrar eden kart |
| **Gevezelik süzgeci** (`_RET_KALIP`, `_model_gevezeligi`) | `_pipe_hibrit_okuma.py:180-215` | YAZ TATİLİ 1963-0035, 2026-08-01: model "Caption:" / "Markdown-style Summary:" basıyor, yönetmen adının üstüne geçip rol-eşlemenin bağlamını bozuyordu |
| Garble/çöküş dedektörü | `_pipe_track_kunye.deepseek_saglik` | rodeo vakası |

Hepsi kuleye taşınır. **Jordan dersi:** *"İstemde 'no commentary' yazması
yetmiyor — süzgeç kodda olmak zorunda."*

---

## 2. Kilitlenmiş kararlar (Çağatay, 2026-08-13/14)

| # | Karar | Gerekçe |
|---|---|---|
| 1 | Kule **havuz + okuma** yapar, çıktısı **METİN** | "Nash'in tüm işi" fiilen bu ikisi; ayrılırsa kule bugün tek başına hiçbir işe yaramaz (okuyucu kulesi yok). Ayrıca Jordan'la aynı biçimde metin üretince MAP.md'nin asıl sorusu — *"master PNG gerekli mi"* — adil ölçülebilir |
| 2 | deepseek-ocr **kule içine** (transformers + yerel ağırlık, Jordan deseni) | Dışarıdaki servise bağlı kule gerçekten kendi kendine yeten bir kule değil; sürüm pinlenmezse başkasının modeli değiştirmesi Nash'i sessizce değiştirir |
| 3 | Kule tek kaynak; üretimdeki kopyalar **kapılı geçişle** sökülür | Kobe'nin "TAŞIMA KAPISI" deseni: taşı, ölç, sapma sıfırsa eskiyi sil |
| 4 | `METIN_YOK` / `KARE_OKUNAMADI` **ayrılır** | Çağatay: *"hata analizi kıymetli, sorun nerede görmek için."* Bugün ikisi tek kutuda |

### 2.1 Kapsam dışı (bilerek)

- **Model yükseltme.** HF'de `DeepSeek-OCR-2` var (2026-01, Apache-2.0). Bu iş
  **sadık taşımadır**: aynı model, aynı istem. Motor rotası değişimi CLAUDE.md'de
  konsey + benchmark gerektiren ayrı karar sınıfı (`no_engine_selection_before_benchmark`).
- **Qwen yapılandırma katmanı** (`pilot_hat.yapilandir`). Üretimde zaten ölü.
  Diriltmek okuma doğruluğu ölçülmeden erken.
- **RONALDO / İBRAHİMOVİC kolları.** Nash'in eri değil, ayrı kuleler
  (MAP.md: `shaq`, `phil_jackson`).
- **Nash'in okuma DOĞRULUĞU.** İnsan-GT'li skor bu işin konusu değil; bu iş
  taşımanın **sadakatini** ölçer. Doğruluk ölçümü ayrı iş (Jordan'da da açık).

---

## 3. Kule

```
Allstar/nash/
├─ nash                     # bash girişi — kendi venv'ini kendi bulur
├─ main.py                  # CLI + akış + sözleşme çevirisi
├─ sozlesme.py              # Girdi / Cikti / ariza
├─ config.yaml              # tavanlar, sigortalar, istem, model yolu
├─ src/
│  ├─ havuz.py              # steve_nash.py — SAF çekirdek, BİREBİR taşınır
│  ├─ secim.py              # dizin → gri → havuz → örnekleme + sigortalar
│  ├─ model.py              # transformers'a dokunan TEK yer
│  └─ okuyucu.py            # kareler → satırlar (dedup + gevezelik süzgeci)
├─ model/deepseek-ocr/      # ağırlık (git'te DEĞİL) + model_kur.sh
├─ olcum/                   # sadakat sondajı + 15 filmlik kapı
├─ out/<film_id>/<bolum>/   # nash.json + nash.txt + _TAMAM
└─ venv/ tests/ README.md CHANGELOG.md DURUM.md KATALOG.md
```

`src/` sözleşmeyi **bilmez** — çeviri yalnız `main.py`'de (Kobe/Jordan ile aynı).

```bash
Allstar/nash/nash tek --kareler /yol/frames/cikis --film-id <id> [--bolum cikis|giris]
Allstar/nash/nash start --input /yol/kare_dizinleri     # model BİR KEZ yüklenir
```

Çıktı daima `Allstar/nash/out/<film_id>/<bolum>/`. Çağıran çıktı yolunu seçmez.

### 3.1 Sözleşme

| durum | Anlamı | Zorunlu |
|---|---|---|
| `OKUNDU` | Metin okundu | `satirlar` (boş olamaz) |
| `METIN_YOK` | Karelerde gerçekten okunacak yazı yok — **içerik gerçeği** | — |
| `ARIZA` | Okuyamadık — **arıza gerçeği** | `sinif` + `mesaj` |

> **`ARIZA` asla `METIN_YOK`'a dönüşmez** (Kobe/Jordan değişmezi). Ve aynası:
> içerik gerçeği de arıza diye etiketlenmez. `METIN_YOK` ve `ARIZA` satır
> taşıyamaz — sözleşme kodla zorlar.

| sinif | Ne oldu |
|---|---|
| `GIRDI_HATASI` | dizin yok/boş, sözleşme ihlali (`--bolum` geçersiz vb.) |
| `KARE_OKUNAMADI` | kareler var, `cv2.imread` **hiçbirini** açamadı |
| `BELLEK` | CUDA OOM |
| `CIKTI_BOZUK` | model konuştu, çıktı garble (`deepseek_saglik` taşınır) |
| `MODEL` | model yüklenemedi / beklenmedik istisna |

**Havuz boş'un ikiye ayrılması.** Bugün `_pipe_track_kunye.py:178` iki farklı
gerçeği tek kutuya atıyor (`skipped/messi_havuz_bos`):

- kareler açıldı, hepsi içeriksiz (`std < 3.0`) → **`METIN_YOK`**
- `cv2.imread` hiçbirini açamadı → **`ARIZA(KARE_OKUNAMADI)`**

Ölçüm yatağında `"durum": "havuz_bos"` yazan bir film var ve hangisi olduğu
**bilinmiyor.** Kule bu körlüğü kapatır.

Tüketici kuralı: **`_TAMAM` yoksa dosya yok sayılır.** Atomik yazım
(`os.replace`) + `_TAMAM` en son.

**`nash.txt` YALNIZ `OKUNDU`'da yazılır** *(uygulama sırasında eklendi,
2026-08-14)*. Gerçek koşuda görüldü: ARIZA'da da boş bir `nash.txt` yazılıyordu.
`_TAMAM` var + dosya boş = yalnız metni okuyan tüketiciye "yazı bulunamadı" gibi
görünür ve tam da bu bölümün kapattığı ayrımı yutar. Dosya yoksa tüketici
`nash.json`'a bakmak **zorunda** kalır.

### 3.1.1 Sağlık bayraktır, hüküm değil *(uygulama düzeltmesi, 2026-08-14)*

İlk tasarımda `deepseek_saglik`'in her olumsuz sonucu `ARIZA(CIKTI_BOZUK)`
üretiyordu. Testler yakaladı: **150 karakterlik gerçek bir kısa jenerik ARIZA
olup içeriği çöpe gidiyordu** — §3.1'in yasakladığı şeyin tam aynası.

| sağlık | sonuç | gerekçe |
|---|---|---|
| `garble_yuksek` | **`ARIZA(CIKTI_BOZUK)`** | elimizdeki metin YANLIŞ; aşağı akışa bırakmak künyeyi zehirler (rodeo vakası: iki kol da çöktüğü için "Kubrick/Godfather" uydurmaları künyeye girdi) |
| `cok_kisa` | yalnız `kanit.saglik` | kısa olmak yanlış olmak değildir |
| `bos_cikti` | `METIN_YOK` yolundan gelir | satır yoksa zaten OKUNDU olamaz |

Üretimde de bayrak zaten hüküm değil: `_pipe_track_kunye` sonucu manifest'e
yazıp içeriği korur. Bayrağı hükme çevirmek, §7'de eleştirilen `e1a201d5`
sınıfından ölçülmemiş bir davranış değişikliği olurdu.

### 3.2 Bölüm farkları — üretimden taşınır, uydurulmaz

| | `cikis` | `giris` |
|---|---|---|
| Sayfa tavanı | 100 | 40 |
| Sigorta | **son kare zorla** (© / SON kartı) | **son 12 ham kare zorla** (ALİE: yönetmen kartı girişin son kartıdır) |

İkisinin de arkasında kayıtlı bir üretim kazası var; birleştirmek birini
kaybetmek olurdu.

### 3.3 `nash.json`

```json
{
 "film_id": "...", "bolum": "cikis", "durum": "OKUNDU",
 "satirlar": [{"kaynak": "cikis_0647.png", "sayfa_sira": 1, "satir_sira": 0,
               "text": "..."}],
 "kanit": {
   "havuz": {"kare":74,"esik":20,"grup":21,"alarm":false,"sayfa":21,
             "ikinci_gecis_ek":3},
   "secilen_kare": 24, "dusurulen_n": 0, "kuyruk_ek": 0,
   "gevezelik_elenen": 0, "sayfa_hata_n": 0, "saglik": "ok"
 },
 "motor_surumu": "nash@<sha>", "uretim_zamani": "...", "sure_sn": 21.3
}
```

`nash.txt` = `satirlar[].text`, göründüğü sırayla, düz metin.

**`kanit.havuz` bilerek bugünkü `olcum_kol_frame.json`'ın `havuz` bloğuyla
birebir aynı biçimde.** Taşıma kapısı bu alanı alan alan kıyaslar.

**`sayfa_hata_n` yeni.** Bugün `oku_deepseek` patlayan sayfayı `continue` ile
**sessizce** atlıyor; 12 sayfadan 9'u okunmuş bir çıktı "tam" görünüyor. Kulede
sayılır ve yazılır.

---

## 4. Ölçüm — kapı hazır, uydurulmadı

`outputs/olcum_yatagi/klipler/` altında **15 film**, ham kare dizinleriyle
(`frames/giris` ~270, `frames/cikis` ~721, `frames/cikis_jenerik` ~74) ve her
filmde `olcum_kol_frame.json` — **eski Ollama yolunun çıktısı satır satır**
(`kaynak`, `text`, `havuz` istatistiği, `satir_n`).

Referans ortam (bu veriyi üreten): **python 3.12.13, numpy 2.3.5, opencv 5.0.0**
(`venvs/ocr`). Kulenin venv'i buna pinlenir.

### 4.1 UYARI — tarihî JSON'lar kapı OLARAK kullanılamaz *(2026-08-14 bulgusu)*

`olcum_kol_frame.json` dosyaları 2026-07-31'de üretildi. **`e1a201d5`
(2026-08-05)** `film_esigi`'nin Otsu aramasını yeniden yazdı — docstring'i
*"Optimize edilmiş O(n) Otsu"* diyor, ama hız optimizasyonu değil, **cevabı
değiştiren** bir davranış değişikliği:

| | Eski | Yeni (bugün üretimde) |
|---|---|---|
| Arama uzayı | `t ∈ [min+1, max)` | `t ∈ [0, 256)` |
| ≥3 eleman şartı | aramayı **kısıtlar** (`continue`) | aramadan **sonra** cevabı reddeder |

15 filmden **1'i** etkilendi: MOBY DICK 1, eşik 28→13, sayfa **15→165 (11×)**.
Tavan 100 olduğu için o film artık 15 yerine 100 sayfa okur — model çağrısı
~6.7×. **Hangisinin doğru olduğu ölçülmedi.**

Bu yüzden kapı **kule vs BUGÜNKÜ üretim kodu** olarak kurulur
(`olcum/referans_uret.py` referansı taze üretir); tarihî fark ayrı satırda
"tarihî sapma" olarak raporlanır ve kapıyı düşürmez. Eşyayı eşyayla kıyaslamak
için şart: aksi halde kapı taşımayı değil o commit'i ölçer.

**Açık borç:** e1a201d5'in ölçülmesi. Nash kulesinin işi değil (kule bugünkü
davranışı sadık taşıdı), ama kaybolmaması gereken bir bulgu.

---

## 5. Fazlar ve kapılar

### Faz 1 — Kulenin SAF yarısı (GPU yok, model yok, indirme yok)

`sozlesme.py` · `config.yaml` · `src/havuz.py` · `src/secim.py` · `main.py` ·
`nash` · testler · CPU venv.

> **KAPI 1 (sert, sapma sıfır):** 15 filmde `kanit.havuz` bloğu
> `olcum_kol_frame.json`'daki `havuz` bloğuyla **birebir aynı** olmalı
> (`kare`, `esik`, `grup`, `alarm`, `sayfa`, `ikinci_gecis_ek`).
> Havuz saf numpy/cv2 — taşınırken tek bit değişmemeli. Sapma varsa taşıma
> hatalıdır veya venv pini yanlıştır; ilerlenmez.

Bu faz **bedelsiz** ve taşımanın sadakatini modele hiç dokunmadan kanıtlar.

### Faz 0′ — Sadakat sondajı (Faz 2'den ÖNCE, ucuz)

Aynı N kare, iki motor: Ollama/llama.cpp vs transformers. Çıktılar diff'lenir.

Neden: DeepSeek-OCR **patch-tabanlı**. llama.cpp'nin `deepseekocr` handler'ı ile
transformers `AutoProcessor` farklı normalize eder → patch sınırları farklı
düşer → satır düzeyinde kayma (`YÖNETMEN` → `YÖNETME N`). difflib `0.92` eşiği
bunu **yeni satır** sayar ve künyeye sızar. *(MiniMax, 2026-08-13 konsey turu.)*

> **KAPI 0′:** sapma bandı ölçülür ve **kayda geçer**. Beklenmedik ölçüde
> büyükse Karar 2 (model kule içine) Çağatay'a **yeniden açılır** — sessizce
> devam edilmez.

Gerektirdiği: `ollama.service` geçici başlatma (Kobe ölçümü **aynı anda
koşmamalı** — açık Ollama Kobe'yi %94.5 → %93.6 düşürüyor) + HF ağırlık indirme
(~6.7 GB). **Çağatay onayı gerekir** (Prensip 2 uzantısı).

### Faz 2 — Okuyucu kule içine

`src/model.py` (transformers'a dokunan TEK yer) · `src/okuyucu.py` (dedup +
gevezelik süzgeci + garble dedektörü) · `model_kur.sh` · pinli `gereksinimler.txt`.

> **KAPI 2 (yumuşak, bantlı):** 15 filmde satır kıyası, Faz 0′'ın ölçtüğü sapma
> bandı içinde. `kanit.havuz` **hâlâ** birebir aynı (okuyucu havuza dokunmaz).

**Yığın mührü zorunlu.** Ollama gguf+manifest ile torch/transformers sürümünü
mühürlüyordu; transformers'da bunu `gereksinimler.txt` yapar. Aynı ağırlık +
farklı torch = farklı logits. Kobe'nin 167-pin dersi burada da geçerli:
**paket listesi elle budanmaz.**

### Faz 3 — Üretim geçişi + sökme

`_pipe_hibrit_okuma.py` ve `_pipe_track_kunye.py` kendi Nash kodunu bırakıp
kuleyi kullanır; sonra `harness/track_kunye/steve_nash.py`, `messi.py`,
`test_messi.py`, `test_steve_nash.py` ve `pilot_hat`'ın havuz/okuma katmanları
**silinir.**

**Faz 3'ün ayrı bir tasarımı olacak.** Sebebi: üretim entegrasyonunun şekli
(senkron mu, asenkron mu) bu spec'te çözülmedi ve çözülmemeli — Faz 1-2 bittiğinde
elde gerçek süre/bellek verisi olacak, karar o zaman verilir. Konseyin bu konudaki
uyarıları §6'da kayıtlı.

---

## 6. Faz 3 için kayıtlı uyarılar (konsey, 2026-08-13)

Tur büyük ölçüde başarısızdı — 5 üyeden Qwen (hesap borcu), Kimi (koltuk
`deepseek-v4-pro`, 2026-08-07'de EOL), Nemotron (timeout) hata verdi; GLM'in
cevabı ortasında bozuldu. **MiniMax** sağlam cevap verdi. Kalanlar:

1. **Asenkron kule → sessiz bozulma sınıfı.** `_TAMAM` "ya hep ya hiç" der ama
   okuma zaten sayfa atlayabiliyor (`continue`); asenkronda üretim bunu "tam"
   sanar ve 12 sayfadan 9'uyla künye yazar. → `sayfa_hata_n` bu yüzden
   sözleşmeye girdi (§3.3).
2. **Kuyruk sigortası asenkronda kırılır.** "Son 12 kare" senkronda atomik;
   kule dizini periyodik tararsa "son" belirsizleşir, ALİE bug'ı başka biçimde
   geri gelir.
3. **`frames/` yarış durumu.** Üretim `frames/giris`'e yazarken kule tararsa
   çıktı yarım filmi temsil eder. Bugünkü senkron tasarım bunu imkânsız kılıyor.
4. **VRAM aritmetiği.** Kobe(~4 GB) + Nash(6.7 GB) = 10.7 GB sığar.
   **Jordan(~18 GB) eklenince 28.7 GB > 24 GB — üçü aynı anda koşamaz.**
5. **Film başına model yükleme korkusu abartılı** — toplu modda bir kez ödenir
   (Kobe `toplu()` / Jordan `start` deseni zaten bunu çözüyor).

---

## 7. DEĞİŞMEZLER

1. **Havuz çekirdeği bit düzeyinde aynı.** `src/havuz.py`, `steve_nash.py`'nin
   birebir kopyasıdır; algoritma **değiştirilmez**. Sadeleştirme, "iyileştirme",
   yeniden yazım YASAK — KAPI 1 bunu ölçer.
2. **Kare işlenmez.** Modele giden karede Sharpen/Contrast/Deblur/Binarizasyon
   yok (Nash'in kendi kısıtı). Kule bunu bozacak bir katman eklemez.
3. **Üretim bozulmaz.** Faz 1-2 boyunca `_pipe_hibrit_okuma.py`,
   `_pipe_track_kunye.py`, `olcum_yatagi_faz2.py` ve `pilot_hat.py`'ye **tek satır
   dokunulmaz.** Sökme yalnız Faz 3'te, kapı geçildikten sonra.
4. **`ARIZA` asla içerik gerçeğine dönüşmez** — ve tersi de doğru.
5. **Ollama açıkken Kobe ölçümü koşturulmaz.**

## 8. Testler

`tests/` (Kobe 61, Jordan 60 deseninde):

- **Sözleşme:** `OKUNDU` satırsız olamaz · `METIN_YOK`/`ARIZA` satır taşıyamaz ·
  `ARIZA` `sinif`+`mesaj`sız olamaz · atomik yazım + `_TAMAM` en son.
- **Havuz:** `test_messi.py`'nin 20 testi taşınır (statik film, sürünen scroll,
  içeriksiz kare, otsu/kde, `ikinci_gecis`).
- **Seçim:** tavan aşımında düzgün adım · **son kare daima seçimde** (çıkış) ·
  **son 12 ham kare daima seçimde** (giriş) · `dusurulen_n` doğru raporlanır.
- **Ayrım:** tüm kareler içeriksiz → `METIN_YOK`; hiçbiri açılamıyor →
  `ARIZA(KARE_OKUNAMADI)`; dizin boş → `ARIZA(GIRDI_HATASI)`.
- **Okuyucu (Faz 2):** fold-dedup ≥0.92 · gevezelik süzgeci gerçek CJK jeneriği
  ATMAZ, tek-karakter gürültüsünü atar · `sayfa_hata_n` sayılır · OOM →
  `ARIZA(BELLEK)`, `METIN_YOK`'a dönüşmez.
- **Akış:** `start` kaldığı yerden devam eder (`_TAMAM` olanı atlar).
