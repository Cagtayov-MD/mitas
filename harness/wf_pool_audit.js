export const meta = {
  name: 'kunye51-pool-audit',
  description: 'AŞAMA-1 ODAK: 51 filmin 2. havuzunu (cikis_jenerik) tek tek görsel doğrula',
  phases: [
    { title: 'PoolAudit', detail: '51 film — 2. havuz görsel denetim (Sonnet-5)' },
    { title: 'Report', detail: 'reports/stage1_pool_audit.md + defect grupları' },
  ],
  model: 'sonnet',
}
const RUN = '/opt/mitas/candidate_runs/kunye51_20260714'
const FILMS = Array.isArray(args) ? args
  : (typeof args === 'string' && args.trim().startsWith('[') ? JSON.parse(args) : [])

const SCHEMA = {
  type: 'object',
  required: ['film_id', 'cikis_verdict', 'seen', 'root_defect'],
  properties: {
    film_id: { type: 'string' },
    cikis_pool_frames: { type: 'integer' },
    pool_first_is_credit: { type: 'boolean', description: 'havuzun İLK karesi kredi mi (footage/mid-credit değil)' },
    pool_has_footage: { type: 'boolean', description: 'havuzda footage (kredi olmayan) kare var mı' },
    pool_complete: { type: 'boolean', description: 'kredi SONUNA kadar kapsıyor mu' },
    cikis_verdict: { type: 'string',
      enum: ['temiz', 'footage_bas', 'footage_ortada', 'gec_baslamis', 'eksik', 'bos_kacan', 'bos_dogru'] },
    giris_verdict: { type: 'string',
      enum: ['temiz', 'footage', 'bos_kacan', 'bos_dogru', 'yok', 'bakilmadi'] },
    seen: { type: 'string', description: 'havuz baş/orta/son + (boşsa) ham karede ne var' },
    root_defect: { type: 'string', description: 'kök: start_pos_erken / start_pos_gec / footage / dil_farsca / dusuk_kontrast / gercekten_yok / temiz' },
  },
}

phase('PoolAudit')
const results = await parallel(FILMS.map(fid => () =>
  agent(
    `MITAS AŞAMA-1 HAVUZ DENETİMİ (2. havuz = cikis_jenerik). film_id: ${fid}\n` +
    `AMAÇ: 2. havuzun KALİTELİ oluşup oluşmadığını GÖZLE doğrula. Havuz = tespit edilen kredi-başlangıcından itibaren kopyalanan karelerdir. İYİ havuz: SADECE kredi kareleri (footage yok), kredi-başından-sonuna TAM. TAHMİN YOK.\n` +
    `ADIMLAR:\n` +
    `1) \`cat ${RUN}/state/${fid}.json\` → stage1.cikis_pool (status, start_pos, pool_frames) + giris_pool.\n` +
    `2) HAVUZ DOLU ise (\`ls ${RUN}/Database/${fid}/frames/cikis_jenerik/\` boş değil):\n` +
    `   • İLK pool karesini (ls'te ilk dosya) Read ile AÇ → bu kredi-başlangıcı mı, yoksa footage/sahne mi? (footage ise start_pos ERKEN).\n` +
    `   • ORTA ve SON pool karesini AÇ → footage karışmış mı? kredi sonuna kadar tam mı?\n` +
    `   • Karar: temiz / footage_bas (baş footage) / footage_ortada / gec_baslamis (kredi başını kaçırmış) / eksik (kredi bitmeden kesilmiş).\n` +
    `3) HAVUZ BOŞ ise (0 kare): \`ls ${RUN}/Database/${fid}/frames/cikis/\` → SON bölgeden 3-4 kare AÇ → ekranda GERÇEK kredi var mı (kaçmış = bos_kacan) yoksa gerçekten footage/THE END/siyah mı (bos_dogru). Dili not et (Farsça/Latin...).\n` +
    `4) giris_jenerik'e kısaca bak (varsa 1 kare): temiz/footage/boş.\n` +
    `root_defect: neden böyle (start_pos_erken / start_pos_gec / footage / dil_farsca / dusuk_kontrast / gercekten_yok / temiz). seen: baş/orta/son kısaca.\n` +
    `EN FAZLA 4 görüntü aç.`,
    { schema: SCHEMA, label: `pool:${fid.slice(-22)}`, phase: 'PoolAudit', agentType: 'general-purpose' }
  ).then(v => v || { film_id: fid, cikis_verdict: 'bakilmadi', seen: 'agent null', root_defect: 'agent_null' })
))

phase('Report')
await agent(
  `MITAS AŞAMA-1 HAVUZ KALİTE RAPORU yaz: ${RUN}/reports/stage1_pool_audit.md + .json.\n` +
  `Girdi: 51 filmin 2-havuz görsel denetimi (JSON aşağıda).\n` +
  `RAPOR (Türkçe, ODAK=havuz kalitesi):\n` +
  `1) Özet: cikis_verdict dağılımı (temiz / footage_bas / footage_ortada / gec_baslamis / eksik / bos_kacan / bos_dogru). Kaç film TEMİZ havuz, kaç film SORUNLU.\n` +
  `2) TAM TABLO 51 satır: | film_id | havuz kare | cikis_verdict | giris_verdict | root_defect | GÖRDÜĞÜM |. Sorunlular üstte.\n` +
  `3) DEFECT GRUPLARI (fix hedefi): root_defect'e göre grupla — (a) start_pos_erken/footage (erken-tespit guard gerek), (b) bos_kacan+dil_farsca (çok-dilli OCR), (c) bos_kacan+dusuk_kontrast (eşik/kuyruk-tarama), (d) gercekten_yok (fixlenmez). Her grup: üye film + detector'da fixlenecek yer.\n` +
  `4) 'MAX VERİM' hedefi: kaç film 'temiz'e çekilebilir (bos_kacan + footage + gec/eksik toplamı = kurtarılabilir havuz sayısı).\n\n` +
  `JSON:\n\`\`\`json\n${JSON.stringify(results.filter(Boolean)).slice(0, 200000)}\n\`\`\`\n` +
  `Write ile yaz; tek satır özet dön.`,
  { label: 'report:pool', phase: 'Report', agentType: 'general-purpose' }
)
const R = results.filter(Boolean)
return {
  films: R.length,
  temiz: R.filter(r => r.cikis_verdict === 'temiz').length,
  sorunlu: R.filter(r => !['temiz', 'bos_dogru'].includes(r.cikis_verdict)).length,
}
