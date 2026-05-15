# 00 — BURADAN BAŞLA

> Bu dosya mutfak klasörünün **akış ve organizasyon dosyasıdır**.
> İçeriğin tamamını burada tutmaz; hangi durumda hangi mutfak dosyasına bakılacağını ve hangi gelişmenin nereye yazılacağını söyler.
> Diğer mutfak dosyaları içerik, karar, plan, durum ve kanıt taşır.

---

## 0. İlk komut - Canlı Mutfak kaynak protokolü

Bu dosyanın bu bölümü mutfak klasörünün **en üst çalışma kuralıdır**. `12_CANLI_MUTFAK_PROTOKOLU.md` bu kuralın ayrıntı kılavuzudur; çelişki olursa önce bu bölüm düzeltilir ve bağlayıcı kaynak burası kabul edilir.

Kullanıcı "mutfak kaynak", "nerede kaldık", "kaldığımız yerden devam" veya benzer bir ifade kullandığında bu klasör **tek kaynak** kabul edilir.

Değişmez kural:

- Canonical workspace: `E:\MITAS`
- Canlı pano: `05_AKTIF_GOREV.md`
- Karar defteri: `06_KARARLAR_GUNLUGU.md`
- Worktree kontrolü: `11_WORKTREE_KOORDINASYON.md`
- Canlı mutfak protokolü: `12_CANLI_MUTFAK_PROTOKOLU.md`
- Takip ID formatı: `PARK-*`, `TASK-*`, `DONE-*`, `TEST-*`, `DEC-*`
- Sabit durum sözlüğü: `Açık`, `Ertelendi`, `Karar bekliyor`, `Devam ediyor`, `Yapıldı`, `Test edildi`, `Kapatıldı`, `İptal edildi`

Her gerçek işlemden sonra mutfak güncellenir:

- iş bittiyse `05_AKTIF_GOREV.md` yapılanlar/kapananlar bölümüne işlenir,
- gerçek test koşulduysa komut ve sonuç `05_AKTIF_GOREV.md` içine yazılır,
- karar verildiyse `06_KARARLAR_GUNLUGU.md` içine yazılır,
- konu ertelendiyse `05_AKTIF_GOREV.md` sonraya bırakılanlar listesine girer,
- ertelenen konu çözülürse açık listeden kapanan/yapılan işe taşınır.

Mutfak güncellenmeden "tamamlandı" denmez. Bu klasör canlıdır; GPT, Opus, Claude Code veya başka bir yardımcı aynı takip sistemine rapor vermekle yükümlüdür.

Bir iş ancak şu kayıtlar varsa tamamlandı sayılır: gerçek workspace/cwd belirtilmiş, değişen dosyalar yazılmış, test koşulduysa komut-sonuç yazılmış veya test koşulmadıysa açıkça belirtilmiş, `05_AKTIF_GOREV.md` canlı pano güncellenmiş, karar niteliği varsa `06_KARARLAR_GUNLUGU.md` işlenmiş, worktree/branch riski varsa `11_WORKTREE_KOORDINASYON.md` ile doğrulanmış.

Bu bölüme yeni bir çalışma kuralı eklendiğinde aynı kural başka dosyalarda uzun uzun tekrar edilmez; ilgili ayrıntı dosyasına sadece referans verilir. Amaç tek kaynak, az tekrar, sıfır çelişkidir.

---

## 1. Organizasyon modeli

`00_BURADAN_BASLA.md` = **akış bilgisi**.

Diğer dosyalar = **içerik bilgisi**.

Bu ayrım değişmez:

