# KONSEY ŞARTNAMESİ — KONTROL-Kuyruğu Sağlıklılaştırma (2026-07-10)

> Kaynak süreç: ChatGPT dış-denetimi (10 iddia → 11-ajanlı adversarial doğrulama: 8 CONFIRMED / 1 PARTIAL / 1 REFUTED→sonradan DÜZELTİLDİ) → tasarım danışması (qwen, bağımsız Opus, 4-üyeli Opus konseyi wf_f0e3c5f2-19a, GPT 3-tur) → GPT tur-2 6-iddia doğrulaması (4C/2P) → GPT tur-3 6-kod-iddiası doğrulaması (6/6 CONFIRMED) → rev.3 delta-onayı (qwen TAM, GLM 3-koşullu → koşullar kapatıldı).
> Onaylı uygulama planı: `C:\Users\TRT03\.claude\plans\giggly-dazzling-moler.md` (rev. 4, Çağatay onayı 2026-07-10).

## PUSULA (hedef metrikler)
- Sessiz teknik-arıza = 0
- İçerik-KONTROL diye yanlış sınıflanmış teknik-arıza = 0
- Çözülmemiş RETRYABLE_FAILURE backlog = 0
- İnsan kapısını atlayan onay = 0
- %78→%55 HEDEF DEĞİL (MESRU_BOS dolu kalabilir); içerik-doğruluğunun statik %0-hata garantisi yok — garanti insan-kapısının atlanmamasıdır.

## KONSEY KARARLARI (eksen-eksen, tek hüküm)

