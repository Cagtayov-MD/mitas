# v7 vs v11 - Raw Tam Transcript İncelemesi

Bu dosyada **tam çıktı**, `raw_segments.json` içindeki bütün segmentlerin birleştirilmiş halidir. Yani `clean_transcript.txt` filtresi uygulanmamıştır.

Önemli not: Önceki `clean` kıyasında bazı v7 konuşmaları `no_speech_prob > 0.6` filtresi yüzünden düşmüş görünüyordu. Bu rapor o yanılgıyı düzeltmek için filtre öncesi raw metni gösterir.

## Özet Tablo

| Klip | Mod | Pencere | v7 raw words | v7 drop | v11 raw words | v11 drop | Kısa not |
|---|---|---|---:|---:|---:|---:|---|
| `1.mp4` | `full_fallback_shorter_than_3min` | `0.000-171.680s` | 37 | 3 | 28 | 0 | v11 artifact: Abone olmayı, Altyazı |
| `2.mp4` | `requested_03_05` | `180.000-300.000s` | 159 | 26 | 161 | 0 | v11 uzun token riski: max_token_length=223 |
| `3.mp4` | `requested_03_05` | `180.000-300.000s` | 24 | 1 | 24 | 0 | v7 clean filtresi konuşma düşürebilir |
| `4.mp4` | `requested_03_05` | `180.000-300.000s` | 8 | 1 | 9 | 0 | v11 artifact: Altyazı |
| `5.mp4` | `requested_03_05` | `180.000-300.000s` | 216 | 0 | 217 | 0 | yakın / manuel dinleme gerekir |
| `beyaz1.mp4` | `requested_03_05` | `180.000-300.000s` | 297 | 24 | 685 | 0 | v11 tekrar riski: max_run=444 |
| `trt_haber (1).mp4` | `full_requested` | `0.000-95.660s` | 141 | 1 | 139 | 0 | v11 artifact: İzlediğiniz için teşekkür ederim |
| `trt_haber (2).mp4` | `full_requested` | `0.000-146.744s` | 256 | 0 | 240 | 0 | yakın / manuel dinleme gerekir |
| `trt_haber (3).mp4` | `full_requested` | `0.000-75.452s` | 135 | 0 | 134 | 0 | yakın / manuel dinleme gerekir |

## 1.mp4

- Source: `E:\MITAS\testklipler\1.mp4`
- Mode: `full_fallback_shorter_than_3min`
- Window: `0.000-171.680s`
- Not: Bu dosya 3 dakikadan kısa olduğu için istenen 03:00-05:00 aralığı yok; tam klip kullanıldı.

### v7 tam çıktı - filtre öncesi raw

- Raw segment: `7`
- Clean segment: `4`
- Drop: `3` / `{'no_speech': 3}`
- Word count raw: `37`
- Total seconds: `13.374`
- Uyarı: artifacts=['İzlediğiniz için teşekkür ederim'], max_run=2, max_token_length=16

```text
Günaydın sevgili dinleyicilerimiz saatimiz 7'yi gösteriyor.

İzlediğiniz için teşekkür ederim. Nazan babanın kucağına gideceksin inşallah.

Hiçbir şeyde gözüm yok

Arda cezanın içi Arda Arda dök Selçuk'u vur gerisinde Selçuk geliyor vuruyor Vur Selçuk geliyor vuruyor
```

### v11 tam çıktı - filtre öncesi raw

- Raw segment: `5`
- Clean segment: `5`
- Drop: `0` / `{}`
- Word count raw: `28`
- Total seconds: `11.742`
- Uyarı: artifacts=['Abone olmayı', 'Altyazı'], max_run=1, max_token_length=16

```text
Günaydın sevgili dinleyicilerimiz. Saatimiz 7'yi gösteriyor.

Abone olmayı, yorum yapmayı ve beğen butonuna tıklamayı unutmayın. azdan babanın kucağına gideceksin inşallah Hiçbir şeyde gözüm yok

Altyazı M.K.
```

## 2.mp4

- Source: `E:\MITAS\testklipler\2.mp4`
- Mode: `requested_03_05`
- Window: `180.000-300.000s`

### v7 tam çıktı - filtre öncesi raw

- Raw segment: `35`
- Clean segment: `9`
- Drop: `26` / `{'no_speech': 26}`
- Word count raw: `159`
- Total seconds: `35.743`

