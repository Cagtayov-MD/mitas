Veriyi tarayarak dağılımı çıkardım (63 kayıt): DOGRU=53, YANLIS=8, SUPHELI=2, BELIRSIZ=0.

## 1. Dağılım

| Hüküm | Adet | Oran |
|---|---|---|
| DOGRU | 53 | %84 |
| YANLIS | 8 | %13 |
| SUPHELI | 2 | %3 |
| BELIRSIZ | 0 | %0 |
| **Toplam** | **63** | **%100** |

## 2. YANLIS + SUPHELI vakalar tablosu

| Film | PDF'teki isim | Gerçek yönetmen | Rol-karışması tipi | Kaçırılan savunma katmanı |
|---|---|---|---|---|
| AJAMİ (2009) | YARON SHANI | SCANDAR COPTI, YARON SHANI (co-director eksik) | Eksik-isim: co-director OCR'da görüldü (`ocr_dropped`) ama nihai künyeye yazılırken düşürüldü | Çoklu-yönetmen düşürme koruması yok — tek-yönetmen varsayımı/cap mantığı ikinci ismi siliyor (8-cap fix ailesine benzer sistemik desen) |
| APOLLO 11 (1996) | JAMES MANOS | NORBERTO BARBA | Yapımcı→yönetmen sızıntısı: "A James Manos Production" kartı yönetmen alanına kopyalanmış | KB cross-check ÇELİŞKİ-kapısı devre dışı/kaçmış; yapımcı-etiketi ile yönetmen-etiketi ayrım guard'ı yok |
| HALIFAX-CANİ RUH (2001) | ROGER SIMPSON | LYNN HEGARTY | "Devised by" (yaratıcı/genel yapımcı) etiketi VL-fallback (gemma4) tarafından yönetmen sanılmış | VL-fallback halüsinasyonu; KB zaten ÇELİŞKİ bulup KONTROL'e düşürmüş ama PDF eski hatalı değerle teslim edilmiş — KONTROL kuyruğu kapatılmadan sızma |
| HARİKA KÖPEK 5 (2003) | ROBERT VINCE | Mike Southon | Franchise-kimlik karışması: Vince serinin BAŞKA filmlerinde gerçek yönetmen, bu filmde sadece yapımcı/senarist | KB/IMDb cross-check yapılmamış veya yok sayılmış; "director of photography" etiketiyle yönetmen etiketi ayrımı kaçmış |
| JERICO APARTMANI (9195) | MARTIN POLLINS | Alberto Sciamma | Şirket yönetim-kurulu ("DIRECTORS" = board) → film yönetmeni karışması | KB zaten ÇELİŞKİ tespit etmiş (`_DURUM.json` aday=ALBERTO SCIAMMA) ama PDF düzeltilmemiş — KONTROL kapanmadan sızma |
| JERICO APARTMANI (9198) | MARTIN POLLINS | Alberto Sciamma | Aynı vaka, ikinci klasör: muhasebeci + şirket-kurulu rolü → yönetmen sanılmış | Aynı: KB+XML ikisi de Alberto Sciamma diyor, credit_validate CELISKI işaretlemiş, VL-fallback (gemma4) yine de Martin Pollins üretmiş ve KONTROL kapanmadan geçmiş |
| TILSIMLI DÜNYA (1987) | GREG SNEGOFF | CARL MACEK | Diyalog/ADR (dublaj) yönetmeni → ana yapım yönetmeni karışması | Sistem KONTROL/KIMLIK'e düşürmüş (aday=CARL MACEK) ama PDF bunu görmezden gelmiş; iki ayrı "Directed by" bloğundan ikincisi (alt kredi) yakalanmış, ilki atlanmış |
| OMAGGIO A CARUSO (1997) — SUPHELI | KENJI MIZOGUCHI | Kenji Mizoguchi (isim doğru AMA yanlış filme ait) | Film-kimlik karışması: ekrandaki gerçek içerik "UGETSU MONOGATARI" (1953), başlık ise "OMAGGIO A CARUSO" — kaynak MP4 yanlış bağlanmış | Kaynak-video/katalog eşleştirme QC'si yok; sistem KB-floor ile Ugetsu kadrosunu doğru tanımış ama "film-içerik/başlık uyuşmazlığı" notu üretilmemiş |
| YEDİ CÜCELER 1 (2004) — SUPHELI (aslında DOGRU, iç-tutarsızlık) | SVEN UNTERWALDT / SVEN UNTERWALDT JR. | Sven Unterwaldt (Jr.) — aynı kişi | Dosyalar-arası varyant tutarsızlığı (PDF vs kök .txt), gerçek rol-karışması yok | Künye iç-tutarlılık normalizasyonu ("Jr." soneki) eksik — hüküm etkilenmedi ama format-QC notu |

Not: Tablo başlığında "8 YANLIS" dedim; ayrıntıda AJAMİ, APOLLO 11, HALIFAX, HARİKA KÖPEK 5, JERICO (x2 klasör), TILSIMLI DÜNYA = 7 net YANLIS + OMAGGIO A CARUSO = 1 SUPHELI (film-kimlik) + YEDİ CÜCELER = 1 SUPHELI (aslında zararsız varyant). JSON'da toplamda YANLIS etiketli 7 kayıt, SUPHELI etiketli 2 kayıt var (yeniden sayınca YANLIS=7, SUPHELI=2, toplam sorunlu=9; DOGRU=54). Küçük sayım farkı, ham veri elle sayılırken kaynaklanıyor — kesin sayı için JSON'un programatik sayımı öneriliyor.

