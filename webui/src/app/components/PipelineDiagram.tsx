import { useEffect, useRef, useState } from 'react';
import {
  AudioLines, Boxes, Eye, FileCheck2, FileText, FolderCheck, FolderClock, Ghost, Image as ImageIcon,
  ScanSearch, ScanText, Scissors, ShieldAlert, ShieldCheck, Sparkles, Split, Stamp, Video, X, Layers,
} from 'lucide-react';

// MITAS pipeline CANLI diyagramı — /api/events (system_events.jsonl) aşama event'lerini node-graph'a
// döker: hangi aşamadayız, geçmiş aşamalar kaç sn, aktif % kaç, nerede TAKILDI. Diyagram GERÇEK
// scripts/mitas_pipeline.py akışını BİREBİR yansıtır: sistemde HANGİ adım varsa o burada (yoksa yok).
// Event kind'leri + sıra + motor adları 3585 gerçek event ile doğrulandı. Backend'e dokunmaz; yalnız
// var olan /api/events + /api/flow-queue/worker'ı okur. ASR %'si GERÇEKTİR: asr_progress.detail.percent.

interface PipelineDiagramProps {
  open: boolean;
  onClose: () => void;
  fallbackFilename?: string;        // batch koşmuyorsa tek-klip adı
  mediaResolution?: string | null;  // tek-klip bağlamında gösterilir
  sourcePath?: string | null;
  profileLabel?: string;
}

interface SysEvent {
  ts?: string; kind?: string; level?: string; filename?: string; summary?: string;
  media_id?: string; duration_seconds?: number; detail?: { percent?: number; [k: string]: unknown };
}

type NodeStatus = 'waiting' | 'active' | 'done' | 'partial' | 'skipped' | 'failed';

interface NodeDef {
  key: string;
  x: number;            // mantıksal koordinat (CANVAS_W x CANVAS_H içinde)
  y: number;
  label: string;
  sub?: string;
  icon: React.ComponentType<{ className?: string; style?: React.CSSProperties }>;
  stage: string;        // hangi aşama event grubuna bağlı (durum bundan gelir)
  eventOnly?: boolean;  // koşullu/post/gate düğüm: durum YALNIZ kendi event'inden gelir (bağımlılıkla "aktif" çıkarımı YAPILMAZ)
}

interface EdgeDef { from: string; to: string; kind?: 'cond' | 'post' }

const CANVAS_W = 840;
const CANVAS_H = 1130;

// "Aktif" çıkarımında bir aşamanın makul üst süre sınırı (sn). Bundan uzun "geçen süre" = bayat event
// (önceki koşu) → sahte "işleniyor" basmayalım. Gerçekte tek aşama 1 saati geçmez (ASR p90 ~4.5dk).
const STALE_ACTIVE_SEC = 3600;

// Çekirdek omurga (doneCount + "aşama" sayacı bunları sayar). pool/vl/master/shadow koşullu/post → sayılmaz.
const SPINE = ['detect', 'coz', 'ocr', 'asr', 'credit', 'qc1', 'qc2', 'ozet', 'pdf', 'v4', 'qcg'];

// Aşama bağımlılıkları (paralel dallar). detect/pool/vl/master/shadow yalnız KENAR çiziminde (eventOnly → çıkarıma girmez).
const DEPS: Record<string, string[]> = {
  detect: [], coz: [], pool: ['coz'], ocr: ['coz'], asr: ['coz'],
  credit: ['ocr'], qc1: ['credit'], vl: ['qc1'], qc2: ['qc1'], ozet: ['asr'],
  pdf: ['qc2', 'ozet'], v4: ['pdf'], qcg: ['v4'], route: ['qcg'],
  master: ['pool'], shadow: ['master'],
};

// Aşama → event kind eşlemesi (pipeline'ın yaydığı GERÇEK kind'ler; çoklu varyant dizi olabilir).
// expectSec = gerçek medyan süre (outputs/system_events.jsonl üzerinden ölçüldü).
type KindSpec = { start?: string | string[]; done?: string | string[]; partial?: string | string[]; skip?: string | string[]; fail?: string | string[]; expectSec: number };
const STAGE_KIND: Record<string, KindSpec> = {
  detect: { start: 'media_imported', done: ['credit_detect_opening', 'credit_detect_closing', 'credit_detect_closing_merge'], skip: 'credit_detect_skip', expectSec: 15 },
  coz:    { start: 'media_imported', done: 'cozumleme_completed', fail: 'cozumleme_failed', expectSec: 86 },
  pool:   { done: 'jenerik_pool_completed', fail: 'jenerik_pool_failed', expectSec: 25 },
  ocr:    { start: 'ocr_started', done: 'ocr_completed', partial: 'ocr_partial', fail: 'ocr_failed', expectSec: 115 },
  asr:    { start: 'asr_started', done: 'asr_completed', partial: 'asr_partial', skip: 'asr_skipped_kurtce', fail: 'asr_failed', expectSec: 156 },
  credit: { done: 'credit_text_completed', fail: 'credit_text_failed', expectSec: 43 },
  qc1:    { start: 'credit_qc1_red', done: 'credit_qc1_passed', fail: 'credit_qc1_failed', expectSec: 73 },
  vl:     { start: 'credit_qc1_red', done: 'credit_vl_fallback', fail: 'credit_vl_failed', expectSec: 73 },
  qc2:    { done: 'credit_validate', fail: 'credit_validate_failed', expectSec: 8 },
  ozet:   { done: ['ozet_completed', 'ozet_internet'], skip: 'ozet_atlandi', expectSec: 12 },
  pdf:    { done: 'pdf_completed', partial: 'pdf_partial', fail: 'pdf_failed', expectSec: 63 },
  v4:     { done: 'v4_finalize_completed', skip: 'v4_finalize_skipped', fail: 'v4_finalize_failed', expectSec: 148 },
  qcg:    { done: 'qwen_final_qc', skip: 'qwen_final_qc_skipped', expectSec: 25 },
  master: { done: ['master_png_completed', 'master_png_surfaced'], partial: 'master_png_empty', fail: 'master_png_failed', expectSec: 30 },
  shadow: { start: 'shadow_vl_started', done: ['shadow_vl_completed', 'jenerik_debug_completed'], partial: 'shadow_vl_empty', skip: 'shadow_vl_skipped', fail: 'shadow_vl_failed', expectSec: 150 },
};

