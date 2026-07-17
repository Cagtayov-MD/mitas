export const meta = {
  name: 'mitas-final-report',
  description: 'MITAS 42-film denetimi: TARAFSIZ Opus inceleme (eleştirel doğrulama) + düzeltme tasarımı (kod-konumlu) + final rapor',
  phases: [
    { title: 'Bagimsiz-Inceleme' },
    { title: 'Duzeltme-Tasarimi' },
    { title: 'Final-Sentez' },
  ],
}

const BASE = `
MITAS boru hatti 42-film canli denetimi tamamlandi. Sen BAGIMSIZ/TARAFSIZ bir Opus denetcisin —
onceki denetimi YAPMADIN; gorevin onu ELESTIREL gozle dogrulamak, abartilari/eksikleri yakalamak.
Repo koku: E:/MITAS. SALT-OKUNUR: kod/Database DEGISTIRME, hicbir sey CALISTIRMA, commit YOK. Yalniz OKU + analiz.

DENETIM ARTEFAKTLARI (TAM OKU):
- outputs/RUN_WATCH_20260622/RAPOR.md  → 42 film tablosu + sistemik bulgular + headline'lar (ANA kaynak)
- outputs/RUN_WATCH_20260622/KOD_DENETIMI.md  → on 10-eksen kod denetimi (6 dogrulanmis bulgu, H1-H5)
- outputs/RUN_WATCH_20260622/FILM31_KEDIGOZU_FORENSIK.md  → KEDI GOZU tam kod-trace (varsa)

ILGILI KOD (iddialari dogrulamak/fix-konumu icin OKU):
scripts/mitas_pipeline.py, scripts/tek_film_kunye.py, scripts/credit_qc_block.py, scripts/credit_text_read.py,
scripts/credit_severity_router.py, scripts/jenerik_detector.py (veya core/pipelines/ocr/), scripts/_channel_lang.py,
scripts/credit_kb_lookup.py ; OCR-worktree/ (clean/stitch).

ANA HATA SINIFLARI (denetimde bulunan; sen dogrula):
1. KB/VL OCR-disi isim ekleme — OCR bos/eksikken kimlik-kapisiz yapimci/cast doldurma + VL halusinasyon
   (BEKARLIK Norman Lear: tek_film_kunye.py:563-564 ; MANASLU Hans Ebner: _in_raw token-kalkan gedigi ;
    KEDI GOZU Parker-cikar/Sarrazin-ekle ikame ; BÜLBÜL Gregory Peck). = KURUCU OCR-otorite ihlali.
2. v4-render OCR-formunu/baslidigini eziyor (LEFEBVRE→LEFEVRE, JOSH→JOSHUA, JAIMEE LEE→JAIMEE; orijinal-ad
   COMPANY MEN→MAN, ROBO MAN fabrikasyon, ESCAPING FORM). Ic .txt dogru, nihai PDF ezik.
3. LOST-ACTOR (en pervasif, ~10 film, 6 mekanizma): 8-cap, blok-segmentasyon, acilis-VEYA-kapanis tek-blok secimi
   (HABABAM acilis kacti / FEDORA kapanis tablosu yoksayildi → Holden/Fonda dustu), footage-bloat OCR-kacirma.
4. H1 Latin-disi (Arap/Kiril/Yunan) cast+yon SIFIRLANIYOR (NAMUS DUSMANI) + LID Turkce→Kurtce yanlis (HABABAM:
   Turkce film ku sanildi→ASR atlandi→TMDB yanlis-film ozeti). credit_text_read _fold + _channel_lang.
5. NON-CAST→CAST sizma (7 film): crew (DE Redaktion/FR Scenario/Dialogue Coach), Special Thanks, Assistant to,
   muzisyen (WAR grubu), hayvan (kopek Dolores), gomulu film-ici-film (BABAMIN SINEMASI Morgan/Marais).
6. garble TESLIM kadrosuna girdi (AYI YOGI DAMES DARREN, stitch temiz-7x yerine garble-1x secti) +
   garble-gate Latin-cop KOR NOKTASI (garble_frac=0.0 raporladi → ONAYLI).
7. POSTER yanlis-film (ONAYLI'da gorunur): yanlis-installment (KARAYIP2→Pirates3) + yanlis-film-ayni-baslik
   (COCUKLARIN SAVASI→Acholi cocuk-asker belgeseli). poster_fetch Ing-baslikla esliyor, OCR-kadro/yon ile dogrulamiyor.
8. QC IKI YONDE YANLIS-AYAR: (a) ONAYLI false-negative — kusurlu filmler "kusursuz/ONAYLI" damgalaniyor (HABABAM,
   KEDI GOZU vb.), QC garble/ezme/sizinti/lost-actor yakalamiyor ; (b) KIMLIK false-positive — temiz filmler
   cast-kesisim=0 ile gereksiz KONTROL'e (KOSENIN KRALI/BEKLENEN BOMBA/ANGOLA).
9. TR-DUBLAJ seslendiren kadrosu dusuyor (BÜLBÜL: 19 Turkce ses oyuncusu atildi) — TRT-kritik.
10. Kozmetik/metadata: footage-bloat master (OCR kullanmiyor, zararsiz), karar↔route.folder bayat (fiziksel teslim
    DOGRU), sidecar (.txt/_teknik/md) v4-sonrasi bayat, yinelenen " 2" klasor, tur-siniflandirici gurultusu.
`

