import { useEffect, useRef, useState } from 'react';
import {
  AudioLines, FileCheck2, FileText, FolderCheck, FolderClock, ScanText,
  Scissors, Sparkles, Video, X, ShieldCheck, Layers,
} from 'lucide-react';

// MITAS pipeline CANLI diyagramı — /api/events (system_events.jsonl) aşama event'lerini
// node-graph'a döker: hangi aşamadayız, geçmiş aşamalar kaç sn, aktif % kaç, nerede TAKILDI.
// Backend'e dokunmaz; sadece var olan /api/events + /api/flow-queue/worker'ı okur.

interface PipelineDiagramProps {
  open: boolean;
  onClose: () => void;
  fallbackFilename?: string;        // batch koşmuyorsa tek-klip adı
  mediaResolution?: string | null;  // tek-klip bağlamında gösterilir
  sourcePath?: string | null;
  profileLabel?: string;
}

interface SysEvent { ts?: string; kind?: string; level?: string; filename?: string; summary?: string }

type NodeStatus = 'waiting' | 'active' | 'done' | 'partial' | 'skipped' | 'failed';

interface NodeDef {
  key: string;
  x: number;            // mantıksal koordinat (CANVAS_W x CANVAS_H içinde)
  y: number;
  label: string;
  sub?: string;
  icon: React.ComponentType<{ className?: string; style?: React.CSSProperties }>;
  stage: string;        // hangi aşama event grubuna bağlı (durum bundan gelir)
}

interface EdgeDef { from: string; to: string }

const CANVAS_W = 760;
const CANVAS_H = 1000;

// Aşama bağımlılıkları (paralel dallar): OCR→Künye ve ASR→Özet AYRI; ikisi PDF'te birleşir.
const DEPS: Record<string, string[]> = {
  coz: [], ocr: ['coz'], asr: ['coz'],
  credit: ['ocr'], ozet: ['asr'],
  pdf: ['credit', 'ozet'], v4: ['pdf'], qc: ['v4'],
};

// Aşama → event kind eşlemesi (pipeline'ın yaydığı gerçek kind'ler)
const STAGE_KIND: Record<string, { start?: string; done?: string; partial?: string; skip?: string; fail?: string; expectSec: number }> = {
  coz:    { start: 'media_imported', done: 'cozumleme_completed', fail: 'cozumleme_failed', expectSec: 8 },
  ocr:    { start: 'ocr_started', done: 'ocr_completed', partial: 'ocr_partial', fail: 'ocr_failed', expectSec: 170 },
  asr:    { start: 'asr_started', done: 'asr_completed', fail: 'asr_failed', expectSec: 170 },
  credit: { done: 'credit_text_completed', fail: 'credit_text_failed', expectSec: 15 },
  ozet:   { done: 'ozet_completed', skip: 'ozet_atlandi', expectSec: 18 },
  pdf:    { done: 'pdf_completed', partial: 'pdf_partial', fail: 'pdf_failed', expectSec: 45 },
  v4:     { done: 'v4_finalize_completed', skip: 'v4_finalize_skipped', fail: 'v4_finalize_failed', expectSec: 95 },
  qc:     { done: 'qwen_final_qc', skip: 'qwen_final_qc_skipped', expectSec: 25 },
};

