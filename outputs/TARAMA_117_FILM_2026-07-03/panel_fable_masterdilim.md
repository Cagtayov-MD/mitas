HAKEM RAPORU — Dilimlenmiş reading-master → künye bağlantısı

Doğruladığım olgular (canlı sistem): K1 gerçekten kurulu ve default-AÇIK (`scripts\_pipe_credit_vl.py:158-172`, `MITAS_VL_CORPUS_DILIM=1`; her korpus satırı gerçek piksel-okuması invariantı + `### DILIM-SINIRI` → sentinel korunuyor). `scripts\master_dilim_oku.py` yerel OneOCR, ollama'sız, koordinatlı jsonl üretiyor. Ollama deposu ŞU AN BOŞ (`ollama list` = sıfır model). E:\QwenModels'da 35b-sınıfı VL YOK — sadece qwen2.5vl-7b, qwen3vl-8b, internvl3-8b ve text-only qwen3-30b-instruct-gguf var. Yani A/C'nin VL bacağı bugün fiilen koşamaz; B bugün tek çalışan yol.

a) "Fark etmez" argümanı — nerede haklı, nerede çürük:
- HAKLI olduğu çekirdek: master'ı okumak frame'leri okumaktan İYİDİR, çünkü run-aware master CLIP-bekçinin (CREDIT_MIN_RUN=10) ve stitch frekans-oylamasının kaybettiği kartları taşıyor. İHTİRAS kanıtı bunu doğruluyor: fark motor değil, MOTORA ULAŞAN PİKSELLER. Çağatay'ın sezgisi (master = üstün girdi) doğru.
- ÇÜRÜK olduğu yer: "OneOCR ha frameden ha masterdan okumuş fark etmez" cümlesi kendi planına karşı delil — madem motor fark etmiyor, o zaman aynı üstün pikselleri OneOCR'a vermek (B) aynı kapsama kazancını 0.15 sn/parça maliyetle, halüsinasyon-sıfır sağlar; İHTİRAS'ta Bill L. Norton/Chokachi'yi 1.1 sn'de EXACT okudu. Asıl fark eden ikinci eksen motorun ÜRETKEN olup olmaması: OneOCR okuyamadığında susar, VL okuyamadığında da bir isim ÜRETEBİLİR (Towles, Orhan Aksoy, John Ford). "Fark etmez" bu ekseni görmüyor.

b) A tek başına kanunlarla BAĞDAŞMAZ:
- OCR-otorite kanunu "OCR ne okuduysa o" der; VL çıktısı piksel-teyitsiz alana yazılırsa otorite VL'ye devredilmiş olur — VLM tam bu yüzden (KÖTÜ EVLAT: metin Henry Hathaway derken "John Ford") ana yoldan çıkarılmıştı. A bu kararı sessizce geri alır.
- "Okunamadı > yanlış oku": VL "okunamadı" demekte yapısal olarak kötüdür; yapılandırılmış soru ("yönetmen kim?") DOLDURMA BASKISI yaratır — boş bırakmak yerine plausible isim üretmeye iter. think=off bunu azaltmaz.
- A'da Towles-sınıfını dizginleyecek tek mekanizma yine bir piksel-teyit katmanıdır — yani B'yi yeniden icat etmek. Golden-suite 28/28 bugün tam da K1 kalkanı sayesinde Orhan-Aksoy/Towles'ı blokta tutuyor.

c) A'nın benzersiz, gerçek artıları:
- Stilize/dekoratif font, el yazısı-fırça jenerik (eski Türk filmleri), düşük kontrast/bozuk transfer, degrade zemin — OneOCR'ın kör sınıfları.
- Layout-semantik rol eşleme (sütunlu cast'te rol↔isim, "bir X filmi" kalıpları) — OneOCR satır verir, rol vermez. (Kısmi ikame: dilim_oneocr.jsonl zaten x/y koordinatı taşıyor; mekanik layout-eşleme mümkün ama proje geçmişi mekanik credit_parse'ın çöp sızdırdığını gösteriyor — temkin.)
- "35 VL-zaten-kör" vakasının kaçının aslında OneOCR-körlüğü olduğu ÖLÇÜLMEMİŞ. Doğru sıra: önce dilim-OneOCR o 35'te koşulsun; korpusun HÂLÂ boş kaldığı alt küme K2'nin gerçek hedef kitlesidir. VL'nin katma değeri ancak orada kanıtlanabilir.

d) NİHAİ HÜKÜM: C — ama katı hiyerarşiyle "B-temelli C" (A'nın planı olduğu gibi DEĞİL):
1. K1 (B) TEMEL ve ZORUNLU katman — zaten canlı, maliyet ~sıfır, ROI kanıtlı (14/17 yönetmen piksel-teyitli, golden 28/28). Hiçbir koşulda sökülmez.
2. K2 (VL master-okuma) İKİNCİL KAYNAK olarak eklenir, modeller döndüğünde. Prompt biçimi değişsin: "yönetmen kim?" tarzı yapılandırılmış soru DEĞİL (doldurma baskısı), "bu görüntüdeki metni satır satır transkribe et; okunamıyorsa okunamadı yaz" + rol eşlemeyi ikinci adımda transkript üzerinden yap. Bu, halüsinasyon yüzeyini yapısal olarak küçültür.
3. YAZMA KURALI (kesin): VL-okunan isim ancak K1 dilim-korpusunda veya ana-OCR korpusunda piksel-teyit (exact/fuzzy/crossline) bulursa alana yazılır. Teyitsiz → alan BOŞ kalır, isim insan-inceleme adayı olarak işaretlenir. Korpus-teyit ŞARTTIR.
4. ÇAPA-1 KB-kilidi tek başına YETMEZ: KB "gerçek bir insan mı" sorusuna cevap verir, "BU filmde mi" sorusuna vermez — DIAGHILEV/Dennis Hopper fabrikasyonu tam bu delikten girdi; John Ford da KB'de vardır. KB-kilit korpus-teyide EK süzgeç olabilir, ALTERNATİF olamaz.
5. Operasyonel sıra: bugün B tam kapasite (zaten canlı) → 35-vaka OneOCR-körlük kırılımı ölçülür → VL modeli geri geldiğinde K2 yalnız korpus-boş/alan-boş filmlerde pilot (35b yoksa qwen3vl-8b ile ölçüm önce) → K2 çıktısı 3. maddedeki kemerle bağlanır.

Tek cümle: Çağatay master'ın DEĞERİ konusunda haklı, o değeri VL'nin OTORİTESİNE çevirmekte haksız — piksel master'ındır, hüküm OneOCR-teyidinindir, VL yalnız teyitli aday üretir.

İlgili dosyalar: E:\MITAS\scripts\_pipe_credit_vl.py (K1 korpus, satır 158-172), E:\MITAS\scripts\master_dilim_oku.py, E:\MITAS\scripts\master_png_dilimle.py, E:\MITAS\outputs\TARAMA_117_FILM_2026-07-03\tum_sonuclar_117.json