// ---- Faz 1: Bağımsız inceleme (2 tarafsız denetçi) ----
phase('Bagimsiz-Inceleme')
const REVIEW_SCHEMA = {
  type: 'object', additionalProperties: false,
  required: ['genel_hukum', 'bulgu_dogrulama', 'oncelik_siralama'],
  properties: {
    genel_hukum: { type: 'string', description: 'Boru hatti genel sagligi + denetimin guvenilirligi hk tarafsiz hukum' },
    bulgu_dogrulama: {
      type: 'array',
      items: {
        type: 'object', additionalProperties: false,
        required: ['sinif', 'hukum', 'not'],
        properties: {
          sinif: { type: 'string', description: 'hata sinifi (1-10)' },
          hukum: { type: 'string', enum: ['DOGRULANDI', 'ABARTILI', 'EKSIK-DEGERLENDIRILMIS', 'CURUTULDU', 'BELIRSIZ'] },
          duzeltilmis_siddet: { type: 'string', enum: ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'KOZMETIK'] },
          not: { type: 'string', description: 'kanit/gerekce; kod veya artefakt referansi' },
        },
      },
    },
    kacirilan_bulgu: { type: 'array', items: { type: 'string' }, description: 'denetimin kacirdigi/yetersiz inceledigi seyler' },
    oncelik_siralama: { type: 'array', items: { type: 'string' }, description: 'TRT teslim-kalitesi acisindan oncelik sirasi (en kritik once)' },
  },
}

const reviewers = [
  {
    key: 'inceleme:bulgu-gecerlilik',
    role: 'BULGU GECERLILIGI + SIDDET denetcisi',
    task: 'RAPOR.md + KOD_DENETIMI.md TAM oku. Her ana hata sinifini (1-10) ELESTIREL dogrula: gercek mi, siddet dogru mu, abartilmis/eksik mi? EN AZ 5 filmin artefaktlarini (Database/<film>/_DURUM.json, ocr/*/kunye.txt, ocr_raw_all.txt, <TRT AD>.pdf) ve iddia edilen kod-konumlarini (orn tek_film_kunye.py:563-564) KENDIN OKUYARAK ornekle. Suphedeysen ABARTILI/BELIRSIZ de. Denetimin yanlis-pozitiflerini ve kacirdiklarini yakala.',
  },
  {
    key: 'inceleme:oncelik-etki',
    role: 'TRT TESLIM-ETKISI + ONCELIK denetcisi',
    task: 'Hangi hata siniflari TRT teslim-kalitesini GERCEKTEN bozuyor (musteriye yanlis/eksik kunye gidiyor) vs kozmetik/ic-artefakt? Bagimsiz bir oncelik siralamasi yap. ONAYLI false-negative (kusurlu→kusursuz) ile KIMLIK false-positive (temiz→gereksiz KONTROL) dengesini degerlendir. OCR-otorite ihlallerinin (kurucu kanun) agirligini tart. Kod oku, kanit ver.',
  },
]
const reviews = await parallel(reviewers.map((r) => () =>
  agent(`${BASE}\n\n=== ROL: ${r.role} ===\n${r.task}\n\nSema ile dondur. bulgu_dogrulama 10 sinifi da kapsamali.`,
    { label: r.key, phase: 'Bagimsiz-Inceleme', schema: REVIEW_SCHEMA, effort: 'high' })
    .then((x) => ({ reviewer: r.key, ...(x || {}) }))
))
const validReviews = reviews.filter(Boolean)
log(`Bagimsiz inceleme: ${validReviews.length}/2 denetci tamam`)

