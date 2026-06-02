import { contentProfileForAnalysisProfile, type AnalysisProfile, type AsrJob } from './asr-api';

export interface TedialSession {
  status: 'disconnected' | 'connecting' | 'connected' | 'expired' | 'error';
  remember: boolean;
  cookie_names: string[];
  error?: string | null;
  auto_login_enabled?: boolean;
  auto_login_configured?: boolean;
  auto_login_attempted?: boolean;
  auto_login_error?: string | null;
}

export interface TedialSearchResult {
  title?: string | null;
  trt_id?: string | null;
  repository_id?: string | null;
  asset_id?: string | null;
  sequence_id?: string | null;
  asset_type?: string | null;
  tc_in?: number | null;
  tc_out?: number | null;
  duration_seconds?: number | null;
  keyframe_url?: string | null;
}

export type TedialAudioTrack = 0 | 1;
export type TedialAsrChannelMode = 'auto' | 'split' | 'mono';
export const DEFAULT_TEDIAL_CHANNEL_MODE: TedialAsrChannelMode = 'auto';

export interface TedialImportOptions {
  audioTrack?: TedialAudioTrack;
  channelMode?: TedialAsrChannelMode;
  analysisProfile?: AnalysisProfile;
  signal?: AbortSignal;
}

export interface TedialMediaImportResult {
  item: TedialSearchResult;
  filename: string;
  mediaType: 'video/mp4' | 'application/dash+xml';
  streamUrl: string;
  audioTrack: TedialAudioTrack;
  channelMode: TedialAsrChannelMode;
}

export interface TedialImportResult extends TedialMediaImportResult {
  job: AsrJob;
}

const TEDIAL_API = '/tedial-api';

export async function fetchTedialSession(useHealth = false): Promise<TedialSession> {
  const response = await fetch(`${TEDIAL_API}/session${useHealth ? '/health' : ''}`);
  if (!response.ok) {
    throw new Error(await readTedialError(response));
  }
  return response.json();
}

export async function startTedialSession(remember: boolean): Promise<TedialSession & { login_url?: string }> {
  const response = await fetch(`${TEDIAL_API}/session/start`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ remember }),
  });
  if (!response.ok) {
    throw new Error(await readTedialError(response));
  }
  const payload = await response.json();
  if (payload.login_url?.startsWith('/')) {
    payload.login_url = `${window.location.origin}${payload.login_url}`;
  }
  return payload;
}

export async function autoLoginTedialSession(): Promise<TedialSession> {
  const response = await fetch(`${TEDIAL_API}/session/auto-login`, { method: 'POST' });
  if (!response.ok) {
    throw new Error(await readTedialError(response));
  }
  return response.json();
}

export async function forgetTedialSession(): Promise<TedialSession> {
  const response = await fetch(`${TEDIAL_API}/session/forget`, { method: 'POST' });
  if (!response.ok) {
    throw new Error(await readTedialError(response));
  }
  return response.json();
}

export async function searchTedial(searchField: string): Promise<TedialSearchResult[]> {
  const query = searchField.trim();
  const items = await searchTedialRaw(query, looksLikeTrtId(query) ? 'trt_id' : 'default');
  const fallbackQuery = compactTrtId(query);
  if (items.length === 0 && fallbackQuery && fallbackQuery !== query) {
    return searchTedialRaw(fallbackQuery, 'default');
  }
  return items;
}

async function searchTedialRaw(searchField: string, searchMode: 'default' | 'trt_id'): Promise<TedialSearchResult[]> {
  const response = await fetch(`${TEDIAL_API}/search`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ searchField, searchMode }),
  });
  if (!response.ok) {
    throw new Error(await readTedialError(response));
  }
  const payload = await response.json();
  return payload.items ?? [];
}

function looksLikeTrtId(value: string): boolean {
  return /^\d{2,4}-\d{3,}/.test(value.trim());
}

function compactTrtId(value: string): string | null {
  const trimmed = value.trim();
  if (!looksLikeTrtId(trimmed)) {
    return null;
  }
  return trimmed.replace(/-/g, '');
}

export function openTedialMediaInMitas(item: TedialSearchResult, options: TedialImportOptions = {}): TedialMediaImportResult {
  if (!item.repository_id || !item.asset_id) {
    throw new Error('Tedial asset bilgisi eksik.');
  }
  const audioTrack = normalizeTedialAudioTrack(options.audioTrack);
  const channelMode = options.channelMode ?? DEFAULT_TEDIAL_CHANNEL_MODE;
  const streamUrl = tedialManifestUrl(item, audioTrack);
  const filename = buildTedialFilename(item, 'application/dash+xml', streamUrl);
  return {
    item: { ...item, duration_seconds: tedialDurationSeconds(item) },
    filename,
    mediaType: 'application/dash+xml',
    streamUrl,
    audioTrack,
    channelMode,
  };
}

