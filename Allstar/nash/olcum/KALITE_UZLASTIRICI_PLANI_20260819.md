# LeBron–Nash–Jordan kalite uzlaştırıcısı planı

Tarih: 2026-08-19

Durum: Tasarım. Bu belge uzlaştırıcıyı henüz üretim koduna eklemez.

## Karar

- Nash her bölümde çalışır; hızlı aday metin ve kaynak kare/bbox kanıtı üretir.
- LeBron her bölümde çalışır; ana metin okuyucudur.
- Jordan varsayılan okuyucu değildir. Yalnız LeBron–Nash anlaşmazlığı, okuyucu arızası veya ölçülmüş düşük güven varsa hakem olarak açılır.
- Üç okuyucunun satırları düz biçimde birleştirilmez. Her karar; kaynak satır, alternatifler, kanıt, sınıf ve karar gerekçesiyle saklanır.
- Altyazı ve logo satırları silinmez; ayrı içerik türüyle korunur ve nihai kredi görünümünden filtrelenir.
- Kalite kapısı okuyucuların birbirleriyle örtüşmesi değil, dondurulmuş elle doğrulanmış gerçek listedir.

## Bugünkü sistemde değişmesi gereken gerçekler

Mevcut Sheriff DAG'ında LeBron ve Jordan, Kobe'nin sınır sonucuna bağlıdır. Kobe `NO_CONTENT` verdiğinde ikisi de çalışmadan `NO_CONTENT` olur. Bu, “LeBron her zaman” kararıyla çelişir.

Yeni akışta Kobe bir daraltma ipucu olacak, içerik kapısı olmayacaktır:

1. `media_prep` giriş/çıkış ana havuzunu hazırlar.
2. Nash ana havuzdan her zaman çalışır.
3. Kobe başarılıysa LeBron için seçili aralığı daraltır.
4. Kobe `NO_CONTENT` veya `FAILED` ise materializer, ana havuzdan nötr metin-kutusu seçimiyle sınırlı bir LeBron havuzu üretir.
5. LeBron her iki durumda da çalışır ve kendi sonucu olarak `READ`, `NO_TEXT` veya `FAILED` verir.
6. İlk uzlaştırma yalnız Nash ve LeBron terminal olduktan sonra yapılır.
7. Jordan görevi ancak ilk uzlaştırmanın denetlenebilir tetik koşulu oluşursa `READY` yapılır.
8. Jordan gerekmezse görev `SKIPPED_POLICY` olur; bu durum video “metinsiz” demediği için `NO_CONTENT` olarak yazılmaz.
9. Son uzlaştırma, Jordan çalıştıysa üç kanalı; çalışmadıysa iki kanalı kullanır.

## Veri modeli

Yeni kanonik çıktı `mitas.uzlastirma/v1` olur. Mevcut tüketiciler için ayrıca geriye uyumlu bir `mitas.okuma/v2` izdüşümü üretilir.

Her uzlaştırma öğesi şunları taşır:

- Ham metinlerin tamamı; hiçbir okuyucunun metni üzerine yazılmaz.
- Script-duyarlı normalize metin ve eşleştirme yöntemi.
- `AGREED`, `LEBRON_ONLY`, `NASH_ONLY`, `CONFLICT`, `UNRESOLVED` karar durumu.
- `CREDIT`, `SUBTITLE`, `LOGO`, `OTHER`, `UNCERTAIN` içerik türü.
- LeBron, Nash ve varsa Jordan satır kimlikleri.
- Her okuyucunun gerçek bbox, kare, zaman ve asset kanıtı.
- Seçilen kanonik metin, alternatifler ve karar kuralı.
- Jordan tetik nedeni ve harcanan süre/VRAM.

`mitas.okuma/v2.lines` yalnız `ACCEPTED_CREDIT` öğelerinden üretilir. Altyazılar kaybolmaz; yeni pakette `RETAINED_SUBTITLE`, uyumlu pakette gerekçeli `rejected_lines` olarak kalır. Bbox'sız satıra bbox eklenmez ve bütün satırlar gerçekten kanıtlı değilse `proof=COMPLETE` yazılmaz.

## Eşleştirme ve karar kuralları

### Aday kümeleri

1. Unicode NFKC, boşluk normalizasyonu ve casefold uygulanır; ham metin korunur.
2. Önce birebir ve fold-birebir eşleşme yapılır.
3. Kalanlar script, satır sırası, kaynak zaman/bbox ve uzunluk kısıtlarıyla adaylaştırılır.
4. Fuzzy benzerlik yalnız çatışma adayı üretir; tek başına yüksek güvenli kabul üretmez.
5. Bir satır iki farklı satıra uyuyorsa otomatik seçim yapılmaz; `UNRESOLVED` kalır.

