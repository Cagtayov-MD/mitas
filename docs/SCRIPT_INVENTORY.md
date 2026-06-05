# MITAS Script Envanteri

`scripts/` dizininin işlevsel kategorilere göre haritası.  
**TAŞIMA YOK** — bu belge sadece referans; runtime path bağımlılıkları kırılır.

---

## PROD — Production Runtime (doğrudan pipeline çağrısı)

`mitas_pipeline.py`'nin `subprocess.Popen` / `import` ile doğrudan çağırdığı scriptler:

| Script | Rol |
|---|---|
| `mitas_pipeline.py` | Ana pipeline orkestratörü (ASR + OCR + PDF + künye zinciri) |
| `_pipe_asr.py` | ASR alt-süreci (faster-whisper + MMS-LID + Kürtçe-atla) |
| `_pipe_ocr.py` | OCR alt-süreci (GLM consensus + stitch + clean) |
| `_pipe_pdf.py` | PDF künye üretici |
| `_pipe_credit_video.py` | Video jenerik kare okuma |
| `tek_film_kunye.py` | v4 künye final düzenleyici (KB + afiş + TÜR) |
| `_channel_lang.py` | Kanal dil tespiti (MMS-LID, `_pipe_asr` ve `_pipe_pdf` kullanır) |
| `_subtitle_detect.py` | Altyazı tespiti (`_pipe_pdf` kullanır) |
| `_kunye_classify.py` | Künye rol sınıflandırıcı (`mitas_pipeline` import eder) |
| `_kunye_qwen_check.py` | Qwen künye filtre/doğrulayıcı (`mitas_pipeline` import eder) |
| `credit_crosscheck.py` | Wikidata/IMDb çapraz-kontrol yardımcısı (`mitas_pipeline` import eder) |
| `credit_kb_lookup.py` | KB yapımcı/yönetmen dolgu (tek_film_kunye bağımlılığı) |

**OCR-worktree/pdf-mitas/ (izlenen production kodu):**

| Script | Rol |
|---|---|
| `OCR-worktree/pdf-mitas/poster_fetch.py` | TMDB/OMDb afiş çekme |
| `OCR-worktree/pdf-mitas/*.py` (diğer) | Pipeline100 zinciri (`_pipe_ocr.py` runtime yükler) |

---

## KÖPRÜ — İnternet-teyitli künye (yarı-otonom batch)

XML kimlik çapraz-kontrol + Wikipedia → altın PDF üretimi. `mitas_pipeline` dışında bağımsız koşar.

| Script | Rol |
|---|---|
| `_hile_manifest.py` | Hedef klip manifestini oluştur |
| `_hile_split.py` | Klibi parçala |
| `_hile_afis.py` | Afiş çek |
| `_hile_pdf.py` | Altın PDF üret |
| `_hile_merge.py` | Çıktıları birleştir |
| `_hile_patch.py` | Manuel düzeltme uygula |
| `_hile_separate.py` | Ayrılan kayıtları işle |
| `_hile_vapply.py` | Video-künye uygula |
| `_hile_vmove.py` | Video dosyalarını taşı/yeniden adlandır |

---

## PİLOT — 102 klasörü batch işlemleri

489 dosya → 399 benzersiz → 257 KESİN+92 SES_TEYIT akışı. Production'a geçmeden önce batch düzeltme araçları.

| Script | Rol |
|---|---|
| `_102_prep_full.py` | Tam hazırlık |
| `_102_manifest.py` | Manifest oluştur |
| `_102_render.py` / `_102_render_kesin.py` / `_102_render_sesteyit.py` / `_102_render_route.py` | Çeşitli render rotaları |
| `_102_aggregate.py` / `_102_aggregate2.py` | Sonuç birleştirme |
| `_102_merge_final.py` / `_102_merge_ozet.py` | Özet/künye birleştirme |
| `_102_ozet_prep.py` / `_102_ozet_redo.py` / `_102_ozet_split.py` / `_102_apply_ozet.py` | Özet hazırlama döngüsü |
| `_102_ses_redetect.py` / `_102_chanlang_batch.py` | Ses/kanal yeniden tespit |
| `_102_upfix_build.py` / `_102_apply_upfix.py` / `_102_apply_redo_final.py` | Düzeltme pipeline'ı |
| `_102_build_verify.py` | Doğrulama adımı |
| `_102_finalize_ozet.py` / `_102_finalize_v2.py` | Finalizasyon |
| `_102_fixset.py` / `_102_residuals.py` | Kalan sorunları gider |
| `_102_split_tr.py` | TR içerik ayırma |
| `_102_preview_kesin.py` | KESİN önizleme |
| `_102_xmlcheck_build.py` / `_102_xmlref.py` | XML referans kontrol |
| `_102_diag.py` / `_102_diag2.py` | Tanılama |
| `_102_delete_kontrol.py` / `_102_del_muzikal.py` | Temizleme |
| `_102_list_diger.py` | Diger kategorisi listele |
| `_102_addgenre.py` / `_102_afis_prefetch.py` | Genre/afiş ön yükle |

