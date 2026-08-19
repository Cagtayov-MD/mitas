# Okuma Uzlaştırma — Faz B (ince dilim)

**Tarih:** 2026-08-19 · **Durum:** tasarım onaylandı, uygulama bekliyor
**Kapsam sahibi:** Çağatay · **Hazırlayan:** Claude

---

## 1. Problem

Üç okuyucu kulesi (LeBron / Nash / Jordan) aynı jeneriği ayrı beslemelerden
okuyor. Shaq bunları uzlaştırmak için kurulmuş ve `mitas.okuma/v1` sözleşmesi,
hizalama, karar ve kör kontrol kuyruğu **hazır**. Buna rağmen uzlaştırma
üretimde çalışmıyor.

Sebebini bu tasarımdan önce ölçtük. İki somut engel var:

### Engel 1 — üç okuyucu aynı birimi üretmiyor

Aynı bölümün üç paketinden örnek satırlar:

```
NASH   : 'nternational' · 'AHORM' · 'XASE' · 'MIS' · 'Scott BRADY'
LEBRON : 'Universal' · 'International' · 'Universal - International'
JORDAN : 'Universal International' · 'Presents' · 'Audie MURPHY'
```

Nash **OCR kutu parçası** üretiyor (bbox'ı bu yüzden var), LeBron ve Jordan
**birleştirilmiş satır**. Bu birimler karşılaştırılamaz.

Ölçüm (76 bölüm, `shaq/in/`): Nash ile LeBron arasında ham uzlaşma **%26,3**.
**Bu sayı geçersizdir** — okuma anlaşmazlığını değil birim uyuşmazlığını
ölçüyor. Gerçek anlaşmazlık oranı bugün **bilinmiyor**, ve bilinmeden hakem
tasarımı yapılamaz.

### Engel 2 — "tam iki paket" şartı gerçeğe uymuyor

`mitas.okuma/v1` bölüm başına tam iki paket istiyor. Ölçülen gerçek (76 bölüm):

| LeBron durumu | bölüm |
|---|---|
| SUCCEEDED | 49 |
| NO_CONTENT | 21 |
| FAILED (ör. *"115 kare tek segmente çökmüş"*) | 6 |

LeBron bölümlerin **%36'sında hiç satır üretmiyor**. Kanal mevcudiyeti sabit
değil; iki-kanal şartı bu bölümlerde Shaq'ı çalışamaz kılıyor.

### Uzamsal çapa yalnız Nash'te

| okuyucu | dosya | satır | bbox'lı |
|---|---|---|---|
| **nash** | 249 | 23.500 | **23.500 (%100)** |
| lebron | 97 | 5.768 | 56 (%1) |
| jordan | 54 | 6.805 | 0 (%0) |

"Anlaşmazlıkta ilgili kareye gidip kör oku" fikri **yalnız Nash'in
koordinatlarıyla** mümkün. Bu, Nash'i zorunlu kanal yapar.

---

## 2. Kapsam

**Faz B — ince dilim.** Üç iş yapılır:

1. Nash kutu parçalarını satıra toplar (kule içinde).
2. Shaq N-kanal kabul eder ve her satırı **güvenle etiketler**.
3. Anlaşmazlık satırları kontrol kuyruğuna **yazılır** — sağlayıcı bağlanmaz.

### Kapsam DIŞI (bilinçli)

- **Kontrol sağlayıcısı bağlanmaz.** Kuyruk yazılır, boş kalır. Gerekçe:
  hakem seçimi, anlaşmazlık yüküne bağlıdır ve o yük bu fazın çıktısıdır.
- Jordan'ın hakemliği kararlaştırılmaz.
- Fuzzy isim düzeltme, sözlük eşleme, diakritik normalleştirme — ayrı iş.
- QC1 bağlantısı yok; Shaq gölge kalır.
- Jordan'a bbox eklenmez.

---

## 3. Mimari

```text
Nash ──► satır toplama (kule içi) ──► nash.okuma.json (satır birimli, bbox'lı)
LeBron ─────────────────────────────► lebron.okuma.json
Jordan ─────────────────────────────► jordan.okuma.json
                                            │
                                            ▼
                                   Shaq: hizala → karar → güven
                                            │
                        ┌───────────────────┴───────────────────┐
                        ▼                                       ▼
              uzlasma.json (satır + güven)          kontrol_kuyrugu/ (bbox'lı
                                                     kırpım isteği, CEVAPSIZ)
```

### 3.1 Nash — satır toplama

**Nerede:** Nash kulesinin içinde. Gerekçe: kule sınırı doktrini — kendi
çıktısının biriminden kule sorumludur. Shaq'ın "nash parça verir" bilgisini
taşıması kule bağımsızlığını zayıflatırdı.

**Ne yapar:** Aynı asset üzerindeki kutuları dikey konumla gruplayıp tek satır
kurar. Satırın bbox'ı, bileşen kutuların birleşimi (min x0/y0, max x1/y1).

**Değişmez:** parça bbox'ları **kaybolmaz**, satırın `evidence` listesinde
bileşen olarak kalır. Kontrol kuyruğu istenirse parçaya inebilmeli.

**Risk:** Nash'in çıktı biçimi değişir; mevcut Nash ölçümleri yeniden
koşulmalıdır. Kabul edildi.

### 3.2 Shaq — N-kanal + güven

`mitas.okuma/v1` "tam iki paket" şartı **N pakete** gevşetilir (1 ≤ N ≤ 3).
Nash zorunlu; diğerleri varsa katılır.

**"Aynı" tanımı — belirsiz bırakılamaz.** İki satır ancak `tr_lower` +
diakritik-koruyan normalleştirmeden sonra **birebir eşitse** aynıdır. Fuzzy
yakınlık aynı DEĞİLDİR; ayrı bir sınıftır ve aşağıda ayrı satırı vardır.
Gerekçe: `ÜMIT` ile `ÜMİT` fuzzy olarak yakın ama biri yanlış — "aynı" saymak
yanlış yazımı sessizce kabul etmek olur.

Karar tablosu — mevcut durumlarla örtüşür, **yeni durum icat edilmez**:

| durum | karar | güven |
|---|---|---|
| 3 kanal birebir aynı | `GECTI` | yüksek |
| 2 kanal birebir aynı, 3. yok | `GECTI` | orta |
| 2 kanal birebir aynı, 3. farklı | `GECTI` + muhalif okuma saklanır | orta |
| kanallar yalnız **diakritikte** ayrışıyor | `KONTROL_BEKLIYOR` | düşük |
| kanallar metinde ayrışıyor | `KONTROL_BEKLIYOR` | düşük |
| tek kanal | `GECTI` + işaret | düşük |

Muhalif okuma hiçbir durumda atılmaz; `uzlasma.json` içinde hangi kanalın ne
dediği kalır. Çoğunluk kararı **doğruluk iddiası değil**, yalnız güven
seviyesidir — üç okuyucu aynı pikselleri okuduğu için çoğunluk ortak hataya da
düşebilir (bkz. §7.1).

**Değişmez:** Shaq **satır silmez.** Silinen satır geri gelmez; işaretlenen
satır QC'de bakılır. Asimetrik risk ilkesi (`harness/kunye_kiyas/isim_normalize.py`
docstring'i): yanlış birleştirme hatayı **gizler**, yanlış ayırma **gösterir**
→ şüphede kalınca **ayır**.

Normalleştirme `isim_normalize.py`'den alınır, yeniden yazılmaz: `tr_lower`
(`İ→i`, `I→ı`, diakritik korunur) ve uzunluğa bağlı fuzzy tolerans (kısa
isimlerde sıfır).

### 3.3 Kontrol kuyruğu

`mitas.kontrol/v1` bugünkü haliyle kullanılır. Shaq **model çağırmaz** —
`kontrol.py`'nin ilk satırındaki sınır korunur. Kuyruk: Nash bbox'ından
kırpım + kör istek (aday metinler istek dosyasına konmaz).

Kuyruk **cevapsız** kalır ve uzunluğu bu fazın asıl ölçüm çıktısıdır.

---

## 4. Hata yönetimi

- Nash paketi yoksa → bölüm `COZUMSUZ`, sebep kaydedilir (bbox yok, kontrol
  kuyruğu kurulamaz).
- Bir kanal `FAILED` → o kanal yok sayılır, kalan kanallarla karar verilir,
  güven düşürülür ve **hangi kanalın düştüğü kanıta yazılır**.
- Hiç kanal yoksa → `ARIZA`. `ARIZA` asla `METIN_YOK`'a dönüşmez (Allstar
  değişmezi).