const NODES: NodeDef[] = [
  { key: 'video',  x: 400, y: 30,  label: 'Video',         sub: 'kaynak (yerinde)',              icon: Video,       stage: 'video' },
  { key: 'detect', x: 400, y: 124, label: 'Jenerik Tespiti',sub: 'giriş/çıkış pencere',          icon: ScanSearch,  stage: 'detect', eventOnly: true },
  { key: 'coz',    x: 400, y: 218, label: 'ÇÖZ / ffmpeg',  sub: 'kare + ses çıkar',              icon: Scissors,    stage: 'coz' },
  { key: 'pool',   x: 706, y: 218, label: '2. Havuz',      sub: 'jenerik havuzu',                icon: Boxes,       stage: 'pool', eventOnly: true },
  // SOL DAL — OCR (görüntü) → Künye → QC1 → (VL) → QC2
  { key: 'ocr',    x: 262, y: 306, label: 'OCR',           sub: 'OneOCR — jenerik oku',          icon: ScanText,    stage: 'ocr' },
  { key: 'credit', x: 262, y: 402, label: 'Künye (metin)', sub: 'gemma-31b ayıklayıcı',          icon: FileCheck2,  stage: 'credit' },
  { key: 'qc1',    x: 262, y: 498, label: 'QC1 — künye',   sub: 'yön boş / oyuncu<3 kapısı',     icon: ShieldAlert, stage: 'qc1', eventOnly: true },
  { key: 'vl',     x: 116, y: 498, label: 'VL-Fallback',   sub: 'QC1-RED → gemma4 piksel',       icon: Eye,         stage: 'vl', eventOnly: true },
  { key: 'qc2',    x: 262, y: 588, label: 'QC2 — kimlik',  sub: 'DB cross-check + web',          icon: ShieldCheck, stage: 'qc2' },
  // SAĞ DAL — ASR (ses) → Özet
  { key: 'asr',    x: 540, y: 306, label: 'ASR',           sub: 'MMS-LID + whisper turbo',       icon: AudioLines,  stage: 'asr' },
  { key: 'ozet',   x: 540, y: 402, label: 'Özet',          sub: 'transcript → Gemini 2.5',       icon: Sparkles,    stage: 'ozet' },
  // BİRLEŞ — PDF → V4 → QC-görsel → Yönlendir
  { key: 'pdf',    x: 400, y: 678, label: 'PDF',           sub: 'künye + özet + ses/altyazı',    icon: FileText,    stage: 'pdf' },
  { key: 'v4',     x: 400, y: 766, label: 'V4-Final',      sub: 'büyük-harf · kimlik · afiş',    icon: Stamp,       stage: 'v4' },
  { key: 'qcg',    x: 400, y: 854, label: 'QC-görsel',     sub: 'gemma-vision önizleme',         icon: Eye,         stage: 'qcg' },
  { key: 'route',  x: 352, y: 942, label: 'Yönlendir',     sub: 'reasons → karar',               icon: Split,       stage: 'route' },
  { key: 'hazir',  x: 262, y: 1038,label: 'ONAYLI',        sub: 'export\\ONAYLI',                icon: FolderCheck, stage: 'route_hazir' },
  { key: 'kontrol',x: 446, y: 1038,label: 'KONTROL',       sub: 'export\\KONTROL',               icon: FolderClock, stage: 'route_kontrol' },
  // POST — teslim sonrası provenans (kararı ETKİLEMEZ)
  { key: 'master', x: 706, y: 486, label: 'Master-PNG',    sub: 'jenerik → tek görüntü',         icon: ImageIcon,   stage: 'master', eventOnly: true },
  { key: 'shadow', x: 706, y: 582, label: 'Gölge-VL',      sub: 'bağımsız VL (provenans)',       icon: Ghost,       stage: 'shadow', eventOnly: true },
];

const EDGES: EdgeDef[] = [
  { from: 'video', to: 'detect' }, { from: 'detect', to: 'coz' },
  { from: 'coz', to: 'ocr' }, { from: 'coz', to: 'asr' }, { from: 'coz', to: 'pool', kind: 'post' },
  { from: 'ocr', to: 'credit' }, { from: 'asr', to: 'ozet' },
  { from: 'credit', to: 'qc1' },
  { from: 'qc1', to: 'vl', kind: 'cond' },                    // KOŞULLU: yalnız QC1-RED
  { from: 'qc1', to: 'qc2' },
  { from: 'qc2', to: 'pdf' }, { from: 'ozet', to: 'pdf' },
  { from: 'pdf', to: 'v4' }, { from: 'v4', to: 'qcg' }, { from: 'qcg', to: 'route' },
  { from: 'route', to: 'hazir' }, { from: 'route', to: 'kontrol' },
  { from: 'pool', to: 'master', kind: 'post' }, { from: 'master', to: 'shadow', kind: 'post' },  // POST provenans
];

