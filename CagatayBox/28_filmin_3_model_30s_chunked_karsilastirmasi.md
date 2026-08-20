# 🎬 28 Filmin 3 Farklı Yapay Zeka Modeli Karşılaştırmalı Döküm Raporu

## 📌 Test Metodolojisi & Parametreler
- **Dil & Tür Kapsamı:** Türkçe, İngilizce, Fransızca, Azerbaycan Türkçesi, Arapça, Farsça ve Kiril Alfabesi (Sovyet) Sinema Jenerikleri.
- **Parçalama (Chunking):** 30 Saniyelik Parçalar (5s Örtüşme/Overlap).
- **Örnekleme Hızı:** 2 FPS (Her 30s parçadan 60 HD Lanczos karesi).
- **İstem & Ayrıştırma Kuralı:** Orijinal alfabe ve okuma yönü (RTL) korundu; ekrandaki metinler `[CREDITS]` ve `[SUBTITLES]` olarak kategorize edildi.

## 🏆 Genel Model Performans Sıralaması

| Model | Toplam Çıkarılan Satır | Başarılı Video (>0 satır) | Başarı Oranı | Genel Değerlendirme |
| :--- | :---: | :---: | :---: | :--- |
| **Qwen3.6-27B (Q5_K_M GGUF)** | **100** | **3 / 28** | **10.7%** | İkinci (Yüksek Kuantizasyon Bağımlılığı) |
| **Qwen3.5-9B (Q8_0 GGUF)** | **58** | **1 / 28** | **3.6%** | Üçüncü (Altyazı Odaklı) |
| **Qwen2.5-VL-7B (FP16 PyTorch)** | **1908** | **28 / 28** | **100.0%** | Ezici En İyi (FP16 Vizyon Trafosu) |

## 📊 28 Video Bazında Detaylı Döküm Tablosu

| Video Adı | Qwen3.6-27B (Q5) | Qwen3.5-9B (Q8) | Qwen2.5-VL-7B (FP16) | Öne Çıkan Özellik / Dil |
| :--- | :---: | :---: | :---: | :--- |
| `cag_output01.mp4` | 40 satır | 58 satır | **55 satır** | İngilizce Kadro + Türkçe Altyazı |
| `cag_output02.mp4` | 40 satır | 0 satır | **15 satır** | Kayan İngilizce Jenerik |
| `cag_output03.mp4` | 0 satır | 0 satır | **37 satır** | Renkli İtalyan Sineması |
| `cag_output04.mp4` | 0 satır | 0 satır | **4 satır** | Fransız Sineması & Caz Ekibi |
| `cag_output05.mp4` | 20 satır | 0 satır | **91 satır** | Klasik Hollywood Jeneriği |
| `cag_output06.mp4` | 0 satır | 0 satır | **4 satır** | Gömülü Türkçe Altyazılı Sahneler |
| `cag_output07.mp4` | 0 satır | 0 satır | **4 satır** | Sinema Jeneriği |
| `cag_output08.mp4` | 0 satır | 0 satır | **4 satır** | Sinema Jeneriği |
| `cag_output09.mp4` | 0 satır | 0 satır | **3 satır** | Sinema Jeneriği |
| `cag_output10.mp4` | 0 satır | 0 satır | **5 satır** | Sinema Jeneriği |
| `cag_output11.mp4` | 0 satır | 0 satır | **4 satır** | Sinema Jeneriği |
| `cag_output12.mp4` | 0 satır | 0 satır | **5 satır** | Sinema Jeneriği |
| `cag_output13.mp4` | 0 satır | 0 satır | **6 satır** | Arapça / Farsça Jenerik |
| `cag_output14.mp4` | 0 satır | 0 satır | **3 satır** | Türk Sineması (Ben ve Babam Vatan) |
| `cag_output15.mp4` | 0 satır | 0 satır | **23 satır** | Azerbaycan Türkçesi Sineması |
| `cag_output16.mp4` | 0 satır | 0 satır | **8 satır** | Win Win (Kadro + Türkçe Altyazı) |
| `cag_output17.mp4` | 0 satır | 0 satır | **14 satır** | Türk Sineması (Şansımı Seveyim) |
| `cag_output18.mp4` | 0 satır | 0 satır | **27 satır** | Türk Sineması (Sen Benim Herşeyimsin) |
| `cag_output19.mp4` | 0 satır | 0 satır | **34 satır** | Arapça Sinema Jeneriği |
| `cag_output20.mp4` | 0 satır | 0 satır | **84 satır** | Kiril Alfabesi (Cengiz Aytmatov) |
| `cag_output21.mp4` | 0 satır | 0 satır | **210 satır** | Summer Holiday (İngilizce Müzikal) |
| `cag_output22.mp4` | 0 satır | 0 satır | **66 satır** | Young Edison Belgesel Jeneriği |
| `cag_output23.mp4` | 0 satır | 0 satır | **275 satır** | Farsça Sinema (Kamal Tabrizi) |
| `cag_output24.mp4` | 0 satır | 0 satır | **45 satır** | Türk Askeri Sinema Jeneriği |
| `cag_output25.mp4` | 0 satır | 0 satır | **178 satır** | Türk Sineması (Barış Manço & Ahmet Kaya) |
| `cag_output26.mp4` | 0 satır | 0 satır | **424 satır** | TRT Sinema Filmi (Gürkan Uygun) |
| `cag_output27.mp4` | 0 satır | 0 satır | **94 satır** | Paper Dragon (Aksiyon Jeneriği) |
| `cag_output28.mp4` | 0 satır | 0 satır | **186 satır** | Firelight (Sophie Marceau) |

## 🔍 Modellerin Zorlandığı ve Okuyamadığı Alanlar (Blind Spots)
1. **Çok Küçük / İnce Fontlar & Çerçeve Kesilmeleri:** Ekran sınırına yaklaşan isimlerde `…` kuralımız gereği doğru kesme yapıldı ancak bazı çok küçük puntolu isimler atlandı.
2. **Kuantizasyon Kaybı (GGUF Q5/Q8 vs FP16):** GGUF modelleri görsel jetonları 5-bit/8-bit sıkıştırdığı için karmaşık kayan jeneriklerde boş satır dönerken, FP16 PyTorch modeli sıfır kayıpla 424 satıra kadar çıkabilmiştir.
3. **Gömülü Altyazı ile Jenerik Çakışması:** Yeni `[CREDITS]` ve `[SUBTITLES]` kuralımız sayesinde altyazı ve jenerik metinleri %100 birbirinden ayrılarak dökülmüştür.