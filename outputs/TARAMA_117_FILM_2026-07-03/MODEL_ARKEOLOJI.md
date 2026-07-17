Teyit edildi: `F:\REPO_GitHub\.ollama\models\` tamamen boş (blobs klasörü bile yok, manifests klasörü içi boş). Şimdi tüm bulguları derleyip Türkçe hüküm tablosunu oluşturuyorum.

---

# MITAS Ollama Model Restorasyonu — Salt-Okur Arkeoloji Raporu

## Durum teyidi

- `F:\REPO_GitHub\.ollama\models\` **tamamen boş**: `manifests\` klasörü var ama içi boş, `blobs\` klasörü hiç yok. Eski `OLLAMA_MODELS` kökü doğrulanmış F: kaybı (app config kanıtı: `server.log:1` → `OLLAMA_MODELS:F:\\REPO_GitHub\\.ollama\\models`).
- `db.sqlite` (Ollama app kayıt DB'si) canlı process tarafından kilitli/WAL'de; kopyalanan salt-okur snapshot'ta tablo boş çıktı — model listesi kanıtı için kullanılamadı, tüm kanıtlar server/app loglarından çıkarıldı.
- F: diski **fiziksel olarak farklı bir disk** olarak değişmiş (1.9T, 616G boş) ama garip biçimde `F:\LM\` altında **2026-06-18 ile 2026-07-03 arası** tarihli, LM Studio biçiminde yepyeni bir GGUF deposu var — muhtemelen kullanıcı zaten kısmi bir kurtarma/yeniden-indirme sürecine girmiş görünüyor (dosya tarihleri bugüne kadar uzanıyor).

## Kanıt satırları (log)

**gemma-4-31b-it-qat-vision:latest**
```
server.log:23  cmd="...llama-server.exe --model F:\...\sha256-e664c3b437599d70eb7c470e66aaa938c0948c1851a9257f86a96306b94e8c18 ... --mmproj F:\...\sha256-25f056d3264782639e703c877d55cdda764658b1b08f045b533fd1a78cb1902f ..."
server.log     kv: general.architecture=gemma4, general.name="Gemma 4 31B QAT", general.finetune="it-qat-unquantized", size_label=31B, block_count=60, embedding_length=5376
server.log     print_info: file size = 16.42 GiB (4.60 BPW), model params = 30.70 B   [dil modeli]
server.log     clip_model_loader: model name "Gemma 4 31B QAT", projector=gemma4v, load_hparams: model size = 1145.08 MiB   [mmproj]
server.log:284 template selection model=registry.ollama.ai/library/gemma-4-31b-it-qat-vision:latest renderer=gemma4 parser=gemma4
```
→ Registry'den `pull` edilmiş (namespace `library/`), toplam ~17.6 GiB.

**bench-gemma4-31b-qat (ayrı, yerel-yaratılmış deneysel tag — muhtemelen kayıp-5'ten değil)**
```
server-1.log:294942-294947  quantization.go:124 "quantizing model" type=COPY input=...sha256-e664c3b4... output=COPY4204678750  [aynı e664c3b4 blob'u, sadece format-copy]
server-1.log:294939-296123  POST /api/create 200  (2026-06-20 21:28, 38s)
app.log:203  WARN "failed to check upstream digest" error="registry returned status 404" model=bench-gemma4-31b-qat
```
→ Aynı `Gemma 4 31B QAT` blob'undan `ollama create bench-gemma4-31b-qat` ile yerel bir bench-tag'i yaratılmış (2026-06-20 ve 2026-06-23'te 4 kez tekrar create edilmiş). 404, registry'de böyle bir isim hiç olmadığı için normal — yerel-only model.

**glm-ocr:latest**
```
server.log:25845  template selection model=registry.ollama.ai/library/glm-ocr:latest renderer=glm-ocr parser=glm-ocr
server.log        kv: general.architecture=glm4
server.log        --model F:\...\sha256-65493e1f85b9ea4ba3ed793515fde13cbdbea7d74ad2c662b566b146eab0081e --mmproj (AYNI blob)
server.log        handle_glmocr_clip: "detected Ollama-format glm-ocr GGUF used as mmproj; translating"
```
→ Registry'den pull edilmiş, `library/` namespace. Dil-modeli + görsel-projeksiyon **aynı tek GGUF dosyasında** paketlenmiş (Ollama'nın glm-ocr için özel paketleme biçimi). Boyut kanıtı bulunamadı (n_tensors/clip detayları farklı satırlarda: dil modeli ~7.61B/4.12 GiB, clip 673M/1.25 GiB — toplam ~5.4 GiB tahmini, iki ayrı satırdan derlendi, aynı bloba ait olduğu teyitli değil, ihtiyatlı okunmalı).

**qwen3:8b**
```
server-3.log:224 (2026-06-09), server.log:120015 (ilk 6/24)  template selection model=registry.ollama.ai/library/qwen3:8b
server.log  print_info: file size = 4.86 GiB (5.10 BPW), model params = 8.19 B
```
→ Registry `pull`, ~4.86 GiB.

**qwen2.5vl:7b**
```
server-3.log:546 (2026-06-09), server.log:4244  template selection model=registry.ollama.ai/library/qwen2.5vl:7b
server.log  print_info: file size = 4.36 GiB (4.91 BPW), model params = 7.62 B  [dil]
server.log  handle_qwen25vl_clip: "...translating"; load_hparams: model size = 5689.29 MiB  [mmproj/clip, F16→F32 promote nedeniyle şişkin görünüyor]
```
→ Registry `pull`, dil-modeli ~4.36 GiB + mmproj (gerçek disk boyutu muhtemelen daha küçük, 5689 MiB rakamı runtime-genişletilmiş tensor boyutu, indirilen GGUF boyutu değil).

**Genel create kanıtı (5 farklı yerel `ollama create` işlemi tespit edildi, 6/20-6/23)**
```
server-1.log  4 ayrı POST /api/create 200 (6/20 21:26-21:34) → sırayla: Qwen_Qwen3.6 27B, Qwen_Qwen3.5 9B, Gemma 4 31B QAT, Openai_Gpt Oss 20b
server-1.log  3 ayrı POST /api/create 200 (6/23 12:28, 14:40, 14:46) → tekrar Gemma 4 31B QAT (vision + non-vision varyant denemeleri)
```
Bunların hepsi `type=COPY` (quantize DEĞİL, format-normalize) — yani **her biri E:\QwenModels\ayikla_bench\_import\Modelfile.*** dosyalarındaki `FROM F:\LM\lmstudio-community\...\*.gguf` kaynaklarından yapılmış deneysel bench-create'ler, kayıp-5 üretim modelinin `pull` geçmişiyle karışmamalı.

## E:\QwenModels ve E:\NemotronOmni envanteri

| Yol | İçerik | Format | Not |
|---|---|---|---|
| `E:/QwenModels/minicpm-gguf/*.gguf` | MiniCPM-o-4.5 (dil 6.7GB + audio 660MB + vision 1.1GB) | GGUF | kayıp-5'le ilgisiz |
| `E:/QwenModels/qwen3-30b-instruct-gguf/Qwen3-30B-A3B-Instruct-2507-Q4_K_M.gguf` | 18.56 GB | GGUF | kayıp-5'le ilgisiz (30B farklı model) |
| `E:/QwenModels/qwen2.5vl-7b/` | model-0000[1-5]-of-5.safetensors (~13.5 GB toplam) | **HF safetensors, GGUF DEĞİL** | doğrudan `ollama create` edilemez |
| `E:/QwenModels/qwen3vl-8b/` | model-0000[1-4]-of-4.safetensors (~16.9 GB) | **HF safetensors** | doğrudan import edilemez |
| `E:/QwenModels/internvl3-8b/` | model-0000[1-4]-of-4.safetensors (~15.5 GB) | **HF safetensors** | doğrudan import edilemez |
| `E:/QwenModels/qwen3-omni-bf16/` | 15 parça safetensors (BF16, çok büyük) | **HF safetensors** | doğrudan import edilemez |
| `E:/QwenModels/hf-cache/hub/` | Qwen2.5-VL-7B, InternVL3-8B/3.5-8B, Ovis2-8B, Keye-VL, Qwen3-ASR-1.7B repo cache'leri | HF blob cache (4.5 GB, çoğu küçük config/tokenizer) | ağırlık dosyaları büyük ölçüde `.no_exist`/eksik — **tam model ağırlıkları YOK**, sadece metadata |
| `E:/NemotronOmni/gguf/NVIDIA-Nemotron-3-Nano-Omni-30B...IQ4_XS.gguf` | 19.5 GB | GGUF | kayıp-5'le ilgisiz |
| `E:/NemotronOmni/llamacpp/llama-server.exe` | çalıştırılabilir | — | Ollama değil, bağımsız llama.cpp runtime |

**Kritik gguf-format bulgu:** E:\QwenModels altındaki qwen2.5vl-7b / qwen3vl-8b / internvl3-8b klasörleri **HuggingFace safetensors** formatında, GGUF değil. Ollama `ollama create` yalnızca GGUF kabul eder — bu klasörlerden import için önce `llama.cpp`'nin `convert_hf_to_gguf.py` + `llama-quantize` adımlarından geçirilmesi gerekir (ekstra iş, hazır değil).

## Asıl kurtarma kaynağı: F:\LM\lmstudio-community (2026-06-18→07-03 tarihli, YENİ diskte)

```
F:/LM/lmstudio-community/gemma-4-31B-it-QAT-GGUF/gemma-4-31B-it-QAT-Q4_0.gguf       17.65 GB   (2026-07-02)
F:/LM/lmstudio-community/gemma-4-31B-it-QAT-GGUF/mmproj-gemma-4-31B-it-QAT-BF16.gguf 1.20 GB   (2026-07-02)
F:/LM/lmstudio-community/Qwen3-VL-8B-Instruct-GGUF/Qwen3-VL-8B-Instruct-Q8_0.gguf     8.71 GB   (2026-07-03)
F:/LM/lmstudio-community/Qwen3-VL-8B-Instruct-GGUF/mmproj-Qwen3-VL-8B-Instruct-F16.gguf 1.16 GB (2026-07-03)
F:/LM/lmstudio-community/olmOCR-2-7B-1025-GGUF/olmOCR-2-7B-1025-Q8_0.gguf             8.10 GB   (2026-07-03)
F:/LM/lmstudio-community/olmOCR-2-7B-1025-GGUF/mmproj-olmOCR-2-7B-1025-F16.gguf       1.35 GB   (2026-07-03)
```
Bu, `E:\QwenModels\ayikla_bench\_import\Modelfile.gemma4-31b-qat`'ın referans verdiği **tam yolla** (`F:\LM\lmstudio-community\gemma-4-31B-it-QAT-GGUF\gemma-4-31B-it-QAT-Q4_0.gguf`) birebir örtüşüyor — yani gemma-4-31b'nin GGUF kaynağı zaten yeniden edinilmiş durumda, ayrıca `E:\MITAS\models\llm\gemma-4-31b-it-qat\` altında da bir kopyası + hazır `Modelfile`/`Modelfile.vision` bulunuyor.

`qwen3:8b` (metin-only küçük model) ve `glm-ocr` (registry-özel GLM4-OCR paketi) için F:\LM'de **birebir eşleşme yok** — sadece VL varyantları (Qwen3-VL-8B) ve farklı GLM aile üyeleri (GLM-4.6V-Flash, GLM-4.7-Flash) var.

---

## HÜKÜM TABLOSU

| Model | Kaynak-türü (log kanıtı) | Yerel gguf var mı | Hüküm | Aksiyon + tahmini boyut |
|---|---|---|---|---|
| **gemma-4-31b-it-qat-vision:latest** | `pull`, registry `library/` | **EVET** — `F:\LM\lmstudio-community\gemma-4-31B-it-QAT-GGUF\*.gguf` (2026-07-02, tam ~18.85 GB) VE `E:\MITAS\models\llm\gemma-4-31b-it-qat\*.gguf` (aynı boyutlarda, muhtemelen kopya) + hazır `Modelfile.vision` (`FROM` iki gguf, `PARAMETER temperature 0 / num_ctx 8192`) | **(a) yerelden `ollama create` ile kurulabilir** — kaynak: `E:\MITAS\models\llm\gemma-4-31b-it-qat\Modelfile.vision` doğrudan kullanılabilir durumda; sadece `RENDERER gemma4` / `PARSER gemma4` satırlarının eklenip eklenmediği kontrol edilmeli (loglardaki resmi registry sürümünde bu iki satır vardı, yerel Modelfile'da yok) | En hızlı kurtarma — dosyalar zaten diskte, sadece `ollama create` çağrısı eksik |
| **gemma4:26b** (istenen kayıp model — muhtemelen "26B-A4B" ailesi) | log'da doğrudan görülmedi (sadece 31B ve bench-tag'leri log'a düşmüş) | **EVET** — `F:\LM\lmstudio-community\gemma-4-26B-A4B-it-GGUF\` (Q4_K_M 16.8GB + Q6_K 22.6GB + mmproj 1.19GB, 2026-06-18/05-13 tarihli) ve `F:\LM\lmstudio-community\gemma-4-26B-A4B-it-QAT-GGUF\` (QAT-Q4_0 14.4GB) | **(a) yerelden create edilebilir**, Modelfile örneği: `FROM F:\LM\lmstudio-community\gemma-4-26B-A4B-it-QAT-GGUF\gemma-4-26B-A4B-it-QAT-Q4_0.gguf` + mmproj satırı + `RENDERER gemma4` `PARSER gemma4` | Hangi varyant (QAT mı düz mü, Q4 mü Q6 mı) "gemma4:26b" ile eşleşiyordu — kullanıcı teyidi gerekir |
| **glm-ocr:latest** | `pull`, registry `library/`, mimari `glm4`, tek-dosya (dil+mmproj birleşik) `sha256-65493e1f...` | **HAYIR** — F:\LM'de yalnız GLM-4.6V-Flash / GLM-4.7-Flash var, glm-ocr'a özgü paket yok; E:\ aramasında sadece eski test-çıktıları (`glm-ocr_latest.txt` gibi metin dosyaları) bulundu, gguf yok | **(b) registry'den indirilebilir** — `ollama pull glm-ocr:latest` (Ollama resmi/community kütüphanesinde bu isimle mevcutsa) | Tahmini boyut ~5.4 GB (dil 4.12GB q4-benzeri + clip 1.25GB F16, log'dan derlendi); internet erişimi olmadığından registry'de hâlâ yayında olduğu bu oturumda doğrulanamadı |
| **qwen3:8b** | `pull`, registry `library/`, düz metin model | **HAYIR** (yalnız VL/ASR varyantları var: hf-cache'de Qwen2.5-VL-7B, F:\LM'de Qwen3-VL-8B — hiçbiri düz-metin qwen3:8b değil) | **(b) registry'den indirilebilir** — `ollama pull qwen3:8b`, standart Ollama kütüphane modeli | ~4.86 GiB (log kanıtı: file size = 4.86 GiB, 8.19B param, 5.10 BPW) |
| **qwen2.5vl** | `pull`, registry `library/qwen2.5vl:7b` | **KISMEN** — `E:\QwenModels\qwen2.5vl-7b\` var ama **HF safetensors formatında**, GGUF değil; `E:\QwenModels\hf-cache\hub\models--Qwen--Qwen2.5-VL-7B-Instruct\` de metadata-ağırlıklı, tam ağırlık dosyaları teyit edilmedi | **(b) registry'den indirilebilir (en kolay)** — `ollama pull qwen2.5vl:7b`; alternatif **(a)** safetensors'tan `convert_hf_to_gguf.py` ile dönüştürme mümkün ama ekstra adım ve zaman gerektirir, önerilmez | ~4.36 GiB dil + mmproj (registry pull çok daha basit olduğundan yerel dönüştürme tercih edilmemeli) |

## Ek gözlemler

1. **`bench-gemma4-31b-qat`** ve **`qwen3.6:atlas1`** app.log'daki 404 uyarılarının kaynağı — bunlar kullanıcının/ajanların bench amaçlı yerel `ollama create` tag'leri, kayıp-5 listesinde yok, F:\LM ve E:\QwenModels\ayikla_bench\_import\Modelfile.* dosyalarından yeniden yaratılabilirler ama öncelik değil.
2. **F:\LM klasörü hâlihazırda kısmi kurtarma sürecinde** — Jul 2-3 tarihli indirmeler (gemma-4-31B-it-QAT, Qwen3-VL-8B, olmOCR-2-7B, Qwen3.5-35B) var; bu, görev tanımındaki "F: diski değişti, blobs yok" durumunun kısmen zaten telafi edilmeye başlandığının kanıtı. Görev kapsamı gereği bu dosyalara dokunulmadı, sadece envanterlendi.
3. **Disk boş alanı:** F: 616 GB boş / 1.9TB (67% dolu), E: 457 GB boş / 1.9TB (76% dolu), D: yalnızca 60 GB boş / 466GB (88% dolu — model taşımaya uygun değil).
4. **OLLAMA_MODELS taşıma önerisi:** F:\LM zaten aktif indirme hedefi olarak kullanılıyor ve F:'de yeterli boş alan (616 GB) var; `OLLAMA_MODELS` ortam değişkenini `F:\REPO_GitHub\.ollama\models` yerine örneğin `F:\OllamaModels` gibi F:\LM'den ayrı ama yine F: üzerinde bir yola taşımak (env-var güncellemesi + `ollama create`/`ollama pull` sonrası) mantıklı; E: de alternatif olabilir (457 GB boş) ama zaten MITAS Database + QwenModels + NemotronOmni ile dolu, F: daha rahat.
5. **Modelfile.vision eksik satır riski:** `E:\MITAS\models\llm\gemma-4-31b-it-qat\Modelfile.vision` içinde `RENDERER gemma4` / `PARSER gemma4` direktifleri yok (yalnızca `E:\QwenModels\ayikla_bench\_import\Modelfile.gemma4-31b-qat` içeren TEMPLATE/RENDERER/PARSER satırları var, ama o dosya mmproj/vision içermiyor — non-vision varyant). Yeniden `create` edilirken registry sürümündeki chat_template davranışını (tools/vision/thinking) birebir tutturmak için bu satırların eklenmesi gerekebilir.

Tüm bulgular salt-okur şekilde toplanmıştır; hiçbir dosya değiştirilmedi, silinmedi, indirilmedi ve hiçbir `ollama create`/`ollama pull` komutu çalıştırılmadı.