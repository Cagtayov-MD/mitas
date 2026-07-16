export const meta = {
  name: 'kunye51-stage1-report',
  description: 'MITAS 51-film Aşama-1 (nezih havuz) film-bazlı analiz + kök-neden + stage1 raporu',
  phases: [
    { title: 'Triage', detail: 'tüm state dosyalarını oku, pass/fail ayır' },
    { title: 'RootCause', detail: 'başarısız/sınırda filmler için kök-neden (Sonnet-5)' },
    { title: 'Report', detail: 'reports/stage1.md + stage1.json yaz' },
  ],
  model: 'sonnet',
}

const RUN = '/opt/mitas/candidate_runs/kunye51_20260714'
const REPO = '/opt/mitas'
const PY = '/opt/mitas/venvs/ocr/bin/python'

const TRIAGE_SCHEMA = {
  type: 'object',
  required: ['films'],
  properties: {
    films: {
      type: 'array',
      items: {
        type: 'object',
        required: ['film_id', 'stage1_status'],
        properties: {
          film_id: { type: 'string' },
          duration_min: { type: 'number' },
          cikis_frames: { type: 'number' },
          giris_frames: { type: 'number' },
          cikis_pool_status: { type: 'string' },
          cikis_pool_frames: { type: 'number' },
          cikis_start_pos: { type: 'number' },
          giris_pool_frames: { type: 'number' },
          credit_type: { type: 'string' },
          stage1_status: { type: 'string', enum: ['pass', 'fail'] },
          root_cause: { type: ['string', 'null'] },
          needs_rootcause: { type: 'boolean' },
        },
      },
    },
  },
}

const RC_SCHEMA = {
  type: 'object',
  required: ['film_id', 'net_cause', 'cls', 'reproduced', 'artifact', 'one_line'],
  properties: {
    film_id: { type: 'string' },
    net_cause: { type: 'string' },
    cls: { type: 'string', enum: ['code', 'film', 'system'] },
    reproduced: { type: 'boolean' },
    artifact: { type: 'string' },
    one_line: { type: 'string' },
    fix_hint: { type: ['string', 'null'] },
  },
}

// ---------- Triage ----------
phase('Triage')
const triage = await agent(
  `MITAS künye 51-film Aşama-1 triyajı. Tüm per-film state dosyalarını oku: \`ls ${RUN}/state/*.json\` sonra her birini \`cat\`.\n` +
  `Her film için stage1 alt-objesinden çıkar: film_id, duration_min (=probe.duration_s/60), cikis_frames, giris_frames, ` +
  `cikis_pool.status→cikis_pool_status, cikis_pool.pool_frames→cikis_pool_frames, cikis_pool.start_pos→cikis_start_pos, ` +
  `giris_pool.pool_frames→giris_pool_frames, cikis_pool.credit_type→credit_type, stage1.status→stage1_status, stage1.root_cause→root_cause.\n` +
  `needs_rootcause=true SADECE EĞER: stage1_status==fail (kapanış havuzu boş = ana çıktı yok) VEYA cikis_pool_frames>=880 (erken/yanlış-tespit şüphesi). ` +
  `giris_pool_frames==0 (opening_paddle_empty) ve 'review'-status BENİGN kabul → needs_rootcause=false (raporda agrege sayılır). Aksi false.\n` +
  `SADECE state dosyalarını oku; tahmin yok, yoksa alanı boş/0 bırak.`,
  { schema: TRIAGE_SCHEMA, label: 'triage', phase: 'Triage' }
)

const films = triage?.films || []
const suspects = films.filter(f => f.needs_rootcause)
log(`Triage: ${films.length} film, ${films.filter(f=>f.stage1_status==='pass').length} pass, ${suspects.length} kök-neden gerektiren`)

