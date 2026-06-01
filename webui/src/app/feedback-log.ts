import type { AsrJob, AsrSegment, TranslationResult } from './asr-api';

export type FeedbackKind = 'transcript' | 'translation' | 'ocr';

export interface FeedbackEntry {
  id: string;
  kind: FeedbackKind;
  createdAt: string;
  jobId?: string;
  filename?: string;
  sourcePath?: string | null;
  segmentIndex?: number;
  start?: number;
  end?: number;
  speaker?: string | null;
  text: string;
  translationText?: string;
  translationModel?: string;
  note?: string;
}

const FEEDBACK_STORAGE_KEY = 'mitas.feedback.marked.v1';
const FEEDBACK_CHANGED_EVENT = 'mitas-feedback-changed';

export function feedbackEntryId(kind: FeedbackKind, jobId: string, segmentIndex: number): string {
  return `${kind}:${jobId}:${segmentIndex}`;
}

export function loadFeedbackEntries(): FeedbackEntry[] {
  if (typeof window === 'undefined') return [];
  try {
    const parsed = JSON.parse(window.localStorage.getItem(FEEDBACK_STORAGE_KEY) || '[]');
    return Array.isArray(parsed) ? parsed.filter(isFeedbackEntry) : [];
  } catch {
    return [];
  }
}

export function saveFeedbackEntries(entries: FeedbackEntry[]) {
  if (typeof window === 'undefined') return;
  window.localStorage.setItem(FEEDBACK_STORAGE_KEY, JSON.stringify(entries));
  window.dispatchEvent(new CustomEvent(FEEDBACK_CHANGED_EVENT));
}

export function subscribeFeedbackEntries(listener: () => void): () => void {
  if (typeof window === 'undefined') return () => undefined;
  window.addEventListener(FEEDBACK_CHANGED_EVENT, listener);
  window.addEventListener('storage', listener);
  return () => {
    window.removeEventListener(FEEDBACK_CHANGED_EVENT, listener);
    window.removeEventListener('storage', listener);
  };
}

export function upsertFeedbackEntry(entry: FeedbackEntry) {
  const entries = loadFeedbackEntries();
  const next = [entry, ...entries.filter((item) => item.id !== entry.id)];
  saveFeedbackEntries(next);
}

export function removeFeedbackEntry(id: string) {
  saveFeedbackEntries(loadFeedbackEntries().filter((entry) => entry.id !== id));
}

export function buildSegmentFeedbackEntry({
  kind,
  job,
  segment,
  segmentIndex,
  translation,
}: {
  kind: FeedbackKind;
  job: AsrJob;
  segment: AsrSegment;
  segmentIndex: number;
  translation?: TranslationResult;
}): FeedbackEntry {
  return {
    id: feedbackEntryId(kind, job.job_id, segmentIndex),
    kind,
    createdAt: new Date().toISOString(),
    jobId: job.job_id,
    filename: job.filename,
    sourcePath: job.original_source_path || job.input_path || job.summary?.input_path || null,
    segmentIndex,
    start: segment.start,
    end: segment.end,
    speaker: segment.speaker ?? segment.channel ?? null,
    text: segment.text,
    translationText: translation?.text,
    translationModel: translation?.model,
  };
}

function isFeedbackEntry(value: unknown): value is FeedbackEntry {
  if (!value || typeof value !== 'object') return false;
  const entry = value as Partial<FeedbackEntry>;
  return typeof entry.id === 'string' && typeof entry.kind === 'string' && typeof entry.createdAt === 'string' && typeof entry.text === 'string';
}
