---
modul: kontrol_analiz
tarih: 2026-08-02
uretim: 2026-08-02T16:13:57
---

# KONTROL Analiz Raporu

## Özet

- **Toplam film:** 345
- **KONTROL:** 203
- **ONAYLI:** 142
- **KONTROL oranı:** %58.8

## Neden Dağılımı

| Sınıf | Sorumlu Modül | Sayı | % | Örnek |
|-------|--------------|------|---|-------|
| kunye_okuma | OCR/okuma — metin çıkarılamadı | 133 | %16.5 | yönetmen doğrulama: okunamadı (yeniden-okuma/insan) |
| kunye_kalite_qc1 | QC1 — okuma→rol eşleme başarısız | 108 | %13.4 | QC1 başarısız (OCR+VL ikisi de RED — düşük künye kalitesi, O |
| cast_bos | Qwen QC — oyuncu bulunamadı | 88 | %10.9 | qwen: oyuncu yok |
| kimlik_zayif | QC2/qc_block — web çapası kilitlenemedi | 82 | %10.1 | qc_block: kimlik kurulamadı (cast-örtüşme<2, web çapası kili |
| yonetmen_yapimci | Qwen QC — yönetmen+yapımcı eksik | 73 | %9.0 | qwen: yön+yapımcı yok |
| kimlik_celiski | QC2/kimlik — KB cross-check uyuşmazlığı | 65 | %8.0 | kimlik çelişkisi (KB cross-check) |
| render_latin | QC — Latin-dışı alfabe romanizasyon | 63 | %7.8 | qwen: Latin-dışı alfabe (deterministik kemer atladı → Kontro |
| ozet | Özet üretimi — LLM | 44 | %5.4 | özet yok/kısa (5k — gerçek özet üretilmemiş) |
| cast | Rol eşleme — oyuncu listesi | 43 | %5.3 | qc_block: CAST_CAP_DUSEN: cap-ustu okunan 199 oyuncu dustu ( |
| kimlik_kaynaksiz | QC2/kimlik — kıyas kaynağı yok | 34 | %4.2 | kimlik doğrulanamadı (kıyas kaynağı yok — OKUNAN_YOK) |
| siniflandirilamadi | VL aday ismi (teyitsiz, insan baksın): Maurice Cam | 25 | %3.1 | OCR bucket=GOZDEN_GECIR |
| yonetmen | Rol eşleme — yönetmen çıkarılamadı | 22 | %2.7 | yönetmen doğrulama: kaynak-çelişkisi (aday: Lütfi Ö. Akad) |
| render | PDF render — çıktı kalitesi | 15 | %1.9 | PDF render yok (md teslim) |
| teknik_hata | Teknik — genel hata | 12 | %1.5 | OCR bucket=HATA |
| teknik_motor | OCR — motor bulunamadı | 1 | %0.1 | OCR bucket=MOTOR_YOK |

## kontrol_tip Dağılımı

- **YONETMEN:** 33 film
- **YONETMEN_KIMLIK:** 21 film
- **UNKNOWN:** 17 film
- **KIMLIK:** 16 film
- **YONETMEN_KIMLIK_CAST:** 15 film
- **YONETMEN_KIMLIK_CAST_RENDER:** 14 film
- **YONETMEN_KIMLIK_RENDER:** 14 film
- **OZET:** 10 film
- **HAFIF_CAST_CAP_DUSEN:** 10 film
- **YONETMEN_KIMLIK_CAST_OZET:** 10 film
- **RENDER:** 9 film
- **KIMLIK_RENDER:** 6 film
- **YONETMEN_RENDER:** 5 film
- **HAFIF_AFIS:** 5 film
- **YONETMEN_CAST_RENDER:** 4 film
- **YONETMEN_OZET:** 4 film
- **KIMLIK_CAST:** 3 film
- **KIMLIK_CAST_RENDER:** 2 film
- **HAFIF_AFIS_CAST_CAP_DUSEN:** 1 film
- **YONETMEN_OZET_RENDER:** 1 film
- **YONETMEN_CAST_OZET:** 1 film
- **OZET_RENDER:** 1 film
- **HAFIF_CASING:** 1 film

## Sistemik Bulgular

- **Yüksek KONTROL oranı:** %58.8 (203/345) — pipeline kalite eşiği gözden geçirilmeli.
- **OCR HATA:** 12 filmde OCR kalitesi HATA seviyesinde — okuma motoru sorunu.
- **Kümülatif kusur:** 136 film (%67) 3+ nedenden KONTROL'e düştü — zincirleme sorun.
- **Tekrar eden hata:** `kunye_okuma` → 133 film aynı sorunu yaşıyor. Kod düzeltmesi ile toplu çözüm mümkün.
- **Tekrar eden hata:** `kunye_kalite_qc1` → 108 film aynı sorunu yaşıyor. Kod düzeltmesi ile toplu çözüm mümkün.
- **Tekrar eden hata:** `cast_bos` → 88 film aynı sorunu yaşıyor. Kod düzeltmesi ile toplu çözüm mümkün.

## Film Detayları (ilk 30)

### 13. SAVAŞÇI (1999-0394-1-0000-90-1)
- **Tip:** OZET
- **Sınıflar:** teknik_motor, kunye_kalite_qc1, ozet
  - OCR bucket=MOTOR_YOK
  - QC1 başarısız (OCR+VL ikisi de RED — düşük künye kalitesi, OCR yetersiz)
  - özet yok/kısa (5k — gerçek özet üretilmemiş)
- **OCR:** MOTOR_YOK, **Süre:** 331sn

### 21. YÜZYIL EŞİĞİNDE TÜRK AİLESİ (1900-0138-0-0009-00-1)
- **Tip:** YONETMEN_KIMLIK
- **Sınıflar:** kunye_kalite_qc1, kimlik_celiski, yonetmen_yapimci
  - QC1 başarısız (OCR+VL ikisi de RED — düşük künye kalitesi, OCR yetersiz)
  - kimlik çelişkisi (KB cross-check)
  - qwen: yön+yapımcı yok
- **OCR:** GUVENILIR, **Süre:** 630sn

### ADI CARMEN (1983-0256-1-0000-00-1)
- **Tip:** OZET
- **Sınıflar:** siniflandirilamadi, ozet, ozet
  - OCR bucket=GOZDEN_GECIR
  - özet yok/kısa (5k — gerçek özet üretilmemiş)
  - qwen: özet yok/placeholder
- **OCR:** GOZDEN_GECIR, **Süre:** 629sn

### AJAMİ (2009-9153-1-0000-00-1)
- **Tip:** RENDER
- **Sınıflar:** siniflandirilamadi, render_latin, render_latin
  - OCR bucket=GOZDEN_GECIR
  - qwen: Latin-dışı alfabe (deterministik kemer atladı → Kontrol)
  - qc_block: Latin-dışı kaynak (erken-translit) → romanizasyon insan teyidi gerek
- **OCR:** GOZDEN_GECIR, **Süre:** 934sn

### AK ALTIN (1957-0067-1-0000-00-1)
- **Tip:** YONETMEN_KIMLIK
- **Sınıflar:** kimlik_celiski, yonetmen_yapimci, yonetmen
  - kimlik çelişkisi (KB cross-check)
  - qwen: yön+yapımcı yok
  - yönetmen doğrulama: kaynak-çelişkisi (aday: Lütfi Ö. Akad)
- **OCR:** GUVENILIR, **Süre:** 270sn

### ALAMO (2004-9213-1-0000-00-1)
- **Tip:** YONETMEN_KIMLIK_CAST_RENDER
- **Sınıflar:** kunye_kalite_qc1, kimlik_kaynaksiz, cast_bos
  - QC1 başarısız (OCR+VL ikisi de RED — düşük künye kalitesi, OCR yetersiz)
  - kimlik doğrulanamadı (kıyas kaynağı yok — OKUNAN_YOK)
  - qwen: oyuncu yok
- **OCR:** GUVENILIR, **Süre:** 306sn

### ALTINA HÜCUM (1925-0008-1-0000-00-1)
- **Tip:** YONETMEN
- **Sınıflar:** kunye_kalite_qc1, yonetmen_yapimci, kunye_okuma
  - QC1 başarısız (OCR+VL ikisi de RED — düşük künye kalitesi, OCR yetersiz)
  - qwen: yön+yapımcı yok
  - yönetmen doğrulama: okunamadı (yeniden-okuma/insan)
- **OCR:** GUVENILIR, **Süre:** 656sn

### AMANSIZ TAKİP (1985-0223-1-0000-00-1)
- **Tip:** YONETMEN_KIMLIK_RENDER
- **Sınıflar:** kunye_kalite_qc1, kimlik_celiski, kunye_okuma
  - QC1 başarısız (OCR+VL ikisi de RED — düşük künye kalitesi, OCR yetersiz)
  - kimlik çelişkisi (KB cross-check)
  - yönetmen okunamadı (KB-fill yok — kırmızı çizgi)
- **OCR:** GUVENILIR, **Süre:** 691sn

### ANNA KARENINA (1988-0520-1-0000-00-1)
- **Tip:** YONETMEN_KIMLIK_RENDER
- **Sınıflar:** kimlik_kaynaksiz, yonetmen_yapimci, kimlik_zayif
  - kimlik doğrulanamadı (kıyas kaynağı yok — KAYNAK_YOK)
  - qwen: yön+yapımcı yok
  - qc_block: kimlik kurulamadı (cast-örtüşme<2, web çapası kilitlenemedi)
- **OCR:** GUVENILIR, **Süre:** 321sn

### ANNEM (2015-1082-1-0000-50-0)
- **Tip:** YONETMEN
- **Sınıflar:** kunye_okuma
  - yönetmen okunamadı (KB-fill yok — kırmızı çizgi)
- **OCR:** GUVENILIR, **Süre:** 594sn

### ARCEDIA (1993-0401-1-0000-00-1)
- **Tip:** OZET
- **Sınıflar:** ozet, ozet
  - özet yok/kısa (5k — gerçek özet üretilmemiş)
  - qwen: özet yok/placeholder
- **OCR:** GUVENILIR, **Süre:** 553sn

### ARTAN İSTEKLER (1980-0142-1-0000-00-1)
- **Tip:** YONETMEN_RENDER
- **Sınıflar:** kunye_kalite_qc1, yonetmen_yapimci, kunye_okuma
  - QC1 başarısız (OCR+VL ikisi de RED — düşük künye kalitesi, OCR yetersiz)
  - qwen: yön+yapımcı yok
  - yönetmen doğrulama: okunamadı (yeniden-okuma/insan)
- **OCR:** GUVENILIR, **Süre:** 787sn

### ATEŞİN IŞIĞI (1997-0385-1-0000-00-1)
- **Tip:** YONETMEN
- **Sınıflar:** kunye_kalite_qc1, yonetmen_yapimci, kunye_okuma
  - QC1 başarısız (OCR+VL ikisi de RED — düşük künye kalitesi, OCR yetersiz)
  - qwen: yön+yapımcı yok
  - yönetmen doğrulama: okunamadı (yeniden-okuma/insan)
- **OCR:** GUVENILIR, **Süre:** 1418sn

### ATIŞ (1997-0365-1-0000-00-1)
- **Tip:** YONETMEN_KIMLIK_CAST_RENDER
- **Sınıflar:** kunye_kalite_qc1, kimlik_kaynaksiz, cast_bos
  - QC1 başarısız (OCR+VL ikisi de RED — düşük künye kalitesi, OCR yetersiz)
  - kimlik doğrulanamadı (kıyas kaynağı yok — OKUNAN_YOK)
  - qwen: oyuncu yok
- **OCR:** GUVENILIR, **Süre:** 478sn

### AYAK TAKIMI (1991-0415-1-0000-00-1)
- **Tip:** HAFIF_CAST_CAP_DUSEN
- **Sınıflar:** cast
  - qc_block: CAST_CAP_DUSEN: cap-ustu okunan 1832 oyuncu dustu (Itions Criptions, Criptions Itions, Iti
- **OCR:** GUVENILIR, **Süre:** 1794sn

### AYNA (1975-1016-1-0000-00-1)
- **Tip:** YONETMEN_CAST_RENDER
- **Sınıflar:** siniflandirilamadi, kunye_kalite_qc1, cast
  - OCR bucket=GOZDEN_GECIR
  - QC1 başarısız (OCR+VL ikisi de RED — düşük künye kalitesi, OCR yetersiz)
  - versiyon cast-teyitsiz (web title+year kilidi — insan onayı)
- **OCR:** GOZDEN_GECIR, **Süre:** 702sn

### AYNA (1997-2176-1-0000-56-0)
- **Tip:** YONETMEN_KIMLIK_CAST_RENDER
- **Sınıflar:** kunye_kalite_qc1, kimlik_kaynaksiz, cast_bos
  - QC1 başarısız (OCR+VL ikisi de RED — düşük künye kalitesi, OCR yetersiz)
  - kimlik doğrulanamadı (kıyas kaynağı yok — OKUNAN_YOK)
  - qwen: oyuncu yok
- **OCR:** GUVENILIR, **Süre:** 941sn

### AYNADAKİ DÜŞMAN (2010-9199-0-0001-88-1)
- **Tip:** KIMLIK_RENDER
- **Sınıflar:** yonetmen, render_latin
  - yönetmen doğrulama: kaynak-çelişkisi (aday: CEM AKYOLDAŞ)
  - qc_block: Latin-dışı kaynak (erken-translit) → romanizasyon insan teyidi gerek
- **OCR:** GUVENILIR, **Süre:** 1043sn

### AĞAÇ (1986-0334-1-0000-00-1)
- **Tip:** HAFIF_AFIS
- **Sınıflar:** 
- **OCR:** GUVENILIR, **Süre:** 590sn

### AĞIZ TADI (2001-9238-1-0000-00-1)
- **Tip:** YONETMEN
- **Sınıflar:** kunye_kalite_qc1, kunye_okuma, kunye_okuma
  - QC1 başarısız (OCR+VL ikisi de RED — düşük künye kalitesi, OCR yetersiz)
  - yönetmen okunamadı (KB-fill yok — kırmızı çizgi)
  - yönetmen doğrulama: okunamadı (yeniden-okuma/insan)
- **OCR:** GUVENILIR, **Süre:** 592sn

### AŞK DOSYASI (1996-0364-1-0000-00-1)
- **Tip:** KIMLIK_CAST
- **Sınıflar:** kunye_kalite_qc1, kimlik_kaynaksiz, cast_bos
  - QC1 başarısız (OCR+VL ikisi de RED — düşük künye kalitesi, OCR yetersiz)
  - kimlik doğrulanamadı (kıyas kaynağı yok — KAYNAK_YOK)
  - qwen: oyuncu yok
- **OCR:** GUVENILIR, **Süre:** 305sn

### AŞK EVLİLİĞİ (1996-0353-1-0000-00-1)
- **Tip:** HAFIF_AFIS
- **Sınıflar:** 
- **OCR:** GUVENILIR, **Süre:** 472sn

### AŞK ŞARKIM (2010-1158-1-0000-50-1)
- **Tip:** YONETMEN_KIMLIK
- **Sınıflar:** kunye_kalite_qc1, kimlik_celiski, cast
  - QC1 başarısız (OCR+VL ikisi de RED — düşük künye kalitesi, OCR yetersiz)
  - kimlik çelişkisi (KB cross-check)
  - XML-PDF cast kesişimi 0 (yanlış-film şüphesi)
- **OCR:** GUVENILIR, **Süre:** 986sn

### BAHAR VE ŞARAP (1970-0061-1-0000-00-1)
- **Tip:** YONETMEN_KIMLIK_CAST_OZET
- **Sınıflar:** siniflandirilamadi, teknik_hata, kunye_kalite_qc1
  - LLM katmanı çalışmadı (ollama model deposu boş/erişilemez — film yeniden koşulmalı)
  - OCR bucket=HATA
  - QC1 başarısız (OCR+VL ikisi de RED — düşük künye kalitesi, OCR yetersiz)
- **OCR:** HATA, **Süre:** 326sn

### BANA TRINITY DERLER (1968-0082-1-0000-00-1)
- **Tip:** YONETMEN
- **Sınıflar:** kunye_kalite_qc1, kunye_okuma, kunye_okuma
  - QC1 başarısız (OCR+VL ikisi de RED — düşük künye kalitesi, OCR yetersiz)
  - yönetmen okunamadı (KB-fill yok — kırmızı çizgi)
  - yönetmen doğrulama: okunamadı (yeniden-okuma/insan)
- **OCR:** GUVENILIR, **Süre:** 732sn

### BAŞKASININ KARISI (1995-0282-1-0000-00-1)
- **Tip:** YONETMEN_KIMLIK_RENDER
- **Sınıflar:** kunye_kalite_qc1, kimlik_celiski, yonetmen_yapimci
  - QC1 başarısız (OCR+VL ikisi de RED — düşük künye kalitesi, OCR yetersiz)
  - kimlik çelişkisi (KB cross-check)
  - qwen: yön+yapımcı yok
- **OCR:** GUVENILIR, **Süre:** 1189sn

### BELL BOY (1960-0039-1-0000-00-1)
- **Tip:** YONETMEN_KIMLIK_CAST
- **Sınıflar:** kunye_kalite_qc1, kimlik_celiski, cast_bos
  - QC1 başarısız (OCR+VL ikisi de RED — düşük künye kalitesi, OCR yetersiz)
  - kimlik çelişkisi (KB cross-check)
  - qwen: oyuncu yok
- **OCR:** GUVENILIR, **Süre:** 474sn

### BENİ UNUTMA (2002-9259-1-0000-00-1)
- **Tip:** YONETMEN
- **Sınıflar:** render, kunye_kalite_qc1, kunye_okuma
  - PDF render yok (md teslim)
  - QC1 başarısız (OCR+VL ikisi de RED — düşük künye kalitesi, OCR yetersiz)
  - yönetmen doğrulama: okunamadı (yeniden-okuma/insan)
- **OCR:** GUVENILIR, **Süre:** 514sn

### BENİ UNUTMA (2002-9259-1-0000-00-1)
- **Tip:** YONETMEN
- **Sınıflar:** kunye_kalite_qc1, kunye_okuma, kunye_okuma
  - QC1 başarısız (OCR+VL ikisi de RED — düşük künye kalitesi, OCR yetersiz)
  - yönetmen okunamadı (KB-fill yok — kırmızı çizgi)
  - yönetmen doğrulama: okunamadı (yeniden-okuma/insan)
- **OCR:** GUVENILIR, **Süre:** 633sn

### BERLİN ALEKSANDER MEYDANI (1987-1125-1-0000-00-1)
- **Tip:** KIMLIK_RENDER
- **Sınıflar:** kimlik_celiski, yonetmen, kimlik_zayif
  - kimlik çelişkisi (KB cross-check)
  - yönetmen VL-dolumu (fuzzy teyidi — insan onayı bekler)
  - qc_block: kimlik kurulamadı (cast-örtüşme<2, web çapası kilitlenemedi)
- **OCR:** GUVENILIR, **Süre:** 330sn
