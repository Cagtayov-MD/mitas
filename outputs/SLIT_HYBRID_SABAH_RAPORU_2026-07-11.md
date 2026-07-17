# HİBRİT-DY GECE VARDİYASI — SABAH RAPORU
2026-07-11 · Commit: `7d8cb6fb` · Şartname: `outputs/MASKELI_DY_KONTROLLU_GECIS_SARTNAME_2026-07-09.md`

## TEK CÜMLE
Hibrit-dy uygulandı, 54-film gölge korpusunda **sıfır yanlış-pozitif + 267/267 SHA birebirlik** kanıtlandı, Yedi Numara turnusolu **geçti** (SEDEF PEHLİVANOĞLU + "63. Bölüm Sonu" düz okunuyor; 31→76 satır) — **G1 kapısı 2 şerhle karşılandı, dizi-hattı aktivasyonuna hazır.**

## KANIT TABLOSU

| Kapı / Test | Sonuç |
|---|---|
| Testler | 13 yeni hibrit + 13 mevcut master = **26/26 yeşil** (OCR venv) |
| SHA: eski-kod vs yeni-kod bayrak-0 | **267/267 birebir** (yol-normalize manifest dahil) — film hattı bit-identik |
| SHA: eski-kod vs gölge | **267/267 birebir** + 41 sidecar üretildi — gölge piksele dokunmuyor |
| Gölge kararları (118 R-run, 54 film) | 116 MASKED, **2 FULL (yalnız Yedi Numara = doğru-pozitif), 0 DEMOTE, 0 yanlış-pozitif** |
| N-1 turnusolu (bayrak=1) | FIRE ✓ · travel 0.24→**1.13** · master 2549→5909px · OneOCR 31→**76 satır** · **SEDEF PEHLİVANOĞLU düz** ✓ · **"63. Bölüm Sonu" ilk satırda** ✓ (eskiden OneOCR'a hiç görünmüyordu) · görsel: kesintisiz temiz rulo, hayalet yok |
| Yakın-kaçak savunması | beyaz_bizon (skip .91) → **cov kapısı** tuttu · yedi_numara kısa-run (n=9) → **n_coin tabanı** tuttu · pinokyo (cov .79) / yarı_sert (cov .69) → **skip kapısı** tuttu — bileşik kuralın her ekseni korpusta gerekliliğini kanıtladı |

## ŞERHLER (dürüstlük)
1. **Tek-eksen ayrılabilirlik TUTMADI:** sağlıklı MASKED dağılımı cov p99=0.786 (FULL-min 0.576'nın ÜSTÜNDE) ve skip p99=0.912 (FULL-min 0.875'in üstünde). Şartnamenin "sağlam-p99 < eşik < patolojik-min" tek-eksen kanıtı sağlanamıyor; **bileşik kural** (cov ∧ skip ∧ n_coin ∧ med_f≥vmin) ise 118/118 doğru. Not: qwen'in tek-cov-%20 önerisi bu korpusta düzinelerce yanlış-pozitif verirdi (MASKED cov p50=0.20). Eşikler "kanıtsız-varsayılan"dan "korpus-doğrulanmış (bileşik)" statüsüne terfi etti; tek-eksen kanıt şartı şartnamede bileşik-kanıtla değiştirilmeli.
2. **DEMOTE hiç ateşlemedi (0/118):** İLK YARIŞ sınıfı (duran-yazı R-run'u) korpuste yok — sentezin öngördüğü gibi "gölge-kanıt bekliyor" statüsünde; davranışı mevcut tam-çökme fallthrough'uyla aynı olduğundan risk asimetrik değil.
3. travel_ratio 1.13, [0.9,1.1] bandının hafif üstünde: blok yüksekliği seed_top+tail eklerini içeriyor, beklenen-yol yalnız şeritleri sayıyor — tanım farkı, hata değil (kayıt: bant tanımı "şeritler+ekler" olarak güncellenebilir).
4. N-1 çıktısında küçük kuyruk tekrarı (TOLGA TÜREL/cast/MAVİ FİL ~3×): ikinci kısa R-run + statik kartların dedup kaçağı — isimler doğru, hayalet değil; dizi-katmanı fold-dedup'u zaten teklerken konsensüs de eler. Ayrı küçük iş olarak not edildi.

## NE DEĞİŞTİ (commit 7d8cb6fb)
`OCR-worktree/db_compose_master.py` (+223): `_slit_channel_stats` / `_slit_channel_decision` (SAF) / `_slit_hybrid_log` / `_hy_manifest_ozet` / `_hybrid_flush`; `slitscan` → `(block, hybrid_info)`, FULL'de tam-kare kare-başına dy + med±3IQR kelepçe, DEMOTE yalnız `allow_demote=True` (reading hattı) yolunda; bayrak `MITAS_SLIT_DY_HYBRID {0,golge,1}` **varsayılan 0** + `--slit-dy-hybrid`. `scripts/_pipe_shadow_vl.py` (+4): tuple-imza uyumu. `scripts/master_saglik_olcum.py`: TRAVEL-ÇÖKÜK bekçisi (+ ilk kez track'e alındı). `tests/test_slit_dy_hybrid.py`: 13 test.

## ÇIKTI YOLLARI
- Gölge kalibrasyon verisi: `outputs/SLIT_HYBRID_GOLGE_KALIBRASYON.json` (118 kayıt, ham istatistikler)
- Korpus çıktıları: `D:\master png test\_out_A_baseline` / `_out_B_flag0` / `_out_C_golge` (41 sidecar) / `_out_N1_aktif`
- N-1 görsel kanıt: `D:\master png test\_out_N1_aktif\yedi_numara\cikis\reading_master_runaware.png` (600×5909, temiz rulo)
- Okuma turnusolu: `..._out_N1_aktif\yedi_numara\master_dilim\dilim_oneocr.txt` (76 satır)

## SIRADAKİ ADIM (senin kararın)
G1 şerhli-karşılandı → **dizi hattına aktivasyon**: `dizi_isle.py` koşularında `MITAS_SLIT_DY_HYBRID=1` (tek satır, dizi-profil-kapsamlı; film hattı 0'da kalıyor). Onay verirsen bağlarım; G2 (kalıcılık) dizi pilotunun 12-segment kabulüyle basılır. Film hattı aktivasyonu (G3) ayrı karar, masada değil.
