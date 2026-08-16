# Lebron kulesi — canlı durum

> **Bu dosya bağlam sigortasıdır.** Oturum kesilirse yeni oturum BURADAN devam
> eder. Her iş biriminden sonra güncellenir.
> Spec: `docs/superpowers/specs/2026-08-15-allstar-lebron-kulesi-design.md`

**Son güncelleme:** 2026-08-17 — **FAZ 0 + 1 + 2 + 3 + 4 TAMAM.**
İskelet kuruldu, derleyici taşındı (sadakat kapısı 8/8 bit-birebir), okuyucu
kuleye alındı, **ölçüm yatağı kulede koşuyor (Faz 3) ve kompozitör seçimi
ÖLÇÜMLE yapıldı (Faz 4): magic > lebron > ibrahimovic —
`raporlar/kompozitor_secim_karari_2026-08-17.md`.** Terfi ve üretim devri
(Faz 5) ayrı talimatla.

---

## Değişmez kurallar (her oturumda geçerli)

- **Kule dışarı uzanmaz.** `master_png_monitor`, `db_compose_master`,
  `Database`, Ollama — hiçbiri import edilmez. `tests/test_izolasyon.py`
  bunu kodda kilitler.
- **`gereksinimler.txt` elle budanmaz.** Kobe'de ölçülmüş ders: 16 paketlik
  seçilmiş liste skoru %94.5 → %92.7 düşürdü.
- **Motora dokunan her değişiklik sadakat kapısını koşmayı gerektirir.**
  `olcum/kapi_sadakat.py`, eşik sapma 0.
- **`git add -A`, `git add .`, `git reset --hard`, `git stash` YASAK.** Ağaçta
  bu işe ait olmayan çok sayıda değişik + silinmiş dosya var. Yalnız adı geçen
  yolları sahnele.
- **Üretim durmuş** (2026-07-31, Çağatay talimatı). Hiçbir fazda toplu koşu
  başlatma.
- **Üretim hattı henüz kuleyi çağırmıyor** — `master_png_monitor.py` hâlâ
  `harness/master_dup/lebron_james.py`'yi kullanıyor. Devir Faz 5, ayrı
  talimatla.

---

## Bitenler

| Faz | İş | Kanıt |
|---|---|---|
| **0** | İskelet: `sozlesme.py` · `main.py` · `lebron` · `config.yaml` · testler | 58 test yeşil |
| **1** | Derleyici taşındı (`src/derleyici.py`) + iki kusur kapatıldı | **kapı 8/8 bit-birebir, sapma 0** |
| **2** | Okuyucu taşındı: `src/okuyucu.py` + `src/model.py` + ağırlık | **95 test yeşil** |
| **3** | Ölçüm yatağı kulede koşuyor: `uret.py` kök-çözümlemesi + `kompozitor_kiyas.py` (lebron↔ibrahimovic ilk kafa-kafaya) | `raporlar/kompozitor_kiyas_*.json` |
| **4** | `aday/magic.py` (lebron ∪ ibrahimovic) + ölçülmüş seçim + ablasyon | **`raporlar/kompozitor_secim_karari_2026-08-17.md` · 135 test yeşil** |

**Faz 2 ne getirdi.** DeepSeek-OCR kule içinde (6.3 GB, `model/deepseek-ocr`),
torch 2.11.0 + transformers 4.46.3 kulenin venv'inde. Ollama'ya HTTP YOK.
Okuma mantığı üretimden birebir taşındı: bantlama 1100/120 · istem
`"<image>\nFree OCR."` · `kutu_n` piksel kalkanı (0 kutu + satır = uydurma) ·
gevezelik süzgeci · yapısal veto · fold-dedup. Elenen satırlar yok edilmez,
`kanit.elenen`e yazılır — yanlış eleme yapıyorsak görünür olsun.

**Uçtan uca ilk koşu** (2026-08-15): `acemiler-cetesi-exit_frames`, 35 kare →
master 854×2321, 2 segment, 18.3 s. Görsel denetim: tam oyuncu listesi + MGM
logosu, kayan jenerik doğru birleşmiş.