export async function startTedialAsrJob(item: TedialSearchResult, options: TedialImportOptions = {}): Promise<TedialImportResult> {
  if (!item.repository_id || !item.asset_id) {
    throw new Error('Tedial asset bilgisi eksik.');
  }
  const audioTrack = normalizeTedialAudioTrack(options.audioTrack);
  const channelMode = options.channelMode ?? DEFAULT_TEDIAL_CHANNEL_MODE;
  const analysisProfile = options.analysisProfile ?? 'stt';
  const streamUrl = tedialStreamUrl(item, audioTrack);
  const filename = buildTedialFilename(item, 'video/mp4', streamUrl);
  const params = new URLSearchParams({
    repository_id: item.repository_id,
    title: item.title || item.asset_id,
    content_profile: contentProfileForAnalysisProfile(analysisProfile),
    diarize: 'auto',
    channel_mode: channelMode,
    word_alignment_mode: 'whisperx',
    audio_track: String(audioTrack),
  });
  const response = await fetch(`${TEDIAL_API}/assets/${encodeURIComponent(item.asset_id)}/asr?${params.toString()}`, {
    method: 'POST',
    signal: options.signal,
  });
  if (!response.ok) {
    throw new Error(await readTedialError(response));
  }
  const job = await response.json() as AsrJob;
  rememberTedialAsrJob(job.job_id);
  const normalizedItem = { ...item, duration_seconds: tedialDurationSeconds(item) };
  return {
    item: normalizedItem,
    filename: job.filename || filename,
    mediaType: 'video/mp4',
    streamUrl: `/api/jobs/${encodeURIComponent(job.job_id)}/media`,
    audioTrack,
    channelMode,
    job,
  };
}

export async function startTedialAsrRangeJob(
  item: TedialSearchResult,
  range: { start: number; end: number },
  options: TedialImportOptions = {},
): Promise<TedialImportResult> {
  if (!item.repository_id || !item.asset_id) {
    throw new Error('Tedial asset bilgisi eksik.');
  }
  if (range.end <= range.start) {
    throw new Error('Geçerli bir in/out aralığı seç.');
  }
  const audioTrack = normalizeTedialAudioTrack(options.audioTrack);
  const channelMode = options.channelMode ?? DEFAULT_TEDIAL_CHANNEL_MODE;
  const analysisProfile = options.analysisProfile ?? 'stt';
  const params = new URLSearchParams({
    repository_id: item.repository_id,
    title: item.title || item.asset_id,
    content_profile: contentProfileForAnalysisProfile(analysisProfile),
    diarize: 'auto',
    channel_mode: channelMode,
    word_alignment_mode: 'whisperx',
    audio_track: String(audioTrack),
    start_seconds: String(range.start),
    end_seconds: String(range.end),
  });
  const response = await fetch(`${TEDIAL_API}/assets/${encodeURIComponent(item.asset_id)}/asr?${params.toString()}`, {
    method: 'POST',
    signal: options.signal,
  });
  if (!response.ok) {
    throw new Error(await readTedialError(response));
  }
  const job = await response.json() as AsrJob;
  rememberTedialAsrJob(job.job_id);
  return {
    item: { ...item, duration_seconds: Math.max(0, range.end - range.start) },
    filename: job.filename || buildTedialFilename(item, 'video/mp4', tedialStreamUrl(item, audioTrack)),
    mediaType: 'video/mp4',
    streamUrl: `/api/jobs/${encodeURIComponent(job.job_id)}/media`,
    audioTrack,
    channelMode,
    job,
  };
}

export async function startTedialPipelineJob(
  item: TedialSearchResult,
  options: TedialImportOptions & { startSeconds?: number; endSeconds?: number } = {},
): Promise<AsrJob> {
  if (!item.repository_id || !item.asset_id) {
    throw new Error('Tedial asset bilgisi eksik.');
  }
  const audioTrack = normalizeTedialAudioTrack(options.audioTrack);
  const analysisProfile = options.analysisProfile ?? 'film_dizi';
  const params = new URLSearchParams({
    repository_id: item.repository_id,
    title: item.title || item.asset_id,
    profile: analysisProfile,
    audio_track: String(audioTrack),
  });
  if (Number.isFinite(options.startSeconds)) {
    params.set('start_seconds', String(options.startSeconds));
    if (Number.isFinite(options.endSeconds)) {
      params.set('end_seconds', String(options.endSeconds));
    }
  }
  const response = await fetch(`${TEDIAL_API}/assets/${encodeURIComponent(item.asset_id)}/pipeline?${params.toString()}`, {
    method: 'POST',
    signal: options.signal,
  });
  if (!response.ok) {
    throw new Error(await readTedialError(response));
  }
  const job = await response.json() as AsrJob;
  rememberTedialAsrJob(job.job_id);
  return job;
}

