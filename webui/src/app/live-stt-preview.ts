import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { PlaybackState, SeekRequest } from './asr-api';

export type LiveSttStatus = 'idle' | 'ready' | 'listening' | 'resolving' | 'paused' | 'error';

export interface LiveSttLine {
  id: string;
  start: number;
  end: number;
  text: string;
  language?: string | null;
  isFinal: boolean;
}

interface LiveSttPreviewParams {
  enabled: boolean;
  mediaElement: HTMLMediaElement | null;
  mediaKey: string | null;
  playback: PlaybackState;
  seekRequest: SeekRequest | null;
  onBusyChange?: (isBusy: boolean) => void;
}

export interface LiveSttPreviewState {
  status: LiveSttStatus;
  statusText: string;
  lines: LiveSttLine[];
  partialLine: LiveSttLine | null;
  error: string | null;
  isBusy: boolean;
  clearLines: () => void;
}

interface LiveSttSegmentPayload {
  id?: string;
  start?: number;
  end?: number;
  text?: string;
  language?: string | null;
  avg_logprob?: number;
  no_speech_prob?: number;
}

interface LiveSttSocketMessage {
  type?: string;
  status?: LiveSttStatus;
  message?: string;
  chunk_id?: string;
  text?: string;
  media_time_start?: number;
  media_time_end?: number;
  publish_until?: number;
  language?: string | null;
  segments?: LiveSttSegmentPayload[];
}

const TARGET_SAMPLE_RATE = 16_000;
const DECODE_INTERVAL_SECONDS = 1.5;
const ROLLING_CONTEXT_SECONDS = 10;
const DEFAULT_DISPLAY_LAG_SECONDS = 3;
const MIN_DISPLAY_LAG_SECONDS = 1.6;
const MAX_DISPLAY_LAG_SECONDS = 4.8;
const MIN_PUBLISH_ADVANCE_SECONDS = 0.75;
const MIN_FLUSH_SECONDS = 0.5;
const ROLLING_CONTEXT_SAMPLE_COUNT = TARGET_SAMPLE_RATE * ROLLING_CONTEXT_SECONDS;
const MIN_FLUSH_SAMPLE_COUNT = TARGET_SAMPLE_RATE * MIN_FLUSH_SECONDS;

