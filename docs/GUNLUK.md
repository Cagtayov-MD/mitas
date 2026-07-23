# MITAS Proje Günlüğü

> Amaç: oturumlar arası süreklilik. Her Claude Code oturumu AÇILIŞTA son 2-3
> kaydı okur, KAPANIŞTA (veya önemli bir iş bitince) yeni kayıt ekler.
> Format: tarih + yapılan + öğrenilen/başarısız denemeler + bekleyen.
> En yeni kayıt EN ÜSTTE.

---

## 2026-07-23 (akşam) — Ex_Frame exit-frame jenerik kesimi: 487 film, 30 Sonnet ajanı (master PNG verisi)

**İş:** `/home/cagatay/Ex_Frame/*-exit_frames/` — 487 film × ~600 kare (son 8dk, exit_%06d.png,
~1.25fps, 288k kare/54GB). Her film için kapanış-jeneriği başlangıç karesini bulup öncesindeki
FİLM SAHNESİ karelerini kalıcı sildik (master PNG yalnız jenerikten kurulmalı). Çağatay kararları:
tümü (önce pilot) + doğrudan rm + kesim=kapanış-bloğu ilk karesi (SON/THE END/ithaf/logo dahil).

**Neden vizyon:** MITAS `credit_onset.py` v4/v5 PaddleOCR gerektiriyor, py3.14'te kurulu değil
→ deterministik dedektör kullanılamadı. Jenerik sık footage ÜSTÜNE akıyor (siyah-kare heuristiği
patlar). Çözüm: **montaj-tabanlı Sonnet vizyon**. Araçlar: `harness/kunye_kiyas/exit_kesim/montaj.py`
(etiketli kontakt-sayfa: kaba→ince) + `kes.py` (gardlı silici: guven<0.60 / onset<=ilk / bayrak /
<8 kare kalır → SİLMEZ, flag'ler; her kesimde audit-şerit + manifest.jsonl).

**Sonuç (doğrulandı):** 10-film pilot %100 doğru (footage-üstü künye dahil) → onay → 30 paralel
Sonnet ajanı, 16'lık batch. **427 film KESİLDİ (193.122 kare silindi), integrity 427/427 tam**
(kalan kare=manifest, ilk-kalan==onset). Kesilmedi (güvenli, tümü duruyor): 43 jenerik_yok/tut_hepsi
(kredi 8dk penceresi dışında ya da ön-jenerikli eski film), 14 cok_az_jenerik (SON sadece son ~5
karede, <8 gard), 1 anomali (tapilacak-yalanlar = iki film birleşmiş → GUNLUK veri-hijyeni deseni),
2 atlandı (oyuncu, iyi-geceler-iyi-sanslar = kaynak tamamen siyah/bozuk). Sadece 1 düşük-güven
kesim (kaptan-january 0.65). Elle-ikinci-tur listesi: `outputs/exit_kesim/elle_inceleme.txt`.

**Öğrenilen:** (1) Montaj kontakt-sayfa + ajan = 600 kareyi tek tek okumadan ~2-3 görselde frame-doğru
onset. (2) Gard tasarımı (min-kare + bayrak) yanlış-kesimi sıfırladı; flag=güvenli. (3) 43 jenerik_yok
üretim sinyali: bu filmlerin kapanış künyesi 8dk exit-penceresinde YOK — daha geniş pencere ya da
giriş-jeneriği gerekebilir. **Kapanış (Çağatay kararı):** kesilemeyen 60 film "havuz zaten yeterli"
denerek KOMPLE SİLİNDİ (35.506 kare; log: `outputs/exit_kesim/silinen_60_klasor.log`). Ex_Frame'de
artık yalnız **427 kesilmiş film** var — hepsi master-PNG başlangıcına hizalı. Bekleyen yok.

---

## 2026-07-23 (akşamüstü) — %92 kampanyası: T4 doğrulandı+commit'lendi (88/110), T6 koşuyor

**Rewind olayı:** Çağatay yanlışlıkla rewind yaptı — HİÇBİR İŞ KAYBOLMADI (tüm commit'ler +
T4'ün diskteki kodu sağlam; tam yedek: ~/mitas_yedek_rewind_152202/). Master PNG çalışması
ayrı FORK oturumuna alındı; bu oturum jenerik-başlangıç hattı.

**T4 (hareket-otoriteli onset) doğrulandı ve commit'lendi (4e0818b):** 84→**88/110 (%80.0)**,
kredisiz 28/29 korundu. Kazanılan: MESLEĞE_DÖNÜŞ(+320), DİPTEKİLER(+203), KARAVAN(+182), "6"(+155).
Tasarım plandan bilinçli saptı: geri-birleştirme scroll-tip şartı OLMADAN her kazanan koşuda
denenir (dört hedefin scroll_oran'ı 0.07-0.24 çıktı — ölçüm planı çürüttü); güvenlik kısa-boşluk
(~45 örnek-kare) + rol-keyword içerik kapısından. Kalıntı risk: kapı geniş _ROL kullanıyor
('produc' logo-riski) — T6'da _ROL_CEKIRDEK'e geçirilecek.

**Veri-hijyeni bulgusu (ÜRETİM İÇİN ÖNEMLİ):** Film Kapanış'ta aynı TRT-id FARKLI film içeriği
taşıyabiliyor (görsel teyit: DİLEK_AĞACI dosyasında Coppola kapanışı, INNISFREE'de TV dizisi).
Asıl kopyalar '30062026SAYFA' batch önekinde. 5 film oradan kurtarıldı (5/5 arşiv-uyum),
3 film dışlandı (veri/dislanan.json). Kare-sayısı paritesi İÇERİK paritesi DEĞİL.

**Perf:** det-önbelleği (_det_cache.json) + olc_pool --paralel 8 → tam 110-film ölçümü ~2 dk
(eskiden ~30 dk). Isıtıcı: veri/det_isit.py.

**T6 (6 alt-adım):** 88→92/110. Kazanılan: SEN_TOM(Almanca sözlük), ÖLDÜRME(İtalyanca
nokta-lider+küçük-harf), TAKTİKLER(seyrek-yol ≥2-çekirdek-rol), ARKADAŞIMIN(scroll-kurtarma).
Kalan engel sınıfları teşhisli: Kiril/Farsça OCR, tek-isim kart dizisi, şirket-kalıbı FP.

**Politika kararı (Çağatay, 13ba2fc):** Restorasyon/TRT-ekleme kartları KÜNYE SAYILMAZ —
orijinal jenerik esas. TAKKELİ GT 588→905 düzeltildi (Kazakça restorasyon kartıydı).

**2. tur (konsey-GLM kırmızı-takım sonrası, 5 alt-adım):** 92→**99/110 (%90.0)**, kredisiz
**29/29** (tek FP DÖNÜŞÜ de düştü — şirket-kalıbı gardı: corporation/pictures/released-by
satırları isim sayılmaz). Kazanılan: VANYA+MELEKLERİ (ikinci-şans KİRİL rec — en-rec çöpü
sezilince lang='ru' yeniden okuma; homoglif çözümü), DOĞUM(Macarca sözlük), ROBOCOP+PARDAYYAN
(kazanan-koşuya bitişik kart-dizisi geri-genişletme — tek_genis'in elediği tek-isim kartları).
GERİ ALINAN: kf-tabanlı scroll-erken gardı (tüm-kare farkı gerçek-scroll'u sahne-bandından
ayıramıyor; 11 film bozdu → revert; DOĞRU yol kutu-MASKELİ zemin farkı). BUG BULUNDU:
_ROL'deki 'produc' \b(...)\b yüzünden HİÇ eşleşmiyormuş (producer/production yakalanmıyor).

**Mini-tur 3:** produc-regex bug'ı düzeltildi (\b(...)\b önek-alternatifleri hiç eşleşmiyordu)
→ KÜÇÜK_SİMBA (+1). Kutu-maskeli zemin-hareketi KALİBRE EDİLEMEDİ (karşı-örnek KAHRAMAN_
UZAYLILAR: gerçek jenerik animasyonlu zemin ÜSTÜNDE başlıyor — salt piksel-hareketi "sahne mi
kredi mi"yi çözemez, geri alındı). CJK hipotezi çürütüldü (İNİŞLİ'deki metin OCR gürültüsü).

**ASİMETRİ POLİTİKASI (Çağatay):** erken KABUL (fazla kare zararsız), geç KABUL EDİLEMEZ
(cast atlanır). olc_pool'a ÜRETİM skoru eklendi (erken≤120/geç≤20, 0eb5f58). Görsel hata
raporu: outputs/jenerik_hata_raporu/rapor.html.

**FİNAL TUR + T8 → KAMPANYA KAPANDI ✅: 103/110 = %93.6 simetrik, ÜRETİM %96.4 (106/110),
kredisiz 29/29.** Kazanımlar: PRENSESİN (producer+isim köprü kapısı), KANDAHAR (Arapça/Farsça
ikinci-şans: kredi_yok→+5), YÜREKTEN (şirket-budaması). Kritik gard: yabancı-alfabe yoluyla
kazanılan koşuda Latin ileri-budama ÇALIŞMAZ (yabanci_yol bayrağı — KANDAHAR/ARKADAŞIMIN
regresyonunun kök-sebep düzeltmesi). T8: GLM kod-avı gardları indi ('y-sesli' ölçülen
regresyonla geri alındı — dürüst ret). ×2 ölçüm deterministik + bağımsız doğrulama birebir.
Kalan 7: 5 kabul-edilebilir-erken (TV-bandı/epilog/tabela sınıfı) + 2 geç (GELECEK +91
yapısal boşluk, İNİŞLİ +89). Kalıcı çözüm adayı: dar-VLM (ayrı karar).

**ÜRETİM AKTİVASYONU (Çağatay: "artık aktif stratejimiz bu", d757ecc):** tespit_v5,
_jenerik_pool.py'de bayraklı birincil yol olarak ÜRETİMDE (MITAS_JENERIK_V5=1, mitas.env).
v5 başarılıysa start_pos otoritesi + eski yama yığını atlanır; kredi_yok/hata → eski akış
birebir (fail-safe). Güvenlik payı PAD=10 kare (asimetri politikası). Smoke: 13. SAVAŞÇI
kopyasında v5=319 vs eski-CV=318 (çapraz-doğrulama), bayrak-kapalı davranış birebir.
GitHub'a push edildi (main).

**Bekleyen:** 
açılış-jeneriği tasarımı; Qwen için Alibaba Model Studio aktivasyonu (Çağatay).

## 2026-07-23 (öğleden sonra) — testas özet stratejisi MITAS'a entegre edildi (v2, flag arkasında)

**Talep (Çağatay):** MITAS künye-özeti (System A) "gereksiz uzun/dağınık, salak salak anlatıyor";
testas'ın prompt+stratejisi "tam istenen format". İki sistem birebir incelendi.

**Kök bulgu:** Prompt'lar AKRABA (aynı Jean-Picard altın örneği, aynı yasaklar). Fark prompt
metni DEĞİL, prompt'u saran 3 mekanizma: (1) MITAS prompt aşırı-reçeteli (135 satır, 5-adım
zorunlu YAPI + "Sabit cümle sayısı YOK" → model uzatıyor), (2) kontrol döngüsü yok (ilk
boş-olmayan çıktıyı körlemesine kabul), (3) kalite kapısı/onarım yok. → Rambling'i öldüren 1+3.

**Yapılan (MITAS_OZET_V2=1 flag arkasında; legacy birebir korundu, Prensip 2):**
- `scripts/_ozet_kalite.py` — testas pdf_auditor/pilot10 gate+repair BİREBİR portu (17 golden test).
- `core/api/prompts/ozet_film_v2.txt` — yalın prompt (legacy'nin ~%42'si) + 2-satır ASR önsözü.
- `mitas_pipeline._generate_ozet_v2` — sağlayıcı-içi 3-deneme öz-düzeltme + kapı + onarım (8 test).
- Girdi (ASR transkripti) ve model zinciri (gemini→sonnet→gemma, bake-off kazananı) DEĞİŞMEDİ.
- `.gitignore`: `!scripts/_ozet_kalite.py` — `scripts/_*` yeni modülü yutuyordu (dağıtımda
  kaybolurdu; git-status'ta görünmemesinden yakalandı).

**Konsey (kırmızı takım, GLM):** KABUL → ASR'de twist-kaybı riski gerçek (Sixth Sense senaryosu:
2 saat gürültü frekansı tek-replik twist'i bastırır) → v2 prompt'a "frekansı betimlemeyle doldurma,
dönümü merkeze koy" satırı eklendi. RED → "kelime limitini 45-75'e genişlet"; kullanıcının şikayeti
TAM DA uzunluk + testas'ın 32-65'i zaten kullanıcı-onaylı (konseyi geçtim). Qwen HTTP 401
(geçersiz anahtar — council_mcp/.env'de düzeltilmeli), Kimi 429 (aşırı yük) → tur TEK üyeli.

**A/B eval SONUCU (6 çeşitli film, aynı ASR, eski vs v2):** v2 AÇIK ARA kazandı. Ortalama
uzunluk eski 73 → v2 55 kelime; kapı-geçme eski 3/6 → v2 6/6. Eski 3 filmde 65-kelime sınırını
aştı (71/83/92 kl — "salak salak uzatıyor"un tam kanıtı), v2 hepsini 52-59'a çekti. GLM'in "twist
kaybolur" korkusu ÇÜRÜDÜ: HALIFAX (whodunit) + ÜÇ RENK MAVİ (aldatma reveal) twist'leri v2'de
merkeze geldi — eklenen "dönümü merkeze koy" satırı çalışıyor. AEON FLUX'ta isim farkı (Aeon/Catherine
vs Ion/Una) = ASR belirsizliği, prompt kusuru değil. Yan bulgu: koşuda gemini 429 (kota) → zincir
Sonnet'e düştü, çıktı geldi (dayanıklılık OK ama gemini kotası üretimde de dolabilir).

**Bağımsız inceleme:** codex CLI kurulu DEĞİL → CLAUDE.md'nin eşleştirdiği dış konsey kod-avı
yapıldı (GLM; Qwen 401/Kimi 429 düştü). GLM 4 bulgu: (1) "produced_any ölü kod" YANLIŞ POZİTİF —
konseye sadeleştirilmiş kod verdiğimden (gerçekte satır 1442'de var; ders: brifingde GERÇEK kod ver);
(2) enforce ValueError→çıktı kaybı: MITAS'ta kelime-bazlı + URL yok + placeholder-by-design (testas
felsefesi) → bug değil; (3) birikimsiz feedback→osilasyon: GERÇEK, KABUL → feedback birikimli yapıldı
(testas orijinaliyle de hizalandı); (4) best ilk-gelen-kazanır: kasıtlı tasarım. 25/25 test hâlâ yeşil.

**PROMOTE YAPILDI (Çağatay onayı "aç"):** mitas.env satır 97-98'e `MITAS_OZET_V2=1` +
`MITAS_OZET_DEEPSEEK=1` eklendi. Ayrıca Çağatay talebi "testas hangi API'yi kullanıyorsa MITAS da
onu kullansın (DeepSeek)" → `_ozet_chain`'e MITAS_OZET_DEEPSEEK flag'i eklendi, DeepSeek zincirin
BAŞINA (birincil). Üretim zinciri artık: **deepseek → gemini → sonnet → gemma-local**.

**Uçtan-uca doğrulama (v2+DeepSeek, 2 yeni film):** SON YARIŞ 47 kl / ROBOCOP 50 kl, ikisi de
kapı GEÇTİ, **Türkçe temiz ve doğal** (Çağatay'ın özel isteği), twist korundu (ROBOCOP: Cable=Alex
Murphy reveal). DeepSeek HIZLI (2.7-3.1s) ve gemini'nin 429 kota sorununu yaşamıyor. 25/25 test yeşil.

**Açık kalem:** Qwen konsey anahtarı council_mcp/.env'de kırık (401) — konsey tek-üyeli (GLM).
Kanıt dosyaları: scratchpad/ab_sonuc.txt (6-film eski-vs-v2), scratchpad/dogrula_deepseek.py.

---

## 2026-07-23 — Reboot veri kaybı KURTARILDI; %92 kampanyası planlandı, Sonnet'e devredildi

**Olay:** Sistem 11:24'te yeniden başladı → /tmp scratchpad SİLİNDİ (119-film GT,
tahminler, tüm kareler). Ders: kritik veri artık REPO'da tutuluyor.

**Kurtarma:**
- 119-film doğrulanmış GT + v5 tahminleri workflow journal'ından
  (`~/.claude/.../wf_aac18f35-fac/journal.jsonl`) bit kaybısız kurtarıldı →
  `harness/kunye_kiyas/veri/{dogrulama_sonuc,v5_tahminler}.json`. Bozuk "_" kaydı
  düşüldü → taban **87/118 = %73.7** (kredi-var 56/87 ≈ %64, kredi-yok 30/31 = %96.8).
- pool_cek_cikar.sh / batch_v5.py / gt_duzeltilmis (8 film + YILDIZ=46) transcript'ten kurtarıldı.
- **Kaynak taşınmış:** 30.06 klasörü boşaltılmış; filmler `Film Kapanış` içine
  `evoArcadmin_<parti>_<id>-<AD>.mp4` adıyla gitmiş. 115/118 tam id eşleşti
  (YOK: SAKLI_GERÇEKLER, RIGOLETTO, 300_SPARTALI).
- **Parite kanıtı:** OPERADAKİ_HAYALET yeniden indirildi → süre 5460s, kare 1201,
  v5=1161 — kayıtla BİREBİR. GT yeni indirmelerde geçerli.
- Kareler artık kalıcı diske iniyor: `/opt/mitas/data/jenerik_havuz/pool_frames/`
  (`veri/havuz_kur.sh`, hata filmleri önce; log: `veri/havuz_kur.log`).

**Konsey (2 tur kırmızı-takım; GLM taşıdı, Kimi her turda 429/Moonshot, Qwen 401):**
GLM "Motion-Gated Onset" önerdi; hakemlik sentezi: scroll-tip koşuda onset otoritesi
HAREKET, statik kartta İÇERİK çapası (epilog gardıyla). Tur-2 kazanımları: 2fps
aliasing gardı (dy max_shift'e yapışırsa scroll say), epilog ayırıcısı=yapısal düzen
(noktalama), SON_ERISIM gevşetmesinde çekirdek-rol beyaz listesi, split-screen ROI (YAGNI).

**Plan → Sonnet:** `docs/MITAS_Jenerik_92_Iyilestirme_Plani_v1.md` (8 görev:
ölçüm harness'ı, kapı-teşhisi, hata atlası, scroll-onset, statik içerik-çapası,
kaçırılan-kurtarma, kabul, kayıt). T1+T2 Sonnet subagent'ları başlatıldı.

**Bekleyen:** indirme ~115 film (saatler); T3 atlası indirme ilerledikçe;
kırmızı çizgi kredi-yok ≥30/31; Kimi tekrar denenecek (görüş eksik kaldı).

## 2026-07-20 (akşam) — Dilim-vs-video testi kuruldu, jenerik-başı tespitinde DURDU

**Karar (Çağatay):** Yol A (kare OCR) sistemden çekilecek; Yol B (havuz→master→dilim→VL)
ve Yol C (start_pos'tan 1'er dk sessiz klip→VL) eşzamanlı koşup 4 sonuç + referans
üretecek, tek PDF'te kıyaslanacak. ASR/QC/PDF-üretimi yok.

**Yapılan:**
- Kaynak: `smb://depo01cifs.int.trt.net.tr/sas_h264/Film Kapanış` (2398 film).
  Mount "denied" verdi; **`gio copy` FUSE'u atlayıp çözdü (57 MB/s)**. GVFS FUSE yolu
  ffmpeg ile KULLANILAMAZ (ffprobe "error reading header", dd açamıyor, cat 100MB→1.1MB).
  Retry şart (GVFS kararsız). 18 film indirildi (13.2 GB).
- Deterministik seçim (tohum 20260720), yapım-id dedup → 20 film; 2'si elendi → **18 film**.
- **Katman A referansı**: 41 agent'lı workflow (2.5M token, 23 dk) — her film için web
  araştırması + bağımsız skeptik doğrulama. 484 isim, ort. 26.9/film. Sentez hükmü:
  *precision ölçülebilir, recall ölçülemez* (referans kapsamı jeneriğin çok altında).
- **`harness/kunye_kiyas/isim_normalize.py`** yazıldı (55 golden test + 6333 çift gerçek
  veri sınaması, 0 yanlış birleştirme / 0 yanlış ayırma).
- **Model benchmark** (5 model × 5 film, 13 çıkış dilimi): kazanan **`qwen36-27b-test`**
  (recall %54.1, tekrar %1.7, kaçış %0, 0 kesik, 497s). `glm-ocr` recall %50.4 ama **6× hızlı** (83s).
  `qwen2.5vl:7b` %52.6. `gemma4:26b` %26.3 (tekrar %77). **`qwen3-vl:8b` %0.8 — kullanılamaz.**

**Öğrenilen / çürüyenler:**
- **`qwen3-vl:8b` (ollama) THINKING DÖNGÜSÜNE giriyor**: 16384 token üretiyor, hepsi
  `thinking` alanına, `response` boş. Tetikleyici thinking metninde yakalandı:
  *"Wait, but in the user's image, is there a duplicate"* — **master PNG'nin duplikasyon
  kusuru modeli kilitliyor**. think=False / /no_think / system mesajı / num_predict
  4096→8192→16384 hiçbiri durdurmadı. vLLM `Qwen3-VL-8B-Instruct` varyantı thinking
  yapmıyor ama **yönetmen uyduruyor** ("A FILM BY ALFRED HITCHCOCK" — film Michael Curtiz'in)
  ve frequency_penalty'siz 672 satır/654 tekrar dejenerasyon veriyor.
- **XML teknik alanları GÜVENİLMEZ**: "HD" dediği 6 filmden 3'ü gerçekte 512×288; codec
  hepsinde yanlış (MPEG2 diyor, gerçek h264). Sadece SÜRE alanı doğru. `sas_h264` düşük
  bitrate proxy tutuyor, XML kaynak master'ı anlatıyor.
- **Okunabilirlik endişesi YERSİZ**: 512×288'de bile kart jenerik ve kayan jenerik
  (Türkçe ĞŞİÜÇÖ dahil) net okunuyor — gözle doğrulandı.
- Ölçüm metodolojisi hatam: jenerik satırları görev etiketi + ismi BİRLİKTE taşıyor
  ("1. Yönetmen Yardımcısı / 1st AD MEHMET GEZMEN"); tam-satır eşleştirme bunu kaçırıyordu.
  `metinde_gecer_mi()` eklendi → SONSUZ AŞK recall 0/26 → 16/26.
- Yanlış karşılaştırma yaptım: üretimdeki "LALELER" (1988) ile benim "LALE SOKAĞI" (1957)
  farklı filmler. **18 filmimin HİÇBİRİ üretim Database'inde yok** (TRT-id kesişimi = 0).
- Master seçimi DOĞRU: `master_png_dilimle.py` varsayılanı `reading_master_runaware`
  (Çağatay'ın düzelttiği). Kanonik `<ad> cikis.png` 3 katmanlı dHash dedup uyguluyor ve
  uzun kayan künyeyi kesiyor. 8 filmin 5'inde ikisi AYNI — çünkü `strict_scroll_frac≥0.75`
  olunca reading, kanoniğe passthrough yapıyor (`db_compose_master.py:1012`).

**DURDURAN SORUN — jenerik başlangıcı tespiti:**
- 7 filmden 3'ü başarısız: LALE SOKAĞI (havuz 887/900, master 600×36695),
  DÖNÜŞÜ OLMAYAN NEHİR (829/900, 600×57781), ANNA KARENINA (havuz 0, stage1 fail).
- Debug kayıtları: **iki katman da çöküyor**. PaddleOCR CV üçünde de `cv_start=None`;
  VLM-rescue (qwen3-vl:30b, 170 çağrı) devreye giriyor ama ikisinde "jenerik en baştan
  başlıyor" diyor (start_frame=13 / left_censored 0), birinde `not_sustained_credit`.
- Çürütülen hipotez: rescue thinking-bugından ölü DEĞİL — `credit_start_vlm.py:88`
  `txt = content or thinking` ile korunmuş. Ama `num_predict=64` şüpheli kaldı.
- **ÜRETİMDE DE VAR ama görünmüyor**: 274 kayıtta `not_found` 47 (%17), havuz=0 olan
  54 film (%20). Bunların **%98'inde `kunye.txt` yine de üretilmiş** — çünkü künyeyi
  Yol A üretiyor. Yol A çekilince bu hata ilk kez görünür hale geliyor.

**Bekleyen:**
- **ÖNCELİK: jenerik başlangıcı tespiti çalışması.** Mevcut yaklaşım tamamen OCR-tabanlı
  ("bu karede yazı var mı"); eski/düşük kontrastlı filmlerde çöküyor. Kullanılmayan
  sinyaller: sahne-kesme yoğunluğu, hareket düzeni (dikey kayma), zemin siyaha dönüşü,
  yazı bölge/aralık düzenliliği, ses/müzik geçişi.
- Master PNG duplikasyon kusuru (SANTA FE'de aynı blok 2 kez; VL kilitleyen tetikleyici).
- `DERİN KUYU` tüm modellerde 0/15 recall — model mi okuyamıyor, referans mı uyuşmuyor?
- Yol C (video klip) hattı hiç koşulmadı.
- Çağatay onayı bekleyen: Yol A deaktivasyonunun test SONRASINA ertelenmesi önerisi.

---

## 2026-07-20 — Video-hibrit router kalibrasyonu → ölçüm kusuru bulundu

**Yapılan:**
- HYBRID_DEVIR_NOTU §4-adım-1 kalibrasyonu yürütüldü (28 film, manifest sinyalleri
  `kunye51_20260714/Database/` altında bulundu). Araçlar: `router_kalibrasyon.py`,
  `router_kiyas.py`, `router_sinyal_v2.py`, `router_loocv.py`,
  `router_kos_sonra_devret.py`, `gt_yanlilik_denetimi.py`,
  `masterpng_kayip_denetimi.py` (hepsi vllm_bench_20260718/, salt-okuma)
- Rapor: `docs/MITAS_Video_Hibrit_Kalibrasyon_v1.md`
- **Adım-2 (router modülü) DURDURULDU** — gerekçe aşağıda

**Öğrenilen / çürüyenler:**
- **Devir notunun ana hipotezi çürüdü:** `strict_scroll_frac` video-uygunluğu
  ayrıştırmıyor (GÜZEL_BİR_ÖLÜM scroll=0.881 → video 1.000; FRANNY scroll=0.063
  → 0.720). En güçlü korelasyon −0.445. A-priori router LOOCV %74 (+0.663 recall,
  2.0× hız) — kural 21/23 fold'da stabil ama karar verdirecek güçte değil.
- **ASIL BULGU — ölçüm dairesel:** `claude_gt`'nin 313 diliminin TAMAMI
  `reading_master_runaware_p*.png` kaynaklı, yani GT master-PNG okunarak
  üretilmiş. Video PNG'nin kaybettiğini okuyunca metrik "uydurma" yazıyor.
  Kanıt: KULÜBE (Rancho Notorious) — GT'nin iki `[okunamadı]` satırını video
  MARLENE DIETRICH / ARTHUR KENNEDY / MEL FERRER diye doldurmuş, satır hizasında.
  "Uydurma" havuzunun %98.7'si isim-formunda, sadece %1.3'ü teknik gürültü.
  → Notun "%24.7 uydurma" hükmü büyük ölçüde ölçüm hatası.
- **Master-PNG kayıp denetimi (Çağatay'ın seçimi):** video'nun 2096 isminin
  680'i (%32.4) hiçbir master-PNG modelinde yok. Üç popülasyon ayrıldı:
  (a) GERÇEK KAYIP — BEYAZ_BİZON'da master-PNG YALNIZ ekip bloğunu içeriyor,
      oyuncu kartı (Dino De Laurentiis, Jack Warden, Clint Walker, Slim Pickens)
      komple kayıp; iki model birebir aynı ekip listesini okuyarak doğruladı.
      Bu film GT'siz 4 filmden biri olduğu için kayıp benchmark'a hiç yansımamıştı.
  (b) GERÇEK UYDURMA — BABAM (390-isim duvarı), DAĞ_ADAMLARI'nda video gerçekten
      uyduruyor (CRAN T. HESTON = CHARLTON HESTON bozulmuşu). Uydurma
      yoğun/kayan jeneriğe özgü, kart-jenerikte değil.
  (c) METRİK ARTEFAKTI — CENNETTE'de İspanyol NO-DO başlıkları isim sanılmış.
- **İki kayıp mekanizması:** blok düşürme (DÜNYANIN 16, CENNETTE 12, JURASSIC 11
  blok düşmüş) VE kırpma taşması (KULÜBE'de 54/54 blok tutulmuş ama satır kesilmiş).
- **Konsey:** kırmızı-takım turu açıldı, YALNIZ GLM cevapladı (Qwen HTTP 401
  anahtar hatası, Kimi HTTP 429 bakiye bitmiş — ikisi de düzeltilmeli).
  GLM "a-priori router kurma, koş-sonra-devret'e geç" dedi; yönü doğru
  (süre iddiası tuttu: 1.52×, post-hoc sinyaller a-priori'den güçlü:
  video_sn ↔ Δrecall −0.664 vs −0.445) ama gerekçesi yanlıştı — %14 uydurmayı
  veri kabul edip metriğin geçerliliğini sorgulamadı.

**Bekleyen:**
- Bağımsız GT (6-8 filmde ham video karelerinden, master-PNG'den DEĞİL) —
  bunsuz ne kayıp oranı ne uydurma oranı sayısallaştırılabilir. PAHALI, onay ister.
- 680 PNG-dışı adayın (a)/(b)/(c) otomatik sınıflandırması yapılmadı.
- Master-PNG kırpma/blok-düşürme kusurunun kök sebebi (`_credit_detect.py`,
  `compose_motion_state_credits.py`) araştırılmadı.
- Router: bağımsız GT sonrası tekrar. Mevcut kanıt koş-sonra-devret'i işaret ediyor.
- Konsey anahtarları: Qwen (Alibaba hesap), Kimi (bakiye).

---

## 2026-07-19 — Ekosistem kurulumu + yönetim modeli

**Yapılan:**
- Skill ekosistemi kuruldu: ~385 skill / 75 agent / 260 command (14 marketplace,
  symlink ile `~/.claude/` altına). Rehber PDF: `docs/rehber/MITAS_Skill_Rehberi.pdf`
- `council_mcp` Linux'a taşındı (.venv yeniden), MCP olarak bağlandı (`council`)
- `providers/kimi.py` yazıldı (Kimi K3); Qwen/GLM'e model-override eklendi
- Yönetim modeli tartışılıp `CLAUDE.md`'ye yazıldı (133 satır): görev dağılımı,
  dış-konsey otonomisi, soru modları, mercek ataması, eskalasyon zinciri
- İlk otonom konsey turu: GLM'e mekanizma tasarımı soruldu — 3 önerisi
  (brifing formatı, sistematik-vs-istisna ayrımı, mercek ataması) deftere girdi
- Kalıcı hafıza başlatıldı (user profili, geri bildirimler, proje durumu)

**Öğrenilen / başarısız:**
- Qwen API: Alibaba hesabında ödeme sorunu → kod değil hesap meselesi
- Çağatay'ın ilk Kimi anahtarı sohbete yapıştırıldı → İPTAL edilip yenilenecek
- Marketplace dizinleri bir kez sessizce silindi (muhtemelen paralel oturumun
  /reload-plugins'i) — broken symlink çıkarsa kaynağa bak

**Ek (aynı gün, devam):**
- Guard hook'ları kuruldu ve CANLI DOĞRULANDI: kilitli-dosya onayı
  (mitas_roots.py, model_manifest.yaml, MITAS_KUNYE_KURALLARI.md, CLAUDE.md),
  .env okuma engeli, üretim-verisi silme engeli (`.claude/hooks/mitas_guard.py`)
- SessionStart hook: GUNLUK son kaydı her oturum açılışında otomatik yüklenir
- 4 MITAS-özel skill yazıldı (`.claude/skills/`): mitas-durum, mitas-benchmark,
  mitas-kunye-qc, mitas-konsey-kaydi. (film-ekle fikri Çağatay tarafından
  reddedildi — o MITAS otomasyonunun işi)

**Ek (aynı gün, devam 2):**
- Gerçek OCR-agent testi: `visual-analysis-ocr` agent'i AHLAT_AĞACI panorama
  görselinde çalıştırıldı — kalite çok iyi ama maliyet yüksek (~108K token,
  ~6dk/görsel). Prensip 2 uzantısı eklendi: maliyetli deneyler önce Çağatay
  onayı gerektirir (CLAUDE.md).
- `model_manifest.yaml`'a Claude-Vision-OCR resmi aday olarak eklendi.
- Konsey ilk GERÇEK kullanımı: yerel VLM fine-tune yol haritası için 2 turlu
  kırmızı-takım/açık-tur. 1. tur YANLIŞ ölçekle (400 dosya) brifing edildi,
  GLM "fine-tune'a girme" dedi. Gerçek ölçek (~2.000 film + 8-10K dizi +
  belgesel/müzik, sürekli büyüyen) ortaya çıkınca 2. tur açıldı, GLM fikrini
  TAMAMEN DEĞİŞTİRDİ: hibrit yaklaşım (yerel taslak + Claude hedefli
  düzeltme) onaylandı, fine-tune kararı veri birikene kadar ertelendi.
  Bkz. `docs/KONSEY_KARARLARI.md`, `docs/MITAS_VLM_Finetuning_Kunye_OCR_Plan_v1.md`.
  DERS: brifing kalitesi kararı doğrudan etkiliyor — yanlış ölçek yanlış
  tavsiyeye yol açtı.

**Ek (aynı gün, devam 3):**
- Konsey kapsamı genişletildi: sadece mimari/strateji değil, artık **kod
  incelemesi/bug avcılığı** için de kullanılıyor (`codex-review`'e ek).
  GLM/Qwen/Kimi'nin kod yeteneği de aktif kullanılacak. Mercek ataması: GLM
  güvenlik, Qwen performans, Kimi edge-case avcısı. CLAUDE.md güncellendi —
  "rutin hata teşhisi" (konsey dışı) ile "proaktif kod incelemesi" (konsey
  içi) net ayrıldı, karıştırılmasın diye özellikle işaretlendi.

**Bekleyen:**
- [ ] Kimi yeni anahtar → `/opt/mitas/council_mcp/.env` (Çağatay, işyerinde)
- [ ] Alibaba ödeme sorunu HÂLÂ ÇÖZÜLMEDİ (Çağatay) — Qwen 2 turdur cevap veremiyor
- [ ] Hibrit OCR hattı için pilot parti (10-20 film) — gerçek maliyet/kalite ölçümü
- [ ] Yeni skill'lerin ilk gerçek koşuda test edilmesi (özellikle mitas-kunye-qc)
- [ ] ~5-10K (taslak,düzeltme) çifti birikince: fine-tune kararını gerçek veriyle ver
- [ ] ~2 hafta sonra: konsey etki değerlendirmesi (karar kayıtlarından)