const TEDIAL_JOB_IDS_KEY = 'mitas.tedial.asrJobIds';

export function getRememberedTedialJobIds(): string[] {
  if (typeof window === 'undefined') {
    return [];
  }
  try {
    const parsed = JSON.parse(window.localStorage.getItem(TEDIAL_JOB_IDS_KEY) || '[]');
    return Array.isArray(parsed) ? parsed.filter((item): item is string => typeof item === 'string' && item.length > 0) : [];
  } catch {
    return [];
  }
}

export function rememberTedialAsrJob(jobId: string | null | undefined) {
  const id = String(jobId || '').trim();
  if (!id || typeof window === 'undefined') {
    return;
  }
  const next = [id, ...getRememberedTedialJobIds().filter((item) => item !== id)].slice(0, 100);
  window.localStorage.setItem(TEDIAL_JOB_IDS_KEY, JSON.stringify(next));
}

export function tedialDurationSeconds(item: TedialSearchResult | null | undefined): number | null {
  if (!item) {
    return null;
  }
  if (Number.isFinite(item.duration_seconds ?? NaN)) {
    return item.duration_seconds ?? null;
  }
  if (Number.isFinite(item.tc_in ?? NaN) && Number.isFinite(item.tc_out ?? NaN)) {
    return Math.max(0, ((item.tc_out ?? 0) - (item.tc_in ?? 0)) / 1000);
  }
  return null;
}

export function tedialKeyframeProxyUrl(item: TedialSearchResult): string | null {
  return item.keyframe_url ? `${TEDIAL_API}/keyframe?url=${encodeURIComponent(item.keyframe_url)}` : null;
}

export function tedialStreamUrl(item: TedialSearchResult, audioTrack: TedialAudioTrack = 0): string {
  if (!item.repository_id || !item.asset_id) {
    return '';
  }
  const params = new URLSearchParams({ repository_id: item.repository_id, audio_track: String(audioTrack) });
  return `${TEDIAL_API}/assets/${encodeURIComponent(item.asset_id)}/stream?${params.toString()}`;
}

export function tedialManifestUrl(item: TedialSearchResult, audioTrack: TedialAudioTrack = 0): string {
  if (!item.repository_id || !item.asset_id) {
    return '';
  }
  const params = new URLSearchParams({ repository_id: item.repository_id, audio_track: String(audioTrack) });
  return `${TEDIAL_API}/assets/${encodeURIComponent(item.asset_id)}/manifest?${params.toString()}`;
}

function normalizeTedialAudioTrack(value: TedialAudioTrack | undefined): TedialAudioTrack {
  return value === 1 ? 1 : 0;
}

function buildTedialFilename(item: TedialSearchResult, contentType: string | null, mediaUrl: string): string {
  const stem = sanitizeName(item.title || item.asset_id || 'tedial_asset');
  const suffix = suffixFromContentType(contentType) || suffixFromPath(mediaUrl) || '.mp4';
  return `${stem}${suffix}`;
}

function sanitizeName(value: string): string {
  return value.trim().replace(/[^A-Za-z0-9._ -]+/g, '_').replace(/^[ .]+|[ .]+$/g, '') || 'tedial_asset';
}

function suffixFromContentType(contentType: string | null): string | null {
  const type = (contentType || '').split(';', 1)[0].trim().toLowerCase();
  if (type === 'application/dash+xml') return '.mpd';
  if (type === 'video/mp4') return '.mp4';
  if (type === 'audio/mpeg') return '.mp3';
  if (type === 'audio/wav' || type === 'audio/x-wav') return '.wav';
  return null;
}

function suffixFromPath(value: string): string | null {
  try {
    const pathname = new URL(value, window.location.origin).pathname;
    const match = pathname.match(/\.[A-Za-z0-9]{2,5}$/);
    return match?.[0] ?? null;
  } catch {
    return null;
  }
}

async function readTedialError(response: Response): Promise<string> {
  try {
    const payload = await response.json();
    return payload.detail || payload.error || response.statusText;
  } catch {
    return response.statusText;
  }
}
