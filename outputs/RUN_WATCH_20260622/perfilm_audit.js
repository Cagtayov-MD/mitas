export const meta = {
  name: 'mitas-perfilm-audit',
  description: 'Canli kosu: yeni biten film(ler)i 10 eksende denetler (master-PNG GORSEL + OCR->PDF sadakat + duzeltme listesi + karar/route celiskisi) + kirmizi cekismeli dogrulama + parti sentezi',
  phases: [
    { title: 'Film-denetimi' },
    { title: 'Kirmizi-dogrulama' },
    { title: 'Parti-sentezi' },
  ],
}

// args = [ "E:/MITAS/Database/<AD TRT>", ... ]
const films = Array.isArray(args) ? args : (args ? [args] : [])
if (!films.length) { return { error: 'film yok (args bos)' } }

const RO = `
KISITLAR (SALT-OKUNUR DENETIM):
- Database/ icindeki HICBIR seyi ve repo KODUNU degistirme/yazma/silme. git/commit YASAK. Boru hatti/model/GPU/mitas_pipeline CALISTIRMA. Surecleri OLDURME.
- TEK izinli yazma: GORSEL onizleme/kirpma uretmek icin SADECE su klasore PNG yazabilirsin: E:/MITAS/outputs/RUN_WATCH_20260622/_qc/<film>/ . Database'e veya koda ASLA yazma.
- Oku: Read (PDF + PNG goruntu RENDER eder), Grep, Glob, salt-okunur python (PIL/fitz/json).
- Iddia=kanit. Emin degilsen "belirsiz". Uydurma yok.
Canli env (hepsi AKTIF): QC2=1, QC2_WEB=1, QC_BLOCK=1, CREDIT_DETECT=1, JENERIK_DETECT=1, MASTER_PNG_AUTO=1, GEMMA_FULLCOVER=1, KB_CAST_ADD=1, QC_DIRECTOR_ANCHOR=1, SES_DIL_KONTROL=0.
OCR-OTORITE KANUNU: OCR ne okuduysa O kanun; KB/web yalnizca DESTEKLER (bos-doldur + okunan-yazimi-duzelt + teyit). Okunani BASKA isimle/forma EZME = ihlal. garble -> KONTROL.
`

// On-kod-denetiminden cikan ve her filmde AKTIF aranacak bilinen kalip listesi
const WATCH = `
BILINEN KALIPLAR (bu filmde VAR MI diye AKTIF kontrol et):
- H1 [Latin-disi silme]: ocr/kunye.txt'de Kiril/Yunan/Arap cast/yonetmen OKUNMUS ama final 'oyuncu yok'/bos -> kapsam kaybi.
- H2 [yanlis-film kimlik kilidi]: OCR cast bos/garble iken final PDF'te OCR'da HIC gecmeyen yabanci kadro -> web title+year ile YANLIS filme kilit (OCR-otorite ihlali). _DURUM neden 'versiyon cast-teyitsiz (web title+year kilidi)' ise sik.
- H3 [ozet placeholder]: ana dil != ku + ASR atlandi -> ozet placeholder kaliyor (TMDB-plot denenmiyor) AMA orijinal-ad OCR'da acik olabilir.
- H4 [25fps saniye sismesi]: 25fps natif filmde _log.jsonl credit_detect_closing end_sec > film suresi.
- H5 [cast 8'e kirpma]: gercek dizi/cok-kadro kunye.txt'de 8+ okunmus ama final tam 8'e dusmus.
- KIM/KIMBERLEY tipi: KB-eklenen ismin FORMU ekran/OCR formuyla celisiyor (kisaltma/bozulma).
- ic-artefakt bayatligi: kunye_teslim.md vs final PDF/txt farkli (v4 sonrasi md guncellenmemis).
- karar<->route celiskisi: _DURUM.karar ile _DURUM.route.folder farkli (orn karar=Kontrol ama route.folder=ONAYLI).
`

