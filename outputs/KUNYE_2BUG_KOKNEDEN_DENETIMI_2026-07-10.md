# 2 Test Hatası — Kök Neden Denetimi (2026-07-10)

**Görev kaynağı:** `filter_cast_by_raw_context` komşu-dışlama düzeltmesini (task_ebc9425c) doğrularken
geniş test paketi çalıştırılınca bulunan 2 test hatası. Sistematik hata-ayıklama (reproduce → trace →
kök-neden → tek-fix → doğrula) ile incelendi. **Hiçbir şey commit edilmedi** — proje kuralı
("değişiklik yalnız talimatla") gereği düzeltmeler working tree'de bırakıldı, insan incelemesi bekliyor.

---

## BUG #1 — `_drop_dubbing_directors` gerçek yönetmeni dublaj sanıp düşürüyor

**Dosya:** [scripts/credit_text_read.py](../scripts/credit_text_read.py:443)
**Test:** `tests/test_credit_qc_block.py::test_dubbing_director_drop`
**Durum:** Gerçek, önceden-var-olan (HEAD `e374cb59`'da da başarısız) — commit `2f9ecdcd` (2026-07-03,
TILSIMLI DÜNYA) ile giren bir **regresyon**, o zamandan beri (~1 haftadır) fark edilmemiş.

### Belirti
```python
raw = ["KURGU", "AHMET K", "SESLENDİRME YÖNETMEN YARDIMCISI", "ESRA TANAR",
       "SESLENDİRME YÖNETMENİ", "ENGİN AYBAKAN", "YÖNETMEN", "Sam Raimi"]
kept, dropped = _drop_dubbing_directors(["ESRA TANAR", "ENGİN AYBAKAN", "Sam Raimi"], raw)
# beklenen: "Sam Raimi" in kept
# gerçek:   kept == [] — Sam Raimi de (dublaj rolleriyle birlikte) düşüyor
```

### Kök neden (instrumentation ile doğrulandı, tahmin değil)
`dub_ctx` penceresi (`folded[i-4 : i+1]`) dublaj-marker arayışı için satırın **4 satır YUKARISINA**
kadar bakıyor — bu pencere, aralarında **başka bir adayın kendi kart sınırı** olsa bile duruyor.
Sam Raimi (satır 7) için pencere satır 3'e (`ESRA TANAR`) kadar geri gidiyor ve satır 4'teki
`"SESLENDİRME YÖNETMENİ"` etiketini yakalıyor — oysa bu etiket satır 5'teki **ayrı bir kişiye**
(ENGİN AYBAKAN) ait, Sam Raimi'nin kendi kartıyla (satır 6-7: `YÖNETMEN` / `Sam Raimi`) hiç ilgisi yok:

```
i-4: ESRA TANAR              <- başka aday (önceki kart)
i-3: SESLENDİRME YÖNETMENİ    <- marker (ENGİN AYBAKAN'ın kartı, Sam Raimi'nin DEĞİL)
i-2: ENGİN AYBAKAN            <- başka aday (kendi kartı ayrıca doğru şekilde düşüyor)
i-1: YÖNETMEN                 <- Sam Raimi'nin KENDİ etiketi
i:   Sam Raimi                <- değerlendirilen aday
```
`dub_ctx` bu marker'ı yakalayınca `_TRUE_DIR_RE` bağışıklığı (ki Sam Raimi için AKTİF olurdu) o dal
için bilinçli olarak bastırılıyor (TILSIMLI DÜNYA'nın kendi mantığı gereği) — yani immunite yok, direkt düşüyor.

**Regresyon zaman-çizelgesi (git arkeolojisi ile doğrulandı):**
- `f8c67de0` (2026-06-20): `_drop_dubbing_directors` + bu test BİRLİKTE eklendi, o zaman ±1/±2 pencereyle geçiyordu.
- `2f9ecdcd` (2026-07-03, "TILSIMLI DÜNYA"): dublaj-marker'a özel ±4 YUKARI pencere + `_TRUE_DIR_RE`
  bağışıklık-bastırma eklendi — "Dialogue Written and Directed by GREG SNEGOFF" gibi 4 satıra bölünen
  TEK kartı çözmek için. Bunu yaparken, pencerenin araya giren AYRI bir kartı aşabileceği durum
  düşünülmemiş → Sam Raimi testi o gün sessizce kırıldı, sonrasında kimse bu dosyayı tekil çalıştırmadı.

### Uygulanan düzeltme (minimal, kök-nedene özel)
`dub_ctx` penceresinin yukarı sınırını, aralardaki **başka bir adayın kendi isim-satırı**nda durdur —
yani pencere başka bir kart'ı ASLA aşmasın. TILSIMLI DÜNYA senaryosunda marker zaten sınır-adayın
(Macek) kendi satırından SONRA/aynı kartta kaldığı için etkilenmiyor:
```
i-3: CARL MACEK               <- başka aday (sınır)
i-2: DIALOGUE                 <- marker, SINIR'DAN SONRA → pencerede KALIYOR
i-1: WRITTEN AND DIRECTED BY
i:   GREG SNEGOFF              <- hâlâ doğru şekilde düşüyor
```
Diğer adaylara ait komşu isim-satırı yoksa (tekil-aday çağrısı, en yaygın gerçek kullanım) davranış
**tamamen değişmiyor** — eski ±4 penceresi aynen çalışıyor.

### Doğrulama
- Hedef test: **PASSED** (`test_dubbing_director_drop`)
- TILSIMLI DÜNYA senaryosu elle yeniden kurulup çalıştırıldı: Macek kept / Snegoff dropped — **korunuyor**
- Tekil-aday çağrısı (başka isim yok): davranış **birebir aynı** (regresyon değil)
- Fail-safe (`raw_lines=None`) yolu: **aynen çalışıyor**
- `tests/test_credit_qc_block.py` tam dosya: **24/24 PASSED**

---

## BUG #2 — `_gate_role_names` "ocr_suffix" fallback'i düşmüş (BAŞKA OTURUMUN regresyonu)

**Dosya:** [scripts/tek_film_kunye.py](../scripts/tek_film_kunye.py:294)
**Test:** `tests/test_tek_film_kunye_person_gate.py::test_global_person_gate_keeps_suffix_when_external_kb_has_no_hit`
**Durum:** **HEAD'de SIFIR sorun** (temiz HEAD'de test PASS ediyor) — bu, MITAS'ta **aynı anda çalışan
başka bir Claude Code oturumunun** `scripts/tek_film_kunye.py` üzerindeki commit'siz değişikliğinin YAN
ETKİSİ (bkz proje-belleği: paralel-oturum-aynı-dosya deseni, 2026-07-07'de de bir örneği görülmüştü).

### Kök neden (git diff ile kesin kanıtlandı, tahmin değil)
`git diff -- scripts/tek_film_kunye.py`, o oturumun EKLEDİĞİ birçok meşru özellikle (poster-fallback,
yapımcı-fuzzy-kanonikleştirme, `_looks_role_heading_name`, director-validation-trace) YAN YANA, şu 6
satırı SİLDİĞİNİ gösterdi:
```python
            if not hit:
                candidates = _suffix_person_candidates(nm)
                if candidates:
                    candidate_used = candidates[0]
                    hit = {"name": candidate_used, "match": "ocr_suffix", "distance": 0}
                    src = "ocr_suffix"
```
Bu blok HEAD'de, `_person_gate_hit` hem ismin kendisi için hem TÜM suffix-adayları için KB/XML/film-havuzunda
hiçbir eşleşme bulamadığında devreye giren SON çare fallback'i: OCR'ın "KARAKTER ADI + OYUNCU ADI" biçimini
ayrıştırıp bulduğu en kısa suffix'i (ör. "Maura Sally Hawkins" → "Sally Hawkins") KB doğrulaması OLMADAN,
ama açıkça `source="ocr_suffix"` etiketiyle tutuyor. Bu, projenin **"KB yokluğu asla ceza değildir"**
ilkesiyle (bkz proje-belleği: KB dizi-kapsaması SIFIR) birebir örtüşüyor — bu düşmüş blok olmadan,
KB'de kaydı olmayan HER oyuncu (dizi crew'unun ~%90'ı) suffix-heuristiği başarılı olsa bile tamamen
düşüyordu.

Diğer oturumun testleri (`test_person_gate_drops_role_heading_without_suffix_truncation` dahil) bu
bloğun silinmesine BAĞLI DEĞİL — o testin kendi senaryosu ana for-döngüsü içinde zaten eşleşme buluyor,
fallback bloğuna hiç erişmiyor. Yani silinme kasıtlı bir yeniden-tasarım değil, muhtemelen aynı fonksiyona
komşu satırlarda (`_looks_role_heading_name` eklenirken) yapılan kazara bir tıraşlama.

### Uygulanan düzeltme
Yalnız o 6 satır, TAM HEAD metniyle, tam eski konumuna geri eklendi — **izole-hunk tekniği** (bkz
proje-belleği: paralel-oturum-aynı-dosya-commit-hijyeni) ile diğer oturumun 120+ satırlık öteki
eklemelerine (poster-fallback, yapımcı-kanonikleştirme, director-validation-trace, vb.) **dokunulmadı**.
Doğrulama: düzeltme sonrası `git diff` bu 6 satırı ARTIK HİÇ GÖSTERMİYOR (HEAD ile birebir eşleşiyor →
diğer değişiklikler hâlâ olduğu gibi duruyor, satır-sayısı 133 eklemeden 127'ye düştü, silinen-satır
sayısı 6'dan 2'ye düştü — kalan 2 silme tamamen diğer oturuma ait, ilgisiz).

### Doğrulama
- Hedef test: **PASSED**
- Aynı dosyadaki diğer 4 person-gate testi + `test_credit_qc_block.py`'deki (diğer oturumun bugün
  eklediği) 3 yeni test (`test_person_gate_drops_role_heading_without_suffix_truncation`,
  `test_director_anchor_weak_external_validation_relaxes_kimlik`,
  `test_existing_poster_fallback_uses_pdf_afis`) dahil **29/29 PASSED**