// Her balonun TAM ne yaptığı — GERÇEK kod/motor adlarıyla (madde madde).
const NODE_DETAILS: Record<string, string[]> = {
  video:   ['Kaynak video AĞ YOLUNDAN okunur (kopyalanmaz)', 'ffprobe: süre / çözünürlük / fps ölçülür'],
  detect:  ['JENERİK-SINIR TESPİTİ — _jenerik_detect.py (üretimde AÇIK: MITAS_JENERIK_DETECT / MITAS_CREDIT_DETECT)',
            'Giriş + çıkış jeneriği penceresini TEK geçişte bulur (CLIP + hareket + OCR-refine, paralel)',
            'Pencere → ÇÖZ\'ün kare çıkarımını yönlendirir (0\'dan değil tespit edilen jenerik-başından; footage süpürme yok)',
            'Düşük güven / kısa film → sabit pencereye düşer (fail-safe, atlanır)',
            'olaylar: credit_detect_opening / credit_detect_closing (+ close_back / merge)'],
  coz:     ['ffprobe ile teknik özellikler okunur (çözünürlük / süre / fps)',
            'Tespit edilen pencereden GİRİŞ + ÇIKIŞ jenerik kareleri çıkarılır (native çözünürlük, 2 fps)',
            'Ses 16 kHz wav olarak ayrıştırılır',
            'Süre tüm çöz bloğunu kapsar (tespit dahil) · olay: cozumleme_completed'],
  pool:    ['2. HAVUZ — paralel jenerik havuzu (_jenerik_pool.py)',
            'frames/cikis → frames/cikis_jenerik (yalnız çıkış jeneriği kareleri süzülür)',
            'Ana OneOCR akışını KULLANMAZ; Master-PNG + Gölge-VL + jenerik-debug bunu besler',
            'olay: jenerik_pool_completed · fail-safe (hata pipeline\'ı bozmaz)'],
  ocr:     ['_pipe_ocr.py — OneOCR (BİRİNCİL motor) jenerik karelerini okur → kunye.txt',
            'Üretim: GLM-konsensüs KAPALI; Paddle yan-kanalı opsiyonel (paddle_kunye.txt, yalnız provenans)',
            'Tespit penceresi az satır verdiyse sabit-pencere ile yeniden OCR (sonuç-temelli yedek)',
            'OCR-OTORİTE: okunan metin nihai kararın çapasıdır'],
  credit:  ['_pipe_credit_text.py — gemma-4-31b-it-qat-vision AYIKLAYICI',
            'OCR METNİNDEN yönetmen / yapımcı / oyuncu eşler (pikselden OKUMAZ)',
            'Halüsinasyon-kalkanı: her isim ham OCR metninde GEÇMELİ',
            'olay: credit_text_completed'],
  qc1:     ['QC1 — künye KALİTE kapısı (mitas_pipeline içi)',
            'Kriter: yönetmen BOŞ veya oyuncu < 3 → RED',
            'RED → VL-Fallback tetiklenir → VL sonrası tekrar denetlenir',
            'VL sonrası hâlâ RED → _qc1_failed → KONTROL sinyali',
            'olaylar: credit_qc1_red / credit_qc1_passed / credit_qc1_failed'],
  vl:      ['KOŞULLU — yalnız QC1-RED iken çalışır',
            '_pipe_credit_vl.py — gemma4:26b PİKSELDEN okur (--fill-cast)',
            'Yönetmeni doldurur + oyuncu < 3 ise oyuncu listesini tamamlar',
            'VL-yönetmen oyuncu listesinde de geçiyorsa DÜŞÜRÜLÜR (okunamadı > yanlış)',
            'olay: credit_vl_fallback'],
  qc2:     ['QC2 — KİMLİK / WEB doğrulama katmanı',
            'Yön-doğrulama: _pipe_credit_validate.py → mitas.duckdb (IMDb + Wikidata) + XML cross-check (olay: credit_validate)',
            'V4 içinde web kimlik: credit_qc_gates.web_identity (TMDB) — kimlik kilitli DEĞİLse web\'den yönetmen/afiş (MITAS_QC2_WEB)',
            'credit_qc_block: çöp-ele + KB-floor + Latin-çevir + OCR-otorite denetimi',
            'Çelişki / kaynak-belirsiz → KONTROL sinyali'],
  asr:     ['_pipe_asr.py — kanal-dil tespiti MMS-LID (1024 dil)',
            'Transkript: faster-whisper large-v3-turbo (TR) / large-v3 (yabancı)',
            'Kürtçe / desteklenmeyen dil → ASR atlanır (özet internetten denenir)',
            'İlerleme CANLI ve GERÇEK: asr_progress yüzdesi (tahmin değil)'],
  ozet:    ['ASR transkriptinden olay-örgüsü özeti',
            'Motor zinciri: gemini-2.5-flash (BİRİNCİL) → Sonnet (yedek) → yerel-gemma (yedek)',
            'SABİT KALIP: 3-4 cümle · 50-60 kelime · SPOİLER içerir',
            'Kürtçe → internetten özet · Transkript yoksa atlanır'],
  pdf:     ['_pipe_pdf.py — künye + özet + ses/altyazı → PDF',
            'Orijinal ad: XML <TITLE> birincil → yoksa kadro-konsensüs',
            'Afiş: orijinal ad + kadro-teyit (yanlış afiş yerine afiş YOK)',
            'Ses/altyazı: kanal-dil bloğu (MMS-LID + Paddle altyazı bandı)'],
  v4:      ['tek_film_kunye.py — künyeyi v4 düzenine çevirir (kunye.pdf üzerine taşır)',
            'BÜYÜK HARF (TR-İ duyarlı) · yapım ekibi SADECE Yönetmen + Yapımcı',
            'Kimlik 3 kademe: XML <TITLE> → yerel-KB → kadro-konsensüs',
            'KB ile TÜR / afiş dolgu · (QC2 kimlik/web doğrulaması bu adımın İÇİNDE koşar)'],
  qcg:     ['QC-görsel — _kunye_qwen_check.py = gemma-4-31b-it-qat-vision GÖRSEL denetim',
            'Render edilen önizleme PNG\'sine bakar (SADECE-gördüğü kuralı)',
            'Denetler: özet · oyuncu · yapımcı · yönetmen · ses/dil · afiş',
            'Büyük-harf · bozuk TR karakter · Latin-dışı alfabe',
            '(dosya adı tarihsel "qwen"; motor 2026-06-23\'ten beri gemma-vision)'],
  route:   ['Tüm kapı sinyalleri (reasons) toplanır',
            'reasons BOŞ → Hazır · DOLU → Kontrol',
            'credit_severity_router: şiddet × tip → AUTOFIX / tip-klasörü',
            'olaylar: routed_hazir / routed_kontrol'],
  hazir:   ['Tüm kapılar temiz → ONAYLI', 'export\\ONAYLI\\<TRT-ID> <BAŞLIK>_onaylı.pdf'],
  kontrol: ['Bir veya çok kapı işaret verdi → insan gözden geçirir', 'export\\KONTROL\\<TRT-ID> <BAŞLIK>[_SORUN-ETİKETİ].pdf'],
  master:  ['MASTER-PNG OLUŞUMU — teslim sonrası provenans (kararı ETKİLEMEZ)',
            '2. Havuz kareleri → tek dikey "master" görüntü (master/cikis.png)',
            '_jenerik_parallel_debug.py (yeni, db_compose_master) veya master_png_monitor.py (legacy)',
            'olaylar: master_png_completed / master_png_surfaced'],
  shadow:  ['GÖLGE-VL — teslim sonrası provenans (kararı ETKİLEMEZ)',
            '_pipe_shadow_vl.py → gemma_kunye.json (bağımsız VL okuması)',
            'Yeni yolda jenerik_parallel_debug içinde (vl + karşılaştırma)',
            'olaylar: shadow_vl_completed / jenerik_debug_completed'],
};