const CHECK = `
Bu filmin TUM klasorunu denetle. ONCE klasoru listele, sonra:

(A) ARTEFAKTLARI OKU:
- _DURUM.json (karar, route{tier,folder,kontrol_tip,agir,hafif,aciklama}, neden, qwen_qc, teslim, timings)
- ocr/ocr-*/kunye.txt (LLM-temiz) + ocr_raw_all.txt / ocr_ham.txt (OCR HAM = ground-truth) + ocr_summary.json
- master/master_manifest.json (giris/cikis: frames, mode, scroll_frac, size)
- <TRT AD>.pdf (yuzey teslim) -> Read tool ile PDF'i AC ve icerigini gor + <TRT AD>.txt + <TRT AD>_teknik.txt + pdf/kunye_teslim.md
- _log.jsonl (asama izi: hangi dedektor, kac frame, KB/web cagrisi, v4_finalize, master_png olaylari)
- frames/giris ve frames/cikis frame SAYISI

(B) MASTER-PNG GORSEL DENETIM (ONEMLI — sadece varlik degil, KALITE):
1. PIL ile master/giris.png ve master/cikis.png: boyut (w x h) + dosya boyutu (MB) al.
2. Heuristik: bir AÇILIŞ jeneriginde giris cok uzun (>~8000px) veya cok buyuk (>~5MB) + scroll_frac dusuk -> FOOTAGE-SISME suphesi (ornek: RED ROCK giris=900x17726/17MB = footage-sisme). Kayan-yazi cikislari uzun olabilir ama yazi-baskin olmali.
3. PIL ile KUCULTULMUS onizleme (genislik~300) + giris'ten 2-3 NATIF kirpma (900x1400: ust/orta/alt) uret, SADECE E:/MITAS/outputs/RUN_WATCH_20260622/_qc/<filmklasor-adi>/ altina yaz, sonra Read ile AC.
4. Her master icin HUKUM: clean (kredi YAZISI baskin) | footage-bloat (hareketli goruntu baskin, yazi seyrek) | ghost (cift-iz/hayalet) | smear (bulasma) | empty (bos) | yok | belirsiz. Kanit: ne gordugunu yaz.

(C) 10 EKSENDE DEGERLENDIR (her eksen status=OK|SORUN|BELIRSIZ + kisa not+kanit):
 1 JENERIK TESPIT: giris/cikis dogru bulunmus mu? frame sayisi makul mu? _log credit_detect/jenerik penceresi; H4 (end_sec>sure) var mi?
 2 ISIM-KURTARMA + MASTER PNG: kunye.txt OCR-ham'daki isimleri kurtarmis mi (atlama var mi)? MASTER-PNG GORSEL HUKMU (yukaridaki B) — kotuyse belirt. tr_upper İ-bozmasi var mi?
 3 GEMMA ESLESME: kisiler dogru role mi atanmis? rol-etiketi (OYNAYANLAR/YONETMEN) bir ismin icine sizmis mi? gemma okunani EZMIS mi (yalniz bos-alan VL-fallback olmali)?
 4 QC1: OCR kalite/garble kapisi calismis mi? ocr_summary bucket mantikli mi? cokme/bos yok mu? QC1 RED ise karar=Kontrol mu?
 5 QC2/QC_BLOCK DUZELTMELERI: SOMUT LISTELE — ocr/kunye.txt kisileri ile final cast/yon/yapimci'yi KARSILASTIR: ne EKLENDI (KB), ne CIKARILDI, ne YENIDEN-BICIMLENDI. KB-floor OCR'da OLMAYAN isim eklemis mi (uydurma)? EZME var mi?
 6 CIKTI YONLENDIRME: karar + route.folder + teslim konumu YAZ. karar != route.folder CELISKISI var mi? Dosya gercekten dogru export klasorunde mi (ONAYLI/KONTROL)? neden listesi gercek mi (artefaktla ortusuyor mu, bayat mi)?
 7 EKSIK KISI KOK-NEDEN: cast<6 ise NEDEN (OCR'da yok=mesru / kunye.txt'de var atilmis=kayip / KB doldurmadi)? yonetmen/yapimci eksikse NEDEN? OCR-ham'a bakarak ayirt et. H1/H5 var mi?
 8 EKSIK AFIS/TUR/OZET/ORIJINAL-AD: hangisi eksik+NEDEN? afis (dogrulama-yok/bos-kadro), ozet (placeholder/truncation/same-title/H3), tur (provenance), orijinal-ad (kaynak). Bos-cast->TUR+orijinal+afis birlikte mi dustu?
 9 PDF SADAKAT (OCR->PDF GIRIYOR MU? EZILEN VAR MI?): PDF'teki HER cast/crew ismini ocr_raw_all.txt/kunye.txt ile karsilastir; her isim icin: OCR-VAR | KB-EKLENTI(bos-doldur) | EZME(OCR'da FARKLI yazim/isim) | SIZINTI(rol-etiketi/disclaimer/diyalog/baska-film). OCR'da dogru olup PDF'te yanlis/eksik olan? Ozet/isim yuzey-dosyalar arasi tutarli mi (PDF vs .txt vs _teknik.txt vs md)?
10 KB (WIKIPEDIA/IMDB): verimli mi (_log: kb/web cagrisi, afis, doldurma)? OCR-otorite ihlali (ezme) var mi? bos yere uydurma mi? H2 var mi?

${WATCH}

KIRMIZI BAYRAK (red_flags): OCR'i ezme, uydurma isim, veri sizintisi, yanlis-kisi/kimlik kaymasi, yanlis yonlendirme, master footage-bloat/cokme, gercek-veri kaybi (H1/H2/H5), karar-celiskisi. Kozmetik olanlar note'ta kalsin.
`

