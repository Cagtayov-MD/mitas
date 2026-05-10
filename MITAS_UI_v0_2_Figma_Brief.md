# MITAS UI Revizyon Talimatı — Figma için

> Hedef: Mevcut "Medya Yapay Zeka Kontrol Paneli" tasarımının v0.2 sürümü.
> Bu sürümde UI **sadece ASR modülüne adanmış** durumdadır. Diğer modüller (Face, OCR, Tag, Logo, Audio Activity, Song Performance) görünür kalır ama her biri "Yapım Aşamasında" rozetiyle disabled (soluk gri) gösterilir.
> Sözleşme uyumsuzlukları, isim hataları ve dil karışıklıkları düzeltilir.

---

## Genel İlkeler

- **Dil:** Tüm UI label'ları **Türkçe** olur. İngilizce kalan etiket bırakılmaz.
- **Aktif modül:** Sadece **ASR (konuşma → metin)**. Diğerleri görünür ama disabled.
- **Renk kodu:** Aktif modüller renkli, disabled olanlar **slate-700 soluk gri** + "Yapım Aşamasında" badge.
- **Mock data:** TRT içeriğine uygun Türk isim/örnek. Hiçbir yabancı ünlü referansı yok.

---

## 1. Üst Bar (Global Shell)

### Düzeltilecek

- "MITAS SYSTEMS" yazısının altına **küçük gri sürüm rozeti**: `v0.1 — geliştirme aşaması`
- Sağ üst köşeye **"DEMO MODU"** rozeti ekle (amber/turuncu renk, küçük). Tooltip: "Showcase: gerçek metadata değil, gösterim amaçlı."
- "Admin Operator" → **"Yönetici"**

### Tab İsimleri

- `Analysis Workstation` → **`Analiz İstasyonu`**
- `FaceBank Builder` → **`Yüz Bankası`** (Yapım Aşamasında rozeti ile — disabled gösterim)

---

## 2. Header (Analiz İstasyonu)

### Türkçeleştirme

- `Analysis Workstation` → **`Analiz İstasyonu`**
- `Upload` → **`Yükle`**
- `Queue (4)` → **`Sıra (4)`**
- `Export` → **`Dışa Aktar`**
- `Analyze` → **`Analiz Et`**

### İş Durumu Barı (YENİ — eklenmeli)

Header'ın altına **ince bir bar** eklenmeli. İçerik:
- Sol: aktif iş durumu örneği: `ASR çalışıyor — Kalan: 12 dk`
- Orta: ilerleme çubuğu (cyan, %35 dolu)
- Sağ: `Sıradaki: —` (çünkü sadece ASR aktif)

İş yokken bar boş ama görünür kalır: `Bekleniyor — yeni iş yok`.

### Model Rozetleri (Alt Bar)

Bu satır şu an: `ASR: V3 | FACE: V2 | OCR: V1 | TAG: V4 | LOGO: V1`.

Değiştir:
- `ASR: large-v3` → **yeşil** (aktif)
- `FACE: —` → **gri / Yapım Aşamasında**
- `OCR: —` → **gri / Yapım Aşamasında**
- `TAG: —` → **gri / Yapım Aşamasında**
- `LOGO: —` → **gri / Yapım Aşamasında**

`Models:` etiketi → **`Modeller:`**

---

## 3. Video Player

### Türkçeleştirme + Disabled

- `Faces` butonu → **`Yüzler`** — disabled, "Yapım Aşamasında" tooltip
- `OCR` butonu → **`OCR`** — disabled, "Yapım Aşamasında" tooltip
- `On Screen:` → **`Ekranda:`**

### Yüz Overlay'leri (R.T. Erdoğan, UNKNOWN_01)

Tamamen kaldırılır. Video player bu sürümde **temiz** kalır, yüz kutusu yok. Sadece üst köşede küçük bir not: "Yüz tanıma yapım aşamasında — v0.4'te aktif olacak."

