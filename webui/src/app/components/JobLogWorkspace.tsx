import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import {
  AlertCircle,
  AlertTriangle,
  CheckCircle2,
  Clock3,
  FileText,
  FolderOpen,
  Globe2,
  ListChecks,
  Loader2,
  PlayCircle,
  RefreshCw,
  Search,
  Sparkles,
  X,
  XCircle,
} from 'lucide-react';
import {
  fetchAsrJob,
  fetchRecentAsrJobs,
  formatClock,
  isAsrJobFinished,
  summarizeAsrJob,
  type AsrJob,
  type AsrJobStatus,
} from '../asr-api';
import { getRememberedTedialJobIds } from '../tedial-api';
import { Badge, Button, ScrollArea } from './ui';
import {
  loadFeedbackEntries,
  removeFeedbackEntry,
  subscribeFeedbackEntries,
  type FeedbackEntry,
} from '../feedback-log';

interface JobLogWorkspaceProps {
  currentJobId?: string | null;
  onOpenJob: (job: AsrJob) => void;
}

type BadgeVariant = 'default' | 'outline' | 'secondary' | 'success' | 'warning' | 'danger';
type LogFilter = 'all' | 'today' | 'tedial' | 'uploads' | 'failed' | 'done' | 'marked';

export function JobLogWorkspace({ currentJobId, onOpenJob }: JobLogWorkspaceProps) {
  const [jobs, setJobs] = useState<AsrJob[]>([]);
  const [selectedJobId, setSelectedJobId] = useState<string | null>(currentJobId ?? null);
  const [selectedJob, setSelectedJob] = useState<AsrJob | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isDetailLoading, setIsDetailLoading] = useState(false);
  const [isSummaryLoading, setIsSummaryLoading] = useState(false);
  const [logSearch, setLogSearch] = useState('');
  const [filterMode, setFilterMode] = useState<LogFilter>('all');
  const [transcriptSearch, setTranscriptSearch] = useState('');
  const [activeTranscriptMatchIndex, setActiveTranscriptMatchIndex] = useState(0);
  const [feedbackEntries, setFeedbackEntries] = useState<FeedbackEntry[]>(() => loadFeedbackEntries());
  const [summaryError, setSummaryError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const transcriptBoxRef = useRef<HTMLDivElement | null>(null);

  const loadJobs = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const nextJobs = await fetchRecentAsrJobs(100, { compact: true, query: logSearch });
      setJobs(nextJobs);
      setSelectedJobId((current) => (
        nextJobs.some((job) => job.job_id === current) ? current : nextJobs[0]?.job_id ?? null
      ));
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Log geçmişi alınamadı.');
    } finally {
      setIsLoading(false);
    }
  }, [logSearch]);

  const loadSelectedJob = useCallback(async (jobId: string) => {
    setIsDetailLoading(true);
    setError(null);
    try {
      const job = await fetchAsrJob(jobId);
      setSelectedJob(job);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'İşlem detayı alınamadı.');
    } finally {
      setIsDetailLoading(false);
    }
  }, []);

  const openJobInAnalysis = useCallback(async (job: AsrJob) => {
    setError(null);
    try {
      const fullJob = selectedJob?.job_id === job.job_id && selectedJob.segments.length > 0
        ? selectedJob
        : await fetchAsrJob(job.job_id);
      setSelectedJob(fullJob);
      onOpenJob(fullJob);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'İşlem Analiz ekranında açılamadı.');
    }
  }, [onOpenJob, selectedJob]);

  useEffect(() => {
    void loadJobs();
    const interval = window.setInterval(() => {
      void loadJobs();
    }, 10000);
    return () => window.clearInterval(interval);
  }, [loadJobs]);

  useEffect(() => subscribeFeedbackEntries(() => setFeedbackEntries(loadFeedbackEntries())), []);

  useEffect(() => {
    if (!currentJobId) return;
    setSelectedJobId(currentJobId);
  }, [currentJobId]);

  useEffect(() => {
    if (!selectedJobId) {
      setSelectedJob(null);
      return;
    }
    setTranscriptSearch('');
    setActiveTranscriptMatchIndex(0);
    setSummaryError(null);
    void loadSelectedJob(selectedJobId);
  }, [loadSelectedJob, selectedJobId]);

  useEffect(() => {
    if (!selectedJob || isAsrJobFinished(selectedJob)) {
      return undefined;
    }
    const jobId = selectedJob.job_id;
    const interval = window.setInterval(() => {
      void loadSelectedJob(jobId);
    }, 2500);
    return () => window.clearInterval(interval);
  }, [loadSelectedJob, selectedJob?.job_id, selectedJob?.status]);

  const totals = useMemo(() => {
    const done = jobs.filter((job) => job.status === 'done').length;
    const partial = jobs.filter((job) => job.status === 'partial').length;
    const failed = jobs.filter((job) => job.status === 'failed').length;
    const running = jobs.filter((job) => job.status === 'queued' || job.status === 'running').length;
    const mediaSeconds = jobs.reduce((sum, job) => sum + (job.summary?.audio_duration ?? 0), 0);
    const processSeconds = jobs.reduce((sum, job) => {
      return sum + (job.summary?.timing?.total_seconds ?? job.module_run?.runtime_sec ?? job.elapsed_seconds ?? 0);
    }, 0);
    return { done, partial, failed, running, mediaSeconds, processSeconds };
  }, [jobs]);

  const selectedStatus = selectedJob?.status ?? jobs.find((job) => job.job_id === selectedJobId)?.status;
  const transcript = selectedJob?.transcript?.trim() ?? '';
  const logs = selectedJob?.logs ?? [];
  const feedbackJobIds = useMemo(() => new Set(feedbackEntries.map((entry) => entry.jobId).filter(Boolean)), [feedbackEntries]);
  const feedbackCountByJobId = useMemo(() => {
    const counts = new Map<string, number>();
    feedbackEntries.forEach((entry) => {
      if (entry.jobId) {
        counts.set(entry.jobId, (counts.get(entry.jobId) ?? 0) + 1);
      }
    });
    return counts;
  }, [feedbackEntries]);
  const filteredJobs = useMemo(() => {
    const tedialIds = new Set(getRememberedTedialJobIds());
    return jobs.filter((job) => {
      if (filterMode === 'today') return isToday(job.created_at);
      if (filterMode === 'tedial') return tedialIds.has(job.job_id);
      if (filterMode === 'uploads') return !tedialIds.has(job.job_id);
      if (filterMode === 'failed') return job.status === 'failed';
      if (filterMode === 'done') return job.status === 'done';
      if (filterMode === 'marked') return feedbackJobIds.has(job.job_id);
      return true;
    });
  }, [feedbackJobIds, filterMode, jobs]);
  const selectedFeedbackEntries = useMemo(() => {
    if (!selectedJob?.job_id) return [];
    return feedbackEntries.filter((entry) => entry.jobId === selectedJob.job_id);
  }, [feedbackEntries, selectedJob?.job_id]);
  const transcriptMatchCount = useMemo(() => countTextMatches(transcript, transcriptSearch), [transcript, transcriptSearch]);
  const transcriptSummary = selectedJob?.transcript_summary;
  const uncoveredRanges = selectedJob?.summary?.safety?.diagnostics?.uncovered_vad_ranges ?? [];
  const dropReasons = Object.entries(selectedJob?.archive?.quality?.drop_reasons ?? {});
  const errorFlags = selectedJob?.summary?.quality_report?.error_flags ?? [];
  const languageIntel = selectedJob?.summary?.language_intelligence;
  const artifactRows = selectedJob ? buildArtifactRows(selectedJob) : [];
  const goToTranscriptMatch = useCallback((nextIndex: number) => {
    if (transcriptMatchCount <= 0) {
      return;
    }
    setActiveTranscriptMatchIndex(((nextIndex % transcriptMatchCount) + transcriptMatchCount) % transcriptMatchCount);
  }, [transcriptMatchCount]);

  useEffect(() => {
    setActiveTranscriptMatchIndex(0);
  }, [transcriptSearch, selectedJob?.job_id]);

  useEffect(() => {
    const marks = transcriptBoxRef.current?.querySelectorAll('mark[data-transcript-match]');
    const target = marks?.[activeTranscriptMatchIndex];
    target?.scrollIntoView({ block: 'center', behavior: 'smooth' });
  }, [activeTranscriptMatchIndex, transcriptMatchCount]);

  useEffect(() => {
    if (!selectedJob?.job_id || !transcript || transcriptSummary?.summary) {
      return undefined;
    }
    let cancelled = false;
    setIsSummaryLoading(true);
    setSummaryError(null);
    summarizeAsrJob(selectedJob.job_id)
      .then((summary) => {
        if (cancelled) return;
        setSelectedJob((current) => current?.job_id === selectedJob.job_id ? { ...current, transcript_summary: summary } : current);
      })
      .catch((summaryLoadError) => {
        if (cancelled) return;
        setSummaryError(summaryLoadError instanceof Error ? summaryLoadError.message : 'Özet üretilemedi.');
      })
      .finally(() => {
        if (!cancelled) {
          setIsSummaryLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [selectedJob?.job_id, transcript, transcriptSummary?.summary]);

  const handleRefreshSummary = useCallback(async () => {
    if (!selectedJob?.job_id) {
      return;
    }
    setIsSummaryLoading(true);
    setSummaryError(null);
    try {
      const summary = await summarizeAsrJob(selectedJob.job_id, { force: true });
      setSelectedJob((current) => current?.job_id === selectedJob.job_id ? { ...current, transcript_summary: summary } : current);
    } catch (summaryLoadError) {
      setSummaryError(summaryLoadError instanceof Error ? summaryLoadError.message : 'Özet üretilemedi.');
    } finally {
      setIsSummaryLoading(false);
    }
  }, [selectedJob?.job_id]);

  return (
    <div className="flex h-full w-full overflow-hidden bg-app-shell text-foreground-default">
      <aside className="flex h-full w-[390px] shrink-0 flex-col border-r border-border-subtle bg-surface/25">
        <div className="flex h-14 items-center justify-between border-b border-border-subtle px-4">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <ListChecks className="h-4 w-4 text-info" />
              <h1 className="truncate text-sm font-bold uppercase tracking-wider text-foreground-strong">Log</h1>
            </div>
            <p className="mt-0.5 text-[10px] uppercase tracking-wider text-foreground-muted">
              {logSearch.trim() || filterMode !== 'all' ? `${filteredJobs.length}/${jobs.length} kayıt` : `Son ${jobs.length} kayıt`}
            </p>
          </div>
          <Button
            variant="outline"
            size="icon-xs"
            onClick={() => void loadJobs()}
            title="Yenile"
            disabled={isLoading}
          >
            <RefreshCw className={`h-3.5 w-3.5 ${isLoading ? 'animate-spin' : ''}`} />
          </Button>
        </div>

        <div className="grid grid-cols-2 gap-2 border-b border-border-subtle p-3">
          <Stat label="Tamam" value={String(totals.done)} tone="success" />
          <Stat label="Kısmi" value={String(totals.partial)} tone="warning" />
          <Stat label="Hata" value={String(totals.failed)} tone="danger" />
          <Stat label="Aktif" value={String(totals.running)} tone="info" />
          <Stat label="Medya" value={formatClock(totals.mediaSeconds)} />
          <Stat label="İşlem" value={formatClock(totals.processSeconds)} />
        </div>

        <div className="border-b border-border-subtle p-3">
          <div className="relative">
            <Search className="absolute left-2 top-1.5 h-3.5 w-3.5 text-foreground-muted" />
            <input
              type="text"
              value={logSearch}
              onChange={(event) => setLogSearch(event.target.value)}
              placeholder="Log/transcript içinde ara..."
              className="h-7 w-full rounded-sm border border-border-mitas bg-app-shell py-1 pl-7 pr-7 text-xs text-foreground-default focus:border-info-strong focus:outline-none"
            />
            {logSearch ? (
              <button
                type="button"
                onClick={() => setLogSearch('')}
                className="absolute right-1 top-1 inline-flex h-5 w-5 items-center justify-center rounded-sm text-foreground-muted hover:bg-surface-elevated hover:text-foreground-strong"
                title="Aramayı temizle"
              >
                <X className="h-3 w-3" />
              </button>
            ) : null}
          </div>
          <div className="mt-2 flex flex-wrap gap-1">
            {([
              ['all', 'Tümü'],
              ['today', 'Bugün'],
              ['tedial', 'Tedial'],
              ['uploads', 'Yüklenenler'],
              ['failed', 'Hatalı'],
              ['done', 'ASR tamamlandı'],
              ['marked', `Benim işaretlediklerim${feedbackEntries.length ? ` (${feedbackEntries.length})` : ''}`],
            ] as const).map(([value, label]) => (
              <Button
                key={value}
                size="xs"
                variant={filterMode === value ? 'secondary' : 'outline'}
                className="h-6 text-[10px]"
                onClick={() => setFilterMode(value)}
              >
                {label}
              </Button>
            ))}
          </div>
        </div>

        {error && (
          <div className="border-b border-danger/30 bg-danger-subtle/30 px-3 py-2 text-[11px] text-danger">
            {error}
          </div>
        )}

        <ScrollArea className="min-h-0 flex-1">
          <div className="flex flex-col gap-1.5 p-3">
            {jobs.length === 0 && !isLoading ? (
              <div className="rounded-sm border border-border-subtle bg-app-shell/50 p-3 text-[11px] text-foreground-muted">
                Kayıt bulunamadı.
              </div>
            ) : filteredJobs.length === 0 ? (
              <div className="rounded-sm border border-border-subtle bg-app-shell/50 p-3 text-[11px] text-foreground-muted">
                Aramaya uygun kayıt bulunamadı.
              </div>
            ) : (
              filteredJobs.map((job) => (
                <button
                  key={job.job_id}
                  type="button"
                  onClick={() => setSelectedJobId(job.job_id)}
                  onDoubleClick={() => void openJobInAnalysis(job)}
                  className={`w-full rounded-sm border p-3 text-left transition-colors ${
                    selectedJobId === job.job_id
                      ? 'border-info-border bg-info-subtle/25'
                      : 'border-border-subtle bg-app-shell/55 hover:border-border-mitas hover:bg-surface/60'
                  }`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <div className="truncate text-xs font-semibold text-foreground-strong">{job.filename}</div>
                      <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-[10px] text-foreground-muted">
                        <span>{formatDate(job.created_at)}</span>
                        <span>{formatClock(job.summary?.audio_duration)}</span>
                        <span>{job.summary?.clean_segments ?? 0} seg</span>
                      </div>
                    </div>
                    <div className="flex shrink-0 flex-col items-end gap-1">
                      <StatusBadge status={job.status} />
                      {(feedbackCountByJobId.get(job.job_id) ?? 0) > 0 ? (
                        <Badge variant="warning" className="gap-1">
                          <AlertTriangle className="h-3 w-3" />
                          {feedbackCountByJobId.get(job.job_id)}
                        </Badge>
                      ) : null}
                    </div>
                  </div>
                  <div className="mt-2 flex items-center gap-2 text-[10px] text-foreground-muted">
                    <span className="truncate">{job.summary?.model_name || 'model yok'}</span>
                    <span className="text-border-mitas">/</span>
                    <span className="truncate">{job.summary?.profile_used || job.profile}</span>
                  </div>
                  {job.search_match?.snippet ? (
                    <div className="mt-2 rounded-sm border border-info-border/40 bg-info-subtle/15 px-2 py-1 text-[10px] leading-relaxed text-foreground-muted">
                      <span className="mr-1 font-mono uppercase text-info">{job.search_match.scope}</span>
                      {job.search_match.count ? <span className="mr-1 font-mono text-info">({job.search_match.count})</span> : null}
                      <span>{job.search_match.snippet}</span>
                    </div>
                  ) : null}
                </button>
              ))
            )}
          </div>
        </ScrollArea>
      </aside>

      <main className="flex min-w-0 flex-1 flex-col">
        <div className="flex h-14 items-center justify-between border-b border-border-subtle bg-surface/15 px-5">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              {selectedStatus ? <StatusIcon status={selectedStatus} /> : <FileText className="h-4 w-4 text-foreground-muted" />}
              <h2 className="truncate text-sm font-bold text-foreground-strong">
                {selectedJob?.filename || 'İşlem seç'}
              </h2>
              {selectedStatus && <StatusBadge status={selectedStatus} />}
            </div>
            <p className="mt-0.5 truncate text-[10px] font-mono text-foreground-muted">
              {selectedJob?.job_id || 'ASR geçmişi'}
            </p>
          </div>
          <div className="flex items-center gap-2">
            {isDetailLoading && <Loader2 className="h-4 w-4 animate-spin text-info" />}
            <Button
              variant="outline"
              size="sm"
              disabled={!selectedJob}
              onClick={() => selectedJob && void openJobInAnalysis(selectedJob)}
              title="Bu işi Analiz ekranında aç"
            >
              <PlayCircle className="mr-1.5 h-3.5 w-3.5" />
              Analizde aç
            </Button>
          </div>
        </div>

        {!selectedJob ? (
          <div className="flex flex-1 items-center justify-center text-xs text-foreground-muted">
            {isLoading ? 'Loglar yükleniyor.' : 'Detay için bir kayıt seç.'}
          </div>
        ) : (
          <ScrollArea className="min-h-0 flex-1">
            <div className="grid gap-4 p-5 xl:grid-cols-[minmax(0,1fr)_360px]">
              <section className="min-w-0 space-y-4">
                <Panel title="Benim İşaretlediklerim" icon={<AlertTriangle className="h-4 w-4 text-warning" />}>
                  {selectedFeedbackEntries.length > 0 ? (
                    <div className="max-h-[260px] overflow-auto rounded-sm border border-warning/25 bg-warning-subtle/10">
                      {selectedFeedbackEntries.map((entry) => (
                        <FeedbackEntryRow key={entry.id} entry={entry} onRemove={() => removeFeedbackEntry(entry.id)} />
                      ))}
                    </div>
                  ) : (
                    <EmptyLine text={feedbackEntries.length > 0 ? 'Bu iş için işaret yok.' : 'Henüz işaretlenmiş hata yok.'} />
                  )}
                </Panel>

                <Panel title="İçerik Özeti" icon={<Sparkles className="h-4 w-4 text-info" />}>
                  <div className="mb-2 flex items-center justify-between gap-2">
                    <div className="min-w-0 text-[10px] uppercase tracking-wider text-foreground-muted">
                      {transcriptSummary ? `${transcriptSummary.provider} / ${transcriptSummary.model}` : 'transcript özeti'}
                    </div>
                    <Button
                      variant="outline"
                      size="xs"
                      onClick={() => void handleRefreshSummary()}
                      disabled={isSummaryLoading || !transcript}
                      title="Özeti yeniden üret"
                    >
                      {isSummaryLoading ? <Loader2 className="mr-1 h-3 w-3 animate-spin" /> : <RefreshCw className="mr-1 h-3 w-3" />}
                      Özet
                    </Button>
                  </div>
                  {isSummaryLoading && !transcriptSummary ? (
                    <EmptyLine text="Transcript modele hazırlanıyor, özet üretiliyor." />
                  ) : summaryError ? (
                    <div className="rounded-sm border border-danger/30 bg-danger-subtle/30 p-3 text-[11px] text-danger">
                      {summaryError}
                    </div>
                  ) : transcriptSummary?.summary ? (
                    <div className="whitespace-pre-wrap rounded-sm border border-border-subtle bg-app-shell/60 p-3 text-[12px] leading-relaxed text-foreground-default">
                      {transcriptSummary.summary}
                    </div>
                  ) : (
                    <EmptyLine text="Özet için transcript bekleniyor." />
                  )}
                </Panel>

                <Panel title="Transcript" icon={<FileText className="h-4 w-4 text-info" />}>
                  {transcript ? (
                    <>
                      <div className="relative mb-2">
                        <Search className="absolute left-2 top-1.5 h-3.5 w-3.5 text-foreground-muted" />
                        <input
                          type="text"
                          value={transcriptSearch}
                          onChange={(event) => setTranscriptSearch(event.target.value)}
                          onKeyDown={(event) => {
                            if (event.key === 'Enter') {
                              event.preventDefault();
                              goToTranscriptMatch(activeTranscriptMatchIndex + 1);
                            }
                            if (event.key === 'Escape') {
                              setTranscriptSearch('');
                            }
                          }}
                          placeholder="Bu transcriptte ara..."
                          className="h-7 w-full rounded-sm border border-border-mitas bg-app-shell py-1 pl-7 pr-[94px] text-xs text-foreground-default focus:border-info-strong focus:outline-none"
                        />
                        {transcriptSearch ? (
                          <div className="absolute right-1 top-1 flex h-5 items-center gap-1">
                            <span className={`font-mono text-[10px] ${transcriptMatchCount > 0 ? 'text-info' : 'text-danger'}`}>
                              {transcriptMatchCount > 0 ? `${activeTranscriptMatchIndex + 1}/${transcriptMatchCount}` : '0'}
                            </span>
                            <button
                              type="button"
                              onClick={() => goToTranscriptMatch(activeTranscriptMatchIndex)}
                              disabled={transcriptMatchCount === 0}
                              className="inline-flex h-5 items-center justify-center rounded-sm px-1 text-[10px] font-semibold text-info hover:bg-surface-elevated disabled:pointer-events-none disabled:opacity-30"
                              title="Aktif eşleşmeye git"
                            >
                              Git
                            </button>
                            <button
                              type="button"
                              onClick={() => {
                                setTranscriptSearch('');
                                setActiveTranscriptMatchIndex(0);
                              }}
                              className="inline-flex h-5 w-5 items-center justify-center rounded-sm text-foreground-muted hover:bg-surface-elevated hover:text-foreground-strong"
                              title="Aramayı temizle"
                            >
                              <X className="h-3 w-3" />
                            </button>
                          </div>
                        ) : null}
                      </div>
                      <div ref={transcriptBoxRef} className="max-h-[360px] overflow-auto whitespace-pre-wrap rounded-sm border border-border-subtle bg-app-shell/60 p-3 text-[12px] leading-relaxed text-foreground-default">
                        {highlightLogText(transcript, transcriptSearch, activeTranscriptMatchIndex)}
                      </div>
                    </>
                  ) : (
                    <EmptyLine text="Transcript kaydı yok." />
                  )}
                </Panel>

                <Panel title="Segmentler" icon={<Clock3 className="h-4 w-4 text-info" />}>
                  {selectedJob.segments.length > 0 ? (
                    <div className="max-h-[320px] overflow-auto rounded-sm border border-border-subtle bg-app-shell/60">
                      {selectedJob.segments.slice(0, 80).map((segment, index) => (
                        <div key={`${segment.start}-${segment.end}-${index}`} className="grid grid-cols-[90px_minmax(0,1fr)] gap-3 border-b border-border-subtle/70 px-3 py-2 last:border-b-0">
                          <span className="font-mono text-[10px] text-foreground-muted">
                            {formatClock(segment.start)}-{formatClock(segment.end)}
                          </span>
                          <span className="text-[12px] text-foreground-default">{segment.text}</span>
                        </div>
                      ))}
                      {selectedJob.segments.length > 80 && (
                        <div className="px-3 py-2 text-[11px] text-foreground-muted">
                          +{selectedJob.segments.length - 80} segment daha var.
                        </div>
                      )}
                    </div>
                  ) : (
                    <EmptyLine text="Segment yok." />
                  )}
                </Panel>

                <Panel title="İşlem Adımları" icon={<ListChecks className="h-4 w-4 text-info" />}>
                  {logs.length > 0 ? (
                    <div className="max-h-[300px] overflow-auto rounded-sm border border-border-subtle bg-app-shell/60">
                      {logs.map((entry, index) => (
                        <div key={`${entry.ts}-${entry.stage}-${index}`} className="grid grid-cols-[110px_90px_minmax(0,1fr)] gap-3 border-b border-border-subtle/70 px-3 py-2 last:border-b-0">
                          <span className="font-mono text-[10px] text-foreground-muted">{formatDate(entry.ts, true)}</span>
                          <span className="truncate font-mono text-[10px] uppercase text-info">{entry.stage || '-'}</span>
                          <span className="text-[11px] text-foreground-default">
                            {typeof entry.progress_percent === 'number' ? `${entry.progress_percent}% · ` : ''}
                            {entry.message}
                          </span>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <EmptyLine text="İşlem adımı yok." />
                  )}
                </Panel>
              </section>

              <aside className="min-w-0 space-y-4">
                <Panel title="İşlem Özeti" icon={<CheckCircle2 className="h-4 w-4 text-success" />}>
                  <div className="mb-3 grid grid-cols-2 gap-2">
                    <Metric label="Model" value={selectedJob.summary?.model_name || selectedJob.module_run?.model_name || '-'} />
                    <Metric label="Profil" value={selectedJob.summary?.profile_used || selectedJob.profile || '-'} />
                    <Metric label="Medya" value={formatClock(selectedJob.summary?.audio_duration)} />
                    <Metric label="İşlem" value={formatClock(selectedJob.summary?.timing?.total_seconds ?? selectedJob.module_run?.runtime_sec ?? selectedJob.elapsed_seconds)} />
                    <Metric label="Temiz" value={String(selectedJob.summary?.clean_segments ?? selectedJob.segments.length)} />
                    <Metric label="Ham" value={String(selectedJob.summary?.raw_segments ?? '-')} />
                    <Metric label="Düşen" value={String(selectedJob.summary?.quality_drops ?? selectedJob.archive?.quality?.drops ?? 0)} />
                    <Metric label="Timeline" value={String(selectedJob.timeline_events?.length ?? selectedJob.summary?.clean_segments ?? 0)} />
                  </div>
                  <Detail label="Başladı" value={formatDate(selectedJob.started_at)} />
                  <Detail label="Bitti" value={formatDate(selectedJob.completed_at)} />
                  <Detail label="Kanal" value={selectedJob.summary?.channels?.mode || selectedJob.channel_mode || '-'} />
                  <Detail label="VAD konuşma" value={formatSpeechRatio(selectedJob.summary?.vad?.speech_ratio)} />
                  <Detail label="GPU" value={selectedJob.module_run?.gpu_used === true ? 'kullanıldı' : selectedJob.module_run?.gpu_used === false ? 'kullanılmadı' : '-'} />
                  <Detail label="Modül" value={selectedJob.module_run?.module_run_id || '-'} mono />
                </Panel>

                {languageIntel && languageIntel.status !== 'disabled' && (
                  <Panel title="Dil Gözlemi" icon={<Globe2 className="h-4 w-4 text-info" />}>
                    <div className="mb-3 grid grid-cols-2 gap-2">
                      <Metric label="Mod" value={languageIntel.mode || '-'} />
                      <Metric label="Durum" value={languageIntel.status || '-'} />
                      <Metric label="Master" value={formatLanguageLabel(languageIntel.master_language)} />
                      <Metric label="Ham skor" value={formatScore(languageIntel.master_raw_score)} />
                    </div>
                    <Detail label="Routing" value={languageIntel.routing?.applied ? 'uygulandı' : 'kapalı'} />
                    <Detail label="Örnek" value={formatClock(languageIntel.sampled_speech_seconds ?? undefined)} />
                    <Detail label="Süre" value={formatClock(languageIntel.runtime_sec ?? undefined)} />
                    <Detail label="Karar" value={languageIntel.decision_reason || languageIntel.skipped_reason || '-'} />
                    {languageIntel.language_distribution && Object.keys(languageIntel.language_distribution).length > 0 && (
                      <div className="mt-3 space-y-1">
                        {Object.entries(languageIntel.language_distribution)
                          .sort(([, first], [, second]) => second - first)
                          .slice(0, 4)
                          .map(([language, share]) => (
                            <Detail key={language} label={formatLanguageLabel(language)} value={formatShare(share)} />
                          ))}
                      </div>
                    )}
                    {(languageIntel.mixed_window_count || languageIntel.low_confidence_window_count) ? (
                      <div className="mt-3 flex flex-wrap gap-1.5">
                        {languageIntel.mixed_window_count ? <Badge variant="warning">mixed {languageIntel.mixed_window_count}</Badge> : null}
                        {languageIntel.low_confidence_window_count ? <Badge variant="warning">low {languageIntel.low_confidence_window_count}</Badge> : null}
                        {languageIntel.master_language === 'az' ? <Badge variant="warning">AZ routing kapalı</Badge> : null}
                      </div>
                    ) : null}
                    {languageIntel.windows && languageIntel.windows.length > 0 && (
                      <div className="mt-3 max-h-[150px] overflow-auto rounded-sm border border-border-subtle bg-app-shell/60">
                        {languageIntel.windows.slice(0, 8).map((window, index) => (
                          <div key={`${window.start}-${window.end}-${index}`} className="grid grid-cols-[76px_48px_minmax(0,1fr)] gap-2 border-b border-border-subtle/70 px-2 py-1.5 text-[10px] last:border-b-0">
                            <span className="font-mono text-foreground-muted">{formatClock(window.start)}-{formatClock(window.end)}</span>
                            <span className="font-mono uppercase text-info">{formatLanguageLabel(window.language)}</span>
                            <span className="truncate text-foreground-default" title={window.decision_reason}>
                              {formatScore(window.raw_score)} · {window.decision_reason || '-'}
                            </span>
                          </div>
                        ))}
                      </div>
                    )}
                  </Panel>
                )}

                <Panel title="Uyarılar" icon={<AlertTriangle className="h-4 w-4 text-warning" />}>
                  {selectedJob.summary?.safety?.failure_reason && (
                    <Detail label="Sebep" value={selectedJob.summary.safety.failure_reason} mono />
                  )}
                  {errorFlags.length > 0 && (
                    <div className="mt-2 flex flex-wrap gap-1.5">
                      {errorFlags.map((flag) => (
                        <Badge key={flag} variant="warning">{flag}</Badge>
                      ))}
                    </div>
                  )}
                  {uncoveredRanges.length > 0 && (
                    <div className="mt-3 rounded-sm border border-warning/30 bg-warning-subtle/15">
                      {uncoveredRanges.map((range, index) => (
                        <div key={`${range.start}-${range.end}-${index}`} className="border-b border-warning/20 px-2 py-1.5 text-[11px] last:border-b-0">
                          <span className="font-mono text-warning">{formatClock(range.start)}-{formatClock(range.end)}</span>
                          <span className="ml-2 text-foreground-muted">
                            {Math.round(range.speech_seconds)} sn konuşma
                          </span>
                        </div>
                      ))}
                    </div>
                  )}
                  {dropReasons.length > 0 && (
                    <div className="mt-3 space-y-1">
                      {dropReasons.map(([reason, count]) => (
                        <Detail key={reason} label={reason} value={String(count)} />
                      ))}
                    </div>
                  )}
                  {!selectedJob.summary?.safety?.failure_reason && errorFlags.length === 0 && uncoveredRanges.length === 0 && dropReasons.length === 0 && (
                    <EmptyLine text="Uyarı yok." />
                  )}
                </Panel>

                <Panel title="Dosyalar" icon={<FolderOpen className="h-4 w-4 text-info" />}>
                  <div className="space-y-2">
                    {artifactRows.map(([label, value]) => (
                      <Detail key={label} label={label} value={value} mono />
                    ))}
                  </div>
                </Panel>
              </aside>
            </div>
          </ScrollArea>
        )}
      </main>
    </div>
  );
}

function FeedbackEntryRow({ entry, onRemove }: { entry: FeedbackEntry; onRemove: () => void }) {
  return (
    <div className="border-b border-warning/20 px-3 py-2 last:border-b-0">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-1.5">
            <Badge variant="warning" className="gap-1">
              <AlertTriangle className="h-3 w-3" />
              {feedbackKindLabel(entry.kind)}
            </Badge>
            <span className="font-mono text-[10px] text-warning">
              {formatClock(entry.start)}-{formatClock(entry.end)}
            </span>
            <span className="text-[10px] text-foreground-muted">{formatDate(entry.createdAt, true)}</span>
          </div>
          <div className="mt-1 text-[11px] leading-relaxed text-foreground-default">{entry.text}</div>
          {entry.translationText ? (
            <div className="mt-1 border-l-2 border-l-warning-strong bg-warning-subtle/20 px-2 py-1 text-[11px] leading-relaxed text-foreground-strong">
              {entry.translationText}
              {entry.translationModel ? (
                <span className="ml-2 font-mono text-[9px] text-foreground-muted">{entry.translationModel}</span>
              ) : null}
            </div>
          ) : null}
          <div className="mt-1 truncate font-mono text-[9px] text-foreground-muted" title={entry.sourcePath || entry.filename || '-'}>
            {entry.filename || '-'} · {entry.sourcePath || '-'}
          </div>
        </div>
        <Button size="icon-xs" variant="ghost" onClick={onRemove} title="İşareti kaldır">
          <X className="h-3 w-3" />
        </Button>
      </div>
    </div>
  );
}

function feedbackKindLabel(kind: FeedbackEntry['kind']): string {
  if (kind === 'translation') return 'Translate';
  if (kind === 'ocr') return 'OCR';
  return 'Transcript';
}

function StatusBadge({ status }: { status: AsrJobStatus }) {
  return <Badge variant={statusVariant(status)}>{statusLabel(status)}</Badge>;
}

function StatusIcon({ status }: { status: AsrJobStatus }) {
  if (status === 'done') return <CheckCircle2 className="h-4 w-4 text-success" />;
  if (status === 'partial') return <AlertTriangle className="h-4 w-4 text-warning" />;
  if (status === 'failed') return <XCircle className="h-4 w-4 text-danger" />;
  if (status === 'interrupted') return <AlertCircle className="h-4 w-4 text-foreground-muted" />;
  if (status === 'queued' || status === 'running') return <Loader2 className="h-4 w-4 animate-spin text-info" />;
  return <AlertCircle className="h-4 w-4 text-foreground-muted" />;
}

function statusVariant(status: AsrJobStatus): BadgeVariant {
  if (status === 'done') return 'success';
  if (status === 'partial') return 'warning';
  if (status === 'failed') return 'danger';
  return 'secondary';
}

function statusLabel(status: AsrJobStatus): string {
  return (
    {
      queued: 'kuyruk',
      running: 'çalışıyor',
      done: 'tamam',
      partial: 'kısmi',
      failed: 'hata',
      interrupted: 'kesildi',
    } as Record<AsrJobStatus, string>
  )[status] ?? status;
}

function Stat({ label, value, tone = 'muted' }: { label: string; value: string; tone?: 'muted' | 'success' | 'warning' | 'danger' | 'info' }) {
  const toneClass = {
    muted: 'text-foreground-strong',
    success: 'text-success',
    warning: 'text-warning',
    danger: 'text-danger',
    info: 'text-info',
  }[tone];
  return (
    <div className="rounded-sm border border-border-subtle bg-app-shell/55 px-2 py-1.5">
      <div className="text-[9px] uppercase tracking-wider text-foreground-muted">{label}</div>
      <div className={`mt-0.5 truncate font-mono text-[12px] font-semibold ${toneClass}`}>{value}</div>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-sm border border-border-subtle bg-app-shell/55 px-2 py-1.5">
      <div className="text-[9px] uppercase tracking-wider text-foreground-muted">{label}</div>
      <div className="mt-0.5 truncate text-[12px] font-semibold text-foreground-strong" title={value}>{value}</div>
    </div>
  );
}

function Panel({ title, icon, children }: { title: string; icon: ReactNode; children: ReactNode }) {
  return (
    <section className="rounded-sm border border-border-subtle bg-surface/25">
      <div className="flex h-10 items-center gap-2 border-b border-border-subtle px-3">
        {icon}
        <h3 className="text-xs font-bold uppercase tracking-wider text-foreground-strong">{title}</h3>
      </div>
      <div className="p-3">{children}</div>
    </section>
  );
}

function Detail({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="grid grid-cols-[92px_minmax(0,1fr)] gap-2 py-1 text-[11px]">
      <span className="truncate uppercase tracking-wider text-foreground-muted">{label}</span>
      <span className={`min-w-0 break-words text-foreground-default ${mono ? 'font-mono text-[10px]' : ''}`} title={value}>
        {value || '-'}
      </span>
    </div>
  );
}

function EmptyLine({ text }: { text: string }) {
  return <div className="rounded-sm border border-border-subtle bg-app-shell/50 p-3 text-[11px] text-foreground-muted">{text}</div>;
}

function countTextMatches(text: string, query: string): number {
  const needle = query.trim().toLocaleLowerCase('tr-TR');
  if (!needle) return 0;
  const haystack = text.toLocaleLowerCase('tr-TR');
  let count = 0;
  let index = haystack.indexOf(needle);
  while (index >= 0) {
    count += 1;
    index = haystack.indexOf(needle, index + Math.max(needle.length, 1));
  }
  return count;
}

function highlightLogText(text: string, query: string, activeIndex = 0) {
  const needle = query.trim();
  if (!needle) return text;
  const lowerText = text.toLocaleLowerCase('tr-TR');
  const lowerNeedle = needle.toLocaleLowerCase('tr-TR');
  const parts = [];
  let cursor = 0;
  let index = lowerText.indexOf(lowerNeedle);
  let matchIndex = 0;
  while (index >= 0) {
    if (index > cursor) {
      parts.push(text.slice(cursor, index));
    }
    const end = index + needle.length;
    parts.push(
      <mark
        key={`${index}-${end}`}
        data-transcript-match="true"
        className={`rounded-sm px-0.5 text-foreground-strong ${matchIndex === activeIndex ? 'bg-info-subtle ring-1 ring-info' : 'bg-warning-subtle'}`}
      >
        {text.slice(index, end)}
      </mark>
    );
    matchIndex += 1;
    cursor = end;
    index = lowerText.indexOf(lowerNeedle, cursor);
  }
  if (cursor < text.length) {
    parts.push(text.slice(cursor));
  }
  return parts;
}

function buildArtifactRows(job: AsrJob): Array<[string, string]> {
  const rows: Array<[string, string]> = [
    ['Kaynak', job.original_source_path || job.input_path || job.summary?.input_path || '-'],
    ['Çıktı', job.output_dir || '-'],
    ['Job', job.job_dir || '-'],
    ['Log', job.log_path || '-'],
    ['Archive', job.archive_path || '-'],
    ['Summary', job.summary_path || '-'],
    ['Module', job.module_run_path || '-'],
    ['Timeline', job.timeline_events_path || '-'],
    ['Review', job.transcript_review_path || '-'],
  ];
  return rows.filter(([, value]) => value && value !== '-');
}

function formatDate(value: string | null | undefined, timeOnly = false): string {
  if (!value) return '-';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '-';
  return new Intl.DateTimeFormat('tr-TR', {
    day: timeOnly ? undefined : '2-digit',
    month: timeOnly ? undefined : '2-digit',
    year: timeOnly ? undefined : '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: timeOnly ? '2-digit' : undefined,
  }).format(date);
}

function isToday(value: string | null | undefined): boolean {
  if (!value) return false;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return false;
  const now = new Date();
  return date.getFullYear() === now.getFullYear()
    && date.getMonth() === now.getMonth()
    && date.getDate() === now.getDate();
}

function formatSpeechRatio(value: number | undefined): string {
  if (!Number.isFinite(value ?? NaN)) return '-';
  return `${Math.round((value ?? 0) * 100)}%`;
}

function formatScore(value: number | null | undefined): string {
  if (!Number.isFinite(value ?? NaN)) return '-';
  return `${Math.round((value ?? 0) * 100)}%`;
}

function formatShare(value: number | null | undefined): string {
  if (!Number.isFinite(value ?? NaN)) return '-';
  return `${Math.round((value ?? 0) * 100)}%`;
}

function formatLanguageLabel(value: string | null | undefined): string {
  if (!value) return '-';
  const labels: Record<string, string> = {
    ar: 'AR',
    az: 'AZ',
    en: 'EN',
    mixed: 'mixed',
    tr: 'TR',
    unknown: 'unknown',
  };
  return labels[value] ?? value.toUpperCase();
}
