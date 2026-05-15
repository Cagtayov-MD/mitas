# MITAS Proje Takip Klasörü

Bu klasör MITAS projesinin **operasyonel beynidir**.

Tek bir LLM oturumu açıldığında veya geliştirici aralıksız çalışmaya geri döndüğünde, **bu klasör okunarak** geçen sefer ne konuşulduğu, ne karara bağlandığı, ne yapıldığı ve sıradakinin ne olduğu anında anlaşılabilir olmalı.

---

## Dosya sırası

1. **00_BURADAN_BASLA.md** — Akış ve organizasyon dosyası. İlk burası okunur; diğer dosyalar içerik taşır.
2. **01_PROJE_VIZYON.md** — MITAS nedir, neden, ne için.
3. **02_CALISMA_DISIPLINI.md** — Nasıl çalışıyoruz, LLM yardımcı ile sözleşme.
4. **03_GUNCEL_DURUM.md** — Şu an nerede duruyoruz.
5. **05_AKTIF_GOREV.md** — Şu an üzerinde çalışılan sprint; "nerede kaldık?" ve "şunu yaptık mı?" canlı panosu.
6. **04_YOL_HARITASI.md** — Sürüm bazında nereye gidiyoruz.
7. **06_KARARLAR_GUNLUGU.md** — Verilmiş kararların kalıcı kaydı.
8. **07_REFERANS_HARITASI.md** — Hangi dosya nerede, neye yarar.
9. **08_TEST_KLIPLER.md** — Ham test klip havuzu.
10. **09_UST_DENETIM_KATMANI.md** — Faz2/üst akıl, model adayları ve kanıt isteyen review döngüsü.
11. **10_UI_NOTLARI.md** — UI davranışları, ASR/UI sözleşmesi, yapılan arayüz düzeltmeleri.
12. **11_WORKTREE_KOORDINASYON.md** — Canonical workspace, Claude worktree karışıklığı ve raporlama protokolü.
13. **12_CANLI_MUTFAK_PROTOKOLU.md** — Mutfak kaynak, canlı pano, gerçek test ve sonraya bırakılanlar protokolü.

---

## Yapısal kural

Bu klasör **canlıdır**. Akış ve organizasyon bilgisi `00_BURADAN_BASLA.md` içindedir; içerik ve ayrıntılar ilgili numaralı dosyalara dağılır. En üst kural `00_BURADAN_BASLA.md` §0 içindedir; `12_CANLI_MUTFAK_PROTOKOLU.md` bu kuralın ayrıntı kılavuzudur. Her gelişme ile ilgili dosya güncellenir.

- Yeni karar → `06_KARARLAR_GUNLUGU.md`
- Sprint değişimi → `05_AKTIF_GOREV.md` arşivlenir, yenisi yazılır
- Sürüm yapısı değişirse → `04_YOL_HARITASI.md`
- Yeni paket/dosya/araç → `03_GUNCEL_DURUM.md` ve gerekirse `07_REFERANS_HARITASI.md`
- Yeni prensip → `01_PROJE_VIZYON.md` veya `02_CALISMA_DISIPLINI.md`
- Üst-denetim / LLM-VLM model seçimi → `09_UST_DENETIM_KATMANI.md`
- UI davranışı / arayüz düzeltmesi → `10_UI_NOTLARI.md`
- Worktree / branch / canonical workspace karışıklığı → `11_WORKTREE_KOORDINASYON.md`
- Canlı takip, "nerede kaldık", ertelenenler/yapılanlar/test kayıtları → `12_CANLI_MUTFAK_PROTOKOLU.md` ve `05_AKTIF_GOREV.md`
- Takip ID'leri ve sabit durum sözlüğü → `12_CANLI_MUTFAK_PROTOKOLU.md` §5; canlı uygulama → `05_AKTIF_GOREV.md` §0

Eski kararlar **silinmez**, üstü çizili kalır. Neden değiştiğini hatırlamak için.

---

## LLM yardımcı ile çalışıyorsan

Eğer Claude / Claude Code / Codex isen ve bu klasöre yönlendirildiysen:

1. **Önce sırayla 00 → 12 dosyalarını oku.** On dakikalık iş, atlanmaz.
2. **Sonra `02_CALISMA_DISIPLINI.md` §5 protokolünü içselleştir.** Bu projenin çalışma tonunu belirler.
3. **`05_AKTIF_GOREV.md` ile devam et.** Şu anki odak orada.

Geliştirici ile aynı bilinç düzeyine geldikten sonra konuşmaya başla. Önceden bilgi vermek için acele etme.

---

## Klasör adı

`_proje_takip` — alt çizgi başta tutulur ki E:\MITAS listelendiğinde tepede dursun.

İçindeki dosyalar sayı önekli (00, 01, ..., 12) okuma sırasını belli eder.

---

## Bu klasör neye dokunmaz

- Teknik karar detayı → `MITAS_Master_Plan_Denetimli_v5.md`
- Sprint kurulum/denetim raporları → `docs/`
- JSON audit çıktıları → `outputs/`
- Pipeline / pipeline kodu → `core/`

Bu klasör **yön gösterir ve hatırlatır**, teknik detay tutmaz.
