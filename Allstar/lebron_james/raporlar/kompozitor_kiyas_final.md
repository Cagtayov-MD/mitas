# Kompozitör kıyası — 2026-08-17T01:25:01

Motorlar: lebron, ibrahimovic, magic

| film | sınıf | kare | lebron: boy/seg/recall/dup/sağlıklı | ibrahimovic: boy/seg/recall/dup/sağlıklı | magic: boy/seg/recall/dup/sağlıklı |
|---|---|---|---|---|---|
| benimle-dans-et | sadakat-doğrulama (recall 0.829) | 55 | 2686/2/0.7861/0.0/✓ | 2367/1/0.7273/0.0/✓ (çökme) | 2206/1/0.7433/0.0/✓ (çökme) |
| olum-emri | sadakat-doğrulama (recall 0.189) | 272 | 10377/2/0.2351/0.0181/✓ | 9915/1/0.2421/0.0083/✓ (çökme) | 9897/1/0.2372/0.0062/✓ (çökme) |
| solaris | sadakat-doğrulama (17 kare, az kare) | 17 | 530/1/0.3333/0.0/✓ | 480/1/0.3333/0.0/✓ | 529/1/0.3333/0.0/✓ |
| baba-2 | sadakat-doğrulama (295 kare, uzun) | 295 | 12204/4/0.8256/0.0/✓ | 11654/4/0.7791/0.0031/✓ | 12492/5/0.8198/0.0044/✓ |
| hizli-silah | sadakat-doğrulama (okunabilirlik 0.25) | 67 | 1851/3/0.0208/0.026/✓ | 1513/2/0.0417/0.0417/✓ | 1851/3/0.0208/0.026/✓ |
| acemiler-cetesi | sadakat-doğrulama (kule ilk koşusu) | 35 | 2321/2/0.8571/0.0/✓ | 2322/2/0.8571/0.0/✓ | 2321/2/0.8571/0.0/✓ |
| kucuk-dev-adam | dissolve zinciri (plato/fake-scroll kalibrasyonu) | 73 | 3913/8/0.1964/0.2462/✗ | 4349/9/0.1845/0.3247/✗ | 1984/4/0.1071/0.0/✓ |
| karadeniz | fade zinciri + soluk kartlar (110'da görünmez) | 233 | 4180/3/0.255/0.0066/✓ | 7341/14/0.2807/0.0062/✓ | 4468/4/0.2697/0.0065/✓ |
| hayat-agaci | çöküş + kar-tulumu gren (fark-tabanı sınıfı) | 113 | 6341/1/0.0/0.0676/✓ (çökme) | 1234/1/0.0/0.1176/✗ (çökme) | 6340/1/0.0/0.0676/✓ (çökme) |
| demir-maskeli-adam | pozitif kontrol (üretimde recall 0.005) | 89 | 14613/9/0.8177/0.0/✓ | 5191/5/0.3046/0.0142/✓ | 14133/8/0.8273/0.0/✓ |
| jetgiller-ve-cakmaktaslar | statik zemin (fark yalnız fallback) | 49 | 4952/10/0.5213/0.2181/✗ | 1340/2/0.1611/0.0337/✓ | 3512/7/0.4265/0.128/✗ |
| komsum-totoro | statik zemin (NCC dominasyon sınıfı) | 116 | 7624/15/0.2414/0.4853/✗ | 11171/23/0.431/0.148/✗ | 7143/14/0.2184/0.4603/✗ |

## Motor özeti

| motor | üretti | sağlıklı | çökme | arıza | recall medyan | dup medyan | boy medyan |
|---|---|---|---|---|---|---|---|
| lebron | 12/12 | 9 | 1 | 0 | 0.2942 | 0.0123 | 4566 |
| ibrahimovic | 12/12 | 9 | 3 | 0 | 0.2926 | 0.0112 | 3358 |
| magic | 12/12 | 10 | 3 | 0 | 0.3015 | 0.0053 | 3990 |

Süre: 486.2 s · Çıktılar: `scratch/kompozitor_kiyas/<motor>/`