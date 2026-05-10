# 01 — PROJE VİZYON

> Son güncelleme: 2026-05-10
> Son değişen bölüm: ilk sürüm

---

## 1. İsim ve kısa tanım

**MITAS:** Türkçe-merkezli, web tabanlı, kurum içi video/medya analiz sistemi.

VITOS'un halefidir. VITOS deneyimlerinden çıkarılmış disiplinlerle, modern model ekosistemi üzerine inşa edilmektedir.

---

## 2. Kim için, neyi çözmek için

**Hedef kullanıcı:** TRT arşiv ve metadata operatörleri.

**Çözmek istediği problem:** Eski TRT arşivinde milyonlarca saat video var. Bunları arayabilmek, zaman damgalı metadata üretebilmek, doğru kişilere doğru rolde atayabilmek bugün hâlâ manuel iş. Mevcut araçlar:

- ya yabancı / İngilizce-merkezli (axle.ai gibi),
- ya bulut tabanlı (KVKK / veri egemenliği problemi),
- ya da eski TRT arşiv kalitesine uyum sağlamıyor (interlaced, U-matic, Betacam kalıntıları, eski TRT KJ formatı, Türkçe karakter karmaşası).

MITAS bu boşluğu doldurur: Türkçe karaktere, TRT KJ formatına, eski arşiv kalitesine, kurum içi çalışmaya, KVKK'ya uyumlu, açıklanabilir metadata üreten bir sistem.

---

## 3. Çekirdek modüller

MITAS bir tek modül değil, **birbirine bağlanan modüller bütünüdür**. Çekirdek modüller:

- **ASR** — Türkçe ses → zaman damgalı transcript + diarization.
- **Face Recognition** — Kendi yapım programlarda yüz tespit / takip / kümeleme / öğrenen yüz bankası. Filmde face identification kapalı.
- **Görsel Tagleme** — Sahne / nesne / atmosfer için kontrollü tag üretimi (YOLO-World + SigLIP).
- **OCR & Text Extraction** — KJ / screen text + müzik segment linker. FilmCreditsParser ayrı bağımsız iş paketi.
- **Audio Activity Layer** — speech / music / applause / silence ayrımı (YAMNet vb.).
- **Song Recognition** — Chromaprint / AcoustID / kurum içi local fingerprint DB.
- **Timeline** — Tüm modüllerin sonuçlarını birleştiren ortak omurga.
- **Review UI** — Sistemin emin olmadığı sonuçları kullanıcı onayına sunan arayüz.

Detay: `MITAS_Master_Plan_Denetimli_v5.md`.

---

## 4. Donanım ve dağıtım hedefi

- **Hedef donanım:** RTX 3090 / 24 GB VRAM.
- **Çalışma yeri:** Kurum içi (lokal). Bulut gönderimi yok.
- **Erişim:** Web tabanlı, tarayıcıdan kullanılır. UI ayrı bir cephe olarak geliştirilir.
- **Ölçekleme hedefi (v1 sonrası):** Çoklu PC, paylaşımlı job queue, paylaşımlı DB.

RTX 6000 Pro veya 96 GB VRAM varsayımları **geçersizdir**. v1 RTX 3090'a göre tasarlanır.

---

## 5. Çekirdek prensipler (asla feda edilmez)

Bu prensipler MITAS'ın **anayasasıdır**. Modüller değişebilir, motorlar değişebilir, UI değişebilir; bu prensipler değişmez.

### 5.1 Yanlış metadata, eksik metadata'dan daha zararlıdır

Bir kişiye yanlış kimlik atamak, hiç kimlik atamamaktan kötüdür. Eksik tag, yanlış tag'ten iyidir. Bu prensip her güven eşiği kararında belirleyicidir: emin değilsen `needs_review` veya `null` yaz.

### 5.2 Her sonuç evidence ile açıklanabilir olmalıdır

UI'da görünen her tag, kişi, transcript parçası **geriye dönük kanıtla** açıklanmalıdır: hangi frame, hangi model, hangi versiyon, hangi skor, hangi kural. Evidence olmayan bilgi final metadata olmaz.

### 5.3 Candidate ≠ Identity

`face_cluster_A4` bir kümedir, kişi değildir. `SPEAKER_01` oturum içi ses ayrımıdır, kişi değildir. KJ'de "Ahmet Yılmaz" yazması ekrandaki yüzün Ahmet Yılmaz olduğu anlamına gelmez. Bu sinyaller **CandidateRelation** olarak birlikte tutulur, kullanıcı onayıyla **identity**'ye dönüşür.

### 5.4 Showcase ≠ Final analiz

Demo/sunum pipeline'ı gerçek metadata üreten final analizden ayrı tutulur. Showcase izlenim içindir; değer final analizdedir. İkisi hiçbir zaman karıştırılmaz.

