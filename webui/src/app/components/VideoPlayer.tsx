import {
  Pause,
  Play,
  Maximize,
  Settings,
  SkipBack,
  SkipForward,
  ChevronLeft,
  ChevronRight,
  UserSquare2,
  Type,
  Volume2,
  VolumeX,
} from 'lucide-react';
import { useCallback, useEffect, useRef, useState, type PointerEvent } from 'react';
import * as dashjs from 'dashjs';
import { Button, Badge } from './ui';
import {
  analysisProfileLabel,
  formatClock,
  type AnalysisProfile,
  type AsrChannelState,
  type AsrJob,
  type PlaybackState,
  type SeekRequest,
} from '../asr-api';

interface VideoPlayerProps {
  asrJob: AsrJob | null;
  selectedFileName: string | null;
  analysisProfile: AnalysisProfile;
  isSttPreviewEnabled: boolean;
  mediaPreviewUrl: string | null;
  mediaType: string | null;
  mediaDurationHint: number | null;
  playback: PlaybackState;
  seekRequest: SeekRequest | null;
  enabledAsrChannels: AsrChannelState;
  onPlaybackChange: (playback: PlaybackState) => void;
  onSeek: (time: number) => void;
  onMediaElementChange: (mediaElement: HTMLMediaElement | null) => void;
}

const RATES = [0.5, 1, 1.25, 1.5, 2];
type AudioListenMode = 'both' | 'L' | 'R';