const FILM_SCHEMA = {
  type: 'object', additionalProperties: false,
  required: ['film', 'genel', 'master_quality', 'axes', 'red_flags'],
  properties: {
    film: { type: 'string' },
    karar: { type: 'string' },
    route_folder: { type: 'string' },
    teslim_tutarli: { type: 'string', enum: ['evet', 'hayir', 'belirsiz'] },
    karar_route_celiski: { type: 'boolean' },
    genel: { type: 'string' },
    master_quality: {
      type: 'object', additionalProperties: false,
      required: ['giris', 'cikis', 'note'],
      properties: {
        giris: { type: 'string', enum: ['clean', 'footage-bloat', 'ghost', 'smear', 'empty', 'yok', 'belirsiz'] },
        cikis: { type: 'string', enum: ['clean', 'footage-bloat', 'ghost', 'smear', 'empty', 'yok', 'belirsiz'] },
        note: { type: 'string' },
      },
    },
    ocr_to_pdf: { type: 'string', description: 'OCR->PDF sadakat ozeti: ezme/sizinti/eksik var mi' },
    duzeltmeler: { type: 'string', description: 'QC2/QC_BLOCK somut eklendi/cikarildi/yeniden-bicimlendi' },
    axes: {
      type: 'array',
      items: {
        type: 'object', additionalProperties: false,
        required: ['axis', 'status', 'note'],
        properties: {
          axis: { type: 'string' },
          status: { type: 'string', enum: ['OK', 'SORUN', 'BELIRSIZ'] },
          note: { type: 'string' },
        },
      },
    },
    red_flags: {
      type: 'array',
      items: {
        type: 'object', additionalProperties: false,
        required: ['axis', 'severity', 'title', 'detail'],
        properties: {
          axis: { type: 'string' },
          severity: { type: 'string', enum: ['CRITICAL', 'HIGH', 'MEDIUM'] },
          title: { type: 'string' },
          detail: { type: 'string' },
          evidence: { type: 'string' },
        },
      },
    },
  },
}

phase('Film-denetimi')
const audits = await pipeline(
  films,
  (folder) => agent(
    `${RO}\n\n=== FILM DENETIMI ===\nKLASOR: ${folder}\n${CHECK}\n\nCiktiyi sema ile dondur. axes 10 eleman (1..10). master_quality ZORUNLU (gorseli gercekten ac). Kanitsiz SORUN deme.`,
    { label: `dn:${String(folder).split(/[\\/]/).pop()}`.slice(0, 55), phase: 'Film-denetimi', schema: FILM_SCHEMA, effort: 'high' }
  ).then((r) => ({ folder, ...(r || {}) })),
  (audit, folder) => {
    const reds = (audit && audit.red_flags) || []
    if (!reds.length) return { ...audit, verified_reds: [] }
    return parallel(reds.map((rf) => () =>
      agent(
        `${RO}\n\nFILM: ${folder}\nKIRMIZI BAYRAK (eksen ${rf.axis}):\nBASLIK: ${rf.title}\nDETAY: ${rf.detail}\nKANIT: ${rf.evidence || '-'}\n\nGOREVIN: Bu bayragi CURUTMEYE calis. Ilgili artefaktlari (OCR-ham, kunye.txt, PDF/goruntu, _DURUM, _log) KENDIN OKU.\nGercek sorun mu yoksa yanlis-alarm mi (OCR'da gercekten yok->mesru eksik / zaten KONTROL'e gitmis / okuma hatasi / olu kod)? Suphedeysen refuted=true. Kanit alintisi ver.`,
        {
          label: `dg:${rf.axis}`.slice(0, 40), phase: 'Kirmizi-dogrulama', effort: 'high',
          schema: {
            type: 'object', additionalProperties: false,
            required: ['refuted', 'reason'],
            properties: {
              refuted: { type: 'boolean' },
              reason: { type: 'string' },
              corrected_severity: { type: 'string', enum: ['CRITICAL', 'HIGH', 'MEDIUM', 'OK'] },
            },
          },
        }
      ).then((v) => ({ ...rf, verify: v || { refuted: false, reason: 'null' } }))
    )).then((vr) => ({ ...audit, verified_reds: vr }))
  }
)

