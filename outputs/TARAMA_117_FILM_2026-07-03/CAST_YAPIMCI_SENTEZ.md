# CAST+YAPIMCI DOĞRULUK — KANUN-SÜZGEÇLİ NİHAİ SENTEZ (104 film)

Kaynak: `E:\MITAS\outputs\TARAMA_117_FILM_2026-07-03\CAST_YAPIMCI_DOGRULUK_104.json`

Süzgeç-3 ön-kontrol sonucu: **104 filmdeki HİÇBİR bulgu ekran-kanıtsız değil** — her `kanit` alanı somut OCR satır no./frame PNG/bbox içeriyor. Dolayısıyla "versiyon-şüphesi" kategorisine düşen sıfır vaka var; bu süzgeç mevcut veri setinde pratikte devre dışı kaldı (ileride ekran-kanıtsız salt-web hükümler çıkarsa bu kanun devreye girecek).

---

## A. SÜZGEÇ-SONRASI TEMİZ/SORUNLU TABLOLARI

Manuel-edit filmi (GÜLE GÜLE JÜPİTER) ayrı tutularak N=103 üzerinden:

### CAST (N=103)
| Hüküm | Sayı |
|---|---|
| TEMİZ | 79 |
| SORUNLU (süzgeç-sonrası gerçek) | 22 |
| BOŞ (cast alanı yok/uygulanamaz — belgesel vb.) | 2 |

**Sorun-tipi frekansı (cast, süzgeç-sonrası):**
| Tip | Sayı |
|---|---|
| CREW-SIZINTISI | 22 |
| KARAKTER-ADI | 11 |
| DİĞER (eksik-cast/çifteleme) | 5 |
| FABRIKASYON | 5 (2'si GÜLE GÜLE JÜPİTER'de manuel-edit kovasına gitti, kalan diğer filmlerden) |
| GARBLE (OCR-yanlış-okuma → yanlış kişi) | 3 |
| YANLIŞ-ROL | 2 |
| ŞİRKET-ADI (sponsor/otel) | 1 |

*Not: bir filmde birden çok isim aynı tipte sorun taşıyabildiği için "sorun sayısı" ≠ "sorunlu-film sayısı"; tablo yukarıda bulgu-sayısı, film-sayısı 22.*

