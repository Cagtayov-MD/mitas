# MITAS Proje Takip Klasörü

Bu klasör MITAS projesinin **operasyonel beynidir**.

Tek bir LLM oturumu açıldığında veya geliştirici aralıksız çalışmaya geri döndüğünde, **bu klasör okunarak** geçen sefer ne konuşulduğu, ne karara bağlandığı, ne yapıldığı ve sıradakinin ne olduğu anında anlaşılabilir olmalı.

---

## Dosya sırası

1. **00_BURADAN_BASLA.md** — Yön levhası. İlk burası okunur.
2. **01_PROJE_VIZYON.md** — MITAS nedir, neden, ne için.
3. **02_CALISMA_DISIPLINI.md** — Nasıl çalışıyoruz, LLM yardımcı ile sözleşme.
4. **03_GUNCEL_DURUM.md** — Şu an nerede duruyoruz.
5. **04_YOL_HARITASI.md** — Sürüm bazında nereye gidiyoruz.
6. **05_AKTIF_GOREV.md** — Şu an üzerinde çalışılan sprint.
7. **06_KARARLAR_GUNLUGU.md** — Verilmiş kararların kalıcı kaydı.
8. **07_REFERANS_HARITASI.md** — Hangi dosya nerede, neye yarar.

---

## Yapısal kural

Bu klasör **canlıdır**. Her gelişme ile ilgili dosya güncellenir.

- Yeni karar → `06_KARARLAR_GUNLUGU.md`
- Sprint değişimi → `05_AKTIF_GOREV.md` arşivlenir, yenisi yazılır
- Sürüm yapısı değişirse → `04_YOL_HARITASI.md`
- Yeni paket/dosya/araç → `03_GUNCEL_DURUM.md` ve gerekirse `07_REFERANS_HARITASI.md`
- Yeni prensip → `01_PROJE_VIZYON.md` veya `02_CALISMA_DISIPLINI.md`

Eski kararlar **silinmez**, üstü çizili kalır. Neden değiştiğini hatırlamak için.

---

## LLM yardımcı ile çalışıyorsan

Eğer Claude / Claude Code / Codex isen ve bu klasöre yönlendirildiysen:

1. **Önce sırayla 00 → 07 dosyalarını oku.** Yedi dakikalık iş, atlanmaz.
2. **Sonra `02_CALISMA_DISIPLINI.md` §5 protokolünü içselleştir.** Bu projenin çalışma tonunu belirler.
3. **`05_AKTIF_GOREV.md` ile devam et.** Şu anki odak orada.

Geliştirici ile aynı bilinç düzeyine geldikten sonra konuşmaya başla. Önceden bilgi vermek için acele etme.

---

## Klasör adı

`_proje_takip` — alt çizgi başta tutulur ki E:\MITAS listelendiğinde tepede dursun.

İçindeki dosyalar sayı önekli (00, 01, ..., 07) okuma sırasını belli eder.

---

## Bu klasör neye dokunmaz

- Teknik karar detayı → `MITAS_Master_Plan_Denetimli_v5.md`
- Sprint kurulum/denetim raporları → `docs/`
- JSON audit çıktıları → `outputs/`
- Pipeline / pipeline kodu → `core/`

Bu klasör **yön gösterir ve hatırlatır**, teknik detay tutmaz.