export function useLiveSttPreview({
  enabled,
  mediaElement,
  mediaKey,
  playback,
  seekRequest,
  onBusyChange,
}: LiveSttPreviewParams): LiveSttPreviewState {
  const [status, setStatus] = useState<LiveSttStatus>('idle');
  const [statusText, setStatusText] = useState('Kapalı');
  const [lines, setLines] = useState<LiveSttLine[]>([]);
  const [partialLine, setPartialLine] = useState<LiveSttLine | null>(null);
  const [error, setError] = useState<string | null>(null);

  const socketRef = useRef<WebSocket | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const sourceNodeRef = useRef<MediaElementAudioSourceNode | MediaStreamAudioSourceNode | null>(null);
  const sourceElementRef = useRef<HTMLMediaElement | null>(null);
  const processorRef = useRef<ScriptProcessorNode | null>(null);
  const silentGainRef = useRef<GainNode | null>(null);
  const sourceOutputConnectedRef = useRef(false);
  const sourceNeedsOutputRef = useRef(false);
  const pendingSamplesRef = useRef<number[]>([]);
  const pendingStartTimeRef = useRef<number | null>(null);
  const pendingEndTimeRef = useRef<number | null>(null);
  const lastSentMediaTimeRef = useRef<number | null>(null);
  const lastPublishUntilRef = useRef<number | null>(null);
  const displayLagSecondsRef = useRef(DEFAULT_DISPLAY_LAG_SECONDS);
  const chunkPublishUntilRef = useRef<Map<string, number>>(new Map());
  const inFlightChunksRef = useRef(0);
  const chunkIndexRef = useRef(0);
  const manualSocketCloseRef = useRef(false);
  const latestPlaybackRef = useRef(playback);

  const isBusy = status === 'listening' || status === 'resolving';

  useEffect(() => {
    latestPlaybackRef.current = playback;
  }, [playback]);

  useEffect(() => {
    onBusyChange?.(isBusy);
  }, [isBusy, onBusyChange]);

  const sendSocketJson = useCallback((payload: Record<string, unknown>) => {
    const socket = socketRef.current;
    if (socket?.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify(payload));
    }
  }, []);

  const flushPendingSamples = useCallback((force: boolean) => {
    const rolling = pendingSamplesRef.current;
    if (rolling.length < MIN_FLUSH_SAMPLE_COUNT) {
      return;
    }

    const startTime = pendingStartTimeRef.current ?? Math.max(0, latestPlaybackRef.current.currentTime - rolling.length / TARGET_SAMPLE_RATE);
    const endTime = pendingEndTimeRef.current ?? latestPlaybackRef.current.currentTime;
    const lastSentTime = lastSentMediaTimeRef.current;
    if (!force && lastSentTime !== null && endTime - lastSentTime < DECODE_INTERVAL_SECONDS) {
      return;
    }

    const lastPublishUntil = lastPublishUntilRef.current ?? startTime;
    const publishAfter = Math.max(startTime, lastPublishUntil);
    const displayLag = displayLagSecondsRef.current;
    const publishUntil = force ? endTime : Math.max(startTime, endTime - displayLag);
    if (!force && publishUntil <= publishAfter + MIN_PUBLISH_ADVANCE_SECONDS) {
      return;
    }
    if (publishUntil <= startTime || (!force && inFlightChunksRef.current > 0)) {
      return;
    }

    const chunkId = `live-${Date.now()}-${chunkIndexRef.current++}`;
    chunkPublishUntilRef.current.set(chunkId, publishUntil);
    lastSentMediaTimeRef.current = endTime;
    inFlightChunksRef.current += 1;
    sendSocketJson({
      type: 'chunk',
      chunk_id: chunkId,
      media_time_start: roundTime(startTime),
      media_time_end: roundTime(endTime),
      publish_after: roundTime(publishAfter),
      publish_until: roundTime(publishUntil),
      audio_b64: pcm16SamplesToBase64(rolling),
    });
  }, [sendSocketJson]);

  const stopAudioCapture = useCallback((flush: boolean) => {
    if (flush) {
      flushPendingSamples(true);
    } else {
      pendingSamplesRef.current = [];
      pendingStartTimeRef.current = null;
      pendingEndTimeRef.current = null;
      lastSentMediaTimeRef.current = null;
      lastPublishUntilRef.current = null;
      displayLagSecondsRef.current = DEFAULT_DISPLAY_LAG_SECONDS;
      chunkPublishUntilRef.current.clear();
      inFlightChunksRef.current = 0;
    }

    processorRef.current?.disconnect();
    silentGainRef.current?.disconnect();
    processorRef.current = null;
    silentGainRef.current = null;
  }, [flushPendingSamples]);

  const startAudioCapture = useCallback(async () => {
    if (!enabled || !mediaElement) {
      return;
    }

    try {
      const AudioContextCtor = window.AudioContext || window.webkitAudioContext;
      if (!AudioContextCtor) {
        throw new Error('Web Audio desteklenmiyor.');
      }
      const audioContext = audioContextRef.current ?? new AudioContextCtor();
      audioContextRef.current = audioContext;
      await audioContext.resume();

      let sourceNode = sourceNodeRef.current;
      if (!sourceNode || sourceElementRef.current !== mediaElement) {
        sourceNodeRef.current?.disconnect();
        const capturedStream = captureMediaElementStream(mediaElement);
        if (capturedStream?.getAudioTracks().length) {
          sourceNode = audioContext.createMediaStreamSource(capturedStream);
          sourceNeedsOutputRef.current = false;
        } else {
          sourceNode = audioContext.createMediaElementSource(mediaElement);
          sourceNeedsOutputRef.current = true;
        }
        sourceNodeRef.current = sourceNode;
        sourceElementRef.current = mediaElement;
        sourceOutputConnectedRef.current = false;
      }

      if (sourceNeedsOutputRef.current && !sourceOutputConnectedRef.current) {
        sourceNode.connect(audioContext.destination);
        sourceOutputConnectedRef.current = true;
      }

      if (processorRef.current) {
        return;
      }

      const processor = audioContext.createScriptProcessor(4096, 2, 1);
      const silentGain = audioContext.createGain();
      silentGain.gain.value = 0;
      sourceNode.connect(processor);
      processor.connect(silentGain);
      silentGain.connect(audioContext.destination);

      processor.onaudioprocess = (event) => {
        if (!latestPlaybackRef.current.isPlaying || socketRef.current?.readyState !== WebSocket.OPEN) {
          return;
        }
        const mono = mixToMono(event.inputBuffer);
        const downsampled = downsampleToPcm16(mono, audioContext.sampleRate, TARGET_SAMPLE_RATE);
        if (!downsampled.length) {
          return;
        }

        const currentTime = mediaElement.currentTime || latestPlaybackRef.current.currentTime;
        const chunkSeconds = downsampled.length / TARGET_SAMPLE_RATE;
        if (pendingStartTimeRef.current === null) {
          pendingStartTimeRef.current = Math.max(0, currentTime - chunkSeconds);
        }
        pendingEndTimeRef.current = currentTime;
        for (const sample of downsampled) {
          pendingSamplesRef.current.push(sample);
        }
        const overflow = pendingSamplesRef.current.length - ROLLING_CONTEXT_SAMPLE_COUNT;
        if (overflow > 0) {
          pendingSamplesRef.current.splice(0, overflow);
          pendingStartTimeRef.current = (pendingStartTimeRef.current ?? 0) + overflow / TARGET_SAMPLE_RATE;
        }
        flushPendingSamples(false);
      };

      processorRef.current = processor;
      silentGainRef.current = silentGain;
    } catch (captureError) {
      setStatus('error');
      setStatusText('Bağlantı hatası');
      setError(captureError instanceof Error ? captureError.message : 'Player sesi yakalanamadı.');
    }
  }, [enabled, flushPendingSamples, mediaElement]);

  const clearLines = useCallback(() => {
    setLines([]);
    setPartialLine(null);
  }, []);

  const adjustDisplayLag = useCallback((message: LiveSttSocketMessage) => {
    const segments = message.segments ?? [];
    const text = (message.text || segments.map((segment) => segment.text || '').join(' ')).trim();
    const hasText = Boolean(text);
    const avgLogprobValues = segments
      .map((segment) => numberOrNull(segment.avg_logprob))
      .filter((value): value is number => value !== null);
    const noSpeechValues = segments
      .map((segment) => numberOrNull(segment.no_speech_prob))
      .filter((value): value is number => value !== null);
    const avgLogprob = avgLogprobValues.length
      ? avgLogprobValues.reduce((sum, value) => sum + value, 0) / avgLogprobValues.length
      : 0;
    const maxNoSpeech = noSpeechValues.length ? Math.max(...noSpeechValues) : 0;
    const lastPublished = lastPublishUntilRef.current ?? numberOr(message.media_time_end, 0);
    const liveEdge = numberOr(message.media_time_end, lastPublished);
    const backlog = liveEdge - lastPublished;

    let nextLag = displayLagSecondsRef.current;
    if (!hasText || maxNoSpeech > 0.45 || avgLogprob < -0.85) {
      nextLag += 0.35;
    } else if (backlog > nextLag + 2.4) {
      nextLag -= 0.45;
    } else if (hasStrongLiveEnding(text) && avgLogprob > -0.55) {
      nextLag -= 0.2;
    } else if (!hasStrongLiveEnding(text) && text.split(/\s+/).length <= 4) {
      nextLag += 0.2;
    } else {
      nextLag -= 0.08;
    }

    displayLagSecondsRef.current = clampNumber(nextLag, MIN_DISPLAY_LAG_SECONDS, MAX_DISPLAY_LAG_SECONDS);
  }, []);

  const registerChunkFinished = useCallback((message: LiveSttSocketMessage) => {
    if (message.chunk_id) {
      const publishedUntil = chunkPublishUntilRef.current.get(message.chunk_id)
        ?? numberOrNull(message.publish_until)
        ?? numberOrNull(message.media_time_end);
      chunkPublishUntilRef.current.delete(message.chunk_id);
      if (typeof publishedUntil === 'number') {
        lastPublishUntilRef.current = Math.max(lastPublishUntilRef.current ?? 0, publishedUntil);
      }
    }
    adjustDisplayLag(message);
    inFlightChunksRef.current = Math.max(0, inFlightChunksRef.current - 1);
  }, [adjustDisplayLag]);

  useEffect(() => {
    if (!mediaKey) {
      clearLines();
      return;
    }
    clearLines();
    pendingSamplesRef.current = [];
    pendingStartTimeRef.current = null;
    pendingEndTimeRef.current = null;
    lastSentMediaTimeRef.current = null;
    lastPublishUntilRef.current = null;
    displayLagSecondsRef.current = DEFAULT_DISPLAY_LAG_SECONDS;
    chunkPublishUntilRef.current.clear();
    inFlightChunksRef.current = 0;
    chunkIndexRef.current = 0;
  }, [clearLines, mediaKey]);

  useEffect(() => {
    if (!enabled) {
      manualSocketCloseRef.current = true;
      socketRef.current?.close(1000, 'preview-disabled');
      socketRef.current = null;
      stopAudioCapture(false);
      setStatus('idle');
      setStatusText('Kapalı');
      setPartialLine(null);
      setError(null);
      return undefined;
    }

    if (!mediaElement) {
      setStatus('ready');
      setStatusText('Hazır');
      return undefined;
    }

    manualSocketCloseRef.current = false;
    setStatus('ready');
    setStatusText('Hazır');
    setError(null);
    const socket = new WebSocket(createLiveSttSocketUrl());
    socketRef.current = socket;

    socket.onopen = () => {
      socket.send(JSON.stringify({ type: 'start', sample_rate: TARGET_SAMPLE_RATE, format: 'pcm_s16le' }));
      if (latestPlaybackRef.current.isPlaying) {
        socket.send(JSON.stringify({ type: 'resume' }));
      }
    };

    socket.onmessage = (event) => {
      const message = parseSocketMessage(event.data);
      if (!message) {
        return;
      }
      if (message.type === 'ready') {
        setStatus('ready');
        setStatusText('Hazır');
        return;
      }
      if (message.type === 'status') {
        setStatus(message.status ?? 'ready');
        setStatusText(message.message || statusLabel(message.status ?? 'ready'));
        return;
      }
      if (message.type === 'partial') {
        const line = messageToLine(message, false);
        setPartialLine(line);
        return;
      }
      if (message.type === 'final') {
        registerChunkFinished(message);
        setPartialLine(null);
        const finalLines = messageToFinalLines(message);
        if (finalLines.length) {
          setLines((current) => [...current, ...finalLines].slice(-80));
        }
        return;
      }
      if (message.type === 'error') {
        registerChunkFinished(message);
        setStatus('error');
        setStatusText('Bağlantı hatası');
        setError(message.message || 'Live STT Preview hatası');
      }
    };

    socket.onerror = () => {
      setStatus('error');
      setStatusText('Bağlantı hatası');
      setError('Live STT Preview bağlantısı kurulamadı.');
    };

    socket.onclose = () => {
      if (!manualSocketCloseRef.current) {
        setStatus('error');
        setStatusText('Bağlantı hatası');
        setError('Live STT Preview bağlantısı kapandı.');
      }
    };

    return () => {
      manualSocketCloseRef.current = true;
      socket.close(1000, 'preview-cleanup');
      if (socketRef.current === socket) {
        socketRef.current = null;
      }
      stopAudioCapture(false);
    };
  }, [enabled, mediaElement, registerChunkFinished, stopAudioCapture]);

  useEffect(() => {
    if (!enabled || !mediaElement) {
      return;
    }

    if (playback.isPlaying) {
      sendSocketJson({ type: 'resume' });
      void startAudioCapture();
    } else {
      sendSocketJson({ type: 'pause' });
      stopAudioCapture(true);
    }
  }, [enabled, mediaElement, playback.isPlaying, sendSocketJson, startAudioCapture, stopAudioCapture]);

  useEffect(() => {
    if (!enabled || !seekRequest) {
      return;
    }
    pendingSamplesRef.current = [];
    pendingStartTimeRef.current = null;
    pendingEndTimeRef.current = null;
    lastSentMediaTimeRef.current = null;
    lastPublishUntilRef.current = null;
    displayLagSecondsRef.current = DEFAULT_DISPLAY_LAG_SECONDS;
    chunkPublishUntilRef.current.clear();
    inFlightChunksRef.current = 0;
    setPartialLine(null);
    sendSocketJson({ type: 'seek', media_time: roundTime(seekRequest.time) });
  }, [enabled, seekRequest, sendSocketJson]);

  return useMemo(
    () => ({
      status,
      statusText,
      lines,
      partialLine,
      error,
      isBusy,
      clearLines,
    }),
    [clearLines, error, isBusy, lines, partialLine, status, statusText],
  );
}