**Q1 Sıralama:** minimal write-side sözleşme → candidate-write/izolasyon → SONRA kitlesel re-run → EN SON tam türetme. Gerekçe: P12+P7 aktif veri kaybı (FUTBOLCU PRENSES); izolasyonsuz re-run yasak. (Opus sırası kazandı; qwen'in "tam-sözleşme-önce"si big-bang riskiyle reddedildi.)

**Q2 Mimari:** AYRI decision_engine.py modülü RED (paralel-oturum merge riski); mevcut `classify()`/`from_durum()` adaptörü tek türeticiye büyütülür, strangler'la. Otorite geçişe kadar `_DURUM.json`'da; `karar.pipeline.json` gölge-yazım (tek-yazıcı: `_DURUM`'u üreten AYNI çağrı) + drift-alarmı.

**Q3 Depolama:** İç-içe `Database/<film>/runs/<id>` RED (≥14 tek-seviye tüketici kırılır — kanıtlı). AYRI KÖK: `candidate/<run_id>/{Database,export,reports,events,manifests}` = `--run-root` sözleşmesi (`--db-root` yetmez: 7 üretim yazma-yüzeyi kanıtlı; kökler mitas_pipeline.py L35-49 hardcode, override yok). İzolasyon kanıtı: üretim köklerinde hash/mtime diff=0 otomatik testi.

**Q3b Promotion:** crash-recoverable TRANSACTION — journal-önce-yaz, adım-işaretli, `os.replace`+üstel-backoff+handle-kapatma, canonical→`archive/<old_run_id>`, candidate→TAM canonical ad, startup-recovery yarım-swap'ı geri sarar, crash-injection testleri. `" (n)"` ekli ikinci aktif hub ASLA (duplicate, `_find_processed_hub`'ı yanıltır — ADI CARMEN ×3 canlı örnek). Mutlak-yol rebase. Resolver: 0=NOT_FOUND / 1=OK / >1=AMBIGUOUS_HUB hard-fail. Ön-kontrol: expected_run_id+input-hash+parent-run. Dedup kuralı: kanonik seçim timestamp'le DEĞİL alan-bazlı içerik çapraz-kontrolü + content-hash raporu; seçim Çağatay'ın; seçilmeyen arşive. Demote zorunlu; promotion MANUEL.

**Q4 Stokastiklik:** ollama options'a `seed` (kanıt: hiç set edilmiyordu; temp=0 kanıtı DeepSeek yolundandı) + `num_predict` + `prompt_eval_count`/`eval_count` telemetrisi. Asıl kalkan: candidate non-destructive + alan-otoritesi kuralı (düşük-kanıtlı otomasyon yüksek-kanıtlı/insan alanını düşüremez; bilinçli kaldırma `operation=REMOVE, reason_code, approved_by`). N-geçiş konsensüs yalnız flip-tespit alanlara. `top_p:0` RED.

**Q5 Context:** `_reasoning` KALDIRILIR (şemada required-İLK, yaptırımsız, ~90-satır üretim + taşma kod-yorumuyla belgeli) — ama ÖNCE shadow-A/B (hedef-cohort, üretim kirletilmez, rollback-eşiği manifest'e sabit). Runtime hard-cap (token+wall-clock) kalır. Sabit 16384 RED (VRAM). Length'te fallback yalnız mantıksal kart-sınırından tek-retry; `done_reason=length` → HATA + CONTEXT_OVERFLOW (sessiz `{}` yasak).

**Q5b extraction_status zinciri:** `OK | ABSTAIN | TECHNICAL_FAILURE` uçtan-uca (4 yutma noktası kanıtlı: _ollama_json:733 → read_credits_auto:2158/2288 → _pipe_credit_text exit-0 → mitas_pipeline:2433 last_json). Precedence: geçerli-boş=ABSTAIN · length/timeout/HTTP/invalid-JSON=TECHNICAL_FAILURE · çok-model aggregate tanımlı · rescue teknik-hatayı maskelemez · romanizasyon-fallback=DEGRADED. DEFERANS korunur ama yalnız OK/ABSTAIN'de; TECHNICAL_FAILURE'da mekanik silinmez + teslim yok + TECH_RETRY.

**Q6 MESRU_BOS:** alan-düzeyi (168 bulgu=105 film, 14 çift-sınıf, (trt,field) tekil — kanıtlı), 6 durum: SOURCE_ABSENT / ROLE_ABSENT / SOURCE_UNREADABLE / OCR_MISSED_VISIBLE_TEXT(→TEKNIK_ARIZA) / EVIDENCE_INSUFFICIENT–FRAME_COVERAGE_GAP (kanıt-kaynağı=frame-örnekleme ölçümü; external cast-list YASAK) / NOT_APPLICABLE. VL çift-tanık alan-bağlamlı; C_OKUNAMAZ otomatik TEKNIK_ARIZA değil. Mühür: `field+source_hash+evidence_hash+gate_version+approved_by`; yeni kanıtta geçersiz; insan-onaylı terminal. 168 vaka grandfather'sız; VL maliyeti önce ölçülür.

**Q7 Manuel-loop birlikte-yaşam:** `karar.pipeline.json` (makine) / `karar.human.json` (insan) / `karar.view.json` (türetilmiş, her yazımda atomik regenerate) FİZİKSEL ayrık; human-lock'lu filme otomasyon dokunmaz; provenance=human immutable.

**AUTOFIX:** executor İNŞA EDİLMEZ; tier silinmez → `NEEDS_REVIEW_HAFIF` yeniden-adlandırma (davranış-nötr) + 7 hafif kodun (AFIS, CASING, GENRE, KEYWORD, OZET_STIL, YAP_FILL, CAST_CAP_DUSEN) geçiş tablosu. (Kanıt: dal silinirse hafif-only filmler sessizce TEMIZ'e düşer.)

**Retry:** SIRA kritik — önce worker force-rmtree (asr_server.py:809-814, gerçek hub'ı siler) kaldırılır, SONRA `{retry_stage: OCR|ASR|SUMMARY|RENDER|FULL, hub_id: canonical, delete_existing: false, candidate_run: zorunlu}`. `:2051` yalnız-ASR; OCR-stage runner İNŞA edilir; `ocr_rerun_35film.py` yalnız komut örneği (timeout'ta ok=True + canonical clip.json yedeksiz mutasyonu kanıtlı). Invalidation DAG (bayat-işaretle, lazy) + node-başına circuit-breaker (maks 3 → DLQ). DLQ TTL→otomatik KARANTİNA (temizlik insan-onaylı); zombie-timeout profil-bazlı.

**Kirli-ağaç:** dirty iki-mod — tek-film geliştirme serbest (patch-hash manifest'e); batch/promotion temiz-commit ZORUNLU, `--allow-dirty` istisnası YOK. Kod-snapshot koşu-öncesi (torn-snapshot yasak); yazıcı-duraklatma graceful. Worktree DEĞİL (Çağatay tercihi): commit + duraklatma + run-root'a kopya.

**Kabul kriterleri:** hedef-cohort'ta yalnız insan-onaylı fark · negatif-cohort'ta açıklanamayan fark=0 (normalize-diff; karantina bandı; trivial-noise bloklamaz) · min hacim · promotion crash/recovery · duplicate-TRT · retry-idempotency · candidate side-effect=0 · Database/export/UI mutabakatı · golden 7×3 yalnız smoke · unit/integration/live/golden AYRI · 470-corpus golden-truth öncesi şema+etiket temizliği.

## DOĞRULANMIŞ KOD-GERÇEKLERİ (satır referanslı, 2026-07-10)

1. AUTOFIX ölü-etiket: credit_severity_router.py:150 (folder=KONTROL kendisi yazar); HAFIF_FIX yalnız açıklama tablosu; docstring :11/:15 bayat ("kontrole gitmez").
2. DEFERANS: _pipe_pdf.py:265; MITAS_CREDIT_DEFERENCE default=1; bilinçli tasarım (2026-06-28), dar risk penceresi.
3. num_ctx=8192 sabit: credit_text_read.py:585/:620; done_reason=length→{} (:624/:654); 4dff40b7 yalnız stderr; `_reasoning` şemada required-İLK (:581), prompt'ta ilk; seed/top_p/num_predict YOK; prompt_eval_count okunmuyor.
4. /retry: asr_server.py:1056; rmtree sanitize-mismatch (gerçek hub'ı ıskalar); force'suz requeue → reused-skip (:806-830) sessiz no-op; force=true yolu (:809-814) GERÇEK hub'ı rmtree'ler; :2051 yalnız-ASR reprocess; OCR endpoint YOK; watchdog oto-retry fiilen işlevsiz.
5. _DURUM çelişkisi: 286 dosyada 11 (5 karar=Kontrol&tier=TEMIZ; 6 karar=Hazır&tier=KONTROL); fiziksel export daha da sapmış.
6. Hata-yutma zinciri: _pipe_credit_text.py:76-129 her istisnada aynı-şema JSON+exit 0; mitas_pipeline.py:2433 last_json; "hata" alanı okunmuyor.
7. Yazma yüzeyleri: mitas_pipeline.py L35-49 kökler hardcode; kök-override YOK; Database dışı 7 yüzey (export :3317, özel-tür :3292, master-log :3383+, Excel :3328, event :110-121, api_status.json, web-cache).
8. classify()/from_durum(): karar() fonksiyonu yok; from_durum() 14 Türkçe substring; AUTOFIX dalı silinirse hafif→TEMIZ düşer (:153-154).
9. Mutlak-yol: hub JSON'ları mutlak-yol dolu; 2026-06-14'te 430-klasör rename koşmuş; rebase yok; /api/jobs/{id}/pdf bayat-yol 404 riski.
10. _find_processed_hub (:609-631): ilk-eşleşme; AMBIGUOUS dalı yok; ADI CARMEN 1983-0256 ×3 canlı.
11. 117/36 canlı-veriden birebir üretilebilir: 185 KONTROL-TRT → 168 _DURUM-eşleşmeli → GUVENILIR=117; karar=Kontrol & qwen_qc{yonetmen_var, oyuncu≥2, ozet_var} = 36 ("temel-alan-dolu-ama-hard-gate-bloke" triaj adayları; "içerik-hazır" DEĞİL).
12. 168 meşru-boş bulgusu = 105 benzersiz film, 14 çift-sınıf; alan-düzeyi tekil.
13. ocr_rerun_35film.py: timeout'ta ok=True (:90-93) + canonical clip.json yedeksiz mutasyon (:59/:68); yalnız komut örneği.
14. Sayılar hareketli: OCR-partial 35→5 (30 done, 2026-07-10 re-run); ASR-failed 47-48 (payda-bağımlı); kirli ağaç ölçüm-anına bağlı.

## GLM KOŞULLARI (kapatıldı) + qwen UÇ-DURUMLARI (işlendi)
- GLM-a: ADI CARMEN dedup kuralı → alan-çapraz-kontrol + content-hash, Çağatay seçer, arşive. ✔
- GLM-b: _reasoning shadow-A/B önce + runtime hard-cap. ✔
- GLM-c: backup-before-mutate (clip.json dahil). ✔
- qwen: os.replace backoff+handle-kapatma ✔ · DAG circuit-breaker (maks3→DLQ) ✔ · A/B rollback-eşiği manifest'e ✔
- Diğer: DLQ TTL→karantina (rapor değil enforcement) ✔ · zombie-timeout profil-bazlı ✔ · DuckDB telemetri schema_version ✔ · view.json atomik regenerate ✔ · FRAME_COVERAGE_GAP kanıt-kaynağı ✔ · web-cache MITAS_WEB_CACHE_DIR ✔ · negatif-cohort normalize-diff+karantina-bandı ✔ · snapshot koşu-öncesi + graceful pause ✔ · legacy lazy-migration ✔

## İŞ PAKETLERİ
İP-0 Hazırlık → İP-1 manifest+preflight+dirty → İP-2 extraction_status → İP-3 context-hijyen → İP-4 karar-gölge+classify+NEEDS_REVIEW_HAFIF → İP-5 RUN_ROOT → İP-6 promotion/demote → İP-7 retry → İP-8 toplu-kurtarma+36-triaj → İP-9 MESRU_BOS+cohort (AYRI ONAY). Detay: plan dosyası rev. 4.
