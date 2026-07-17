# MITAS — Genel Durum Özeti
*(2026-07-05 itibarıyla)*

## Nedir, Neden Var
MITAS, TRT arşivindeki eski film/dizi kayıtlarını otomatik işleyip standart bir **"künye"** (yönetmen, oyuncu, yapımcı, tür, özet, ses/dil, afiş) çıkaran bir video-işleme boru hattı. Amaç: binlerce arşiv kaydını minimum insan emeğiyle, yüksek doğrulukla künyeleyip teslime hazır hale getirmek.

**Kurucu ilke** (sistemin tamamı bunun üzerine kurulu): Filmin kendi jeneriğinden **OCR ile okunan bilgi tek gerçek kaynaktır**. İnternet/bilgi tabanı (IMDb, Wikidata) bu bilgiyi hiçbir zaman **ezmez** — sadece yazım hatasını düzeltir veya OCR'ın boş bıraktığı alanı doldurur. Bu kural, geçmişte yaşanan "yanlış film verisiyle künyenin ezilmesi" olaylarından sonra kesinleşti ve tüm mimari buna göre kuruldu.

## Ne Yapabiliyor (Uçtan Uca Akış)
Bir video girdi verildiğinde sistem otomatik olarak:
1. **ASR** — Türkçe (gerekirse yabancı dil) konuşma tanıma ile transkript çıkarır
2. **OCR / jenerik okuma** — açılış-kapanış künye karelerini okuyup yönetmen + yapımcı + oyuncu kadrosu + tür bilgisini çıkarır
3. **Çapraz-doğrulama** — IMDb/Wikidata ile karşılaştırır (ezmeden, yalnız teyit/destek)
4. **Özet** — olay örgüsü özetini (spoiler dâhil) bulut LLM ile üretir
5. **Ses/dil kontrolü** — ana dil ve altyazı tutarlılığını denetler
6. **Afiş** — IMDb/TMDB/Wikipedia'dan görsel bulur
7. **Kalite kontrol** — görsel-LLM ile künyenin tutarlılığını denetler
8. **Rapor** — standart PDF + markdown üretir, otomatik **"Hazır"** (onaylı) / **"Kontrol"** (insan bakmalı) olarak etiketler

Bir WebUI üzerinden filmler kuyruğa alınıp pipeline'ın aşama aşama ilerleyişi canlı izlenebiliyor. Toplu (batch) işlemede bugüne dek 1000+ film işlenmiş durumda.

## Güncel Doğruluk Durumu
*(son geniş denetim: 117 film, 03-04 Temmuz 2026, ekran-kanıtına dayalı)*

| Alan | Sonuç |
|---|---|
| **Yönetmen** (alan doluysa) | 74 örnekte **%89 doğru** (66 doğru / 7 yanlış / 1 şüpheli) — 7 yanlışın hepsi ekrandan teyit edilip kök nedeni bulundu, düzeltmeler canlıda |
| **Oyuncu kadrosu** | 103 filmde **%77 temiz** (79 temiz / 22 sorunlu / 2 boş) — en büyük hata kaynağı ekip-isimlerinin oyuncuya karışması ve iki-kolonlu jeneriklerde karakter-adı/oyuncu-adı karışıklığı |
| **Yapımcı** | 49 temiz / 22 sorunlu / 32 bilinçli boş (OCR'da hiç görünmüyorsa doldurulmaz — "okunamadı, yanlış okumaktan iyidir" ilkesi) |

Bu hafta canlıya alınanlar: 4 kök-neden düzeltmesi (isim-klonu çökertme, ekip-bağlamı genişletme, yapımcıda alt-rol dışlama, bilgi-tabanı toleransı), karakter-adı/oyuncu karışıklığının kök çözümü, ve PDF'e otomatik **"Film Notu"** kutusu (sessiz film / jenerik yok / animasyon gibi durumları deterministik tespit edip standart not düşüyor; animasyon filmlerde oyuncu alanı bilinçli boş bırakılıyor çünkü isimler seslendirme sanatçısı).

## Altyapı Olayı
3 Temmuz'da harici bir diskin değişmesi 5 üretim LLM modelini aynı anda düşürdü; bir süre fark edilmeden LLM'siz künye üretildi. Çözüldü: modeller sabit yerel diske taşındı + LLM erişilemezse filmi sessizce işlemek yerine otomatik **"Kontrol"**e düşüren bir güvenlik denetimi eklendi.

## Performans
Ölçülen hız **~890 sn/film (~4 film/saat)** — tek GPU'nun seri kullanımı bunun sebebi. Üç aşamalı bir hızlandırma planı onaylandı; ilk güvenli aşama (model bekletme ayarı, bilgi-tabanının yerel diske kopyalanmasıyla **19 kat** hızlanma, VRAM taşma valfi) canlı. İleri fazlarla hedef **~8-10 film/saat**.

## Teknoloji Yığını

| Katman | Teknoloji |
|---|---|
| Platform | Windows, tek makine, RTX 3090 24GB GPU (GPU-kilitli seri işleme) |
| Backend / Pipeline | Python + FastAPI/uvicorn (`core/api/`) |
| WebUI | React 18 + TypeScript + Vite, Tailwind/Radix-UI, Recharts |
| ASR (konuşma tanıma) | faster-whisper large-v3-turbo (hızlı) → kalite sinyali tetiklenirse large-v3'e otomatik yükseltme |
| OCR | OneOCR (üretimde ana motor) + PaddleOCR / GLM-OCR (yedek/deney) + çok-kolonlu künye kareleri için özel "stitch" birleştirme katmanı |
| Yerel LLM (Ollama) | gemma-4-31b (künye rol-çıkarımının ana motoru), gemma4:26b/gemma3:12b (görsel yedek + yerel özet yedeği), qwen3 / qwen2.5vl / glm-ocr (yardımcı) |
| Bulut LLM | Gemini 2.5-flash (özet üretimi, birincil), Claude (yedek + geliştirme sürecinin kendisi) |
| Bilgi tabanı | SQLite (mitas.db, iş/proje takibi) + DuckDB: Wikidata (~20GB) + IMDb (~12GB) kopyaları, hız için yerel diske senkronize |
| Dış servis | TMDB / OMDb / Wikipedia (afiş görseli) |
| Veri modeli | JSON Schema tanımlı kayıtlar (media_item, timeline_event, evidence, job_run) — modüler/izlenebilir yapı |
| Geliştirme aracı | `council_mcp/` — teknik kararlar için çoklu-LLM danışma sunucusu (Gemini/Qwen/GLM/GPT) |

## Açık Noktalar
- Bazı dillerde (Rusça/Fransızca jenerik düzeni) karakter-adı/oyuncu karışıklığı tam çözülmedi
- Hızlandırma planının ileri fazları (GPU/CPU iş örtüşmesi, +%35-50 hedefi) onay bekliyor
- 89 filmlik yeniden-koşu (bu haftaki düzeltmelerin üretime yansıması) + yeni model pilotu sırada
