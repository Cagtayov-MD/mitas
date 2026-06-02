# OCR 10 Film Gerçek Test Ara Raporu

Tarih: 2026-05-22

## Durum

- Output: `E:\MITAS\outputs\ocr_credit_experiments\filmtest_10_last3min_candidate_selector_20260522`
- Engine: paddle, oneocr
- Tamamlanan: 5/10
- Failed: 0
- Completed at: None

## Claude/tools Katkısı Bu Koşuda Nerede?

Bu koşu sadece eski OCR hattı değil; Claude/tools incelemesinden gelen güvenli parçaları da içeriyor:

- `dark_ratio` static gate: film sahnesi üstündeki sabit overlay yazıların statik jenerik sanılmasını azaltıyor.
- Kontrollü dark-frame filter: row reconstruction öncesi çok açık/sahne ağırlıklı kareleri şartlar uygunsa dışarıda bırakıyor.
- `quality_score` / `quality_warning`: üretilen row composite kullanılabilir mi diye skor üretiyor.
- `cruise_speed_ema`: ana algoritma değil; candidate selector içinde alternatif aday olarak deneniyor.

Claude/tools tarafından önerilen `cruise_speed_ema` doğrudan ana hatta alınmadı; daha önce 18 film testinde çıktıyı düşürdüğü için bu koşuda sadece aday olarak yarıştırılıyor.

## Tamamlanan Filmler

| # | Film | Status | Frames | Frame OCR | Stable | Canvas | ROI | Scene | Row selected | Row count | Quality | Claude/tools etkisi |
| ---: | --- | --- | ---: | ---: | ---: | ---: | --- | --- | --- | ---: | ---: | --- |
| 1 | filmtest_01_evoArcadmin_COZUMLEMEV2S17_1925-0009-1-0000-00-1-SON_ADAM | done | 1080 | 4652 | 190 | 0 | auto | moving_scene/static_card | current_displacement | 14 | 0.68 | dark_gate+quality_score+candidate_selector+cruise_candidate |
| 2 | filmtest_02_evoArcadmin_COZUMLEMEV2S17_1988-0375-1-0000-00-1-KONTES_MARIZA | done | 1080 | 2642 | 160 | 46 | auto | moving_scene/static_card | cruise_speed_ema | 5 | 0.666 | dark_gate+quality_score+candidate_selector+cruise_candidate |
| 3 | filmtest_03_evoArcadmin_COZUMLEMEV2S17_1991-0339-1-0000-01-1-K-2 | done | 1080 | 25009 | 1930 | 231 | auto_refined | moving_scene/vertical_scroll | current_displacement | 21 | 1.0 | dark_gate+quality_score+candidate_selector+cruise_candidate |
| 4 | filmtest_04_evoArcadmin_COZUMLEMEV2S17_1991-0377-1-0000-00-1-SİYAH_KADİFE_ELBİSE | done | 1080 | 13819 | 508 | 80 | auto | camera_motion/vertical_scroll | static_best_frame | 7 | 1.0 | dark_gate+quality_score+candidate_selector+cruise_candidate |
| 5 | filmtest_05_evoArcadmin_SİNEMA_FİLM_1950-2118-1-0000-90-1-GÜN_BATISI | done | 1080 | 373 | 13 | 0 | auto | moving_scene/static_card | current_displacement | 5 | 0.8 | dark_gate+quality_score+candidate_selector+cruise_candidate |
| 6 | filmtest_06_evoArcadmin_SİNEMA_FİLM_1990-0325-1-0000-90-1-BABA_3 | running |  |  |  |  |  |  |  |  |  |  |

## Not

Bu ara rapordur. Batch tamamlanınca her film için PNG yolları, OCR son metinleri ve candidate skorları ayrı ayrı genişletilecek.
