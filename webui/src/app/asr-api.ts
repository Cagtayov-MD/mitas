export type AsrJobStatus = 'queued' | 'running' | 'done' | 'partial' | 'failed';

export interface AsrSegment {
  start: number;
  end: number;
  text: string;
  speaker?: string | null;
  language?: string | null;
  avg_logprob?: number;
  no_speech_prob?: number;
  channel?: string | null;
  flags?: string[];
}

export type AsrChannelKey = 'L' | 'R';
export type AsrChannelState = Record<AsrChannelKey, boolean>;

export interface AsrJob {
  job_id: string;
  status: AsrJobStatus;
  filename: string;
  size_bytes: number;
  profile: string;
  channel_mode: string;
  created_at: string;
  started_at?: string | null;
  completed_at?: string | null;
  message?: string | null;
  error?: string | null;
  output_dir?: string;
  progress_percent?: number;
  progress_label?: string | null;
  elapsed_seconds?: number;
  logs?: AsrJobLog[];
  summary?: {
    audio_duration?: number;
    clean_segments?: number;
    raw_segments?: number;
    quality_drops?: number;
    profile_used?: string;
    model_name?: string;
    fallback_triggered?: boolean;
    safety?: {
      safe?: boolean | null;
      failure_reason?: string | null;
    };
    timing?: {
      total_seconds?: number | null;
      decode_seconds?: number | null;
      chunk_count?: number | null;
    };
  };
  archive?: {
    quality?: {
      drops?: number;
      drop_reasons?: Record<string, number>;
      safety_passed?: boolean | null;
    };
  };
  transcript: string;
  segments: AsrSegment[];
}

export interface AsrJobLog {
  ts: string;
  level?: 'info' | 'warning' | 'error' | string;
  stage?: string;
  message: string;
  progress_percent?: number;
}

export interface TranslationResult {
  text: string;
  model: string;
  source_lang: string;
  target_lang: string;
  cache_hit: boolean;
  latency_ms: number;
  created_at: string;
}

export type SegmentTranslationState =
  | { status: 'loading' }
  | { status: 'done'; result: TranslationResult }
  | { status: 'error'; error: string };

interface TranslateSegmentsResponse {
  items: Array<{
    segment_id: string;
    translation: TranslationResult;
  }>;
  cache_dir: string;
}

export interface PlaybackState {
  currentTime: number;
  duration: number;
  isPlaying: boolean;
}

export interface SeekRequest {
  id: number;
  time: number;
}

export type AnalysisProfile = 'documentary' | 'music_entertainment' | 'sports' | 'studio' | 'news' | 'stt';

export interface AnalysisProfileOption {
  value: AnalysisProfile;
  label: string;
  description: string;
}

export const ANALYSIS_PROFILE_OPTIONS: AnalysisProfileOption[] = [
  { value: 'documentary', label: 'Belgesel', description: 'Belgesel içerik profili' },
  { value: 'music_entertainment', label: 'Müzik / Eğlence', description: 'Program, konser, performans ve eğlence akışı' },
  { value: 'sports', label: 'Spor Karşılaşmaları', description: 'Maç ve canlı spor yayını profili' },
  { value: 'studio', label: 'Stüdyo Programları', description: 'Çok konuşmacılı stüdyo/panel profili' },
  { value: 'news', label: 'Haber', description: 'Haber bülteni ve haber paketi profili' },
  { value: 'stt', label: 'STT', description: 'Speech to Text / konuşmadan metne' },
];

export function analysisProfileLabel(profile: AnalysisProfile): string {
  return ANALYSIS_PROFILE_OPTIONS.find((option) => option.value === profile)?.label ?? profile;
}

export function defaultAsrChannelState(): AsrChannelState {
  return { L: true, R: true };
}

export async function startAsrJob(file: File): Promise<AsrJob> {
  const params = new URLSearchParams({
    filename: file.name,
    profile: 'fast_with_fallback',
    channel_mode: 'auto',
  });
  const response = await fetch(`/api/asr/transcribe?${params.toString()}`, {
    method: 'POST',
    headers: {
      'content-type': file.type || 'application/octet-stream',
    },
    body: file,
  });

  if (!response.ok) {
    throw new Error(await readError(response));
  }
  return response.json();
}

