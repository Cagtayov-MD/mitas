# Özet Modeli Bake-off + Sağlıklı-Özet Çözümü — 2026-06-27

**Hedef:** Sistemin sağlıklı (kaynağa sadık) Türkçe film özeti üretmesini sağlamak. ASR transkriptinden 40-60 kelime, doğru kim-kime, kilit dönüm var, final uydurmasız.

## Sorun (önceki denetimden)
10-film denetiminde gemma4:26b özetleri **0/10 tam doğru** çıkmıştı. 4 sistematik kusur: (A) kilit dönüm atlama, (B) rol/yön tersine çevirme (kim kime ne yaptı), (C) kaynakta net olmayan finali uydurma, (D) yabancı dil transkriptinde klişeyle doldurma. Teşhis: darboğaz **model kavraması**, prompt değil.

## Web araştırması (workflow)
- Yerel TurkBench 2026: qwen3:30b-a3b özetlemede #1 (SM 81.9 > gemma 74.1), GLM-4.6 okuma-anlamada 94.0.
- **Reasoning modu halüsinasyonu 2-3× artırıyor** (Vectara HHEM) → think KAPALI şart.
- extract-then-abstract +%15-35 sadakat; self-critique ve CoD bu ölçekte ÖNERİLMEZ.
- Cloud: Gemini Flash ~$1.25/1000 film (batch), Haiku 4.5 ucuzlar içinde Türkçe'de en tutarlı (iddia), Sonnet en kaliteli.

## Model bake-off — 6 zor film (her hata tipini kapsar), aynı V2/QA promtu

| Model | Nasıl | Sonuç | Hüküm |
|---|---|---|---|
| **gemma4:26b** (mevcut) | yerel, think=False, ~6s/film | Temiz format, HIZLI — ama kim-kime/dönüm/final hataları sürüyor | Kavrama tavanı |
| **Qwen3.6-27B** (LM Studio) | dense, GGUF | think KAPANMIYOR → 60-125s/film, çöp (done=length) | ELENDI |
| **Qwen3.6-27B** (ollama GGUF import) | think:false | Şablon BOZUK → İngilizce+Çince+emoji+meta kusuyor | ELENDI |
| **gpt-oss:20b** (ollama native) | reasoning | think:false'a rağmen reasoning bütçeyi yiyor → 0 kelime | ELENDI |
| **nemotron-30b** (GGUF import) | reasoning omni | 95-103 kelime garble ("Alison=kadın", anlamsız) | ELENDI |
| **qwen3:30b-a3b** (ollama native, TurkBench #1) | think=True + sade prompt, ~40s/film | Cemile'yi DOĞRU yaptı (tek!) AMA: Sundown İngilizce çıktı, garble ("agansının"), X-Men "Victor'ın hafızası silinir" (yanlış), Flashdance "ihanetle öldü" (yanlış), tekrar; ÇOK YAVAŞ | Güvenilmez |
| **Haiku 4.5** (cloud, ucuz) | agent | Türkçesi bozuk ("seducting", "kaçan seramı"), Cemile yine ressam, kavrama hataları | ELENDI |
| **Sonnet 4.6** (cloud) | agent | Cemile DOĞRU (Daniyar ile kaçar), X-Men Kayla ihaneti DOĞRU, Flashdance torpil DOĞRU, Sundown Tate sağ DOĞRU | **TEK SAĞLIKLI (~5.5/6)** |

## Kesin sonuç
**Hiçbir yerel model güvenilir sağlıklı Türkçe özet üretemiyor.** Non-reasoning tek temiz model gemma'nın kavrama tavanı var; reasoning modelleri (Qwen3.6/gpt-oss/nemotron/qwen3:30b) ya think kapanmıyor ya şablon bozuk ya yavaş+garble. Ucuz cloud (Haiku) Türkçe'de zayıf. **Yalnız Sonnet 4.6 sağlıklı.** Darboğaz temelden model kavraması; tek GPU'da çalışan modeller bu işi Sonnet kalitesinde yapamıyor.

## Uygulananlar (CANLI, güvenli, default davranış korundu)
1. **Zaman-damgası soyma** — `_ozet_source_text` artık `[HH:MM:SS]` damgalarını kırpmadan önce soyar (flag `MITAS_OZET_STRIP_TS` default-ON, fail-safe). Uzun-film bağlam-aşımı "H" çöp özetini önler + ~%30 token kazancı + daha hızlı.
2. **Opt-in cloud zinciri** — `_ozet_chain()`: default SADECE gemma-local (değişmedi); `MITAS_OZET_CLOUD=1` ise zincir başına Sonnet eklenir (gemma fallback). Default-OFF → anahtar ortamda olsa bile bilerek açılmadıkça bulut çağrılmaz (maliyet koruması). Anahtar yoksa otomatik gemma'ya düşer.
3. Promt sadeleştirmesi (40-60 kelime + "ana konuya in") — bu oturumda CANLI (gemma için).

## Karar (Çağatay'a)
Sağlıklı özet = Sonnet. Seçenekler:
- **A) Cloud aç (ÖNERİLEN):** `MITAS_OZET_CLOUD=1` + `ANTHROPIC_API_KEY`. Maliyet ~$23/1000 film (Sonnet 4.6) — düşürmek için yalnız KONTROL/sorunlu filmlerde aç (hibrit). Kalite kanıtlı.
- **B) Hibrit:** gemma default + yalnız zor/flaglı filmlerde Sonnet → maliyet minimum, çoğu yerel.
- **C) Tam yerel kal:** gemma + iyileştirilmiş prompt + damga-fix → hızlı/bedava ama kavrama hataları kalır (tam sağlıklı DEĞİL).

Artefaktlar: `outputs/OZET_AB/LAB_*.md` (tüm model çıktıları), `DOGRULAMA_10FILM.md` (önceki denetim), bu rapor.
