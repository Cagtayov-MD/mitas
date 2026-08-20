# MITAS — KALAN İŞLER

> Çağatay: *"Kalanların tamamını bir liste halinde yaz, bulmak kolay olsun."*
> Bu dosya **açık kalemlerin tek adresi**. Bir kalem kapanınca buradan silinir ve
> `MITAS_BULGU_DEFTERI_2026-08-01.md`'nin A bölümüne commit'iyle geçer.
> Son güncelleme: 2026-08-01 19:15

---

## ŞU AN KOŞUYOR

**Üretim — ANA HAVUZ** · `outputs/toplu_kosu/anahavuz_fix_*.log`
1751 film, düz sıra (21 düzeltme-adayı kovalaması Çağatay talimatıyla bırakıldı:
*"21'i boşver"*). Database'de olan filmler ATLA'nır. Hakem VL KAPALI.
Kod durumu: `1ebd63ad` (giriş-jeneriği kesme + kasa kapısı fix'leri DAHİL).
21 filmin yedeği duruyor: `Database_kalan21_yedek_20260801_1901/` — 11'i hiç
işlenmedi, Database'de olmadıkları için bu koşuda normal sırayla işlenecekler.

---

## 1. SIRADAKİ — koşu sonucu bekleyen

### 1.1 Prompt kalıplarını GERİ AL (defter A kalemi)
Bugün `credit_text_read.PROMPT` kural 4'e üç kalıp eklendi (assistant réalisateur /
geschichte von / konum uyarısı). Sonra **kart sınırlı metin** yapıldı ve o kalıpları
gereksiz kılması bekleniyor — model artık yapıyı görüyor, kalıp ezberlemesine
gerek yok. Çağatay'ın itirazı: *"Sen bu talimatı vereceksen gemma'yı niye
kullanıyoruz?"*
**Yapılacak:** koşu sonrası 3 vakayı (YAZ TATİLİ / KARA GÜNLER / ÇİNGENE) kalıplar
KAPALI ölçüp, kart metni tek başına yetiyorsa kalıpları kaldır.

### 1.2 KB'yi karardan MAKYAJA indir (defter B8)
Çağatay kararı. Ölçüm kancası takılı (`credit_yonetmen_kb_kapisi_sildi`,
`tek_film_kunye.py:810`) ama **henüz tek olay basılmadı** — koşu sayı üretecek.
**Sıra şart:** eşleme sertleşti (✓ bugün) → hakem kuruldu (✓ bugün) → *şimdi* KB inebilir.
Ölçülen dayanak: KB otoriter yönetmeni olan 164 filmin 109'unda (%66) aynı ismi
okuduk; gerçek çelişki %5; KB çelişkide en fazla yarı yarıya haklı.

---

## 2. ÖLÇÜLDÜ, YAPILMADI

### 2.1 CAST_CAP=10 — dizinin "eksiksiz künye" hedefi (defter B7)
`credit_qc_block.py:492` varsayılan **10**, satır 793 sert kesme. 54 filmde
`CAST_CAP_DUSEN` uyarısı.
**Tuzak:** cap farkında olmadan çöp filtresi görevi görüyor. HAYATIN TUZU'nda
düşen "3902 oyuncu"nun içeriği: 8 gerçek isim + kurum-adı kayan pencere çiftleri
+ `Q LJDH`, `SOW CINAN` gibi saf çöp. Cap=999 yapılırsa bunlar PDF'e girer.
**Sıra:** önce "bu satır gerçek oyuncu adı mı" kapısı, SONRA cap kalkar.

### 2.1b Footage-üstü yazıda phash dedup metin varyasyonunu yutuyor (ALİE kanıtı)
`ALİE 2010-9253` giriş jeneriğinde `yapımcı` (g_0205) ve `oktay kaynarca` (g_0208)
kartları AYNI köprü planının üstüne biniyor; yalnız küçük yazı değişiyor.
phash kümelemesi baskın GÖRÜNTÜye göre kümeleyip tek temsilci (g_0205) seçti —
o da yalnız ETİKETİ taşıyordu, İSİM hiç okunmadı. `giris_jenerik` havuzunda
g_0206/0208/0210 VAR; havuz doğru, okuyucu örneklemesi kaçırdı.
**Bu 2.2 ile aynı çözümü ister:** det-kutulu/metin-değişen kare örneklemede
önceliklendirilsin. İki ayrı sınıf değil, tek kök.

### 2.2 Frame kolu örnekleme adımı kart atlıyor (defter B3)
`MAX_SAYFA_GIRIS=40`, ham 270 kare → adım ~6.75. KUTSAL HAZİNE'de
`A JOHN HUNECK FILM` kartı (g_0020-0025) iki örnek arasına düştü
(g_0017 timecode barı → g_0027 Starring). Master kolu emniyet ağıydı, o da yoktu
(A16 ile düzeldi).
**Fikir:** det-kutulu kareleri örneklemede önceliklendir — `kutu_n>0` olan kare
atlanmasın. Altyapı var (`_det_kutu_n`), maliyet: örnekleme öncesi det taraması.

