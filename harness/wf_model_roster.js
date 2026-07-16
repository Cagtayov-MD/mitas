export const meta = {
  name: 'kunye-vl-roster',
  description: 'Film-künye master-PNG okuma için VL/OCR model roster araştırması (24GB RTX3090)',
  phases: [
    { title: 'Research', detail: '6 model-ailesi paralel web araştırması' },
    { title: 'Synthesis', detail: 'somut indirilebilir roster + acquisition komutları' },
  ],
  model: 'sonnet',
}

const RUN = '/opt/mitas/candidate_runs/kunye51_20260714'

const FAMILY_SCHEMA = {
  type: 'object',
  required: ['family', 'candidates'],
  properties: {
    family: { type: 'string' },
    candidates: {
      type: 'array',
      items: {
        type: 'object',
        required: ['name', 'is_vision', 'params', 'fits_24gb', 'backend', 'acquire', 'suitability'],
        properties: {
          name: { type: 'string' },
          hf_repo: { type: ['string', 'null'] },
          ollama_tag: { type: ['string', 'null'] },
          is_vision: { type: 'boolean' },
          is_ocr_specialist: { type: 'boolean' },
          params: { type: 'string' },
          quant_for_24gb: { type: 'string' },
          fits_24gb: { type: 'boolean' },
          backend: { type: 'string', enum: ['ollama', 'llama.cpp', 'vllm', 'transformers', 'unknown'] },
          acquire: { type: 'string' },
          ocrbench: { type: ['string', 'null'] },
          suitability: { type: 'integer' },
          notes: { type: ['string', 'null'] },
        },
      },
    },
  },
}

const TASK = (fam, detail) =>
  `Film jeneriği (credits) master-PNG okuma görevi için VL/OCR model araştırması. HEDEF DONANIM: tek RTX 3090 (24GB). ` +
  `GÖREV KARAKTERİ: yüksek-çözünürlüklü, uzun (300x3000+ px), yoğun-metinli jenerik dilimleri; karışık Latin/Türkçe/Fransızca + bazen Arapça/Kiril; ` +
  `küçük/stilize font; amaç isimleri EKSİKSİZ ve HALÜSİNASYONSUZ transkribe etmek (OCR-benzeri). ` +
  `AİLE: ${fam}. ${detail}\n` +
  `Her aday için doldur: is_vision (görüntü okuyabilir mi — SADECE vision/VL modeller işe yarar; metin-only ise is_vision=false ve dışla), ` +
  `is_ocr_specialist, params, quant_for_24gb (24GB'a sığacak quant; FP16/FP8 çoğu 30B+ için sığmaz → Q4_K_M/AWQ/INT4), fits_24gb, ` +
  `backend (ollama|llama.cpp|vllm|transformers), acquire (tam komut: 'ollama pull X' YA DA 'hf download REPO' + serving notu), ` +
  `hf_repo, ollama_tag (varsa), ocrbench (biliniyorsa skor/sıra), suitability (0-100: bu credit-OCR görevine uygunluk), notes. ` +
  `WebSearch/WebFetch kullan; huggingface.co ve ollama.com/library'yi doğrula. Var olmayan/erişilemeyen repo'ları 'acquire' içinde işaretle. ` +
  `SADECE 24GB'a makul sığan (quant ile) adayları öner; sığmayanları fits_24gb=false ile kaydet ama dışlama.`

