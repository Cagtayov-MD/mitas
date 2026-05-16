import { Layers, FileText, User, Type, Tag, Image, AlertTriangle, ZoomIn, ZoomOut, Lock, Volume2, Music, X } from 'lucide-react';
import { ScrollArea, Button } from './ui';
import type { PointerEvent } from 'react';
import type { AsrChannelKey, AsrChannelState, AsrJob, AsrSegment, PlaybackState } from '../asr-api';

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

// Track listesi — renkler intent ile bağlanır; raw Tailwind palet sınıfı yok.
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

// Intent → blok stilleri. Literal string'ler PurgeCSS'in görmesi için burada.
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
  onSeek: (time: number) => void;
  onToggleAsrChannel: (channel: AsrChannelKey) => void;
  onSelectSegment: (index: number) => void;
}

function segmentStyle(segment: AsrSegment, duration: number | undefined) {
  const total = Math.max(duration || segment.end || 1, 1);
  const left = Math.max(0, Math.min(99, (segment.start / total) * 100));
  const width = Math.max(0.75, Math.min(100 - left, ((segment.end - segment.start) / total) * 100));
  return { left: `${left}%`, width: `${width}%` };
}

export function Timeline({ asrJob, playback, enabledAsrChannels, selectedSegmentIndex, onSeek, onToggleAsrChannel, onSelectSegment }: TimelineProps) {
  const segments = asrJob?.segments ?? [];
  const duration = playback.duration || asrJob?.summary?.audio_duration || 0;
  const qualityDrops = asrJob?.summary?.quality_drops ?? 0;
  const hasLeftChannel = segments.some((segment) => segmentChannelKey(segment) === 'L');
  const hasRightChannel = segments.some((segment) => segmentChannelKey(segment) === 'R');
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

  const seekFromPointer = (event: PointerEvent<HTMLDivElement>) => {
    if (duration <= 0) {
      return;
    }
    const rect = event.currentTarget.getBoundingClientRect();
    const labelWidth = 176;
    const usableWidth = Math.max(1, rect.width - labelWidth);
    const x = Math.max(0, Math.min(usableWidth, event.clientX - rect.left - labelWidth));
    onSeek((x / usableWidth) * duration);
  };

  return (
    <div className="h-72 border-t border-border-subtle bg-app-shell flex flex-col shrink-0">
      <div className="flex items-center justify-between px-3 py-1.5 border-b border-surface bg-app-shell text-xs">
        <div className="flex items-center gap-2 text-foreground-muted">
          <Layers className="h-3.5 w-3.5" />
          <span className="font-semibold uppercase tracking-wider text-[10px]">AI KANIT KATMANLARI</span>
        </div>
        <div className="flex items-center gap-1">
          <Button variant="ghost" size="xs" className="h-6 text-foreground-muted hover:text-foreground-strong">1dk</Button>
          <Button variant="ghost" size="xs" className="h-6 text-foreground-muted hover:text-foreground-strong">5dk</Button>
          <Button variant="ghost" size="xs" className="h-6 bg-surface-elevated text-foreground-strong">30dk</Button>
          <Button variant="ghost" size="xs" className="h-6 text-foreground-muted hover:text-foreground-strong">TAM</Button>
          <div className="w-px h-3 bg-border-mitas mx-1"></div>
          <Button variant="ghost" size="icon-xs"><ZoomOut className="h-3.5 w-3.5 text-foreground-muted" /></Button>
          <Button variant="ghost" size="icon-xs"><ZoomIn className="h-3.5 w-3.5 text-foreground-muted" /></Button>
        </div>
      </div>

      <ScrollArea className="flex-1">
        <div
          className="min-w-[1000px] w-full p-2 relative"
          onPointerDown={seekFromPointer}
          onPointerMove={(event) => {
            if (event.buttons === 1) {
              seekFromPointer(event);
            }
          }}
        >
          <div
            className="absolute top-2 bottom-2 w-px bg-info z-20 shadow-glow-info-strong cursor-ew-resize"
            style={playheadStyle}
            title="Timeline konumu"
          >
            <div className="absolute -top-1 -left-1 w-2.5 h-2.5 bg-info rotate-45"></div>
          </div>
          {/* Time markers */}
          <div className="h-5 flex border-b border-border-subtle/50 mb-1 relative pl-44">
            {[...Array(12)].map((_, i) => (
              <div key={i} className="flex-1 border-l border-border-subtle/50 text-[9px] font-mono text-foreground-muted pl-1">
                00:{i * 5 < 10 ? `0${i*5}` : i*5}:00
              </div>
            ))}
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
              const iconText = isWip || !channelEnabled ? 'text-foreground-disabled' : INTENT_ICON_TEXT[track.intent];

              return (
                <div
                  key={track.id}
                  className={`flex h-7 items-center group rounded-sm ${trackBg}`}
                >
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
                        onPointerDown={(event) => event.stopPropagation()}
                        onClick={(event) => {
                          event.stopPropagation();
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

                    {track.id === 'warn' && (
                      <>
                        {qualityDrops > 0 && (
                          <div className={`absolute left-[45%] w-[1%] h-4 ${markerBg} rounded-sm cursor-pointer hover:scale-y-125 transition-transform`} title={`${qualityDrops} kalite düşümü`}></div>
                        )}
                      </>
                    )}
                    {(track.id === 'asr' || track.id === 'asr-l' || track.id === 'asr-r') && channelEnabled && (
                      <>
                        {segments.map((segment, index) => {
                          if (track.channel && segmentChannelKey(segment) !== track.channel) {
                            return null;
                          }
                          const isSelected = selectedSegmentIndex === index;
                          return (
                            <div
                              key={`${segment.start}-${segment.end}-${index}`}
                              className={`absolute h-4 border rounded-sm cursor-pointer hover:brightness-125 transition-all ${
                                isSelected
                                  ? 'bg-info border-info-strong shadow-glow-info-strong ring-1 ring-info-strong/70'
                                  : `${blockBg} ${blockBorder}`
                              }`}
                              style={segmentStyle(segment, duration)}
                              title={`${formatSegmentTime(segment)} ${segment.text}`}
                              onPointerDown={(event) => {
                                event.stopPropagation();
                                onSelectSegment(index);
                              }}
                            ></div>
                          );
                        })}
                        {asrJob?.status === 'running' && (
                          <div className={`absolute left-[2%] w-[18%] h-4 ${blockBg} border ${blockBorder} rounded-sm animate-pulse`}></div>
                        )}
                      </>
                    )}
                    {isWip && (
                      <>
                        <div className={`absolute left-[5%] w-[10%] h-4 ${blockBg} border ${blockBorder} rounded-sm`}></div>
                        <div className={`absolute left-[30%] w-[20%] h-4 ${blockBg} border ${blockBorder} rounded-sm`}></div>
                        <div className={`absolute left-[65%] w-[15%] h-4 ${blockBg} border ${blockBorder} rounded-sm`}></div>
                      </>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </ScrollArea>
    </div>
  );
}

function formatSegmentTime(segment: AsrSegment): string {
  return `${segment.start.toFixed(1)}s-${segment.end.toFixed(1)}s`;
}

function segmentChannelKey(segment: AsrSegment): 'L' | 'R' | null {
  const value = String(segment.channel ?? '').trim().toUpperCase();
  if (value === 'L' || value === 'LEFT' || value === '1' || value === 'KANAL 1') {
    return 'L';
  }
  if (value === 'R' || value === 'RIGHT' || value === '2' || value === 'KANAL 2') {
    return 'R';
  }
  return null;
}