**Sadakat kapısı** (Ex_Frame ilk 8 film): 20-bulusma 2696 · acemiler-cetesi
2321 · aci-cikolata 7508 · affedilmeyen 7276 · affedilmeyenler 574 ·
aile-babasi 7027 · ajans 10961 · al-jolson 1924 — **hepsi birebir.**

---

**Çalışma zamanı doğrulandı** (2026-08-15): `venv_kur.sh` koşuldu → **11 GB**,
`paddle 3.3.1 (CUDA açık)` · `paddleocr 3.7.0` · `numpy 2.3.5` ·
`pillow 12.1.0` · `opencv 5.0.0`. Kulenin KENDİ venv'iyle tekrar koşuldu:
58 test yeşil · `./lebron tek --bolum giris,cikis` iki rafa da yazdı (model
bir kez yüklendi: 12.7 s → 3.8 s) · sadakat kapısı yine **8/8 birebir**.

---

---

## Toplama (2026-08-15, Çağatay: "master png'ye ait her şey bu klasör altında")

`harness/master_dup/` kümesi + dağınık master-PNG malzemesi kuleye toplandı:
**aday motor · 20 ölçüm dosyası · 8 ölçüm testi · 9 rapor · 4 arşiv denemesi ·
4 yan araç.** Harita: `KATALOG.md`.

**KOPYALANDI, TAŞINMADI — bilerek.** Orijinaller iki sebeple yerinde duruyor:
1. Üretim (`master_png_monitor.py:127`) hâlâ `harness/master_dup/lebron_james`'i
   import ediyor. Silmek üretimi bozar (Prensip 2).
2. Sadakat kapısı orijinali **kıyas tarafı** olarak okuyor — silinirse kapı
   ölçemez hale gelir.

Silme **Faz 5**'te (üretim devri) yapılır. Nash'in izlediği sıra budur: önce
çağrı yerleri kuleye döndü, sonra kopyalar silindi.

**İbrahimovic `aday/` altında, `src/` altında DEĞİL.** `src/` yalnız koşan kodu
tutar; ibrahimovic bağlı değil ve iki borcu var (gömülü `/home/cagatay/Ex_Frame`
yolu, `olcum/saglik`'e bağımlılık). İki test bunu korur: dosya **silinmesin**
(`test_aday_motor_kulede_ama_BAGLI_DEGIL`) ve borçlar **görünür kalsın**
(`test_aday_motorun_bilinen_borclari`).

---

## Faz 2'de çıkan iki kaza (ikisi de kapatıldı)

**1. CUDA nesil çarpışması — kule kurulumunun gerçek tuzağı.**
Kulenin venv'inde iki CUDA nesli yan yana yaşıyor: Paddle `cu12` (derleyici),
torch 2.11 `cu13` (okuyucu). torch'un JIT'i `libnvrtc-builtins.so.13.0`'ı düz
adla arıyor, yükleyici önce cu12 dizinini bulup 12.6 sürümünü görüyor ve
`nvrtc: error: failed to open libnvrtc-builtins.so.13.0` ile patlıyor.
**Her bant bu yüzden okunamıyordu.**

Çözüm cerrahi: `venv/nvrtc13/` içinde YALNIZ o tek dosyanın sembolik bağlantısı,
`lebron` betiği onu `LD_LIBRARY_PATH`'e ekliyor. `cu13/lib`'i komple yola
eklemek YANLIŞ olurdu — orada `libcufft.so.12` / `libcurand.so.10` /
`libcusolver.so.12` gibi Paddle'ın cu12 zinciriyle **aynı soname**'e sahip
dosyalar var; derleyici sessizce başka kütüphanelere bağlanırdı.

**2. Kendi sözleşmemizi çiğneyen sessiz yalan.**
Üç bandın üçü de patlayınca hatalar tek tek sayılıp yutuldu, satır listesi boş
kaldı ve kule **`METIN_YOK`** dedi — yani "bu jenerikte yazı yok". Yazı vardı,
biz okuyamadık. ARIZA sessizce içerik gerçeğine dönüşmüştü.

Artık `okuyucu.OkumaCoktu` → `ARIZA(OKUMA_COKTU)`, ilk hatanın sebebi mesaja
taşınıyor. `tests/test_okuyucu.py::test_HEPSI_patlarsa_metin_yok_DEGIL` kilitler.

---

## Sıradaki iş

1. ~~Okuyucu kapısı~~ — kuyrukta; satır-düzeyi kıyas ölçütü spec'te tanımlı.
2. ~~Kapıyı genişlet~~ — 440 film koşusu hâlâ Çağatay onayı ister.
3. ~~Faz 3+4~~ — **tamam** (2026-08-17): kıyas koşusu + magic adayı + ölçülmüş
   karar. **Sıradaki:** magic'in terfisi (src/'ye alınması + varsayılan yapılması)
   ve üretim devri (Faz 5) — ikisi de AYRI TALİMATLA. Açık borçlar karar
   raporunda: jetgiller eşik-üstü dup, totoro metrik yanlış-pozitifi,
   kucuk-dev recall-dengesi.

