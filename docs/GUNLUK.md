# MITAS Proje Günlüğü

> Amaç: oturumlar arası süreklilik. Her Claude Code oturumu AÇILIŞTA son 2-3
> kaydı okur, KAPANIŞTA (veya önemli bir iş bitince) yeni kayıt ekler.
> Format: tarih + yapılan + öğrenilen/başarısız denemeler + bekleyen.
> En yeni kayıt EN ÜSTTE.

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
