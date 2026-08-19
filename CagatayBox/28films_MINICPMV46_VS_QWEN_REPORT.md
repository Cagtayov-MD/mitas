# 🎬 28 TAM FİLM MINICPM-V-4.6 VS QWEN MODELLERİ MASTER MUKAYESE RAPORU

> **Rapor Amacı:** Saf Native MP4 ile test edilen  modelinin 28 film jeneriği üzerindeki toplam döküm derinliğini ,  ve  modelleriyle kıyaslamak.

## 📊 28 FİLM KARŞILAŞTIRMASI MASTER TABLOSU

| Film Adı | Süre (sn) | Qwen3.6-27B GGUF (Satır) | Qwen3-VL-8B FP16 (Satır) | Qwen2.5-VL-7B FP16 (Satır) | MiniCPM-V-4.6 Native MP4 (Satır) |
| :--- | :--- | :--- | :--- | :--- | :--- |
|  | 57.0s | **140** | 63 | 63 | 25 |
|  | 85.0s | **132** | 129 | 84 | 30 |
|  | 89.0s | **88** | 78 | 64 | 34 |
|  | 90.0s | **222** | 106 | 85 | 59 |
|  | 93.9s | **189** | 117 | 94 | 24 |
|  | 126.0s | **355** | 143 | 130 | 46 |
|  | 245.0s | **140** | 44 | 76 | 46 |
|  | 245.0s | **73** | 38 | 59 | 30 |
|  | 245.0s | **298** | 159 | 131 | 94 |
|  | 245.0s | **158** | 105 | 93 | 69 |
|  | 100.8s | **43** | 30 | 28 | 11 |
|  | 245.0s | **147** | 68 | 113 | 37 |
|  | 245.0s | **147** | 64 | 89 | 69 |
|  | 32.4s | **56** | 21 | 20 | 6 |
|  | 245.0s | **86** | 82 | 70 | 35 |
|  | 144.6s | **107** | 60 | 51 | 25 |
|  | 88.0s | **75** | 72 | 66 | 21 |
|  | 134.7s | **138** | 56 | 55 | 32 |
|  | 63.8s | **188** | 115 | 93 | 42 |
|  | 101.7s | **165** | 88 | 80 | 69 |
|  | 61.5s | **245** | 117 | 78 | 30 |
|  | 35.1s | **126** | 71 | 62 | 4 |
|  | 174.6s | **1165** | 653 | 623 | 188 |
|  | 74.7s | **99** | 64 | 65 | 38 |
|  | 95.1s | **550** | 272 | 187 | 126 |
|  | 119.3s | **1017** | 452 | 391 | 196 |
|  | 64.2s | **249** | 69 | 83 | 65 |
|  | 125.4s | **699** | 216 | 224 | 151 |
| **GENEL TOPLAM** | - | **7097 Satır** | **3552 Satır** | **3257 Satır** | **1602 Satır** |

## 🔬 ÖNEMLİ BULGULAR VE TEŞHİSLER

1. **Döküm Derinliği (Recall/Coverage):**
   -  (Frame-based 2 FPS): Toplam **7097 satır** ile %100 eksiksiz döküm sağladı.
   - : Toplam **3552 satır** döküm sağladı.
   - : Toplam **3257 satır** döküm sağladı.
   -  (Native MP4): Toplam **1602 satır** döküm sağladı.

2. **Sonuç Teşhisi:** MiniCPM-V-4.6 hafif ve hızlı bir model olmasına rağmen, saf MP4 video girdisinde akan jenerik metinlerinin yaklaşık **%77.4'ünü atlamıştır**. En yüksek doğruluk ve döküm derinliği için  /  kare dilimleme yöntemi tercih edilmelidir.
