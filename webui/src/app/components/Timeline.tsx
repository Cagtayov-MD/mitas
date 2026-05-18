import { Layers, FileText, User, Type, Tag, Image, AlertTriangle, ZoomIn, ZoomOut, Lock, Volume2, Music, X, Languages, Maximize2 } from 'lucide-react';
import { ScrollArea, Button } from './ui';
import { useState, useEffect, useRef } from 'react';
import type { PointerEvent, MouseEvent } from 'react';
import type { AsrChannelKey, AsrChannelState, AsrJob, AsrSegment, PlaybackState } from '../asr-api';
import { formatClock } from '../asr-api';

type TrackStatus = 'active' | 'wip';
type TrackIntent = 'warning' | 'info' | 'muted';

interface TimelineTrack {
  id: string;
  label: string;
  icon: typeof AlertTriangle;
  status: TrackStatus;
  intent: TrackIntent;
  channel?: 'L' | 'R';
}

const TIMELINE_HEAD_TRACKS: TimelineTrack[] = [
  { id: 'warn',  label: 'Uyarılar',          icon: AlertTriangle, status: 'active', intent: 'warning' },
];

const TIMELINE_TAIL_TRACKS: TimelineTrack[] = [
  { id: 'audio', label: 'Ses Aktivitesi',    icon: Volume2,       status: 'wip',    intent: 'muted' },
  { id: 'song',  label: 'Şarkı Performansı', icon: Music,         status: 'wip',    intent: 'muted' },
  { id: 'faces', label: 'Yüzler',            icon: User,          status: 'wip',    intent: 'muted' },
  { id: 'ocr',   label: 'Ekran Yazısı (KJ)', icon: Type,          status: 'wip',    intent: 'muted' },
  { id: 'tags',  label: 'Görsel Etiketler',  icon: Tag,           status: 'wip',    intent: 'muted' },
  { id: 'logos', label: 'Logolar',           icon: Image,         status: 'wip',    intent: 'muted' },
];

const LABEL_WIDTH_PX = 176;
const MIN_TIMELINE_WIDTH_PX = 1000;

const INTENT_BG: Record<TrackIntent, string> = {
  warning: 'bg-warning-subtle',
  info: 'bg-info-subtle',
  muted: 'bg-surface-elevated/20',
};
const INTENT_BORDER: Record<TrackIntent, string> = {
  warning: 'border-warning-border',
  info: 'border-info-border',
  muted: 'border-surface-elevated/30',
};
const INTENT_MARKER: Record<TrackIntent, string> = {
  warning: 'bg-warning-strong',
  info: 'bg-info',
  muted: 'bg-foreground-disabled/40',
};
const INTENT_LABEL_TEXT: Record<TrackIntent, string> = {
  warning: 'text-warning-strong/80',
  info: 'text-foreground-muted',
  muted: 'text-foreground-disabled',
};
const INTENT_ICON_TEXT: Record<TrackIntent, string> = {
  warning: 'text-warning-strong',
  info: 'text-foreground-muted',
  muted: 'text-foreground-disabled',
};

interface TimelineProps {
  asrJob: AsrJob | null;
  playback: PlaybackState;
  enabledAsrChannels: AsrChannelState;
  selectedSegmentIndex: number | null;
  inPoint: number | null;
  outPoint: number | null;
  onSeek: (time: number) => void;
  onSetInPoint: (t: number | null) => void;
  onSetOutPoint: (t: number | null) => void;
  onToggleAsrChannel: (channel: AsrChannelKey) => void;
  onSelectSegment: (index: number) => void;
  onTranslateRange: (from: number, to: number) => void;
}

function segmentStyle(segment: AsrSegment, duration: number | undefined) {
  const total = Math.max(duration || segment.end || 1, 1);
  const left = Math.max(0, Math.min(99, (segment.start / total) * 100));
  const width = Math.max(0.75, Math.min(100 - left, ((segment.end - segment.start) / total) * 100));
  return { left: `${left}%`, width: `${width}%` };
}

function wordMarkerStyle(segment: AsrSegment, word: NonNullable<AsrSegment['word_timestamps']>[number]) {
  const span = Math.max(0.001, segment.end - segment.start);
  const left = Math.max(0, Math.min(100, ((word.start - segment.start) / span) * 100));
  return { left: `${left}%` };
}

