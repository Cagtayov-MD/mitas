# Shaq durumu

Shaq kuruldu ve gölge modundadır; QC1'e veya canlı hatta bağlı değildir.

**AÇIK KUSUR (2026-08-20): Shaq, Nash'in bugünkü paketlerini okuyamıyor.**
`sozlesme.py` `mitas.okuma/v1` istiyor, Nash `mitas.okuma/v2` üretiyor; fark
yapısal (`bolum`→`section`, `durum` dizgi→`status` sözlük, bbox sözlük→liste,
`text`→`raw_text`). Gerçek paketle denendi, `SozlesmeHatasi` ile reddedildi.
Kule gölgede olduğu için bugüne kadar fark edilmedi. Ayrıntı ve sürüm
etiketinin neden `v1` bırakıldığı: `README.md` girdi sözleşmesi bölümündeki
uyarı kutusu. **Uyumsuzluk kapanmadan Shaq üretim hattına bağlanamaz.**

Kontrol modeli **bilerek bağlı değildir**. Kule, kör bbox crop'ları ve
`mitas.kontrol/v1` istek/cevap dosyalarını hazırlar; ileride seçilecek 27B veya
başka bir sağlayıcı bu sözleşmeye bağlanır. Gerçek insan etiketli ölçüm henüz
olmadığından doğruluk oranı iddia edilmez.

Doğrudan IMDb/TMDb/Wikidata bağlantısı bilerek bağlı değildir. Bugün kule,
bu kaynaklardan üretilmiş film-ID kapsamındaki salt-okunur kredi snapshot'ını
`--kimlik-json` adaptörüyle alır. Gelecekteki doğrudan sağlayıcı aynı
`KimlikSaglayici` sözleşmesine takılır. Kesin film dış kimliği olmadan
başlıktan film tahmini yapılmaz; veri tabanında görünmeyen ekip üyeleri
olumsuz kanıt sayılmaz.

## HAKEEM paralel motoru

Mevcut Shaq değiştirilmeden HAKEEM challenger aynı kuleye eklendi. HAKEEM;
conflict-group, gerçek model bağımsızlığı, deterministik bbox istekleri,
kanıta bağlı kontrol cevapları ve dört-paket film manifesti kullanır.
`out_hakeem/` izoledir ve QC1'e bağlı değildir.

100-film ölçüm aracı hazırdır; ancak 2026-08-17 itibarıyla çalışma ağacında
`*.okuma.json` üretimi başladı: 2026-08-19 itibarıyla ağaçta **883** paket var
(sheriff: nash 347 · lebron 125 · jordan 72; ayrıca `shaq/in/` altında 30 film
× 76 bölüm üç kanallı). Gerçek karşılaştırmanın önündeki engel artık paket
yokluğu DEĞİL, **birim uyuşmazlığıdır**: Nash kutu parçası, LeBron/Jordan
birleştirilmiş satır üretiyordu. Faz B bunu Nash içinde kapatır.
Okuyucu adaptörleri dört bbox'lı paketi ürettikten ve insan GT'si hazırlandıktan
sonra kazanan `karsilastir` raporuyla belirlenecektir. Ayrıntı: `HAKEEM.md`.