### 2.3 Hakem VL'nin kapsama açığı (defter B5 kalanı)
Hakem çalışıyor, 4 uydurma sınıfını reddediyor, **hiçbir uydurmayı kabul etmiyor**.
Ama KUTSAL HAZİNE'de doğru kartı (`A JOHN HUNECK FILM`, ilk 20 sn) 7 blokta
BULAMADI — blok 0 hiç cevap vermedi.
**Yapılacak:** blok 0'ın neden boş döndüğünü ölç (ffmpeg `-ss 0` kesimi mi, model mi).
Varsayılan KAPALI (`MITAS_HAKEM_VL=1`), ~20 GB VRAM.

### 2.4 `Wiliam` — OCR yanlış okuması (defter B12)
HANK WILLIAMS künyesinde `Wiliam Marshall` (tek L), yanında `Henr Van`,
`Rolr Peter`, `Stephenson Assoclate` gibi kayan-pencere artefaktları.
Okuma kalitesi sorunu; harf kasası (Kidd) bunu çözmez.

---

## 3. DOKUNULMAYAN FİLM KUYRUKLARI

### 3.1 Eski KONTROL havuzu — 178 film
Bugünkü A/B yalnız **bizim 29'luk kohortumuzu** kapsadı. Kalan 178 film
Paddle/OneOCR ile okunmuştu; yeniden koşmak okuyucu+fix'i AYNI ANDA değiştirir,
hangi kazanımın kimden geldiği ayrılamaz. Sınıflandırma yapıldı:
```
 38  sahte Latin damgası      (künye %0.00-0.99 → çürütme kapısı temizler)
  1  görsel/afiş kaynaklı
 12  yönetmen kurtarılabilir  (KOVBOY→Delmer Daves, LA BOHEME→Luigi Comencini…)
127  başka sebepler           (dokunulmadı)
```
Üretim koşusu bunları zaten sırasıyla işleyecek (Database'de oldukları için
ATLA'nacaklar → **ayrıca taşınmaları gerekir**, aksi halde eski kararlarıyla kalırlar).

### 3.2 Videosu paylaşımda OLMAYAN 13 film
Fix adayı olup videosu bulunamayan: `2010-9199-0-0001-88-1`, `1995-0282`,
`1987-1125`, `1996-0324`, `1999-0321`, `1981-0279`, `2004-9139`, `1994-0345`,
`1988-0430`, `1979-0243`, `1980-0209`, `2000-0489`, `1988-0461`.
6'sının kareleri var → `--from-hub` ile koşulabilir (video gerekmez).
Kalan 7'nin ne karesi ne videosu var → **veri kaynağı sorulmalı**.

---

## 4. SÜREÇ / DENETİM

### 4.1 codex-review bu dalda HİÇ koşmadı (defter B11)
Bot "usage limits" dedi, tek kelime geri bildirim yok. CLAUDE.md'nin
"kritik fix → bağımsız inceleme" kapısı **28 commit boyunca açık kaldı**.
**Alternatif:** dış konseye gerçek diff ile mercekli bug-avı turu
(GLM=güvenlik, Qwen=performans, Kimi=edge-case).

### 4.2 Ruff uyarıları (20+, warn-only)
TRY004 / C409 / UP024 — hepsi eski dosyalarda, CI'ı düşürmüyor. Temizlenmedi.

---

## 5. AÇIK SORU — cevabı Çağatay'da

**Dizi profili "eksiksiz künye"** hedefinin iki engeli var (2.1 CAST_CAP ve
"gerçek oyuncu adı" kapısı). Kapı tasarımı bir karar gerektiriyor: bir satırın
oyuncu adı olduğuna neyle karar vereceğiz — piksel kanıtı + kart yapısı yeter mi,
yoksa KB imlacı olarak devreye girmeli mi?

---

## KAPANANLAR
Bugün 28 commit. Tam liste ve kanıtları:
`docs/MITAS_BULGU_DEFTERI_2026-08-01.md` bölüm A.
Öne çıkanlar: rol etiketlerinin dedup'a kurban gitmesi (rol-eşlemenin kökü) ·
500-satır kesmesinin yönetmen kartını atması · İbrahimovic kolunun girişe körlüğü ·
9 sabit-yol vakası (biri ölçüm aracını sahte-yeşil yapmıştı, biri Kidd'in beynini
kapatmıştı) · iki sahte QC kapısı · JASON KIDD harf kapısı.
