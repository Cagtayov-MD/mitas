# Allstar — Lebron kulesinde GİRİŞ kolu: earvin + film-modu çıktı sözleşmesi

**Tarih:** 2026-08-18 · **Durum:** TASARIM (onay bekliyor) · **Sahip:** Çağatay
**Bağlam:** `docs/superpowers/specs/2026-08-15-allstar-lebron-kulesi-design.md`
(Faz 0-4 tamam; magic terfi etti, çıkış kolu kilitli)

---

## 0. Soru

Çıkış kulesi (lebron_james, kompozitör **magic**) kuruldu ve ölçümle kilitlendi.
Giriş jeneriği hâlâ üretim tarafında `compose_reading_runaware` (V2) +
OCR-imza semantik kurtarmasıyla üretiliyor; kulede giriş yalnız raf etiketi.
Çağatay'ın vizyonu (2026-08-18):

> "Giriş ve çıkış AYNI kulede yaşayacak. Kobe'den iki klasör gelecek —
> biri giriş, biri çıkış kareleri. Çıkışta magic, girişte magic_lite
> çalışacak. Film klasörü altında 2 PNG + 1 veri çıktısı; okuyan DeepSeek
> de kendi çıktısını koyacak."

## 1. Bulgu: zemin hazır

- **Kobe'de teslim kapasitesi VAR:** `kobe tek --video V --film-id F
  --bolum giris,cikis --uret kare` → `out/<F>/{giris,cikis}/kareler/` +
  `_TAMAM` (kobe/main.py:34-38, 191-234). Giriş kareleri: OCR-seçilmiş
  ARDIŞIK OLMAYAN liste (ör. 480→75 kare); çıkış: onset'ten geriye ardışık
  aralık. MAP.md kuralı zaten bunu tanır: iletişim yalnız sözleşme +
  `_TAMAM` işaretli dosyalar.
- **Kritik tasarım gerçeği:** giriş havuzu ardışık olmadığı için magic'in
  scroll ölçümü (ardışık çift faz-korelasyonu) girişte ANLAMSIZDIR. Giriş
  jeneriği kart-tabanlıdır: doğru kol magic'in **plato + token-kimlik +
  fold-dedup** hattıdır, scroll kolu değil.
- **Ölçüm malzemesi:** Kobe `olcum/giris/yatak_kur.sh` 10-film yatağı
  (kuruldu, GT G5 bekliyor) + `candidate_runs/giris_test_20260717` mini
  havuzları. V2 kıyas tarafı `olcum/uret.py --seg giris` ile koşabilir.

## 2. Kararlar (önerilen; alternatifler §8'de)

| # | Karar | Değer |
|---|---|---|
| K1 | Giriş kompozitörünün adı | **earvin** (Magic'in gerçek adı — yalın/kart-yönelimli hâli) |
| K2 | Yaşam yeri | Aynı kule: `Allstar/lebron_james/src/earvin.py` |
| K3 | Yeni CLI modu | `lebron film --kobe <kobe_out_kok>/<film_id>` — tek çağrıda iki bölüm |
| K4 | Çıktı düzeni | **film-düz:** `out/<film_id>/{giris.png, cikis.png, kunye.json, _TAMAM}` |
| K5 | Veri formatı | **tek `kunye.json`** — durum + satırlar + kanıt, iki bölüm bir arada |
| K6 | Eski `tek`/`toplu` raf düzeni | DOKUNULMAZ (geriye uyumluluk; sadakat kapısı bunları kullanır) |
| K7 | Giriş ölçümü | earvin ↔ V2(+kurtarma) kıyası, Kobe yatağı havuzlarında; ölçütsüz devreye alma YOK |

## 3. Mimari

### 3.1 earvin — giriş kompozitörü (`src/earvin.py`)

Magic'in KART hattının giriş için sadeleştirilmiş türevi; scroll kolu yok:

- **Girdi:** kare listesi (sıra: dosya adındaki sayı; ardışıklık VARSAYILMAZ).
- **Ele-feneri maskesi** (Paddle det) + `token_saglayici` dikişleri: magic ile
  AYNI yardımcılar (tek kopya: `src/magic.py`'den import; magic'inkiler saf).
- **Sayfa makinesi:** her kare bir adaydır; sıralama küme yürüyüşüyle:
  `token_ayni(kare, son_basilan)` → aynı ise atla (fold-dedup zaten var);
  farklı+metin-profili → yeni sayfa. dissolve/fade zincirleri: `kosu`
  kavramı yok; ardışık-gelmeyen karelerde plato anlamsız → **plato kolu
  kapalı**, bunun yerine tek-kare temsilciliği + varsa yerel yoğunluk
  (ardışık gelen karelerde en keskin).
- **Sınıf A fold-dedup:** segment kapanışında token kapsaması (magic'teki
  `segment_dusur` yeniden kullanılır) — giriş kartları sıklıkla tekrar
  gösterilir (beyaz-kugu dersi).
- **Sobel yedek yolu:** OCR patlarsa kare-bazlı yedek (film-düz yarışma YOK —
  ardışıklık olmadığı için dy karşılaştırması tanımsız).
- **Çöküş dedektörü:** giriş için `cokme_min_kare` bölüm-parametresi
  (öneri: 6; kobe havuzları 2-75 kare). `kural.cokmus` çağrısı film-modu
  içinde bölüm-eşiğiyle yapılır; `kural.py`'ye dokunulmaz (parametre
  çağrı yerinden).
- **Sözleşme sınıfları:** OKUNDU/METIN_YOK/ARIZA semantic'ini kompozisyon
  tarafında değil film-modu taşıyor (bkz. 3.3).

Boyut hedefi: ~200 satır; magic'in ağırlığı scroll/trim/yarışma'da — earvin
bunların hiçbirini istemez.

### 3.2 film-modu (`main.py`'ye `film` alt-komutu)

```
lebron film --kobe /opt/mitas/Allstar/kobe/out/<film_id>
```

Akış (tek süreç; model bir kez yüklenir):
1. Kobe sözleşmesini oku: `<kobe>/<bolum>/kobe.json` **yalnız `_TAMAM`
   varsa**; `kareler/` yolu künyeden. Bölüm YOKSA/ARIZA → o bölüm
   `HAVUZ_YOK` durumuyla json'a yazılır, PNG yazılmaz (sessiz kayıp yok).
2. `cikis` → `magic.derle(ims=...)` (mevcut kulemaster; dokunulmaz).
3. `giris` → `earvin.derle(ims=...)`.
4. Master'lar **bölüm bağımsız yazılır** (okuma patlasa da artefakt kalır —
   mevcut kule ilkesi): `out/<film_id>/{giris,cikis}.png`.
5. Okuyucu (mevcut `okuyucu.oku` + `model.sor`) İKİ master'ı da okur:
   bantlama 1100/120 aynı; `kutu_n` kalkanı aynı.
6. `kunye.json` atomik yaz (`kunye.json.tmp` + `os.replace`), EN SON
   `_TAMAM`.

### 3.3 `kunye.json` sözleşmesi

```json
{
  "film_id": "...",
  "motor": {"giris": "earvin@<sha>", "cikis": "magic@<sha>",
            "okuyucu": "deepseek-ocr"},
  "uretim_zamani": "...", "sure_sn": 123.4,
  "giris": {"durum": "OKUNDU|METIN_YOK|HAVUZ_YOK|ARIZA",
            "satirlar": ["..."],
            "kanit": {"kare": 75, "segment": 9, "segment_dusuren": [...],
                       "bant_n": 3, "elenen_n": 0, "kobe": {...}}},
  "cikis":  {"durum": "...", "satirlar": [...], "kanit": {...}}
}
```

Kurallar (mevcut sözleşmenin taşıyıcıları):
- `satirlar` YALNIZ OKUNDU'da; ARIZA'da `sinif+mesaj` zorunlu; ARIZA asla
  METIN_YOK'a dönüşmez.
- `_TAMAM` en son; yoksa dosya yok sayılır.
- PNG okuma sonucundan bağımsız yazılır.
- txt tüketici gereksinimi Faz 5'te `kunye.json`'dan türetilir (bugün yok).

### 3.4 MAP.md uyumu

Kobe'nin ürettiği veri (`kareler/`, `kobe.json`) YALNIZ `_TAMAM` sözleşmesi
üzerinden okunur — pipeline'ın bugün `kobe.json` okumasıyla aynı meşru yol.
Kule Kobe'yi çağırmaz; çağıran Kobe çıktısını gösterir (kim kime bağlı
netleşir: besleyici Kobe, tüketici lebron).

## 4. Ölçüm ve kabul (K7)

1. **Yatak:** Kobe `havuz/giris/` 10 filmi `kobe --uret kare`'den geçer
   → gerçek teslim biçimiyle havuzlar.
2. **Kıyas:** `kompozitor_kiyas.py --seg giris` uzantısı: earvin ↔ V2
   (`uret.py --seg giris` zinciri) aynı havuzlarda; ölçütler aynı üçlü
   (saglik + sadakat-benzeri text_recall [havuz kareleri referans] +
   dup_metrik).
3. **Kabul eşiği:** çıkıştaki gibi peşinen sayı uydurulmaz; ilk koşunun
   dağılımıyla konur. Kıyası earvin kayamazsa devreye alınmaz
   (`no_engine_selection_before_benchmark`).
4. **Regresyon nöbetleri:** çıkış testleri + kapı AYNEN koşar (film-modu
   yeni olur; `tek`'e dokunulmaz).

## 5. Testler

- `test_earvin_kart.py`: sentetik kart dizisi (tekrar kartı düşer, farklı
  kart sayfa açar, fade-dedup) — GPU'suz, sahte flashlight/token.
- `test_film_sozlesme.py`: kunye.json kuralları (satır yalnız OKUNDU'da,
  _TAMAM en son, HAVUZ_YOK png'siz, ARIZA sınıflı).
- `test_film_akis.py`: iki bölüm uçtan uca (sahte motorlarla), tek bölüm
  eksik Kobe, model bir kez yüklenir.
- `test_izolasyon.py`: film-modu da Kobe yolunu SÖZLEŞME ile okur (yalnız
  _TAMAM); kobe'yi import etmez.

## 6. Kapsam dışı

- Pipeline/Faz 5 devri (ayrı talimat) · Kobe G5 GT · kanonik cropstack'in
  akıbeti · txt türetme · V2'nin üretimden kaldırılması.

## 7. Riskler

| Risk | Karşı-önlem |
|---|---|
| Ardışık-olmayan havuzda magic yardımcıları yanlış davranır | earvin scroll/trim/plato KOLARINI hiç içermez; yalnız kart hattı |
| Kobe giriş havuzu seçimi ölçümsüz (G5) | earvin'in kabulü Kobe'nin değil kendi kıyasının eşiğine bağlı; havuz kalitesi ayrı borç olarak görünür kalır |
| `cokme_min_kare=20` girişte yanlış alarm | bölüm-parametresi (6) + test |
| kunye.json tüketici kırılması | tüketici yok henüz (Faz 5); JSON şeması spec'te kilitli |

## 8. Alternatifler (reddedilenler)

- **Ad:** `magic_lite` (açıklayıcı ama kule kültürü oyuncu adı ister),
  `johnson` (soyad; karışır). **earvin** seçildi.
- **Çıktı:** raf düzeni korunsaydı tüketici kolaylırdı ama kullanıcının
  "3 dosya" vizyonuna aykırı; `tek` modu zaten rafta duruyor.
- **Veri:** ayrı `giris.txt/cikis.txt` — dosya sayısı artar, tek-künye
  tüketimi bozulur. **Tek kunye.json.**
- **Ayrı kule (lebron_giris):** MAP "arızayı tek cümleye indir" ilkesine
  aykırı — giriş/çıkış aynı sorunun iki yüzü.