phase('Research')
const FAMILIES = [
  ['Qwen3-VL (resmi)', 'qwen3-vl: 2b/4b/8b/30b/30b-a3b-instruct/32b/235b. Hangileri ollama.com/library/qwen3-vl da mevcut, hangileri 24GB dense/MoE sığar, credit-OCR icin en iyisi hangisi.'],
  ['Qwen 35B-A3B sınıfı', 'Qwen/Qwen3.5-35B-A3B, Qwen/Qwen3.6-35B-A3B, Qwen/Qwen3.6-27B ve unsloth GGUF (mmproj) sürümleri. KRİTİK: bunlar VISION mı yoksa metin-only mı? mmproj var mı? llama.cpp Q4 ile 24GB sığar mı?'],
  ['DeepSeek', 'deepseek-ai/deepseek-vl2 (27B MoE), DeepSeek-OCR, DeepSeek-OCR-2. Serving (vllm), 24GB fit, OCRBench.'],
  ['InternVL', 'OpenGVLab InternVL3 ve InternVL3.5 (8B/14B/38B) + AWQ/INT4 sürümleri. 24GB da hangi boy sığar (38B quant?), doc-OCR gücü.'],
  ['NVIDIA Nemotron', 'nvidia/NVIDIA-Nemotron-Nano-12B-v2-VL, nvidia/llama-3.1-nemotron-nano-vl-8b-v1, nvidia/nemotron-ocr-v2. OCRBench v2 lideri; serving (vllm/transformers); 24GB fit. 27-35B NVIDIA OCR-VL var mı gercekten?'],
  ['OCR-uzmanları + GLM', 'dots.ocr (3B), MiniCPM-V 4.5 (8B), GOT-OCR2, PaddleOCR-VL, GLM-4.1V ve glm-ocr (ollama). Küçük ama credit-OCR de guclu olanlar.'],
]

const results = await parallel(FAMILIES.map(([fam, detail]) => () =>
  agent(TASK(fam, detail), { schema: FAMILY_SCHEMA, label: `research:${fam.slice(0,18)}`, phase: 'Research' })
))

phase('Synthesis')
const all = results.filter(Boolean)
await agent(
  `Film-künye VL/OCR bench ROSTER'ini sentezle ve yaz: ${RUN}/reports/model_roster.md + ${RUN}/reports/model_roster.json.\n` +
  `Girdi: 6 aile araştırması (JSON aşağıda).\n` +
  `KURALLAR: (1) is_vision=false olanları DIŞLA (görüntü okuyamaz). (2) fits_24gb=true olanları ÖNCELİKLE, sığmayanları ayrı 'sığmaz' bölümüne. ` +
  `(3) glm-ocr her koşulda dahil (kullanıcı istedi, ollama'da mevcut). (4) Zaten yerelde olanları işaretle: qwen2.5vl:7b, glm-ocr:latest (mevcut); qwen3-vl:8b/30b-a3b-instruct/32b, minicpm-v (indiriliyor).\n` +
  `TABLO sütunları: model | modalite(VL/OCR) | params | backend | quant(24GB) | acquire | OCRBench | uygunluk(0-100) | durum(mevcut/indiriliyor/indirilecek).\n` +
  `Modelleri TIER'la: T1 kullanıcının adlandırdıkları (qwen3.5/3.6-35b-a3b, qwen3.6-27b, qwen3-vl-30b-a3b, qwen3-vl-32b), T2 ölçek-eşi (deepseek-vl2, internvl3-38b), T3 OCR-uzmanları+NVIDIA+glm. ` +
  `Her tier'dan uygunluk skoruna göre BENCH'e girecek NİHAİ listeyi öner (24GB'a sığan, VL olan, ~8-12 model). ` +
  `Serving backend özeti: hangileri ollama, hangileri llama.cpp (GGUF+mmproj), hangileri vLLM. ` +
  `acquisition komutlarını ayrı kod bloğunda topla (ollama pull ... ; hf download ... ).\n\n` +
  `JSON:\n\`\`\`json\n${JSON.stringify(all).slice(0, 150000)}\n\`\`\`\n` +
  `Write ile iki dosyayı yaz; sonra 'model_roster yazıldı: bench listesi = [...]' tek satır dön.`,
  { label: 'synth:roster', phase: 'Synthesis' }
)

return { families: all.length, total_candidates: all.reduce((n, r) => n + (r.candidates?.length || 0), 0) }
