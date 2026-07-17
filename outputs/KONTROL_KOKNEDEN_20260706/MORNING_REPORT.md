# SABAH RAPORU — KONTROL Kök-Neden Denetimi + Fix Hazırlığı (gece 2026-07-06→07)

## TL;DR
- ✅ **242 KONTROL PDF'inin kök-neden denetimi TAMAM** (216 benzersiz film, 470 bulgu; kalan 13 film Database'de yok).
- ✅ **Türkan Şoray vakası çözüldü** (görsel kanıtla): kaybın kökü OCR isim-parçalama + rescue-yokluğu.
- ✅ **2 FİX UYGULANDI + DOĞRULANDI + COMMIT'LENDİ** (master'da):
  - **`0a30ba02`** — FIX 6 lexicon_anchor (CLOUZOT sınıfı): "PRODUIT ET DIRIGE PAR" → doğru "H.G. CLOUZOT".
    Kanıt: anchor_roles reprodüksiyonu (['PRODUIT ET'] → ['H.G. CLOUZOT']) + golden 4/7 KORUNDU (geçen 4 bozulmadı).
  - **`81b10bf9`** — FIX 1+2 (cast_cap 10→18 + ocr_dropped RESCUE / Türkan Şoray sınıfı).
    Kanıt: yeni `test_ocr_dropped_rescue` deterministik PASS + golden 4/7 KORUNDU + qc suite yeni-fail yok.
- ⚠️ **Baseline golden KIRMIZI ama BENDEN DEĞİL:** `regresyon_golden.py` HEAD'de 4/7 (FAIL: Minnelli,
  Rochefoucauld, ANGOLA/Martinson) + `test_dubbing_director_drop` (Sam Raimi) + 2 bayat cap-testi (expect 8).
  Bunların **HEPSİ PARDAYYAN oturumundan / önceki tech-debt** (commit `46ff2565` ANGOLA'yı golden'a ekledi ama
  geçmiyor). Benim 2 commit'im bu kırmızıları **ne yarattı ne bozdu** — geçen vakaları koruduğumu her adımda kanıtladım.
- ⏳ **UYGULANMADI (bilinçli):** TIER 3 = KB_veto/guard/identity_unlocked — PARDAYYAN'ın AKTİF çalıştığı alan
  (KB/fuzzy/yapımcı) ile çakışıyor + daha riskli. Tasarımları FIX_PLAN.md'de; PARDAYYAN'la uzlaştırıp sen uygula.
