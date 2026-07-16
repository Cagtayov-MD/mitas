export const meta = {
  name: 'kunye51-stage2-report',
  description: 'MITAS 51-film Aşama-2 (master PNG) film-bazlı analiz + kök-neden + stage2 raporu',
  phases: [
    { title: 'Triage', detail: 'state dosyaları: stage2 durum + segment boyutları + bayraklar' },
    { title: 'RootCause', detail: 'master üretmeyen/şüpheli filmler (Sonnet-5)' },
    { title: 'Report', detail: 'reports/stage2.md + stage2.json' },
  ],
  model: 'sonnet',
}

const RUN = '/opt/mitas/candidate_runs/kunye51_20260714'

const TRIAGE_SCHEMA = {
  type: 'object', required: ['films'],
  properties: { films: { type: 'array', items: {
    type: 'object', required: ['film_id', 'stage2_status'],
    properties: {
      film_id: { type: 'string' },
      stage2_status: { type: 'string', enum: ['pass', 'fail', 'skipped'] },
      cikis_reading_h: { type: 'number' }, cikis_canonical_h: { type: 'number' },
      giris_reading_h: { type: 'number' }, giris_canonical_h: { type: 'number' },
      flags: { type: 'array', items: { type: 'string' } },
      entry_source: { type: ['string', 'null'] },
      root_cause: { type: ['string', 'null'] },
      needs_rootcause: { type: 'boolean' },
    },
  } } },
}
const RC_SCHEMA = {
  type: 'object', required: ['film_id', 'net_cause', 'cls', 'reproduced', 'artifact', 'one_line'],
  properties: {
    film_id: { type: 'string' }, net_cause: { type: 'string' },
    cls: { type: 'string', enum: ['code', 'film', 'system'] },
    reproduced: { type: 'boolean' }, artifact: { type: 'string' },
    one_line: { type: 'string' }, fix_hint: { type: ['string', 'null'] },
  },
}

phase('Triage')
const triage = await agent(
  `MITAS künye Aşama-2 (master PNG) triyajı. \`ls ${RUN}/state/*.json\` → her birini cat. Yalnız stage1 pass olan filmlerde stage2 beklenir.\n` +
  `Her film için stage2'den çıkar: stage2.status→stage2_status (yoksa 'skipped'), segments.cikis.reading.h→cikis_reading_h, segments.cikis.canonical.h→cikis_canonical_h, ` +
  `segments.giris.reading.h→giris_reading_h, segments.giris.canonical.h→giris_canonical_h, manifest'ten bayraklar (very_short_master/single_card_only/no_cast/no_output/bloat/cut_storm)→flags, entry_source, stage2.root_cause.\n` +
  `needs_rootcause=true EĞER: stage2_status!=pass, VEYA cikis_reading_h yok/0 (çıkış master üretilmedi), VEYA giris_reading_h yok/0 (giriş master yok), VEYA flags boş değil. Aksi false.\n` +
  `Yoksa alanı 0/boş bırak; tahmin yok.`,
  { schema: TRIAGE_SCHEMA, label: 'triage', phase: 'Triage' }
)
const films = triage?.films || []
const suspects = films.filter(f => f.needs_rootcause)
log(`Stage2 triage: ${films.length} film, ${films.filter(f=>f.stage2_status==='pass').length} pass, ${suspects.length} şüpheli`)

phase('RootCause')
const rc = await parallel(suspects.map(f => () =>
  agent(
    `MITAS künye Aşama-2 KÖK-NEDEN — film: ${f.film_id}. Klip: ${RUN}/Database/${f.film_id}\n` +
    `Sinyaller: stage2_status=${f.stage2_status}, cikis_reading_h=${f.cikis_reading_h}, giris_reading_h=${f.giris_reading_h}, flags=${JSON.stringify(f.flags||[])}, entry_source=${f.entry_source}.\n` +
    `MERDİVEN (ilk kanıtta dur, tahmin yasak, artefakt zorunlu):\n` +
    `1) Havuz girdisi: \`ls ${RUN}/Database/${f.film_id}/frames/cikis_jenerik | wc -l\` ve giris_jenerik — havuz boşsa master üretilemez (upstream=stage1).\n` +
    `2) Manifest: \`cat ${RUN}/Database/${f.film_id}/'*master_manifest.json'\` — status/kept_blocks/blocks[].skip reasons (unreadable/no-text/empty/dup)/bloat/cut_frac. Hepsi dup/no-text mi (→ compose eşiği=code) yoksa 3-kare sağlıklı havuz mu (→ film, very_short)?\n` +
    `3) Monitör çıktısı: state'teki stage2.monitor_tail; hata/exception var mı (compositor_error=code).\n` +
    `4) Giriş özel: giris_reading_h yoksa — cropstack (cs) OneOCR'a mı takıldı yoksa giris_jenerik havuzu boş mu? state ve loglara bak. (system=OneOCR / upstream=havuz).\n` +
    `Sınıflandır cls=code|film|system; net_cause kısa kod; one_line Türkçe; artifact yol; reproduced bool; fix_hint.`,
    { schema: RC_SCHEMA, label: `rc:${f.film_id.slice(-22)}`, phase: 'RootCause' }
  ).then(v => v || { film_id: f.film_id, net_cause: 'agent_null', cls: 'system', reproduced: false, artifact: '-', one_line: 'agent döndürmedi' })
))

phase('Report')
await agent(
  `MITAS künye Aşama-2 RAPORU yaz: ${RUN}/reports/stage2.md + ${RUN}/reports/stage2.json.\n` +
  `Başlık: "N/51 film master üretti (giriş+çıkış); şüpheli/başarısız M." \n` +
  `Tablo | film_id | entry_source | giriş master h | çıkış master h | kept_blocks | flags | S2 | root_cause |. Başarısız/bayraklı üstte.\n` +
  `Agregasyon: kaç filmde giriş master var vs yok (OneOCR/havuz etkisi), çıkış master var vs yok, bayrak dağılımı (no_cast/very_short/bloat...), entry_source=giris_jenerik vs giris(raw fallback) sayısı.\n` +
  `"Şüphe/Başarısızlık Grupları": kök-neden (net_cause,cls) demetine göre grupla; üye film_id + tek-satır + fix_hint; cls=film 'fixlenmez'.\n` +
  `Öz-değerlendirme: reproduced=false audit borcu; giriş-surrogate'in pass'i şişirip şişirmediği (entry_source=giris raw fallback sayısı).\n\n` +
  `JSON:\n\`\`\`json\n${JSON.stringify({ films, rootcause: rc.filter(Boolean) }).slice(0, 120000)}\n\`\`\`\n` +
  `Write ile yaz; sonra tek satır özet dön.`,
  { label: 'report:stage2', phase: 'Report', agentType: 'general-purpose' }
)
return { films: films.length, pass: films.filter(f=>f.stage2_status==='pass').length, suspects: suspects.length }