### Metin kararı

- LeBron ve Nash birebir/fold-birebir anlaşıyorsa metin yüksek güvenle kabul edilir.
- Anlaşmaları, satırın kredi olduğunu tek başına kanıtlamaz; içerik sınıfı ayrıca belirlenir.
- Yalnız LeBron'da bulunan, kanıtlı ve isim/rol niteliği güçlü satır geçici kabul edilebilir; düşük kanıt veya bozukluk sinyali Jordan tetikler.
- Yalnız Nash'te bulunan satır, yüksek Paddle güveni ve zamansal destek taşıyorsa korunur; LeBron'un sessiz kalması nedeniyle silinmez.
- Jordan iki adaydan biriyle açıkça uyuşursa iki-oy kuralıyla o aday seçilir.
- Jordan'ın tek başına ürettiği yeni metin, diğer kanallardan kaynak kanıtı yoksa otomatik olarak kanonik metnin üzerine yazılmaz; alternatif olarak tutulur.
- İki model anlaşmıyor ve Jordan da kesinleştirmiyorsa iki alternatif de saklanır, öğe `UNRESOLVED` olur.

### Altyazı etiketi

Altyazı kararı tek bir “alt yüzde” kuralına bağlanmaz. Aşağıdaki sinyaller birlikte raporlanır:

- Alt bölgede konum ve kısa süreli değişim.
- Cümle yapısı, konuşma noktalaması ve satır uzunluğu.
- Ardışık karelerde yer değiştirme/değişme örüntüsü.
- İsim/rol sözlüğü, büyük harf kartı ve jenerik düzeni karşı sinyalleri.
- Kanal logosunda küçük köşe konumu ve uzun süre değişmeme.

İlk sürüm kalibre edilene kadar sonuç yalnız kural etiketi ve gerekçe taşır; güven skoru gerçek veri olmadan uydurulmaz.

## Jordan tetik politikası

Jordan bütün bölümü rutin olarak okumaz. Aşağıdakilerden biri gerçekleşirse açılır:

- LeBron `FAILED`; veya LeBron `NO_TEXT` iken Nash gerçek metin buldu.
- Nash `FAILED`; LeBron kanıt kapsamı düşük veya bozukluk sinyali yüksek.
- Ortak adaylardaki gerçek metin çatışma oranı kalibre edilmiş eşiği aştı.
- Kanıtlı/name-like tek-kanal satırları var ve diğer okuyucu bunları doğrulamıyor.
- Çok alfabeli yönlendirme, düşük Latin güveni veya script takeover gerçekleşti.
- LeBron proof kapsamı kabul eşiğinin altında.

Salt satır sayısı farkı Jordan açmak için yeterli değildir. Eşikler elle etiketli kalibrasyon kümesinden çıkarılır; başlangıçta sabit “sihirli” oran üretime konmaz.

Jordan'a mümkünse yalnız tartışmalı kaynak zamanları/bbox bölgeleri verilir. Yakın bölgeler tek kısa klipte birleştirilir. Bir LeBron satırının kaynak zamanı yoksa ve riskli isim kaybı ihtimali varsa son çare olarak bölüm klibi kullanılır. Jordan modeli, backend'i ve istem reçetesi Jordan kulesinin kendi config'inde kalır; Sheriff model seçmez.

## Sheriff DAG değişikliği

Yeni görevler:

- `materialize_primary`: Kobe sonucunu ipucu olarak kullanır; başarısız/no-content durumda ana havuz fallback'i üretir.
- `reconcile_primary`: Nash + LeBron paketlerini karşılaştırır ve Jordan kararını üretir.
- `materialize_disputes`: yalnız tetik varsa tartışmalı kısa klipleri hazırlar.
- `reader_video`: başlangıçta `WAITING_POLICY`; sonra `READY` veya `SKIPPED_POLICY`.
- `reconcile_final`: iki veya üç kanaldan nihai paketi oluşturur.
- `handoff`: ham kanalları, uzlaştırma paketini ve karar manifestini birlikte yayımlar.

`SKIPPED_POLICY` Sheriff'in iç terminal durumudur; `NO_CONTENT`, `FAILED` veya `CANCELLED` anlamına gelmez. Bundle şeması v2, iki zorunlu kanal (LeBron/Nash), bir isteğe bağlı Jordan kanalı ve zorunlu uzlaştırma kanalını doğrular. Kobe sonucu hiçbir okuyucunun var olmayan metin sonucuna dönüştürülmez.

