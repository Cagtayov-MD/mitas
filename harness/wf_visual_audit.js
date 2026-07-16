export const meta = {
  name: 'kunye51-visual-audit',
  description: '51 filmin TAMAMINI görsel denetim: her film için ekranda ne var + pipeline/model doğru mu',
  phases: [
    { title: 'Audit', detail: '51 film — her biri görsel açılıp denetlenir (Sonnet-5)' },
    { title: 'Report', detail: 'reports/visual_audit_51.md' },
  ],
  model: 'sonnet',
}
const RUN = '/opt/mitas/candidate_runs/kunye51_20260714'
const FILMS = Array.isArray(args) ? args
  : (typeof args === 'string' && args.trim().startsWith('[') ? JSON.parse(args) : [])

const AUDIT_SCHEMA = {
  type: 'object',
  required: ['film_id', 'reached', 'onscreen_credits', 'seen', 'pipeline_verdict', 'best_model'],
  properties: {
    film_id: { type: 'string' },
    reached: { type: 'string', enum: ['stage3', 'stage2', 'stage1_fail'] },
    onscreen_credits: { type: 'boolean', description: 'ekranda gerçek okunur künye var mı' },
    language: { type: 'string' },
    seen: { type: 'string', description: 'GÖRDÜĞÜN: yönetmen + birkaç oyuncu/rol (kısa, gerçek okuma)' },
    pipeline_verdict: { type: 'string',
      enum: ['dogru', 'kunye_kacti', 'kunyesiz_dogru', 'kismi', 'erken_tespit', 'master_bozuk'] },
    models: { type: 'array', items: { type: 'object', required: ['model', 'verdict'],
      properties: { model: { type: 'string' }, verdict: { type: 'string', enum: ['iyi', 'orta', 'kotu', 'bos'] },
        note: { type: 'string' } } } },
    best_model: { type: 'string' },
    issue: { type: 'string' },
  },
}

phase('Audit')
const results = await parallel(FILMS.map(fid => () =>
  agent(
    `MITAS künye — TEK FİLM GÖRSEL DENETİM. film_id: ${fid}. Klip: ${RUN}/Database/${fid}\n` +
    `AMAÇ: ekranda GERÇEKTE ne yazdığını GÖZÜNLE gör, pipeline'ın ve modellerin doğru olup olmadığını yargıla. TAHMİN YOK — sadece açtığın görüntüye dayan.\n` +
    `ADIMLAR:\n` +
    `1) \`cat ${RUN}/state/${fid}.json\` — stage1/stage2/stage3 durumu + hangi modellerin sonucu var (stage3.models anahtarları).\n` +
    `2) \`ls ${RUN}/Database/${fid}/master_dilim/*.png 2>/dev/null\`.\n` +
    `   • VARSA (film Aşama-2'yi geçti): reading-master dilimlerinden 3-4 tanesini (baş/orta/son) **Read ile GÖRSEL AÇ**. Ekranda yazan YÖNETMEN + birkaç OYUNCU/ROL'ü oku (seen alanına kısa yaz). Dil? (latin/türkçe/farsça/kiril...). reached='stage3' (VL sonucu varsa) veya 'stage2'.\n` +
    `   • YOKSA (Aşama-1 fail): reached='stage1_fail'. \`ls ${RUN}/Database/${fid}/frames/cikis/\` → SON bölgeden 3-4 kare (ör. 840,865,885,895. kare) **Read ile aç**. Gerçek kapanış künyesi VAR MI yoksa footage/siyah/THE END mi? (kaçan mı, gerçekten künyesiz mi).\n` +
    `3) Eğer master_dilim VARSA, \`ls ${RUN}/Database/${fid}/master_dilim/dilim_vl__*.json\` → her modelin transkriptini oku, GÖRDÜĞÜNLE karşılaştır: model doğru mu okudu (iyi/orta/kotu/bos). En iyi okuyanı best_model yap.\n` +
    `KARARLAR:\n` +
    `• onscreen_credits: ekranda gerçek okunur künye var mı (fail filmde bile bak — kaçan mı).\n` +
    `• pipeline_verdict: 'dogru'=künye var+yakalandı+okundu; 'kunye_kacti'=gerçek künye var ama pipeline/OCR kaçırdı; 'kunyesiz_dogru'=gerçekten künye yok, boş olması doğru; 'kismi'=kısmen; 'erken_tespit'=master çoğu footage; 'master_bozuk'=master var ama okunamaz/bozuk.\n` +
    `• seen: EN AZ yönetmen + 2-3 isim (gördüğün). Boşsa 'okunur künye görülmedi'.\n` +
    `KISA yaz. En fazla 4 görüntü aç (token). best_model yoksa '-'.`,
    { schema: AUDIT_SCHEMA, label: `audit:${fid.slice(-22)}`, phase: 'Audit', agentType: 'general-purpose' }
  ).then(v => v || { film_id: fid, reached: 'stage1_fail', onscreen_credits: false, seen: 'agent döndürmedi',
                     pipeline_verdict: 'master_bozuk', best_model: '-', models: [], issue: 'agent null' })
))

phase('Report')
await agent(
  `MITAS 51-film GÖRSEL DENETİM RAPORU yaz: ${RUN}/reports/visual_audit_51.md + ${RUN}/reports/visual_audit_51.json.\n` +
  `Girdi: 51 filmin görsel-denetim verisi (JSON aşağıda).\n` +
  `RAPOR (Türkçe):\n` +
  `1) Başlık + özet sayılar: kaç film pipeline_verdict='dogru' / 'kunye_kacti' (KURTARILABİLİR!) / 'kunyesiz_dogru' / 'kismi' / 'erken_tespit' / 'master_bozuk'. Kaç filmde ekranda gerçek künye var (onscreen_credits).\n` +
  `2) TAM TABLO — 51 satır: | film_id | reached | ekranda künye? | dil | GÖRDÜĞÜM (yönetmen+isimler kısa) | pipeline | en iyi model | sorun |. pipeline_verdict='kunye_kacti' olanları ÜSTE al (kurtarılabilir kayıplar).\n` +
  `3) 'KURTARILABİLİR KAÇANLAR' bölümü: kunye_kacti + erken_tespit filmleri, neden kaçtı + fix.\n` +
  `4) MODEL kalite özeti: modellerin iyi/orta/kotu/bos dağılımı + best_model kaç filmde kim.\n` +
  `5) 'GERÇEKTEN KÜNYESİZ' (kunyesiz_dogru) filmler ayrı liste (bunlar fixlenmez, kaynak).\n\n` +
  `JSON:\n\`\`\`json\n${JSON.stringify(results.filter(Boolean)).slice(0, 200000)}\n\`\`\`\n` +
  `Write ile yaz; sonra tek satır özet dön.`,
  { label: 'report:audit', phase: 'Report', agentType: 'general-purpose' }
)
const R = results.filter(Boolean)
return {
  films: R.length,
  dogru: R.filter(r => r.pipeline_verdict === 'dogru').length,
  kacti: R.filter(r => r.pipeline_verdict === 'kunye_kacti').length,
  kunyesiz: R.filter(r => r.pipeline_verdict === 'kunyesiz_dogru').length,
}
