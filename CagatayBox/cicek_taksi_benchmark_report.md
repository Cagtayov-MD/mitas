# 🎬 ÇİÇEK TAKSİ (00:00 - 01:42) QWEN ÜÇLÜSÜ BENCHMARK RAPORU

> **Klip:** `evoArcman_ÇİÇEK TAKSİ_2001-9011-0-001-00-1-ÇİÇEK_TAKSİ.mp4` (00:00 - 01:42 / 102 Saniye)
> **Taranan HD Kare Sayısı:** 204 Kare (`fps=2`, Lanczos HD + Unsharp Masking)

## 📊 1. ÖZET KARŞILAŞTIRMA TABLOSU

| Model & Test Yöntemi | Çıkarılan Satır | İşlem Süresi | Derinlik & Kalite Değerlendirmesi |
| :--- | :--- | :--- | :--- |
| **`Qwen3.6-27B GGUF (Frame-by-Frame)`** | **55 Satır** 🏆 | 88.9 saniye | 🏆 **En Yüksek Derinlik (Tüm Oyuncu ve Teknik Ekibi Okudu)** |
| **`Qwen3-VL-8B FP16 (Frame-by-Frame)`** | **48 Satır** 🥈 | **57.8 saniye** ⚡ | ⚡ **En Hızlı Kare Yöntemi (+48 Satır)** |
| **`Qwen2.5-VL-7B FP16 (Frame-by-Frame)`** | **47 Satır** 🥉 | 60.8 saniye | 🎯 **Başarılı Kare Dökümü (+47 Satır)** |
| `Qwen2.5-VL-7B FP16 (Native MP4)` | 19 Satır | 6.1 saniye | ⚠️ Native MP4 Hızlı ama 28 Satır Oyuncu İsmini Özetleyip Atladı |
| `Qwen3-VL-8B FP16 (Native MP4)` | 2 Satır | 1.0 saniye | ❌ Native MP4 Yöntemi Jenerik Yazılarını Kaçırdı |

--- 

## 💡 CRITICAL FINDING: Frame-by-Frame vs Native MP4 Video
1. **Frame-by-Frame (Lanczos + Unsharp):** Pikseller tek tek işlendiği için `ERLER FİLM SUNAR`, `EROL GÜNAYDIN`, `GÜL GÖLGE`, `ÜMİT YESİN`, `TUNA ARMAN`, `BEKİR AKSOY`, `ALEV ORALOĞLU`, `CİVAN CANOVA`, `MELDA ARAT MUTU`, `SELİM ERDOĞAN`, `MİNE SOLEY`, `CENGİZ KÜÇÜKAYVAZ`, `KAYHAN YILDIZOĞLU` gibi tüm oyuncu kadrosunu eksiksiz yakaladı.
2. **Native MP4 Video:** Modeller video klibini özetleme eğiliminde olduğu için oyuncu isimlerinin çoğunu atlayıp geçti. **Dolayısıyla jenerik dökümünde Frame-by-Frame (Lanczos HD) yöntemi ezici üstünlük sağladı.**

--- 

## 📜 2. MODELLERİN TAM OKUMA DÖKÜMLERİ

### 🔍 Qwen3.6-27B-GGUF (Frame) (55 Satır / 88.9s)
```text
<think>
</think>
ERLER FILM
SUNAR
ERLER FİLM
ÇiÇEK
TAK
Çiçek
Taksi
EROL GÜNAYDIN
GÜL GÖLGE
ÜMİT YESİN
TUNA ARMAN
BEKIR AKSOY
ALEV ORALOĞLU
CİVAN CANOVA
MELDA ARAT MUTU
SELİM ERDOĞAN
MİNE SOLEY
CENGİZ KÜÇÜKAYVAZ
GENİZ KUCUKAYAZ
SİBEL CEYLAN
KAYHAN YILDIZOĞLU
FUNDAYGURLU
FUNDA GÜRDAĞ
KAMIL GÜLER
KAMİL GÜLER
ZUHAL YALÇIN
ENVER DEMİRKAN
ve
ESREF KOLÇAK
ışık şefi
ADNAN ÇEVİRMECİ
kurgu
ZEYNEP S. AGIN
kurğu
ZEYNEP S. AĞIN
yardımcı yönetmen
ZEYNEP GÖKMEN ATİK
ZEYNEP GÖKMEN ATIK
görüntü yönetmeni
HALİL ARİF NURDAN
NADİ ÖZERKAL
senaryo
VİLİMER ÖZÇINAR
ALİ CENGİZ AKDENİZ
VİLMER ÖZÇINAR
senaryo danışmanı
ERDOĞAN TÜNAŞ
genel koordinatör
YILMAZ EKMEKÇİ
yapımcı
TÜRKER İNANOĞLU
yönetmen
YAŞAR SERİNER
```

