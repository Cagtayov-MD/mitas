# OCR Canvas Gorsel QC Duzeltme - 2026-05-22

## Net Duzeltme

`phase2_canvas_contact_sheet.jpg` gorsel kontrolunden sonra onceki "canvas pass" yorumu final kalite anlaminda geri cekildi.

- `phase_quality=pass` sadece phase-correlation sinyalinin teknik olarak hesaplandigini gosteriyor.
- Bu metrik, panonun okunabilir/temiz/final jenerik oldugunu kanitlamiyor.
- Contact sheet'te cok sayida pano ghosting, ust uste binme, yanlis katman hizalama ve background tasimasi iceriyor.
- Bu nedenle mevcut canvas ciktilari **dogru final sonuc degil**.

## Gorsel Bulgular

- 01, 02, 05, 09, 10 gibi yatay/statik gorunen kliplerde canvas gereksiz veya yanlis semantik uretiyor.
- 03, 04, 06, 07, 08, 12, 13, 16, 17, 18 dikey pano uretmis; fakat panolarin bir bolumu temiz text strip degil, ust uste bindirilmis frame izleri gibi gorunuyor.
- 18 cok uzun pano uretmis ama text-layer yerine sahne/zemin hareketi ve parlak alanlar da birikmis.
- 06, 08, 12, 13, 16, 17 gibi dar dikey panolarda hareket yonu yakalanmis olabilir; yine de OCR icin bu panolarin tekrar islenmesi gerekiyor.

## Neden Yaniltti?

Mevcut de-scroll uygulamasi:

1. Tum frame veya gevsek text mask ile phase correlation yapiyor.
2. Kayan metin katmani ile arka plan/altyazi/legal/logo katmanlarini kesin ayirmiyor.
3. Frame'leri `maximum` blend ile uzun canvas'a bindiriyor.
4. Bu, beyaz metinlerde bazen sinyal koruyor ama ghosting ve ust uste binme de uretiyor.
5. Sonra uzun canvas tek parca OCR'a veriliyor; bu da kucuk font ve kontrast sorununu buyutuyor.

## Dogru Sonuc Sayilabilecek Kisim

- Frame extraction calisti.
- OCR motorlari calisti.
- Text motion sinyali hesaplandi.
- Panoramik gorsel dosyalari uretildi.
- OneOCR temporal stable output, ham veri olarak en kullanilabilir motor sinyalini verdi.

## Dogru Sonuc Sayilamayacak Kisim

- Uretilen panolar final/temiz jenerik panosu degil.
- Candidate `.txt` dosyalari final jenerik listesi degil.
- Canvas OCR sonuclari kalite kararinda kullanilacak seviyede degil.
- Ground truth olmadigi icin dogruluk orani halen yok.

## Bundan Sonraki Duzeltme

1. Tam ekran yerine once credit ROI ve subtitle-discard bolgesi belirlenecek.
2. Motion estimation sadece text bbox/text mask uzerinde, RANSAC/median shift ile yapilacak.
3. Global background motion ve text motion ayrilacak.
4. Canvas tum frame ile degil, text-layer crop/mask ile olusturulacak.
5. Uzun pano tek parca OCR'a verilmeyecek; okunabilir seritlere bolunup 2x/3x upscale + contrast ile OCR yapilacak.
6. Gorsel QC metrikleri eklenecek: ghosting skoru, canvas occupancy, text sharpness, OCR-on-canvas recall proxy.
7. Ilk duzeltme sadece 3 klipte denenmeli: `SON HAVA BUKUCU`, `FIRTINANIN ICINDE`, `BEYAZ BALINA`.

## Karar

Bu deneme basarisiz degil, ama final kalite acisindan basarili da degil. Degerli sonucu su: full-frame naive de-scroll yaklasimi gercek film jeneriginde yeterli degil; ROI + text-layer-only de-scroll sart.
