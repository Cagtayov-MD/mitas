import { Search, SplitSquareHorizontal, Merge, AlertCircle, Info, Lock, Loader2, Radio, Trash2 } from 'lucide-react';
import { Tabs, TabsList, TabsTrigger, TabsContent, ScrollArea, Button, Badge } from './ui';
import { formatClock, segmentConfidence, shouldOfferTurkishTranslation, translateFreeTextToTurkish, type AsrChannelState, type AsrJob, type AsrJobLog, type SegmentTranslationState, type TranslationResult } from '../asr-api';
import { useEffect, useMemo, useRef, useState } from 'react';
import type { LiveSttLine, LiveSttPreviewState, LiveSttStatus } from '../live-stt-preview';

function WipPlaceholder({ title, version }: { title: string, version: string }) {
  return (
    <div className="flex-1 flex flex-col items-center justify-center p-8 text-center gap-4 h-full min-h-[300px]">
      <div className="h-16 w-16 bg-surface border border-border-subtle rounded-full flex items-center justify-center shadow-inner">
        <Lock className="h-6 w-6 text-foreground-disabled" />
      </div>
      <div className="space-y-1">
        <h3 className="text-sm font-semibold text-foreground-default">{title} Yapım Aşamasında</h3>
        <p className="text-xs text-foreground-muted max-w-[250px] mx-auto leading-relaxed">
          Bu modül v{version} sürümünde aktif olacak.
        </p>
      </div>
      <a href="#" className="text-[10px] text-foreground-disabled underline hover:text-foreground-muted cursor-not-allowed">
        İlerleme detayı
      </a>
    </div>
  );
}

// Severity → semantik renk haritası.
// Karar: brief'te tanımlı 3 severity (yüksek/orta/düşük) sırasıyla danger/warning/info'ya bağlanır.
const SEVERITY_BAR_BG: Record<string, string> = {
  'yüksek': 'bg-danger-strong',
  'orta': 'bg-warning-strong',
  'düşük': 'bg-info-strong',
};
const SEVERITY_ICON_TEXT: Record<string, string> = {
  'yüksek': 'text-danger',
  'orta': 'text-warning',
  'düşük': 'text-info',
};

function describeDropReason(reason: string): string {
  if (reason.startsWith('stock_artifact:')) {
    const text = reason.replace('stock_artifact:', '');
    return `Konuşma yerine hazır kalıp/altyazı artefaktı gibi algılandı: "${text}"`;
  }
  if (reason.startsWith('no_speech')) {
    return 'Model bu parçayı konuşma olarak güvenilir bulmadı.';
  }
  if (reason.startsWith('repetition_collapse')) {
    return 'Tekrar eden bozuk transcript üretimi temizlendi.';
  }
  if (reason.startsWith('long_token_artifact')) {
    return 'Aşırı uzun/bozuk kelime çıktısı temizlendi.';
  }
  return reason;
}

interface SidebarProps {
  asrJob: AsrJob | null;
  uploadError: string | null;
  hasMedia: boolean;
  isSttPreviewEnabled: boolean;
  livePreview: LiveSttPreviewState;
  enabledAsrChannels: AsrChannelState;
  selectedSegmentIndex: number | null;
  isTranslatingAll: boolean;
  segmentTranslations: Record<number, SegmentTranslationState>;
  onSelectSegment: (index: number) => void;
  onTranslateSegment: (index: number) => void;
  onTranslateAllSegments: () => void;
}

const LIVE_STATUS_CLASS: Record<LiveSttStatus, string> = {
  idle: 'border-border-subtle text-foreground-muted bg-surface/60',
  ready: 'border-info-border text-info bg-info-subtle',
  listening: 'border-success-subtle text-success bg-success-subtle',
  resolving: 'border-warning-border text-warning bg-warning-subtle',
  paused: 'border-border-mitas text-foreground-muted bg-surface/80',
  error: 'border-danger-subtle text-danger bg-danger-subtle',
};

type ChannelFilter = 'all' | 'L' | 'R';

