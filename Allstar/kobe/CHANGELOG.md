# Kobe — değişiklik günlüğü

## 2026-08-13 — kule kuruldu

**Taşıma.** `harness/kunye_kiyas/` içinden `Allstar/kobe/`'ye taşındı;
`figo` adı repo genelinden silindi (tek isim: Kobe). `kobe.py → src/motor.py`,
`credit_box.py → src/kutu.py`, `credit_content.py → src/icerik.py`,
ölçüm yatağı `olcum/`'a, testler `tests/`'e. Çağıran `scripts/_jenerik_pool.py`
yeni yola çevrildi.

**Kendi çalışma zamanı.** `venv/` — paddlepaddle-gpu 3.3.1 (CUDA 12.6) +
paddleocr 3.7.0, 167 pin. `venv_kur.sh` sıfırdan kurar. Gerekçe paralellik
değil **sürüm dondurma**: ortak venv'de biri paddleocr'ı yükseltirse Kobe'nin
skoru sessizce kayar ve ölçüm kapısı anlamsızlaşır.

**Sözleşme.** `sozlesme.py` — `Girdi` (film_id + video XOR kareler), `Cikti`
(`BULUNDU`/`KREDI_YOK`/`ARIZA`), `ariza()`. Atomik yazım (`os.replace`) +
`_TAMAM` işareti. Değişmez: `ARIZA` kanıtsız olamaz, `KREDI_YOK` arıza alanı
taşıyamaz.

**CLI.** `main.py` + `kobe` sarmalayıcı + `config.yaml`. `kobe start --input`
idempotent toplu kuyruk (`_TAMAM` olanı atlar, kaldığı yerden devam eder);
`kobe tek` tek film. Video verilirse kapanış penceresini kendi çıkarır
(`havuz_kur.sh` tarifi birebir: son 600 sn, fps 2) ve **kendi açtığı**
`scratch/` dizinini siler — dışarıdan verilen kare dizinine dokunmaz.

**Üç ölçüm kapısı da geçti, sapma sıfır.** kapsam 110, genel 104/110 = %94.5,
üretim 107/110 = %97.3, kredi-var 75/81, kredi-yok 29/29. Kayıtlar:
`raporlar/olcum_{ONCE,SONRA_tasima,SONRA}.json`. Testler 39/39. Uçtan uca
gerçek koşu: POTEMKİN ZIRHLISI → `BULUNDU`, kare 1133, 21.4 sn
(`golden/tek_film.json`).

**Ölçüm havuzu içeri alındı.** `data/jenerik_havuz/pool_frames/` (120 film,
28 GB, +118 `_det_cache.json`) → `Allstar/kobe/havuz/`. Bu dizini kule dışında
kullanan yoktu; yolu yalnız Kobe'nin kendi dosyaları biliyordu. Aynı diskte
olduğu için taşıma anlık (kopyalama yok). Taşıma sonrası ölçüm birebir aynı:
%94.5 / %97.3 / 29-29. `data/jenerik_havuz/` dizini tamamen kalktı.

### Pahalı ders — çalışma zamanı budanmaz

İlk denemede `venvs/ocr`'dan **elle seçilmiş 16 paketlik** bir pin listesi
kullanıldı. Ölçüm **%94.5 → %92.7** düştü: iki film doğru → `KREDI_YOK` oldu
(`MELEKLERİ`/Kiril, `ARKADAŞIMIN`/Farsça), bir film 2 kare kaydı.

Bu olurken altı kilit paket **ikisinde de birebir aynıydı**: paddle 3.3.1
(CUDA 12.6, cuDNN 9.5.1, aynı commit), paddleocr 3.7.0, paddlex 3.7.2,
numpy 2.3.5, pillow 12.1.0, opencv 5.0.0.93. Det önbelleği, model ağırlıkları
ve ölçümün tekrarlanabilirliği de tek tek elendi.

Eksik 76 paket kurulunca skor **tam olarak** geri geldi.

> **Kobe'nin çıktısı, kodunun HİÇ import etmediği paketlere bağlı.**
> `motor.py`/`kutu.py`/`icerik.py` hiçbiri torch, sklearn, easyocr, timm veya
> transformers'a dokunmuyor. "Hangi paket önemli" TAHMİN EDİLMEZ — ortam bütün
> olarak dondurulur. Paket çıkarmadan önce 110 filmlik ölçümü koş.

### Bilinen borç

`src/kutu.py` ve `src/icerik.py`, `harness/kunye_kiyas/` altındaki asıllarının
**kopyasıdır**. Aslını üretim okuyucusu `scripts/_pipe_hibrit_okuma.py:111`
kullanıyor; taşınsaydı okuyucu kırılırdı, yeni yolu gösterseydi bu kez okuyucu
Kobe'nin klasörüne bağımlı olurdu. Okuma kulesi kurulunca o kule kendi
kopyasını alacak ve `harness/kunye_kiyas/` tamamen silinecek.

### Ertelenen

CPU/GPU kaynak bölüşümü ölçümü (spec §4.7): Kobe'yi CPU'da geniş paralel,
okuma kulesini GPU'da koşturma hedefi. Kobe'nin Paddle yükü ağırlıkla
detection-only olduğu için CPU'ya uygun görünüyor, ama kayan-nokta farkı det
kutusunu oynatabilir — 110 filmlik yatakta ölçülmeden kabul edilmez.