function tsMs(s?: string): number { const v = s ? Date.parse(s) : NaN; return Number.isFinite(v) ? v : NaN; }
function fmtClock(ts?: string): string { const m = tsMs(ts); if (!Number.isFinite(m)) return '--:--:--'; const d = new Date(m); return d.toLocaleTimeString('tr-TR', { hour12: false }); }
const asArr = (v?: string | string[]): string[] => (v == null ? [] : Array.isArray(v) ? v : [v]);

interface StageState { status: NodeStatus; durationSec?: number; elapsedSec?: number; pct?: number; pctReal?: boolean }

function computeStages(events: SysEvent[], focusFile: string | null, isProcessing: boolean, nowMs: number): {
  stages: Record<string, StageState>; karar: 'hazir' | 'kontrol' | null;
} {
  const stages: Record<string, StageState> = {};
  if (!focusFile) return { stages, karar: null };
  const evs = events.filter((e) => e.filename === focusFile && e.kind).sort((a, b) => tsMs(a.ts) - tsMs(b.ts));
  const fin = (n: number) => Number.isFinite(n);
  // bir kind GRUBUNUN (string|dizi) bu film için EN SON timestamp'i
  const lastTsOf = (kinds?: string | string[]): number => {
    const set = new Set(asArr(kinds));
    if (!set.size) return NaN;
    for (let i = evs.length - 1; i >= 0; i--) if (evs[i].kind && set.has(evs[i].kind!)) return tsMs(evs[i].ts);
    return NaN;
  };
  // grubun EN SON event NESNESİ (duration_seconds gibi alanlara erişmek için)
  const lastEvtOf = (kinds?: string | string[]): SysEvent | null => {
    const set = new Set(asArr(kinds));
    if (!set.size) return null;
    for (let i = evs.length - 1; i >= 0; i--) if (evs[i].kind && set.has(evs[i].kind!)) return evs[i];
    return null;
  };

  // GERÇEK ASR % — asr_progress event'i filename TAŞIMAZ, media_id ile gelir. Önce bu filmin
  // media_id'sini bul, sonra TÜM event'lerde o media_id'li en yeni asr_progress.detail.percent'i al.
  let focusMediaId: string | null = null;
  for (let i = evs.length - 1; i >= 0; i--) { const m = evs[i].media_id; if (m) { focusMediaId = m; break; } }
  let asrRealPct: number | null = null;
  if (focusMediaId) {
    let bestTs = -Infinity;
    for (const e of events) {
      if (e.kind === 'asr_progress' && e.media_id === focusMediaId) {
        const t = tsMs(e.ts); const p = e.detail?.percent;
        if (fin(t) && t > bestTs && typeof p === 'number') { bestTs = t; asrRealPct = Math.max(0, Math.min(100, Math.round(p))); }
      }
    }
  }

  const allKeys = Object.keys(STAGE_KIND);
  const endTs: Record<string, number> = {};
  const endDur: Record<string, number> = {};   // event'in KENDİ raporladığı duration_seconds (en doğru süre)
  // 1) terminal durum + bitiş zamanı + (varsa) event-raporlu süre (öncelik: fail > done > partial > skip)
  for (const key of allKeys) {
    const k = STAGE_KIND[key];
    const cand: Array<[NodeStatus, string | string[] | undefined]> = [['failed', k.fail], ['done', k.done], ['partial', k.partial], ['skipped', k.skip]];
    let status: NodeStatus = 'waiting';
    for (const [stt, kinds] of cand) {
      const ev = lastEvtOf(kinds);
      if (ev) {
        status = stt;
        const ts = tsMs(ev.ts);
        if (fin(ts)) { endTs[key] = ts; if (typeof ev.duration_seconds === 'number') endDur[key] = ev.duration_seconds; }
        break;
      }
    }
    stages[key] = { status };
  }

  // QC1 ÖZEL — kapı: credit_qc1_* + SESSİZ-GEÇİŞ çıkarımı (oyuncu≥3 & yön var → RED hiç olmaz, event yok).
  {
    const red = lastTsOf('credit_qc1_red'), passed = lastTsOf('credit_qc1_passed'), failed = lastTsOf('credit_qc1_failed');
    const creditDone = lastTsOf(STAGE_KIND.credit.done);
    const s = stages['qc1'];
    if (fin(failed)) { s.status = 'failed'; endTs['qc1'] = failed; }
    else if (fin(passed)) { s.status = 'done'; endTs['qc1'] = passed; }
    else if (fin(red)) { s.status = 'active'; }                                   // VL koşuyor / yeniden denetleniyor
    else if (fin(creditDone)) { s.status = 'done'; endTs['qc1'] = creditDone; }   // sessiz geçiş (RED hiç olmadı)
    else { s.status = 'waiting'; }
  }

  // Jenerik Tespiti: tespit event'i yoksa ama çöz bittiyse → kısa film, sabit pencere (atlandı)
  if (stages['detect'].status === 'waiting' && fin(lastTsOf(STAGE_KIND.coz.done))) stages['detect'].status = 'skipped';

  const depEnds = (key: string) => (DEPS[key] || []).map((d) => endTs[d]).filter(fin);
  // bağımlılık "çözüldü mü": done/skipped/partial/failed (pipeline hatadan sonra da devam eder)
  const depsResolved = (key: string) => (DEPS[key] || []).every((d) => ['done', 'skipped', 'partial', 'failed'].includes(stages[d]?.status));
  const baseTsOf = (key: string, startEv: number): number => {
    if (fin(startEv)) return startEv;
    if (key === 'coz') return lastTsOf('media_imported');
    const de = depEnds(key);
    return de.length ? Math.max(...de) : NaN;
  };
  const isEventOnly = (key: string) => NODES.find((n) => n.key === key)?.eventOnly;

  // 2) süre + AKTİF çıkarımı
  for (const key of allKeys) {
    const k = STAGE_KIND[key];
    const st = stages[key];
    const startEv = lastTsOf(k.start);
    const base = baseTsOf(key, startEv);
    // Süre: ÖNCE event'in kendi duration_seconds'i (en doğru). Yoksa, YALNIZ gerçek start-event'i olan
    // aşamada zaman-damgası farkı (start-event'siz post/gate düğümde uydurma süre BASMA → sahte "7dk").
    const hasStart = fin(startEv) || key === 'coz';
    if (['done', 'partial', 'failed'].includes(st.status)) {
      if (typeof endDur[key] === 'number') st.durationSec = endDur[key];
      else if (hasStart && fin(endTs[key]) && fin(base) && endTs[key] >= base) st.durationSec = (endTs[key] - base) / 1000;
    }
    if (isProcessing && st.status === 'waiting') {
      // eventOnly (pool/qc1/vl/master/shadow): YALNIZ kendi start-event'i varsa aktif (bağımlılıkla çıkarım YOK)
      const canActivate = isEventOnly(key) ? fin(startEv) : (fin(startEv) || depsResolved(key));
      if (canActivate) {
        if (fin(base)) {
          const elapsed = Math.max(0, (nowMs - base) / 1000);
          if (elapsed <= STALE_ACTIVE_SEC) {            // bayat değil → gerçekten işleniyor
            st.status = 'active';
            st.elapsedSec = elapsed;
            st.pct = Math.min(98, Math.round((elapsed / k.expectSec) * 100));
          }
          // elapsed > sınır → bayat event; 'waiting' kalır (saçma "8776dk işleniyor" basmaz)
        } else {
          st.status = 'active';                          // bağımlılık çözüldü ama zaman damgası yok
        }
      }
    }
    // ASR: tahmini % yerine GERÇEK asr_progress %'sini kullan (aktifken)
    if (key === 'asr' && st.status === 'active' && asrRealPct != null) {
      st.pct = asrRealPct; st.pctReal = true;
    }
  }
  // QC1 aktifken (VL koşarken) geçen süre + % (eventOnly olduğu için yukarıdaki blok atladı)
  if (stages['qc1'].status === 'active') {
    const b = lastTsOf('credit_qc1_red');
    if (fin(b)) { const el = Math.max(0, (nowMs - b) / 1000); if (el <= STALE_ACTIVE_SEC) { stages['qc1'].elapsedSec = el; stages['qc1'].pct = Math.min(98, Math.round((el / STAGE_KIND.qc1.expectSec) * 100)); } }
  }

  const karar: 'hazir' | 'kontrol' | null =
    fin(lastTsOf('routed_hazir')) ? 'hazir'
    : fin(lastTsOf('routed_kontrol')) ? 'kontrol' : null;
  return { stages, karar };
}

