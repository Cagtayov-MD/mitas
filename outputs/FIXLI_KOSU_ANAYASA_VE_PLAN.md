# FİXLİ KOŞU — Çağatay Anayasası ve İş Planı

> **Tek cümle amaç:** Framede okunan isimleri **KAÇIRMA** — garble'ı KB/teyitle doğruya çevirip kurtar,
> ama **yanlış-okumayı doğru diye PDF'e YAZMA** (Kemal Sunal → "Kamal Sunay" ise, düzeltilemiyorsa PDF'e girmez).
> Her Kontrol vakasını tek tek **İNCELE → BUL → ÇÖZ → FİXLE**; hedef Kontrol'ü **~60'a** indir. **Sonuç alana kadar DUR YOK.**

---

## 1) ANAYASA (bozulmaz kurallar)

1. **Framede DOĞRU okunan isim PDF'e girer — ama yanlışı doğru diye YAZMA.** OneOCR "Kemal Sunal"ı
   "Kamal Sunay" okuduysa ve düzeltilemiyorsa PDF'e YANLIŞ haliyle GİRMEZ; Kontrol'de kalır.
   **Amaç bu isimleri KAÇIRMAMAK** (garble'ı KB/Wiki/IMDb/teyitle doğruya çevirip kurtarmak).
   Kontrol YALNIZ: framede-yok / okunamadı / alfabe-bozuk / kaynak-çelişkisi / düzeltilemeyen-garble.
2. **Her vaka tek tek:** İNCELE → BUL (kök-neden) → ÇÖZ → FİXLE. Toplu-varsayım yok.
3. **Okunamadı > yanlış-oku.** Doğrulanmamış isim ASLA yazılmaz (KB / Wiki / IMDb / XML / VL ile teyit).
4. **Çalışanı bozma.** Golden 6/6 korunur, byte-nötr, kill-switch'li, additive. 65 Hazır'a dokunma.
5. **Sonuç alana kadar dur yok.** Hedef tutmazsa yeni mahkeme-turu.

---

## 2) ŞU ANKİ DURUM (başlangıç noktası)

- **287 film** izleniyor · **65 Hazır / 222 Kontrol** · **Hedef: Kontrol ~60**
- Kontrol sebepleri (**ÇAKIŞAN** — bir film aynı anda birden çok sebeple Kontrol'de; bu yüzden sayılar toplanmaz):

  | Sebep | Film | Anlamı |
  |---|---|---|
  | YÖNETMEN garble | 122 | yönetmen framede var ama garble okundu → boş |
  | KİMLİK kurulamadı | 105 | cast-örtüşme eşiği tutmadı → kimlik kilitlenemedi |
  | ÖZET yok | 55 | gerçek özet üretilmemiş (ASR tarafı) |
  | CAST yok | 55 | oyuncu okunamadı |
  | RENDER Latin-dışı | 42 | Kiril/Yunan/Arapça alfabe |
  | *(neden)* LLM çalışmadı | 24 | **SAHTE Kontrol** — ollama düştüğünde koşan filmler (altyapı, kalite değil) |

- **Kritik teknik gerçekler:**
  - Frameler + OCR **cached** → yeniden koşuda **video GEREKMEZ** (pipeline --video'yu sadece giriş-kimliği için ister; 139 filmde bu yol taşınmış).
  - **Okuma VL-stokastik** (tek model `gemma-4-31b-it-qat-vision`): aynı film iki koşuda farklı çıkabilir
    (TOPLU GÖSTERİLER → bir koşuda "Vincente Minnelli", diğerinde "VincenTe Minnati").
    → **Standalone tek-model re-run GÜVENİLMEZ.** Doğru yol = **TAM PIPELINE** (VL + KB-fuzzy-kanonik + QC katmanları birlikte). Golden'ın çalışma sebebi de tam-yolun katmanları.

---

## 3) İŞ AKIŞI (5 kol — /loop)

**(a) İZLE:** kuyruk ilerleme (`queue.json`) + `NOBETCI.log` çapraz-kontrol + anomali-monitör.

**(b) FİX-ETKİ örneklemi:** biten filmlerde resmî koşu doğrulaması —
- AYAK TAKIMI / BAŞKAN VE MARI / CENNETE resmî koşuda da **doğru** mu?
- CAP / özet / kimlik **aileleri Hazır'a döndü mü?**
- Dönmeyenlerde **reason-kalıntısını KÖK-KAZI et ve fixle.**

**(c) VAKA-VAKA (kalan meşrular):** okunamadı-ağır-garble sınıfı (OSCAR / TAKKELİ / KOLEKSIYON …) →
**K2-VL dilim-tanık pilotu** (gemma-26b mod-A), **3 filmde** dene; isim çıkarsa **ÇİFT-KANIT** şartıyla değerlendir.

**(d) ALFABE-BOZUK:** 4+3 film için **Kiril / Arapça translit** çözüm araştır (`translit_util` mevcut).

**(e) RAPOR:** koşu bitince **SINIF-BAZLI ÖNCE/SONRA tablosu** + rapor.
Kontrol ~60 **tutmazsa → yeni mahkeme-turu.**

---

## 4) BAŞARI ÖLÇÜTÜ

- Her Kontrol-olmayan film **sebep-etiketli.**
- **Gerçek-kayıp (framede-var / PDF'te-yok) = 0.**
- Kontrol **~60** (meşru kalan: sessiz-film / belgesel / gerçekten-okunamayan / Latin-dışı-çözülemeyen).
- **Sınıf-bazlı önce/sonra** raporu teslim.

---

## 5) YÖNTEM UYARILARI (bu tuzaklara düşme)

- Ara-artefakt (master-png footage/kozmetik) **kovalanmaz** — okuyucu zaten ayıklar; odak "isim PDF'e ulaşıyor mu".
- "Önce temiz GPU / önce ölçüm / önce doğrulama" gibi **istenmeyen ön-adım İCAT ETME** — doğrudan işi yap.
- Kör-batch re-run yok (VL-stokastik → garble PDF riski) — **tam-pipeline + çift-kanıt.**
- Basit işi karmaşıklaştırma. Engelde büyütme, basitleş.