const valid = audits.filter(Boolean)
const confirmedReds = []
for (const a of valid) {
  for (const rf of (a.verified_reds || [])) {
    if (rf.verify && rf.verify.refuted === false) confirmedReds.push({ film: a.film || a.folder, ...rf })
  }
}
log(`${valid.length} film denetlendi; ${confirmedReds.length} dogrulanmis kirmizi bayrak`)

phase('Parti-sentezi')
const synth = await agent(
  `${RO}\n\nAsagida ${valid.length} filmin 10-eksen canli denetim sonucu var. Kisa PARTI RAPORU yaz (Turkce):\n` +
  `1) Her film 1 satir: <FILM> | karar/route | master(giris/cikis) | OK/10 | dogrulanmis-kirmizi | tek-cumle hukum\n` +
  `2) DOGRULANMIS KIRMIZI BAYRAKLAR (film+eksen+ne+kanit)\n` +
  `3) MASTER-PNG durumu (hangi filmde footage-bloat/kotuluk)\n` +
  `4) OCR->PDF: ezme/sizinti gorulen filmler\n` +
  `5) SISTEMIK kalip (bu partide >1 filmde tekrar) + on-kod-denetimi H1-H5'ten hangileri canli teyit oldu\n` +
  `6) ACIL insan-mudahalesi gereken film(ler)\n\n` +
  `VERILER (JSON):\n${JSON.stringify(valid.map((a) => ({ film: a.film || a.folder, karar: a.karar, route_folder: a.route_folder, karar_route_celiski: a.karar_route_celiski, teslim_tutarli: a.teslim_tutarli, master_quality: a.master_quality, ocr_to_pdf: a.ocr_to_pdf, duzeltmeler: a.duzeltmeler, genel: a.genel, axes: a.axes, verified_reds: (a.verified_reds || []).map((r) => ({ axis: r.axis, sev: r.severity, title: r.title, refuted: r.verify && r.verify.refuted, reason: (r.verify && r.verify.reason || '').slice(0, 400) })) })), null, 1).slice(0, 110000)}`,
  { label: 'parti-sentez', phase: 'Parti-sentezi', effort: 'high' }
)

return {
  films_checked: valid.length,
  confirmed_red_count: confirmedReds.length,
  per_film: valid.map((a) => ({
    film: a.film || a.folder,
    karar: a.karar,
    route_folder: a.route_folder,
    karar_route_celiski: a.karar_route_celiski,
    teslim_tutarli: a.teslim_tutarli,
    master_giris: a.master_quality && a.master_quality.giris,
    master_cikis: a.master_quality && a.master_quality.cikis,
    ocr_to_pdf: a.ocr_to_pdf,
    ok_count: (a.axes || []).filter((x) => x.status === 'OK').length,
    sorun_axes: (a.axes || []).filter((x) => x.status === 'SORUN').map((x) => x.axis),
    confirmed_reds: (a.verified_reds || []).filter((r) => r.verify && r.verify.refuted === false).map((r) => ({ axis: r.axis, severity: r.severity, title: r.title })),
    genel: a.genel,
  })),
  confirmed_reds: confirmedReds.map((r) => ({ film: r.film, axis: r.axis, severity: (r.verify.corrected_severity || r.severity), title: r.title, detail: r.detail, reason: (r.verify.reason || '').slice(0, 500) })),
  report: synth,
}
