# Fast vs Quality ASR Difference Report

Karşılaştırma yönü: `fast / large-v3-turbo` -> `quality / large-v3`.
Bu liste referans doğruluğu değil, iki modelin farklı duyduğu aday yerleri gösterir.

## Neretva Üstüne Düşen Hilal

- Fast kelime: 1497
- Quality kelime: 1496
- Yer değiştirme: 71
- Fast fazladan kelime: 10
- Quality fazladan kelime: 9

| Fast | Quality | Adet | Fast bağlam | Quality bağlam |
|---|---|---:|---|---|
| kurulardan | kurulalıdan | 1 | Ben Mustafa Kaytas Mostar şehri kurulardan beri burada oturur benim ailem Belki de | Ben Mustafa Kaytas Mostar şehri kurulalıdan beri burada oturur benim ailem Belki de |
| burada | burayı | 1 | Ben Mustafa Kaytas Mostar şehri kurulardan beri burada oturur benim ailem Belki de onlar kurdular | oturur benim ailem Belki de onlar kurdular burayı Yalnız soyumun Türkiye'den gelme olduğunu biliyorum Asırlarca |
| çektik | çekti | 1 | bir savaşı kabullenemediler Biz kaldık ama neler çektik Hayatta kalabilmek çok zordu Dolap beygiri gibi | bir savaşı kabullenemediler Biz kaldık ama neler çekti Hayatta kalabilmek çok zor Dolap peygiri gibi |
| beygiri | peygiri | 1 | neler çektik Hayatta kalabilmek çok zordu Dolap beygiri gibi dönüp duruyordu Ölmeyenler eminim ki bir | neler çekti Hayatta kalabilmek çok zor Dolap peygiri gibi dönüp duruyordu Ölmeyenler eminim ki bir |
| güne | Bugüne | 1 | değirmenleri hanlar hamamlar çeşmeler ve camiler Bu güne kadar yüz yıldır tahrip edilerek bir kısmının | su değirmenleri hanlar hamamlar çeşmeler ve camiler Bugüne kadar yüzyıldır tahrip edilerek bir kısmının izinin |
| yıldır | yüzyıldır | 1 | çeşmeler ve camiler Bu güne kadar yüz yıldır tahrip edilerek bir kısmının izinin bile kalmadığını | hanlar hamamlar çeşmeler ve camiler Bugüne kadar yüzyıldır tahrip edilerek bir kısmının izinin bile kalmadığını |
| tanınmış | tanımış | 1 | izinin bile kalmadığını görürsünüz Dünyanın bildiği en tanınmış varlığımız köprümüzdür O sanki taştan yapılma bir | izinin bile kalmadığını görürsünüz Dünyanın bildiği en tanımış varlığımız köprümüzdür O sanki taştan yapılma bir |
| değildir | değil | 1 | köprümüzdür O sanki taştan yapılma bir köprü değildir Efsanevi bir varlığı Ona nasıl kıydılar bilemiyordum | gezerdi Yine gelenler oluyor ama o kadar değil Dediğim gibi Mostar Türklerin şehir yaptığı bir |
| varlığı | varlıktı | 1 | taştan yapılma bir köprü değildir Efsanevi bir varlığı Ona nasıl kıydılar bilemiyordum Şimdi köprü yok | taştan yapılma bir köprü değil Efsanevi bir varlıktı ona nasıl kıydılar bilemiyorum şimdi köprüyor Mostar |
| bilemiyordum | bilemiyorum | 1 | değildir Efsanevi bir varlığı Ona nasıl kıydılar bilemiyordum Şimdi köprü yok Mostar ne kadarmış Şehrin | değil Efsanevi bir varlıktı ona nasıl kıydılar bilemiyorum şimdi köprüyor Mostar ne kadarmış Şehrin her |
| yok | köprüyor | 1 | varlığı Ona nasıl kıydılar bilemiyordum Şimdi köprü yok Mostar ne kadarmış Şehrin her yanında olduğu | bir varlıktı ona nasıl kıydılar bilemiyorum şimdi köprüyor Mostar ne kadarmış Şehrin her yanında olduğu |
| dokuyu | hukuyu | 1 | büyük kulelerde her iki yandaki çarşılarda tarihi dokuyu muhafaza eden bütün yapılar her yan delik | büyük kulelerde her iki yandaki çarşılarda tarihi hukuyu muhafaza eden bütün yapılar her yan delik |
| çalışıyorlar | çalışıyor | 1 | her gün umutla dükkanını açıp işini yapmaya çalışıyorlar İşte demircisiydi bakırcısıydı kelemcisiydi şosobosu El emeği | her gün Umut'la dükkanını açıp işini yapmaya çalışıyor İşte demircisiydi bakırcisiydi kelemcisiydi şosobosu El emeği |
| Neretve'ye | Neretva'ya | 1 | haliyle onarılmayı bekliyor Büyük köprünün hemen yakınında Neretve'ye karışan Radovolya çayı var Şimdi barajlar yüzünden | haliyle onarılmayı bekliyor Büyük köprünün hemen yakınında Neretva'ya karışan Radobolya çayı var Şimdi barajlar yüzünden |
| Radovolya | Radobolya | 1 | bekliyor Büyük köprünün hemen yakınında Neretve'ye karışan Radovolya çayı var Şimdi barajlar yüzünden pek suyu | bekliyor Büyük köprünün hemen yakınında Neretva'ya karışan Radobolya çayı var Şimdi barajlar yüzünden pek suyu |
| değerinin | değirmeni | 1 | gür akarmış Zaten üzerinde pek çok su değerinin vardı İşte burada Büyük köprünün denemesini yapmışlar | gür akarmış Zaten üzerinde pek çok su değirmeni vardı İşte burada büyük köprünün denemesini yapmışlar |
| camiydi | camiyiydi | 1 | etrafını Türkler tekrar yaptılar Mostar'ın en eski camiydi Sokağıyla evleriyle müştemilatıyla yapıldı yeniden Kuyumcular Çarşısı | etrafını Türkler tekrar yaptılar Mostar'ın en eski camiyiydi Sokağıyla evleriyle müştemilatıyla yapıldı yeniden Kuyumcular çarşısı |
| debbaların | debbağların | 1 | tabiata ne kadar uyar Tabakani Camii buradaki debbaların ibadet yeriymiş Epey zarar görmüştü yenilendi Eminim | tabiata ne kadar uyar Tabakani Camii buradaki debbağların ibadet yeriymiş Epey zarar görmüştü yenilendi Eminim |
| çożun | çocuğun | 1 | soyadım Lakşe Büyüklerim Konyalıymış Bu Gizel Kente çożun geçmiş Mostar önce çok güzel bir şehir | soyadım Lakşe Büyüklerim Konyalıymış Bu gizel kente çocuğun geçmiş Mostar önce çok güzel bir şehirmiş |
| şehir | şehirmiş | 1 | o kadar değil Dediğim gibi Mostar Türklerin şehir yaptığı bir yer Bunların arasında benim atalarım | çocuğun geçmiş Mostar önce çok güzel bir şehirmiş Her şey Bosna'da bizim için en güzel |
| imiş | Her | 1 | geçmiş Mostar önce çok güzel bir şehir imiş Herzek Bosna'da bizim için engizel kent Mostarlar | hem diğer insanlarımız birçok şeylerini kaybetmeye başladılar Her şeyi devletleştirdiler o zaman Elimizde avucumuzda ne |
| Herzek | şey | 1 | Mostar önce çok güzel bir şehir imiş Herzek Bosna'da bizim için engizel kent Mostarlar çok | buradan geçen insanlar yüzyıllar öncesinde hissederdik Her şey orijinal halinde korunmaya çalışılıyordu Bugün yine gayret |
| engizel | güzel | 1 | bir şehir imiş Herzek Bosna'da bizim için engizel kent Mostarlar çok çok seviyor Bırakıyor ama | gizel kente çocuğun geçmiş Mostar önce çok güzel bir şehirmiş Her şey Bosna'da bizim için |
| Mostarlar | Mostar'ı | 1 | imiş Herzek Bosna'da bizim için engizel kent Mostarlar çok çok seviyor Bırakıyor ama sonra dönüyor | kültür dokusu Neretva'nın iki yamacına kurulmuş olan Mostar'ı Mostar yapan eserleri tanımak lazım tanıtmak lazım |
| seviyor | seviyorum | 1 | bizim için engizel kent Mostarlar çok çok seviyor Bırakıyor ama sonra dönüyor Konya'yı bırakıyor sonra | için en güzel kent Mostar'ı çok çok seviyorum Bırakıyor ama sonra dönüyor Konya'yı bırakıyor sonra |
| Mostarçok | çok | 1 | yapıyoruz Mostar bir din yada Evet şimdi Mostarçok şe savaşta zarar görmüş çok harabe var | Biz kaldık ama neler çekti Hayatta kalabilmek çok zor Dolap peygiri gibi dönüp duruyordu Ölmeyenler |
| Mostar | mostlar | 1 | Ben Mustafa Kaytas Mostar şehri kurulardan beri burada oturur benim ailem | görmüş çok harabe var Şimdi yavaş yavaş mostlar yine kalkıyor yaralar geçiyor Güzel oluyor Eski |
| Bileçya'da | Bilekçe'de | 1 | kazanmaya çalışan şu Mostar'lı hanımı bir dinleseniz Bileçya'da doğdum ama 1948'den beri Mostar'da yaşıyorum Üç | kazanmaya çalışan şu Mostarlı Hanım'ı bir dinleseniz Bilekçe'de doğdum ama 1948'den beri Mostar'da yaşıyorum Üç |
| kaybetti | kaybettik | 1 | oldu İçimiz yandı Sanki onunla her şeyimizi kaybetti Ancak şunu söylemeliyim ki asla suçlu değildik | oldu İçimiz yandı Sanki onunla her şeyimizi kaybettik Ancak şunu söylemeliyim ki asla suçlu değildik |
| Camii | Camiyi | 1 | Eğri Köprüyü Sel sularına kapıldı İnşallah Nezira Camii gibi o da tekrar yapılır 950 senesinde | dediğiniz büyük vezirin günlükçüsüymüş Çok hayırsever biriymiş Camiyi Türkiye restore ediyor Gençler çalışıyordu Savaşta minaresi |
| görünümüdür | görünümlüdür | 1 | nokta Koski Mehmetbaşa Camii'ndendir Biri minarenin şerefesinden görünümüdür diğeri ise yan avlusundaki çıkıntı üzeridir Haziresinde | nokta Koski Mehmetbaşa Camii'ndendir Biri minarenin şerefesinden görünümlüdür diğeri ise yan avlusundaki çıkıntı üzeridir Haziresinde |
| Mostar'ın | Moslar'ın | 1 | yıktırılan cami ve etrafını Türkler tekrar yaptılar Mostar'ın en eski camiydi Sokağıyla evleriyle müştemilatıyla yapıldı | mezar taşları vardı Şadırvanı da halen kullanılıyor Moslar'ın sembol eserlerinden Bişçevişköy Sahipleri Ahmet Bey de |
| Köşkü | Bişçevişköy | 1 | da halen kullanılıyor Mostar'ın sembol eserlerinden Bişeviş Köşkü Sahipleri Ahmet Bey de Zehra Hanım'da vefat | Şadırvanı da halen kullanılıyor Moslar'ın sembol eserlerinden Bişçevişköy Sahipleri Ahmet Bey de Zehra Hanım da |
| Hanım'da | da | 1 | Bişeviş Köşkü Sahipleri Ahmet Bey de Zehra Hanım'da vefat ettiler Kim bilir ne hatıralar yıkmış | bugün böyle bir şans tanımadılar Nasıl oldu da hayatta kalabildik bilmiyorum Çocuklarımız burayı terk ettiler |
| mangaları | mangalları | 1 | kimler inip çıkmıştır Kapıları pencereleri sedirleri sergenleri mangaları yastıkları Ziyaretçisi hiç eksik olmaz müzeydir Avrupa'nın | kimler inip çıkmıştır Kapıları pencereleri sedirleri sergenleri mangalları yastıkları Ziyaretçisi hiç eksik olmaz müze evdir |
| müzeydir | evdir | 1 | sergenleri mangaları yastıkları Ziyaretçisi hiç eksik olmaz müzeydir Avrupa'nın ortasında tam bir Türk evini hem | mangalları yastıkları Ziyaretçisi hiç eksik olmaz müze evdir Avrupa'nın ortasında tam bir Türk evini hem |
| halini | haliyle | 1 | Türk evini hem de otantik ve orijinal halini görmek belki onları şaşırtıyordu ama kültür bu | çıkarıyor Kalın kesme taşlar Eksikleri tamamlanıp eski haliyle onarılmayı bekliyor Büyük köprünün hemen yakınında Neretva'ya |
| birlikteydi | birlikte | 1 | görmek belki onları şaşırtıyordu ama kültür bu birlikteydi Hacı Zayim Mehmet Bey denince kimse bilmez | uğraştılar beni İşte yaşıyorum Bu evde hanımla birlikte kalıyoruz Bu evin tarihi geçmişi çok eski |
| Zayim | Zahim | 1 | onları şaşırtıyordu ama kültür bu birlikteydi Hacı Zayim Mehmet Bey denince kimse bilmez Onu herkes | onları şaşırtıyordu ama kültür bu birlikte Hacı Zahim Mehmet Bey denilince kimse bilmez Onu herkes |
| denince | denilince | 1 | kültür bu birlikteydi Hacı Zayim Mehmet Bey denince kimse bilmez Onu herkes Karagöz Mehmet Bey | kültür bu birlikte Hacı Zahim Mehmet Bey denilince kimse bilmez Onu herkes Karagöz Mehmet Bey |
| öğerlerdi | överlerdi | 1 | bina kesme taştandır Mostarlılar bu camiyi pek öğerlerdi Emsali olmayan bir eser gibi anlatırlardı Son | bina kesme taştandır Mostarlılar bu camiyi pek överlerdi Emsali olmayan bir eser gibi anlatırlardı Son |
| bilmiyor | biliniyor | 1 | işgali sırasında bu bezemelerle ne kadar oynandığı bilmiyor Savaşın cami ve bilhassa kubbesinde meydana getirdiği | işgali sırasında bu bezemelerle ne kadar oynandığı biliniyor Savaşın cami ve bilhassa kubbesinde meydana getirdiği |
| de | camiinde | 1 | kurulardan beri burada oturur benim ailem Belki de onlar kurdular burada Yalnız soyumun Türkiye'den gelme | avluları yoktur İşte Karagöz Bey'in yaptırdığı bu camiinde dar bir dış avlusu vardır Kapısı köşededir |
| Çanının | Çanunun | 1 | hanım yaptırmış 300 yıldan fazla olsa gerek Çanının sesinin pek uzaklardan duyulduğu anlatılır hep Nasu | hanım yaptırmış 300 yıldan fazla olsa gerek Çanunun sesinin pek uzaklardan duyulduğu anlatılır hep Nasu |
| Mostar'ın | Mosler'in | 1 | mezar taşları vardı Şadırvanı da halen kullanılıyor Mostar'ın sembol eserlerinden Bişeviş Köşkü Sahipleri Ahmet Bey | Nasu Ağa Camii meydanı dolduran eserlerden biri Mosler'in güzelliklerinden Savaşın ne feci ne çirkin olduğunun |
| peki | iyimser | 1 | yapılmış şiirler dizilmiş Gelecek neler getirecek bilmiyorum peki imserde değilim ama gençler çok iyi düşünüp | şiirler dizilmiş Gelecek neler getirecek bilmiyorum pek iyimser de değilim Ama gençler çok iyi düşünüp |
| imserde | de | 1 | şiirler dizilmiş Gelecek neler getirecek bilmiyorum peki imserde değilim ama gençler çok iyi düşünüp bu | kurulalıdan beri burada oturur benim ailem Belki de onlar kurdular burayı Yalnız soyumun Türkiye'den gelme |
| beldeyi | perdeyi | 1 | gençler çok iyi düşünüp bu dünya güzeli beldeyi yeniden yaşanır kılmalıdır Eskiden köprüden atlama yarışları | gençler çok iyi düşünüp bu dünya güzeli perdeyi yeniden yaşanır kılmalıdır Eskiden köprüden atlama yarışları |
| vardı | bizden | 1 | akarmış Zaten üzerinde pek çok su değerinin vardı İşte burada Büyük köprünün denemesini yapmışlar Adı | kültür eserleri yok edildi İnsanın aklının alacağı bizden Mostarımızın sembolü tarihi köprü gitti yok oldu |
| kararındaydılar | kararındaydı | 1 | hatırlatan sembolize eden her şeyi yok etme kararındaydılar Savaş öncesi hırvatlar burada yüzde on civarındaydı | hatırlatan sembolize eden her şeyi yok etme kararındaydı Savaş öncesi ırvatlar burada yüzde on civarındaydı |
| hırvatlar | ırvatlar | 1 | yada Eski Sırp kilisesiydi Sırplar bir yandan hırvatlar bir yandan Müslümanları ortada kıstırmışlardı Fakat hani | her şeyi yok etme kararındaydı Savaş öncesi ırvatlar burada yüzde on civarındaydı Şimdi bakınız nasıl |
| çalışıyorum | çalışılıyor | 1 | on civarındaydı Şimdi bakınız nasıl kimlik değiştirmeye çalışıyorum İnanın ben tamamen objektifim Yani ne saçma | yapılar onarıldıkça çatıları da eski haline getirilmeye çalışılıyor Kaygan kaya çatı örtüsü Bu havalide sıkça |
| başkalarıyla | ile | 1 | ne de haklı çıkmak için konuşuyorum Hem başkalarıyla da konuşacaksınız Zaten burası kimindir sorusunun cevabı | de haklı çıkmak için konuşuyorum Hem başkaları ile de konuşacaksınız Zaten burası kimindir sorusunun cevabı |
| Yollarım | Kullarım | 1 | vatanında sığıntı olmak Ne harcı günlerdi Tanrım Yollarım halen İsviçre'de Geriye Mostar'a dönmeyi istiyorlar ama | vatanında sığıntı olmak Ne acı günlerdi tanrım Kullarım halen İsviçre'de Geriye Mostar'a dönmeyi istiyorlar ama |
| Hırvatlısı | Sırp | 1 | bir sistem getirildi ki işlemez halde Müslüman Hırvatlısı karma yönetimi Güçlü topraklar bile üçe ayrılmış | ne çirkin olduğunun misallerinden şu yapı Eski Sırp kilisesiydi Sırplar bir yandan Hırvatlar bir yandan |
| Güçlü | Üçlü | 1 | ki işlemez halde Müslüman Hırvatlısı karma yönetimi Güçlü topraklar bile üçe ayrılmış gibi Mutlu muyuz | işlemez halde Müslüman Hırvat Sırp Karma yönetimi Üçlü Topraklar bile üçe ayrılmış gibi Mutlu muyuz |
| günün | oyunun | 1 | ki Sanki bir oyun oynuyoruz Bakalım o günün sonu nasıl olacak | değil ki Sanki bir oyun oynuyoruz Bakalım oyunun sonu nasıl olacak |

