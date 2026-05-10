# 00 — BURADAN BAŞLA

> Bu klasör MITAS projesinin operasyonel beynidir.
> Buraya yazılan her şey: ne yaptığımız, ne yapacağımız, neyi neden seçtiğimiz.
> Acele kararlar değil; ince ince dokunmuş yol haritası.

---

## 1. Bu klasör nedir, neden var

MITAS, tek kişi tarafından geliştirilen TRT arşivi için Türkçe-merkezli medya analiz sistemidir. Geliştirme süreci uzun ve katmanlıdır; Claude (web), Claude Code (Opus 4.7) ve gerekirse Codex gibi LLM araçlarıyla paralel ilerlemektedir.

LLM oturumları **token sınırına girer ve kapanır**. Yeni oturum açıldığında "geçen sefer ne konuşmuştuk" stresi yaşanmamalıdır. Bu klasör tam bunun için var:

- her oturuma aynı bilinç düzeyinde başlamak,
- aynı disiplin tonunu sürdürmek,
- aynı kararlara sahip çıkmak,
- "ay ne yapıyorduk?" telaşını ortadan kaldırmak.

Bu sebeple bu klasör **proje koduyla aynı disiplinle** tutulur: her karar değiştiğinde ilgili dosya güncellenir, eskiyen bölümler çizilir, yeni kararlar tarihiyle eklenir.

---

## 2. Klasörü kim okur

İki muhatap var:

**(A) Geliştirici (Ç.)** — Tek kişilik geliştirici. Bir oturum kapatıp diğerini açtığında bu klasörden başlar. Aktif sprintini, açık kararlarını, son durumunu buradan hatırlar.

**(B) LLM yardımcı (Claude / Claude Code / Codex)** — Yeni oturuma başlayan herhangi bir LLM, "MITAS projesinde sana yardım edeceğim" denilerek bu klasöre yönlendirildiğinde, **aynı ciddiyet ve aynı tonla devam etmek üzere** buraya bakar. Geçici bir asistan değil, projenin kuralları içine girmiş bir yardımcı olarak.

---

## 3. Okuma sırası (önemli — atlatma)

Bir LLM oturumuna başlarken dosyalar şu sırayla okunmalıdır:

1. **00_BURADAN_BASLA.md** ← bu dosya, çatıyı verir
2. **01_PROJE_VIZYON.md** ← MITAS nedir, neden, ne için
3. **02_CALISMA_DISIPLINI.md** ← nasıl çalışılır, nasıl konuşulur
4. **03_GUNCEL_DURUM.md** ← şu an nerede duruyoruz
5. **05_AKTIF_GOREV.md** ← şu an üzerinde çalışılan iş
6. **04_YOL_HARITASI.md** ← sırada neler var
7. **06_KARARLAR_GUNLUGU.md** ← geçmişte ne karara bağlandı
8. **07_REFERANS_HARITASI.md** ← hangi dosya nerede

**Yedi dakikada hepsi okunur.** Bunu yapmadan kod konuşması başlamaz.

---

## 4. Çekirdek özet — "tek paragrafta MITAS"

> MITAS, VITOS'un halefi olan, Türkçe-merkezli, web tabanlı, kurum içi çalışan video/medya analiz sistemidir. Çekirdek modülleri ASR, Face Recognition, Görsel Tagleme, OCR & Text Extraction, Audio Activity, Song Recognition, Timeline ve Review UI'dir. RTX 3090 / 24 GB VRAM hedef donanımdır. Geliştirme tek kişiliktir, LLM destekli ama disiplinlidir. Yanlış metadata eksik metadata'dan zararlıdır; her sonuç evidence ile açıklanabilir olmalıdır. Aday ilişki (candidate) ile kesin kimlik (identity) ayrı katmanlardır. Demo ile final analiz aynı şey değildir.

---

## 5. Şu an aktif

**Aktif sürüm hedefi:** v0.1 — ASR dikey dilim.
**Aktif odak:** ASR pipeline'ını düzgün şekilde ayağa kaldırmak.
**Bloke olan:** Yok (10 Mayıs 2026 itibarıyla).
**Sonraki adım:** `05_AKTIF_GOREV.md` içine bak.

---

## 6. Sürüm ve güncelleme disiplini

Her dosyanın başında **son güncelleme tarihi** ve **son değişen bölüm** yazar.
Karar değiştiğinde:
- ilgili dosya güncellenir,
- eski karar üstü çizili olarak bırakılır (silinmez — neden değiştiğini hatırlamak için),
- `06_KARARLAR_GUNLUGU.md` dosyasına yeni satır eklenir.

Bu klasör **canlıdır**. Statik bir doküman değil, projenin nabzı.

---

## 7. Bu klasör neye dokunmaz

Bu klasör aşağıdakileri **kapsamaz**:

- Master plan (`MITAS_Master_Plan_Denetimli_v5.md`) — teknik karar dosyası, ayrı.
- Uygulama planı (`MITAS_Uygulama_Plani_v1.md`) — sprint detayı, ayrı.
- `docs/` altındaki sprint raporları — kurulum/denetim çıktıları, ayrı.
- `outputs/` altındaki JSON raporları — operasyonel artefakt, ayrı.

Bu klasörün görevi **yön vermek ve hatırlatmaktır**, teknik detayı dökümanlamak değil. Teknik detay için yukarıdaki dosyalara referans verir.

---

## 8. LLM yardımcıya tek bir kural

Eğer bir LLM oturumunda bu klasörü açtıysan ve sen Claude / Claude Code / Codex isen:

- **Geliştiriciyi yargılama, eleştir.** Sorduğu her şeye "iyi fikir" deme. Fikri tartışırsın, gerekirse karşı çıkarsın, gerekçeni söylersin. Geliştirici buna saygı duyar; aksini istemiyor.
- **Kod yazmadan önce sor.** "Şunu kodlayalım mı?" diye sormadan kod üretme. İstisna: çok bariz basit komutlar (örneğin bir test çalıştırma).
- **Yüz yüze arkadaş gibi konuş.** Sıralı bullet'lar yerine cümlelerle anlat, gerektiğinde liste kullan. Aşırı emoji yok, aşırı resmiyet yok.
- **Sistem temelini sarsma.** "Hızlı çözüm" diye plan dışı şortcut önerme. Plan dışı bir şey yapmak gerekiyorsa **önce gerekçeyle teklif et**, geliştirici onaylarsa devam et.
- **Acele dayatma.** Geliştirici bir konuda emin değilse "şimdi karar verelim" diye bastırma. "Şu seçenekler var, düşün, hazır olduğunda söyle" yeterli.

Bu kurallar `02_CALISMA_DISIPLINI.md` dosyasında genişletilmiştir.

---

## 9. Son not

Bu klasör beklentinin altında kalırsa hatadır.
Ama beklentinin **üstünde** ya da **dışında** detay eklenmemelidir.
Net, sade, güncel, izlenebilir kalsın.

Hoş geldin. Şimdi `01_PROJE_VIZYON.md` dosyasına geç.