- Satır toplama bir asseti çözemezse → parça satırlar korunur, o asset
  "toplanamadı" diye işaretlenir. Sessiz düşürme yasak.

---

## 5. Test

- **Nash satır toplama:** sentetik bbox kümeleriyle birim testi — aynı satır,
  ayrı satır, üst üste binen kutular, tek kutu. Parça bbox'larının korunduğu
  ayrıca test edilir.
- **Shaq N-kanal:** 1/2/3 kanallı sentetik paketlerle karar tablosunun beş
  satırı da test edilir.
- **Sıfır-sapma kapısı:** mevcut 30 filmlik `shaq/in/` yatağında, üç kanalın
  hepsi dolu ve aynı olan bölümlerde karar `GECTI` kalmalı — yani değişiklik
  hâlihazırda uzlaşan satırları bozmamalı.
- **Regresyon:** Nash'in mevcut kule testleri (163) yeşil kalmalı.

---

## 6. Başarı ölçütü ve KARAR NOKTASI

Bu fazın çıktısı bir özellik değil, **bir sayı**: birim hizalandıktan sonraki
gerçek anlaşmazlık oranı.

| ölçülen oran | anlamı | sonraki adım |
|---|---|---|
| düşük (~%5–10) | okuyucular birbirini doğruluyor; ansambl işe yarıyor | hakem seç, kontrol sağlayıcısını bağla (Faz C) |
| yüksek (~%30+) | üç okuyucu üç ayrı gerçek üretiyor; uzlaştırma çözmez | mimariyi gözden geçir: tek okuyucu + isim/rol evrenine eşleme |