---

## DESTEK — Genel batch / raporlama araçları

Periyodik veya elle koşulan, pipeline'ın dışında yardımcı scriptler.

| Script | Rol |
|---|---|
| `gece_batch.py` | Gece toplu ASR/künye çalıştırma (resumable) |
| `gece_monitor.py` | Gece batch izleyici |
| `gece_qc.py` | Gece QC kontrol |
| `qc44.py` | QC round 44 — rapor / düzeltme |
| `refix_44.py` | 44. round düzeltme yeniden işle |
| `reset_results.py` | Re-run öncesi sonuç temizleme |
| `refetch_afis.py` | Eksik afişleri TMDB ile yeniden çek |
| `foreign_reprocess.py` | Yabancı dil tespitli filmleri yeniden işle |
| `credit_export.py` | Künye JSON çıktısı |
| `credit_qc.py` | Künye kalite kontrol raporu |
| `credit_crosscheck_goldtest.py` | Çapraz-kontrol altın test seti |
| `credit_video_batch.py` | Video jenerik toplu okuma |
| `credit_video_read.py` | Video jenerik tek okuma (VLM) |
| `credit_role_lexicon.py` | Rol sözlüğü (çok-dilli + alt-rol) |
| `run_credit_composer_batch.py` | Kredi compositor toplu koşu |
| `jenerik_tek_png.py` | Tek film jenerik PNG üretici |
| `tek_klip_child.py` | Tek klip alt-süreç |
| `asr_archive_batch_runner.py` | Arşiv ASR toplu runner |
| `ornek8_render.py` | Örnek 8 render |

---

## SCRATCH / DEV — Geliştirme ve araştırma

**`scripts/_*` gitignore kural gereği izlenmez** (`_pipe_*.py`, `_channel_lang.py`, `_subtitle_detect.py`, `_kunye_classify.py`, `_kunye_qwen_check.py` hariç).

Karakteristik prefix'ler ve örnek içerik:

| Kategori | Prefix / Pattern | Örnekler |
|---|---|---|
| Debug/analiz | `_debug_*`, `_analyze_*` | `_debug_kizgin_dedup.py`, `_analyze_debug.py` |
| Smoke/test | `_smoke_*`, `_test_*` | `_smoke_vlm.py`, `_test_glm.py`, `_test_netozet.py` |
| Inspect | `_inspect_*` | `_inspect_blob_details.py`, `_inspect_blobs.py` |
| Blur / metrik | `_blur_*` | `_blur_metric.py` |
| POC/deneme | `_panorama_ocr.py`, `_credit_sheet_composer.py`, `_fast_asr.py` | — |
| OCR harness | `_hakim_*`, `_consensus_*`, `_jenerik_*` | `_hakim_shadow_report.py`, `_consensus_poc_glm.py` |
| VLM / LLM | `_vlm_*`, `_llm_*` | `_vlm_credits.py`, `_vlm_router.py`, `_llm_eye_discriminate.py` |
| Scan / probe | `_scan_*`, `_probe_*`, `_goz_*` | `_scan_scroll_darkratio.py`, `_probe_textmotion.py` |
| Diğer util | `_save_frame.py`, `_frames_to_png.py`, `_rst.py`, `_ptd.py` | — |
| Kunye test | `_kunye_test_db.py`, `_v4_render_one.py`, `_v4_ornek_yabanci.json` | — |
| Credit composer | `_prototype_credits_*`, `_static_cards_*`, `_master_from_region.py` | — |

**Uyarı:** `_fast_asr.py` özet→ASR tek-pass profilini barındırır; silinmeden önce kontrol et.

---

## İzleme özeti

| Kategori | Sayım (yaklaşık) | Git durumu |
|---|---|---|
| PROD (pipeline runtime) | 12 script + pdf-mitas/*.py | İzleniyor (.gitignore istisnası) |
| KÖPRÜ | 9 script | İzleniyor (scripts/ istisnasız) |
| PİLOT (_102_*) | ~30 script | İzleniyor |
| DESTEK (batch/QC) | ~25 script | İzleniyor |
| SCRATCH/DEV (_*) | ~60+ script | **Yoksayılıyor** (scripts/_* kuralı) |