```text
kötü olmasının matematiksel bir açıklaması olabilir. Allah razı olsun. Teşekkür ederim.

Ben Nils'in. Sembol kriptolojisinden. Nils bir Japon şifresini çözdü. Dünyayı faşizmden kurtardı. Merhaba. En azından kızları öyle diyor. Değil mi Nils? Adım Bender. Atom fizikçisiyim. Nasılsın? Geç mi kaldın? Evet. Evet Bay Sol. İyiyim. Merhaba. Ben Sol. Richard Sol. Merhaba. Deha'nın ağırlığı. Öyle çok naranma, öyle asıl mal var ki Bay Sol. Bender. Teşekkür ederim. Seni de sevmek çok güzel. Teşekkür ederim. Anlayamadım Affedersin seni garson zannettim Biraz kibar ol Ensın Ensın kibarlıktan anlamaz Evet Martin Ensın Adın Martin'di değil mi? Evet John, adım Martin. Yanlış hesaplar yapmak sende alışkanlık haline gelmiş. Makalelerini okumuştum. İkisini de, nazi şifreleri üzerine olanı ve doğrusal olmayan denklemler hakkında yazdığını, her ikisinde de ne ufuk açan ne de yenilik getiren tek bir fikir bile olmadığından son derece eminim. Afiyet olsun.

Beyler, John Nash ile tanışın. Batı Virjinalı, Esra Ringiz dahi. Seçkin Carnegie Bursunu kazanan diğer adam. Tamam. Tabii ki.
```

### v11 tam çıktı - filtre öncesi raw

- Raw segment: `45`
- Clean segment: `45`
- Drop: `0` / `{}`
- Word count raw: `161`
- Total seconds: `14.418`
- Uyarı: artifacts=[], max_run=2, max_token_length=223

```text
kötü olmasının matematiksel bir açıklaması olabilir. Hıhıhıhıhıhıhıhıhıhıhıhıhıhıhıhıhıhıhıhıhıhıhıhıhıhıhıhıhıhıhıhıhıhıhıhıhıhıhıhıhıhıhıhıhıhıhıhıhıhıhıhıhıhıhıhıhıhıhıhıhıhıhıhıhıhıhıhıhıhıhıhıhıhıhıhıhıhıhıhıhıhıhıhıhıhıhıhıhıhıhıhıhıhıhıhıhıhıhıhıhıhıhıhıhıhıhıhıhıhıhıh Teşekkür ederim.

Ben Nils'in. Sembol kriptolojisinden. Nils bir Japon şifresini çözdü. Dünyayı faşizmden kurtardı. En azından kızları öyle diyor. Değil mi Nils? Adım Bender. Atom fizikçisiyim. Nasılsın? Geç mi kaldın? Evet. Evet Bay Sol. Tamam. İyiyim. Merhaba. Ben Sol. Richard Sol. Merhaba. Dehanın ağırlığı. Öyle çok. İşte geldim. Nasılsın? Var ki Bay Sol. Bender. Seni görmek ne güzel. Seni de sevmek çok güzel. Teşekkür ederim. Anlayamadım Affedersin seni garson zannettim Biraz kibar ol Ensign Ensign kibarlıktan anlamaz mı? Sıra bakma Evet Martin Ensign Adın Martin'di değil mi? Evet John, adın Martin. Yanlış hesaplar yapmak sende alışkanlık haline gelmiş. Makalelerini okumuştum. İkisini de Nazi şifreleri üzerine olanı ve doğrusal olmayan denklemler hakkında yazdığını. Her ikisinde de ne ufuk açar ne de yenilik getiren tek bir fikir bile olmadığından son derece eminim. Afiyet olsun.

Beyler, John Nash ile tanışın. Batı Virginalı, Esra Rengiz dahi. Seçkin Carnegie bursunu kazanan diğer adam. Aynen. Tamam. Tabii ki.
```

## 3.mp4

- Source: `E:\MITAS\testklipler\3.mp4`
- Mode: `requested_03_05`
- Window: `180.000-300.000s`

### v7 tam çıktı - filtre öncesi raw

- Raw segment: `8`
- Clean segment: `7`
- Drop: `1` / `{'no_speech': 1}`
- Word count raw: `24`
- Total seconds: `9.801`

