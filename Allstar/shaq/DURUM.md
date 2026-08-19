# Shaq durumu

Shaq kuruldu ve gölge modundadır; QC1'e veya canlı hatta bağlı değildir.

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
`*.okuma.json` sayısı **0** olduğu için gerçek karşılaştırma henüz koşulamaz.
Okuyucu adaptörleri dört bbox'lı paketi ürettikten ve insan GT'si hazırlandıktan
sonra kazanan `karsilastir` raporuyla belirlenecektir. Ayrıntı: `HAKEEM.md`.