---

## Faz 4 ne getirdi (2026-08-17)

**`aday/magic.py`** — lebron iskeleti + ibrahimovic'in dört mekanizması
(plato v4 + dissolve bekçisi, token-kimlik, Sobel yedek yolu, token ızgara
sondajı). Token'lar kulenin İÇİNDEKİ Paddle'dan (saglik yan-kapısı
taşınmadı). `flashlight`/`token_saglayici` geri-çağrıları enjekte edilebilir
— karar mantığının tamamı GPU'suz test ediliyor (135 test).

**Kıyas koşusu** (`olcum/kompozitor_kiyas.py`): 12 karma-zorluk film ×
motor; saglik + sadakat + dup + çöküş. İlk kafa-kafaya lebron↔ibrahimovic
(GUNLUK 2026-08-11'in açık boşluğu kapandı) + ablasyon (token-kapalı).

**Sonuç:** magic 10/12 sağlıklı (lebron 9, ibrahimovic 9) · recall medyan
0.3015 (L 0.294, I 0.293) · dup medyan 0.005 (L 0.012, I 0.011). Hiçbir
sağlıklı filmde lebron'dan geri yok. (Çöküş bayrakları: M 3 / L 1 / I 3 —
magic'inkiler tek-segmentli-sağlıklı masterlardan, ayrıntı karar raporunda.)

**Taşımayı öğreten dört kusur** (hepsi gözle+ölçümle bulundu, testle kilitlendi;
ayrıntı karar raporunda): acemiler (sobel kararı fener maskesinden ölçülmez),
totoro (sobel zemine kilitlenir — substrat YARIŞMASI: çok scroll bulan kazanır),
hayat-agaci ×2 (token 'farklı' hükmü sayfa açmaz; duraksamasız filmde gren-tabanı
kesmeden).

**Ölçüm yatağı düzeltmesi:** `olcum/uret.py` kule kopyasında PROJECT_ROOT
çözümlemesi eklendi (parents[2] kulede Allstar'a düşüyordu; saglik→uret→
monitor→F1b/F1c zinciri kulede ilk kez bu sayede koştu — Faz 3'ün kapısı buydu).

---

## Açık borçlar (spec §11)

1. **Model ağırlıkları: kopya mı paylaşım mı** — Nash emsali (kule içinde,
   6.3 GB) ile MAP.md metni ("dışarı, kasten paylaşılır") çelişiyor. Çağatay
   kararı, Faz 2'den önce.
2. **mp4 girdisi** — Faz 1'de kapalı; açılırsa fps kalibrasyonu gerekir.
3. **Tek kare davranışı** — `ARIZA(GIRDI_HATASI)` seçildi, ölçülmedi.
4. **Giriş bölümünde kompozitör kalitesi** — kule giriş/çıkışta aynı
   derleyiciyi koşar; üretimin bugünkü giriş yolu farklı
   (`compose_reading_runaware`). Ölçülmeden üretime bağlanmaz.