```text
Baba, lütfen yanlış çıkışa girdiğini söyle.

Boya dükkanı. Yarın ilk iş. Bir boya dükkanı varsa tabii. Julie. Ne? Hadi gidip odanızı bulalım kızlar. Hadi.
```

### v11 tam çıktı - filtre öncesi raw

- Raw segment: `7`
- Clean segment: `7`
- Drop: `0` / `{}`
- Word count raw: `24`
- Total seconds: `6.904`

```text
Baba, lütfen yanlış çıkışa girdiğini söyle.

Boya dükkanı. Yarın ilk iş. Bir boya dükkanı varsa tabii. Julie. Ne? Hadi gidip odanızı bulalım kızlar. Hadi.
```

## 4.mp4

- Source: `E:\MITAS\testklipler\4.mp4`
- Mode: `requested_03_05`
- Window: `180.000-300.000s`

### v7 tam çıktı - filtre öncesi raw

- Raw segment: `2`
- Clean segment: `1`
- Drop: `1` / `{'low_logprob': 1}`
- Word count raw: `8`
- Total seconds: `9.476`
- Uyarı: artifacts=['İzlediğiniz için teşekkür ederim'], max_run=1, max_token_length=11

```text
İzlediğiniz için teşekkür ederim. Ağabey, peşiniz göğe at.
```

### v11 tam çıktı - filtre öncesi raw

- Raw segment: `3`
- Clean segment: `3`
- Drop: `0` / `{}`
- Word count raw: `9`
- Total seconds: `6.899`
- Uyarı: artifacts=['Altyazı'], max_run=1, max_token_length=7

```text
Altyazı M.K. Altyazı M.K. Altyazı M.K.
```

## 5.mp4

- Source: `E:\MITAS\testklipler\5.mp4`
- Mode: `requested_03_05`
- Window: `180.000-300.000s`

### v7 tam çıktı - filtre öncesi raw

- Raw segment: `15`
- Clean segment: `15`
- Drop: `0` / `{}`
- Word count raw: `216`
- Total seconds: `24.044`

```text
Köprü bu şekilde sabit kalıyor. İki kulesinin suyun üzerinde birbirine olan 2023 metrelik uzaklığı onu dünyanın en uzun orta açıklıklı köprüsü yapıyor. Peki ama mühendisliğin sınırlarını tam anlamıyla zorlayacak bir köprü nasıl planlanır?

Gerçekten çok ihtişamlı. Buradan bakınca kendimin ne kadar küçük olduğunu hissettim. Evet köprü gerçekten çok büyük ama inan yapım amacı çok çok daha büyük. Daha önce çok geçtim. Özellikle bayramlarda. Feribotla saatlerce beklediğim oldu. Bu sürenin kısalacak olması çok güzel. Bu amaçladığımız faydalardan sadece bir tanesi. Asıl master plan ve karayolları genel müdülünü buna bağlı olarak... Mega projesi Marmara bölgesinin etrafını otoyol ringiyle dönmek, bütün buradaki mevcut olan veya sonradan otoyol imalatı tamamlandıktan sonra yapılacak olan organize sanayi bölgeleri, limanlar, havalimanları, tren garlarının tamamının birbirine olan entegrasyonunu sağlamak ve üretimi desteklemek. Pekin'den Londra'ya kadar uzanan modern ipek yolu diyebileceğimiz ve tüm dünya ticaretini ilgilendiren bir güzergah oluşuyor. İşte Çanakkale Boğazı da bu güzergahın kilit noktasında yer alıyor. Hem Doğu ülkelerinin Anadolu üzerinden Avrupa'ya geçişinde hem de Türkiye sınırları içindeki karayolu bağlantısıyla 1915 Çanakkale Köprüsü dev bir ağın en önemli parçası. Yani bu köprüyle birlikte doğu batı arası en uzak noktalarda Türkiye'nin de dahil olduğu ithalat ve ihracat karayolu üzerinden yapılabilecek. Fakat böyle bir karayolu ağının Çanakkale Boğazı'ndan geçecek olması köprünün nerede konumlanacağı ile ilgili soruları da beraberinde getiriyor.
```

### v11 tam çıktı - filtre öncesi raw

- Raw segment: `13`
- Clean segment: `13`
- Drop: `0` / `{}`
- Word count raw: `217`
- Total seconds: `10.746`