### OCR Overlay (ANKARA 1987)

Kaldırılır. Yerine küçük not: "OCR yapım aşamasında — v0.2'de aktif olacak."

### Alt Bilgi Çubuğu (`On Screen: R.T. Erdoğan, UNKNOWN_01, TRT Logo`)

Yerine: **"Aktif konuşmacı: SPEAKER_01"** (ASR'den gelen, kişi kimliği değil ses ayrımı).

---

## 4. Timeline

### Track İsimleri (Türkçe + Master Plan Hizalama)

| Şu an | Yeni isim | Durum |
|---|---|---|
| Warnings | **Uyarılar** | aktif, amber |
| Speech (ASR) | **Konuşma (ASR)** | aktif, cyan |
| Faces | **Yüzler** | **Yapım Aşamasında** (gri) |
| OCR/Credits | **Ekran Yazısı (KJ)** | **Yapım Aşamasında** (gri) |
| Visual Tags | **Görsel Etiketler** | **Yapım Aşamasında** (gri) |
| Logos | **Logolar** | **Yapım Aşamasında** (gri) |

### Yeni Track'ler (eklenmeli)

Timeline'a iki yeni track eklenir:

- **Ses Aktivitesi** (Audio Activity) — konuşma/müzik/alkış/sessizlik renkli bantlar — **Yapım Aşamasında** (gri)
- **Şarkı Performansı** (Song Performance) — şarkı segmentleri — **Yapım Aşamasında** (gri)

Track sırası yukarıdan aşağı:
1. Uyarılar
2. Konuşma (ASR) ← aktif
3. Ses Aktivitesi ← yapım aşamasında
4. Şarkı Performansı ← yapım aşamasında
5. Yüzler ← yapım aşamasında
6. Ekran Yazısı (KJ) ← yapım aşamasında
7. Görsel Etiketler ← yapım aşamasında
8. Logolar ← yapım aşamasında

### Track Görsel Stili

- **Aktif track:** Mevcut renkli görünüm korunur.
- **Yapım aşamasında track:** Tüm renk **slate-700 / opacity 40%**. Track ismi yanına küçük 🔒 ikonu veya `[yapım aşamasında]` text. Üzerine tıklama disabled.

### Zaman Aralık Butonları

- `1M / 5M / 30M / FULL` → **`1dk / 5dk / 30dk / TAM`**

### Üst Başlık

- `AI EVIDENCE TRACKS` → **`AI KANIT KATMANLARI`**

---

## 5. Sidebar (Sağ Panel)

### Tab İsimleri

| Şu an | Yeni | Durum |
|---|---|---|
| Queue | **Sıra** | aktif, kırmızı nokta kalır |
| ASR (Transcript) | **ASR** | aktif |
| Faces | **Yüzler** | disabled (Yapım Aşamasında) |
| Tags | **Etiketler** | disabled |
| OCR | **OCR** | disabled |
| Meta | **Bilgi** | aktif |
| Evd | **Kanıt** | aktif |

Disabled tab'lara tıklanınca: küçük overlay → "Bu modül v0.X sürümünde aktif olacak."

---

## 6. Sıra (Queue) İçeriği

### Mevcut item'lar değiştirilir

**Şu anki "Low Confidence Face Match — Michael Jordan"** → **Tamamen kaldır.** Michael Jordan dahil hiçbir yabancı ünlü referansı kalmaz.

**Şu anki "Suspicious Tag — yangın"** → **Kaldır.** Tag review v1.1'e bırakıldı.

### Yeni Sıra örnekleri (ASR odaklı)

1. **`ASR — Düşük Güven Segmenti`** (severity: amber)
   - "00:01:23-00:01:35 arası segment %62 güvenle çıkarıldı. Manuel inceleme gerekebilir."
   - Butonlar: `Reddet` / `Düzenle` / `Onayla`

2. **`ASR — Yabancı Dil Tespit Edildi`** (severity: blue)
   - "00:03:45-00:03:52 arası bölümde İngilizce alıntı tespit edildi."
   - Butonlar: `İncele` / `Onayla`

3. **`ASR — VAD Boşluk`** (severity: blue)
   - "00:05:10-00:05:25 arası 15 saniyelik ses tespit edilemedi."
   - Butonlar: `İncele` / `Görmezden Gel`

### Tab Üst Bar

- `Action Required` → **`İnceleme Bekleyen`**
- `Pending` rozet metni → **`bekliyor`**

### Severity Etiketleri

- `high` → **`yüksek`**
- `medium` → **`orta`**
- `low` → **`düşük`**

---

## 7. ASR (Transcript) Sekmesi

### Türkçeleştirme

- `Search transcript...` → **`Transkript içinde ara...`**
- `Split` → **`Böl`**
- `Merge` → **`Birleştir`**

### Konuşmacı Etiketleri

Mevcut karışık etiketler: `UNKNOWN_01`, `Speaker 2`, `Speaker 3`.

Yeni standart (master plan §0.3.5 + §5.3 prensibi):
- **`SPEAKER_01`**, **`SPEAKER_02`**, **`SPEAKER_03`** — diarization çıktısı (ses ayrımı, kişi değil)
- Bu etiketin yanında ufak bilgi ikonu: tooltip → "Diarization ses ayrımıdır; kişi kimliği değildir."

Mock transcript örnekleri: Türk konuşmacılarla, TRT bağlamına uygun.

### Güven Skoru

- `95%` formatı kalır, ama altında küçük etiket:
  - `≥ 0.85` → yeşil **`onaylı (auto)`**
  - `0.65 - 0.85` → amber **`inceleme bekliyor`**
  - `< 0.65` → kırmızı **`düşük güven`**

---

## 8. Yüzler / Etiketler / OCR Sekmeleri

Bu üç sekme tamamen **disabled / placeholder** görünür. İçeriği:

- Büyük bir kapalı kilit ikonu (🔒)
- Başlık: **"Yapım Aşamasında"**
- Açıklama: **"Bu modül v0.X sürümünde aktif olacak."**
  - Yüzler → v0.4
  - Etiketler → v0.3
  - OCR → v0.2
- Küçük disabled "İlerleme detayı" linki.

---

## 9. Bilgi (Meta) Sekmesi

### Türkçeleştirme

Sol kolon başlıkları:
- `MEDIAID` → **`Medya Kimliği`**
- `TITLE` → **`Başlık`**
- `DURATION` → **`Süre`**
- `DATE` → **`Tarih`**
- `LANGUAGE` → **`Dil`**
- `SOURCE` → **`Kaynak`**
- `FORMAT` → **`Format`**
- `PROCESSINGSTATUS` → **`İşlem Durumu`**
- `EXPORTSTATUS` → **`Dışa Aktarım`**

Üst bar: `Media Details` → **`Medya Detayları`**

---

## 10. Kanıt (Evidence) Sekmesi

### Türkçeleştirme

- Action `Face Match` → **`Yüz Eşleşmesi`** — ama disabled (bu satırı kaldır, çünkü face aktif değil)
- Action `Visual Tag` → **`Görsel Etiket`** — kaldır
- Action `Speech-to-Text` → **`Konuşma → Metin`** — kalır

### Yeni Kanıt Örnekleri (ASR odaklı)

Üç örnek satır:
1. **`Konuşma → Metin`** — Model: `faster-whisper large-v3` — Segment, WER tahmini, alignment durumu
2. **`VAD Konuşma Tespiti`** — Model: `Silero VAD` — Segment uzunluğu, güven
3. **`Konuşmacı Ayrımı (Diarization)`** — Model: `pyannote-audio 4.0.4` — Speaker count, segmentler

### Alanlar

- `Model:` kalır
- `CONF:` → **`Güven:`**

---

## 11. Yüz Bankası Sekmesi (Üst Tab)

Bu tab **disabled** olur (henüz v0.4 sürümünde aktif olacak).

Tıklanınca tüm Yüz Bankası ekranı yerine büyük bir placeholder:

- Büyük kilit ikonu 🔒
- **"Yüz Bankası Yapım Aşamasında"**
- **"Bu modül v0.4 sürümünde aktif olacak. Şu anki sürüm ASR (konuşma → metin) modülüne odaklanmıştır."**
- "Yol haritasını incele" linki (gri, disabled).

---

## 12. Yan Bar Genel Tutarlılığı

- Tüm "approved/pending/rejected/verified" badge'ları yeni vocabulary'ye dönüştürülür:
  - `approved` → **`onaylı`**
  - `pending` → **`inceleniyor`**
  - `rejected` → **`reddedildi`**
  - `verified` → **`doğrulanmış`**
  - `auto` (yeni) → **`oto-kabul`** (yeşil tonu)
  - `low_confidence` (yeni) → **`düşük güven`** (amber)

---

## 13. Renk Tutarlılığı

Disabled / "Yapım Aşamasında" track ve sekmeler için tek tip ton:

- **Arka plan:** slate-800 / 30% opacity
- **Border:** slate-700 / 50% opacity
- **Metin:** slate-500
- **İkon:** slate-600 + küçük 🔒 emoji veya kilit svg

Aktif modüller (ASR) için renk kodu mevcut cyan-500 / emerald-500 ailesi korunur.

---

## 14. Tipografi ve Boşluk

Bu sürümde değişmez. Mevcut Tailwind sınıfları korunur.

---

## 15. Sürüm Kaydı (Footer veya Header'da küçük not)

Mevcut UI'da yer yoksa, sağ alt köşede çok küçük bir gri yazı:

`MITAS UI v0.2 — ASR odaklı — Yapım aşamasındaki modüller v0.X'te aktif olacak`

---

## Önemli Notlar

1. **Tüm mock veriler Türkçe / TRT bağlamına uygun** olmalı. Türk yer adları (Ankara, İstanbul, İzmir), Türk politikacı / sanatçı / gazeteci isimleri (gerçek isim kullanmaktan kaçınılıp jenerik soyadlar tercih edilebilir).

2. **Hiçbir yerde "approved/pending"** İngilizce vocabulary'si kalmaz.

3. **Hiçbir yerde yabancı ünlü ismi** (Michael Jordan vb.) referansı kalmaz.

4. **Üç farklı ID kavramı net olmalı:**
   - `SPEAKER_01` = diarization (ses ayrımı)
   - `FACE_CLUSTER_A4` = yüz kümesi (henüz kişi değil) — bu sürümde görünür değil, sonraki sürümde
   - `Recep Tayyip Erdoğan` = onaylanmış kişi — bu sürümde görünür değil

5. **Sadece ASR aktif. Diğer her şey görünür ama disabled + "Yapım Aşamasında".**

---

## Kabul Kriteri

Tasarım v0.2 olarak teslim edildiğinde:

- [ ] Tüm UI Türkçe
- [ ] Hiçbir yerde "approved/pending/rejected/verified" İngilizce status yok
- [ ] Hiçbir yerde yabancı ünlü ismi yok
- [ ] Header'da sürüm rozeti + Demo Modu rozeti var
- [ ] İş durumu barı eklenmiş
- [ ] Timeline'a Ses Aktivitesi + Şarkı Performansı track'leri eklenmiş
- [ ] Diğer tüm modüller "Yapım Aşamasında" gri stilinde
- [ ] Video player yüz/OCR overlay'leri kaldırılmış
- [ ] Konuşmacı etiketleri SPEAKER_01 / SPEAKER_02 formatında
- [ ] Sıra item'larında ASR odaklı örnekler
- [ ] Kanıt sekmesinde ASR odaklı örnekler
- [ ] Yüz Bankası tab'ı disabled placeholder

Bu maddeler tamamlandığında v0.2 UI hazırdır.
