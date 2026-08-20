# Nash kalite onarım planı

**Durum:** Yalnız uygulama planıdır. Mevcut Nash davranışı değiştirilmemiştir.

**Baz commitler:**

- `6df21e13a` — metin izli okuyucu
- `24f7d11cd` — 20 videoluk toplu ölçüm koşucusu

## 1. Nesnel başlangıç noktası

`/home/cagatay/Belgeler/okunmalık jenerikler` koşusu:

- 20/20 `OKUNDU`, 0 arıza
- 3.479 adet 2-fps kare
- 2.036 çıktı satırı
- 561,159 saniye
- Rapor: `/tmp/nash-okunmalik-jenerikler/rapor.json`

Bu yalnız operasyonel başarıdır; kalite kabulü değildir. Elle hazırlanmış GT
ile sıralı fuzzy kapsama: Suç Dosyası 77/81, İz Peşinde 79/86, Güneş 24/27,
Dost Eller 55/62, Marnalı 105/128, Pastane 41/59. GT dosyalarında açıklama,
birleşik satır ve kısmi kapsam bulunduğu için oranlar tek başına hüküm değildir;
aşağıdaki kesin vakalar zorunlu regresyon kapısıdır.

### Kesin kayıplar

1. Cennetin Çocukları: `YÖNETMEN`, `SONER CANER`, `YAPIMCI`, `HASAN KARUL`
   Paddle tarafından 0,986–0,999 güvenle ve çok karede okunmasına rağmen
   `altyazi` olarak silindi.
2. Suç Dosyası: `Komiser Sadi`, `Komiser Timur`, `Komiser Atilla` tek iz oldu;
   üç v6 kırpımı üçünü de yaklaşık 0,9999 güvenle okudu, yalnız Timur çıktı.
3. Cennetin Çocukları: `Murat Koçak`, `Berat Koç`, `Rıfat Koç` tek iz oldu;
   yalnız Murat çıktı. `Sanat Asistanları` ile `Kamera Asistanları` da birleşti.
4. Kulübe: `SCREENPLAY BY`, `RICHARD MUELLER`, `MAC DALGLEISH` ayrı v6
   kırpımlarında yaklaşık 0,999 güvenle okunmasına rağmen başka izlerde yutuldu.
5. Aspern Mektupları: `José María Pou`, `Productor Delegado`,
   `Productor Ejecutivo` başka benzer metinlerle birleşti.
6. İz Peşinde: `Işık Ekibi` ile `Set Ekibi` birleşti.
7. Pastane: eski/stilize fontta `Oynayanlar→Ogoypnlor`,
   `Resim Seçici→Resin Sogiai`, `Video Kayıt→Vibo Kopt`,
   `Video Kurgu→Vibo Kugn` gibi gerçek tanıma hataları var.

## 2. Değişmez tasarım kararı

Nash'in önceliği **eksiksizlik ve kaynak sadakati** olacak. Gürültülü bir
adayın kanıtla etiketlenmesi, gerçek bir kredinin sessizce silinmesinden daha
güvenlidir.

- DeepSeek açılmayacak; Nash dış bilgiden isim tamamlamayacak.
- Sponsor/logo metni silinmeyecek; gerekirse `logo_adayi` olarak işaretlenecek.
- Tekrarlanan ad/rol global olarak tekilleştirilmeyecek.
- Birden fazla yüksek güvenli zamansal metin tek sonuca zorlanmayacak.
- Eşikler tahminle seçilmeyecek; aşağıdaki gerçek vakalarda dağılım ölçülerek
  belirlenecek.
- 3 fps, yapısal kayıplar çözülmeden denenmeyecek.

## 3. Uygulama sırası

### Faz A — Önce testler, davranış değişikliği yok

Dokunulacak: `tests/test_hibrit.py`, `tests/test_metin_izleri.py`,
`tests/test_metin_uzlastirici.py`; yeni `olcum/kritik_vakalar.yaml`.

Saf sözlük/detection fixture'larıyla şu kırmızı testleri ekle:

1. Aynı bbox'ta ardışık üç statik kart: Komiser Sadi/Timur/Atilla üç ayrı iz.
2. Aynı soyadlı Murat/Berat/Rıfat Koç üç ayrı iz.
3. Aynı gerçek satırın küçük OCR varyantları tek iz.
4. Hızlı kayan aynı satır, bbox hareketine rağmen tek iz.
5. Sanat/Kamera Asistanları ayrı; Işık/Set Ekibi ayrı.
6. Alt bantta 10 kare süren yüksek güvenli YÖNETMEN kartı korunur.
7. Üç ensemble kırpımı üç zamansal moda aitse biri seçilip diğerleri yutulmaz.

