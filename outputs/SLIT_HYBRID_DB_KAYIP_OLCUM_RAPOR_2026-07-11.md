# HİBRİT-DY — ÜRETİM DATABASE KAYIP ÖLÇÜMÜ (294 film)
2026-07-11 · SALT-OKUR karar taraması (compose/yazma YOK) · veri: outputs/SLIT_HYBRID_DB_KAYIP_OLCUM.json

## ÜST CEVAP: 294 FİLMDE KAYIP = SIFIR
Tüm üretim Database'i (294 hub × giriş+çıkış = 588 segment, 467 kayan-run) tarandı. Hibrit'in kararı:

| Karar | Sayı | Anlam |
|---|---|---|
| **MASKED** | **466 run** | Hibrit dokunmaz → eski kodla BİREBİR → değişim yok → **kayıp imkânsız** |
| **FULL** | **1 run** | Tek film değişir: HAYALET BABAM giriş → aşağıda incelendi |
| DEMOTE | 0 | — |
| HATA | 0 | — |

Yani 294 filmden **293'ü kelimesi kelimesine aynı kalır**, yalnız 1 film-segmenti değişir.

## TEK DEĞİŞEN: HAYALET BABAM (giriş) — NÖTR, KAYIP DEĞİL
- Sinyal: run [4,17], 14 kare, cov=0.461 (eşik 0.40'ın hemen üstünde), skip=0.615, n_coin=8, med_f=5.2 (yavaş kayma).
- İçerik: gece şehir-manzarası (Seattle) üzerine **hareketli footage** açılış jeneriği (donmuş DEĞİL).
- Görsel kıyas (KIYAS_ust.png + SIDNEY_kirp.png tam-çözünürlük): ESKİ ve YENİ **neredeyse aynı** (boyut 4046 vs 4044 px). DENISE NICHOLAS ve IAN BANNEN ikisinde de TEMİZ. **DÜZELTME (Çağatay yakaladı):** "a film by SIDNEY POITIER" satırı ikisinde de YARIM — harflerin altından sarı footage-sızma bandı (şehir ışıkları) geçiyor, harfler görünür ama zedeli. Bu bulaşma ESKİDE DE YENİDE DE birebir aynı → hibrit ne yarattı ne düzeltti (önceden-var footage-sızması). %27 piksel farkı arka plan footage istiflenmesinde.
- **Hüküm: NÖTR + KAYIP YOK.** SIDNEY POITIER eşit-zedeli (hibrit kötüleştirmedi), diğer isimler eşit-temiz. Hibrit hiçbir şeyi bozmadı; ama bu vakada bir şeyi DÜZELTMEDİ de (footage-sızması hareketli-footage sınıfı, senin_hikayen ailesi — FULL bunu çözmez). Yani bu tek "değişim" kazanç bile değil, nötr.

## DÜRÜST NÜANS: eşik kalibrasyonu
HAYALET BABAM aslında marjinal bir tetik: cov=0.461, eşiğin (0.40) hemen üstünde, ve **hareketli-footage** vakası (FULL'ün teorik risk yönü — footage-hareketini takip). Burada zararsız çıktı (kısa run, isimler okunur). İstenirse cov eşiği 0.50'ye çekilerek film-Database %100 dokunulmadan bırakılabilir — margin var: HAYALET BABAM 0.461 vs Yedi Numara (gerçek hayalet) 0.576. Ama gerekmiyor: değişim zaten zararsız.

## NEDEN BU KADAR AZ DEĞİŞİM?
Hayalet, bir **DİZİ** olgusu (oyuncular grup-poz verip donuyor, üstünden yazı akıyor). Bu Database ise ağırlıkla **FİLM** — filmlerde bu kalıp neredeyse yok. Bu yüzden düzeltilecek hayalet ~0 (beklendiği gibi). Kazanç dizilerde görünür (Yedi Numara), filmlerde değil.

## "HEPSİNE GEÇSEK KAYBIMIZ OLUR MU?" — KESİN CEVAP
**Hayır.** 294 üretim filminin 293'ü birebir aynı; 1'i (HAYALET BABAM) zararsız-nötr değişir. Hiçbir filmin jeneriği daha az okunur hale gelmiyor. Bayrak-1'i tüm Database'e açsan **sıfır kayıp**. Tek stratejili motora geçiş güvenli — ve istersen cov eşiğini 0.50 yapıp o tek nötr değişimi de eleyerek film-Database'i %100 dokunulmadan bırakabilirsin.