```text
Bu köprü bu şekilde sabit kalıyor. İki kulesinin suyun üzerinde birbirine olan 2023 metrelik uzaklığı onu dünyanın en uzun orta açıklıklı köprüsü yapıyor. Peki ama mühendisliğin sınırlarını tam anlamıyla zorlayacak bir köprü nasıl planlanır?

Gerçekten çok ihtişamlı. Buradan bakınca kendimin ne kadar küçük olduğunu hissettim. Evet köprü gerçekten çok büyük ama inan yapım amacı çok çok daha büyük. Daha önce çok geçtim. Özellikle bayramlarda. Feribotla saatlerce beklediğim oldu. Bu sürenin kısalacak olması çok güzel. Bu amaçladığımız faydalardan sadece bir tanesi. Asıl master plan ve karayolları genel müdürünün buna bağlı olarak... Mega projesi Marmara bölgesinin etrafını otoyol ringiyle dönmek, bütün buradaki mevcut olan veya sonradan otoyol imalatı tamamlandıktan sonra yapılacak olan organize sanayi bölgeleri, limanlar, havalimanları, tren garların tamamının birbirine olan entegrasyonunu sağlamak ve üretimi desteklemek. Pekin'den Londra'ya kadar uzanan modern ipek yolu diyebileceğimiz ve tüm dünya ticaretini ilgilendiren bir güzergah oluşuyor. İşte Çanakkale Boğazı da bu güzergahın kilit noktasında yer alıyor. Hem Doğu ülkelerinin Anadolu üzerinden Avrupa'ya geçişinde hem de Türkiye sınırları içindeki karayolu bağlantısıyla 1915 Çanakkale Köprüsü dev bir ağın en önemli parçası. Yani bu köprüyle birlikte Doğu-Batı arası en uzak noktalarda Türkiye'nin de dahil olduğu ithalat ve ihracat karayolu üzerinden yapılabilecek. Fakat böyle bir karayolu ağının Çanakkale Boğazı'ndan geçecek olması köprünün nerede konumlanacağı ile ilgili soruları da beraberinde getiriyor.
```

## beyaz1.mp4

- Source: `E:\MITAS\testklipler\beyaz1.mp4`
- Mode: `requested_03_05`
- Window: `180.000-300.000s`

### v7 tam çıktı - filtre öncesi raw

- Raw segment: `41`
- Clean segment: `17`
- Drop: `24` / `{'no_speech': 24}`
- Word count raw: `297`
- Total seconds: `28.744`

```text
Konusu ne filmin? Grafik inanılmaz iniş çıkışlı. Konusu şu an pek anlatmak istemiyorum işin açıkçası. Sürpriz olsun. Peki o kadar çok dizi film varken piyasada böyle bir ürk mü ediniz mi ya? Yani biz de bir film yapıyoruz arada gerçi tabii herkesin aksiyonu farklı, karizması farklı kendine güveniyorsan tabii ki yaparsın tutulur da. Ama bu dönemde çok fazla film var hiç böyle bir ürküntü falan gelmedi mi? Şimdi Beyaz bundan 4 sene önce de bana dizi teklifi geliyordu. Evet. Benim için dizi teklifi bana dizi teklifi edilmesi çok cazip geliyordu bana. Evet. Gözümde dizi güzel bir şeydi. Yapmak istediğim bir projeydi. Bu ama dizi film değil hala. Bu sinema filmi. Şu an sinema. Yalnız filmin konusu dizi olarak devam edecek. Anladım. Dizi başka bir konuyla devam etmiyor. Aynı kadro, aynı konu.

Esin peki senin daha önce bir sinema deneyimi var mıydı? Bir tane 90 yılında var. Tatar Ramazan isimli bir sinema filmim olmuştu. Ramazan'ı oynamıyordun. Tatar'ı oynamıyordun. Ne oynuyordun? Tatar kızını oynuyordum. Tatar kızını oynuyordun. Var mı tatarlık ailede? Hiç yok. Hayır. Yok. Göçmenlik var mı? Gözler mavi çünkü. var yani göçmen sayesinde yarımadası'na gelmiş atalarımız moralı oğlu soy ismi oradan kaynakları zaten Karaferya Selanik moralı oğullar gelmiş Ege'ye yerleşmişler göçmenlik yok ama Tatar kızına benzemek için o dönemde 7 kilo filan almıştım Karakaşlar Tatar kızları da güzel olur güzel olur hakikaten var mı aramızda Tatar kızı

Evet Sevim Aval Ankara'dan aramış Telefonumuzda bekliyor Alo Sevim Hanım iyi akşamlar iyi geceler İyi geceler Teşekkür ederim iyiyim sizler nasılsınız Çok teşekkür ederiz biz de iyiyiz Arkadaşlarla oturduk sohbet ediyoruz Var mı söylemek istediğiniz sormak istediğiniz bir şeyler Öncelikle Beyaz programını çok severek Ama çok severek ve beğenerek izliyorum Sağolun teşekkür ederiz Artık programın hep böyle sürmesini istiyorum İnşallah Önce sana bir sorum var
```