Testler gerçek hatayı mevcut kodda göstermeden uygulamaya geçme.

### Faz B — Altyazı filtresini kayıpsız hale getir

Ana yer: `src/hibrit.py:paddle_oku` içindeki `yalniz_altyazi` erken elemesi.

Önerilen çözüm:

1. Alt-bant geometrisini erken ve yıkıcı bir eleme olmaktan çıkar.
2. Adayı izleyiciye gönder; yalnız `altyazi_adayi=true` kanıtı ekle.
3. Nash içinde salt alt-bant konumuyla hiçbir metni silme.
4. İleride filtre gerekiyorsa yalnız baskın kredi penceresi dışında kalan,
   kısa ömürlü, izole ve cümle-benzeri izleri ayrı bir postprocess sınıfında
   değerlendir. Şüphede koru.

Kabul: Cennetin Çocukları'ndaki dört kesin satır gelir; Çiçek Taksi 1'in 43
satırı ve Suç Dosyası'ndaki sahne-yazısı/layout temizliği gerilemez.

### Faz C — İz birleştirmeyi düzelt

Ana yer: `src/metin_izleri.py:izleri_kur`.

İki katmanlı güvenlik kur:

1. **Eşleme kapısı:** Orta metin benzerliği (`0,66` sınıfı), yalnız kırpım
   dHash'i ve öngörülen hareket de aynı nesneyi destekliyorsa bağ kurabilsin.
   Metin ve görünüm birlikte değişiyorsa aynı bbox yeterli olmasın.
2. **Statik/hareketli ayrımı:** Statik kart izi için boşluk en fazla 2 kare;
   12-kare tolerans yalnız tutarlı dikey hareketi kanıtlanmış scroll izinde.
3. **İz-içi mod bölme:** İz kurulduktan sonra gözlemleri zaman sırasıyla metin
   modlarına ayır. Farklı metinler ayrı zaman aralıklarında ve her biri çok
   kare/yüksek güvenle destekleniyorsa çocuk izlere böl.
4. Aynı yazımın OCR varyantları benzerlik + dHash + zaman yakınlığıyla tek
   kalmalı; yalnız ad ortaklığı (`Komiser`, `Koç`, `Asistanları`) birleşme için
   yeterli olmamalı.
5. Aynı metin jeneriğin iki uzak yerinde gerçekten tekrar ediyorsa iki ayrı iz
   olarak korunmalı; tekrar-blok katmanı ancak en az üç satırlık aynı diziyi
   kanıtladığında karar vermeli.

dHash ve benzerlik eşikleri önce kesin aynı/farklı çiftlerde raporlanmalı.
Dağılım görülmeden sayı config'e yazılmamalı.

### Faz D — Ensemble heterojen izleri saklamasın

Ana yer: `src/metin_uzlastirici.py:ikinci_tani` ve
`src/hibrit.py:_ensemble_kirpimlari`.

1. Üç kırpım farklı zaman modlarından geliyorsa tek metin uzlaşması yapma.
2. `secondary_vote_ratio < 1` tek başına hata değildir; fakat iki veya daha
   fazla yüksek güvenli ve anlamlı biçimde farklı metin varsa iz
   `heterojen_iz` olarak bölme katmanına geri gönderilmeli.
3. Kanıta tüm modlar, kare aralıkları, skorlar ve seçilmeme nedeni yazılmalı.
4. Aynı metnin noktalama/diyakritik varyantları mevcut uzlaşmadan yararlanmaya
   devam etmeli.

Kabul: Suç Dosyası üç Komiser rolünü, Cennetin Çocukları üç Koç adını, Kulübe
ve Aspern kesin kayıplarını ayrı ve doğru sırada vermeli.

### Faz E — Pastane font deneyi

Yapısal düzeltmeler yeşil olmadan model/önişleme değiştirme. Sabit Pastane
kırpımlarında şu matrisi ölç:

- Latin v5 normal ve mevcut sharpen
- v6 medium normal ve sharpen
- gri + CLAHE + 2x/3x büyütme
- yalnız gerekirse adaptif eşik; orijinal renkli kırpım kanıtı daima korunur