### 5.5 Türkçe-merkezli olmak teknik bir karardır

Türkçe karakterler (ı/İ/ş/ğ/ö/ü/ç), Türkçe karakter karmaşası (I/i/İ/ı), TRT KJ formatı, eski arşiv terminolojisi — bunlar "sonradan ekleriz" değildir. **Modeller bunlara göre seçilir ve test edilir.** Yabancı çözümlerin başarı oranları MITAS için anlamlı değildir; ölçüt Türkçe arşiv malzemesidir.

### 5.6 Kurum içi olmak teknik bir karardır

TRT arşiv malzemesi ve özellikle yüz embedding'leri biyometrik veridir. Bulut servisine yüklemek **mümkün değildir**. Tüm modüller lokal çalışabilir olmalıdır. Lisansı bulut-only olan model production'a girmez.

### 5.7 Modüler venv disiplini

Her modülün kendi venv'i, kendi lock dosyası, kendi smoke test'i vardır. Bir modülde yapılan paket değişikliği diğer modülleri kırmaz. Bu disiplin demo sırasında bilinçli olarak gevşetilebilir, ama production'a girerken geri sıkılır.

### 5.8 Modül config ile açılıp kapanır

3090 VRAM bütçesi nedeniyle ASR, OCR, Face, Visual Tag, Audio Activity, Song Recognition gibi modüller config ile açılıp kapanabilir olmalıdır. Hepsi aynı anda zorunlu çalışmaz.

### 5.9 VITOS'tan dersler

- Unknown satır otomatik cast'e düşmeyecek.
- Parser default state `unknown` olacak.
- Evidence olmayan bilgi final metadata olmayacak.
- Review gereken bilgi otomatik kesin bilgi gibi gösterilmeyecek.
- Ortak status vocabulary kullanılacak; her modül kendi kelimesini uydurmayacak.
- Timeline ortak omurga olacak; modüller ayrı evrenlerde yaşamayacak.

Bu prensipler 2026-05-09 tarihli karar günlüğünde maddelendirilmiştir.

---

## 6. Rakip bağlamı: axle.ai

**axle.ai** profesyonel bir medya yönetim / metadata sistemidir, MITAS'ın doğal karşılaştırma referansıdır.

axle.ai güçlü olduğu yerler: ürünleşmiş arayüz, geniş entegrasyon, olgun ekosistem.

MITAS'ın farklılaşma noktaları:

- **Türkçe-merkezli ve TRT arşiv-spesifik:** axle.ai'nin Türkçe karakter / TRT KJ formatı / eski arşiv kalitesine yönelik özel optimizasyonu yoktur.
- **Kurum içi ve KVKK uyumlu:** Bulut servislerine veri çıkışı yoktur. Biyometrik veri kurum içinde kalır.
- **Sahip olunan sistem:** Lisans ücretine değil, geliştirme emeğine bağlı maliyet modeli. Uzun vadede satın almaktan ucuz; üstelik değişiklik talebi bir başkasına bağlı değildir.
- **Evidence-based ve audit'lenebilir:** Her sonuç açıklanabilir; arşivin uzun ömrü için kritik.

Bu farklılaşma noktaları sunumda da kullanılır, ama daha önemlisi **proje kararlarını yönlendirir.** axle.ai özelliği MITAS için referans değil, alternatif tasarım yolundan biridir.

---

## 7. Zaman ufku (esnek)

- **v0.1 — ASR dikey dilim:** çalışan ASR pipeline, JSON çıktı, kalite raporu.
- **v0.2 — OCR/KJ + Müzik segment dikey dilim.**
- **v0.3 — Görsel Tagleme dikey dilim.**
- **v0.4 — Face Recognition dikey dilim.**
- **v0.5 — Timeline birleşimi.**
- **v1.0 — MVP release.** Tek video üzerinde uçtan uca analiz + Review UI + JSON export.
- **v1.x — FilmCreditsParser.**

Tarih hedefleri bilinçli olarak yazılmaz; baskı kararları çarpıtır. Yol haritası detayı: `04_YOL_HARITASI.md`.

---

## 8. Bu klasörün ilişkisi

Bu vizyon, **master plan v5'in özetidir** ama özet değil **çerçevedir**: master plan teknik kararları tutar, bu dosya **niye** sorusunun cevabını tutar. Bir karar tartışılırken çelişki çıkarsa:

- niyet ve prensip için bu dosya kazanır,
- teknik karar için master plan kazanır.

İkisi birbiriyle çatışırsa **çelişki günlüğe yazılır** ve düzeltilir.

---

## 9. Bir cümle ile

MITAS, Türkçe arşivin doğru, açıklanabilir ve sürdürülebilir metadata altyapısıdır.