function createLiveSttSocketUrl(): string {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${protocol}//${window.location.host}/api/stt/preview/ws`;
}

function captureMediaElementStream(mediaElement: HTMLMediaElement): MediaStream | null {
  const capturable = mediaElement as HTMLMediaElement & {
    captureStream?: () => MediaStream;
    mozCaptureStream?: () => MediaStream;
  };
  try {
    return capturable.captureStream?.() ?? capturable.mozCaptureStream?.() ?? null;
  } catch {
    return null;
  }
}

function statusLabel(status: LiveSttStatus): string {
  const labels: Record<LiveSttStatus, string> = {
    idle: 'Kapalı',
    ready: 'Hazır',
    listening: 'Dinliyor',
    resolving: 'Çözümlüyor',
    paused: 'Durakladı',
    error: 'Bağlantı hatası',
  };
  return labels[status];
}

function parseSocketMessage(data: unknown): LiveSttSocketMessage | null {
  if (typeof data !== 'string') {
    return null;
  }
  try {
    return JSON.parse(data) as LiveSttSocketMessage;
  } catch {
    return null;
  }
}

function messageToLine(message: LiveSttSocketMessage, isFinal: boolean): LiveSttLine | null {
  const text = (message.text || '').trim();
  if (!text) {
    return null;
  }
  return {
    id: message.chunk_id || `live-${Date.now()}`,
    start: numberOr(message.media_time_start, 0),
    end: numberOr(message.media_time_end, numberOr(message.media_time_start, 0)),
    text,
    language: message.language,
    isFinal,
  };
}

