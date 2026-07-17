# MASTER-PNG KAPSAMA — BULGULAR + BUILD PLANI (2026-07-06)

## Çağatay isteği
Master-PNG (reading_master_runaware.png / giris_reading_master_runaware.png) TÜM jenerikli filmlerde
sağlıklı gelsin. Kaliteden memnun, ama düzenli gelmiyor. Sebep: bizim hata mı sistem mi?

## KAPSAMA (263 kunye'li film, DOĞRU dosyalarla)
- giris_reading_master: 250 (%95) · reading_master (çıkış): 203 (%77) · hiç-yok: 8 (%3)
- Üretim SAĞLIKLI ve yaygın (uzun-metin istifi, footage-çöp değil).

## SEBEP-AYRIMI (kanıtlı)
1. **Zamanlama-kaçağı (5 film):** havuz-dolu-master-yok. KANIT: SINIR ÇİZGİSİ elle koşulunca sorunsuz
   üretildi. → ✅ BACKFILL DÜZELTTİ (5/6; ZİRVEDEKİ monitor-bug'ı).
2. **İki-master-sistemi (312 film):** reading_master (run-aware, İYİ) ≠ kök '<ad> giris/cikis.png'
   (crop-stack/slit-scan, ZAYIF/küçük). Kök-adlar sık 100× küçük (13.SAVAŞÇI çıkış 39KB vs 4580KB).
   → Hangisi kanonik olsun kararı (konsey planına eklenecek).
3. **Detect-kaçağı (LOTR-tip):** sıkı-detektör gerçek jeneriği reddediyor. KANIT: YÜZÜKLERİN EFENDİSİ
   sıkı=0, gevşek-motor=525 kredi-karesi! Koca kapanış-jeneriği çöpe atılıyordu.
   → cikis_yazi (gevşek-motor) master'a bağla + sağlık-kapısı.
4. **Çökme (TOPLU 0356):** OCR MOTOR_YOK; ham-kare var, gevşek=12. → yeniden-koşu.
5. **Meşru-boş (TACİZ/BEKARLIK):** gerçekten jeneriksiz olabilir → gevşek-motorla teyit gerek.

## ÇIKIŞ %70 < GİRİŞ %95'İN KÖKÜ (konsey)
İki farklı motor: giriş gevşek-yazı-seçimi (yüksek kapsama) vs çıkış sıkı-kredi-çapası (not_found reddi).
"Kapanış zor" DEĞİL — motor-felsefesi farkı.

## BUILD PLANI (konsey ÇİFT-onaylı, kanıt-kapılı)
- Faz-1: master-backfill KALICI pipeline-adımı (zamanlama-kaçağı bir daha olmaz). Kill: MITAS_MASTER_BACKFILL.
- Faz-2: sağlık-skoru ÖLÇÜM-modu (hizalama-düzenliliği birincil + scroll + text-mask + yükseklik).
- Faz-3: cikis_yazi→master bağla (sağlık-kapısı arkasından). Kill: MITAS_MASTER_CIKIS_YAZI_KAYNAK.
- Faz-4: reading_master vs kök-ad kanonik kararı (iki-master-sistemi çözümü).
- ZİRVEDEKİ monitor-bug (bir segment boş→hepsi düşüyor) düzelt.
Hepsi default-OFF, byte-nötr, credit_detect/karar/PDF'e DOKUNMAZ, golden 28/28 sabit.
