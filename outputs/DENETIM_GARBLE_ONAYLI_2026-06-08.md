# DENETİM — Künye garble + kontaminasyon (ONAYLI kaçağı)
Tarih: 2026-06-08 · Tetikleyen: ÇANAKKALE ARSLANLARI Yapımcı alanı çöp OCR

## Özet
- Taranan üretilmiş künye: **45** (Database/*/pdf/kunye_teslim.md)
- Karar dağılımı: **5 Hazır (ONAYLI)** · **39 Kontrol** · 1 karar yok
- **ONAYLI'da KESİN bozuk: 3 / 5** → ÇANAKKALE ARSLANLARI, KRAL OİDİPUS, UYANIŞ
- KAÇAK + LİSEDE PANİK: yalnız düşük-güven sinyal (büyük ihtimal temiz, FP)

## KÖK NEDEN
QC kapısı ([mitas_pipeline.py:887-984](../scripts/mitas_pipeline.py)) yalnız **yapı / kodlama / varlık / dil / KB-çapraz** ölçer.
**"Harfler geçerli Türkçe ama kelime gerçek bir kelime mi / çöp mü"** diye bakan TEK kontrol yok.
Garbled metin (TÜNK SİLAHU KUYVETLENİ) geçerli Türkçe harflerden (Ü/İ/Ş) oluştuğu için:
- isim-QC Latin-dışı kemeri → temiz
- qwen `turkce_karakter_bozuk_var` → false (harfler render oluyor, kelimeler çöp)
- yön+yapımcı/oyuncu "var" → alanlar dolu

Asıl savunma olması gereken `_guard` ([credit_text_read.py:129](../scripts/credit_text_read.py)) bir
**halüsinasyon kalkanı**, garble kalkanı DEĞİL: temel kuralı "her token OCR'da geçmeli" — garbled
OCR parçaları tanımı gereği OCR'dan geldiği için bu kalkanı **garanti geçer**.

## ÖNEMLİ: kapı kontaminasyonu ŞANS ESERİ yakalıyor
KONTROL'e düşen kontamine filmlerin gerçek nedeni garble DEĞİL, başka sinyal:
- PİNOKYO, AĞABEYİM JACK → "yönetmen okunamadı"
- İKİLİ OYUN, GÖLGE SAVAŞÇI, ASİ, BÜYÜKANNEM, ÖNCE AĞLARSIN → "kimlik çelişkisi (KB cross-check)"

3 bozuk ONAYLI film bu sinyalleri tetiklemedi çünkü garble içinde **KB-doğrulanabilir bir yönetmen** vardı
(ÇANAKKALE: TURGUT N. DEMİRAĞ · KRAL OİDİPUS: DON TAYLOR · UYANIŞ: MİKE NEWELL) → diğer çöp eklerle
birlikte ONAYLI'ya geçti. neden=[] üçünde de.

---

## 🔴 ONAYLI — KESİN BOZUK (3)

### ÇANAKKALE ARSLANLARI (1975-0149-1-0000-00-1) — AĞIR
Tek bir jenerik cümlesi ("TSK'nın müştereken çevirdiği... Çanakkale Arslanları") kayan karelerde
defalarca yanlış okunup oyuncu/yönetmen/yapımcı kutularına dağılmış:
- Oyuncu + Yapımcı: `TÜRK SİLAHLI KUVVETLERİ` (kurum, kişi değil)
- Yapımcı: `MÜŞTEREKEN ÇEVİRDİĞİ` (fiil/cümle), `PİİMİM SOMR`, `FİLMHİ SANAK`, `ARSUANL ARI` (=filmin adı)
- garble-varyant: `TÜRK SİLAHLI KUVVETLERİ`≈`TÜNK SİLAHU KUYVETLENİ` · `VAVIZ KARAKAC`≈`YAVUZ KARAKAŞ` · `MUÇTEREEN ÇEVİNPİEİ`≈`MÜŞTEREKEN ÇEVİRDİĞİ`
- cast↔yapımcı kontaminasyon + başlık-parçası

### KRAL OİDİPUS (1986-0204-1-0000-00-1)
- Oyuncu: `CI IORUS QF` (="CHORUS OF"), `THEBAN SENATORS` (karakter grubu, oyuncu değil)
- Yönetmen: `MAKS-UP BASIGNER` (="MAKE-UP DESIGNER" rol etiketi). Gerçek yönetmen DON TAYLOR garble arasında.

### UYANIŞ (1980-0166-1-0000-00-1)
- Yönetmen alanına 3 OYUNCU sızmış: `SUSANNAH YORK`, `JİLL TOWNSEND`, `PATRİCK DRURY`. Gerçek yönetmen yalnız MİKE NEWELL.

## 🟡 ONAYLI — şüpheli (düşük güven, muhtemelen temiz)
- **KAÇAK**: `MİCHAEL CRİCHTON`≈`MİCHAEL RACHMİL` (69%) — ikisi de gerçek ayrı kişi, FP olası.
- **LİSEDE PANİK**: `DANIEL PETRIE, JR.`≈`DANIEL PETRIE` (81%) — JR/baba-oğul veya tekrar; garble değil.

---

## KONTROL kovasında kontaminasyon (doğru ayrılmış — referans)
PİNOKYO (PRODACERS~PRODUCER + Landau/Patel cast→yapımcı), İKİLİ OYUN (Russo/Leary cast→yönetmen),
GÖLGE SAVAŞÇI, BÜYÜKANNEM, ASİ (DIRECTON~DIRECTOR), AĞ (AISSISTANT~ASSISTANT), AĞLIYORUM
(...HAZIRLANMIŞTIR cümlesi), ÖNCE AĞLARSIN (...CAMERA), SARAYDA BİR ÇOCUK (MIOUAEL COTTLIE≈MICHAEL GOTTLIEB)...
→ HEPSİ başka sinyalle yakalandı, garble-tespitiyle değil.

## ÖNERİLEN FİX (ayrı karar)
1. `_guard`'a garble/near-dup/kurum/cümle-eki filtresi (bu denetimin heuristikleri).
2. Bu sinyalleri `reasons`'a bağla → KONTROL'e düşür (kapıya ekle).
3. Mevcut 3 bozuk ONAYLI'yı KONTROL'e taşı + yeniden çöz.

Denetim aracı: `outputs/garble_audit.py` (DB'siz, yüksek-isabet; tekrar koşulabilir).