| Soru / ihtiyaç | İlk bakılacak yer | Ne için? |
|---|---|---|
| Nerede kaldık? | `05_AKTIF_GOREV.md` | Canlı pano, açık işler, sıradaki adım |
| Şunu yaptık mı? | `05_AKTIF_GOREV.md` | Yapılanlar/kapananlar ve açık park listesi |
| Bu karar verilmiş miydi? | `06_KARARLAR_GUNLUGU.md` | Kalıcı karar ve gerekçe |
| Sırada hangi sürüm/iş var? | `04_YOL_HARITASI.md` | Yol haritası ve v0.x/v1 akışı |
| Genel durum ne? | `03_GUNCEL_DURUM.md` | Sistem/env/modül durumu |
| Hangi dosya nerede? | `07_REFERANS_HARITASI.md` | Referans, output, script ve belge haritası |
| Test klibi/dataset neydi? | `08_TEST_KLIPLER.md` | Test malzemesi ve kullanım amacı |
| Üst-denetim / model seçimi ne durumda? | `09_UST_DENETIM_KATMANI.md` | Faz2/üst akıl kararları |
| UI davranışı ne durumda? | `10_UI_NOTLARI.md` | UI sözleşmesi ve arayüz notları |
| Başka worktree'de mi çalışıyoruz? | `11_WORKTREE_KOORDINASYON.md` | Canonical workspace ve worktree kontrolü |
| Mutfak nasıl canlı tutulacak? | `12_CANLI_MUTFAK_PROTOKOLU.md` | Güncelleme, test, erteleme, kapanış kuralları |
| Bir maddeyi nasıl takip edeceğiz? | `12_CANLI_MUTFAK_PROTOKOLU.md` | ID formatı, durum sözlüğü, tamamlandı kriteri |

Yeni bir kural eklenecekse önce bu dosyanın §0 veya §1 bölümüne kısa akış kuralı olarak yazılır. Ayrıntısı ilgili içerik dosyasına gider.

---

## 2. Bu klasör nedir, neden var

MITAS, tek kişi tarafından geliştirilen TRT arşivi için Türkçe-merkezli medya analiz sistemidir. Geliştirme süreci uzun ve katmanlıdır; Claude (web), Claude Code (Opus 4.7) ve gerekirse Codex gibi LLM araçlarıyla paralel ilerlemektedir.

LLM oturumları **token sınırına girer ve kapanır**. Yeni oturum açıldığında "geçen sefer ne konuşmuştuk" stresi yaşanmamalıdır. Bu klasör tam bunun için var:

- her oturuma aynı bilinç düzeyinde başlamak,
- aynı disiplin tonunu sürdürmek,
- aynı kararlara sahip çıkmak,
- "ay ne yapıyorduk?" telaşını ortadan kaldırmak.

Bu sebeple bu klasör **proje koduyla aynı disiplinle** tutulur: her karar değiştiğinde ilgili dosya güncellenir, eskiyen bölümler çizilir, yeni kararlar tarihiyle eklenir.

---

## 3. Klasörü kim okur

İki muhatap var:

**(A) Geliştirici (Ç.)** — Tek kişilik geliştirici. Bir oturum kapatıp diğerini açtığında bu klasörden başlar. Aktif sprintini, açık kararlarını, son durumunu buradan hatırlar.

**(B) LLM yardımcı (Claude / Claude Code / Codex)** — Yeni oturuma başlayan herhangi bir LLM, "MITAS projesinde sana yardım edeceğim" denilerek bu klasöre yönlendirildiğinde, **aynı ciddiyet ve aynı tonla devam etmek üzere** buraya bakar. Geçici bir asistan değil, projenin kuralları içine girmiş bir yardımcı olarak.

---

## 4. Okuma sırası (önemli — atlatma)

Bir LLM oturumuna başlarken dosyalar şu sırayla okunmalıdır:

1. **00_BURADAN_BASLA.md** ← bu dosya, çatıyı verir
2. **01_PROJE_VIZYON.md** ← MITAS nedir, neden, ne için
3. **02_CALISMA_DISIPLINI.md** ← nasıl çalışılır, nasıl konuşulur
4. **03_GUNCEL_DURUM.md** ← şu an nerede duruyoruz
5. **05_AKTIF_GOREV.md** ← şu an üzerinde çalışılan iş
6. **04_YOL_HARITASI.md** ← sırada neler var
7. **06_KARARLAR_GUNLUGU.md** ← geçmişte ne karara bağlandı
8. **07_REFERANS_HARITASI.md** ← hangi dosya nerede
9. **08_TEST_KLIPLER.md** ← ham test klip havuzu
10. **09_UST_DENETIM_KATMANI.md** ← Faz2 üst-denetim / "üst akıl" katmanı, model adayları
11. **10_UI_NOTLARI.md** ← UI davranışları ve ASR/UI sözleşmesi
12. **11_WORKTREE_KOORDINASYON.md** ← canonical workspace / Claude worktree karışıklığı protokolü
13. **12_CANLI_MUTFAK_PROTOKOLU.md** ← mutfak kaynak / canlı pano / sonraya bırakılanlar protokolü

