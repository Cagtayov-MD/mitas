# 02 — ÇALIŞMA DİSİPLİNİ

> Son güncelleme: 2026-05-10
> Son değişen bölüm: ilk sürüm

Bu dosya MITAS projesinde **nasıl çalışıldığını** anlatır. Bir insan ile bir veya birden fazla LLM yardımcı arasındaki **çalışma sözleşmesidir**.

---

## 1. Geliştirici profili

- **Tek kişilik geliştirici.** Çağrılan adıyla: Ç.
- Hem geliştiricidir, hem test set sahibidir, hem ground truth sahibidir, hem ürün sahibidir.
- Tek kişi olması bir kısıttır; planlama ve karar verme bu kısıta saygı gösterir.
- Stres altında yargı bozulur. Yorgun karar verilmez.

---

## 2. Sürdürülebilir tempo

- Günde **10-12 saat odaklı çalışma**, aralarda 10-15 dakika molalar.
- Gece **6-7 saat uyku kesin**. Gece boyu çalışma sürdürülebilir değil ve günü kaybettirir.
- Bir oturumda planlanan süreyi **1.5 katından fazla aşan iş**: dur, geri çekil, başka yaklaşım dene.
- Bir kavşakta tıkanıldıysa: 10-15 dakika çekil, kahve, yürüyüş, sonra dön. Israrla aynı duvara vurmak zaman kaybıdır.

26 saatlik tek oturum üretkenliği değil, sonraki gün kaybını çağırır. Bu deneyimle öğrenildi.

---

## 3. Karar verme çerçevesi

Her özellik, model, motor veya mod için dört soru sorulur:

1. **Gerçekten gerekli mi?**
2. **Bizim koşullarımızda kullanılabilir mi?** Türkçe, RTX 3090, lisans, eski arşiv malzemesi.
3. **Maliyeti değer mi?** Karmaşa, runtime, bakım yükü.
4. **Ne zaman?** v1, v2, hiç.

Sonuç üç kovadan birine düşer:

- **Tut:** v1 veya net yakın hedef.
- **Ertele:** değerli ama şimdi değil.
- **Çıkar:** maliyet/fayda oranı kötü veya ana hedefe zarar veriyor.

İki yerleşik disiplin:

- **Tek seçenek mantığı:** Master plan birden fazla alternatifle şişirilmez. Ana seçenek seçilir; yedekler benchmark koşuluyla yazılır.
- **Showcase ≠ Final analiz:** Demo/sunum pipeline'ı gerçek metadata üreten final analizden ayrıdır.

---

## 4. Çalışma temposunda iki tür konuşma alanı

### 4.1 Karar Alanı (varsayılan)

Standart konuşma. Geliştirici bir soru sorar, LLM cevap verir, gerekirse tartışılır, karara bağlanır. Karar `06_KARARLAR_GUNLUGU.md`'ye düşer.

### 4.2 Fırtına Alanı

Geliştirici `///` ile bir konu açar, `///son` ile kapatır.

- Amaç: fikri tartışmak, eleştirmek, teste tabi tutmak, doğruluğunu ve uygunluğunu bulmak.
- Bu alandaki her şey **kalıcı karar değil**, beyin fırtınasıdır.
- `///son` ile kapatıldıktan sonra ortaya çıkan bir karar **açıkça** "şunu kararlaştırıyoruz" diye geliştirici tarafından söylenmedikçe kalıcı olmaz.
- Fırtına Alanı'nda LLM serbestçe karşı çıkar, alternatifler önerir, "bu kötü fikir çünkü..." der.

### 4.3 NOT++ talebi

Geliştirici bir konuyu kalıcı hatırlatma olarak istediğinde **`NOT++`** der.

- LLM bu talebe karşı: konuyu sonradan ayrı bir oturumda yeniden açıldığında **tam olarak anlaşılabilecek** bir özet/not üretir.
- Çıktı .md formatında olur ve geliştiricinin uygun gördüğü yere kaydedilir.
- Süslemeden, gereksiz uzatmadan, hatırlatma niyetine uygun.

---

## 5. LLM yardımcı ile çalışma protokolü

Bu bölüm Claude / Claude Code / Codex gibi yardımcıların **uyması beklenen kurallarıdır**. Yeni bir oturuma başlayan LLM bu bölümü okuyarak projenin tonuna geçer.

### 5.1 Sormadan kodlamak yok

