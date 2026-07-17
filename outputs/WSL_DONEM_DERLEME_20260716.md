# WSL2 Dönemi (13-16 Temmuz 2026) — Tam Derleme ve Bugüne Aktarım

> Kaynaklar: KONUSMA_TAM_20260713-16.md (24.934 satır, eksiksiz okundu) + linux_backup_wsl2_20260714
> (kod_fixleri/harness/hafıza/raporlar) + oturum JSONL arşivi. 6 Sonnet ajanı, çapraz-doğrulamalı.
> Derleme tarihi: 2026-07-16, bare-metal Ubuntu (bu belge /opt/mitas/outputs altında yaşar).

## 1. Ne yapıldı (kronolojik özet)
- 51 film (D:\filmtest\aaaa) WSL-MITAS ile 3-aşamalı koşuya sokuldu: (1) nezih havuz
  (son 10dk+ilk 4dk @1.5fps + jenerik-başı tespiti), (2) master PNG, (3) dilim + VL bench.
- Gece tam-otonom koşu: Stage-1 51/51 (45 pass), Stage-2 30/51 master, VL bench başladı.
  Gecenin iki kalıcı fixi: **num_ctx=16384** (~8× hız) ve **deepseek "Free OCR." prompt-style**.
- **KKF protokolü doğdu** (katman-katman, gözle doğrula, genelleştirilebilir fix; 200'lük koşu tetiği).
- Aşama-1 KKF döngüsü: footage-baş trim (33/51), giriş trailing-trim (27/51, 6.381 kare),
  kuyruk-footage sınıfı (ATTİLA/MAKSİM/PİNOKYO), hibrit mimari **paddle-primer + VLM-rescue**
  (dış-model panelinin VLM-primary konsensüsü bilinçli reddedildi).
- **Master kalite krizi**: 1.5fps seyrek kare → compositor motion-eşikleri kırılıyor → scroll
  "statik kart" sanılıp smear. Kök-fix = **dense-frame** (HALLERİ: scroll_frac 0.0→0.755) — POC kanıtlı,
  ÜRETİME GİRMEDİ (Aşama-2 v2 koşu borcu).
- GT karnesi (GPT insan-GT'sine karşı, fix'ler sonrası): ort.hata 124.8→64.1 kare, tam-isabet 3/8→5/8;
  ATTİLA hâlâ -25 kare (GPT window-boundary-v1 entegrasyonu bekliyor).
- 14 Tem 23:42 haftalık limit; 16 Tem dual-boot kararı + yedekleme; hiçbir fix o gün üretime işlenmedi.

## 2. Bugün (2026-07-16) restore edilenler — commit 54b9a47
- `_jenerik_pool.py` 241→487 satır (footage-trim v1/v2, backward-extend, blank-veto v2, VLM-rescue).
- `credit_start_vlm.py` (YENİ; qwen3-vl:30b, STRIDE=12, 512px, büyük-bölge guard).
- `master_png_monitor.py` env-fix (Linux sessiz-boş master riski).
- `_pipe_dilim_vl.py` (openai-backend + Free-OCR prompt ailesi + num_ctx=16384; default model qwen3-vl:8b).
- `master_png_dilimle.py --source {canonical,reading,both}` (default reading — kanonik denemesi geri alınmıştı).
- `harness/` 24 script (yollar+tag'ler bare-metal'e uyarlandı; FILMS_DIR=/opt/mitas/filmtest/aaaa).

## 3. Model envanteri — akıbetler (tam tablo için ajan raporları)
Bugün ollama'da (12): gemma-4-31b-vision, gemma4:26b (bench-DIŞI — kullanıcı kararı), glm-ocr
("inanılmaz iyi okur" — cov 0.69), qwen2.5vl:7b (baseline, %10.1 okunamadı), qwen3:8b (metin),
qwen3-vl:8b (prec 0.77 ama kirli koşu — TEMİZ RE-RUN BORÇ), qwen3-vl:30b (VLM-rescue motoru),
qwen3-vl:32b (bench borcu), qwen36-27b/35b-test (bench borcu), minicpm-v (bench borcu),
deepseek-ocr (Free-OCR fixiyle 51-film tam koşmuştu; geri çekildi).
HF'e bugün inenler: Nemotron-Nano-12B-v2-VL-FP8 (hiç koşturulmadı — vLLM yolu), olmOCR-2-7B-FP8
(arkeoloji #1 önerisi), dots.ocr, PaddleOCR-VL-1.6, InternVL3_5-8B. + qwen2.5vl:32b, mistral-small3.2 (ollama).
Kesin elenenler (tekrar deneme): gpt-oss-20b, Phi-3.5-V, llama3.2-vision, moondream, granite-vision,
Omni ailesi (TR-ASR whisper'a yenik, video OOM), DeepSeek-VL2/InternVL3-38B+ (VRAM).
Kalıcı bilgi: qwen3-vl:30b ollama `think:false` bug'ı → num_predict≥4096 + repeat_penalty=1.0 şart.

## 4. Açık koşu borçları (öncelik sırasıyla)
1. **Aşama-2 v2**: dense-master 51-film (asama2_v2.py hazır; dense POC kanıtlı) — filmler bulununca.
2. **Aşama-3 VL bench**: 192 dilim + roster hazır (master_run.sh CORE+STRETCH güncel) — hiç başlamadı.
3. **ATTİLA/CENNETİN**: GPT window-boundary-v1 entegrasyonu (naif hali regresyon vermişti — redesign).
4. **MAVZER collapse otomasyonu**: mosaic-stack fallback (manuel çözüldü; h<200 & havuz>20 tetiği).
5. **GPT'nin 2 kod bug'ı**: `is_end_card_text` THE-END cezası; `review_boundary_ambiguous` otomatik
   temiz-havuza yayın; + mitas_pipeline.py:1625 civarı 720-vs-900-kare kontrat uyuşmazlığı.
6. qwen3-vl:8b temiz re-run; kırpılan glm-ocr koşusunun tamamlanması.
7. Giriş kuyruk-gevşekliği taraması; CENNETTE giriş-master footage-sınıfı.
8. Fable+GLM panel görüşleri hiç alınamadı; Candidate B/C/D (OCR+LLM-yargıç / saf-CV / optik-akış) denenmedi.

## 5. Kayıp/aranan
- **51 film (720p_test_*)**: D:\filmtest\aaaa BOŞALTILMIŞ; E/F/D/Database'de yok. Kullanıcı ayrıca bakacak.
- F:\LM GGUF deposu (olmOCR-2, Qwen3.5-35B vb.) Ubuntu kurulumuyla silindi — kritik olanlar HF'den tazelendi.