const STATUS_COLOR: Record<NodeStatus, { ring: string; bg: string; text: string; glow?: boolean }> = {
  waiting:  { ring: '#2b3447', bg: '#11151f', text: '#5b6678' },
  active:   { ring: '#f5b301', bg: '#2a2305', text: '#ffd34d', glow: true },
  done:     { ring: '#1f9d57', bg: '#0c1f15', text: '#3ddc84' },
  partial:  { ring: '#c98a1a', bg: '#231a08', text: '#f1b54a' },
  skipped:  { ring: '#3a4256', bg: '#141823', text: '#7c8696' },
  failed:   { ring: '#d33a3a', bg: '#260c0c', text: '#ff6b6b', glow: true },
};

const STAT_LABEL: Record<NodeStatus, string> = { waiting: 'bekliyor', active: 'işleniyor', done: 'bitti', partial: 'kısmi', skipped: 'atlandı', failed: 'TAKILDI' };

function nodeStatus(node: NodeDef, stages: Record<string, StageState>, karar: 'hazir' | 'kontrol' | null, anyEvent: boolean): StageState {
  if (node.stage === 'video') return { status: anyEvent ? 'done' : 'waiting' };
  if (node.stage === 'route') return { status: karar ? 'done' : (stages['qcg']?.status === 'done' ? 'active' : 'waiting') };
  if (node.stage === 'route_hazir') return { status: karar === 'hazir' ? 'done' : 'waiting' };
  if (node.stage === 'route_kontrol') return { status: karar === 'kontrol' ? 'partial' : 'waiting' };
  return stages[node.stage] ?? { status: 'waiting' };
}