- ⏳ **RE-RUN (senin tetiklemene bırakıldı):** çok-saatlik ağır iş, sabah penceresi kapandı. Bkz. aşağıdaki 36-film
  bloğu + UTANMAZ ADAM (FIX 1+2'yi uçtan-uca teyit için — beklenen: TÜRKAN ŞORAY künyede görünür).

## 🎯 EN SOMUT SABAH AKSİYONU — 36 film SADECE RE-RUN istiyor (kod-fix YOK)
216 filmin **36'sı** OCR bucket=HATA/BOS/MOTOR_YOK + `ocr_lines=0`; **26'sı açıkça
"LLM katmanı çalışmadı (ollama model deposu boş/erişilemez)"** diyor → bunlar **ollama-kesintisi**
döneminde LLM/OCR'siz işlenmiş sahte-KONTROL'ler. **ollama şu an AYAKTA** (gemma4:26b, glm-ocr,
qwen'ler mevcut — doğrulandı), yani bu 36 film **yeniden koşulunca düzelmeli**. Kod değişikliği gerekmez.
- Liste: `RERUN_OCR_ARIZALI.json` (36 film, ör. 1967-0037 MUTLU GÜNLER, 2010-9169 PERCY JACKSON,
  2011-9209 EL GUSTO, 1999-0394 13. SAVAŞÇI...).
- Re-run aracı: `scripts/yeniden_kosu_kickoff.py` (backend kuyruğuna API 8787 ile ekler) veya WebUI.
- ⚠️ **AMA PARDAYYAN temizlenmeden re-run YAPMA:** kuyruk-worker canlı working-tree kodunu kullanır;
  PARDAYYAN'ın commit'siz/yarım kodu output'a sızar. Önce ağaç temiz + test yeşil.

## Teslim dosyaları (`E:\MITAS\outputs\KONTROL_KOKNEDEN_20260706\`)
- **`KOKNEDEN_TAM_LISTE.md`** — film-film tam liste (her alan → verdict + kök-aşama + isim + kod-konumu + fix-ipucu)
- **`KOKNEDEN_MASTER.csv`** — tablo (kanıt-frame + OCR-alıntı + kod-konumu sütunları)
- **`KOKNEDEN_RAPOR.md`** — sayısal özet
- **`FIX_PLAN.md`** — hazır-uygulanır fix diff'leri (bu rapor tamamlayıcısı)

## Audit sonucu (216 film, 470 bulgu)
| Hüküm | Adet | Fixlenebilir? |
|---|---|---|
| **A_ELENDI** (framede var, elendi) | 188 | ✅ EVET |
| **B_OCR_OKUYAMADI** (framede okunur, OCR kaçırdı) | 32 | ✅ EVET |
| D_JENERIKTE_YOK (gerçekten yok) | 141 | ⛔ hayır |
| ÖZET_TRANSKRIPT_YOK (sessiz/konuşma yok) | 50 | ⛔ hayır |
| C_OKUNAMAZ (yabancı/bozuk) | 27 | 🔶 zor |
| E_VERI_YOK | 26 | — |
| OZET_URETILEMEDI (ASR arıza) | 5 | 🔶 ASR |

**~220 bulgu fixlenebilir** (isim var, sistem kaybetti).

### A_ELENDI kök-aşamaları (fixlenecek asıl buglar)
| Aşama | Film | Durum |
|---|---|---|
| **cast_cap** | 52 | FIX 1 hazır (env 10→18) |
| **KB_veto** | 39 | gece fix-tasarımı (fuzzy + KB-boşsa-veto-yok) |
| **lexicon_anchor_misparse** | 28 | gece fix-tasarımı (bileşik-başlık/cümle-red) |
| **garble_gate** | 28 | DEĞİŞİKLİK YOK (yanlış-atıf; çoğu re-run/lexicon/OCR) |
| **guard** | 25 | gece fix-tasarımı (bir kısmı OCR-job HATA) |
| **identity_unlocked** | 22 | gece fix-tasarımı (riskli — dikkatli) |
| **deferans** | 14 | KB_veto ile birlikte |

## Türkan Şoray (UTANMAZ ADAM 1961-0005) — çözüldü
Master-PNG **görsel-teyitli**: TÜRKAN ŞORAY jenerikte 2. oyuncu, final künyede yok. Kök: OCR adını
**ters/ayrık** okumuş (`SORAY / ARDUTÜRKANN / TÜRKAN`) → isim-birleştirici kuramadı. Sistem düştüğünü
**biliyor** (`otorite_audit.ocr_dropped=["Türkan Soray"]`) ama geri koymuyor. **KB-veto/fuzzy değil**;
çözüm = FIX 2 (ocr_dropped rescue) + FIX 1 (cap, çünkü append'te #11 olup cap'e takılıyor). İkisi **eşleşik**.

## Neden uygulanmadı (önemli)
Oturum başında bu dosyalar `M` (commit'siz) idi; gece **PARDAYYAN oturumu** bunları commit'ledi
(`758e38df`, `46ff2565`, `b0f371e8`) ve **hâlâ aktif** (credit_text_read.py commit'siz-dirty, bir dubbing
testi kırmızı). Paylaşılan çalışma dizininde eşzamanlı edit = clobber. Bu yüzden **golden-yeşil + ağaç-temiz**
olana kadar bekliyorum. Fix'ler dakikada uygulanır.

## Sabah yapılacaklar (öneri sıra)
1. PARDAYYAN oturumunu bitir/commit'le (ağaç temizlensin, kırmızı test düzelsin).
2. FIX_PLAN.md'deki FIX 1 + FIX 2'yi uygula (eşleşik) → golden test → UTANMAZ ADAM re-run (Türkan Şoray döndü mü) → commit.
3. Gece fix-tasarımlarını (KB_veto/lexicon/guard/identity) FIX_PLAN.md'ye eklenmiş halde gözden geçir, güvenli olanları uygula.
4. Etkilenen filmleri (cap/rescue/lexicon) toplu re-run.

## Ben ne yapıyorum (gece devam)
- Kalan kova fix-tasarımlarını FIX_PLAN.md'ye işliyorum.
- PARDAYYAN'ı izliyorum; temiz+yeşil olunca FIX 1+2'yi uygulayıp golden+re-run ile doğrulayıp commit'leyeceğim.
