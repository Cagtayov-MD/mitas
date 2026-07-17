# Film #31 — KEDİ GÖZÜ (Eye of the Cat, 1969) FORENSİK
## OCR-otorite kanunu ihlali — yanlış ONAYLI/AutoFix vakası
2026-06-22 · SALT-OKUNUR · kanıt: `Database/KEDİ GÖZÜ 1969-0057-1-0000-00-1/`

## Gözlenen kusur
- **ELEANOR PARKER** (ham OCR'da 6× okundu) → final'de **YOK** (okunanı-çıkar).
- **MICHAEL SARRAZIN** (ham OCR'da **0×**) → final'e **EKLENDİ** (okunmayanı-ekle = saf KB-ikamesi).
- **GAYLE HUNNICUTT** (ham OCR'da 3× okundu) → önce düştü, sonra KB ile geri eklendi.
- Yapımcı: **PHILLIP HAZELTON** (OCR 9×) + **PHILLIP HAZLETON** (OCR 0×, uydurma yazım) → çift-kayıt.
- Karar = **AutoFix** (route AUTOFIX, tek "hafif" bulgu CASING) → **KONTROL'e GİTMEDİ**. OCR-otorite çiğnenmiş ama "temiz" muamelesi gördü.

## Olay sırası (log + artefakt kanıtı)
| Saat | Aşama | Cast | Not |
|---|---|---|---|
| 03:21 | OCR (ham) | — | ham: HUNNICUTT 3× + ELEANOR PARKER 6× (üstte açılış yıldız kartları) + 6 yardımcı |
| 03:22 | credit_text | **6** | PARKER + HUNNICUTT burada düştü (sadece 2-token yardımcılar kaldı) |
| 03:23 | pdf | **6** | erken md/PDF: 6 oyuncu, tek HAZELTON |
| 03:26 | **v4_finalize (138 sn)** | **8** | SARRAZIN + HUNNICUTT eklendi, HAZLETON-double doğdu |
| 03:26 | qwen_final_qc | — | hepsi-iyi → AutoFix |

## 4 SUÇLU (zincir — her biri kod-satırıyla doğrulandı)

### ① YUKARI-AKIŞ RECALL KAYBI — `OCR-worktree/py/20260601_clean.py:61` (KÖK ÖN-KOŞUL)
```python
if n == 1: return "frag"   # tek-kelime satır kredi olamaz (isimler >=2 kelime)
```
`clean()` yalnız `buckets["credit"]`'i döndürür (`:108-114`); `frag` bucket'ı asla `merged`'e girmez. Açılış yıldız kartlarında ad ve soyad AYRI satırlarda (tek-token): `GAYLE` / `HUNNICUTT` / `ELEANOR` / `PARKER` → hepsi `n==1` → `frag` → ATILIR. Yardımcılar (`TIM HENRY`, `LAURENCE NAISMITH` …) 2-token → kalır. **"Başroller düşer, yardımcılar kalır" deseninin tam nedeni.** Yorumun varsayımı ("isimler ≥2 kelime") arşiv açılış jeneriği için YANLIŞ. Kanıt: isimler `ocr_raw_all.txt` (1-18) ve `ocr_ham.txt` (1-4) içinde VAR, ama `kunye.txt` (clean sonrası) içinde YOK. `_pipe_ocr.py:494` clean'i çağırır. kb_suffix_split kurtarması (`:507`) çıplak "PARKER"ı kurtarmaz (KARAKTER+OYUNCU bitişik arar, KB-gated).

### ② KB-İKAME + 8-CAP — `scripts/credit_qc_block.py:562-572` + `FILL_TARGET=8` (`:369`)
```python
# S7: MIN-OYUNCU FLOOR DOLDURMA (yalnız kilitli; OCR'dan SONRA ekle)
if locked and otoriter_cast:
    have = {_fold(n) for n in cast}
    for a in otoriter_cast:                 # IMDb fatura/billing sırası
        if len(cast) >= FILL_TARGET: break  # = 8
        if _fold(a) not in have and not any(cc.name_match(a, o) for o in cast):
            cast.append(a)                  # OCR'da OLMAYAN ismi ekle
cast = cast[:FILL_TARGET]                   # = 8
```
Giren cast = 6 (① yüzünden eksik). `locked=True` (`:469` cast_ov≥2/fuzzy_ov≥2/TEYİT). `otoriter_cast` = IMDb principals `ORDER BY ordering LIMIT 10`[:8] (credit_crosscheck.py:447,590) → billing-başı **[SARRAZIN(1.), HUNNICUTT(2.), PARKER(3.), …]**. Döngü: Sarrazin ekle→7, Hunnicutt ekle→8 → `len≥8` **BREAK** → **PARKER (3.) hiç sıraya gelmedi**. Sarrazin (0× OCR) içeri, Parker (6× OCR) dışarı. Floor-fill, Parker'ın yukarıda OCR'da okunmuş olduğundan **habersiz** — KB billing'i mutlak doğru sayıyor. (`MITAS_KB_CAST_ADD` default AÇIK; `tek_film_kunye.py:452-465` ikincil yol da aynı.)

### ③ CREW ÇİFT-KAYIT — `scripts/credit_qc_block.py:581-593` (S8, strict-only dedup)
Yapımcı KB-tamamla; dedup yalnız `_fold` birebir-eşitlik + strict `cc.name_match` (son-token TAM eşit şartı, credit_crosscheck.py:52-78). `HAZELTON` vs `HAZLETON` tek transpozisyon (Lev=2) → name_match=False, fold≠ → KB varyantı **ayrı kayıt** olarak eklenir. Sistemin elindeki `name_close`/`name_close_window` (credit_crosscheck.py:158-208, eşik 0.80) bu çifti **birleştirirdi** ama bu dedup noktasında HİÇ çağrılmıyor. (Karşılaştırma: kb_suffix_split.py:23-39 fuzzy-dedup paterni projede VAR, buraya uygulanmamış.)

### ④ ROUTE KÖRLÜĞÜ (yanlış ONAYLI) — `scripts/credit_severity_router.py:91-117` + PROPAGATION KESİNTİSİ
AĞIR (→KONTROL) sinyal listesinde **şunların HİÇBİRİ yok**: (a) OCR-okunan ismin düşmesi (cast-shrink), (b) KB-floor-ekleme izi, (c) fuzzy çift-kayıt. İhlalin ham kanıtı qc_block'ta **üretiliyor** (`credit_qc_block.py:571` `kb-floor-doldur` iz, `:665` `ocr_cast_k`, `:667` `otoriter_cast`) ama:
- **Bariyer 1:** `tek_film_kunye.py:725-730` `rapor["v4"]`'e yalnız karar/tip/gerekceler/floor kopyalar — `kaynak_izi`/`ocr_cast_k` **düşürülür**.
- **Bariyer 2:** `mitas_pipeline.py:2090-2104` yalnız `v4.qc_block_*` okur, `adimlar.qc_block.kaynak_izi`'ye **hiç bakmaz** (grep: pipeline'da `kaynak_izi`/`ocr_cast_k` referansı SIFIR).

Sonuç: ihlal route'a hiç ulaşmaz → geriye tek "hafif" CASING kalır → AutoFix. `qwen_final_qc` (_kunye_qwen_check.py:14-31) yalnız PDF-pikseli üzerinde **yapısal sayım** yapar (oyuncu_var/yapimci_var/hepsi_buyuk_harf), ground-truth'a erişimi YOK → Sarrazin-eklendi/Parker-düştü/Hazleton-double'ı yapısal olarak göremez.

## Sentez
Tek başına ① (recall kaybı) → KONTROL'e gitse kurtarılabilirdi. Ama ① cast'i 6'ya düşürünce ② floor-fill'i tetikledi; ② KB billing'i mutlak sayıp 8-cap'le Parker'ı (OCR'da okunmuş) keser ve Sarrazin'i (OCR'da yok) içeri alır = **tam "Ahmet okuyup Mehmet yazma"**; ③ aynı KB-tamamla yolu crew'de çift-kayıt; ④ ihlal sinyali kodda üretiliyor ama route'a propagate edilmediği için "temiz/ONAYLI" damgası. Bu, memory'deki H5 (8-cap), başrol-kaybı ve **PROPAGATION** (qc_block kanıtı router'a ulaşmıyor — [[project_son250_forensik_20260620]], [[project_ocr_qc1_denetim_20260620]]) köklerinin TEK vakada birleşik kanıtı.

## Onarım yönü (UYGULANMADI — yalnız öneri)
1. **①** `clean.py:61` frag-kapısını kaldırma yerine: ardışık tek-token satırları KB/komşuluk ile isim-yeniden-birleştir (büyük yıldız-kartı paterni), VEYA frag'leri kb_exact ile kurtar.
2. **②** floor-fill'i "OCR-okunan ama düşen isim varsa onları ÖNCE geri al, sonra billing-doldur" yap; 8-cap'i OCR-okunanları korumak için esnet.
3. **③** S8 (ve cast dedup) `name_close`/`name_close_window` fuzzy-dedup ekle.
4. **④** qc_block'ta cast-shrink/floor-add/fuzzy-dup → AĞIR sinyal üret; `kaynak_izi`/`ocr_cast_k`'yı `v4` bloğundan router'a propagate et.