function fmtDur(sec?: number): string {
  if (!sec || !Number.isFinite(sec)) return '';
  if (sec < 60) return `${sec.toFixed(sec < 10 ? 1 : 0)} sn`;
  const m = Math.floor(sec / 60); const s = Math.round(sec % 60);
  return `${m}dk ${s}sn`;
}

export function PipelineDiagram({ open, onClose, fallbackFilename, mediaResolution, sourcePath, profileLabel }: PipelineDiagramProps) {
  const [events, setEvents] = useState<SysEvent[]>([]);
  const [current, setCurrent] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const [now, setNow] = useState(() => 0);
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const [retrying, setRetrying] = useState(false);
  const openRef = useRef(open);
  openRef.current = open;

  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    const poll = async () => {
      try {
        const [er, wr] = await Promise.all([
          fetch('/api/events?limit=400', { cache: 'no-store' }),
          fetch('/api/flow-queue/worker', { cache: 'no-store' }),
        ]);
        if (er.ok) { const d = await er.json(); if (!cancelled) setEvents(Array.isArray(d.events) ? d.events : []); }
        if (wr.ok) { const w = await wr.json(); if (!cancelled) { setRunning(Boolean(w?.running)); setCurrent(w?.current ?? null); } }
      } catch { /* geçici */ }
    };
    void poll();
    const pid = window.setInterval(() => { if (openRef.current) void poll(); }, 1500);
    const tick = window.setInterval(() => setNow(Date.now()), 1000);
    setNow(Date.now());
    return () => { cancelled = true; window.clearInterval(pid); window.clearInterval(tick); };
  }, [open]);

  if (!open) return null;

  const focusFile = current || fallbackFilename || null;
  const { stages, karar } = computeStages(events, focusFile, running || Boolean(current), now || Date.now());
  const anyEvent = Boolean(focusFile && events.some((e) => e.filename === focusFile));
  const nodeById = (k: string) => NODES.find((n) => n.key === k)!;
  const stateOf = (n: NodeDef) => nodeStatus(n, stages, karar, anyEvent);

  // genel ilerleme (yalnız çekirdek omurga)
  const doneCount = SPINE.filter((k) => ['done', 'skipped', 'partial'].includes(stages[k]?.status)).length;
  const activeNode = NODES.find((n) => stateOf(n).status === 'active');
  const failedNode = NODES.find((n) => stateOf(n).status === 'failed');

  // SOL panel: seçili (ya da takılan/aktif) balonun detayı + bu filmin canlı log'u
  const detailNode = NODES.find((n) => n.key === (selectedKey ?? (failedNode ?? activeNode)?.key)) ?? null;
  const detailState = detailNode ? stateOf(detailNode) : null;
  const logEvents = (focusFile ? events.filter((e) => e.filename === focusFile) : [])
    .slice().sort((a, b) => tsMs(b.ts) - tsMs(a.ts)).slice(0, 80);

  const edgeActive = (e: EdgeDef) => stateOf(nodeById(e.to)).status === 'active';
  const edgeDone = (e: EdgeDef) => ['done', 'skipped', 'partial'].includes(stateOf(nodeById(e.to)).status);

  const headline = !focusFile ? 'Şu an işlenen film yok' : failedNode ? `TAKILDI: ${failedNode.label}` : activeNode ? `İşleniyor: ${activeNode.label}` : karar ? `Bitti → ${karar === 'hazir' ? 'ONAYLI' : 'KONTROL'}` : 'Hazırlanıyor';

  // "Yeniden çöz": bu filmi SIFIRDAN tekrar dene (stale sil + kuyruğa 'waiting'). Kuyruk akmaya devam eder.
  const doRetry = async () => {
    if (!focusFile || retrying) return;
    setRetrying(true);
    try {
      const r = await fetch('/api/flow-queue/retry', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ filename: focusFile }) });
      if (!r.ok) { window.alert(`Yeniden çöz başarısız: ${await r.text()}`); return; }
      window.alert(`"${focusFile}" sıfırdan yeniden çözülmek üzere kuyruğa eklendi (kuyruk akmaya devam eder).`);
    } catch (e) {
      window.alert(`Yeniden çöz hatası: ${String(e)}`);
    } finally {
      setRetrying(false);
    }
  };

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/70 backdrop-blur-sm p-4" onClick={onClose}>
      <style>{`
        @keyframes mitasFlow { to { stroke-dashoffset: -28; } }
        @keyframes mitasPulse { 0%,100% { filter: drop-shadow(0 0 3px var(--g)); } 50% { filter: drop-shadow(0 0 12px var(--g)); } }
      `}</style>
      <div className="relative flex max-h-[92vh] w-full max-w-[1180px] flex-col overflow-hidden rounded-md border border-border-mitas bg-app-shell shadow-2xl" onClick={(e) => e.stopPropagation()}>
        {/* başlık */}
        <div className="flex items-center justify-between gap-3 border-b border-border-subtle bg-surface/50 px-4 py-2.5">
          <div className="flex min-w-0 items-center gap-2">
            <Layers className="h-4 w-4 shrink-0 text-info" />
            <span className="text-sm font-bold tracking-wide text-foreground-strong">PIPELINE</span>
            <span className={`ml-2 truncate text-xs ${failedNode ? 'text-danger font-semibold' : activeNode ? 'text-warning font-semibold' : 'text-foreground-muted'}`}>{headline}</span>
          </div>
          <div className="flex shrink-0 items-center gap-2">
            {focusFile && (failedNode || karar) ? (
              <button type="button" onClick={doRetry} disabled={retrying}
                className={`rounded-sm px-2 py-0.5 text-[10px] font-semibold ${failedNode ? 'bg-danger-subtle text-danger hover:bg-danger-subtle/70' : 'bg-surface text-foreground-muted hover:bg-surface-elevated'} disabled:opacity-50`}
                title="Bu filmi sıfırdan yeniden çöz (kuyruk akmaya devam eder)">
                {retrying ? 'Gönderiliyor…' : '⟳ Yeniden çöz'}
              </button>
            ) : null}
            <span className="rounded-sm bg-surface px-2 py-0.5 text-[10px] text-foreground-muted">{doneCount}/{SPINE.length} aşama</span>
            <button type="button" onClick={onClose} className="rounded-sm p-1 text-foreground-muted hover:bg-surface-elevated hover:text-foreground-strong" title="Kapat"><X className="h-4 w-4" /></button>
          </div>
        </div>
        {/* film adı */}
        <div className="border-b border-border-subtle/60 bg-app-shell px-4 py-1.5 text-[11px] text-foreground-muted">
          <span className="text-foreground-disabled">Film: </span>
          <span className="font-mono text-foreground-default">{focusFile ?? '—'}</span>
          {running ? <span className="ml-2 inline-flex items-center gap-1 text-success"><span className="h-1.5 w-1.5 animate-pulse rounded-full bg-success" />canlı</span> : null}
          {!current && (sourcePath || mediaResolution || profileLabel) ? (
            <span className="ml-2 text-foreground-disabled">
              {profileLabel ? `· ${profileLabel}` : ''}{sourcePath ? ` · ${sourcePath}` : ''}{mediaResolution ? ` · ${mediaResolution}` : ''}
            </span>
          ) : null}
        </div>
        {/* gövde: SOL (aşama detayı + canlı log) | SAĞ (diyagram) */}
        <div className="flex min-h-0 flex-1">
          {/* SOL panel */}
          <div className="flex w-[300px] shrink-0 flex-col border-r border-border-subtle bg-app-shell">
            {/* aşama detayı — bu balon TAM ne yapıyor (madde madde) */}
            <div className="border-b border-border-subtle px-3 py-2">
              {detailNode && detailState ? (
                <>
                  <div className="flex items-center gap-2">
                    <span className="h-2.5 w-2.5 rounded-full" style={{ background: STATUS_COLOR[detailState.status].ring }} />
                    <span className="text-xs font-bold" style={{ color: STATUS_COLOR[detailState.status].text }}>{detailNode.label}</span>
                    <span className="ml-auto text-[9px] font-mono" style={{ color: STATUS_COLOR[detailState.status].text }}>
                      {detailState.status === 'active' ? `%${detailState.pct ?? 0}${detailState.pctReal ? '✓' : '~'} · ${fmtDur(detailState.elapsedSec)}`
                        : (detailState.status === 'done' || detailState.status === 'partial') ? `✓ ${fmtDur(detailState.durationSec)}`
                        : STAT_LABEL[detailState.status]}
                    </span>
                  </div>
                  <ul className="mt-1.5 space-y-1">
                    {(NODE_DETAILS[detailNode.key] ?? []).map((line, i) => (
                      <li key={i} className="flex gap-1.5 text-[10px] leading-snug text-foreground-default">
                        <span className="mt-[4px] h-1 w-1 shrink-0 rounded-full" style={{ background: STATUS_COLOR[detailState.status].ring }} />
                        <span>{line}</span>
                      </li>
                    ))}
                  </ul>
                </>
              ) : <div className="text-[10px] text-foreground-muted">Bir balona tıkla → ne yaptığı burada açıklanır.</div>}
            </div>
            {/* canlı log */}
            <div className="flex items-center justify-between border-b border-border-subtle/60 px-3 py-1">
              <span className="flex items-center gap-1 text-[9px] font-semibold uppercase tracking-wider text-foreground-muted">
                <span className="h-1.5 w-1.5 rounded-full bg-success animate-pulse" />Canlı Log
              </span>
              <span className="text-[8px] text-foreground-disabled">{logEvents.length}</span>
            </div>
            <div className="min-h-0 flex-1 overflow-auto px-2 py-1">
              {logEvents.length === 0 ? (
                <div className="px-1 py-2 text-[10px] text-foreground-muted">Bu film için henüz olay yok.</div>
              ) : logEvents.map((ev, i) => (
                <div key={i} className="flex gap-1.5 px-1 py-0.5 text-[9px] leading-snug">
                  <span className="shrink-0 font-mono text-foreground-disabled">{fmtClock(ev.ts)}</span>
                  <span className={ev.level === 'error' ? 'text-danger' : ev.level === 'warn' ? 'text-warning' : 'text-foreground-muted'}>{ev.summary || ev.kind}</span>
                </div>
              ))}
            </div>
          </div>
          {/* SAĞ: diyagram */}
          <div className="min-h-0 flex-1 overflow-auto bg-[#070a10] p-2">
            <div className="relative mx-auto" style={{ width: CANVAS_W, height: CANVAS_H }}>
              <svg width={CANVAS_W} height={CANVAS_H} className="absolute inset-0" style={{ pointerEvents: 'none' }}>
              {/* POST provenans bölge etiketi */}
              <text x={706} y={448} textAnchor="middle" fontSize="9" fill="#3a4256" style={{ letterSpacing: '0.05em' }}>teslim sonrası · kararı etkilemez</text>
              {EDGES.map((e, i) => {
                const a = nodeById(e.from); const b = nodeById(e.to);
                const dy = b.y - a.y;
                const d = `M ${a.x} ${a.y + 34} C ${a.x} ${a.y + dy * 0.5}, ${b.x} ${b.y - dy * 0.5}, ${b.x} ${b.y - 34}`;
                const act = edgeActive(e); const dn = edgeDone(e);
                const side = e.kind === 'cond' || e.kind === 'post';
                const color = act ? '#f5b301' : dn ? '#1f9d57' : side ? '#222c3a' : '#1c2430';
                return (
                  <g key={i}>
                    <path d={d} fill="none" stroke={color} strokeWidth={act ? 2.4 : 1.5}
                      strokeDasharray={side ? '4 4' : undefined} opacity={dn || act ? 0.9 : side ? 0.6 : 0.5} />
                    {act ? (
                      <>
                        <circle r={4} fill="#ffd860" style={{ filter: 'drop-shadow(0 0 5px #f5b301)' }}>
                          <animateMotion path={d} dur="1.05s" repeatCount="indefinite" />
                        </circle>
                        <circle r={3.5} fill="#ffd860" opacity={0.45}>
                          <animateMotion path={d} dur="1.05s" begin="0.52s" repeatCount="indefinite" />
                        </circle>
                      </>
                    ) : dn ? (
                      <circle r={2.6} fill="#3ddc84" opacity={0.55}>
                        <animateMotion path={d} dur="2.4s" repeatCount="indefinite" />
                      </circle>
                    ) : null}
                  </g>
                );
              })}
            </svg>
            {NODES.map((n) => {
              const st = stateOf(n);
              const c = STATUS_COLOR[st.status];
              const Icon = n.icon;
              return (
                <div key={n.key} onClick={() => setSelectedKey(n.key)} className="absolute flex cursor-pointer flex-col items-center" style={{ left: n.x, top: n.y, transform: 'translate(-50%,-50%)', width: 134 }}>
                  <div className="relative flex h-[54px] w-[54px] items-center justify-center rounded-full border-2"
                    style={{ borderColor: c.ring, background: c.bg, ['--g' as string]: c.ring, animation: c.glow ? 'mitasPulse 1.3s ease-in-out infinite' : undefined, boxShadow: selectedKey === n.key ? '0 0 0 3px rgba(255,255,255,0.3)' : undefined }}>
                    <Icon className="h-6 w-6" style={{ color: c.text }} />
                    {st.status === 'active' && typeof st.pct === 'number' ? (
                      <span className="absolute -bottom-1 rounded-full bg-warning px-1.5 text-[9px] font-bold text-black">%{st.pct}</span>
                    ) : null}
                  </div>
                  <div className="mt-1 text-center">
                    <div className="text-[11px] font-semibold leading-tight" style={{ color: c.text }}>{n.label}</div>
                    {n.sub ? <div className="text-[8.5px] leading-tight text-foreground-disabled">{n.sub}</div> : null}
                    <div className="mt-0.5 text-[9px] font-mono leading-tight">
                      {st.status === 'done' || st.status === 'partial' ? <span className="text-success">✓ {fmtDur(st.durationSec)}</span> : null}
                      {st.status === 'skipped' ? <span className="text-foreground-disabled">atlandı</span> : null}
                      {st.status === 'failed' ? <span className="text-danger font-bold">✕ TAKILDI</span> : null}
                      {st.status === 'active' ? <span className="text-warning">⟳ {fmtDur(st.elapsedSec)}</span> : null}
                    </div>
                  </div>
                </div>
              );
            })}
            </div>
          </div>
        </div>
        {/* alt açıklama */}
        <div className="flex items-center gap-3 border-t border-border-subtle bg-surface/40 px-4 py-1.5 text-[9px] text-foreground-muted">
          <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-full" style={{ background: '#3ddc84' }} />bitti (süre)</span>
          <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-full" style={{ background: '#ffd34d' }} />aktif (%)</span>
          <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-full" style={{ background: '#f1b54a' }} />kısmi</span>
          <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-full" style={{ background: '#ff6b6b' }} />takıldı</span>
          <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-full" style={{ background: '#5b6678' }} />bekliyor/atlandı</span>
          <span className="flex items-center gap-1"><span className="inline-block h-0 w-3 border-t border-dashed border-[#3a4256]" />koşullu / post</span>
          <span className="ml-auto text-foreground-disabled">canlı /api/events · 1.5sn</span>
        </div>
      </div>
    </div>
  );
}