export async function fetchAsrJob(jobId: string): Promise<AsrJob> {
  const response = await fetch(`/api/jobs/${encodeURIComponent(jobId)}`);
  if (!response.ok) {
    throw new Error(await readError(response));
  }
  return response.json();
}

export async function fetchRecentAsrJobs(limit = 1): Promise<AsrJob[]> {
  const params = new URLSearchParams({ limit: String(limit) });
  const response = await fetch(`/api/jobs?${params.toString()}`);
  if (!response.ok) {
    throw new Error(await readError(response));
  }
  const payload = (await response.json()) as { jobs?: AsrJob[] };
  return payload.jobs ?? [];
}

export async function translateAsrSegment(jobId: string, index: number, segment: AsrSegment): Promise<TranslationResult> {
  const effectiveSourceLang = guessSegmentSourceLanguage(segment);
  if (effectiveSourceLang === 'tr') {
    return originalTurkishResult(segment.text);
  }

  const segmentId = `seg_${index.toString().padStart(4, '0')}`;
  const response = await fetch('/api/translate/segments', {
    method: 'POST',
    headers: {
      'content-type': 'application/json',
    },
    body: JSON.stringify({
      job_id: jobId,
      target_lang: 'tr',
      items: [
        {
          segment_id: segmentId,
          source_text: segment.text,
          source_lang: effectiveSourceLang,
        },
      ],
    }),
  });

  if (!response.ok) {
    throw new Error(await readError(response));
  }
  const payload = (await response.json()) as TranslateSegmentsResponse;
  const translation = payload.items[0]?.translation;
  if (!translation) {
    throw new Error('Çeviri sonucu boş döndü.');
  }
  return translation;
}

export async function translateAsrSegments(jobId: string, segments: AsrSegment[]): Promise<Record<number, TranslationResult>> {
  const results: Record<number, TranslationResult> = {};
  const remoteItems: Array<{ index: number; segment_id: string; source_text: string; source_lang: string }> = [];

  segments.forEach((segment, index) => {
    const text = segment.text.trim();
    if (!text) {
      return;
    }
    const sourceLang = guessSegmentSourceLanguage(segment);
    if (sourceLang === 'tr') {
      return;
    }
    remoteItems.push({
      index,
      segment_id: `seg_${index.toString().padStart(4, '0')}`,
      source_text: text,
      source_lang: sourceLang,
    });
  });

  for (let start = 0; start < remoteItems.length; start += 40) {
    const chunk = remoteItems.slice(start, start + 40);
    const response = await fetch('/api/translate/segments', {
      method: 'POST',
      headers: {
        'content-type': 'application/json',
      },
      body: JSON.stringify({
        job_id: jobId,
        target_lang: 'tr',
        items: chunk.map(({ segment_id, source_text, source_lang }) => ({
          segment_id,
          source_text,
          source_lang,
        })),
      }),
    });

    if (!response.ok) {
      throw new Error(await readError(response));
    }
    const payload = (await response.json()) as TranslateSegmentsResponse;
    payload.items.forEach((item) => {
      const match = chunk.find((queued) => queued.segment_id === item.segment_id);
      if (match) {
        results[match.index] = item.translation;
      }
    });
  }

  return results;
}

export async function translateFreeTextToTurkish(text: string, sourceLang = 'en'): Promise<TranslationResult> {
  const normalizedText = text.trim();
  if (!normalizedText) {
    throw new Error('Çevrilecek metin boş.');
  }
  const response = await fetch('/api/translate/segments', {
    method: 'POST',
    headers: {
      'content-type': 'application/json',
    },
    body: JSON.stringify({
      target_lang: 'tr',
      items: [
        {
          segment_id: `live_${Date.now()}`,
          source_text: normalizedText,
          source_lang: normalizeSourceLanguage(sourceLang) ?? 'en',
        },
      ],
    }),
  });

  if (!response.ok) {
    throw new Error(await readError(response));
  }
  const payload = (await response.json()) as TranslateSegmentsResponse;
  const translation = payload.items[0]?.translation;
  if (!translation) {
    throw new Error('Çeviri sonucu boş döndü.');
  }
  return translation;
}