### v11 tam çıktı - filtre öncesi raw

- Raw segment: `44`
- Clean segment: `44`
- Drop: `0` / `{}`
- Word count raw: `685`
- Total seconds: `21.736`
- Uyarı: artifacts=['İzlediğiniz için teşekkür ederim'], max_run=444, max_token_length=13

```text
Konusu ne filmin? Grafik inanılmaz. Konusu şu an pek anlatmak istemiyorum. Sürpriz olsun. Peki o kadar çok dizi film varken piyasada böyle bir ürkmediniz mi? Yani biz de bir film yapıyoruz. Gerçi tabii herkesin aksiyonu farklı, karizması farklı. Kendine güveniyorsan tabii ki yaparsın. Ama bu dönemde çok fazla film var. Hiç böyle bir ürküntü falan gelmedi mi? Şimdi Beyaz bundan 4 sene önce de bana dizi teklifi geliyordu. Benim için bana dizi teklif edilmesi çok cazip geliyordu bana. İzlediğiniz için teşekkür ederim. Gözümde dizi güzel bir şeydi, yapmak istediğim bir projeydi. Bu ama dizi film değil hala, bu sinema filmi. Şu an sinema, yalnız filmin konusu dizi olarak devam edecek. Anladım. Dizi başka bir konuyla devam ediyor. Aynı kadro, aynı konu.

Esin peki senin daha önce bir sinema deneyimin var mıydı? Bir tane 90 yılında var, Tatar Ramazan isimli bir sinema filmi olmuştu. Ramazan'ı oynamıyordun, Tatar'ı oynamıyordun. Tatar kızını oynuyordun. Tatar kızını oynuyordun. Var mı Tatarlık ailede? Hiç yok, hayır. Yok, göçmenlik var mı? Gözler mavi çünkü. Yenek. Yenek. Ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben ben Evet Sevim Aval Ankara'dan aramış telefonumuzda bekliyor hatımızda. Alo Sevim Hanım iyi akşamlar iyi geceler. İyi geceler. Nasılsınız? Teşekkür ederim iyiyim sizler nasılsınız? Çok teşekkür ederiz bizler de iyiyiz. Arkadaşlar da oturduk sohbet ediyoruz. Var mı söylemek istediğiniz sormak istediğiniz bir şeyler? Öncelikle Beyaz programını çok severek ama çok severek ve beğenerek izliyorum. Sağ olun teşekkür ederiz. Artık programının hep böyle sürmesini istiyorum. İnşallah. Önce sana bir sorum var.
```

## trt_haber (1).mp4

- Source: `E:\MITAS\testklipler\trt_haber (1).mp4`
- Mode: `full_requested`
- Window: `0.000-95.660s`

### v7 tam çıktı - filtre öncesi raw

- Raw segment: `10`
- Clean segment: `9`
- Drop: `1` / `{'no_speech': 1}`
- Word count raw: `141`
- Total seconds: `18.857`
- Uyarı: artifacts=['İzlediğiniz için teşekkür ederim'], max_run=2, max_token_length=19

