# Künye Sistemi — Değişiklik Notları & Yeniden-Doğrulama (re-verify)
_Çağatay: "eklediğin/yaptığın şeyleri not alalım, ileride doğruluğunu tekrar kontrol edebilelim."_

Her satır: NE eklendi + NASIL yeniden doğrulanır (smoke). Bağımsız çalıştırılabilir. GPU gereken testler için akış worker'ını önce durdur.

## A. Okuma çekirdeği
| Değişiklik | Dosya / commit | Yeniden-doğrulama |
|---|---|---|
| Video baş+son + gemma4:26b+qwen2.5vl:7b ensemble + KB | `credit_video_read.py` / 439f7067, 2e255887 | `venvs/ocr/Scripts/python.exe scripts/credit_video_read.py --film-dir <tester/film>` → YÖNETMEN/YAPIMCI/OYUNCULAR+güven |
| production kare globu (g_/c_) | credit_video_read.py / ebf3f286 | `python -c "import credit_video_read as cv; print(len(cv.list_frames(r'Database/3/frames/giris')))"` → >0 |
| prompt-echo filtresi (_is_junk) | credit_video_read.py / ebf3f286 | `cv.split_names('X, <Producer, Yapımcı, ... yanındaki isim')` → ['X'] |
| placeholder (<NAME>/<yok>) → okunamadı | credit_video_read.py / bf470d65 | `cv.is_abstain('<NAME>')` → True |

## B. Çok-dilli rol lexicon + QC
| Değişiklik | Dosya / commit | Yeniden-doğrulama |
|---|---|---|
| Çok-dilli deterministik rol çapalama | `credit_role_lexicon.py` / 4f01a458 | `python scripts/credit_role_lexicon.py` → 5 dil doğru, alt-roller elenir |
| Teslimat QC (deterministik + qwen-VL) | `credit_qc.py` / 6ec320eb | `python scripts/credit_qc.py` → hazir/kontrol + _kontrol_kayit.xlsx + sebep dağılımı |
| XML yönetmen+oyuncu isim eşleşmesi + PDF damga | credit_qc.py / b1977259, f39e940c | XML'i olan clip'te `XML_YON_UYUMSUZ` → dağıtım kopyası PDF'ine "(!) XML" damgası |

## C. Pipeline entegrasyonu (flag MITAS_USE_VIDEO_CREDITS)
| Değişiklik | Dosya / commit | Yeniden-doğrulama |
|---|---|---|
| subprocess runner | `_pipe_credit_video.py` / ebf3f286 | `venvs/ocr/.../python.exe scripts/_pipe_credit_video.py --giris <d> --cikis <d>` → tek-satır JSON |
| _pipe_pdf --video-credits AUGMENT | `_pipe_pdf.py` / bc97d44a | `--video-credits '{"yonetmen":["ZZTEST"],...}'` → çıktıda ZZTEST; arg'sız → birebir eski |
| mitas_pipeline flag + video bloğu | `mitas_pipeline.py` / dbee3453 | flag-ON: `_DURUM.timings_sec.video_kunye` var + `credit_video_completed` olayı; flag-OFF: yok |

**ENTEGRASYON DOĞRULAMASI (4-adım smoke, hepsi geçti):** (1) list_frames 120+240 kare; (2) runner temiz JSON; (3) _pipe_pdf WITH→ZZTEST eklendi/WITHOUT→regresyon temiz; (4) flag-ON uçtan-uca video_kunye=59s+olay+Hazır, flag-OFF regresyon temiz, py_compile OK.

## D. Akış / klasör / süre
| Değişiklik | Yer | Yeniden-doğrulama |
|---|---|---|
| teslimat klasörleri | `teslimat/{export,hazir,kontrol}` | mevcut |
| süre raporu | `pipeline_timing.py` | `python scripts/pipeline_timing.py` → klip başına dk + ort/min/max |
| **teslim akışı** (export→qwen→hazır/kontrol) | `credit_export.py` | `python scripts/credit_export.py [--crosscheck] [--visual]` → teslimat/export + hazır/kontrol + Excel. Smoke: 5 clip → export 5, hazır 2/kontrol 3 |
| çöp/kısa başlık koruması (cross-check) | credit_qc.py crosscheck_check (≥4 harf) | title="3" → cross-check atlanır (yanlış-eşleşme önlenir) |

## E. Idea 2 — otonom çapraz-kontrol (Wikidata + IMDb, birinci-sınıf)
| Değişiklik | Dosya | Yeniden-doğrulama |
|---|---|---|
| Çapraz-kontrol modülü (Wikidata mitas.duckdb + IMDb imdb.duckdb) — kimlik Türkçe-başlık-önce, otoriter yön/cast, TEYİT/ÇELİŞKİ/KAYNAK_YOK, **düzeltmez raporlar** | `credit_crosscheck.py` | `python scripts/credit_crosscheck.py --baslik "AHLAT AĞACI" --yonetmen "Nuri Bilge Ceylan" --yil 2018` → TEYİT |
| Klasik gold testi | `credit_crosscheck_goldtest.py` | `python scripts/credit_crosscheck_goldtest.py` → **16/16** (14 TEYİT + 2 ÇELİŞKİ yakalama) |
| Türkçe-fold (ı→i, ğ→g…) — title-only eşleşme (İ/ı tuzağı) | credit_crosscheck.py `_tfold/_sqlfold` | "AHLAT AĞACI" (sadece Türkçe başlık) → film bulunur (öncesi: original gerekiyordu) |
| **QC'ye flag'li bağlandı** | `credit_qc.py` (`--crosscheck` / `MITAS_USE_CROSSCHECK`) | `--crosscheck` ile ÇELİŞKİ → `CROSSCHECK_CELISKI` flag + PDF damga + kontrol. Flag KAPALI (vars.)=sıfır etki (kb=None). Birim: Murat Cemir/AHLAT→flag, NBC→yok |

**Kaynaklar (kalıcı/birinci-sınıf):** Wikidata `works_master` (label_tr/director/cast_member/imdb_id) + `qid_labels` (Türkçe isim); IMDb `titles/akas/crew/principals/names`. Kimlik = Türkçe başlık (katalog no DEĞİL — Yabandan→Sergio Leone kanıtı). 300 gibi kısa başlıkta **exact-first** retrieval. Çelişki yakalama: Murat Cemir / Jean-Louis Godfroy → ÇELİŞKİ.

## Bilinen sınırlar / tunable
- cast augment OCR-önce (video cast OCR 8 doluysa eleniyor) — video-önce yapılabilir.
- mutabakat bile nadir yanılır (içerik nihai hakem; katalog/XML ~%90).
- QC `--visual` (qwen-VL) GPU testi bekliyor.
- Otonom XML/IMDb çapraz-kontrol (Idea 2) bekliyor.