async function readError(response: Response): Promise<string> {
  try {
    const payload = await response.json();
    return payload.detail || payload.error || response.statusText;
  } catch {
    return response.statusText;
  }
}

export function isAsrJobFinished(job: AsrJob | null): boolean {
  return job?.status === 'done' || job?.status === 'partial' || job?.status === 'failed';
}

export function formatClock(seconds: number | undefined | null): string {
  if (!Number.isFinite(seconds ?? NaN)) {
    return '00:00:00';
  }
  const total = Math.max(0, Math.floor(seconds ?? 0));
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const secs = total % 60;
  return [hours, minutes, secs].map((value) => value.toString().padStart(2, '0')).join(':');
}

export function segmentConfidence(segment: AsrSegment): number {
  if (typeof segment.avg_logprob === 'number') {
    return Math.max(0, Math.min(1, Math.exp(segment.avg_logprob)));
  }
  if (typeof segment.no_speech_prob === 'number') {
    return Math.max(0, Math.min(1, 1 - segment.no_speech_prob));
  }
  return 0;
}

export function normalizeSourceLanguage(language: string | null | undefined): string | null {
  const value = (language ?? '').trim().toLowerCase().replace('_', '-');
  if (!value || value === 'unknown' || value === 'und') {
    return null;
  }
  if (value.startsWith('en')) {
    return 'en';
  }
  if (value.startsWith('tr') || value.startsWith('tur')) {
    return 'tr';
  }
  return value.split('-')[0] || null;
}

export function isTurkishSourceLanguage(language: string | null | undefined): boolean {
  return normalizeSourceLanguage(language) === 'tr';
}

export function shouldOfferTurkishTranslation(segment: Pick<AsrSegment, 'text' | 'language'>): boolean {
  if (!segment.text.trim()) {
    return false;
  }
  return guessSegmentSourceLanguage(segment) !== 'tr';
}

export function guessSegmentSourceLanguage(segment: Pick<AsrSegment, 'text' | 'language'>): string {
  const text = segment.text.toLocaleLowerCase('tr-TR');
  const normalized = normalizeSourceLanguage(segment.language);
  if (normalized === 'tr') {
    return 'tr';
  }
  const englishHits = countWordHits(text, [
    'the',
    'prime',
    'minister',
    'please',
    'debate',
    'again',
    'time',
    'would',
    'apologize',
    "can't",
    'cannot',
    "don't",
    'have',
    'start',
  ]);
  const turkishHits = countWordHits(text, [
    'abi',
    'acaba',
    'ama',
    'ancak',
    'artık',
    'bakan',
    'başkan',
    'ben',
    'beni',
    'benim',
    'biz',
    'bizim',
    'bunu',
    'böyle',
    'çok',
    'daha',
    'da',
    'de',
    'için',
    'ile',
    'ki',
    'mı',
    'mi',
    'mu',
    'mü',
    'ne',
    'neden',
    'nasıl',
    'evet',
    'hayır',
    'değil',
    'davos',
    'şimdi',
    'sonra',
    'önce',
    'olan',
    'olarak',
    'oldu',
    'olacak',
    'var',
    'yok',
    'sesin',
    'yüksek',
    'öldürmeye',
    'gelince',
    'bilirsiniz',
  ]);
  if (/[çğıöşü]/i.test(text) || turkishHits >= 2 || (turkishHits >= 1 && englishHits === 0)) {
    return 'tr';
  }
  if (englishHits >= 2 && englishHits > turkishHits) {
    return 'en';
  }
  if (normalized && !isTurkishSourceLanguage(normalized)) {
    return normalized;
  }
  return 'en';
}

function countWordHits(text: string, words: string[]): number {
  return words.reduce((count, word) => {
    const escaped = word.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    return count + (new RegExp(`(^|\\s)${escaped}($|\\s|[,.!?;:])`, 'i').test(text) ? 1 : 0);
  }, 0);
}

function originalTurkishResult(text: string): TranslationResult {
  return {
    text,
    model: 'source-tr',
    source_lang: 'tr',
    target_lang: 'tr',
    cache_hit: true,
    latency_ms: 0,
    created_at: new Date().toISOString(),
  };
}
