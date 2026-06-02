export type AsrJobStatus = 'queued' | 'running' | 'done' | 'partial' | 'failed';

export interface AsrSegment {
  start: number;
  end: number;
  text: string;
  normalized_text?: string;
  speaker?: string | null;
  language?: string | null;
  avg_logprob?: number;
  no_speech_prob?: number;
  channel?: string | null;
  flags?: string[];
  word_timestamps?: Array<{
    word: string;
    start: number;
    end: number;
    source?: string;
    score?: number;
  }>;
}

export type AsrChannelKey = 'L' | 'R';
export type AsrChannelState = Record<AsrChannelKey, boolean>;

export interface AsrJob {
  job_id: string;
  clip_id?: string;
  media_id?: string;
  status: AsrJobStatus;
  filename: string;
  size_bytes: number;
  profile: string;
  content_profile?: string | null;
  diarize?: 'auto' | 'on' | 'off';
  word_alignment_mode?: 'whisperx' | 'interpolated' | 'off';
  channel_mode: string;
  created_at: string;
  started_at?: string | null;
  completed_at?: string | null;
  message?: string | null;
  error?: string | null;
  original_source_path?: string | null;
  input_path?: string;
  output_dir?: string;
  job_dir?: string;
  clip_dir?: string;
  log_path?: string;
  archive_path?: string;
  module_run_path?: string;
  summary_path?: string;
  transcript_review_path?: string;
  timeline_events_path?: string;
  transcript_summary_path?: string;
  progress_percent?: number;
  progress_label?: string | null;
  elapsed_seconds?: number;
  logs?: AsrJobLog[];
  summary?: {
    pipeline_version?: string;
    code_version?: string;
    input_path?: string;
    normalized_audio_path?: string;
    audio_duration?: number;
    clean_segments?: number;
    raw_segments?: number;
    quality_drops?: number;
    duplicate_drops?: number;
    clean_words?: number;
    profile_used?: string;
    profile_requested?: string;
    model_name?: string;
    fallback_triggered?: boolean;
    fallback_reason?: string | null;
    selection_reason?: string | null;
    normalized_entities?: number;
    fallback_report?: Record<string, unknown>;
    word_alignment?: {
      status?: string;
      method?: string;
      fallback_method?: string | null;
      expected_words?: number;
      aligned_words?: number;
      coverage?: number | null;
      success?: boolean | null;
      reason?: string | null;
    };
    language_intelligence?: {
      enabled?: boolean;
      mode?: 'off' | 'shadow' | string;
      status?: string;
      model_name?: string;
      model_source?: string;
      pilot_languages?: string[];
      unsupported_asr_languages?: string[];
      timeline_granularity?: string;
      runtime_sec?: number | null;
      runtime_budget_seconds?: number | null;
      sampled_speech_seconds?: number | null;
      master_language?: string | null;
      master_raw_score?: number | null;
      calibrated_confidence?: number | null;
      calibration_version?: string | null;
      language_distribution?: Record<string, number>;
      mixed_window_count?: number;
      low_confidence_window_count?: number;
      unsupported_asr?: boolean;
      pilot_language?: boolean;
      decision_reason?: string | null;
      skipped_reason?: string | null;
      error?: string | null;
      routing?: {
        enabled?: boolean;
        applied?: boolean;
        reason?: string;
        guardrails?: Record<string, string>;
      };
      eval_requirements?: {
        minimum_labeled_segments?: number;
        az_tr_pair_segments_before_routing?: number;
        code_switching_category_required?: boolean;
      };
      windows?: Array<{
        start: number;
        end: number;
        duration?: number;
        language?: string;
        decision?: string;
        raw_score?: number | null;
        margin?: number | null;
        calibrated_confidence?: number | null;
        calibration_version?: string | null;
        decision_reason?: string;
        top_candidates?: Array<{
          language?: string;
          raw_score?: number | null;
          calibrated_confidence?: number | null;
          calibration_version?: string | null;
        }>;
      }>;
      notes?: string[];
    };
    vad?: {
      speech_seconds?: number;
      speech_ratio?: number;
      segment_count?: number;
    };
    channels?: {
      requested_mode?: string;
      mode?: string;
      tracks?: string[];
      duplicate_drops?: number;
    };
    quality_report?: {
      error_flags?: string[];
      selective_quality_repair?: Record<string, unknown>;
      vad_gap_repair?: Record<string, unknown>;
      speaker_word_timeline?: {
        status?: string;
        reason?: string | null;
        segments?: number;
        speaker_segments?: number;
        word_timed_segments?: number;
        speaker_word_segments?: number;
        speaker_segment_coverage?: number;
        word_timed_segment_coverage?: number;
        speaker_word_segment_coverage?: number;
        timed_words?: number;
        speaker_timed_words?: number;
      };
      entity_normalization?: {
        status?: string;
        method?: string;
        count?: number;
        items?: unknown[];
      };
    };
    safety?: {
      safe?: boolean | null;
      failure_reason?: string | null;
      diagnostics?: {
        uncovered_vad_ranges?: Array<{
          start: number;
          end: number;
          range_seconds: number;
          speech_seconds: number;
        }>;
      };
    };
    timing?: {
      normalize_seconds?: number | null;
      transcribe_total_seconds?: number | null;
      total_seconds?: number | null;
      decode_seconds?: number | null;
      chunk_count?: number | null;
      fallback_seconds?: number | null;
      fallback_chunk_count?: number | null;
      fallback_total_chunk_count?: number | null;
      fallback_mode?: string | null;
    };
  };
  module_run?: {
    module_run_id?: string;
    job_id?: string;
    media_id?: string;
    module_name?: string;
    module_version?: string;
    model_name?: string;
    model_version?: string | null;
    status?: string;
    started_at?: string | null;
    completed_at?: string | null;
    runtime_sec?: number | null;
    gpu_used?: boolean | null;
    vram_peak_mb?: number | null;
    error_msg?: string | null;
  };
  archive?: {
    quality?: {
      drops?: number;
      drop_reasons?: Record<string, number>;
      safety_passed?: boolean | null;
    };
  };
  transcript: string;
  transcript_summary?: TranscriptSummary;
  search_match?: {
    scope: 'metadata' | 'transcript' | string;
    label?: string;
    count?: number;
    snippet?: string;
  };
  module_summary?: Partial<Record<ClipGeneratedDataKind, {
    status?: string | null;
    latest_job_id?: string | null;
    job_count?: number;
    updated_at?: string | null;
  }>>;
  segments: AsrSegment[];
  timeline_events?: Array<Record<string, unknown>>;
}