function messageToFinalLines(message: LiveSttSocketMessage): LiveSttLine[] {
  const segments = message.segments ?? [];
  const mapped: LiveSttLine[] = [];
  segments.forEach((segment, index) => {
    const text = (segment.text || '').trim();
    if (!text) {
      return;
    }
    mapped.push({
      id: segment.id || `${message.chunk_id || 'live'}-${index}`,
      start: numberOr(segment.start, numberOr(message.media_time_start, 0)),
      end: numberOr(segment.end, numberOr(message.media_time_end, numberOr(message.media_time_start, 0))),
      text,
      language: segment.language ?? message.language,
      isFinal: true,
    });
  });

  if (mapped.length) {
    return mapped;
  }

  const fallback = messageToLine(message, true);
  return fallback ? [fallback] : [];
}

function mixToMono(buffer: AudioBuffer): Float32Array {
  const channelCount = buffer.numberOfChannels;
  const length = buffer.length;
  const mono = new Float32Array(length);
  for (let channel = 0; channel < channelCount; channel += 1) {
    const data = buffer.getChannelData(channel);
    for (let index = 0; index < length; index += 1) {
      mono[index] += data[index] / channelCount;
    }
  }
  return mono;
}

function downsampleToPcm16(input: Float32Array, sourceRate: number, targetRate: number): Int16Array {
  if (!input.length || sourceRate <= 0) {
    return new Int16Array();
  }
  const ratio = sourceRate / targetRate;
  const outputLength = Math.floor(input.length / ratio);
  const output = new Int16Array(outputLength);
  for (let outputIndex = 0; outputIndex < outputLength; outputIndex += 1) {
    const start = Math.floor(outputIndex * ratio);
    const end = Math.min(input.length, Math.floor((outputIndex + 1) * ratio));
    let sum = 0;
    let count = 0;
    for (let inputIndex = start; inputIndex < end; inputIndex += 1) {
      sum += input[inputIndex];
      count += 1;
    }
    const sample = count > 0 ? sum / count : input[start] ?? 0;
    output[outputIndex] = clampPcm16(sample);
  }
  return output;
}

function clampPcm16(sample: number): number {
  const clamped = Math.max(-1, Math.min(1, sample));
  return clamped < 0 ? Math.round(clamped * 32768) : Math.round(clamped * 32767);
}

function pcm16SamplesToBase64(samples: number[] | Int16Array): string {
  const bytes = new Uint8Array(samples.length * 2);
  const view = new DataView(bytes.buffer);
  samples.forEach((sample, index) => {
    view.setInt16(index * 2, sample, true);
  });
  let binary = '';
  const batchSize = 0x8000;
  for (let index = 0; index < bytes.length; index += batchSize) {
    binary += String.fromCharCode(...bytes.subarray(index, index + batchSize));
  }
  return window.btoa(binary);
}

function numberOr(value: unknown, fallback: number): number {
  return typeof value === 'number' && Number.isFinite(value) ? value : fallback;
}

function numberOrNull(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
}

function clampNumber(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

function hasStrongLiveEnding(text: string): boolean {
  return /[.!?…][)"'»”’\]]*$/.test(text.trim());
}

function roundTime(value: number): number {
  return Math.max(0, Math.round(value * 1000) / 1000);
}

declare global {
  interface Window {
    webkitAudioContext?: typeof AudioContext;
  }
}