export function Sidebar({
  asrJob,
  uploadError,
  hasMedia,
  isSttPreviewEnabled,
  livePreview,
  enabledAsrChannels,
  selectedSegmentIndex,
  isTranslatingAll,
  segmentTranslations,
  onSelectSegment,
  onTranslateSegment,
  onTranslateAllSegments,
}: SidebarProps) {
  const segments = asrJob?.segments ?? [];
  const logs = asrJob?.logs ?? [];
  const qualityDrops = asrJob?.summary?.quality_drops ?? 0;
  const rawSegments = asrJob?.summary?.raw_segments ?? 0;
  const dropReasons = Object.entries(asrJob?.archive?.quality?.drop_reasons ?? {});
  const hasTranscript = segments.length > 0;
  const liveBottomRef = useRef<HTMLDivElement | null>(null);
  const logBottomRef = useRef<HTMLDivElement | null>(null);
  const segmentRefs = useRef<Array<HTMLDivElement | null>>([]);
  const hasLiveTranscript = livePreview.lines.length > 0 || livePreview.partialLine !== null;
  const [channelFilter, setChannelFilter] = useState<ChannelFilter>('all');
  const hasLeftChannel = segments.some((segment) => segmentChannelKey(segment) === 'L');
  const hasRightChannel = segments.some((segment) => segmentChannelKey(segment) === 'R');
  const hasSplitChannels = hasLeftChannel && hasRightChannel;
  const translatableSegmentCount = segments.filter(shouldOfferTurkishTranslation).length;
  const activeChannelFilter = hasSplitChannels ? channelFilter : 'all';
  const visibleSegments = segments
    .map((item, idx) => ({ item, idx }))
    .filter(({ item }) => activeChannelFilter === 'all' || segmentChannelKey(item) === activeChannelFilter)
    .filter(({ item }) => {
      const channel = segmentChannelKey(item);
      return !hasSplitChannels || !channel || enabledAsrChannels[channel];
    });

  useEffect(() => {
    if (selectedSegmentIndex === null) {
      return;
    }
    segmentRefs.current[selectedSegmentIndex]?.scrollIntoView({
      block: 'center',
      behavior: 'smooth',
    });
  }, [selectedSegmentIndex]);

  useEffect(() => {
    if (channelFilter !== 'all' && !enabledAsrChannels[channelFilter]) {
      setChannelFilter('all');
    }
  }, [channelFilter, enabledAsrChannels]);

  useEffect(() => {
    if (!isSttPreviewEnabled) {
      return;
    }
    liveBottomRef.current?.scrollIntoView({
      block: 'end',
      behavior: 'smooth',
    });
  }, [isSttPreviewEnabled, livePreview.lines.length, livePreview.partialLine?.text, livePreview.status]);

  useEffect(() => {
    logBottomRef.current?.scrollIntoView({
      block: 'end',
      behavior: 'smooth',
    });
  }, [logs.length]);

  return (
    <div className="w-[450px] bg-app-shell border-l border-border-subtle flex flex-col shrink-0 text-foreground-default">
      <Tabs defaultValue="transcript" className="w-full flex flex-col h-full">
        <div className="border-b border-border-subtle bg-app-shell">
          <TabsList className="w-full grid grid-cols-8 h-auto bg-transparent p-0 rounded-none border-none">
            <TabsTrigger value="queue" className="relative">
              Uyarılar
              {qualityDrops > 0 && <span className="absolute top-1 right-1 w-1.5 h-1.5 bg-danger-strong rounded-full"></span>}
            </TabsTrigger>
            <TabsTrigger value="transcript">ASR</TabsTrigger>
            <TabsTrigger value="faces" className="text-foreground-disabled data-[state=active]:text-foreground-muted">Yüzler</TabsTrigger>
            <TabsTrigger value="tags" className="text-foreground-disabled data-[state=active]:text-foreground-muted">Etiketler</TabsTrigger>
            <TabsTrigger value="ocr" className="text-foreground-disabled data-[state=active]:text-foreground-muted">OCR</TabsTrigger>
            <TabsTrigger value="meta">Bilgi</TabsTrigger>
            <TabsTrigger value="evidence">Kanıt</TabsTrigger>
            <TabsTrigger value="logs">Log</TabsTrigger>
          </TabsList>
        </div>

        <ScrollArea className="flex-1 bg-app-shell">

          {/* ASR warnings tab */}
          <TabsContent value="queue" className="p-0 m-0 border-none h-full">
            <div className="p-3 bg-surface/50 border-b border-border-subtle flex items-center justify-between">
              <h3 className="text-xs font-semibold uppercase tracking-wider text-foreground-strong">ASR Uyarıları</h3>
              <Badge variant={qualityDrops > 0 ? 'danger' : 'success'}>{qualityDrops} uyarı</Badge>
            </div>
            <div className="p-3 flex flex-col gap-3">
              {uploadError || asrJob?.status === 'failed' ? (
                <div className="bg-surface border border-danger-subtle rounded-sm p-3 shadow-sm relative overflow-hidden">
                  <div className="absolute left-0 top-0 bottom-0 w-1 bg-danger-strong"></div>
                  <div className="flex justify-between items-start mb-2 pl-2">
                    <div className="flex items-center gap-2">
                      <AlertCircle className="h-3.5 w-3.5 text-danger" />
                      <span className="text-xs font-semibold text-foreground-strong">ASR Hatası</span>
                    </div>
                    <span className="text-[10px] font-mono text-foreground-muted">şimdi</span>
                  </div>
                  <p className="text-[11px] text-foreground-muted pl-2 leading-relaxed">{uploadError || asrJob?.error}</p>
                </div>
              ) : qualityDrops > 0 ? (
                <div className="bg-surface border border-warning-subtle rounded-sm p-3 shadow-sm relative overflow-hidden">
                  <div className={`absolute left-0 top-0 bottom-0 w-1 ${SEVERITY_BAR_BG['orta']}`}></div>
                  <div className="flex justify-between items-start mb-2 pl-2">
                    <div className="flex items-center gap-2">
                      <AlertCircle className={`h-3.5 w-3.5 ${SEVERITY_ICON_TEXT['orta']}`} />
                      <span className="text-xs font-semibold text-foreground-strong">ASR temizleme filtresi</span>
                    </div>
                    <span className="text-[10px] font-mono text-foreground-muted">{qualityDrops} segment</span>
                  </div>
                  <p className="text-[11px] text-foreground-muted pl-2 leading-relaxed">
                    Ham ASR {rawSegments} segment üretti; {qualityDrops} tanesi güvenilir bulunmadığı için temiz transcript'e alınmadı. Bu OCR/Face hatası değil, sadece ASR çıktısını kirleten parçaları ayıklama adımı.
                  </p>
                  {dropReasons.length > 0 && (
                    <div className="mt-2 pl-2 text-[10px] text-foreground-muted space-y-1">
                      {dropReasons.map(([reason, count]) => (
                        <div key={reason}>
                          <span className="text-warning-strong">{count}x</span> {describeDropReason(reason)}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              ) : (
                <div className="bg-surface border border-border-subtle rounded-sm p-3 text-[11px] text-foreground-muted">
                  {asrJob
                    ? 'ASR uyarısı yok.'
                    : hasMedia
                      ? 'Medya hazır. STT başlatılmadan uyarı üretilemez.'
                      : 'Henüz medya yok.'}
                </div>
              )}
            </div>
          </TabsContent>

          {/* Transcript Tab */}
          <TabsContent value="transcript" className="p-0 m-0 border-none">
            <div className="p-2 border-b border-border-subtle bg-surface/50 flex gap-2">
              <div className="relative flex-1">
                <Search className="absolute left-2 top-1.5 h-3.5 w-3.5 text-foreground-muted" />
                <input
                  type="text"
                  placeholder="Transkript içinde ara..."
                  className="w-full bg-app-shell border border-border-mitas rounded-sm py-1 pl-7 pr-2 text-xs text-foreground-default focus:outline-none focus:border-info-strong"
                />
              </div>
              {!isSttPreviewEnabled && hasTranscript && translatableSegmentCount > 0 ? (
                <Button
                  variant="success"
                  size="xs"
                  className="shrink-0"
                  disabled={isTranslatingAll}
                  onClick={onTranslateAllSegments}
                  title="Yalnızca Türkçe dışı transcript satırlarını Türkçeye çevir"
                >
                  {isTranslatingAll ? <Loader2 className="h-3 w-3 mr-1 animate-spin" /> : <span className="mr-1 font-bold">T</span>}
                  Yabancıları Çevir
                </Button>
              ) : null}
              {isSttPreviewEnabled ? (
                <>
                  <div className={`inline-flex items-center gap-1.5 rounded-sm border px-2 text-[10px] font-semibold ${LIVE_STATUS_CLASS[livePreview.status]}`}>
                    {livePreview.status === 'listening' || livePreview.status === 'resolving' ? (
                      <Loader2 className="h-3 w-3 animate-spin" />
                    ) : (
                      <span className="h-1.5 w-1.5 rounded-full bg-current"></span>
                    )}
                    <span>{livePreview.statusText}</span>
                  </div>
                  <Button variant="outline" size="xs" onClick={livePreview.clearLines} disabled={!hasLiveTranscript} title="Canlı transcript temizle">
                    <Trash2 className="h-3 w-3 mr-1" /> Temizle
                  </Button>
                </>
              ) : (
                <>
                  <Button variant="outline" size="xs"><SplitSquareHorizontal className="h-3 w-3 mr-1"/> Böl</Button>
                  <Button variant="outline" size="xs"><Merge className="h-3 w-3 mr-1"/> Birleştir</Button>
                </>
              )}
            </div>
            {!isSttPreviewEnabled && hasSplitChannels ? (
              <div className="flex items-center gap-1 border-b border-border-subtle bg-surface/30 px-3 py-2">
                {([
                  ['all', 'Tümü'],
                  ['L', 'Kanal 1'],
                  ['R', 'Kanal 2'],
                ] as const).map(([value, label]) => (
                  <Button
                    key={value}
                    variant={channelFilter === value ? 'secondary' : 'ghost'}
                    size="xs"
                    disabled={value !== 'all' && !enabledAsrChannels[value]}
                    onClick={() => setChannelFilter(value)}
                  >
                    {label}
                  </Button>
                ))}
              </div>
            ) : null}
            <div className="p-0 flex flex-col">
              {isSttPreviewEnabled ? (
                <>
                  <div className="border-b border-border-subtle bg-info-subtle/60 px-3 py-2 text-[11px] text-foreground-muted">
                    <div className="flex items-center gap-2 text-info font-semibold uppercase tracking-wider">
                      <Radio className="h-3.5 w-3.5" />
                      Canlı transcript
                    </div>
                    <div className="mt-1">
                      Preview açıkken konuşmalar gecikmeli canlı metin olarak akar. Bu hatta kişi ayırma yok; speaker etiketi batch STT/diarization çıktısından gelir.
                    </div>
                    {livePreview.error ? (
                      <div className="mt-1 text-danger">{livePreview.error}</div>
                    ) : null}
                  </div>
                  {!hasLiveTranscript && (
                    <div className="p-4 text-xs text-foreground-muted leading-relaxed">
                      {hasMedia
                        ? 'Hazır. Play basınca player sesi canlı transcript olarak burada akacak.'
                        : 'Canlı transcript için önce medya yükle.'}
                    </div>
                  )}
                  {hasLiveTranscript ? (
                    <LiveTranscriptFlow lines={livePreview.lines} partialLine={livePreview.partialLine} isWriting={livePreview.status === 'listening' || livePreview.status === 'resolving'} />
                  ) : null}
                  <div ref={liveBottomRef} className="h-1" />
                </>
              ) : !asrJob && (
                <div className="p-4 text-xs text-foreground-muted leading-relaxed">
                  {hasMedia
                    ? 'Medya hazır. STT Başlat düğmesine basınca transcript burada görünecek.'
                    : 'Mock transcript kapalı. Medya yükle, sonra STT Başlat ile model çalıştır.'}
                </div>
              )}
              {!isSttPreviewEnabled && (asrJob?.status === 'queued' || asrJob?.status === 'running') ? (
                <div className="p-4 text-xs text-info leading-relaxed">
                  {asrJob.message || 'Gerçek ASR modeli çalışıyor. Transcript tamamlanınca burada görünecek.'}
                </div>
              ) : null}
              {!isSttPreviewEnabled && asrJob && !hasTranscript && (asrJob.status === 'done' || asrJob.status === 'partial') && (
                <div className="p-4 text-xs text-warning leading-relaxed">
                  ASR tamamlandı ama temiz transcript boş kaldı. Ham çıktılar kalite filtresinde elenmiş olabilir; Uyarılar sekmesinde nedeni görünüyor.
                </div>
              )}
              {!isSttPreviewEnabled && visibleSegments.map(({ item, idx }) => {
                const confidence = segmentConfidence(item);
                const isSelected = selectedSegmentIndex === idx;
                const confidenceLabel = confidence >= 0.85 ? 'yüksek güven' : confidence >= 0.65 ? 'orta güven' : 'düşük güven';
                const confidenceClass = confidence >= 0.85 ? 'text-success-strong' : confidence >= 0.65 ? 'text-warning-strong' : 'text-danger-strong';
                const translationState = segmentTranslations[idx];
                const canTranslate = shouldOfferTurkishTranslation(item);
                return (
                <div
                  key={`${item.start}-${item.end}-${idx}`}
                  ref={(node) => { segmentRefs.current[idx] = node; }}
                  role="button"
                  tabIndex={0}
                  onClick={() => onSelectSegment(idx)}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter' || event.key === ' ') {
                      event.preventDefault();
                      onSelectSegment(idx);
                    }
                  }}
                  className={`group flex gap-3 p-3 border-b border-border-subtle/50 text-sm cursor-pointer outline-none ${
                    isSelected
                      ? 'bg-info-subtle border-l-2 border-l-info-strong shadow-inner'
                      : 'hover:bg-surface/30 border-l-2 border-l-transparent'
                  }`}
                >
                  <div className="w-16 shrink-0 flex flex-col items-start gap-1">
                    <span className="text-[10px] text-info font-mono">{formatClock(item.start)}</span>
                    <span className="text-[9px] text-foreground-disabled font-mono">{formatClock(item.end)}</span>
                  </div>
                  <div className="flex-1">
                    <div className="flex items-center justify-between mb-1">
                      <div className="flex items-center gap-2">
                        <Badge variant="outline" className="text-[9px] cursor-pointer hover:bg-surface-elevated" title="Diarization ses ayrımıdır; kişi kimliği değildir.">
                          {item.speaker || channelLabel(item) || 'ASR'} <Info className="h-2 w-2 ml-1 inline text-foreground-muted" />
                        </Badge>
                        <span className="text-[9px] text-foreground-muted font-mono">{(confidence * 100).toFixed(0)}%</span>
                      </div>
                      <div className="flex items-center gap-1.5">
                        {canTranslate ? (
                          <Button
                            variant={translationState?.status === 'done' ? 'success' : 'outline'}
                            size="xs"
                            disabled={translationState?.status === 'loading'}
                            title="Bu segmenti Türkçeye çevir"
                            onClick={(event) => {
                              event.stopPropagation();
                              onTranslateSegment(idx);
                            }}
                          >
                            {translationState?.status === 'loading' ? (
                              <Loader2 className="h-3 w-3 animate-spin" />
                            ) : (
                              <span className="text-[10px] font-bold">T Çevir</span>
                            )}
                          </Button>
                        ) : null}
                        <span className={`text-[8px] font-medium ${confidenceClass}`}>{confidenceLabel}</span>
                      </div>
                    </div>
                    <div className={`text-[12px] leading-relaxed mt-1.5 ${isSelected ? 'text-foreground-strong' : 'text-foreground-muted'}`}>
                      {item.text}
                    </div>
                    {translationState?.status === 'done' ? (
                      <div className="mt-2 border-l-2 border-l-success-strong bg-success-subtle/40 px-2 py-1.5 text-[11px] leading-relaxed text-foreground-strong">
                        <div className="mb-1 flex items-center justify-between gap-2 text-[8px] font-semibold uppercase tracking-wider text-success">
                          <span>TR çeviri</span>
                          <span className="font-mono text-foreground-muted">
                            {translationModelLabel(translationState.result)}
                          </span>
                        </div>
                        {translationState.result.text}
                      </div>
                    ) : null}
                    {translationState?.status === 'error' ? (
                      <div className="mt-2 border-l-2 border-l-danger-strong bg-danger-subtle/40 px-2 py-1.5 text-[11px] leading-relaxed text-danger">
                        {translationState.error}
                      </div>
                    ) : null}
                  </div>
                </div>
              )})}
            </div>
          </TabsContent>

          {/* WIP Tabs */}
          <TabsContent value="faces" className="p-0 m-0 border-none h-full">
            <WipPlaceholder title="Yüzler" version="0.4" />
          </TabsContent>
          <TabsContent value="tags" className="p-0 m-0 border-none h-full">
            <WipPlaceholder title="Etiketler" version="0.3" />
          </TabsContent>
          <TabsContent value="ocr" className="p-0 m-0 border-none h-full">
            <WipPlaceholder title="OCR" version="0.2" />
          </TabsContent>

          {/* Meta Tab */}
          <TabsContent value="meta" className="p-3 m-0 border-none">
            <div className="bg-surface border border-border-subtle rounded-sm overflow-hidden">
              <div className="p-2 bg-surface-elevated/50 border-b border-border-subtle font-semibold text-xs text-foreground-strong">
                Medya Detayları
              </div>
              <div className="p-0">
                {Object.entries({
                  'Dosya': asrJob?.filename || '-',
                  'Durum': asrJob?.status || 'bekleniyor',
                  'Süre': formatClock(asrJob?.summary?.audio_duration),
                  'Model': asrJob?.summary?.model_name || '-',
                  'Profil': asrJob?.summary?.profile_used || asrJob?.profile || 'fast_with_fallback',
                  'Segment': String(asrJob?.summary?.clean_segments ?? 0),
                  'Çıktı': asrJob?.output_dir || '-',
                }).map(([key, value]) => (
                  <div key={key} className="flex border-b border-border-subtle/50 last:border-0 text-[11px]">
                    <div className="w-2/5 bg-app-shell p-2 text-foreground-muted uppercase tracking-wider font-semibold border-r border-border-subtle/50">{key}</div>
                    <div className="w-3/5 p-2 text-foreground-default font-mono">{value}</div>
                  </div>
                ))}
              </div>
            </div>
          </TabsContent>

          {/* Evidence Tab */}
          <TabsContent value="evidence" className="p-3 m-0 border-none">
             <div className="flex flex-col gap-2">
              {!asrJob && (
                <div className="bg-surface border border-border-subtle rounded-sm p-3 text-[11px] text-foreground-muted">
                  STT/ASR kanıtı üretmek için STT Başlat düğmesini kullan.
                </div>
              )}
              {asrJob && [
                {
                  id: 'asr',
                  action: 'Konuşma → Metin',
                  model: asrJob.summary?.model_name || 'faster-whisper',
                  time: formatClock(0),
                  result: `${asrJob.segments.length} transcript segmenti`,
                  confidence: asrJob.summary?.safety?.safe === false ? 0.5 : 0.9,
                  detail: `Profil: ${asrJob.summary?.profile_used || asrJob.profile}. Çıktı: ${asrJob.output_dir}`,
                },
                {
                  id: 'vad',
                  action: 'VAD Konuşma Tespiti',
                  model: 'Silero VAD',
                  time: formatClock(0),
                  result: `${asrJob.summary?.raw_segments ?? 0} ham segment`,
                  confidence: 0.9,
                  detail: `Toplam süre: ${formatClock(asrJob.summary?.audio_duration)}.`,
                },
              ].map(ev => (
                <div key={ev.id} className="bg-surface border border-border-subtle rounded-sm p-3 flex flex-col gap-2">
                  <div className="flex justify-between items-start">
                    <div className="flex items-center gap-2">
                      <Info className="h-3.5 w-3.5 text-info-strong" />
                      <span className="text-[11px] font-semibold text-foreground-strong">{ev.action}</span>
                    </div>
                    <span className="text-[9px] font-mono text-foreground-muted">{ev.time}</span>
                  </div>
                  <div className="bg-app-shell p-2 rounded-sm border border-border-subtle">
                    <div className="text-[11px] text-foreground-default font-mono mb-1">{ev.result}</div>
                    <div className="text-[9px] text-foreground-muted">{ev.detail}</div>
                  </div>
                  <div className="flex justify-between items-center text-[9px] text-foreground-muted font-mono">
                    <span>Model: {ev.model}</span>
                    <span>Güven: {(ev.confidence * 100).toFixed(1)}%</span>
                  </div>
                </div>
              ))}
            </div>
          </TabsContent>

          {/* Log Tab */}
          <TabsContent value="logs" className="p-0 m-0 border-none">
            <div className="p-3 bg-surface/50 border-b border-border-subtle flex items-center justify-between">
              <h3 className="text-xs font-semibold uppercase tracking-wider text-foreground-strong">İşlem Logu</h3>
              <Badge variant={asrJob?.status === 'failed' ? 'danger' : logs.length > 0 ? 'secondary' : 'outline'}>
                {logs.length} kayıt
              </Badge>
            </div>
            <div className="p-3 flex flex-col gap-2">
              {!asrJob ? (
                <div className="bg-surface border border-border-subtle rounded-sm p-3 text-[11px] text-foreground-muted">
                  Henüz kalıcı ASR logu yok. STT Başlat ile yeni job oluşunca kayıtlar burada tutulur.
                </div>
              ) : logs.length === 0 ? (
                <div className="bg-surface border border-border-subtle rounded-sm p-3 text-[11px] text-foreground-muted">
                  Job var ama log kaydı henüz oluşmadı.
                </div>
              ) : (
                logs.map((entry, index) => (
                  <LogEntry key={`${entry.ts}-${entry.stage}-${index}`} entry={entry} />
                ))
              )}
              <div ref={logBottomRef} className="h-1" />
            </div>
          </TabsContent>

        </ScrollArea>
      </Tabs>
    </div>
  );
}

function LogEntry({ entry }: { entry: AsrJobLog }) {
  const isError = entry.level === 'error';
  return (
    <div className={`rounded-sm border px-2.5 py-2 text-[11px] ${isError ? 'border-danger-subtle bg-danger-subtle/30' : 'border-border-subtle bg-surface/60'}`}>
      <div className="mb-1 flex items-center justify-between gap-2 font-mono text-[9px] uppercase tracking-wider text-foreground-muted">
        <span>{formatLogTime(entry.ts)}</span>
        <span>{entry.stage || 'işlem'}{typeof entry.progress_percent === 'number' ? ` · ${entry.progress_percent}%` : ''}</span>
      </div>
      <div className={isError ? 'text-danger' : 'text-foreground-default'}>{entry.message}</div>
    </div>
  );
}

function formatLogTime(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

function LiveTranscriptFlow({
  lines,
  partialLine,
  isWriting,
}: {
  lines: LiveSttLine[];
  partialLine: LiveSttLine | null;
  isWriting: boolean;
}) {
  const [translationState, setTranslationState] = useState<SegmentTranslationState | null>(null);
  const targetText = useMemo(() => {
    const parts = lines.map((line) => line.text.trim()).filter(Boolean);
    const partialText = partialLine?.text.trim();
    if (partialText) {
      parts.push(partialText);
    }
    return prepareLiveFlowText(combineLiveFlowParts(parts), isWriting);
  }, [isWriting, lines, partialLine?.text]);
  const canTranslateLiveText = shouldOfferTurkishTranslation({ text: targetText, language: null });

  useEffect(() => {
    setTranslationState(null);
  }, [targetText]);

  const handleTranslateLiveText = async () => {
    if (!targetText.trim()) {
      return;
    }
    setTranslationState({ status: 'loading' });
    try {
      const result = await translateFreeTextToTurkish(targetText, 'en');
      setTranslationState({ status: 'done', result });
    } catch (error) {
      setTranslationState({
        status: 'error',
        error: error instanceof Error ? error.message : 'Çeviri başarısız oldu.',
      });
    }
  };

  return (
    <div className="border-b border-border-subtle/50 border-l-2 border-l-info-strong/70 bg-surface/20 p-3 text-sm">
      <div className="min-w-0">
        <div className="flex items-center justify-between mb-1">
          <div className="flex items-center gap-2">
            <Badge variant="outline" className="text-[9px]" title="Live Preview şu an speaker diarization çalıştırmaz.">
              LIVE
            </Badge>
          </div>
          <div className="flex items-center gap-1.5">
            {canTranslateLiveText ? (
              <Button
                variant={translationState?.status === 'done' ? 'success' : 'outline'}
                size="icon-xs"
                disabled={translationState?.status === 'loading'}
                title="Canlı transcript metnini Türkçeye çevir"
                onClick={handleTranslateLiveText}
              >
                {translationState?.status === 'loading' ? (
                  <Loader2 className="h-3 w-3 animate-spin" />
                ) : (
                  <span className="text-[10px] font-bold">T</span>
                )}
              </Button>
            ) : null}
            <div className="flex items-center gap-1 text-[8px] font-medium text-info">
              {isWriting ? <Loader2 className="h-3 w-3 animate-spin" /> : null}
              <span>{isWriting ? 'yazılıyor' : 'canlı'}</span>
            </div>
          </div>
        </div>
        <div className="mt-2 min-h-[120px] whitespace-pre-wrap text-[13px] leading-7 text-foreground-strong">
          <FlowingTypewriterText text={targetText} active />
        </div>
        {translationState?.status === 'done' ? (
          <div className="mt-3 border-l-2 border-l-success-strong bg-success-subtle/40 px-2 py-1.5 text-[11px] leading-relaxed text-foreground-strong">
            <div className="mb-1 flex items-center justify-between gap-2 text-[8px] font-semibold uppercase tracking-wider text-success">
              <span>TR çeviri</span>
              <span className="font-mono text-foreground-muted">
                {translationModelLabel(translationState.result)}
              </span>
            </div>
            {translationState.result.text}
          </div>
        ) : null}
        {translationState?.status === 'error' ? (
          <div className="mt-3 border-l-2 border-l-danger-strong bg-danger-subtle/40 px-2 py-1.5 text-[11px] leading-relaxed text-danger">
            {translationState.error}
          </div>
        ) : null}
      </div>
    </div>
  );
}

function translationModelLabel(result: TranslationResult): string {
  if (result.model === 'source-tr') {
    return 'orijinal Türkçe';
  }
  return `${result.model}${result.cache_hit ? ' · cache' : ''}`;
}

function segmentChannelKey(segment: { channel?: string | null }): 'L' | 'R' | null {
  const value = String(segment.channel ?? '').trim().toUpperCase();
  if (value === 'L' || value === 'LEFT' || value === '1' || value === 'KANAL 1') {
    return 'L';
  }
  if (value === 'R' || value === 'RIGHT' || value === '2' || value === 'KANAL 2') {
    return 'R';
  }
  return null;
}

function channelLabel(segment: { channel?: string | null }): string | null {
  const channel = segmentChannelKey(segment);
  if (channel === 'L') {
    return 'Kanal 1';
  }
  if (channel === 'R') {
    return 'Kanal 2';
  }
  return null;
}

function FlowingTypewriterText({ text, active }: { text: string; active: boolean }) {
  const [visibleText, setVisibleText] = useState(active ? '' : text);

  useEffect(() => {
    if (!active) {
      setVisibleText(text);
      return undefined;
    }

    if (!text) {
      setVisibleText('');
      return undefined;
    }

    const interval = window.setInterval(() => {
      setVisibleText((current) => {
        if (current === text) {
          return current;
        }
        if (text.startsWith(current)) {
          const remaining = text.length - current.length;
          return text.slice(0, current.length + typewriterStep(remaining));
        }
        const commonLength = commonPrefixLength(current, text);
        return text.slice(0, Math.min(text.length, commonLength + 1));
      });
    }, 38);
    return () => window.clearInterval(interval);
  }, [active, text]);

  return (
    <>
      {visibleText}
      {active ? (
        <span className="ml-0.5 inline-block h-3 w-px translate-y-0.5 animate-pulse bg-info"></span>
      ) : null}
    </>
  );
}

function prepareLiveFlowText(text: string, isWriting: boolean): string {
  const normalized = text.replace(/\s+/g, ' ').trim();
  if (!isWriting || !normalized || hasStrongEnding(normalized)) {
    return normalized;
  }

  const lastBoundary = findLastSentenceBoundary(normalized);
  const head = lastBoundary >= 0 ? normalized.slice(0, lastBoundary + 1).trim() : '';
  const tail = lastBoundary >= 0 ? normalized.slice(lastBoundary + 1).trim() : normalized;
  if (!tail) {
    return normalized;
  }

  const tailWords = tail.split(/\s+/).filter(Boolean);
  if (tailWords.length <= 3 || tail.length <= 22) {
    return head;
  }

  const stableTail = tailWords.slice(0, -1).join(' ');
  return [head, stableTail].filter(Boolean).join(' ').trim();
}

function combineLiveFlowParts(parts: string[]): string {
  return parts.reduce((merged, part) => appendLiveFlowPart(merged, part), '');
}

function appendLiveFlowPart(current: string, next: string): string {
  const normalizedNext = next.replace(/\s+/g, ' ').trim();
  if (!normalizedNext) {
    return current;
  }
  if (!current) {
    return normalizedNext;
  }

  const currentKey = normalizeLiveTextKey(current);
  const nextKey = normalizeLiveTextKey(normalizedNext);
  if (currentKey.endsWith(nextKey)) {
    return current;
  }
  if (nextKey.startsWith(currentKey)) {
    return normalizedNext;
  }

  const currentWords = current.split(/\s+/).filter(Boolean);
  const nextWords = normalizedNext.split(/\s+/).filter(Boolean);
  const currentKeys = currentWords.map(normalizeLiveWordKey);
  const nextKeys = nextWords.map(normalizeLiveWordKey);
  const maxOverlap = Math.min(currentKeys.length, nextKeys.length, 24);

  for (let overlap = maxOverlap; overlap > 0; overlap -= 1) {
    const currentTail = currentKeys.slice(currentKeys.length - overlap);
    const nextHead = nextKeys.slice(0, overlap);
    if (currentTail.every((word, index) => word && word === nextHead[index])) {
      const newWords = nextWords.slice(overlap).join(' ');
      return newWords ? `${current} ${newWords}` : current;
    }
  }

  return `${current} ${normalizedNext}`;
}

function normalizeLiveTextKey(text: string): string {
  return text
    .replace(/\s+/g, ' ')
    .trim()
    .toLocaleLowerCase('tr-TR');
}

function normalizeLiveWordKey(word: string): string {
  return word
    .replace(/^[^\p{L}\p{N}]+|[^\p{L}\p{N}]+$/gu, '')
    .toLocaleLowerCase('tr-TR');
}

function hasStrongEnding(text: string): boolean {
  return /[.!?…][)"'»”’\]]*$/.test(text);
}

function findLastSentenceBoundary(text: string): number {
  let boundary = -1;
  for (const match of text.matchAll(/[.!?…]/g)) {
    boundary = match.index ?? boundary;
  }
  return boundary;
}

function commonPrefixLength(left: string, right: string): number {
  const limit = Math.min(left.length, right.length);
  let index = 0;
  while (index < limit && left[index] === right[index]) {
    index += 1;
  }
  return index;
}

function typewriterStep(remaining: number): number {
  if (remaining > 140) {
    return 5;
  }
  if (remaining > 80) {
    return 4;
  }
  if (remaining > 40) {
    return 3;
  }
  if (remaining > 18) {
    return 2;
  }
  return 1;
}