export interface TranscriptSummary {
  job_id: string;
  filename?: string | null;
  created_at: string;
  elapsed_seconds?: number;
  provider: string;
  model: string;
  summary: string;
  source_chars?: number;
  used_chars?: number;
  note?: string;
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
  source_variant?: string | null;
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

export type AnalysisProfile = 'film' | 'dizi' | 'documentary' | 'music_entertainment' | 'sports' | 'studio' | 'news' | 'stt';
export type AsrContentProfile = 'bulten_haber' | 'studio_panel' | 'muzik_programi' | 'film' | 'belgesel' | 'spor';

export const OCR_ANALYSIS_PROFILES: readonly AnalysisProfile[] = ['film', 'dizi', 'documentary', 'music_entertainment', 'studio'];
export function profileRunsOcr(profile: AnalysisProfile): boolean { return OCR_ANALYSIS_PROFILES.includes(profile); }
export type ClipGeneratedDataKind = 'asr' | 'ocr' | 'face' | 'tag';

export interface AnalysisProfileOption {
  value: AnalysisProfile;
  label: string;
  description: string;
}

export const ANALYSIS_PROFILE_OPTIONS: AnalysisProfileOption[] = [
  { value: 'film', label: 'Film', description: 'İlk 8 oyuncu + yapımcı/yönetmen + özet (künye → PDF)' },
  { value: 'dizi', label: 'Dizi', description: 'Tüm oyuncular + özet (künye → PDF)' },
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

export function contentProfileForAnalysisProfile(profile: AnalysisProfile): AsrContentProfile {
  switch (profile) {
    case 'documentary':
      return 'belgesel';
    case 'music_entertainment':
      return 'muzik_programi';
    case 'studio':
      return 'studio_panel';
    case 'sports':
      return 'spor';
    case 'film':
    case 'dizi':
      return 'film';
    case 'news':
    case 'stt':
    default:
      return 'bulten_haber';
  }
}

export async function startAsrJob(file: File, analysisProfile: AnalysisProfile = 'stt', options: { signal?: AbortSignal; force?: boolean } = {}): Promise<AsrJob> {
  const params = new URLSearchParams({
    filename: file.name,
    content_profile: contentProfileForAnalysisProfile(analysisProfile),
    diarize: 'auto',
    channel_mode: 'auto',
    word_alignment_mode: 'whisperx',
  });
  params.set('ocr', profileRunsOcr(analysisProfile) ? 'auto' : 'off');
  if (options.force) {
    params.set('force', 'full');
  }
  const sourcePath = localFileSourcePath(file);
  if (sourcePath) {
    params.set('original_source_path', sourcePath);
  }
  const response = await fetch(`/api/asr/transcribe?${params.toString()}`, {
    method: 'POST',
    headers: {
      'content-type': file.type || 'application/octet-stream',
    },
    signal: options.signal,
    body: file,
  });

  if (!response.ok) {
    throw new Error(await readError(response));
  }
  return response.json();
}

export async function reprocessClipAsr(clipId: string, analysisProfile: AnalysisProfile = 'stt'): Promise<AsrJob> {
  const params = new URLSearchParams({
    content_profile: contentProfileForAnalysisProfile(analysisProfile),
    diarize: 'auto',
    channel_mode: 'auto',
    word_alignment_mode: 'whisperx',
  });
  const response = await fetch(`/api/clips/${encodeURIComponent(clipId)}/modules/asr/reprocess?${params.toString()}`, {
    method: 'POST',
  });
  if (!response.ok) {
    throw new Error(await readError(response));
  }
  return response.json();
}

export async function processClipAsrRange(
  clipId: string,
  range: { start: number; end: number },
  analysisProfile: AnalysisProfile = 'stt',
): Promise<AsrJob> {
  const params = new URLSearchParams({
    start_seconds: String(range.start),
    end_seconds: String(range.end),
    content_profile: contentProfileForAnalysisProfile(analysisProfile),
    diarize: 'auto',
    channel_mode: 'auto',
    word_alignment_mode: 'whisperx',
  });
  const response = await fetch(`/api/clips/${encodeURIComponent(clipId)}/modules/asr/range?${params.toString()}`, {
    method: 'POST',
  });
  if (!response.ok) {
    throw new Error(await readError(response));
  }
  return response.json();
}

export async function deleteClipGeneratedData(clipId: string, kind: ClipGeneratedDataKind): Promise<{
  clip_id: string;
  module: ClipGeneratedDataKind;
  deleted: boolean;
  artifacts_deleted: boolean;
  module_record_deleted: boolean;
  deleted_job_ids: string[];
}> {
  const response = await fetch(`/api/clips/${encodeURIComponent(clipId)}/modules/${encodeURIComponent(kind)}`, {
    method: 'DELETE',
  });
  if (!response.ok) {
    throw new Error(await readError(response));
  }
  return response.json();
}

export function localFileSourcePath(file: File): string | null {
  const desktopPath = (file as File & { path?: string }).path;
  if (desktopPath) return desktopPath;
  const relativePath = (file as File & { webkitRelativePath?: string }).webkitRelativePath;
  return relativePath || null;
}

export async function fetchAsrJob(jobId: string): Promise<AsrJob> {
  const response = await fetch(`/api/jobs/${encodeURIComponent(jobId)}`);
  if (!response.ok) {
    throw new Error(await readError(response));
  }
  return response.json();
}

export async function fetchRecentAsrJobs(limit = 1, options?: { compact?: boolean; query?: string }): Promise<AsrJob[]> {
  const params = new URLSearchParams({ limit: String(limit) });
  if (options?.compact) {
    params.set('compact', 'true');
  }
  if (options?.query?.trim()) {
    params.set('q', options.query.trim());
  }
  const response = await fetch(`/api/jobs?${params.toString()}`);
  if (!response.ok) {
    throw new Error(await readError(response));
  }
  const payload = (await response.json()) as { jobs?: AsrJob[] };
  return payload.jobs ?? [];
}

export async function summarizeAsrJob(jobId: string, options?: { force?: boolean }): Promise<TranscriptSummary> {
  const params = new URLSearchParams();
  if (options?.force) {
    params.set('force', 'true');
  }
  const query = params.toString();
  const response = await fetch(`/api/jobs/${encodeURIComponent(jobId)}/transcript-summary${query ? `?${query}` : ''}`, {
    method: 'POST',
  });
  if (!response.ok) {
    throw new Error(await readError(response));
  }
  return response.json();
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

export async function translateFreeTextToTurkish(text: string, sourceLang = 'auto'): Promise<TranslationResult> {
  const normalizedText = text.trim();
  if (!normalizedText) {
    throw new Error('Çevrilecek metin boş.');
  }
  const effectiveSourceLang = inferSourceLanguage(normalizedText, sourceLang);
  if (effectiveSourceLang === 'tr') {
    return originalTurkishResult(normalizedText);
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
  if (!value || value === 'unknown' || value === 'und' || value === 'auto') {
    return null;
  }
  if (value.startsWith('en')) {
    return 'en';
  }
  if (value.startsWith('tr') || value.startsWith('tur')) {
    return 'tr';
  }
  if (value === 'ar' || value === 'ara' || value === 'arabic' || value.startsWith('arb')) {
    return 'ar';
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
  return !isClearlyTurkishText(segment);
}

export function guessSegmentSourceLanguage(segment: Pick<AsrSegment, 'text' | 'language'>): string {
  const normalized = normalizeSourceLanguage(segment.language);
  if (isClearlyTurkishText(segment)) {
    return 'tr';
  }
  const scriptLanguage = detectScriptLanguage(segment.text);
  if (scriptLanguage && scriptLanguage !== 'tr') {
    return scriptLanguage;
  }
  if (normalized && !isTurkishSourceLanguage(normalized)) {
    return normalized;
  }
  return 'en';
}

function inferSourceLanguage(text: string, declaredLanguage: string | null | undefined): string {
  const normalized = normalizeSourceLanguage(declaredLanguage);
  const scriptLanguage = detectScriptLanguage(text);
  if (scriptLanguage) {
    return scriptLanguage;
  }
  if (isClearlyTurkishText({ text, language: normalized })) {
    return 'tr';
  }
  return normalized ?? 'en';
}

function detectScriptLanguage(text: string): string | null {
  const letters = Array.from(text).filter((char) => /\p{L}/u.test(char));
  if (letters.length === 0) {
    return null;
  }
  const arabicLetters = letters.filter((char) => /[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]/u.test(char)).length;
  return arabicLetters / letters.length >= 0.35 ? 'ar' : null;
}

function isClearlyTurkishText(segment: Pick<AsrSegment, 'text' | 'language'>): boolean {
  const text = segment.text.toLocaleLowerCase('tr-TR');
  const normalized = normalizeSourceLanguage(segment.language);
  const englishHits = countWordHits(text, ENGLISH_TRANSLATION_HINTS);
  const turkishHits = countWordHits(text, TURKISH_TRANSLATION_BLOCKERS);
  if (englishHits > turkishHits) {
    return false;
  }
  if (/[çğıış]/i.test(text) || turkishHits >= 2) {
    return true;
  }
  return normalized === 'tr' && turkishHits >= 1 && englishHits === 0;
}

const ENGLISH_TRANSLATION_HINTS = [
  'the',
  'a',
  'an',
  'and',
  'or',
  'but',
  'one',
  'minute',
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
  'we',
  'you',
  'your',
  'our',
  'this',
  'that',
  'is',
  'are',
  'was',
  'were',
];

const TURKISH_TRANSLATION_BLOCKERS = [
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
  'diye',
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
  'şimdi',
  'sonra',
  'önce',
  'olan',
  'olarak',
  'oldu',
  'olacak',
  'var',
  'yok',
  'merhaba',
  'tamam',
  'lütfen',
  'sesin',
  'yüksek',
  'öldürmeye',
  'gelince',
  'bilirsiniz',
];

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