Kaynak tüketiminde LeBron ve Jordan aynı anda yüklenmez. `max_deepseek_jobs=1`, Jordan exclusive rezervasyonu ve OOM exclusive retry korunur. Jordan tetik oranı ile yalnız tartışmalı klip saniyesi raporlanır.

## Gerçek veri ve ölçüm

29 videonun 58 giriş/çıkış bölümü dondurulmuş kabul yatağı olur:

- 12 film/24 bölüm kalibrasyon ve geliştirme kümesi.
- Kalan 17 film/34 bölüm kör kabul kümesi.
- Statik kart, kayan jenerik, altyazılı, düşük kontrast, Arabic, Cyrillic ve çift dilli örnekler iki kümeye dengeli dağıtılır.

Her gerçek kayıt şunları içerir:

- Ekranda gerçekten bulunan kişi adları ve kredi satırları.
- Ham yazım, normalize yazım, script ve `CREDIT/SUBTITLE/LOGO` etiketi.
- En az bir kaynak kare/zaman; mümkün olan yerde bbox.
- Okunamayan/kararsız alan işareti.

Etiketler model çıktısından kopyalanmaz. İlk transkripsiyondan sonra görüntüye bakılarak ayrı ikinci kontrol yapılır; uyuşmazlıklar karara bağlanır ve veri hash'i dondurulur. Kalibrasyon tamamlandıktan sonra kör küme eşik ayarlamak için kullanılmaz.

Ölçümler film ve bölüm bazında raporlanır:

- Gerçek kişi adı precision/recall/F1.
- Tam kredi satırı exact ve fuzzy-normalize recall.
- Gerçek isim kaybı ve yanlış isim ekleme listesi.
- Altyazı/logo bulaşma oranı.
- `UNRESOLVED` oranı.
- Gerçek bbox kanıt precision'ı ve kapsamı.
- Jordan tetiklenen bölüm/bölge/saniye oranı.
- Toplam süre, model çağrısı, peak VRAM ve doğru benzersiz isim başına maliyet.

## Üretim kabul kapıları

- Kör kümede hiçbir yüksek-güvenli gerçek kişi adı, LeBron–Nash birleşik aday havuzunda bulunduğu halde nihai sonuçta kaybolmayacak.
- Nihai kişi adı precision'ı hem LeBron hem Nash tekil sonucundan yüksek olacak; recall en iyi tekil okuyucudan gerilemeyecek.
- Altyazı/logo bulaşması en iyi tekil okuyucuya göre en az %50 azalacak; kredi recall kaybı %1'i aşmayacak.
- Jordan bölüm bazında en fazla %35 oranında açılacak; öncelik bütün bölüm yerine tartışmalı bölgeler olacak.
- Kabul edilen her satır en az bir gerçek okuyucu kaynağına bağlı olacak. Üretilmiş bbox olmayacak.
- Jordan arızası nihai paketi sessizce `NO_CONTENT` yapmayacak; anlaşmazlıklar görünür `UNRESOLVED` kalacak.
- LeBron ve Nash, Kobe `NO_CONTENT` veya `FAILED` olsa da iki bölümde de çalışacak.

Bu eşikler ilk kör ölçümden sonra gevşetilmez. Geçmeyen sürüm yalnız shadow çıktısı üretir ve mevcut üretim handoff'unun yerini almaz.

## Uygulama sırası

1. Önce mevcut LeBron `COKME`, proof ve gereksiz model çağrısı hataları kapatılır.
2. Tamamlanmış 29-video çıktıları üzerinde salt-okunur offline uzlaştırıcı yazılır; Sheriff DAG değişmez.
3. Gerçek liste etiketleme aracı ve doğrulama şeması hazırlanır; veri dondurulur.
4. Eşleştirme, içerik etiketi ve Jordan tetik eşikleri yalnız kalibrasyon kümesinde ayarlanır.
5. Tartışmalı bölge materializer'ı ve Jordan hakem istemi eklenir.
6. Kör kabul kapıları çalıştırılır ve ayrıntılı fark raporu üretilir.
7. Başarılıysa Sheriff'e feature flag ile yeni DAG eklenir; önce shadow, sonra üretim terfisi yapılır.

## Bilinçli olarak yapılmayacaklar

- Üç JSON'u düz union/dedup yapmak.
- En çok satır üreten modeli otomatik kazanan saymak.
- Fuzzy benzerliği gerçek bbox veya gerçek isim kanıtı saymak.
- Altyazıyı kayıtsız silmek.
- Jordan'ın tek başına önerdiği metni kanıtsız biçimde doğru kabul etmek.
- Sheriff'ten Jordan model/backend ayarı göndermek.
- Elle doğrulanmış gerçek liste oluşmadan güven eşiklerini üretime kilitlemek.
