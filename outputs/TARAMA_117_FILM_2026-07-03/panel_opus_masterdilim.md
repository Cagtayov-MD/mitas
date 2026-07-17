Tüm kanıtlar teyitli. `web_identity` ÇAPA-1 gerçekten film-özgül (imdb_find title+original+year → o filmin yönetmen listesinde OCR-yönetmeni ara → eşleşirse locked=director). ÇAPA-2/tmdb ise kod yorumunda "versiyon-teyitsiz" diye açıkça ayrılmış ve VL kalkanında reddediliyor (satır 413, `method=='director' ŞART`).

Elimde net tablo var. Hükmü veriyorum.

---

# HAKEM HÜKMÜ: Dilim reading-master → künye bağlanması

**Kritik önbulgu (soruyu çerçeveler): Seçenek-C zaten kod-canlı, siz A-mı-B-mi diye soruyorsunuz ama sistemin fiili hali C.** `_pipe_credit_vl.py:164-177` dilim-OneOCR korpusunu hayalet-kalkanına additive besliyor (K1), VL zaten gap-filler olarak bağlı (K2), ÇAPA-1 KB-kilidi (A2) çalışıyor. 111/118 filmde `dilim_oneocr.txt`, 549 parça mevcut. Yani hüküm "sıfırdan hangisi" değil, **"mevcut C'yi mi koruyalım, yoksa Çağatay'ın A'sına mı geçelim"** sorusudur. Kanıtlar C'nin korunmasını söylüyor.

## a) "Fark etmez" argümanı — nerede haklı, nerede kanıtla çelişiyor

**Haklı olan çekirdek:** "OneOCR ha frameden ha masterdan okumuş" — *motor eşdeğerliği* doğru. OneOCR yerel, deterministik, 0.15 sn/parça, halüsinasyon üretmez. Master'dan okumak frameden okumaktan **daha iyi** çünkü İHTİRAS'ta kanıtlandı: `David Chokachi` + `DIRECTED BY / Bill L. Norton` ana zincirde YOKKEN dilim-OneOCR 91 satırda exact okudu. Yani Çağatay master'ın **girdi üstünlüğünde** %100 haklı.

**Kanıtla çelişen kısım:** Çağatay bu cümleyi OneOCR→OneOCR eşdeğerliği için kurdu ama onu **OneOCR-yerine-VL** kararına genişletiyor. Bu geçersiz bir genişletme. Sizin kendi ampirik bulgunuz (madde 1) "fark motor değil, MOTORA ULAŞAN PİKSELLER" diyor — ve bu bulgu tam da **girdiyi değiştir, motoru değiştirme** sonucunu veriyor. Master'a geçmek kaybı çözüyor; motoru VL yapmak ise madde 3'teki halüsinasyon sicilini (Towles/Orhan-Aksoy/John-Ford) geri davet ediyor. Kısaca: **"master frameden iyi" doğru; "o yüzden VL OneOCR'dan iyi" kanıtsız ve tehlikeli.**

## b) VL-birincil (A) tek başına projenin kanunlarıyla bağdaşır mı — HAYIR

İki kurucu kanunla doğrudan çatışır:
- **OCR-OTORİTE KANUNU** (EN ÜST KURAL): "OCR ne okuduysa o." VL-birincil, otoriteyi pikselden-okumayan-bir-modele devreder. VL layout-semantik yapar ama isim *icat edebilir* — bu tam olarak KÖTÜ EVLAT vakasında oldu (metin Hathaway derken VLM "John Ford" dedi; VLM bu yüzden zaten ana yoldan çıkarılmıştı). A onu geri koyar.
- **OKUNAMADI > YANLIŞ-OKU KANUNU:** VL asla "okuyamadım" demez, en olası ismi *uydurur*. Bu kanunun ihlali A'nın yapısal özelliğidir, bir bug değil.

**Towles/Orhan-Aksoy sınıfını A'da ne dizginler? — Hiçbir şey yapısal olarak.** A'da VL çıktısı doğrudan alana yazılır; kalkan yok. Golden-suite'in bugün 28/28 temiz olması *korpus-kalkanı sayesinde* — kalkanı söken A, o 28'i korumaz. Üstelik operasyonel gerçek A'yı bugün imkânsız kılıyor: **ollama deposu boş (F: olayı), VL fiilen çalışmıyor.** A tek-yol olsaydı bugün künye üretimi sıfır olurdu; OneOCR-C ise çalışıyor.

## c) A'nın benzersiz artıları — gerçekte ne kadar belirleyici

VL'nin OneOCR'ın yapamadığı gerçek yetenekleri var: **stilize/dekoratif font, düşük kontrast, layout-semantik rol eşleme** (hangi isim "yönetmen" etiketinin altında). Bunlar gerçek ve değerlidir.

**Ama "35 VL-zaten-kör vakası" iddiasını kanıt zayıflatıyor:** Bu vakaların önemli kısmı VL-körlüğü değil **girdi-körlüğü** — kart CLIP-seçiminde eleniyordu, motora hiç ulaşmıyordu (İHTİRAS deseni). Girdiyi master'a çevirince (C'nin K1'i) bu vakaların çoğu VL gerektirmeden çözülüyor: madde 2 kanıtı — 17 kayıp yönetmenin 14'ü dilim-OneOCR korpusuyla piksel-teyitli (11 exact/2 fuzzy/1 crossline). Yani "VL-zaten-kör" sanılanların çoğu aslında **OneOCR-körü değil, eski-girdi-körü.** VL'nin *gerçekten* belirleyici olduğu kalan pay dardır: OneOCR'ın master'da bile çözemediği ağır-stilize font + rol-belirsizliği. O dar pay için VL gap-filler olarak tutulmalı — ama **birincil-otorite değil, kalkan-altında.**

