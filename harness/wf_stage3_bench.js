export const meta = {
  name: 'kunye51-stage3-bench',
  description: 'MITAS 51-film Aşama-3 VL bench: agreement + görsel spot-check + fix-plan + self-audit',
  phases: [
    { title: 'Prep', detail: 'bench_agreement + report_basic çalıştır, 8-film spot-check seç' },
    { title: 'SpotCheck', detail: '8 film: PNG görsel-denetim × modeller (Sonnet-5)' },
    { title: 'Report', detail: 'reports/stage3_bench.md + genel fix-plan + self-audit' },
  ],
  model: 'sonnet',
}
const RUN = '/opt/mitas/candidate_runs/kunye51_20260714'
const H = '/opt/mitas/harness'
const PY = '/opt/mitas/venvs/ocr/bin/python'

const PREP_SCHEMA = {
  type: 'object', required: ['leaderboard', 'spotcheck_films'],
  properties: {
    leaderboard: { type: 'array', items: { type: 'object', properties: {
      model: { type: 'string' }, films: { type: 'number' }, total_lines: { type: 'number' },
      agreement: { type: ['number', 'null'] }, coverage: { type: ['number', 'null'] },
      consensus_precision: { type: ['number', 'null'] } } } },
    spotcheck_films: { type: 'array', items: { type: 'string' }, description: '8 film_id' },
    models: { type: 'array', items: { type: 'string' } },
  },
}
const SPOT_SCHEMA = {
  type: 'object', required: ['film_id', 'per_model', 'best_model', 'notes'],
  properties: {
    film_id: { type: 'string' },
    per_model: { type: 'array', items: { type: 'object', required: ['model', 'accurate', 'halluc', 'miss'],
      properties: { model: { type: 'string' }, accurate: { type: 'integer' }, halluc: { type: 'integer' },
        miss: { type: 'integer' }, quality: { type: 'integer' } } } },
    best_model: { type: 'string' }, notes: { type: 'string' },
  },
}

// ---------- Prep ----------
phase('Prep')
const prep = await agent(
  `MITAS Aşama-3 bench hazırlığı. ÖNCE şu iki komutu Bash ile çalıştır (cwd=/opt/mitas, env: MITAS_RUN_ROOT=${RUN}):\n` +
  `  MITAS_RUN_ROOT=${RUN} ${PY} ${H}/bench_agreement.py\n` +
  `  MITAS_RUN_ROOT=${RUN} ${PY} ${H}/report_basic.py\n` +
  `Sonra ${RUN}/reports/bench_agreement.json'u oku → leaderboard (model,films,total_lines,agreement,coverage,consensus_precision) ve models listesi.\n` +
  `SPOT-CHECK için 8 film_id seç (çeşitlilik): ${RUN}/Database/*/master_dilim/ olan filmlerden 2 yüksek-agreement, 2 düşük-agreement, 2 yüksek-satır (uzun jenerik), 2 non-Latin/yabancı başlıklı (Arapça/Kiril/Fransızca isimli dosya). film_id = Database klasör adı.`,
  { schema: PREP_SCHEMA, label: 'prep', phase: 'Prep', agentType: 'general-purpose' }
)
const films = prep?.spotcheck_films || []
log(`Bench prep: ${(prep?.models||[]).length} model, ${films.length} spot-check filmi`)