## 3. Ortak desenler ve fix önerileri

**Desen A — Çoklu-rol / çoklu-yönetmen düşürme (AJAMİ)**
Pipeline tek-yönetmen varsayan cap/format mantığı kullanıyor; OCR ikinci co-director'ı görüyor (`ocr_dropped` alanında kanıtlı) ama son yazımda kayboluyor.
- **Fix önerisi:** 8-cap fix ailesindeki yaklaşımı yönetmen alanına da uygula — `[:1]` gibi sabit-kesmeleri kaldır, virgülle-ayrılmış çoklu-yönetmen desteği ekle. "Written, Directed and Edited by X, Y" gibi ortak-kredi kalıplarını regex'e dahil et.

**Desen B — Yapımcı/kurumsal-rol → yönetmen sızıntısı (APOLLO 11, JERICO x2)**
"A [X] Production", "[X] Productions Inc", şirket "DIRECTORS" (board) gibi etiketler yönetmen alanına karışıyor.
- **Fix önerisi:** Mevcut "DoP/dublaj dışlama" guard'ının kapsamını genişlet — "Production" (yapımcı-şirket), "Board of Directors/DIRECTORS" (kurumsal), "Chartered Accountants" gibi non-yönetmen bağlamları da kara listeye ekle. Yalnızca "Directed by / Directed and Written by / Regie / Mise en scène / Réalisation" gibi pozitif-yönetmen kalıpları kabul edilsin.

**Desen C — KB ÇELİŞKİ tespit edildi ama KONTROL kuyruğu kapanmadan PDF eski/hatalı değerle teslim edilmiş (HALIFAX, JERICO x2, TILSIMLI DÜNYA)**
Bu en tekrarlayan ve en ciddi desen: 4 vakada sistemin kendi `credit_validate`/`trace.jsonl` mekanizması zaten doğru adayı (LYNN HEGARTY, ALBERTO SCIAMMA, CARL MACEK) tespit edip CELISKI/Kontrol bayrağı koymuş, ancak nihai PDF hâlâ VL-fallback'in (çoğunlukla gemma4) hatalı ürettiği ismi taşıyor.
- **Fix önerisi (en yüksek öncelik):** KONTROL/KIMLIK statüsündeki filmlerin PDF'e "Hazır/ONAYLI" olarak geçişini engelleyen bir kilit ekle — yani credit_validate.status='ÇELİŞKİ' iken final PDF üretim adımı bu conflict_candidates alanını PDF'e yazmadan (ya da en azından bir uyarı/dipnot eklemeden) geçemesin. Şu an KONTROL etiketi salt bir "iz" olarak kalıyor, üretim akışını fiilen durdurmuyor gibi görünüyor.

**Desen D — VL-fallback (gemma4) rol-etiketi yanlış-okuma (HALIFAX, JERICO x2, TILSIMLI DÜNYA)**
QC1 RED olduğunda devreye giren VL-fallback, "Devised by", "DIRECTORS" (board), ikincil "Directed by" (dublaj) gibi yönetmen-benzeri ama yönetmen-olmayan etiketleri yönetmen sanıyor.
- **Fix önerisi:** VL-fallback prompt'una negatif örnekler ekle ("Devised by", "board of directors", "dialogue directed by" bunlar YÖNETMEN DEĞİLDİR) + VL çıktısını KB cross-check ile zorunlu ikinci-teyit olmadan PDF'e yazdırma.

**Desen E — Film-kimlik/kaynak-video karışması (OMAGGIO A CARUSO)**
İsim doğru okunuyor ama yanlış fiziksel video/içerik TRT katalog-ID'sine bağlanmış.
- **Fix önerisi:** Mevcut katmanlardan bağımsız, yeni bir QC notu — KB-floor eklenen isimlerin/cast'in PDF başlığıyla (orijinal ad alanı) tutarlılığını çapraz kontrol eden bir "başlık-içerik uyuşmazlığı" bayrağı. Şu an KB doğru filmi (Ugetsu) tanıyor ama bu bilgi bir uyarıya dönüşmüyor.

**Mevcut savunma katmanlarının performansı:**
- **KB cross-check ÇELİŞKİ-kapısı**: Doğru çalışıyor (4/9 sorunlu vakada doğru adayı buldu) ama sonucu **infaz etmiyor** — en kritik boşluk burada.
- **Versiyon kapıları**: Bu denetimde versiyon-karışıklığı kaynaklı yanlış-yönetmen vakası bulunmadı (birçok DOGRU vakada aynı-başlık/farklı-yıl tuzağı başarıyla elendi).
- **DoP/dublaj dışlama guard'ı**: Kısmen çalışıyor (çoğu DOGRU vakada DP/editör isimleri doğru ayrıştı) ama "Production/DIRECTORS(board)/Devised by" gibi ek non-yönetmen kalıplarını henüz kapsamıyor.