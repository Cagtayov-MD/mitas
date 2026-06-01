# QA RAPORU — clip_pipeline100 master'ları (166 master, ~90 film)

Tarih: 2026-06-01 · Yöntem: programatik triyaj (gerçek PNG yükseklikleri + künye metinleri) →
şüphelilerin görsel teyidi (kontak sayfası + nokta kontrolü). `_SUMMARY.json` bayat (337B) olduğu
için ona güvenilmedi; ölçümler doğrudan dosyalardan alındı.

## Özet sayım (166 master)

| Sınıf | Adet | Durum |
|---|---:|---|
| ✅ OK (temiz) | 132 | Sorun yok |
| ✅ LEGIT_LONG (meşru uzun scroll) | 13 | Sorun yok — "BLOAT_H" flag'i yanlış alarmdı |
| 🔴 FOOTAGE_BLOAT (footage/siyah dolgu, çok az metin) | 11 | **Gerçek hata** |
| 🔴 EMPTY (künye=0, master dolu) | 8 | **Gerçek hata** |
| 🟡 FOREIGN (yabancı alfabe) | 2 (1 film) | Kapsam-dışı / gerçekten-zor — hata değil |

**Sonuç: 145/166 (%87) iyi. Gerçek hata: 19 segment, hepsi TEK kök sebepten. 1 film (Arapça) kapsam-dışı.**

🟢 Önemli olumlu bulgu: künye METNİNDE tekrar/hayalet YOK (her yerde consec=0, max_rep=1) →
temizlik katmanının consensus-dedup'ı çalışıyor. Uzun scroll'lar (300 SPARTALI 713 satır,
BEBEK 518, AZAP YOLU 506, BEKARLIĞA VEDA 465) **doğru** dizilmiş.

## 🔴 Gerçek hatalar — TEK kök sebep

**Kök sebep:** Kapanış (cikis) jeneriğinde CLIP, filmin **son sahne footage'ını** kredi sanıp
işaretliyor. Bu run `is_scroll=True` alınca piksel-mozaiği (slitscan2) footage'ı **metin olup
olmadığına bakmadan** üst üste diziyor → uzun footage/siyah master, ama OCR'da neredeyse hiç metin.
(line-mozaiği yolu yalnız metinli bant eklediği için bu tuzağa düşmüyor; tuzak SADECE scroll/piksel yolunda.)

### FOOTAGE_BLOAT (11) — en kötüler
| film (master stem) | yükseklik | künye | kanıt |
|---|---:|---:|---|
| BAŞKALARININ_HAYATI …__cikis | 12678 | 14 | üstte küçük film sahnesi (kâğıt/masa/el), altı %75 SİYAH |
| AFFEDİLMEYEN …__cikis | 9582 | 20 | footage dizilmiş |
| AİLE_BABASI …__cikis | 8152 | 2 | footage, neredeyse metin yok |
| AŞKIN_GÜCÜ …__cikis | 7449 | 16 | footage |
| BENİM_KALBİMİ_KIRMA …__cikis | 7029 | 3 | footage |
| AFRİKA_DA_BİR_YERDE …__cikis | 6129 | 1 | footage |
| AHLAT_AĞACI …__cikis | 5160 | 1 | footage (Nuri Bilge — son sahne uzun plan) |
| AMERİKAN_OTELİ …__cikis | 3563 | 2 | footage |
| 300_SPARTALI …__giris | 3165 | 1 | footage |
| (+ BERBER_DÜKKANI_2 giris 6491/20, BENİM_KALBİMİ_KIRMA giris 3972/11) | | | |

### EMPTY (8) — künye=0 ama master üretilmiş
BUĞDAY cikis (8825px), BİBİ_BLOCKSBERG cikis (7830px), BİR_BÜLBÜL_ÖTTÜ giris (1770),
BROOKER giris (1726), ASTRONOTUN_KARISI giris (1527), BİR_VARMIŞ_BİR_YOKMUŞ cikis (730),
AYRILIK giris (423), BUDAPEŞTE_MASALLARI cikis (72).
→ Hiç metin yok; master ya hiç üretilmemeli ya da boş bırakılmalı.

### Hafif kusur (gövde iyi)
300_SPARTALI cikis (17743/713) ve birkaç scroll'da **üstte birkaç footage karesi** var ama
gövde meşru ve uzun → kozmetik; aynı kök-sebep guard'ı bunların da tepesini temizler.

## 🟡 Gerçekten zor / kapsam-dışı (hata DEĞİL)

- **ALLAH_GELECEK (2010)** — Mısır yapımı, jenerik **Arap alfabesinde** (`هشام هنيدي` = Hisham Heneidy).
  OneOCR Arapçayı kısmen okumuş; Latin/Türkçe künye üretemeyiz. cikis %91 "garble" = aslında Arapça.
- Yabancı-dil ama OKUNABİLİR künyeler (hata değil, sadık): **BABA (1966)** = İstván Szabó "Apa",
  Macarca (`ÍRTA ÉS RENDEZTE: SZABÓ ISTVÁN`) — %13 OCR-gürültüsü dışında temiz; BUDAPEŞTE MASALLARI,
  ANTON ÇEHOV (dekoratif/kırmızı zemin), BATIYA GİDEN YOL (manzara zemin). Bunlar OK/LEGIT kovasında.

## ÖNCELİKLİ DÜZELTME (tek nokta, 19 segmenti birden çözer)

`20260601_pipeline100.py → compose_hybrid()`, scroll dalında:
piksel-mozaiği (`sl.slitscan2`) bloğunu eklemeDEN ÖNCE `read_pos(blk)` ile OCR et; blok yeterli
metin taşımıyorsa (örn. eşik: ≥2 satır VEYA ≥2-kelimeli bir satır) bloğu **EKLEME** (footage'dır).
Bu, line-mozaiği yolundaki footage-FP filtresinin scroll yolundaki karşılığıdır. EMPTY ve
FOOTAGE_BLOAT'un tamamını + scroll-tepesi footage'ları temizler. Meşru uzun scroll'lara dokunmaz.

## Kapsam (sessiz kısıtlama yok)

- Triyaj: 166 master'ın TAMAMI (yükseklik + künye metni) tarandı.
- Görsel: en şüpheli 15 master tek kontak sayfasında (`_QA_CONTACT.png`) + 2 künye metni (Arapça/Macarca)
  doğrudan okundu. Geri kalan LEGIT_LONG/OK kovaları metin+yükseklik metriğiyle (garble<%3, p/l düşük)
  güvenle temiz sayıldı; tek tek görsel açılmadı.
- Dosyalar: `_TRIAGE.json` (tüm 166 sıralı), `_QA_CONTACT.png` (görsel ızgara), bu rapor.