**Bu karar noktası bilinçlidir.** Beş aydır cevaplanmamış "hangi besleme daha
iyi okuyor / redundans işe yarıyor mu" sorusu, bu ölçümle ilk kez veriye
bağlanır. Faz C'ye ölçüm görülmeden geçilmez.

---

## 7. Bilinen riskler ve açık kalemler

1. **Ansambl varsayımı sınanmamış.** Nash ve Jordan aynı pikselleri okuyor;
   hataları bağımsız olmayabilir. Bağımsız değilse üç okuyucunun bedeli
   ödenip faydası alınmıyor demektir. Faz B'nin ölçümü buna da ışık tutar.
2. **Nash'in çıktısı gürültülü.** Kutu parçaları arasında `AHORM`, `XASE`,
   `MIS` gibi okunamayan diziler var. Satır toplama bunları birleştirince
   gürültü satıra taşınabilir. Ölçülmeli.
3. **Belge–kod sapması.** Shaq `README.md` alan adlarını `text` / `bolum` /
   `durum` ve bbox'ı sözlük olarak anlatıyor; üretilen dosyalar `raw_text` /
   `section` / `status` ve bbox'ı **liste** kullanıyor. `DURUM.md` ise
   `*.okuma.json` sayısını 0 sanıyor — gerçekte 883 var. Faz B'de düzeltilir.
4. **GT darlığı.** Dizi GT'sinin 14 bölümünün 8'i boş şablon; doğruluk
   iddiaları 6 bölüme (519 satır) dayanıyor.
5. **Dejenerasyon süzgeci ayrı duruyor.** Ölçüldü (2.520 ham satır → 58
   elendi, **GT kaybı 0**; eşik 5, gerçek GT'lerde ölçülen en uzun ardışık
   aynı-isim 2 olduğu için). Faz B'ye dahil değil; uzlaştırıcı içinde bir
   adım olarak yaşayabilir, kararı Faz C'ye bırakıldı.

---

## 8. Kaynaklar

- Ölçüm yatağı: `Allstar/shaq/in/` (30 film, 76 bölüm, üç kanal)
- Dizi GT: `Allstar/gt_dizi/` (6 bölümde gerçek GT)
- Normalleştirme: `harness/kunye_kiyas/isim_normalize.py`
- Shaq sözleşmesi: `Allstar/shaq/README.md`, `src/kontrol.py`