## d) NİHAİ HÜKÜM: **C (mevcut hibrit) — koru ve iki noktada sertleştir. A reddedilir, B eksiktir.**

**Sıra:**
1. **OneOCR-dilim = PRIMARY girdi otoritesi** (K1). Metin künye-okuma yolu (`_pipe_credit_text`) OneOCR-master-dilimi görmeli. **Şu an görmüyor** — dilim-korpusu yalnız VL-kalkanına (`_pipe_credit_vl._load_raw_ocr`) bağlı; primary `_pipe_credit_text` sadece `ocr/*/kunye.txt`'yi (CLIP-seçili, dar) okuyor. **Bu C'nin tek gerçek boşluğu:** İHTİRAS'ın Norton'u primary'ye hâlâ girmiyor, sadece VL uydurursa kalkandan geçebiliyor. Bu ters — girdi zenginliği kalkanda değil, otoritede olmalı.
2. **VL = yalnız gap-filler** (QC1-RED tetikli: yönetmen boş VEYA cast<3), mevcut tetikleme doğru.
3. **VL çıktısı alana YALNIZCA korpus-teyitliyse yazılır.** Bu şart olmalı, gevşetilmemeli.

**Güvenlik kemerleri (mevcut, korunmalı):**
- Hayalet-kalkanı korpus-teyidi (exact/fuzzy/crossline) — **şart.** VL adayı gerçek piksel-satırında yoksa alana yazılmaz.
- ÇAPA-1 KB-kilidi (`web_identity method=='director'`) korpus TAM-kör kaldığında son-şans olarak **yeter mi? — koşullu yeter.** Kanıt: kod film-özgül (imdb_find title+original+year → o filmin yönetmeninde ara). ÇAPA-2/tmdb (title+year, versiyon-teyitsiz) **reddedilmeye devam etmeli** — kod satır 413 bunu zaten yapıyor, doğru. ÇAPA-1'in tek başına yazması **shadow-döneminde KONTROL etiketiyle** kalmalı (sessiz-ONAYLI yok) — bugünkü davranış budur, korunmalı.
- fuzzy/crossline yoluyla dolan yönetmen exact'ten ayrık işaretlenip KONTROL'e gitmeli (mevcut `vl_yon_kaynak` suffix'i bunu yapıyor).

**Tek somut aksiyon (C'yi tamamlar):** `master_dilim/dilim_oneocr.txt`'yi **primary metin-okuma girdisine** de bağla (kalkan-korpusuna ek olarak) — ki İHTİRAS/Norton VL'nin uydurmasına muhtaç kalmadan doğrudan otoriteden çıksın. Şu an dilim yalnız *doğrulama* tarafında; *okuma* tarafında değil. Kanun ("okunamadı>yanlış") açısından güvenli: OneOCR uydurmaz, additive satır sadece recall artırır.

**Neden B tek başına yetmez:** B, VL'yi doğrular ama VL çalışmadığında (bugünkü F:-durumu) ve VL-tetiklenmeyen filmlerde dilim-master'ın recall'unu primary'ye taşımaz — 14/17 kurtarma ancak korpus okuma-yoluna da bağlanırsa tam meyve verir. **Neden A tek başına reddedilir:** OCR-otorite + okunamadı>yanlış kanunlarını yapısal olarak ihlal eder, bugün fiilen çalışamaz, ve "belirleyici" sandığı 35 vakanın çoğu aslında girdi-körüdür, VL-gerektirmez.

---

**Tek cümle hüküm:** Master-dilimi VL'nin gözü değil, **OneOCR'ın otoritesi** yap — dilim-korpusunu hem primary okuma-yoluna hem kalkana bağla (C-tam); VL'yi yalnız korpus-teyitli/ÇAPA-1-director-kilitli gap-filler olarak, KONTROL-shadow altında tut; "fark etmez" argümanı girdi için doğru, motor-otorite için kanıta aykırıdır.

**İlgili kanıt dosyaları:**
- `E:\MITAS\scripts\_pipe_credit_vl.py:164-177` (K1 dilim-korpus additive besleme — CANLI)
- `E:\MITAS\scripts\_pipe_credit_vl.py:400-457` (hayalet-kalkanı + ÇAPA-1 KB-kilidi — CANLI)
- `E:\MITAS\scripts\_pipe_credit_text.py:26-30,45` (primary yol — dilim-korpusu GÖRMÜYOR, boşluk)
- `E:\MITAS\scripts\master_dilim_oku.py` (K1 OneOCR-dilim okuyucu — CANLI, yerel, ollama-bağımsız)
- `E:\MITAS\scripts\credit_qc_gates.py:151-219` (`web_identity` ÇAPA-1 film-özgül director-lock — versiyon-teyitli)
- `E:\MITAS\Database\İHTİRAS CİNAYETİ 2003-9048-1-0000-00-1\master_dilim\dilim_oneocr.txt` (Norton/Chokachi exact kanıtı)
- Ollama deposu (`F:\REPO_GitHub\.ollama\models\blobs`) BOŞ — VL bugün çalışamaz (A operasyonel olarak imkânsız).