```text
Tüm hazırlıklar tamamlandı. P-16'lar Eskişehir 1. Anajet Üssü'nden havalandı.

Eskişehir'de F-16 pilotlarının İzmir'de gerçekleştirilen EFES 2026 tatbikatı için hazırlıklarını TRT Haber ekibi görüntüledi. Pilotlar gökyüzünde karşılışacakları G kuvvetine karşı ekipmanlarını giyip hangara geçti.

Bu kontroller uçuş hazırlıkları yapıldı. Yer ekibi her detayı tek tek inceledi. Pilot kokpite geçti, ekipten uçağa dair raporu aldı ve F-16 pilotu savaş uçağındaki yerini aldı. F-16 savaş uçaklarının kokpitinde olmak hiç de kolay değil. Onlar birbirinden zorlu eğitimleri tamamlayarak hava sahamızın muhafızlarına dönüşüyor. Bazen terörle mücadele, bazense keşif ve istihbarat. Bu kez ise görev Efes 2026. İzlediğiniz için teşekkür ederim. Angardan çıkan F-16, dosta güven, düşmana korku veren sesiyle göğe yükselmek üzere aprondaki yerini aldı. Her şey hazır. Kahraman pilotların havalanması için tek bir talimat bekleniyor. Gerisi onların havadaki zorlu görevleri büyük bir kolaylık ve ustalıkla gerçekleştirmesinde.
```

### v11 tam çıktı - filtre öncesi raw

- Raw segment: `13`
- Clean segment: `13`
- Drop: `0` / `{}`
- Word count raw: `139`
- Total seconds: `9.029`
- Uyarı: artifacts=['İzlediğiniz için teşekkür ederim'], max_run=2, max_token_length=19

```text
Tüm hazırlıklar tamamlandı. P-16'lar Eskişehir 1. Anajet üstünden havalandı.

Eskişehir'de F-16 pilotlarının İzmir'de gerçekleştirilen FS-2026 tatbikatı için hazırlıklarını TRT Haber ekibi görüntüledi. Pilotlar gökyüzünde karşılaşacakları C kuvvetine karşı ekipmanlarını giyip hangara geçti.

İkin kontroller uçuş hazırlıkları yapıldı. Yer ekibi her detayı tek tek inceledi. Pilot kokpite geçti, ekipler uçağa dair raporu aldı ve F-16 pilotu savaş uçağındaki yerini aldı. F-16 savaş uçaklarının kokpitinde olmak hiç de kolay değil. Onlar birbirinden zorlu eğitimleri tamamlayarak hava sahamızın muhafızlarına dönüşüyor. Bazen terörle mücadele, bazense keşif ve istihbarat. Bu kez ise görev FS-2026. İzlediğiniz için teşekkür ederim. Angardan çıkan F-16, dosta güven, düşmana korku veren sesiyle göğe yükselmek üzere aprondaki yerini aldı. Her şey hazır. Kahraman pilotların havalanması için tek bir talimat bekleniyor. Gerisi onların havadaki zorlu görevleri büyük bir kolaylıkla, ustalıkla gerçekleştirmesinde.
```

## trt_haber (2).mp4

- Source: `E:\MITAS\testklipler\trt_haber (2).mp4`
- Mode: `full_requested`
- Window: `0.000-146.744s`

### v7 tam çıktı - filtre öncesi raw

- Raw segment: `27`
- Clean segment: `27`
- Drop: `0` / `{}`
- Word count raw: `256`
- Total seconds: `27.969`

```text
Ben özellikle anne olduktan sonra kendi mesleğim kadın doğum hekimliğine bakış açım çok fazla değişti. Hastalara o empati yapabilme. Aslında bizim anne olarak bu işi yaptığımızdaki çok ortak yanları. Bazen acil bir durum için hastaneye koşuyorlar, bazen de nöbette çocuklarından ayrı kalmanın zorluğunu yaşıyorlar. Çan ve Sakura Şehir Hastanesi'nin kadın hastalıkları ve doğum uzmanları bir taraftan hastalarına umut olmaya çalışırken bir taraftan da evde onları bekleyen çocuklarına yetişmeye çalışıyorlar. Zorlu geçen nöbetler, acil ameliyatlar, uykusuz gecelere rağmen onlar çocuklarını fedakarca, sevgiyle büyütmeye çalışıyorlar. Gözde Şahin 19 yıllık hekim. 14 yaşında bir kızı var. Çocuğumu ayağımdan sallarken bırakıp hemen koşarak hastaneye gittim. Bunun gibi birçok örnek durumla karşılaştık ve çocuğumun hiçbir zaman mesela ilk sözcüğünü duyamadım, yürüyüşünü hiçbir zaman göremedim. Ayşe Ceren Yıldız ise 6 yıllık hekim, 20 aylık kızı var. Doğumu başladığında poliklinikte hasta muayene ediyordu. Ben de gebelik sürecimde aktif olarak çalışmaya devam ettim. Hatta 36 hafta gebeyken poliklinikte hasta bakıyordum ve o akşam doğumum başladı. Başka annelere, başka annelerin evlatlarına da şifa almaya çalışıyoruz. Kübra Keskin Topbaş'ta 11 yıllık hekim. Anne olmak zaten çok büyük bir sorumluluk. Aynı zamanda hekim bir anne olmak bu sorumluluğu ikiye katlıyor. Bir tarafta evde bekleyen bir çocuğunuz var, bir tarafta hastalarınız var. İkisine de hakkaniyetli olup eşit çerçevede yaklaşmaya çalışıyorsunuz. Şadiye Hande Soyer Somunsuysa çiçeği burnunda bir anne. Hekimlik hayallerime devam edebiliyorsam annelerin varlığı sayesinde diyor. Annelik mesaisi hiç bitmiyor. Eğer gözüm arkada kalmadan işe gelip... hastalara şifa olabiliyorsam hem kendi annem hem eşimin annesi bana destek olduğu için devam edebiliyorum. Anneanneler, babaanneler iyi ki varlar.
```

