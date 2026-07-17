# HİBRİT-DY — TÜM KORPUS GÖRSEL QC ("hepsine geçsek sorun olur mu?")
2026-07-11 · 6 paralel görsel-QC ajanı, 37 benzersiz master (D:\master png test baseline = eski kod çıktısı) tek tek açıldı · SALT-OKUR

## ÜST CEVAP
**Hepsine geçmek GÜVENLİ: sıfır regresyon.** Gölge taraması 52 filmden yalnız **Yedi Numara**'yı FULL'e sokuyor; kalan hepsi MASKED = eski kodla birebir (SHA 267/267 kanıtlı). Görsel QC bunu doğruladı: hibrit'in dokunmadığı filmler eskisiyle aynı, hiçbiri kötüleşmiyor. Yedi Numara hayaleti düzeliyor (isim-düzeyi kanıtlı). **AMA hibrit evrensel hayalet-öldürücü DEĞİL** — farklı türden bir hayalet (senin_hikayen) çözülmeden kalıyor (ama bozulmuyor da).

## ÜÇ KOVA

### A) HİBRİT'İN DÜZELTTİĞİ (bayrak-1'de değişen tek film)
- **yedi_numara** — donmuş-arka-plan + kayan yazı → maske %57.6 şişip masked-dy çöküyordu (105/120 kare atlanmış → katastrofik hayalet: SEDEF PEHLİVANOĞLU→"SFAFF PEHI OANAGI U"). Hibrit FULL → tam-kare hız → temiz. İki ajan bağımsız doğruladı: ESKİ=ders kitabı hayalet, YENİ=her kredi kendi satırında.

### B) HİBRİT'İN DOKUNMADIĞI + ZATEN TEMİZ (çoğunluk — MASKED, birebir aynı)
alt_n_yumruk, anjel_k_ve_sultan, attila_marcel (10492px), babam, beni_böyle_sev, cennetin_rengi, dirilis_ertugrul, drakula, franny, hayat_bir_romandır, jurassic_park (16612px), kardeşim, kazananlar_kulübü, kukla_adam, maksim, marie_curie, mavzer, monte_kristo, mumya (kinetik-harf açılışı hayalet DEĞİL, kaynak-tasarım), plak_ağaçlar, pororoca, robinson, son_metro, x_men, yabandan_gelen_adam, yalaza, özgürlük_yürüyüşü — **hepsi okunur, 0 hayalet.**

### C) HİBRİT İLE ALAKASIZ ÖNCEDEN-VAR DURUMLAR (bayrak fark etmez, aynı kalır)
- **senin_hikayen — FARKLI TÜR HAYALET (v2 hedefi):** jenerikler arasına serpiştirilmiş HAREKETLİ film-klip küçük-resimleri → dikey smear + aralıklı satır-çakışması. Gölge kararı MASKED (cov 0.198, eşik altında). Hibrit DOKUNMAZ — ve dokunmakla iyi eder: FULL ateşleseydi tam-kare o hareketli footage'ı takip ederdi (İLK YARIŞ ters-patolojisi → daha kötü). İsimler çoğunlukla kurtarılabilir okunuyor ama master gözle bozuk. **Şartnamede "üçüncü mod, çözülmedi" diye işaretli olan tam bu.**
- **Gerçek ama okunur SMEAR** (footage-üstü/geçiş, farklı mekanizma, hibritsiz de böyle): beyaz_bizon (Cast of Characters geçiş paneli — komşu panelden kurtarılıyor), pilkington (yürüyen figür), bizim_evin_halleri (=Ferhunde; 2 küçük yerel çakışma, isimler okunur).
- **FOOTAGE-BLOAT / BOŞ** (kaynakta jenerik yok — pipeline hatası değil): d_zinesi_bir_arada ("The End" kartı), zengin_olsaydın (dublajlı yabancı, "The End"), k_zg_n_silah (eski Western, kapanışta jenerik akmıyor), pinokyo (footage-bloat ama yazı okunur).

## VERİ-KAYBI HÜKMÜ
- **Regresyon (bir şeyi bozmak): 0.** Sadece Yedi Numara değişiyor, o da iyileşiyor. Diğer 36 film MASKED = değişmez.
- **Kazanç: 1** (Yedi Numara, katastrofik → temiz).
- **Açık kalan (kayıp DEĞİL, iyileşme-yok): senin_hikayen sınıfı** (hareketli-küçük-resim) + okunur-smear'ler. Bunlar zaten böyleydi, hibrit bozmuyor ama düzeltmiyor.

## SONUÇ
"Hepsine geç" = güvenli ve doğru; **kayıp yok, 1 net kazanç.** Ama "tüm hayaletler bitti" demek YANLIŞ olur — en az bir farklı hayalet sınıfı (senin_hikayen: hareketli-küçük-resim) açık kalıyor. Bu sınıf, ayrı bir v2 işi (şartnamedeki "üçüncü mod"un canlı örneği bulundu). Tam üretim arşivi için: aynı gölge-taramayı tüm Database'de koşup karar histogramına bakmak — yalnız-MASKED + bilinen donmuş-scroll ise varsayılanı çevir + bayrak dalını sil.
