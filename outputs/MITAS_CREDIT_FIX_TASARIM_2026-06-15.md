# MITAS Künye-Fix Tasarımı — kök-neden DÜZELTİLDİ + cerrahi plan
_2026-06-15 · forensic + kod-izleme sonrası · UYGULAMA YOK, önce onay_

## 0. ÖNEMLİ DÜZELTME — suçlu qwen DEĞİL, `parse_credits`

Forensic rapor `.txt` yüzeyini ölçtü ve "qwen %64" dedi. Kodu uçtan uca izleyince **modül-atfı yanlış çıktı** (kanıtla düzeltiyorum):

**Production zinciri (film/dizi):**
```
OneOCR → kunye.txt
   ├─(A) qwen3.6:35b (credit_text_read)  → video_credits  → v4 (tek_film_kunye) → kunye.pdf   [TEMİZ]
   └─(B) _pipe_pdf.py:249 parse_credits(raw)  →  kunye_teslim.md  → surface → .txt            [KİRLİ]
                         + qwen "AUGMENT" (REPLACE değil) + role_reconcile
```

**Kanıt (log'dan, qwen gerçekte ne döndürdü vs .txt):**

| Film | qwen (A) — TEMİZ | .txt (B, parse_credits) — KİRLİ |
|---|---|---|
| KORKUNÇ ŞÜPHE | `CLAUDE MILLER, JEAN HERMAN` | + TOUS DROİTS RÉSERVÉS, PELLİCULE KODAK, PELLİCULE SON PYRAL |
| HAYDUT | `BARRY LEVINSON` | + PRADESTİAS MANAGET, **FİRET AZTİSTANT DİRSETAR** (=1st assistant dir garble), HARLEY PEYTON |
| AZRAİL | `ALEXANDER FRIEDRICH` | + CELLULOİD DREAMS, GAMEH PANAL |

**İki sonuç:**
1. **qwen aslında temiz okuyor.** Çöpü ekleyen **`parse_credits` (deterministik)**.
2. **DIVERGENCE:** teslim PDF'i (v4/qwen) ≈ temiz; `.txt`/`_teknik.txt` (parse_credits) kirli. İki yüzey **aynı filmde farklı künye** gösteriyor. (v4 PDF finalize=True teyitli.)

## 1. parse_credits'te çöp NEDEN doğuyor (mekanizma, credit_parse.py)

1. **Same-line etiket+isim yutulması** — `role_of("UN FILM DE NICOLAS VANIER")` tüm satırı "Yönetmen ETİKETİ" sayar, **isim VANIER düşer** (kod satır 161-165). Gerçek yönetmen kaybolur → S2_ROLE_UNMATCHED.
2. **Sonraki-satır sızması** — etiketten sonra `cur="Yönetmen"`, takip eden kişi-satırları `cap=3`'e kadar Yönetmen'e dolar (satır 234-236). Yabancı filmde temiz CAST başlığı yoksa oyuncular yönetmene akar → S2_ROLE_OVERREACH.
3. **Disclaimer/garble rol-etiketi geçişi** — `is_person()` yalnız harf-oranı + şirket-kelime + rakam bakar (satır 175-190). "tous droits réservés", "pellicule kodak", garble "FİRET AZTİSTANT DİRSETAR" → is_person=True → role'a/cast'e sızar.
4. **Garble şirket** — `is_company` `_CORP_KW` exact arar; garble "DMODON GLOBAL INO" eşleşmez → cast'e sızar (S4_NOISE GARBLE=111).

qwen tarafı (credit_text_read) bunları ZATEN çözmüş: `_JUNK_WORDS`, `_valid_person_name`, `_looks_garble`, token-anti-halüsinasyon. **Bu mantık parse_credits'te YOK.**

## 2. TASARIM — iki additive, flag-korumalı katman (var olanı EKSİLTMEDEN)

> İlke: flag KAPALI iken davranış **byte-aynı** (mevcut sistem dokunulmaz). AÇIK iken yalnız çöp elenir / temiz kaynak tercih edilir. OCR-otorite korunur (her iki kaynak da OCR-türevi; uydurma yok). Mevcut MITAS_FUZZY_DBQC / MITAS_QC2 kalıbı.

### FIX-1 (BİRİNCİL, düşük risk) — `parse_credits` çöp-sertleştirme  ·  flag `MITAS_CREDIT_PARSE_V2`
credit_text_read'deki kanıtlanmış süzgeçleri credit_parse'e taşı (kod kopyası değil, ortak küçük modül):
- **Same-line etiket→isim çıkarımı:** "UN FILM DE / DIRECTED BY / A FILM BY <İSİM>" satırında etiketten sonraki ismi role AT (düşürme); böylece (a) gerçek yönetmen kurtulur, (b) `cur` dolduğundan sonraki-satır sızması durur.
- **Junk/disclaimer/rol-etiketi sözlüğü** (`_JUNK_WORDS` + çok-dilli disclaimer: tous droits, pellicule, all rights, copyright, avec la participation, with the participation, courtesy of…) → `is_person`/`role-fill` RED.
- **Yüksek-isabet garble rol-etiketi** (`_looks_garble`: "FİRET AZTİSTANT DİRSETAR"~"first assistant director", fiil-eki, rol-token) → RED. **SADECE yüksek-isabet** (memory dersi: naif garble gerçek-isim düşürür).
- **Bleed cap:** crew rol-fill'i etiket-satırı + en fazla 1 takip satırıyla sınırla, kişi-olmayan/boş satırda DUR (cap=3→akış kesilir).
- Risk: ORTA-DÜŞÜK (yalnız yüksek-isabet eleme). Recall korunur (gerçek isim düşmez).

### FIX-2 (OPSİYONEL, divergence'ı kapatır) — `.txt`'yi temiz kaynağa hizala  ·  flag `MITAS_CREDIT_PREFER_TEXT`
`_pipe_pdf.py`'de qwen video_credits GÜVENLİ (yön dolu + guven≥ORTA) ise o alanı **AUGMENT yerine BİRİNCİL** yap (parse_credits o alanda yedek). Sonuç: `.txt` == teslim PDF'i (tutarlılık), overreach/çöp kaynağı baştan devre dışı.
- Risk: DÜŞÜK (qwen çıktısı zaten token-doğrulanmış+garble-kapılı). Nadiren qwen daha az-merkezi ama TEMİZ isim seçebilir (Paronnaud↔Friedrich). Flag-kapalı=mevcut davranış.

### Kapsam dışı (ayrı iş, bu fix'e karıştırma)
- **GARBLE saf isim (111)** ve **CHARACTER (65):** sözlükle yakalanmaz; ayrı (DB-fuzzy / bağlam) gerekir.
- **CJK/Kiril etiket (S6):** transliterasyon gerekir, ayrı.
- **QC garble-gate körlüğü (25 film):** üst-akış, ayrı fix (garble_frac script-aware).

## 3. DOĞRULAMA PLANI (uygulamadan ÖNCE kanıt)
1. `parse_credits`'in mevcut hali + FIX-1'li hali için **149-film harness** (OCR kunye.txt'ten yeniden parse — GPU YOK, deterministik, saniyeler).
2. Her film için before/after yönetmen+yapımcı+cast diff; metrik: **çöp-token düşüşü** (disclaimer/role-label/company) vs **gerçek-isim kaybı (regresyon=0 hedef)**.
3. **40 CLEAN film** kontrol: değişmemeli (flag-off=aynı; flag-on=regresyon yok).
4. Tablo + örnek diff'ler → onayına sun → sonra production flag aç.

## 4. ÖZET
- Kök neden **parse_credits** (deterministik), qwen değil. qwen temiz; `_pipe_pdf` onu yalnız augment'liyor, parse_credits çöpü hakim.
- Fix: **FIX-1 (parse_credits sertleştir, flag)** ± **FIX-2 (.txt'yi qwen'e hizala, flag)**. İkisi de additive, flag-off=dokunulmaz.
- Önce 149-film deterministik harness ile before/after kanıtı, sonra production.