// ---------- SpotCheck (görsel) ----------
phase('SpotCheck')
const spot = await parallel(films.map(fid => () =>
  agent(
    `MITAS Aşama-3 GÖRSEL SPOT-CHECK — film: ${fid}. Klip: ${RUN}/Database/${fid}\n` +
    `1) \`ls ${RUN}/Database/${fid}/master_dilim/*.png\` — dilim PNG'leri (jenerik parçaları). Bunlardan 2-3 tanesini Read ile GÖRSEL olarak aç (gerçekte ekranda YAZAN isimleri gör).\n` +
    `2) \`ls ${RUN}/Database/${fid}/master_dilim/dilim_vl__*.json\` — her modelin transkripti. Her birini oku.\n` +
    `3) Her model için: PNG'de fiziksel yazan metne göre transkriptte accurate (doğru okunan satır), halluc (görüntüde OLMAYAN uydurma), miss (görüntüde olup atlanan/[okunamadı]) SAY (yaklaşık, örneklem). quality 0-100.\n` +
    `best_model = bu filmde en doğru okuyan. notes: tek cümle (ör. stilize font X modelini zorladı).\n` +
    `TAHMİN YOK: yalnız açtığın PNG'lerde gördüğüne dayan; görmediğin parçayı sayma, örneklem olduğunu belirt.`,
    { schema: SPOT_SCHEMA, label: `spot:${fid.slice(-20)}`, phase: 'SpotCheck', agentType: 'general-purpose' }
  ).then(v => v || { film_id: fid, per_model: [], best_model: '-', notes: 'agent döndürmedi' })
))

// ---------- Report ----------
phase('Report')
await agent(
  `MITAS Aşama-3 VL BENCH RAPORU + GENEL FİX-PLAN + SELF-AUDIT yaz: ${RUN}/reports/stage3_bench.md.\n` +
  `Kaynakları OKU: ${RUN}/reports/bench_agreement.json (leaderboard+pairwise), ${RUN}/reports/stage3_bench_basic.md (per-model aggregate+matris), ` +
  `${RUN}/reports/stage1.md (Aşama-1 fail grupları F1/C1...), ${RUN}/reports/stage2.md (Aşama-2 partial/fail).\n` +
  `Spot-check verisi (JSON):\n\`\`\`json\n${JSON.stringify(spot.filter(Boolean)).slice(0, 60000)}\n\`\`\`\n` +
  `RAPOR İÇERİĞİ (Türkçe):\n` +
  `1) Başlık: kaç model × kaç film koştu; kaç film uçtan uca (A1+A2+A3) okunabilir sonuç verdi (kullanıcının hedef cümlesi: "N film 1-2-3 geçti okunur sonuç; M şu sebeple olmadı").\n` +
  `2) MODEL LİDERLİK: bench_agreement leaderboard'ı (consensus_precision, coverage, agreement) + basic matris (Σsatır, [okunamadı]%, latency). GT yok → uzlaşı+precision birincil; spot-check ile DOĞRULA (elle örnek en iyi modeli teyit ediyor mu?). Bütçe-kırpılan modelleri (kısmi film) İŞARETLE.\n` +
  `3) SPOT-CHECK ÖZETİ: 8 filmde per-model accurate/halluc/miss + best_model dağılımı. Liderlik ile tutarlı mı?\n` +
  `4) UÇTAN UCA 51-FİLM DURUMU: A1 pass 45 / A2 master 49(30 tam) / A3 okunur — nerede kim çatladı; film_id bazında özet tablo (kısa).\n` +
  `5) GENEL FİX-PLAN (grup→neden→cls→üye film→fix→etki→regresyon riski): Aşama-1 (F1 film-kaynağı FİXLENMEZ; C1 kod: yabancı-alfabe OCR leksikon/dil kapısı → PaddleOCR çok-dilli rec veya _ML_CREDIT_RE genişletme, etki ~2 film), Aşama-2 (kod-fixlenebilir 5), Aşama-3 (yüksek-[okunamadı] filmler = model seçimi). SADECE grup≥2 veya tüm-set etkileyen fix öner; tek-film film-kaynağı fixleme.\n` +
  `6) SELF-AUDIT ("daha iyi yapabilir miydim"): concurrency/GPU-seri doğru muydu; giriş-surrogate (Paddle, OneOCR yerine) pass'i şişirdi mi; bütçe-kırpma bench adaletini bozdu mu (kısmi-film modelleri); reproduced=false borcu; GT'siz 'kazanan' savunulur mu; 1 'sonraki sefer X' her aşama için.\n` +
  `Write ile yaz; sonra tek satır özet dön.`,
  { label: 'report:stage3', phase: 'Report', agentType: 'general-purpose' }
)
return { models: (prep?.models||[]).length, spotcheck: films.length }