// ---- Faz 2: Düzeltme tasarımı (hata sınıfı başına kod-konumlu fix) ----
phase('Duzeltme-Tasarimi')
const FIX_CLASSES = [
  'KB/VL OCR-disi isim ekleme (kimlik-kapisiz fill + VL token-kalkan)',
  'v4-render OCR-form/baslik ezme',
  'Lost-actor: acilis+kapanis blok birlestirme + 8-cap + blok-segmentasyon',
  'H1 Latin-disi cast/yon + LID Turkce→Kurtce',
  'non-cast→cast sizma (crew/thanks/asistan/muzisyen/hayvan/gomulu-film)',
  'garble teslime girme + garble-gate Latin kor noktasi',
  'poster yanlis-film (OCR-kadro ile dogrulama yok)',
  'QC kalibrasyonu: ONAYLI false-negative + KIMLIK false-positive',
]
const FIX_SCHEMA = {
  type: 'object', additionalProperties: false,
  required: ['sinif', 'kok_neden', 'fix', 'kod_konumu', 'regresyon_riski', 'dogrulama', 'oncelik'],
  properties: {
    sinif: { type: 'string' },
    kok_neden: { type: 'string', description: 'kodda dogrulanmis kok-neden (dosya:satir)' },
    fix: { type: 'string', description: 'somut, minimal, additive/flag-kapili duzeltme onerisi' },
    kod_konumu: { type: 'string', description: 'degisecek dosya:satir(lar)' },
    regresyon_riski: { type: 'string', enum: ['DUSUK', 'ORTA', 'YUKSEK'] },
    regresyon_notu: { type: 'string' },
    dogrulama: { type: 'string', description: 'fix sonrasi hangi filmde/nasil dogrulanir (42 oturum-filminden ornek)' },
    oncelik: { type: 'string', enum: ['1-ACIL', '2-YUKSEK', '3-ORTA', '4-DUSUK'] },
  },
}
const fixes = await parallel(FIX_CLASSES.map((c) => () =>
  agent(`${BASE}\n\n=== DUZELTME TASARIMI ===\nHATA SINIFI: ${c}\n\nBu sinif icin: (1) Kodda kok-nedeni DOGRULA (ilgili dosyalari oku, dosya:satir ver). (2) MINIMAL, regresyon-guvenli (tercihen additive/flag-kapili) bir fix oner — MITAS kurallari: OCR-otorite korunur, garble→KONTROL, silme yok. (3) Regresyon riskini + nasil dogrulanacagini (42 oturum-filminden hangi film) belirt. Kod OKU, uydurma.\n\nSema ile dondur.`,
    { label: `fix:${c}`.slice(0, 48), phase: 'Duzeltme-Tasarimi', schema: FIX_SCHEMA, effort: 'high' })
    .then((x) => x || { sinif: c, fix: 'null' })
))
const validFixes = fixes.filter(Boolean)
log(`Duzeltme tasarimi: ${validFixes.length}/${FIX_CLASSES.length} sinif tamam`)

// ---- Faz 3: Final sentez ----
phase('Final-Sentez')
const final = await agent(
  `${BASE}\n\nAsagida (A) iki tarafsiz denetcinin inceleme sonucu, (B) hata-sinifi basina duzeltme tasarimlari var.\n` +
  `Bunlari + RAPOR.md'yi sentezleyerek Cagatay icin TEK, EYLEME-DONUK FINAL RAPOR yaz (Turkce, markdown).\n\n` +
  `(A) BAGIMSIZ INCELEMELER:\n${JSON.stringify(validReviews, null, 1).slice(0, 45000)}\n\n` +
  `(B) DUZELTME TASARIMLARI:\n${JSON.stringify(validFixes, null, 1).slice(0, 45000)}\n\n` +
  `FINAL RAPOR FORMATI:\n` +
  `# MITAS 42-FİLM DENETİMİ — FİNAL RAPOR (düzeltme + yeniden-koşu için)\n` +
  `1) YÖNETİCİ ÖZETİ (boru hattı genel sağlığı; bağımsız denetçinin tarafsız hükmü; en kritik 3 şey)\n` +
  `2) HATA SINIFLARI — ÖNCELİK SIRALI tablo: sınıf | doğrulanmış şiddet | kök-neden (dosya:satır) | önerilen fix | regresyon riski | hangi filmde doğrulanır\n` +
  `3) BAĞIMSIZ DENETÇİ DÜZELTMELERİ (denetimin abartı/eksik/çürütülen bulguları — şeffaflık)\n` +
  `4) YENİDEN-KOŞU PLANI: aynı 42 oturum-filmi (liste outputs/RUN_WATCH_20260622/seen.txt), öncesi/sonrası karşılaştırma metrikleri (ONAYLI-defekt-oranı, lost-actor-sayısı, OCR-otorite-ihlali-sayısı, garble-teslim, yanlış-afiş)\n` +
  `5) İYİ ÇALIŞAN (regresyon yaratmamak için korunması gerekenler)\n` +
  `6) NET KARAR: önce hangi 3-4 fix yapılmalı (en yüksek getiri/en düşük risk)\n` +
  `Kurallar: yalniz rapor; kod degisikligi/commit YOK (Cagatay yapacak).`,
  { label: 'final-sentez', phase: 'Final-Sentez', effort: 'high' }
)

return {
  reviewers_done: validReviews.length,
  fixes_done: validFixes.length,
  reviews: validReviews,
  fixes: validFixes,
  final_report: final,
}
