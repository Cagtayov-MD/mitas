# KONTROL Kök-Neden — KONSOLİDE FIX PLANI (2026-07-07, gece)

242 KONTROL PDF adli denetiminden (216 film incelendi) çıkan **7 kova** için, kök-kodu okunmuş +
çoğu canlı-reprodüksiyonla doğrulanmış fix-tasarımları. Öncelik + risk + **PARDAYYAN-çakışma** haritalı.

---

## ⚠️ UYGULAMA ÖN-KOŞULU (hepsi için geçerli)
Gece boyu **PARDAYYAN oturumu** (yapımcı/KB işi) aynı kredi-dosyalarını aktif düzenledi/commit'ledi
(`758e38df`, `46ff2565`, `b0f371e8`) ve `credit_text_read.py`'de commit'siz WIP + o an KIRMIZI bir test
bıraktı. **Ağaç temiz + `pytest tests/test_credit_qc_block.py` yeşil olmadan HİÇBİR şey uygulanmaz/re-run edilmez**
(re-run kuyruk-worker'ı da canlı working-tree kodunu kullanır → PARDAYYAN'ın yarım kodu output'a sızar).

**PARDAYYAN-dosya sahipliği (bu an):** `credit_text_read.py` (DIRTY), `credit_crosscheck.py` (KB-tolerans commit'i),
`tek_film_kunye.py`, `mitas_pipeline.py` (pipeline commit'i) → bu dosyalara dokunan fix'ler PARDAYYAN bitince
+ onun değişiklikleriyle uzlaştırılarak uygulanmalı. `credit_role_lexicon.py` ve `credit_qc_block.py` daha izole.

---

## TIER 1 — KOD-FIX YOK, sadece RE-RUN (en büyük temiz kazanç)
### 36 film: OCR-arızalı (ollama-kesintisi) → yeniden koş
`ocr_bucket=HATA/BOS/MOTOR_YOK` + `ocr_lines=0`; 26'sı açıkça "LLM katmanı çalışmadı (ollama model deposu boş)".
**ollama şu an AYAKTA** (doğrulandı) → yeniden koşulunca OCR/LLM üretecek. **Liste: `RERUN_OCR_ARIZALI.json`.**
- Araç: `scripts/yeniden_kosu_kickoff.py` benzeri (backend kuyruğu API 8787) veya WebUI enqueue.
- Ayrıca "kod-zaten-fixli" filmler (1942-0020 WERKER, 1955-0046 CLOUZOT, 1976-0184 MARTINSON...) da bu turda.
- **Risk: yok** (yeni kod değil). Ön-koşul: PARDAYYAN temiz + test yeşil.

---

## TIER 2 — Doğrulanmış, düşük-riskli kod fixleri

### FIX 1 — cast_cap: 10-sınırı gerçek oyuncuları kesiyor (52 film)
Canlı render `cast[:_cap]`, `_cap=MITAS_CAST_CAP(10)`. `[:8]` render dosyaları ESKİ varyant (canlı=`_make_pdf`).
**DIFF:** `scripts/mitas_pipeline.py` anchor `"MITAS_CAST_CAP": "10",` → `"18",`; `scripts/start_mitas.ps1` `'10'`→`'18'`.
**Risk: düşük** (cap yalnız >10-oyunculu filmde bağlayıcı; ≤10 değişmez). **PARDAYYAN: mitas_pipeline.py sahipliği → uzlaştır.**

### FIX 2 — RESCUE: OCR-okunmuş + KB-teyitli düşen isim geri (Türkan Şoray sınıfı)
`otorite_audit.ocr_dropped` zaten hesaplanıyor (credit_qc_block.py:174-217) ama geri konmuyor.
**DIFF:** credit_qc_block.py `return {` (satır ~894) ÖNCESİ, audit hesabından (892) sonra:
```python
        # S12b RESCUE — ocr_dropped'dan KB/GT-teyitli düşen isim (2026-07-07, UTANMAZ ADAM/Türkan Şoray)
        _rescue_on = (os.environ.get("MITAS_CAST_RESCUE_DROPPED", "1").strip().lower()
                      not in ("0","false","off","no"))
        if _rescue_on and locked and isinstance(otorite_audit, dict) and otorite_audit.get("ocr_dropped"):
            _have = {_fold(n) for n in temiz_cast}
            for _dn in (otorite_audit.get("ocr_dropped") or []):
                if _dn and _fold(_dn) not in _have:
                    temiz_cast.append(_upper_names([_dn])[0]); _have.add(_fold(_dn))
                    iz.append({"alan":"oyuncu","kaynak":"rescue-ocr_dropped","isim":_dn})
```
`_fold`(112) + `_upper_names`(92) mevcut. **EŞLEŞİK: FIX 1 ile birlikte** (append'te #11 olup cap'e takılmasın).
**Risk: düşük** (ocr_dropped ham+KB çift-teyitli). credit_qc_block.py nispeten izole.

### FIX 6 — lexicon_anchor_misparse: yönetmen-başlık yanlış parse (28 film)
Bug1 "PRODUIT ET DIRIGE PAR"→"PRODUIT ET" (CLOUZOT); Bug2 "DIRECTED BY"+cümle→"EXPLODED THROUGHOUT..." (TRENCHARD-SMITH).
**DIFF:** `scripts/credit_role_lexicon.py`: (a) DIRECTOR listesine bileşik başlıklar ekle
("PRODUIT ET DIRIGE PAR","PRODUCED AND DIRECTED BY"...); (b) `_is_name`'e cümle-parçası filtresi
(≥3 token + ≥2 stopword → reddet). Selftest: `python scripts/credit_role_lexicon.py`.
**Risk: düşük-orta** (stopword-listesi heuristik; gerçek isim "SOUTH/WAR" içerirse yanlış-red — selftest+golden ile teyit).
**PARDAYYAN: credit_role_lexicon.py muhtemelen sahipliği DIŞINDA → en izole fix.** NOT: bazı kalıplar dd55c0ae/d4df63f3'te
kısmen ele alınmış olabilir; uygulamadan önce mevcut kodda kalıbın HÂLÂ açık olduğunu selftest ile teyit et.

---

## TIER 3 — Taslak / riskli / PARDAYYAN-çakışan (ertele + uzlaştır)

### FIX 4 — KB_veto/deferans: fuzzy gevşetme (39+14 film)
Taslak: `credit_crosscheck.py` fuzzy eşiği 0.80→0.75 + Türkçe-aware edit-cap + KB-boş fuzzy-rescue bloğu.
**Risk: orta** (yanlış-kabul artışı). **PARDAYYAN TAM BU ALANDA AKTİF** ("KB-fill", "KB tek-harf tolerans") →
büyük olasılıkla kısmen çözülüyor. **DOKUNMA; PARDAYYAN çıktısıyla uzlaştır.** (Türkan Şoray bu değil, FIX 2 ile çözülüyor.)

### FIX 5 — guard: iki alt-küme
- **OCR-HATA alt-kümesi** → TIER 1 re-run (kod-fix yok). En büyük parça.
- **guard-gevşetme** (CARL CALDANA gibi ham+VL'de olan gerçek isim eleniyor): taslak, `credit_text_read.py`'de
  VL+KB çift-imza bypass. **Risk: orta. PARDAYYAN DIRTY BU DOSYADA → ertele.**

### FIX 7 — identity_unlocked: kilit gevşetme (22 film)
**ÖNEMLİ: bu filmlerde cast SİLİNMİYOR** (OCR-otorite korur), yalnız KONTROL'e gidiyor (gereksiz-KONTROL).
Taslak: `locked = ... or (cast_ov>=1 and strong_ocr_cast)`. **Risk: orta** (sequel/aynı-kadro yanlış-film).
Kayıp olmadığı için **düşük öncelik**; istenirse dikkatli + golden ile.

---

## FIX 3 — garble_gate: DEĞİŞİKLİK YOK
Mekanizma doğru; "garble" etiketleri yanlış-atıf (gerçek kök: OCR-HATA/lexicon/upstream). Dokunma.

---

## ÖNERİLEN UYGULAMA SIRASI (PARDAYYAN temiz+yeşil olunca)
1. **Golden baseline**: `pytest tests/test_credit_qc_block.py tests/test_qc_*.py`; `python scripts/regresyon_golden.py` — YEŞİL teyidi.
2. **FIX 6 (lexicon)** — en izole; uygula → selftest → golden → commit.
3. **FIX 1 + FIX 2 (cap+rescue, eşleşik)** — uygula → golden → UTANMAZ ADAM re-run (cast>10 + Türkan Şoray döndü) → commit.
4. **TIER 1 re-run** — 36 OCR-arızalı film + kod-zaten-fixli filmleri kuyruğa ver; örnek 3-5 filmde OCR üretimini teyit et.
5. **TIER 3** — PARDAYYAN çıktısıyla uzlaştırıp (KB_veto/guard) tek tek, golden ile; identity_unlocked opsiyonel.
6. Her fix AYRI commit; her commit öncesi golden yeşil + ilgili film re-run kanıtı (Çağatay kuralı).