### v11 tam çıktı - filtre öncesi raw

- Raw segment: `24`
- Clean segment: `24`
- Drop: `0` / `{}`
- Word count raw: `240`
- Total seconds: `11.368`

```text
Ben özellikle anne olduktan sonra kendi mesleğim kadın doğum hekimliğine bakış açım çok fazla değişti. Hastalara o empati yapabilme. Aslında bizim anne olarak bu işi yaptığımızdaki çok ortak yanları. Bazen acil bir durum için hastaneye koşuyorlar, bazen de nöbette çocuklarından ayrı kalmanın zorluğunu yaşıyorlar. Çam ve Sakura Şehir Hastanesi'nin kadın hastalıkları ve doğum uzmanları bir taraftan hastalarına umut olmaya çalışırken bir taraftan da evde onları bekleyen çocuklarına yetişmeye çalışıyorlar. Zorlu geçen nöbetler, acil ameliyatlar, uykusuz gecelere rağmen onlar çocuklarını fedakarca sevgiyle büyütmeye çalışıyorlar.

Çocuğumu ayağımdan sallarken bırakıp hemen koşarak hastaneye gittim. Bunun gibi birçok örnek durumla karşılaştık ve çocuğumun hiçbir zaman mesela ilk sözcüğünü duyamadım. Yürüyüşünü hiçbir zaman göremedim. Ayşe Ceren Yıldız'a 6 yıllık hekim, 20 aylık kızı var. Doğumu başladığında poliklinikte hasta muayene ediyordu. Ben de gebelik sürecimde aktif olarak çalışmaya devam ettim. Hatta 36 hafta gebeyken poliklinikte hasta bakıyordum ve o akşam doğumum başladı. Başka annelere, başka annelerin evlatlarına da şifa almaya çalışıyoruz.

Anne olmak zaten çok büyük bir sorumluluk. Aynı zamanda hekim bir anne olmak bu sorumluluğu ikiye katlıyor. Bir tarafta evde bekleyen bir çocuğunuz var, bir tarafta hastalarınız var. İkisine de hakkaniyetli olup eşit çerçevede yaklaşmaya çalışıyorsunuz. Şadiye Hande Soyer somunsuysa çiçeği burnunda bir anne. Hekimlik hayallerime devam edebiliyorsam annelerin varlığı sayesinde diyor. Annelik mesaisi hiç bitmiyor. Eğer gözüm arkada kalmadan işe gelip... Hem hastalara şifa olabiliyorsam hem kendi annem hem eşimin annesi bana destek olduğu için devam edebiliyorum. Anneanneler, babaanneler iyi ki varlar.
```

## trt_haber (3).mp4

- Source: `E:\MITAS\testklipler\trt_haber (3).mp4`
- Mode: `full_requested`
- Window: `0.000-75.452s`

### v7 tam çıktı - filtre öncesi raw

- Raw segment: `13`
- Clean segment: `13`
- Drop: `0` / `{}`
- Word count raw: `135`
- Total seconds: `18.318`