const NODES: NodeDef[] = [
  { key: 'video',  x: 380, y: 54,  label: 'Video',        sub: 'kaynak (yerinde)',            icon: Video,       stage: 'video' },
  { key: 'coz',    x: 380, y: 150, label: 'Çöz / ffmpeg', sub: 'frame + ses ayır',            icon: Scissors,    stage: 'coz' },
  // SOL DAL — OCR (görüntü)
  { key: 'oneocr', x: 165, y: 262, label: 'OneOCR',       sub: 'jenerik oku',                 icon: ScanText,    stage: 'ocr' },
  { key: 'glm',    x: 315, y: 262, label: 'GLM',          sub: 'jenerik oku',                 icon: ScanText,    stage: 'ocr' },
  { key: 'ocrm',   x: 240, y: 378, label: 'OCR birleş',   sub: 'OneOCR ∥ GLM mutabakat',      icon: Layers,      stage: 'ocr' },
  { key: 'credit', x: 240, y: 492, label: 'Künye / Rol',  sub: 'OCR metni · KB + kurallar',   icon: FileCheck2,  stage: 'credit' },
  // SAĞ DAL — ASR (ses) → Özet (Claude, paralel)
  { key: 'asr',    x: 585, y: 262, label: 'ASR',          sub: 'LID + transkript',            icon: AudioLines,  stage: 'asr' },
  { key: 'ozet',   x: 585, y: 420, label: 'Özet',         sub: 'transcript → Claude (async)', icon: Sparkles,    stage: 'ozet' },
  // BİRLEŞ
  { key: 'pdf',    x: 400, y: 610, label: 'PDF',          sub: 'künye + özet + ses/altyazı',  icon: FileText,    stage: 'pdf' },
  { key: 'v4',     x: 400, y: 710, label: 'V4-Final',     sub: 'büyük harf · afiş · format',  icon: Sparkles,    stage: 'v4' },
  { key: 'qc',     x: 400, y: 810, label: 'QC',           sub: 'qwen kalite kontrol',         icon: ShieldCheck, stage: 'qc' },
  { key: 'hazir',  x: 270, y: 918, label: 'HAZIR',        sub: 'teslime hazır',               icon: FolderCheck, stage: 'route_hazir' },
  { key: 'kontrol',x: 530, y: 918, label: 'KONTROL',      sub: 'gözden geçmeli',              icon: FolderClock, stage: 'route_kontrol' },
];

const EDGES: EdgeDef[] = [
  { from: 'video', to: 'coz' },
  { from: 'coz', to: 'oneocr' }, { from: 'coz', to: 'glm' }, { from: 'coz', to: 'asr' },
  { from: 'oneocr', to: 'ocrm' }, { from: 'glm', to: 'ocrm' },
  { from: 'ocrm', to: 'credit' },
  { from: 'asr', to: 'ozet' },                 // ASR → Özet (paralel, Claude)
  { from: 'credit', to: 'pdf' }, { from: 'ozet', to: 'pdf' }, { from: 'asr', to: 'pdf' },  // ses/altyazı da ASR'dan
  { from: 'pdf', to: 'v4' }, { from: 'v4', to: 'qc' },
  { from: 'qc', to: 'hazir' }, { from: 'qc', to: 'kontrol' },
];

// Her balonun TAM ne yaptığı — yüzeysel ama açıklayıcı (madde madde).
const NODE_DETAILS: Record<string, string[]> = {
  video:   ['Kaynak video AĞ YOLUNDAN okunur (kopyalanmaz)', 'Süre / çözünürlük / fps ölçülür (ffprobe)'],
  coz:     ['ffmpeg: ses ayrıştırılır → 16 kHz wav', 'Görüntü kareleri çıkarılır (giriş + çıkış jeneriği)', 'Çözünürlük / süre / fps ölçülür'],
  oneocr:  ['OneOCR ile jenerik kareleri okunur', 'Türkçe metin çıkarılır'],
  glm:     ['GLM-OCR ile jenerik kareleri okunur (2. motor)', 'Mutabakat için OneOCR\'dan AYRI okuma'],
  ocrm:    ['OneOCR ∥ GLM çıktısı mutabakatla BİRLEŞTİRİLİR', 'Tek temiz künye metni (kunye.txt) üretilir'],
  credit:  ['OCR metninden isim → ROL eşlemesi (LLM)', 'KB çapraz-kontrol ile kimlik teyidi', 'Pikselden OKUMAZ: her isim OCR metninde olmalı (halüsinasyon kalkanı)'],
  asr:     ['Kanal-dil tespiti (MMS-LID)', 'Kürtçe / desteklenmeyen dil → ASR atlanır', 'Whisper large-v3-turbo ile transkript'],
  ozet:    ['ASR transkriptinden Sonnet/Claude ile özet (async)', 'SABİT PROMPT: 3-4 cümle · 50-60 kelime', 'Olay örgüsü + SPOİLER içerir', 'Transkript yoksa atlanır'],
  pdf:     ['Künye + özet + ses&altyazı → PDF', 'Afiş çekilir (TMDB)', 'Ses / altyazı kanal-dil bloğu eklenir'],
  v4:      ['BÜYÜK HARF (TR-İ duyarlı)', 'Yapım ekibi: SADECE Yönetmen + Yapımcı', 'KB ile TÜR / afiş dolgu', 'Final düzen (efektsiz)'],
  qc:      ['Afiş durumu kontrol edilir', 'Özet durumu kontrol edilir', 'Büyük-harf kontrol edilir', 'Latin-dışı alfabe kontrol edilir', 'Türkçe karakter bozukluğu kontrol edilir', '(yerel qwen kalite kontrol)'],
  hazir:   ['Karar = HAZIR', 'HAZIR/ klasörüne teslim edilir'],
  kontrol: ['Karar = KONTROL (gözden geçmeli)', 'KONTROL/ klasörüne ayrılır'],
};