- Kod yazmadan önce **"Şunu kodlayalım mı?"** diye sorulur.
- İstisna: çok bariz basit komutlar (örneğin `pytest -k something`, `pip list`, mevcut dosyayı `view` etmek).
- Sorudan sonra yeşil ışık gelmedikçe kod yazılmaz.

### 5.2 Kod ile değil cümleyle anlatmak

- Geliştirici kod istemediği sürece **çözüm fikri kod bloklarıyla** değil **cümlelerle** anlatılır.
- "Şu fonksiyonu yazarız" değil, "şu paketi çağırıp şu fonksiyonu kullanırız, dönen değer şunu içerir" şeklinde.
- Geliştirici **kod yazmaya hazır olduğunda söyler.** O zaman kodlanır.

### 5.3 Eleştir, yes-man olma

- Geliştirici "şunu yapalım" dediğinde **otomatik onaylama**.
- Fikir zayıfsa neden zayıf olduğunu söyle.
- Daha iyi alternatif varsa öner.
- Geliştiricinin saygı duyduğu LLM, ona katılan değil, doğruyu birlikte arayandır.

### 5.4 Acele dayatma yok

- "Hemen karar verelim" baskısı yapmak yok.
- "Şu seçenekler var, şu artıları şu eksileri, düşünmeye zaman ver" tonu.
- Geliştirici emin değilse: kararı erteleyebilir, ayrı dosyaya yazılabilir.

### 5.5 Sistem temelini sarsma

- "Hızlı çözüm" diye plan dışı kısayollar **önerilmez**.
- Plan dışına çıkmak gerekiyorsa: **önce gerekçeyle teklif edilir**, geliştirici onaylarsa devam edilir.
- v5 master plan, bu klasör ve `MITAS_Uygulama_Plani_v1.md` üçü bağlayıcıdır.

### 5.6 Aşama aşama ilerleme

- Bir konuda ilerlerken: küçük, test edilebilir adımlar.
- Her adım sonunda durup "tamam, sıradaki?" yerine **"bunu doğruladık mı?"** kontrolü.
- Bir adım çalışmadan diğerine geçilmez.

### 5.7 Sadakat ve kayıt

- Her oturumda **bu klasör okunarak başlanır**, kapanırken **gerekli güncellemeler önerilir**.
- "Bir önceki oturumda şöyle demiştik" tipi tartışmalar **yazılı kayda** dayanmalı; LLM hafızasına değil.

---

## 6. Konuşma tarzı

- **Yüz yüze arkadaş gibi.** Aşırı resmiyet yok, aşırı emoji yok.
- Geliştirici bir terimi bilmiyorsa "kodla açıklama" değil, "anlatarak açıklama".
- Geliştirici kod yazmaya hazır olduğunda kod konuşulur.
- Cümleler doğal Türkçe; bullet listeleri sadece gerekli olduğunda.

---

## 7. Test, ground truth, kabul

- Test seti sahibi: **geliştirici (Ç.)**.
- Ground truth sahibi: **geliştirici (Ç.)**.
- Bu rol tek kişiye düşüyor; bu kişinin zamanı ve enerjisi sınırlı.
- O sebeple test setleri **aşamalı** kurulur (önce 1 saat smoke, sonra 5 saat mini, sonra 20 saat v1).
- "20 saat test seti hazırla" gibi monolit görevler dağıtılır, monolit hedeflerle stresi büyütülmez.

---

## 8. Commit ve dokümantasyon disiplini

- Her shift sonunda commit.
- Karar değiştikçe `06_KARARLAR_GUNLUGU.md` güncellenir.
- Aktif sprint biterken `05_AKTIF_GOREV.md` arşivlenir / güncellenir.
- v5 master plan değişirse versiyon arttırılır (v5 → v5.1 değil v6); büyük değişiklikler ayrı dosya.

---

## 9. Bu disiplinin nedeni

Tek kişi geliştiriyorsun, bir taraftan model seçiyorsun, bir taraftan benchmark planlıyorsun, bir taraftan UI tasarlıyorsun, bir taraftan KVKK düşünüyorsun. Kafa kapasitesi sınırlı.

Bu disiplinin amacı **kapasiteni boş yere harcamamak**. Ne her toplantıda baştan başlamak, ne her oturumda "geçen sefer ne demiştik" stresi, ne de yorgun kafayla yanlış karar.

Doğru karar verdikten sonra **bu klasöre yaz**, gerisini bırakan klasör halletsin.

---

## 10. Bir cümle ile

Acele etmeyiz, savsaklamayız, yalan teselli vermeyiz, fikre değil sonuca bakarız, kararlarımızı yazarız.
