# OLLAMA RESTORASYON RUNBOOK — 2026-07-03
(Kaynak: MODEL_ARKEOLOJI.md — log-kanıtlı; hiçbiri henüz ÇALIŞTIRILMADI)

## 0) Önce depo kararı (Çağatay seçer)
Seçenek-A (önerilen): F:'de ayrı temiz depo
    setx OLLAMA_MODELS "F:\OllamaModels"
Seçenek-B: E:'ye taşı (457GB boş; F: tekrar değişirse etkilenmez)
    setx OLLAMA_MODELS "E:\OllamaModels"
Sonra ollama'yı yeniden başlat (tray'den quit + başlat; env yeni process'te okunur).
NOT: LLM-preflight bekçisi (commit bd8cb3ad) artık depo koparsa filmleri görünür işaretler.

## 1) gemma-4-31b-it-qat-vision  (rol-eşleme ana modeli) — YERELDEN, indirme YOK
Dosyalar hazır: E:\MITAS\models\llm\gemma-4-31b-it-qat\ (gguf + mmproj + Modelfile.vision)
    cd /d E:\MITAS\models\llm\gemma-4-31b-it-qat
    ollama create gemma-4-31b-it-qat-vision -f Modelfile.vision
Kontrol: Modelfile.vision'da RENDERER/PARSER gemma4 satırları yoksa ekle (registry sürümünde vardı;
E:\QwenModelsyikla_bench\_import\Modelfile.gemma4-31b-qat'ta örneği mevcut).

## 2) gemma4:26b  (VL-fallback + özet-yerel) — YERELDEN, varyant SEÇİMİ GEREKLİ
F:\LM\lmstudio-community\gemma-4-26B-A4B-it-QAT-GGUF\ (QAT-Q4_0 14.4GB)  ← muhtemel eski eşdeğer
veya ...\gemma-4-26B-A4B-it-GGUF\ (Q4_K_M 16.8GB / Q6_K 22.6GB) + mmproj 1.19GB
Modelfile:  FROM <gguf>  +  FROM <mmproj>  (tek FROM satırı ikili değil; iki ayrı FROM)
    ollama create gemma4:26b -f <Modelfile>

## 3) Registry'den küçükler (internet gerekir; toplam ~15GB)
    ollama pull glm-ocr:latest      (~5.4GB)
    ollama pull qwen3:8b            (~4.9GB)
    ollama pull qwen2.5vl:7b        (~4.4GB)

## 4) Doğrulama
    ollama list   →  5 üretim modeli görünmeli
    python -c "..."  (LLM-preflight zaten her koşuda /api/show probe ediyor)

## 5) Modeller dönünce sıra
  a) YENIDEN_KOSU_ADAYLARI.md (76 C + 13 D film) toplu yeniden koşu — bugünkü 12 fix + K1 zinciri devrede.
  b) K2 pilotu: K2_VL_PILOT_ADAYLARI.md (55 film) üzerinde
         python scripts/_pipe_dilim_vl.py --clip <film>   (gölge; karara bağlı değil)
     Model adayları: F:\LM'de Qwen3.5-35B indirilmiş görünüyor (Çağatay'ın tercihi) → ollama create
     ile kur, MITAS_DILIM_VL_MODEL env'ine yaz; yoksa Qwen3-VL-8B (F:\LM'de hazır, mmproj dahil).