export function VideoPlayer({
  asrJob,
  selectedFileName,
  analysisProfile,
  isSttPreviewEnabled,
  mediaPreviewUrl,
  mediaType,
  mediaDurationHint,
  playback,
  seekRequest,
  enabledAsrChannels,
  onPlaybackChange,
  onSeek,
  onMediaElementChange,
}: VideoPlayerProps) {
  const mediaRef = useRef<HTMLMediaElement | null>(null);
  const frameRef = useRef<HTMLDivElement | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const audioSourceRef = useRef<MediaElementAudioSourceNode | null>(null);
  const audioSourceElementRef = useRef<HTMLMediaElement | null>(null);
  const audioNodesRef = useRef<{ splitter: ChannelSplitterNode | null; merger: ChannelMergerNode | null }>({ splitter: null, merger: null });
  const [isMuted, setIsMuted] = useState(false);
  const [playbackRate, setPlaybackRate] = useState(1);
  const isVideo = Boolean(mediaPreviewUrl && mediaType?.startsWith('video/'));
  const isDashVideo = Boolean(mediaPreviewUrl && mediaType === 'application/dash+xml');
  const isAudio = Boolean(mediaPreviewUrl && (mediaType?.startsWith('audio/') || (!isVideo && !isDashVideo)));
  const isMediaReadyForAsr = Boolean(selectedFileName && mediaPreviewUrl && !asrJob);
  const isSttSelected = analysisProfile === 'stt';
  const selectedProfileLabel = analysisProfileLabel(analysisProfile);
  const duration = saneDuration(playback.duration) || saneDuration(mediaDurationHint) || saneDuration(asrJob?.summary?.audio_duration) || 0;
  const progress = duration > 0 ? Math.max(0, Math.min(100, (playback.currentTime / duration) * 100)) : 0;
  const audioListenMode = resolveAudioListenMode(enabledAsrChannels);

  const setVideoNode = useCallback((node: HTMLVideoElement | null) => {
    mediaRef.current = node;
    onMediaElementChange(node);
  }, [onMediaElementChange]);

  const setAudioNode = useCallback((node: HTMLAudioElement | null) => {
    mediaRef.current = node;
    onMediaElementChange(node);
  }, [onMediaElementChange]);

  const publishState = useCallback(() => {
    const media = mediaRef.current;
    if (!media) {
      onPlaybackChange({ currentTime: 0, duration: 0, isPlaying: false });
      return;
    }
    const nativeDuration = saneDuration(media.duration);
    onPlaybackChange({
      currentTime: media.currentTime || 0,
      duration: nativeDuration || duration,
      isPlaying: !media.paused,
    });
  }, [duration, onPlaybackChange]);

  const disconnectAudioGraph = useCallback(() => {
    audioNodesRef.current.splitter?.disconnect();
    audioNodesRef.current.merger?.disconnect();
    audioNodesRef.current = { splitter: null, merger: null };
    audioSourceRef.current?.disconnect();
  }, []);

  const connectAudioGraph = useCallback(() => {
    const media = mediaRef.current;
    if (!mediaPreviewUrl || !media) {
      return;
    }
    const AudioContextCtor = window.AudioContext || (window as Window & { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
    if (!AudioContextCtor) {
      return;
    }
    const context = audioContextRef.current ?? new AudioContextCtor();
    audioContextRef.current = context;

    if (!audioSourceRef.current || audioSourceElementRef.current !== media) {
      disconnectAudioGraph();
      audioSourceRef.current = context.createMediaElementSource(media);
      audioSourceElementRef.current = media;
    } else {
      disconnectAudioGraph();
    }

    const source = audioSourceRef.current;
    if (audioListenMode === 'both') {
      source.connect(context.destination);
      return;
    }

    const splitter = context.createChannelSplitter(2);
    const merger = context.createChannelMerger(2);
    const sourceOutput = audioListenMode === 'L' ? 0 : 1;
    source.connect(splitter);
    splitter.connect(merger, sourceOutput, 0);
    splitter.connect(merger, sourceOutput, 1);
    merger.connect(context.destination);
    audioNodesRef.current = { splitter, merger };
  }, [audioListenMode, disconnectAudioGraph, mediaPreviewUrl]);

  useEffect(() => {
    const media = mediaRef.current;
    if (!media || !seekRequest) {
      return;
    }
    const nativeDuration = saneDuration(media.duration);
    const target = Math.max(0, Math.min(seekRequest.time, nativeDuration || duration || seekRequest.time));
    media.currentTime = target;
    publishState();
  }, [publishState, seekRequest]);

  useEffect(() => {
    const media = mediaRef.current;
    if (media) {
      media.playbackRate = playbackRate;
      media.muted = isMuted;
    }
  }, [isMuted, playbackRate, mediaPreviewUrl]);

  const togglePlay = useCallback(async () => {
    const media = mediaRef.current;
    if (!media) {
      return;
    }
    if (media.paused) {
      if (audioContextRef.current?.state === 'suspended') {
        await audioContextRef.current.resume();
      }
      await media.play();
    } else {
      media.pause();
    }
    publishState();
  }, [publishState]);

  const seekBy = useCallback((delta: number) => {
    const media = mediaRef.current;
    const current = media?.currentTime ?? playback.currentTime;
    onSeek(Math.max(0, Math.min(duration || current + delta, current + delta)));
  }, [duration, onSeek, playback.currentTime]);

  const seekFromPointer = (event: PointerEvent<HTMLDivElement>) => {
    if (duration <= 0) {
      return;
    }
    const rect = event.currentTarget.getBoundingClientRect();
    const ratio = Math.max(0, Math.min(1, (event.clientX - rect.left) / rect.width));
    onSeek(ratio * duration);
  };

  const cycleRate = () => {
    const index = RATES.indexOf(playbackRate);
    const nextRate = RATES[(index + 1) % RATES.length];
    setPlaybackRate(nextRate);
  };

  const toggleMute = () => {
    setIsMuted((value) => !value);
  };

  const enterFullscreen = () => {
    void frameRef.current?.requestFullscreen?.();
  };

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (!mediaPreviewUrl || event.defaultPrevented || event.altKey || event.ctrlKey || event.metaKey) {
        return;
      }
      const target = event.target as HTMLElement | null;
      if (target?.closest('input, textarea, select, button, [role="button"], [contenteditable="true"]')) {
        return;
      }

      const key = event.key.toLowerCase();
      if (key === ' ' || key === 'spacebar' || key === 'k') {
        event.preventDefault();
        if (!event.repeat) {
          void togglePlay();
        }
        return;
      }
      if (key === 'j') {
        event.preventDefault();
        seekBy(-10);
        return;
      }
      if (key === 'l') {
        event.preventDefault();
        seekBy(10);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [mediaPreviewUrl, seekBy, togglePlay]);

  useEffect(() => {
    const media = mediaRef.current;
    if (!mediaPreviewUrl || mediaType !== 'application/dash+xml' || !(media instanceof HTMLVideoElement)) {
      return undefined;
    }
    const player = dashjs.MediaPlayer().create();
    player.updateSettings({
      streaming: {
        buffer: {
          fastSwitchEnabled: true,
        },
      },
    });
    player.initialize(media, mediaPreviewUrl, false);
    return () => {
      player.reset();
    };
  }, [mediaPreviewUrl, mediaType]);

  useEffect(() => {
    connectAudioGraph();
  }, [connectAudioGraph]);

  useEffect(() => {
    return () => {
      disconnectAudioGraph();
      void audioContextRef.current?.close();
      audioContextRef.current = null;
      audioSourceRef.current = null;
      audioSourceElementRef.current = null;
    };
  }, [disconnectAudioGraph]);

  return (
    <div ref={frameRef} className="flex flex-col flex-1 bg-app-shell overflow-hidden relative border-b border-border-subtle">
      {/* Top Overlays toggle */}
      <div className="absolute top-4 right-4 z-10 flex gap-2">
        <Button
          variant="outline"
          size="xs"
          disabled
          title="Yapım Aşamasında"
          className="gap-1 bg-surface/50 backdrop-blur border-border-mitas/50 text-foreground-muted opacity-60"
        >
          <UserSquare2 className="h-3 w-3" /> Yüzler
        </Button>
        <Button
          variant="outline"
          size="xs"
          disabled
          title="Yapım Aşamasında"
          className="gap-1 bg-surface/50 backdrop-blur border-border-mitas/50 text-foreground-muted opacity-60"
        >
          <Type className="h-3 w-3" /> OCR
        </Button>
      </div>


      {/* Video Content Area */}
      <div className="relative flex-1 flex flex-col items-center justify-center overflow-hidden bg-app-shell">
        <div className="relative w-full h-full flex items-center justify-center">
          {isMediaReadyForAsr && (
            <div className="absolute top-4 left-4 z-20 rounded-sm border border-info-border bg-app-shell/95 px-3 py-2 shadow-glow-info">
              <div className="text-[12px] font-semibold text-info">
                {isSttSelected
                  ? `${selectedFileName} STT için hazır`
                  : `${selectedFileName} yüklendi`}
              </div>
              <div className="mt-0.5 text-[10px] text-foreground-muted">
                {isSttSelected
                  ? 'Model çalışmadı. Başlatmak için STT Başlat.'
                  : `Seçili profil: ${selectedProfileLabel}. Konuşmadan metne için STT seç.`}
              </div>
            </div>
          )}
          {(isVideo || isDashVideo) && mediaPreviewUrl && (
            <video
              ref={setVideoNode}
              src={isDashVideo ? undefined : mediaPreviewUrl}
              className="w-full h-full object-contain object-center bg-surface"
              preload="metadata"
              onLoadedMetadata={publishState}
              onTimeUpdate={publishState}
              onPlay={publishState}
              onPause={publishState}
              onEnded={publishState}
            />
          )}
          {isAudio && mediaPreviewUrl && (
            <div className="mt-4 w-full max-w-xl border border-border-subtle bg-surface p-4 rounded-sm">
              <div className="text-xs text-foreground-muted mb-3">
                {selectedFileName
                  ? isSttSelected
                    ? `${selectedFileName} STT için hazır.`
                    : `${selectedFileName} yüklendi. Konuşmadan metne için STT seç.`
                  : 'Ses dosyası yüklendi.'}
                {isSttSelected ? ' STT için STT Başlat düğmesini kullan.' : ''}
              </div>
              <audio
                ref={setAudioNode}
                src={mediaPreviewUrl}
                preload="metadata"
                onLoadedMetadata={publishState}
                onTimeUpdate={publishState}
                onPlay={publishState}
                onPause={publishState}
                onEnded={publishState}
              />
              <div className="h-24 border border-border-subtle bg-app-shell rounded-sm flex items-center justify-center">
                <div className="h-10 w-10 rounded-full border border-info-border bg-info-subtle flex items-center justify-center">
                  {playback.isPlaying ? <Volume2 className="h-5 w-5 text-info" /> : <VolumeX className="h-5 w-5 text-foreground-muted" />}
                </div>
              </div>
            </div>
          )}
          {!mediaPreviewUrl && (
            <div className="mt-6 ml-6 text-left">
              <div className="text-sm font-semibold text-foreground-strong">Gerçek medya bekleniyor</div>
              <div className="text-xs text-foreground-muted mt-1">Yükle butonu ile video veya ses seç; konuşmadan metne işlemi STT seçiliyken başlar.</div>
            </div>
          )}
        </div>
      </div>

      {/* Below Video Info Bar */}
      <div className="h-8 bg-surface border-t border-border-subtle flex items-center px-4 gap-4 shrink-0">
        <span className="text-[10px] uppercase tracking-wider text-foreground-muted">Ekranda:</span>
        <div className="flex gap-2 items-center">
          <span className="text-[11px] text-foreground-default">STT/ASR durumu:</span>
          <Badge variant="outline" className="border-info-border text-info bg-info-subtle">
            {asrJob?.status || (mediaPreviewUrl ? 'başlatılmadı' : 'bekleniyor')}
          </Badge>
          <Badge variant={isSttSelected ? 'success' : 'warning'}>
            {selectedProfileLabel}
          </Badge>
          {isSttPreviewEnabled && isSttSelected ? (
            <Badge variant="outline" className="border-info-border text-info bg-info-subtle">Preview açık</Badge>
          ) : null}
          {audioListenMode !== 'both' ? (
            <Badge variant="outline" className="border-warning-border text-warning bg-warning-subtle">
              {audioListenMode === 'L' ? 'Kanal 1 dinleniyor' : 'Kanal 2 dinleniyor'}
            </Badge>
          ) : null}
          {asrJob?.segments.length ? (
            <span className="text-[11px] text-foreground-muted">{asrJob.segments.length} segment</span>
          ) : null}
        </div>
        <div className="ml-auto text-[10px] font-mono text-foreground-muted">
          {formatClock(playback.currentTime)} / {formatClock(duration)}
        </div>
      </div>

      {/* Video Controls */}
      <div className="h-12 bg-app-shell border-t border-surface flex items-center justify-between px-4 shrink-0">
        <div className="flex items-center gap-2 text-foreground-muted">
          <Button variant="ghost" size="icon-xs" onClick={() => seekBy(-10)} disabled={!mediaPreviewUrl}>
            <SkipBack className="h-3.5 w-3.5" />
          </Button>
          <Button variant="ghost" size="icon-xs" onClick={() => seekBy(-1)} disabled={!mediaPreviewUrl}>
            <ChevronLeft className="h-3.5 w-3.5" />
          </Button>
          <Button
            variant="default"
            size="icon-xs"
            className="h-7 w-7 rounded-sm bg-foreground-strong text-app-shell hover:bg-foreground-strong/90"
            onClick={togglePlay}
            disabled={!mediaPreviewUrl}
          >
            {playback.isPlaying ? <Pause className="h-3.5 w-3.5" /> : <Play className="h-3.5 w-3.5 ml-0.5" />}
          </Button>
          <Button variant="ghost" size="icon-xs" onClick={() => seekBy(1)} disabled={!mediaPreviewUrl}>
            <ChevronRight className="h-3.5 w-3.5" />
          </Button>
          <Button variant="ghost" size="icon-xs" onClick={() => seekBy(10)} disabled={!mediaPreviewUrl}>
            <SkipForward className="h-3.5 w-3.5" />
          </Button>
          <button
            type="button"
            onClick={cycleRate}
            disabled={!mediaPreviewUrl}
            className="ml-2 flex items-center gap-1 bg-surface px-2 py-0.5 rounded text-[10px] font-mono border border-border-subtle disabled:opacity-50"
          >
            <span className="text-foreground-default">{playbackRate}x</span>
          </button>
        </div>

        <div className="flex-1 px-6 flex items-center">
          <div
            className="h-3 w-full bg-surface-elevated rounded-sm relative cursor-pointer overflow-hidden"
            onPointerDown={seekFromPointer}
            onPointerMove={(event) => {
              if (event.buttons === 1) {
                seekFromPointer(event);
              }
            }}
            title="Oynatma konumu"
          >
            <div className="absolute top-0 left-0 h-full bg-info-strong" style={{ width: `${progress}%` }}></div>
            <div className="absolute top-1/2 h-3 w-1 -translate-y-1/2 rounded-sm bg-foreground-strong shadow-glow-info" style={{ left: `${progress}%` }}></div>
          </div>
        </div>

        <div className="flex items-center gap-2 text-foreground-muted">
          <Button variant="ghost" size="icon-xs" onClick={toggleMute} disabled={!mediaPreviewUrl}>
            {isMuted ? <VolumeX className="h-3.5 w-3.5" /> : <Volume2 className="h-3.5 w-3.5" />}
          </Button>
          <Button variant="ghost" size="icon-xs" disabled>
            <Settings className="h-3.5 w-3.5" />
          </Button>
          <Button variant="ghost" size="icon-xs" onClick={enterFullscreen} disabled={!mediaPreviewUrl}>
            <Maximize className="h-3.5 w-3.5" />
          </Button>
        </div>
      </div>
    </div>
  );
}

function saneDuration(value: number | null | undefined): number {
  if (!Number.isFinite(value ?? NaN)) {
    return 0;
  }
  const seconds = Number(value);
  return seconds > 0 && seconds < 24 * 60 * 60 ? seconds : 0;
}

function resolveAudioListenMode(channels: AsrChannelState): AudioListenMode {
  if (channels.L && !channels.R) {
    return 'L';
  }
  if (!channels.L && channels.R) {
    return 'R';
  }
  return 'both';
}