```text
İstanbul'da tramvay yolunda hızla ilerleyen otomobil ışıklarda karşıya geçmeye çalışan araca çarptı. Saniyeler önce karşıya geçen yaya ise şans eseri kurtuldu. O anlar güvenlik kameralarına yansıdı. Yunanistan'a açılan Edirne Pazar Kule sınır kapısında modernizasyon çalışmaları başladı. Giriş ve çıkış peron sayısı artırılacak ve kapı daha aktif hale getirilecek. Ayrıntıları öğreneceğiz hemen. Yavuz Demir bizi bekliyor.

Vanda durum bu. Arkadaşımız Hümeyra Pardeli'nin güç koşullarda yaptığı yayını paylaştık, getirdik ekranlarınıza. Şimdi Ardahan ve Karst sınırları arasında bulunan Çıldır Gölü'nün de yüzeyi kısmen buz tuttu. Buz kalınlığının 20 santimetreyi bulmasıyla birlikte atlı kızaklar göle gelen ziyaretçilere hizmet vermeye başladı. Gürcistan sınırında bulunan ve donan Aktaş Gölü ise patencileri ağırladı. Bu görüntülerle noktalıyoruz bugün haber ajandasını. Yarın saatler 14'ü gösterdiğinde biz yine burada olacağız. Sizleri de ekranlarınızın başına bekliyoruz efendim. İyi akşamlar diliyoruz. Hoşçakalın.
```

### v11 tam çıktı - filtre öncesi raw

- Raw segment: `10`
- Clean segment: `10`
- Drop: `0` / `{}`
- Word count raw: `134`
- Total seconds: `8.309`

```text
İstanbul'da tramvay yolunda hızla ilerleyen otomobil, ışıklarda karşıya geçmeye çalışan araca çarptı. Saniyeler önce karşıya geçen yaya ise şans eseri kurtuldu. O anlar güvenlik kameralarına yansıdı. Yunanistan'a açılan Edirne Pazar Kule sınır kapısında modernizasyon çalışmaları başladı. Giriş ve çıkış peron sayısı artırılacak ve kapı daha aktif hale getirilecek. Ayrıntıları öğreneceğiz hemen. Yavuz Demir bizi bekliyor.

Van'da durum bu. Arkadaşımız Yümeyra Pardeli'nin güç koşullarda yaptığı yayını paylaştık getirdik ekranlarınıza. Ardahan ve Karş sınırları arasında bulunan Çıldır Gölü'nünde yüzeyi kısmen buz tuttu. Buz kalınlığının 20 santimetreyi bulmasıyla birlikte atlı kızaklar göle gelen ziyaretçilere hizmet vermeye başladı. Gürcistan sınırında bulunan ve donan Aktaş Gölü ise patencileri ağırladı. Bu görüntülerle noktalıyoruz bugün haber ajandasını. Yarın saatler 14'ü gösterdiğinde biz yine burada olacağız. Sizleri de ekranlarınızın başına bekliyoruz efendim. İyi akşamlar diliyoruz. Hoşçakalın.
```

## Karşılaştırmalı Yorum

1. `clean_transcript.txt` bu değerlendirme için tek başına güvenilir değil. Özellikle `2.mp4` örneğinde v7 konuşmayı raw aşamada yakalamış, fakat `no_speech_prob > 0.6` filtresi 26 segmenti düşürmüş. Bu yüzden v7 eksik konuşmuş gibi görünmüş.

2. v7 raw çıktıları genel olarak daha kontrollü. Bazı segmentlerde yanlış kelime/özel isim var, fakat v11 kadar büyük tekrar veya stock subtitle hallucination üretmiyor.

3. v11 hız avantajı sağlıyor ve bazı temiz anlatı/haber kliplerinde iyi duruyor; fakat `beyaz1.mp4` içinde yüzlerce `ben` tekrarı, `2.mp4` içinde uzun `Hıhı...` tokenı, bazı kliplerde `Altyazı` / `Abone olmayı` / `İzlediğiniz için teşekkür ederim` gibi artifactler üretiyor.

4. Nihai karar değişmiyor: varsayılan kalite modu `v7` olmalı. Ancak post-filter yeniden tasarlanmalı: `no_speech_prob` tek başına segment düşürmemeli, önce `low_confidence` olarak işaretlenmeli. Düşürme kararı `avg_logprob`, metin tekrar/artifact kontrolleri ve gerekiyorsa ikinci model doğrulamasıyla verilmelidir.

5. v11 sadece hızlı mod adayı olarak kalmalı ve şu kalite kapıları olmadan üretim defaultu yapılmamalı: uzun token, ardışık tekrar, stock subtitle artifactleri ve anormal word-count artışı.