### YAPIMCI (N=103)
| Hüküm | Sayı |
|---|---|
| TEMİZ (Exec-Producer'ı doğru sayan 6 vaka dahil) | 49 |
| SORUNLU (süzgeç-sonrası gerçek) | 22 |
| BOŞ (yapımcı alanı yok/tespit edilmedi) | 32 |

**KESİN-KURAL ile AYIKLANAN (yapımcı, "sorun değil" hale getirilen):** 6 vaka — hepsi düz "Executive Producer/Yönetici Yapımcı" etiketiyle ekranda geçiyor, ajan yanlışlıkla YANLIŞ-ROL etiketlemiş:
- NEHİRDE YARIŞ: SAMUEL Z. ARKOFF, LOUIS S. ARKOFF
- TOPLU GÖSTERİLER (KONVOY): MICHAEL DEELEY, BARRY SPIKINGS
- YEDİ CÜCELER 1: ANDREAS SCHMID, GEREON SOMMERHAUSER

**Sorun-tipi frekansı (yapımcı, süzgeç-sonrası gerçek 22 film için):**
| Tip | Sayı |
|---|---|
| YANLIŞ-ROL (gerçek — associate/line/co-producer/senarist/teşekkür/vs.) | 14 |
| CREW-SIZINTISI | 3 |
| ASSOC-PRODUCER-SIZINTISI (co-producer sızıntısı) | 2 |
| ŞİRKET-ADI (sponsor/lab/prodüksiyon-banner) | 2 |
| GARBLE (harf-hatası: AGRAMA→ACRAMA) | 2 |
| FABRİKASYON | 2 |
| DİĞER (eksik-gerçek-yapımcı/çift-kayıt) | 3 |

Not: KESİN-KURAL sonrası bile bazı filmler (NEHİRDE YARIŞ, TOPLU GÖSTERİLER-KONVOY, YEDİ CÜCELER 1) "SORUNLU" kalıyor çünkü **başka** gerçek hatalar da taşıyorlar (co-producer sızıntısı FRED BAUM, production-manager sızıntısı, maske-ekibi sızıntısı ANN-KATHRIN GUBALLA) — sadece exec-producer bulgusu tek başına o filmleri temize çıkarmazdı zaten, ama bulgu-sayısını düşürüyor.

---

## B. KÖK-NEDEN GRUPLARI → FIX ÖNCELİĞİ (en çok filmi kurtaran önce)

### Öncelik 1 — CREW-SIZINTISI (cast: 22 bulgu / ~9 film, yapımcı: 3 bulgu / 3 film) → **En yüksek öncelik**
**Kod-katmanı:** `filter_cast_by_raw_context` / rol-lexicon (muhtemel dosya: `scripts/credit_role_lexicon.py` veya `_pipe_credit_text.py` içindeki lexicon tablosu).

**(i) Toplanan ekran-etiketleri listesi** (rol-lexicon'a eklenmesi gereken, şu an filtre-dışı kalan crew etiketleri):
- KAMERA Yrd. / Kamera Yardımcısı (Camera Assistant)
- Kamera (düz — Director of Photography/kameraman anlamında, "Oyuncular" değil)
- Seslendirme Yönetmeni / Dublaj Yönetmeni
- İSPOLNİTELİ PESEN (Rusça: şarkı seslendiren / song performer)
- associate producer (İngilizce çeşitli OCR-garble varyantları: "asscriate", "aseecime p", "associote p")
- art director / "ar di" / "ort di" garble-varyantları
- director of photography / "director of pho" kesik varyantı
- camera operator / "ramera"
- sound recordist / "soun[d]"
- "Miss X's dresser/costume" (kişisel giyim ekibi)
- Collaborateurs au scénario (Fransızca: senaryo ortak-yazarları)
- Truccatore (İtalyanca: makyajcı)
- Producer/Co-Producer/Supervising Producer alt-varyantları (bunlar YAPIMCI alanına sızdığında ayrı problem — Mekke'ye Yolculuk 4 vaka)
- **DIRECTEUR DE PRODUCTION** (Fransızca: yapım yönetmeni/production manager) — ajanın kendi notu **açıkça** "credit_role_lexicon.py'de tam 'DIRECTEUR DE PRODUCTION' varyantı negatif-rol listesinde yok (yalnız 'DIRECTEUR DE LA PHOTOGRAPHIE' ve 'PRODUCTION MANAGER' var), bu yüzden filtre kaçırmış olabilir" diyor — **somut, isimlendirilmiş bir kod-gap**.
- Maske (Almanca: makyaj ekibi)

**Değerlendirme:** Bu grup tek bir lexicon-genişletme fix'i ile 9+ filmi (BİR BEBEK EVİ tek başına 7 isim, LENI RIEFENSTAHL 2, AYNADAKİ DÜŞMAN 1, MEKKE'YE YOLCULUK 4, MISSOURI GÜZELİ 2, vb.) düzeltebilir — **en yüksek getiri/efor oranı**.

### Öncelik 2 — KARAKTER-ADI (cast: 11 bulgu / 6 film)
**(ii) Mekanizma:** Kanıtlar **iki alt-mekanizma** gösteriyor:
1. **Çift-kolon karışıklığı (baskın, 9/11 vaka):** Ekranda SOL=oyuncu / SAĞ=karakter (veya İngilizce filmlerde SOL=oyuncu/SAĞ=karakter, Rusça/Fransızca'da bazen ters: SOL=karakter/SAĞ=oyuncu — VANYA DAYI ve KIZIL HAYAT'ta karakter üstte/solda). Pipeline kolon-eşleştirmesini karıştırıp SAĞ/karakter sütunundaki ismi cast alanına yazıyor, gerçek oyuncu adı hiç PDF'e girmiyor. Örnek: SINIR ÇİZGİSİ'nde 5 karakter-adı (JEB MAYNARD, JIMMY FANTE, CARL RICHARDS, ELENA MORALES, SCOOTER JACKSON) hepsi bu desende.
2. **Tek karakter-adı / repo tabelası (2/11 vaka):** BJ VE AYI'da "Billie Joe McKay" aslında sahne-içi kamyon tabelası (jenerik kredi kartı değil) — OCR bunu jenerik sanıp cast'e yazmış.

**Kod-katmanı önerisi:** İki-kolon credit parse mantığı (muhtemelen `_pipe_credit_text.py` içinde satır-hizalama/bbox-x-kordinat ayrımı) — kolon rolünü (karakter mi oyuncu mu) etiket-bağlamından (örn. "Players:"/"в ролях"/"avec" başlık satırından sonra gelen ilk sütun genelde karakter) değil, sabit sol/sağ varsayımından çıkarıyor olabilir. Film-diline göre kolon-sırası DEĞİŞKEN — dil-duyarlı kolon tespiti gerekiyor.

### Öncelik 3 — s5_form_overwrite_confirmed ama PDF'e yansımamış (Paul Walker III tipi)
**(iii) Sayı: 1 vaka** (bu 104-film setinde) — HIZLI VE ÖFKELİ filminde PAUL WALKER III. `_DURUM.json.otorite_audit.s5_form_overwrites` alanı sistemin kendi kendine "ocr='Paul Walker III', kb='Paul Walker', ocr_in_raw=true" tespitini yaptığını ve `s5_form_overwrite_confirmed=true` bayrağını kaldırdığını gösteriyor — yani **sistem hatayı zaten biliyor ama düzeltme PDF render adımına aktarılmıyor**.

**Kod-katmanı önerisi:** Bu S5 form-overwrite-confirmed bayrağının PDF/final-render adımına (muhtemelen `tek_film_kunye.py` veya PDF compose script'i) bağlı olmadığı anlaşılıyor — bayrak set ediliyor ama tüketen kod yok ya da güvenmiyor. **Düşük hacim (bu örneklemde 1) ama yüksek sinyal**: sistemin zaten doğru tespit ettiği bir düzeltmeyi PDF'e UYGULAYAN bir köprü eksik. Bu aynı zamana FABRİKASYON grubundaki bazı "candidate_read LLM tarafından üretildi ama ekran-kanıtı yok" vakalarıyla (ROBERT PRESTON/Rupert Preston, Sakyo Komatsu) benzer bir "iç-denetim var ama nihai render'a aktarılmıyor" örüntüsünün parçası — genelleştirilebilir bir fix: **her `otorite_audit` bayrağının (s5_form_overwrite, kb_floor_added, vb.) PDF-render'dan ÖNCE zorunlu bir gate'den geçmesi**.

### Öncelik 4 — FABRIKASYON (cast: 5, yapımcı: 2 — manuel-edit hariç)
Kök-neden: LLM (credit_text candidate_read adımı) tek/bulanık bir OCR parçasından tam isim uyduruyor (HAMZA ARORE, TOPLU GÖSTERİLER'de SIYING XUE hiç jenerik-kare yokken üretilmiş; ROBERT PRESTON = "Rupert Preston" LLM'in ikinci varyant üretmesi; SHAOLIN'de iki Çince-garble satırdan iki ayrı uydurma İngilizce isim). **Kod-katmanı:** `credit_text.candidate_read` — muhtemelen 8-cap doldurma baskısı (bkz. MEMORY: "8-cap fix" geçmişi) LLM'i eksik-kalan slotları uydurmaya itiyor olabilir; `otorite_audit.kb_floor_added`/`raw_cap_dropped` mantığının FABRİKASYON'u da yakalayacak şekilde genişletilmesi (OCR-kaynak-satırı gösterilemeyen her isim otomatik reddedilmeli — MEMORY'deki "3 sistemik fix" ile aynı aile).

### Öncelik 5 — Executive/Associate/Co-Producer rol-ayrımı ince-ayarı (yapımcı: 14+2 gerçek YANLIŞ-ROL)
Bu grup KESİN-KURAL sonrası bile **gerçek** kalıyor çünkü associate/line/co-producer/production-manager gerçekten "Yapımcı" değil. Kod-katmanı: aynı rol-lexicon dosyası (Öncelik 1 ile aynı katman) — "PRODUCED BY" pozitif-eşleşme regex'i muhtemelen "PRODUCER" substring'ini çok gevşek yakalıyor (örn. "Executive Producer", "Line Producer", "Co-Producer", "Directeur de Production", "Producteur Associé" hepsi "produc*" içeriyor). **Fix: pozitif-eşleşmeyi sadece TAM "PRODUCED BY"/"PRODUCER(S)" (herhangi bir önek olmadan) ile sınırlayan negatif-önek listesi** (Executive/Line/Co/Associate/Supervising/Directeur de/In Charge of/Program).

---

## C. MANUEL-EDIT VAKALARI (insan-politikası konusu, pipeline hatası DEĞİL)

**1 film, tam kapsamlı:**

**GÜLE GÜLE JÜPİTER 1991-0544-1-0000-00-1**
- `_DURUM.json` notu: sistem filmi kendiliğinden `KONTROL/YONETMEN_KIMLIK_RENDER` olarak işaretlemiş.
- 30.06.2026 tarihli **manual_pdf_fix**: bir operatör yönetmen+yapımcı alanlarını ekran-dışı kaynaktan (muhtemelen web/IMDb) elle doldurup PDF'i "Hazır"a çevirmiş.
- Cast'teki 8 isim (Tomokazu Miura, Diane d'Angely, Miyuki Ono, Rachel Huggett, Paul Tagawa, Akihiko Hirata, Masumi Okada, Hisaya Morishige) ekran-korpusunda (OneOCR+GLM+VL, 3 motor) **hiç** geçmiyor — muhtemelen aynı operatör-eli ile web'den girilmiş.
- Yapımcı alanındaki "Sakyo Komatsu" da aynı şekilde: roman yazarı, ekranda hiç Latin/katakana okunmuyor, ama aynı zamanda kunye_teslim.md içinde çelişkili biçimde "Yönetmen" olarak da listelenmiş (çift-rol hatası — bu da operatör-elinin tutarsızlığına işaret).
- **OCR-otorite kuralına aykırı** (ekrandaki jenerik tek otorite ilkesi) ama isimlerin kendisi muhtemelen doğru (gerçek film bilgisiyle örtüşüyor).
- **Kategori:** MANUEL-EDİT, ekran-teyitsiz — pipeline bug değil, operatör kararı; Çağatay'ın ayrı ele alması gereken politika sorusu (web-kaynaklı doldurmaya izin var mı / hangi durumda).

---

## D. EN KRİTİK 10 VAKA (film + isim + tip + tek-satır kanıt)

1. **BİR BEBEK EVİ (1973)** — 7 isim topluca (Reginald Beck, Richard Dalton, Eileen Diss, Gerry Fisher, Bernard Ford, Peter Handford, Edith Hoad) — CREW-SIZINTISI — tek bir filmde 7 crew-üyesi cast'e sızmış, rol-lexicon'daki en yoğun tekil kanıt: "associate p[roducer]/art di[rector]/director of pho[tography]/camera/sound/Miss Fonda's dresser" etiketleri OCR'da net ama filtre yakalamıyor.
2. **MEKKE'YE YOLCULUK (2017)** — 4 isim (Dominic Cunningham-Reid, Al Zain Al Sabah, Dima Alansari, Diane Roberts+Tony Thatcher) — CAST'e sızan Producer/Co-Producer/Supervising Producer — "Produced By" ve "Co-Producers" kartları net ekran-kanıtlı (frames/cikis/c_0513, c_0528, c_0536).
3. **HIZLI VE ÖFKELİ (2009)** — PAUL WALKER III — YANLIŞ-ROL — `s5_form_overwrite_confirmed=true` ama PDF'e hiç uygulanmamış: "otorite_audit.s5_form_overwrites=[{'ocr':'Paul Walker III','kb':'Paul Walker','ocr_in_raw':true}]" — sistem kendi hatasını biliyor, düzeltme köprüsü eksik.
4. **SINIR ÇİZGİSİ (1995)** — 5 karakter-adı (Jeb Maynard/Jimmy Fante/Carl Richards/Elena Morales/Scooter Jackson) + 1 çift-karakter-birleşme (Malcolm Wallace Hotchkiss = 2 ayrı kişi tek isimde kaynaşmış) — KARAKTER-ADI+FABRİKASYON — gerçek oyuncular (Bronson, Kirby, Remsen, Wilford Brimley, McMillan, Ed Harris) PDF'te hiç yok, tek filmde en yoğun oyuncu-kaybı.
5. **GÜLE GÜLE JÜPİTER (1991)** — 8 cast ismi + Sakyo Komatsu — MANUEL-EDİT (ayrı kategori) — operatör 30.06.2026 tarihinde ekran-dışı web-kaynaktan doldurmuş, üç OCR motorunda (OneOCR/GLM/VL) hiçbiri yok.
6. **21. YÜZYIL EŞİĞİNDE TÜRK AİLESİ** — 3 isim (Ümit Kül, Nazım Edeer, Özcan Sürmeli) — CREW-SIZINTISI — belgesel filmde hiç "Oyuncular" bloğu yok, üçü de "KAMERA Yrd." etiketi altında 7+ tekrarda net.
7. **AJAMİ (2009)** — ROBERT PRESTON (yapımcı FABRİKASYON) — "debug_trace/trace_summary.md" LLM'in tek bir OCR-kaynaklı ismi (Rupert Preston) hem doğru hem uydurma-varyant (Robert Preston) olarak iki kez ürettiğini gösteriyor — LLM candidate-read'in kendi kendini çoğaltma hatası.
8. **SHAOLIN (2011)** — BAO JIAN FENG + XIN SHI FENG — cast FABRİKASYON — Çince garble OCR satırından ("Xiong Xinxny0. Hai" gibi) iki tam uydurma İngilizce isim üretilmiş, hiçbir OCR dosyasında iz yok.
9. **TOPLU GÖSTERİLER (1991)** — HAMZA ARORE — FABRİKASYON, en çıplak vaka — tek kelime "Arore" (ev-güvenlik-sistemi ekran-metni parçası, jenerik bile değil) LLM tarafından tam ad+soyada dönüştürülmüş; `giris_jenerik_manifest.json: total_kept=0/270` yani jenerik kare bile tespit edilmemiş bir filmde isim uydurulmuş.
10. **VANYA DAYI (1989)** + **KIZIL HAYAT (1996)** — Serebryakov Aleksandr Vladimirovich / Vadim Alexander Balouev — KARAKTER-ADI (çift-kolon ters-yön) — bu ikisi diğer örneklerin aksine karakter SOL/ÜSTTE, oyuncu SAĞ/ALTTA dizilmiş (Rusça geleneği) — kolon-sırası dile göre değiştiğini kanıtlıyor, tek-yönlü sabit varsayım kod-hatasının kanıtı.

---

**Özet — fix sırası tavsiyesi:** (1) rol-lexicon genişletmesi [crew-etiketleri listesi madde B-(i)] → en çok filmi (~12+) tek hamlede kurtarır; (2) "produced by" pozitif-regex'i tam-eşleşmeye daraltma (Executive/Line/Co/Associate/Directeur-de negatif-önek) → yapımcı YANLIŞ-ROL'ün büyük kısmını (14 vaka) çözer; (3) dil-duyarlı iki-kolon karakter/oyuncu ayrımı → KARAKTER-ADI'nın 9/11'ini çözer; (4) `otorite_audit` bayraklarının (s5_form_overwrite, kb_floor_added) PDF-render'a bağlanma zorunluluğu → hem Paul Walker III hem bazı FABRİKASYON vakalarını kapsar; (5) GÜLE GÜLE JÜPİTER manuel-edit vakası ayrı politika kararı olarak Çağatay'a bırakılmalı (pipeline fix konusu değil).
---
## DÜZELTME (2026-07-04) — Öncelik-3 "s5_form_overwrite→PDF köprüsü" YANLIŞ ALARM

Fable derin-iz takibi (mikro-repro + PDF-binary metin çıkarımı):
- `qc_credit_block` mikro-repro: `temiz_cast = ['PAUL WALKER', ...]` — S5 düzeltmesi blokta ÇALIŞIYOR.
- Gerçek PDF'ler (`pdf/kunye.pdf` + kök teslim PDF'i) **'PAUL WALKER'** içeriyor — III YOK, köprü SAĞLAM.
- Yüzey .txt de doğru ('PAUL WALKER').
- III yalnız `pdf/kunye_teslim.md`'de kalmıştı (_pipe_pdf'in HAM md'si; V4-patch o koşuda md'ye geri
  yazılmıyordu). Denetçi-ajan md'yi PDF-vekili olarak okuyunca "PDF'e yansımamış" sanmış =
  BAYAT-ARTEFAKT TUZAĞI (bkz. feedback_bayat_artefakt_tuzagi).
- KAPANIŞ: md-senkron fix (mitas_pipeline.py:278, bu oturum commit'li) patch'li md'yi diske geri
  yazıyor → gelecek koşularda md≡PDF. Ek köprü işi GEREKMİYOR.