// ---------- RootCause (yalnız şüpheliler, paralel) ----------
phase('RootCause')
const rc = await parallel(suspects.map(f => () =>
  agent(
    `MITAS künye Aşama-1 KÖK-NEDEN — film: ${f.film_id}. Klip dizini: ${RUN}/Database/${f.film_id}\n` +
    `State: ${RUN}/state/${f.film_id}.json (önce onu oku). Sinyaller: cikis_pool_frames=${f.cikis_pool_frames}, start_pos=${f.cikis_start_pos}, giris_pool_frames=${f.giris_pool_frames}, status=${f.cikis_pool_status}.\n` +
    `KÖK-NEDEN MERDİVENİ (ilk kanıtta dur, TAHMİN YASAK, her sonuç bir artefakta bağlı olmalı):\n` +
    `1) Film-içsel: \`/usr/bin/ffprobe -v error -show_streams "${f.film_id}"\` kaynağı ${RUN.replace('candidate_runs/kunye51_20260714','')}... aslında src state'te. Süre/codec/video-akış sorunu mu?\n` +
    `2) Ekstraksiyon: \`ls ${RUN}/Database/${f.film_id}/frames/cikis | wc -l\` beklenen ~900 mü?\n` +
    `3) Tespit: \`cat ${RUN}/Database/${f.film_id}/frames/jenerik_detection_cikis.json\` — status/start_pos/confidence/reason; ${RUN}/Database/${f.film_id}/jenerik_debug/ içine bak.\n` +
    `4) Havuz: start_pos vs kare sayısı; cikis_pool_frames>=880 ise 'erken tespit' (kredi başlangıcı çok erken bulunmuş, footage havuza girmiş) olabilir — detection reason'a bak.\n` +
    `5) Giriş: giris_pool_frames==0 ise ${RUN}/Database/${f.film_id}/frames/jenerik_detection_giris.json'a bak (opening_paddle_empty mi, gerçekten açılış-jeneriği yok mu).\n` +
    `Sınıflandır: cls=code|film|system. net_cause kısa kod, one_line tek cümle Türkçe, artifact=incelediğin dosya yolu, reproduced=tek-aşamayı tekrar koşup doğruladın mı (pahalıysa false ve belirt), fix_hint varsa.`,
    { schema: RC_SCHEMA, label: `rc:${f.film_id.slice(-24)}`, phase: 'RootCause' }
  ).then(v => v ? { ...v } : { film_id: f.film_id, net_cause: 'agent_null', cls: 'system', reproduced: false, artifact: '-', one_line: 'agent döndürmedi' })
))

// ---------- Report ----------
phase('Report')
const rcById = {}
for (const r of rc.filter(Boolean)) rcById[r.film_id] = r
const payload = { films, rootcause: rc.filter(Boolean) }

await agent(
  `MITAS künye Aşama-1 RAPORU yaz. Aşağıdaki JSON verisini kullan (triyaj + kök-neden). İki dosya yaz:\n` +
  `1) ${RUN}/reports/stage1.md  2) ${RUN}/reports/stage1.json (ham payload).\n\n` +
  `stage1.md İÇERİĞİ (Türkçe, house-triage stili):\n` +
  `- Başlık satırı: "51 film · Aşama-1: N temiz geçti (kapanış havuzu doldu), M başarısız." (N=stage1_status pass sayısı).\n` +
  `- Tablo | film_id | süre(dk) | giriş kare | çıkış kare | detection | start_pos | çıkış havuz | giriş havuz | S1 | root_cause | (tüm filmler, çıkış-havuz artan sırada başarısızlar üstte).\n` +
  `- Agregasyon: cikis_pool_status dağılımı; giris_pool_frames==0 (opening_paddle_empty) sayısı; çıkış havuz>=880 'erken tespit şüphesi' sayısı; ekstraksiyon hataları.\n` +
  `- "Başarısızlık / Şüphe Grupları" bölümü: kök-neden sonuçlarını (stage,net_cause,cls) demetine göre grupla, her grubun üye film_id'leri + tek-satır neden + fix_hint. cls=film olanları 'fixlenmez (kaynak)' diye ayır.\n` +
  `- Kısa öz-değerlendirme: kaç filmde reproduced=false kaldı (audit borcu).\n\n` +
  `JSON payload:\n\`\`\`json\n${JSON.stringify(payload).slice(0, 120000)}\n\`\`\`\n` +
  `Dosyaları Write ile yaz, sonra 'reports/stage1.md yazıldı: N pass, M fail/şüphe' diye tek satır dön.`,
  { label: 'report:stage1', phase: 'Report', agentType: 'general-purpose' }
)

return { films: films.length, pass: films.filter(f=>f.stage1_status==='pass').length, suspects: suspects.length }