---

## Doğrulama metodolojisi — "temiz HEAD'e karşı" izolasyon

Her iki bulguda da iddia "önceden-var mı yoksa bugünkü commit'siz işin yan etkisi mi" sorusu, üç farklı
teknikle **çalıştırılarak** (sadece diff okunarak değil) kanıtlandı:
1. Bug #1 ve #2 için: `git show HEAD:dosya.py` ile scratchpad'e izole kopya çıkarılıp doğrudan import
   edildi (gerçek working tree'ye hiç dokunulmadan).
2. Bug #2 için ayrıca: `git diff -- scripts/tek_film_kunye.py` okunarak silinen bloğun TAM METNİ tespit edildi.
3. Ek 12 test (aşağıda) için: bu oturumun KENDİ git worktree'si (`claude/zealous-meninsky-f51b1f`, HEAD
   `e374cb59` — E:\MITAS master ile birebir aynı commit, hem bugünkü hem diğer oturumun commit'siz
   değişikliklerinden ARINMIŞ) kullanılarak testler orada tekrar çalıştırıldı.

## Ek bulgu (KAPSAM DIŞI — düzeltilmedi, yalnız kayıt): 12 başka önceden-var testi hatası

Tam paket koşusunda (`pytest tests/ -q`, 821 passed / 12 failed / 13 skipped / 7 collection-error,
343s) görevin kapsamındaki 2 hata dışında 12 hata daha bulundu. Yukarıdaki izolasyon yöntemiyle
(oturumun kendi temiz worktree'si) TEK TEK doğrulandı: **12'si de HEAD'de ZATEN başarısız** — ne bu
oturumun 2 düzeltmesiyle ne de öteki oturumun commit'siz `tek_film_kunye.py`/`credit_text_read.py`
değişiklikleriyle bir ilgisi yok, tamamen bağımsız/önceden-var sorunlar:

- `test_translate_payload_language.py` (2) + `test_tedial_router_lazy.py` (2): ortam eksikliği
  (`ModuleNotFoundError: No module named 'fastapi'`) — kod hatası değil, bkz proje-belleği (Tedial pilotu).
- `test_qc_c2_ocr_keep.py::test_c2_cast_cap_8` + `test_c2_cast_cap_bozuk_8_fallback`: `assert 10 == 8`
  tipi cap uyuşmazlığı — muhtemelen `credit_text_read._cast_cap`/`_llm_cast_ceiling` civarı, ayrı inceleme ister.
- `test_qc_c1_producer_strongid.py` (3 test)
- `test_credit_crew_leak_gate.py::test_raw_context_gate_drops_crew_names_only`
- `test_prod_defaults_ps1_mirror.py` (2 test)

Bu 12'si bu görevin kapsamı DIŞINDA bırakıldı (yalnız 2 hata için talimat vardı, "değişiklik yalnız
talimatla" kuralı). Ayrı bir inceleme oturumu için işaretlendi.

## Commit durumu

**Hiçbir dosya commit edilmedi.** `scripts/credit_text_read.py` ve `scripts/tek_film_kunye.py`
working tree'de değişik, `git status` ile görülebilir. `tek_film_kunye.py`'nin geri kalanı (diğer
oturumun işi) da olduğu gibi duruyor — dokunulmadı.