function niceMarkerInterval(durationSec: number): number {
  if (durationSec <= 120) return 10;
  if (durationSec <= 600) return 60;
  if (durationSec <= 3600) return 300;
  return 1800;
}

function timeMarkers(durationSec: number, interval: number): number[] {
  if (durationSec <= 0) return [];
  const markers: number[] = [];
  for (let t = 0; t < durationSec; t += interval) {
    markers.push(t);
  }
  if (markers[markers.length - 1] !== durationSec) {
    markers.push(durationSec);
  }
  return markers;
}

interface ContextMenu {
  x: number;
  y: number;
  time: number;
}

export function Timeline({
  asrJob,
  playback,
  enabledAsrChannels,
  selectedSegmentIndex,
  inPoint,
  outPoint,
  onSeek,
  onSetInPoint,
  onSetOutPoint,
  onToggleAsrChannel,
  onSelectSegment,
  onTranslateRange,
}: TimelineProps) {
  const [zoomLevel, setZoomLevel] = useState(1);
  const [viewportWidth, setViewportWidth] = useState(0);
  const [contextMenu, setContextMenu] = useState<ContextMenu | null>(null);
  const scrollAreaRef = useRef<HTMLDivElement | null>(null);

  const segments = asrJob?.segments ?? [];
  const duration = playback.duration || asrJob?.summary?.audio_duration || 0;
  const qualityDrops = asrJob?.summary?.quality_drops ?? 0;
  const uncoveredRanges = asrJob?.summary?.safety?.diagnostics?.uncovered_vad_ranges ?? [];
  const hasLeftChannel = segments.some((s) => segmentChannelKey(s) === 'L');
  const hasRightChannel = segments.some((s) => segmentChannelKey(s) === 'R');
  const speechTracks: TimelineTrack[] = hasLeftChannel && hasRightChannel
    ? [
        { id: 'asr-l', label: 'ASR Kanal 1', icon: FileText, status: 'active', intent: 'info', channel: 'L' },
        { id: 'asr-r', label: 'ASR Kanal 2', icon: FileText, status: 'active', intent: 'info', channel: 'R' },
      ]
    : [{ id: 'asr', label: 'Konuşma ASR', icon: FileText, status: 'active', intent: 'info' }];
  const timelineTracks = [...TIMELINE_HEAD_TRACKS, ...speechTracks, ...TIMELINE_TAIL_TRACKS];

  const playheadPercent = duration > 0 ? Math.max(0, Math.min(100, (playback.currentTime / duration) * 100)) : 0;
  const playheadStyle = {
    left: `calc(11rem + ${playheadPercent}% - ${(playheadPercent / 100) * 11}rem)`,
  };

  const inPercent  = inPoint  != null && duration > 0 ? Math.max(0, Math.min(100, (inPoint  / duration) * 100)) : null;
  const outPercent = outPoint != null && duration > 0 ? Math.max(0, Math.min(100, (outPoint / duration) * 100)) : null;

  const hasSelection = inPercent !== null && outPercent !== null && outPercent > inPercent;
  const selectionHasSegments = hasSelection && segments.some(
    (s) => s.start < outPoint! && s.end > inPoint!
  );

  // Keyboard shortcuts: I = in-point, O = out-point
  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;
      if (e.key === 'i' || e.key === 'İ' || e.key === 'ı' || e.key === 'I' || e.code === 'KeyI') onSetInPoint(playback.currentTime);
      else if (e.key === 'o' || e.key === 'O' || e.code === 'KeyO') onSetOutPoint(playback.currentTime);
    };
    document.addEventListener('keydown', handleKey);
    return () => document.removeEventListener('keydown', handleKey);
  }, [playback.currentTime, onSetInPoint, onSetOutPoint]);

  // Close context menu on outside click
  useEffect(() => {
    if (!contextMenu) return;
    const close = () => setContextMenu(null);
    document.addEventListener('mousedown', close, { capture: true });
    return () => document.removeEventListener('mousedown', close, { capture: true });
  }, [contextMenu]);

  useEffect(() => {
    const root = scrollAreaRef.current;
    if (!root) return undefined;

    const updateWidth = () => {
      const width = root.getBoundingClientRect().width;
      if (Number.isFinite(width) && width > 0) {
        setViewportWidth(Math.round(width));
      }
    };

    updateWidth();
    const observer = new ResizeObserver(updateWidth);
    observer.observe(root);
    return () => observer.disconnect();
  }, []);

  const fitWidth = viewportWidth || MIN_TIMELINE_WIDTH_PX;
  const contentWidth = Math.max(1, Math.round(fitWidth * zoomLevel));

  const timeFromPointerEvent = (event: { clientX: number; currentTarget: HTMLDivElement }): number | null => {
    if (duration <= 0) return null;
    const rect = event.currentTarget.getBoundingClientRect();
    const labelWidth = LABEL_WIDTH_PX;
    const usableWidth = Math.max(1, rect.width - labelWidth);
    const x = Math.max(0, Math.min(usableWidth, event.clientX - rect.left - labelWidth));
    return (x / usableWidth) * duration;
  };

  const seekFromPointer = (event: PointerEvent<HTMLDivElement>) => {
    const t = timeFromPointerEvent(event);
    if (t !== null) onSeek(t);
  };

  const handleContextMenu = (event: MouseEvent<HTMLDivElement>) => {
    event.preventDefault();
    const t = timeFromPointerEvent(event);
    if (t === null) return;
    setContextMenu({ x: event.clientX, y: event.clientY, time: t });
  };

  const interval = duration > 0 ? niceMarkerInterval(duration) : 300;
  const markers = timeMarkers(duration, interval);

  const setZoomPreset = (targetSeconds: number) => {
    if (duration <= 0) return;
    setZoomLevel(Math.max(1, duration / targetSeconds));
  };

  const fitTimeline = () => {
    setZoomLevel(1);
    const viewport = scrollAreaRef.current?.querySelector('[data-radix-scroll-area-viewport]') as HTMLElement | null;
    viewport?.scrollTo({ left: 0 });
  };

  return (
    <div className="h-72 border-t border-border-subtle bg-app-shell flex flex-col shrink-0">
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-1.5 border-b border-surface bg-app-shell text-xs">
        <div className="flex items-center gap-2 text-foreground-muted">
          <Layers className="h-3.5 w-3.5" />
          <span className="font-semibold uppercase tracking-wider text-[10px]">AI KANIT KATMANLARI</span>
        </div>
        <div className="flex items-center gap-1">
          {/* I/O info + translate button */}
          {(inPoint !== null || outPoint !== null) && (
            <div className="flex items-center gap-1 mr-2 text-[10px] font-mono text-foreground-muted">
              <span className="text-success font-semibold">I:{inPoint != null ? formatClock(inPoint) : '—'}</span>
              <span>›</span>
              <span className="text-danger font-semibold">O:{outPoint != null ? formatClock(outPoint) : '—'}</span>
              {hasSelection && (
                <Button
                  variant="ghost"
                  size="xs"
                  className="ml-1 h-5 gap-1 text-[10px] text-info hover:text-info-strong disabled:opacity-40"
                  disabled={!selectionHasSegments}
                  title="Seçili aralığı translate et"
                  onPointerDown={(e) => e.stopPropagation()}
                  onClick={(e) => {
                    e.stopPropagation();
                    onTranslateRange(inPoint!, outPoint!);
                  }}
                >
                  <Languages className="h-3 w-3" />
                  Çevir
                </Button>
              )}
            </div>
          )}
          {/* Zoom presets */}
          <Button variant="ghost" size="xs" className="h-6 text-foreground-muted hover:text-foreground-strong" onClick={() => setZoomPreset(60)}>1dk</Button>
          <Button variant="ghost" size="xs" className="h-6 text-foreground-muted hover:text-foreground-strong" onClick={() => setZoomPreset(300)}>5dk</Button>
          <Button variant="ghost" size="xs" className="h-6 text-foreground-muted hover:text-foreground-strong" onClick={() => setZoomPreset(1800)}>30dk</Button>
          <Button variant="ghost" size="xs" className={`h-6 ${zoomLevel === 1 ? 'bg-surface-elevated text-foreground-strong' : 'text-foreground-muted hover:text-foreground-strong'}`} onClick={fitTimeline}>TAM</Button>
          <div className="w-px h-3 bg-border-mitas mx-1"></div>
          <Button variant="ghost" size="xs" className="h-6 gap-1 text-foreground-muted hover:text-foreground-strong" title="Timeline'ı ekrana sığdır" onClick={fitTimeline}>
            <Maximize2 className="h-3 w-3" />
            Fit
          </Button>
          <Button variant="ghost" size="icon-xs" title="Uzaklaştır" onClick={() => setZoomLevel(z => Math.max(1, z / 1.5))}>
            <ZoomOut className="h-3.5 w-3.5 text-foreground-muted" />
          </Button>
          <Button variant="ghost" size="icon-xs" title="Yakınlaştır" onClick={() => setZoomLevel(z => Math.min(20, z * 1.5))}>
            <ZoomIn className="h-3.5 w-3.5 text-foreground-muted" />
          </Button>
        </div>
      </div>

      <ScrollArea ref={scrollAreaRef} className="flex-1">
        <div
          className="p-2 relative"
          style={{ width: `${contentWidth}px` }}
          onPointerDown={seekFromPointer}
          onPointerMove={(event) => {
            if (event.buttons === 1) seekFromPointer(event);
          }}
          onContextMenu={handleContextMenu}
        >
          {/* Playhead */}
          <div
            className="absolute top-2 bottom-2 w-px bg-info z-20 shadow-glow-info-strong cursor-ew-resize"
            style={playheadStyle}
            title="Timeline konumu"
          >
            <div className="absolute -top-1 -left-1 w-2.5 h-2.5 bg-info rotate-45"></div>
          </div>

          {/* I/O region overlay — sits in the usable area (right of labels) */}
          {duration > 0 && (inPercent !== null || outPercent !== null) && (
            <div className="absolute top-2 bottom-2 pointer-events-none z-10" style={{ left: '11rem', right: 0 }}>
              {/* Selected region fill */}
              {hasSelection && (
                <div
                  className="absolute top-0 bottom-0 bg-info/10 border-x border-info/25"
                  style={{ left: `${inPercent}%`, width: `${outPercent! - inPercent!}%` }}
                />
              )}
              {/* In-point marker */}
              {inPercent !== null && (
                <div className="absolute top-0 bottom-0 flex flex-col items-start" style={{ left: `${inPercent}%` }}>
                  <div className="w-px h-full bg-success/70" />
                  <span className="absolute top-0.5 left-0.5 text-[9px] text-success font-bold leading-none select-none">I</span>
                </div>
              )}
              {/* Out-point marker */}
              {outPercent !== null && (
                <div className="absolute top-0 bottom-0 flex flex-col items-end" style={{ left: `${outPercent}%` }}>
                  <div className="w-px h-full bg-danger/70" />
                  <span className="absolute top-0.5 right-0.5 text-[9px] text-danger font-bold leading-none select-none">O</span>
                </div>
              )}
            </div>
          )}

          {/* Time markers */}
          <div className="h-5 border-b border-border-subtle/50 mb-1 relative pl-44">
            {duration > 0 ? (
              <div className="absolute inset-y-0 left-44 right-0">
                {markers.map((time, i) => {
                  const left = Math.max(0, Math.min(100, (time / duration) * 100));
                  const isEnd = i === markers.length - 1;
                  return (
                    <div
                      key={`${time}-${i}`}
                      className="absolute top-0 bottom-0 border-l border-border-subtle/50 text-[9px] font-mono text-foreground-muted"
                      style={{ left: `${left}%` }}
                    >
                      <span className={`absolute left-0 top-0 whitespace-nowrap ${isEnd ? '-translate-x-full pr-1' : 'pl-1'}`}>
                        {formatClock(time)}
                      </span>
                    </div>
                  );
                })}
              </div>
            ) : (
              <div className="absolute inset-y-0 left-44 right-0 grid grid-cols-12">
                {Array.from({ length: 12 }, (_, i) => (
                  <div key={i} className="border-l border-border-subtle/50 text-[9px] font-mono text-foreground-muted pl-1">
                    {formatClock((i + 1) * interval)}
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Tracks */}
          <div className="space-y-0.5">
            {timelineTracks.map(track => {
              const isWip = track.status === 'wip';
              const channelEnabled = !track.channel || enabledAsrChannels[track.channel];
              const trackBg = isWip
                ? 'bg-surface/20'
                : channelEnabled
                  ? 'bg-surface/40 hover:bg-surface-elevated/40'
                  : 'bg-surface/15 opacity-60';
              const blockBg = INTENT_BG[track.intent];
              const blockBorder = INTENT_BORDER[track.intent];
              const markerBg = INTENT_MARKER[track.intent];
              const labelText = isWip || !channelEnabled ? 'text-foreground-disabled' : INTENT_LABEL_TEXT[track.intent];
              const iconText  = isWip || !channelEnabled ? 'text-foreground-disabled' : INTENT_ICON_TEXT[track.intent];

              return (
                <div key={track.id} className={`flex h-7 items-center group rounded-sm ${trackBg}`}>
                  <div className="w-44 shrink-0 flex items-center justify-between px-2 border-r border-border-subtle/50">
                    <div className="flex items-center gap-2">
                      <track.icon className={`h-3 w-3 ${iconText} ${!isWip ? 'group-hover:text-foreground-default' : ''}`} />
                      <span className={`text-[10px] uppercase font-semibold tracking-wider ${labelText} ${!isWip ? 'group-hover:text-foreground-strong' : ''}`}>
                        {track.label}
                      </span>
                    </div>
                    {track.channel ? (
                      <Button
                        variant={channelEnabled ? 'ghost' : 'outline'}
                        size="icon-xs"
                        className={`h-5 w-5 ${channelEnabled ? 'text-foreground-muted hover:text-danger' : 'border-info-border text-info'}`}
                        title={`${track.label} ${channelEnabled ? 'kapat' : 'aç'}`}
                        aria-label={`${track.label} ${channelEnabled ? 'kapat' : 'aç'}`}
                        onPointerDown={(e) => e.stopPropagation()}
                        onClick={(e) => {
                          e.stopPropagation();
                          onToggleAsrChannel(track.channel as AsrChannelKey);
                        }}
                      >
                        {channelEnabled ? <X className="h-3 w-3" /> : <Volume2 className="h-3 w-3" />}
                      </Button>
                    ) : isWip && (
                      <span title="Yapım Aşamasında" aria-label="Yapım Aşamasında">
                        <Lock className="h-2.5 w-2.5 text-foreground-disabled" />
                      </span>
                    )}
                  </div>

                  <div className={`flex-1 relative h-full flex items-center px-1 ${isWip || !channelEnabled ? 'pointer-events-none opacity-40' : ''}`}>
                    {track.id === 'warn' && qualityDrops > 0 && (
                      <div className={`absolute left-[45%] w-[1%] h-4 ${markerBg} rounded-sm cursor-pointer hover:scale-y-125 transition-transform`} title={`${qualityDrops} kalite düşümü`} />
                    )}
                    {track.id === 'warn' && duration > 0 && uncoveredRanges.map((range, idx) => {
                      const left = Math.max(0, Math.min(99, (range.start / duration) * 100));
                      const width = Math.max(0.5, Math.min(100 - left, ((range.end - range.start) / duration) * 100));
                      return (
                        <div
                          key={`vad-gap-${idx}`}
                          className="absolute h-4 bg-warning-strong/70 border border-warning-strong rounded-sm cursor-pointer hover:brightness-125 transition-all"
                          style={{ left: `${left}%`, width: `${width}%` }}
                          title={`Kapsanamamış bölge: ${range.start.toFixed(1)}s–${range.end.toFixed(1)}s (≈${Math.round(range.speech_seconds)} sn konuşma)`}
                          onPointerDown={(e) => {
                            e.stopPropagation();
                            onSeek(range.start);
                          }}
                        />
                      );
                    })}
                    {(track.id === 'asr' || track.id === 'asr-l' || track.id === 'asr-r') && channelEnabled && (
                      <>
                        {segments.map((segment, index) => {
                          if (track.channel && segmentChannelKey(segment) !== track.channel) return null;
                          const isSelected = selectedSegmentIndex === index;
                          const wordTicks = segment.word_timestamps ?? [];
                          const showWordTicks = wordTicks.length > 1 && (isSelected || zoomLevel >= 2.25);
                          return (
                            <div
                              key={`${segment.start}-${segment.end}-${index}`}
                              className={`absolute h-4 border rounded-sm cursor-pointer hover:brightness-125 transition-all overflow-hidden ${
                                isSelected
                                  ? 'bg-info border-info-strong shadow-glow-info-strong ring-1 ring-info-strong/70'
                                  : `${blockBg} ${blockBorder}`
                              }`}
                              style={segmentStyle(segment, duration)}
                              title={`${formatSegmentTime(segment)} ${segment.normalized_text ?? segment.text}`}
                              onPointerDown={(e) => {
                                e.stopPropagation();
                                onSelectSegment(index);
                              }}
                            >
                              {showWordTicks && wordTicks.slice(0, 80).map((word, wordIndex) => (
                                <span
                                  key={`${word.start}-${word.end}-${wordIndex}`}
                                  className="absolute top-0 bottom-0 w-px bg-foreground-strong/60 opacity-70"
                                  style={wordMarkerStyle(segment, word)}
                                  title={`${formatClock(word.start)} ${word.word}`}
                                  aria-hidden="true"
                                />
                              ))}
                            </div>
                          );
                        })}
                        {asrJob?.status === 'running' && (
                          <div className={`absolute left-[2%] w-[18%] h-4 ${blockBg} border ${blockBorder} rounded-sm animate-pulse`} />
                        )}
                      </>
                    )}
                    {isWip && (
                      <>
                        <div className={`absolute left-[5%] w-[10%] h-4 ${blockBg} border ${blockBorder} rounded-sm`} />
                        <div className={`absolute left-[30%] w-[20%] h-4 ${blockBg} border ${blockBorder} rounded-sm`} />
                        <div className={`absolute left-[65%] w-[15%] h-4 ${blockBg} border ${blockBorder} rounded-sm`} />
                      </>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </ScrollArea>

      {/* Right-click context menu */}
      {contextMenu && (
        <div
          className="fixed z-50 min-w-[160px] rounded-sm border border-border-mitas bg-app-shell shadow-lg py-1 text-xs"
          style={{ top: contextMenu.y, left: contextMenu.x }}
          onMouseDown={(e) => e.stopPropagation()}
        >
          <div className="px-2 py-1 text-[10px] font-mono text-foreground-disabled border-b border-border-subtle/50 mb-1">
            {formatClock(contextMenu.time)}
          </div>
          <button
            className="w-full text-left px-3 py-1.5 hover:bg-surface-elevated text-foreground-default flex items-center gap-2"
            onClick={() => { onSetInPoint(contextMenu.time); setContextMenu(null); }}
          >
            <span className="text-success font-bold text-[10px] w-3">I</span>
            In Point Koy
          </button>
          <button
            className="w-full text-left px-3 py-1.5 hover:bg-surface-elevated text-foreground-default flex items-center gap-2"
            onClick={() => { onSetOutPoint(contextMenu.time); setContextMenu(null); }}
          >
            <span className="text-danger font-bold text-[10px] w-3">O</span>
            Out Point Koy
          </button>
          {(inPoint !== null || outPoint !== null) && (
            <button
              className="w-full text-left px-3 py-1.5 hover:bg-surface-elevated text-foreground-muted flex items-center gap-2 border-t border-border-subtle/50 mt-1"
              onClick={() => { onSetInPoint(null); onSetOutPoint(null); setContextMenu(null); }}
            >
              <span className="text-[10px] w-3">×</span>
              I/O Temizle
            </button>
          )}
        </div>
      )}
    </div>
  );
}

function formatSegmentTime(segment: AsrSegment): string {
  return `${segment.start.toFixed(1)}s-${segment.end.toFixed(1)}s`;
}

function segmentChannelKey(segment: AsrSegment): 'L' | 'R' | null {
  const value = String(segment.channel ?? '').trim().toUpperCase();
  if (value === 'L' || value === 'LEFT' || value === '1' || value === 'KANAL 1') return 'L';
  if (value === 'R' || value === 'RIGHT' || value === '2' || value === 'KANAL 2') return 'R';
  return null;
}