function tsMs(s?: string): number { const v = s ? Date.parse(s) : NaN; return Number.isFinite(v) ? v : NaN; }
function fmtClock(ts?: string): string { const m = tsMs(ts); if (!Number.isFinite(m)) return '--:--:--'; const d = new Date(m); return d.toLocaleTimeString('tr-TR', { hour12: false }); }

interface StageState { status: NodeStatus; durationSec?: number; elapsedSec?: number; pct?: number }

function computeStages(events: SysEvent[], focusFile: string | null, isProcessing: boolean, nowMs: number): {
  stages: Record<string, StageState>; karar: 'hazir' | 'kontrol' | null;
} {
  const stages: Record<string, StageState> = {};
  if (!focusFile) return { stages, karar: null };
  const evs = events.filter((e) => e.filename === focusFile && e.kind).sort((a, b) => tsMs(a.ts) - tsMs(b.ts));
  const lastTsOf = (kind?: string): number => {
    if (!kind) return NaN;
    for (let i = evs.length - 1; i >= 0; i--) if (evs[i].kind === kind) return tsMs(evs[i].ts);
    return NaN;
  };
  const fin = (n: number) => Number.isFinite(n);
  const order = ['coz', 'ocr', 'asr', 'credit', 'ozet', 'pdf', 'v4', 'qc'];
  const endTs: Record<string, number> = {};
  // 1) terminal durum + bitiş zamanı
  for (const key of order) {
    const k = STAGE_KIND[key];
    const fail = lastTsOf(k.fail), done = lastTsOf(k.done), partial = lastTsOf(k.partial), skip = lastTsOf(k.skip);
    let status: NodeStatus = 'waiting'; let e = NaN;
    if (fin(fail)) { status = 'failed'; e = fail; }
    else if (fin(done)) { status = 'done'; e = done; }
    else if (fin(partial)) { status = 'partial'; e = partial; }
    else if (fin(skip)) { status = 'skipped'; e = skip; }
    stages[key] = { status };
    if (fin(e)) endTs[key] = e;
  }
  const depEnds = (key: string) => DEPS[key].map((d) => endTs[d]).filter(fin);
  const depsOk = (key: string) => DEPS[key].every((d) => ['done', 'skipped', 'partial'].includes(stages[d]?.status));
  const baseTsOf = (key: string, startEv: number): number => {
    if (fin(startEv)) return startEv;
    if (key === 'coz') return lastTsOf('media_imported');
    const de = depEnds(key);
    return de.length ? Math.max(...de) : NaN;
  };
  // 2) süre + AKTİF (bağımlılık-tabanlı → OCR∥ASR ve Künye∥Özet paralel doğru işler)
  for (const key of order) {
    const k = STAGE_KIND[key];
    const st = stages[key];
    const startEv = lastTsOf(k.start);
    const base = baseTsOf(key, startEv);
    if (['done', 'partial', 'failed'].includes(st.status) && fin(endTs[key]) && fin(base) && endTs[key] >= base) {
      st.durationSec = (endTs[key] - base) / 1000;
    }
    if (isProcessing && st.status === 'waiting' && (fin(startEv) || depsOk(key))) {
      st.status = 'active';
      if (fin(base)) {
        st.elapsedSec = Math.max(0, (nowMs - base) / 1000);
        st.pct = Math.min(98, Math.round((st.elapsedSec / k.expectSec) * 100));
      }
    }
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
          fetch('/api/events?limit=300', { cache: 'no-store' }),
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

  // genel ilerleme
  const order = ['coz', 'ocr', 'asr', 'credit', 'ozet', 'pdf', 'v4', 'qc'];
  const doneCount = order.filter((k) => ['done', 'skipped', 'partial'].includes(stages[k]?.status)).length;
  const activeNode = NODES.find((n) => stateOf(n).status === 'active');
  const failedNode = NODES.find((n) => stateOf(n).status === 'failed');

  // SOL panel: seçili (ya da takılan/aktif) balonun detayı + bu filmin canlı log'u
  const detailNode = NODES.find((n) => n.key === (selectedKey ?? (failedNode ?? activeNode)?.key)) ?? null;
  const detailState = detailNode ? stateOf(detailNode) : null;
  const logEvents = (focusFile ? events.filter((e) => e.filename === focusFile) : [])
    .slice().sort((a, b) => tsMs(b.ts) - tsMs(a.ts)).slice(0, 80);

  const edgeActive = (e: EdgeDef) => stateOf(nodeById(e.to)).status === 'active';
  const edgeDone = (e: EdgeDef) => ['done', 'skipped', 'partial'].includes(stateOf(nodeById(e.to)).status);

  const headline = !focusFile ? 'Şu an işlenen film yok' : failedNode ? `TAKILDI: ${failedNode.label}` : activeNode ? `İşleniyor: ${activeNode.label}` : karar ? `Bitti → ${karar === 'hazir' ? 'HAZIR' : 'KONTROL'}` : 'Hazırlanıyor';

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
      <div className="relative flex max-h-[92vh] w-full max-w-[1160px] flex-col overflow-hidden rounded-md border border-border-mitas bg-app-shell shadow-2xl" onClick={(e) => e.stopPropagation()}>
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
            <span className="rounded-sm bg-surface px-2 py-0.5 text-[10px] text-foreground-muted">{doneCount}/8 aşama</span>
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
                      {detailState.status === 'active' ? `%${detailState.pct ?? 0} · ${fmtDur(detailState.elapsedSec)}`
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
              {EDGES.map((e, i) => {
                const a = nodeById(e.from); const b = nodeById(e.to);
                const dy = b.y - a.y;
                const d = `M ${a.x} ${a.y + 34} C ${a.x} ${a.y + dy * 0.5}, ${b.x} ${b.y - dy * 0.5}, ${b.x} ${b.y - 34}`;
                const act = edgeActive(e); const dn = edgeDone(e);
                const color = act ? '#f5b301' : dn ? '#1f9d57' : '#1c2430';
                return (
                  <g key={i}>
                    <path d={d} fill="none" stroke={color} strokeWidth={act ? 2.4 : 1.5} opacity={dn || act ? 0.9 : 0.5} />
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
                <div key={n.key} onClick={() => setSelectedKey(n.key)} className="absolute flex cursor-pointer flex-col items-center" style={{ left: n.x, top: n.y, transform: 'translate(-50%,-50%)', width: 150 }}>
                  <div className="relative flex h-[58px] w-[58px] items-center justify-center rounded-full border-2"
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
          <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-full" style={{ background: '#ff6b6b' }} />takıldı</span>
          <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-full" style={{ background: '#5b6678' }} />bekliyor</span>
          <span className="ml-auto text-foreground-disabled">canlı /api/events · 1.5sn</span>
        </div>
      </div>
    </div>
  );
}