**On dakikada hepsi okunur.** Bunu yapmadan kod konuşması başlamaz.

---

## 5. Çekirdek özet — "tek paragrafta MITAS"

> MITAS, VITOS'un halefi olan, Türkçe-merkezli, web tabanlı, kurum içi çalışan video/medya analiz sistemidir. Çekirdek modülleri ASR, Face Recognition, Görsel Tagleme, OCR & Text Extraction, Audio Activity, Song Recognition, Timeline ve Review UI'dir. RTX 3090 / 24 GB VRAM hedef donanımdır. Geliştirme tek kişiliktir, LLM destekli ama disiplinlidir. Yanlış metadata eksik metadata'dan zararlıdır; her sonuç evidence ile açıklanabilir olmalıdır. Aday ilişki (candidate) ile kesin kimlik (identity) ayrı katmanlardır. Demo ile final analiz aynı şey değildir.

---

## 6. Şu an aktif

**Aktif sürüm hedefi:** v0.1 — ASR dikey dilim.
**Aktif odak:** ASR pipeline + Faz2 üst-denetim tasarımı. ASR production wrapper ve phase2 hook iskeletleri var; üst-denetim modeli ve kanıt döngüsü karara bağlanıyor.
**Bloke olan:** Üst-denetim için nihai model seçimi ve benchmark seti netleşmeli.
**Sonraki adım:** `05_AKTIF_GOREV.md` ve `09_UST_DENETIM_KATMANI.md` içine bak.

---

## 7. Sürüm ve güncelleme disiplini

Her dosyanın başında **son güncelleme tarihi** ve **son değişen bölüm** yazar.
Karar değiştiğinde:
- ilgili dosya güncellenir,
- eski karar üstü çizili olarak bırakılır (silinmez — neden değiştiğini hatırlamak için),
- `06_KARARLAR_GUNLUGU.md` dosyasına yeni satır eklenir.

Bu klasör **canlıdır**. Statik bir doküman değil, projenin nabzı.

---

## 8. Bu klasör neye dokunmaz

Bu klasör aşağıdakileri **kapsamaz**:

- Master plan (`MITAS_Master_Plan_Denetimli_v5.md`) — teknik karar dosyası, ayrı.
- Uygulama planı (`MITAS_Uygulama_Plani_v1.md`) — sprint detayı, ayrı.
- `docs/` altındaki sprint raporları — kurulum/denetim çıktıları, ayrı.
- `outputs/` altındaki JSON raporları — operasyonel artefakt, ayrı.

Bu klasörün görevi **yön vermek ve hatırlatmaktır**, teknik detayı dökümanlamak değil. Teknik detay için yukarıdaki dosyalara referans verir.

---

## 9. LLM yardımcıya tek bir kural

Eğer bir LLM oturumunda bu klasörü açtıysan ve sen Claude / Claude Code / Codex isen:

- **Geliştiriciyi yargılama, eleştir.** Sorduğu her şeye "iyi fikir" deme. Fikri tartışırsın, gerekirse karşı çıkarsın, gerekçeni söylersin. Geliştirici buna saygı duyar; aksini istemiyor.
- **Kod yazmadan önce sor.** "Şunu kodlayalım mı?" diye sormadan kod üretme. İstisna: çok bariz basit komutlar (örneğin bir test çalıştırma).
- **Yüz yüze arkadaş gibi konuş.** Sıralı bullet'lar yerine cümlelerle anlat, gerektiğinde liste kullan. Aşırı emoji yok, aşırı resmiyet yok.
- **Sistem temelini sarsma.** "Hızlı çözüm" diye plan dışı şortcut önerme. Plan dışı bir şey yapmak gerekiyorsa **önce gerekçeyle teklif et**, geliştirici onaylarsa devam et.
- **Acele dayatma.** Geliştirici bir konuda emin değilse "şimdi karar verelim" diye bastırma. "Şu seçenekler var, düşün, hazır olduğunda söyle" yeterli.

Bu kurallar `02_CALISMA_DISIPLINI.md` dosyasında genişletilmiştir.

---

## 10. Son not

Bu klasör beklentinin altında kalırsa hatadır.
Ama beklentinin **üstünde** ya da **dışında** detay eklenmemelidir.
Net, sade, güncel, izlenebilir kalsın.

Hoş geldin. Şimdi `01_PROJE_VIZYON.md` dosyasına geç.
