# Neretva Screenshot Diff Confidence Scores

`avg_logprob`: yüksek/sıfıra yakın olan daha iyi. `no_speech_prob`: düşük olan daha iyi.
`combined`: `avg_logprob - no_speech_prob`; kaba karar sinyali, yüksek olan daha iyi.

| Fast | Quality | Fast avg_logprob | Quality avg_logprob | Fast no_speech | Quality no_speech | Avg winner | Combined winner | Fast time | Quality time |
|---|---|---:|---:|---:|---:|---|---|---|---|
| kurulardan | kurulalıdan | -0.1455 | -0.151 | 0.0 | 0.5215 | near_tie | fast | 43.3-56.26 | 43.3-56.26 |
| burada | burayı | -0.1455 | -0.151 | 0.0 | 0.5215 | near_tie | fast | 43.3-56.26 | 43.3-56.26 |
| çektik | çekti | -0.1688 | -0.1726 | 0.0 | 0.1512 | near_tie | fast | 111.34-113.42 | 111.34-113.4 |
| beygiri | peygiri | -0.1688 | -0.1726 | 0.0 | 0.1512 | near_tie | fast | 116.58-119.16 | 115.9-119.18 |
| güne | Bugüne | -0.0685 | -0.0583 | 0.0 | 0.0003 | near_tie | near_tie | 212.915-227.295 | 212.935-227.135 |
| yıldır | yüzyıldır | -0.0685 | -0.0583 | 0.0 | 0.0003 | near_tie | near_tie | 212.915-227.295 | 212.935-227.135 |
| tanınmış | tanımış | -0.0685 | -0.0583 | 0.0 | 0.0003 | near_tie | near_tie | 212.915-227.295 | 212.935-227.135 |
| değildir | değil | -0.0685 | -0.1472 | 0.0 | 0.2715 | fast | fast | 212.915-227.295 | 194.07-196.11 |
| varlığı | varlıktı | -0.4809 | -0.3831 | 0.0 | 0.1418 | quality | near_tie | 227.3-229.3 | 227.3-235.8 |
| bilemiyordum | bilemiyorum | -0.4809 | -0.3831 | 0.0 | 0.1418 | quality | near_tie | 229.8-232.3 | 227.3-235.8 |
| yok | köprüyor | -0.4809 | -0.3831 | 0.0 | 0.1418 | quality | near_tie | 232.3-234.3 | 227.3-235.8 |
| dokuyu | hukuyu | -0.2079 | -0.1451 | 0.0 | 0.1357 | quality | fast | 242.92-252.18 | 242.9-252.18 |
| çalışıyorlar | çalışıyor | -0.2079 | -0.1451 | 0.0 | 0.1357 | quality | fast | 255.82-261.36 | 255.82-261.28 |

## Segment Contexts

### kurulardan -> kurulalıdan

- Fast: `Ben Mustafa Kaytas. Mostar şehri kurulardan beri burada oturur benim ailem. Belki de onlar kurdular burada. Yalnız soyumun Türkiye'den gelme olduğunu biliyorum.`
- Quality: `Ben Mustafa Kaytas, Mostar şehri kurulalıdan beri burada oturur benim ailem. Belki de onlar kurdular burayı. Yalnız soyumun Türkiye'den gelme olduğunu biliyorum.`

### burada -> burayı

- Fast: `Ben Mustafa Kaytas. Mostar şehri kurulardan beri burada oturur benim ailem. Belki de onlar kurdular burada. Yalnız soyumun Türkiye'den gelme olduğunu biliyorum.`
- Quality: `Ben Mustafa Kaytas, Mostar şehri kurulalıdan beri burada oturur benim ailem. Belki de onlar kurdular burayı. Yalnız soyumun Türkiye'den gelme olduğunu biliyorum.`

### çektik -> çekti

- Fast: `Biz kaldık ama neler çektik.`
- Quality: `Biz kaldık ama neler çekti.`

### beygiri -> peygiri

- Fast: `Dolap beygiri gibi dönüp duruyordu.`
- Quality: `Dolap peygiri gibi dönüp duruyordu.`

### güne -> Bugüne

- Fast: `Bu güne kadar yüz yıldır tahrip edilerek bir kısmının izinin bile kalmadığını görürsünüz. Dünyanın bildiği en tanınmış varlığımız köprümüzdür. O sanki taştan yapılma bir köprü değildir.`
- Quality: `Bugüne kadar yüzyıldır tahrip edilerek bir kısmının izinin bile kalmadığını görürsünüz. Dünyanın bildiği en tanımış varlığımız köprümüzdür. O sanki taştan yapılma bir köprü değil.`

### yıldır -> yüzyıldır

- Fast: `Bu güne kadar yüz yıldır tahrip edilerek bir kısmının izinin bile kalmadığını görürsünüz. Dünyanın bildiği en tanınmış varlığımız köprümüzdür. O sanki taştan yapılma bir köprü değildir.`
- Quality: `Bugüne kadar yüzyıldır tahrip edilerek bir kısmının izinin bile kalmadığını görürsünüz. Dünyanın bildiği en tanımış varlığımız köprümüzdür. O sanki taştan yapılma bir köprü değil.`

### tanınmış -> tanımış

- Fast: `Bu güne kadar yüz yıldır tahrip edilerek bir kısmının izinin bile kalmadığını görürsünüz. Dünyanın bildiği en tanınmış varlığımız köprümüzdür. O sanki taştan yapılma bir köprü değildir.`
- Quality: `Bugüne kadar yüzyıldır tahrip edilerek bir kısmının izinin bile kalmadığını görürsünüz. Dünyanın bildiği en tanımış varlığımız köprümüzdür. O sanki taştan yapılma bir köprü değil.`

### değildir -> değil

- Fast: `Bu güne kadar yüz yıldır tahrip edilerek bir kısmının izinin bile kalmadığını görürsünüz. Dünyanın bildiği en tanınmış varlığımız köprümüzdür. O sanki taştan yapılma bir köprü değildir.`
- Quality: `Yine gelenler oluyor ama o kadar değil.`

### varlığı -> varlıktı

- Fast: `Efsanevi bir varlığı.`
- Quality: `Efsanevi bir varlıktı, ona nasıl kıydılar bilemiyorum, şimdi köprüyor Mostar ne kadarmış.`

### bilemiyordum -> bilemiyorum

- Fast: `Ona nasıl kıydılar bilemiyordum.`
- Quality: `Efsanevi bir varlıktı, ona nasıl kıydılar bilemiyorum, şimdi köprüyor Mostar ne kadarmış.`

### yok -> köprüyor

- Fast: `Şimdi köprü yok.`
- Quality: `Efsanevi bir varlıktı, ona nasıl kıydılar bilemiyorum, şimdi köprüyor Mostar ne kadarmış.`

### dokuyu -> hukuyu

- Fast: `Sağ ve soldaki büyük kulelerde, her iki yandaki çarşılarda, tarihi dokuyu muhafaza eden bütün yapılar, her yan delik diş gibi.`
- Quality: `Sağ ve soldaki büyük kulelerde, her iki yandaki çarşılarda, tarihi hukuyu muhafaza eden bütün yapılar, her yan delik diş gibi.`

### çalışıyorlar -> çalışıyor

- Fast: `Kendi imkanlarıyla kurtaranlar da her gün umutla dükkanını açıp işini yapmaya çalışıyorlar.`
- Quality: `Kendi imkanlarıyla kurtaranlar da her gün Umut'la dükkanını açıp işini yapmaya çalışıyor.`