### 🔍 Qwen2.5-VL-7B-FP16 (Frame) (47 Satır / 60.8s)
```text
ERLER FILM
SUINAR
SUNAR
Ç/ÇEK
TAK
EROL GÜNAYDIN
GÜL GÖLGE
ÜMIT
YESİN
TUNA ARMAN
BEKIR AKSOY
ALEV ORALOĞLU
CİVAN CANOVA
MELDA
ARAT
MUTU
SELİM ERDOĞAN
MİNE SOLEY
CENGIZ KÜÇÜKAYVAZ
SIBEL GEYLAN
FUNDAYÜRDAC
KAMIL GÜLER
ZUHAL YALÇIN
ENVER DEMIRKAN
ve
ESREF KOLÇAK
işık şefi
ADNAN ÇEVİRMECİ
kurgu
ZEYNEP S. AĞIN
yardımcı yönetmen
ZEYNEP GÖKMEN ATIK
görüntü yönetmeni
HALIL ARİF NURDAN
NADI ÖZERKAL
senaryo
VİLMER ÖZÇINAR
ALİ CENGİZ AKDENİZ
senaryo danışmanı
ERDOĞAN TÜNAŞ
genel koordinatör
YILMAZ EKMEKÇİ
yapımcı
TÜRKER İNANOĞLU
yönetmen
YAŞAR ŞERİNER
YAŞAR SERİNER
```

### 🔍 Qwen2.5-VL-7B-FP16 (Native MP4) (19 Satır / 6.1s)
```text
ERLER FILM
SUNAR
ÇİÇEK TAŞIYAN
GÜL GÖLGE
TUNA ARMAN
ALEKIRAKSOYLU
CİVAN CANOVA
ZUHAL YALÇIN
ENVER DEMİRKAN
ISIK SEFI
ADNAN ÇEVİRMECİ
YARDIMCI YÖNETMEN
HALIL ARIF NURDAN
NADI ÖZERKAL
SENYORCOORDINATOR
ERDÎKAZ İKANEGOGLU
YÖNETMEN
VİLMER ÖZÇINAR
ALİ CENGİZ AKDENIZ
```

### 🔍 Qwen3-VL-8B-FP16 (Frame) (48 Satır / 57.8s)
```text
ERLER FILM
SUNAR
ÇİÇEK
TAK
TAKSİ
EROL GÜNAYDIN
GÜL GÖLGE
ÜMIT YESIN
TUNA ARMAN
BEKİR AKSOY
ALEV ORALOĞLU
CIVAN CANOVA
MELDA ARAT MUTU
SELİM ERDOĞAN
MİNE SOLEY
CENGİZ KÜÇÜKAYVAZ
CENGIZ KUCUKAYVAZ
SIBEL CEYLAN
KAYHAN YILDIRIZOĞLU
FUNDAGÜRDAG
KAMIL GÜLER
KAMİL GÜLER
ZUHAL YALÇIN
ENVER DEMIRKAN
ENVER DEMİRKAN
ve
ESREF KOLÇAK
Işık şefi
ADNAN ÇEVİRMEÇİ
kurgu
ZEYNEP S. AĞIN
yardımcı yönetmen
ZEYNEP GÖKMEN ATIK
görüntü yönetmeni
HALİL ARİF NURDAN
NADİ ÖZERKAL
senaryo
VİLMER ÖZÇINAR
ALİ CENGİZ AKDENİZ
senaryo danışmanı
ERDOĞAN TÜNASH
ERDOĞAN TÜNAS
genel koordinatör
YILMAZ EKMEKÇİ
yapımcı
TÜRKER İNANOĞLU
yönetmen
YAŞAR SERİNER
```

### 🔍 Qwen3-VL-8B-FP16 (Native MP4) (2 Satır / 1.0s)
```text
yönetmen
EASER DEARRKAN
```