Ölçüler: sıralı GT kapsaması, kişi adı kapsaması, karakter hata oranı, yanlış
satır sayısı, süre. Suç Dosyası/Güneş/İz Peşinde temiz kohortu zarar kontrolü.
Kazanan her metinde değil, yalnız zayıf izlerde koşmalı. Üretim eşiği için
en az +10 GT satırı veya +10 puan kapsama ve temiz kohortta sıfır kayıp şartı
önerilir. Hiçbiri geçmezse mevcut OCR korunur ve düşük güvenli iz Jordan'a
kanıt/alternatifleriyle gönderilir; generatif düzeltme yapılmaz.

### Faz F — Gürültü ve sayısal kredi

- `2003` gibi çok-kareli, kredi bölgesi içindeki yıl salt `harfsiz` diye
  silinmemeli.
- `DOS`, `YAPIN` gibi tek-kare/zayıf artıklar support + model çatışmasıyla
  etiketlenmeli; kesin kredi kaybına yol açacak genel sayı/kısa metin yasağı
  konmamalı.
- Cennetin Çocukları sponsorları kaynaktaki gerçek metindir. İstenmiyorsa
  silmek yerine `logo_adayi`/`sponsor_adayi` sınıfıyla ayrı yüzey sunulmalı.

## 4. Zorunlu kabul kapıları

1. Tüm Nash testleri yeşil; başlangıç tabanı en az `232 passed, 1 skipped`.
2. Yukarıdaki yedi kesin vaka tek tek yeşil.
3. Çiçek Taksi 1: mevcut 43 satır ve bilinen doğru kişi/rol satırları korunur.
4. Marnalı: beş satırlık gerçek tekrar blok temizlenir, benzersiz satır kaybı
   olmaz.
5. 20-video koşusu yeniden: 20/20 `OKUNDU`, 0 arıza.
6. İnsan GT'li hiçbir filmde eşleşen satır sayısı düşmez; Suç, Cennet,
   Pastane ve Kulübe kesin vakaları artar.
7. Süre 561 saniyenin 1,5 katını, GPU bellek Sheriff'in Nash bütçesini aşmaz.
8. Her gerçek koşunun `rapor.json`, kritik vaka karşılaştırması ve değişen
   satır listesi saklanır. Yalnız `OKUNDU` sayısı kabul kanıtı sayılmaz.

Komutlar:

```bash
cd /opt/mitas/Allstar/nash
venv/bin/python -m pytest tests -q
venv/bin/python olcum/okunmalik_toplu.py \
  --run-dir /tmp/nash-okunmalik-jenerikler-v2
venv/bin/python olcum/jenerik_kabul.py \
  --gt /opt/mitas/Allstar/gt_dizi/suc_dosyasi/cikis.txt \
  --candidate /tmp/nash-okunmalik-jenerikler-v2/out/20_suc_dosyası_29m35s_bitis/cikis/nash.json
```

## 5. Commit ve teslim disiplini

Önerilen ayrı commitler:

1. `nash: add credit-loss regression fixtures`
2. `nash: make subtitle evidence non-destructive`
3. `nash: split heterogeneous temporal text tracks`
4. `nash: improve weak legacy-font recognition` — yalnız Faz E kapıyı geçerse
5. `nash: record full credit-reader acceptance`

Yalnız Nash yolları stage edilmeli. Ağaçtaki `Allstar/MAP.md`, GT dosyaları,
`model_manifest.yaml`, yedek ZIP'ler, `Allstar/selami/` ve `locks/gpu.lock`
bu işin dışında bırakılmalı. Son commit/push ancak bütün kabul kapıları
geçtiğinde yapılmalı.

## Sonnet için kısa görev metni

> `/opt/mitas/Allstar/nash/docs/2026-08-20-kalite-onarim-plani.md` dosyasını
> eksiksiz uygula. Önce mevcut hataları kırmızı regresyon testleriyle yeniden
> üret. Nash'in mevcut üretim davranışını ölçümsüz değiştirme; DeepSeek açma,
> dış bilgiden isim düzeltme ve global dedup yapma. Her faz sonunda hedefli
> testleri, finalde 20-video gerçek koşusunu ve insan GT karşılaştırmasını
> çalıştır. Yalnız Nash dosyalarını stage et; bütün kapılar geçmeden final
> commit/push yapma. Yaptığını, yapamadığını ve kalan gerçek kayıpları açıkça
> raporla.