### İfade Seviyesi Ek/Fazla Parçalar

| Taraf | Metin |
|---|---|
| fast_extra | bir saygı |

## Meraklı Momolar

- Fast kelime: 1199
- Quality kelime: 1227
- Yer değiştirme: 49
- Fast fazladan kelime: 7
- Quality fazladan kelime: 35

| Fast | Quality | Adet | Fast bağlam | Quality bağlam |
|---|---|---:|---|---|
| Sanada | da | 2 | gün Ne güzel bir gün Herkese merhaba Sanada Merhaba Sanada Sapsi sana da merhaba Tapçi | Ne güzel bir gün Herkese merhaba Sana da merhaba Sana da Sapsi sana da merhaba |
| Roscoe'nun | Rosco'nun | 2 | Amorosko ayrıca özel kedi maması da yiyor Roscoe'nun evde kalması için eğitilmesi gerekiyor Tuvalet için | Rosco ayrıca özel kedi maması da yiyor Rosco'nun evde kalması için eğitilmesi gerekiyor Tuvalet için |
| Pemi'cim | Pemiciğim | 1 | Ne besleyeceğimi buldum Buldun mu Sağ ol Pemi'cim Senin sayende buldum Benim sayende mi buldun | Ne besleyeceğimi buldum Buldun mu Sağ ol Pemiciğim Senin sayende buldum Benim sayende mi buldum |
| buldun | buldum | 1 | beslesen Ne beslesen Buldum Ne besleyeceğimi buldum Buldun mu Sağ ol Pemi'cim Senin sayende buldum | görünce çığlık atmaz Ben tırtıla dokunamam ki Buldum Ay hep beslemek istemişimdir bunu Ama nasıl |
| Fekri | Fikri | 1 | Hoşçakal Çok merak ettim Hep böyle oluyor Fekri ben veriyorum ama Bulduklarında bana söylemiyorlar Bir | Ya çok merak ettim Hep böyle oluyor Fikri ben veriyorum ama bulduklarında bana söylemiyorlar Bir |
| Sapsa | Sapsın | 1 | beni Beni de bekleyin ben de geliyorum Sapsa Sapsi sana sesleniyorum Aa duymamışım seni mom | beni Beni de bekleyin ben de geliyorum Sapsın Sapsi sana sesleniyorum Aa duymamışım seni mom |
| sonrayı | sonra | 1 | içerim galiba Kurabiyeler beni su sattı Biraz sonrayı sormuyorum canım Şimdi ne yapmayı düşünüyorsun Şimdi | parmaklarımı yiyecektim Parmaklarını mı yiyecektin Sakın ha Sonra ne yaparsın parmaksız parmaksız Demi Porti kurabiyeleri |
| kaçtığını | kaçtığımı | 1 | mom Tıka basa doydum Sapsi ellerini yıkamaktan kaçtığını düşünüyorum Doğru mu Aa neden kaçayım mom | mom Tıka basa doydum Sapsi ellerini yıkamaktan kaçtığımı düşünüyorum Doğru mu Aa Neden kaçayım Moğol |
| mom | Moğol | 1 | ne kadar iştahlısınız böyle İştahlı ne demek Mom Bugün çok yiyorsunuz demek Bir tepsi kurabiyenin | kaçtığımı düşünüyorum Doğru mu Aa Neden kaçayım Moğol Ben de şimdi yıkayacaktım Tabii Ben de |
| zamana | zamanı | 1 | Neyse biraz sonra anlarız nasılsa Şimdi özgü zamana Kafam kaşınıyor Arda'ya sordum Kaşı o zaman | kimsenin aklına bir şey getirmeyeceğim Şimdi şarkı zamanı Bugün ne kadar iştahlısınız böyle İştahlı ne |
| tertemiz | tertibiz | 1 | gerekiyormuş İnsan vücudunda böcekler yaşamazmış Oh ellerim tertemiz oldu Hem de mis gibi kokuyor Ne | gerekiyormuş İnsan vücudunda böcekler yaşamazmış Oh ellerim tertibiz oldu Hem de mis gibi kokuyor Ne |
| mom | Mum | 1 | kurabiyenin kırıntısını bile bırakmadınız Kırıntıları ne yapacaktın Mom Kuşlara mı atacaktın Hayır onun için söylemedim | görmüş olamazsın değil mi I ıh hayır Mum Tamam Eee Sapsi ellerini yıkadın mı Şey |
| Eee | Ne | 1 | görmüş olamazsın değil mi Hayır Mum Tamam Eee Sapsi ellerini yıkadın mı Şey Lütfen doğruyu | hayran olur bayılır kuzucuklar taze çimen ararlar Ne güzel bir gün Ne güzel bir gün |
| dememom | Mom | 1 | mi Evet Bitlerin mi yani Onlara bit dememom Alınıyorlar Onların da adı var Başında bitmeme | ne kadar iştahlısınız böyle İştahlı ne demek Mom Bugün çok yiyorsunuz demek Bir tepsi kurabiyenin |
| Dur | durun | 1 | hemen bulaştırmalıyım Bulaştırmalıyım mı dedim Bulmalıyım diyecektim Dur gitme merak ettim Hoşçakal Çok merak ettim | da adı var Başında bitmeme istiyorsun yani Durun durun durun durun durun Sakin olun Hepimiz |
| 6 | altı | 1 | kedinin iki tane yavrusu oldu Yavrular şimdi 6 aylık Yani anne kedinin onları yalnız bırakabileceği | kedinin iki tane yavrusu oldu Yavrular şimdi altı aylık Yani anne kedinin onları yalnız bırakabileceği |
| Rosko | Roscoe | 1 | anne kedinin onları yalnız bırakabileceği kadar büyüdüler Rosko artık kendi başına yemek yemeli Günde dört | kedilerden birini alabilir O da Roscoe'yi seçiyor Roscoe artık kendi başına yemek yemeli Günde dört |
| Amorosko | Rosco | 1 | defa Önce Laura ona biraz süt veriyor Amorosko ayrıca özel kedi maması da yiyor Roscoe'nun | Önce Laura ona biraz süt veriyor Ama Rosco ayrıca özel kedi maması da yiyor Rosco'nun |
| Catbox | box | 1 | evde kalması için eğitilmesi gerekiyor Tuvalet için Catbox kullanması gerekir Bu bir kedi tuvaleti Catbox'ın | kalması için eğitilmesi gerekiyor Tuvalet için cat box kullanması gerekir Bu bir kedi tuvaleti Cat |
| Catbox'ın | box'ın | 1 | Catbox kullanması gerekir Bu bir kedi tuvaleti Catbox'ın içi kedi kumu denilen bir çeşit kumla | kullanması gerekir Bu bir kedi tuvaleti Cat box'ın içi kedi kumu denilen bir çeşit kumla |
| kopması | kapması | 1 | bir çeşit kumla dolduruluyor Böylece evin kutu kopması engellemiş oluyor Laura Roscoe ile oynamayı çok | bir çeşit kumla dolduruluyor Böylece evin kutu kapması engellenmiş oluyor Laura Rosco ile oynamayı çok |
| engellemiş | engellenmiş | 1 | çeşit kumla dolduruluyor Böylece evin kutu kopması engellemiş oluyor Laura Roscoe ile oynamayı çok seviyor | çeşit kumla dolduruluyor Böylece evin kutu kapması engellenmiş oluyor Laura Rosco ile oynamayı çok seviyor |
| Roscoe | Rosco | 1 | Böylece evin kutu kopması engellemiş oluyor Laura Roscoe ile oynamayı çok seviyor Ve tüm kediler | Böylece evin kutu kapması engellenmiş oluyor Laura Rosco ile oynamayı çok seviyor Ve tüm kediler |
| götürmeniz | getirmemiz | 1 | yerleri keşfediyor Yavru kedileri doktora yani veterinere götürmeniz gerekir veteriner Jack Rusköy'ü görecek Rosco'nun sağlığı | yerleri keşfediyor Yavru kedileri doktora yani veterinere getirmemiz gerekir Veteriner Jacques Roske'yi görecek Rosko'nun sağlığı |
| Jack | Jacques | 1 | kedileri doktora yani veterinere götürmeniz gerekir veteriner Jack Rusköy'ü görecek Rosco'nun sağlığı çok iyi ama | kedileri doktora yani veterinere getirmemiz gerekir Veteriner Jacques Roske'yi görecek Rosko'nun sağlığı çok iyi ama |
| Rusköy'ü | Roske'yi | 1 | doktora yani veterinere götürmeniz gerekir veteriner Jack Rusköy'ü görecek Rosco'nun sağlığı çok iyi ama yine | doktora yani veterinere getirmemiz gerekir Veteriner Jacques Roske'yi görecek Rosko'nun sağlığı çok iyi ama yine |
| Rosco'nun | Rosko'nun | 1 | veterinere götürmeniz gerekir veteriner Jack Rusköy'ü görecek Rosco'nun sağlığı çok iyi ama yine de bu | veterinere getirmemiz gerekir Veteriner Jacques Roske'yi görecek Rosko'nun sağlığı çok iyi ama yine de bu |
| iğnede | de | 1 | kurtlardan kurtulmuş olacak Ayrıca hastalanmasını önlemek için iğnede oluyor Roscoe'nun mırıldandığını duyuyor musunuz Bu çok | ellerimde hiç kırıntı yok Olsun Bence yine de yıkamalısınız Parmaklarınız yağlanmıştır Yıkamazsak ne olur Mom |
| Rosco | Roscoe | 1 | odalarına girmeleri yasaktır Ama bazen Laura ve Rosco kurallara uymuyorlar Ne var Başın kaşınıyor mu | odalarına girmeleri yasaktır Ama bazen Laura ve Roscoe kurallara uymuyorlar Ne var Başın kaşınıyor mu |
| kalacak | oldu | 1 | Başın kaşınıyor mu Anam çok güzel mi kalacak Yok yok herhalde bana öyle geldi Ben | İnsan vücudunda böcekler yaşamazmış Oh ellerim tertibiz oldu Hem de mis gibi kokuyor Ne güzel |
| Vallahi | Anam | 1 | bugün Bitler'le çok uğraştım da ondan herhalde Vallahi ne yapacak Evet Bitler Şuna bak söyleyince | kurallara uymuyorlar Ne var Başın kaşınıyor mu Anam ne oldu Yok yok herhalde bana öyle |
| yapacak | korkuyorum | 1 | çok uğraştım da ondan herhalde Vallahi ne yapacak Evet Bitler Şuna bak söyleyince bile kaşınıyorum | ondan herhalde Anam ne oldu Ben çok korkuyorum Evet bitler Şuna bak söyleyince bile kaşınıyorum |
| dememom | mom | 1 | bitlerin beslenebilecek hayvanlar olduğunu zannetmiş Onlara bit dememom Alınıyorlar Onların da adı var Başında bitme | ne kadar iştahlısınız böyle İştahlı ne demek Mom Bugün çok yiyorsunuz demek Bir tepsi kurabiyenin |
| Korşularının | Koşularının | 1 | besliyorsun yani Durun ya Nereden mi bulmuş Korşularının çocuğu bitlenmiş O da onun tokasını takmış | bitme besliyorsun yani Durun Nereden mi bulmuş Koşularının çocuğu bitlenmiş O da onun tokasını takmış |
| 34347 | 4347 | 1 | de TRT İstanbul Televizyonu Meraklı Momolar Programı 34347 Ortakey İstanbul Möraklimamolar Et dere dere nokta | de TRT İstanbul televizyonu Meraklı Momolar programı 4347 Ortaki İstanbul Merakli momolar et trt net |
| Ortakey | Ortaki | 1 | TRT İstanbul Televizyonu Meraklı Momolar Programı 34347 Ortakey İstanbul Möraklimamolar Et dere dere nokta net | TRT İstanbul televizyonu Meraklı Momolar programı 4347 Ortaki İstanbul Merakli momolar et trt net tr |
| Et | Merakli | 1 | Meraklı Momolar Programı 34347 Ortakey İstanbul Möraklimamolar Et dere dere nokta net nokta dere Meraklı | Meraklı Momolar başlıyor Mama buna hayran olur bayılır |
| dere | momolar | 1 | Momolar Programı 34347 Ortakey İstanbul Möraklimamolar Et dere dere nokta net nokta dere Meraklı Momolar | Meraklı Momolar başlıyor Mama buna hayran olur bayılır kuzucuklar |

### İfade Seviyesi Ek/Fazla Parçalar

| Taraf | Metin |
|---|---|
| quality_extra | Laura yavru kedilerden birini alabilir O da Roscoe'yi seçiyor |
| quality_extra | Meraklı Momolar başlıyor |
| quality_extra | Durun durun durun |
| quality_extra | oldu Ben çok |
| quality_extra | Ah E |
| quality_extra | I ıh |
| fast_extra | çok güzel |
