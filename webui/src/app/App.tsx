import { Button, Tabs, TabsList, TabsTrigger, TabsContent } from './components/ui';
import { AnalysisWorkspace } from './components/AnalysisWorkspace';
import type { HeaderProcessStatus } from './components/Header';
import { AccessGate } from './components/AccessGate';
import { SysInfoBar } from './components/SysInfoBar';
import { RestartButton } from './components/RestartButton';
import { FaceBankWorkspace } from './components/FaceBankWorkspace';
import { Lock, LogOut } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';
import { Select, SelectContent, SelectItem, SelectTrigger } from './components/ui/select';
import { JobLogWorkspace } from './components/JobLogWorkspace';
import { TedialWorkspace } from './components/TedialWorkspace';
import type { FlowQueuedMediaRequest } from './components/FlowQueuePanel';
import { fetchMitasAccessSession, logoutMitasAccess } from './auth';
import {
  DEFAULT_TEDIAL_CHANNEL_MODE,
  openTedialMediaInMitas,
  searchTedial,
  startTedialAsrRangeJob,
  startTedialAsrJob,
  startTedialPipelineJob,
  tedialDurationSeconds,
  tedialManifestUrl,
  type TedialAsrChannelMode,
  type TedialAudioTrack,
  type TedialImportResult,
  type TedialMediaImportResult,
  type TedialSearchResult,
} from './tedial-api';
import {
  fetchAsrJob,
  defaultAsrChannelState,
  deleteClipGeneratedData,
  isAsrJobFinished,
  localFileSourcePath,
  prepareClip,
  processClipAsrRange,
  profileRunsOcr,
  reprocessClipAsr,
  shouldOfferTurkishTranslation,
  startAsrJob,
  startPipelineJob,
  translateAsrSegment,
  translateAsrSegments,
  ANALYSIS_PROFILE_OPTIONS,
  analysisProfileLabel,
  type AnalysisProfile,
  type AsrChannelKey,
  type AsrChannelState,
  type ClipGeneratedDataKind,
  type AsrJob,
  type PlaybackState,
  type SeekRequest,
  type SegmentTranslationState,
} from './asr-api';

interface TopProfileControlsProps {
  analysisProfile: AnalysisProfile;
  onAnalysisProfileChange: (profile: AnalysisProfile) => void;
}

type WorkspaceKey = 'analysis' | 'tedial' | 'facebank' | 'logs';

interface AuthenticatedAppProps {
  onSignOut: () => void;
}

interface RangeAsrState {
  start: number;
  end: number;
  jobId: string | null;
  starting: boolean;
}

type LastSessionSnapshot =
  | { kind: 'job'; jobId: string; activeWorkspace?: WorkspaceKey }
  | {
      kind: 'tedial';
      item: TedialSearchResult;
      audioTrack: TedialAudioTrack;
      channelMode: TedialAsrChannelMode;
      activeWorkspace?: WorkspaceKey;
    };

const LAST_SESSION_KEY = 'mitas.lastOpenMedia.v1';

function readLastSessionSnapshot(): LastSessionSnapshot | null {
  if (typeof window === 'undefined') return null;
  try {
    const parsed = JSON.parse(window.localStorage.getItem(LAST_SESSION_KEY) || 'null');
    if (!parsed || typeof parsed !== 'object') return null;
    if (parsed.kind === 'job' && typeof parsed.jobId === 'string' && parsed.jobId) {
      return { kind: 'job', jobId: parsed.jobId, activeWorkspace: parsed.activeWorkspace };
    }
    if (parsed.kind === 'tedial' && parsed.item && typeof parsed.item === 'object') {
      return {
        kind: 'tedial',
        item: parsed.item,
        audioTrack: parsed.audioTrack === 1 ? 1 : 0,
        channelMode: parsed.channelMode === 'split' || parsed.channelMode === 'mono' ? parsed.channelMode : DEFAULT_TEDIAL_CHANNEL_MODE,
        activeWorkspace: parsed.activeWorkspace,
      };
    }
  } catch {
    return null;
  }
  return null;
}

function writeLastSessionSnapshot(snapshot: LastSessionSnapshot): void {
  if (typeof window === 'undefined') return;
  window.localStorage.setItem(LAST_SESSION_KEY, JSON.stringify(snapshot));
}

function clearLastSessionSnapshot(): void {
  if (typeof window === 'undefined') return;
  window.localStorage.removeItem(LAST_SESSION_KEY);
}

function TopProfileControls({
  analysisProfile,
  onAnalysisProfileChange,
}: TopProfileControlsProps) {
  return (
    <div className="flex items-center gap-2 shrink-0 rounded-sm border border-border-subtle bg-surface/40 px-2 py-1">
      <Select value={analysisProfile} onValueChange={(value) => onAnalysisProfileChange(value as AnalysisProfile)}>
        <SelectTrigger
          size="sm"
          className="h-7 w-[150px] rounded-sm border-border-mitas bg-app-shell/80 px-2 py-1 text-xs text-foreground-default"
          title="İşlem profilini seç"
        >
          <span className="truncate font-semibold">{analysisProfileLabel(analysisProfile)}</span>
        </SelectTrigger>
        <SelectContent className="border-border-mitas bg-surface text-foreground-default">
          {ANALYSIS_PROFILE_OPTIONS.map((option) => (
            <SelectItem
              key={option.value}
              value={option.value}
              className="cursor-pointer text-xs focus:bg-surface-elevated focus:text-foreground-strong"
            >
              <div className="flex flex-col">
                <span>{option.label}</span>
                <span className="text-[10px] text-foreground-muted normal-case">{option.description}</span>
              </div>
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}

function inferMediaType(filename: string): string | null {
  const ext = filename.split('.').pop()?.toLowerCase();
  if (!ext) return null;
  if (['mp4', 'm4v', 'mov'].includes(ext)) return 'video/mp4';
  if (ext === 'webm') return 'video/webm';
  if (ext === 'ogg' || ext === 'ogv') return 'video/ogg';
  if (ext === 'wav') return 'audio/wav';
  if (ext === 'mp3') return 'audio/mpeg';
  if (ext === 'm4a') return 'audio/mp4';
  return null;
}

function mediaTypeForFile(file: File): string | null {
  if (file.type && file.type !== 'application/octet-stream') {
    return file.type;
  }
  return inferMediaType(file.name);
}

function generatedDataAvailabilityForJob(job: AsrJob | null): Record<ClipGeneratedDataKind, boolean> {
  const availability: Record<ClipGeneratedDataKind, boolean> = {
    asr: false,
    ocr: false,
    face: false,
    tag: false,
  };
  if (!job?.clip_id) {
    return availability;
  }
  (Object.keys(availability) as ClipGeneratedDataKind[]).forEach((kind) => {
    const state = job.module_summary?.[kind];
    availability[kind] = Boolean((state?.job_count ?? 0) > 0 || state?.latest_job_id || state?.status);
  });
  availability.asr = availability.asr || Boolean(
    job.job_id && (
      job.segments?.length > 0 ||
      job.transcript?.trim() ||
      job.archive_path ||
      job.summary_path ||
      job.status === 'done' ||
      job.status === 'partial'
    )
  );
  return availability;
}

async function resolveTedialQueueItem(query: string | null | undefined): Promise<TedialSearchResult | null> {
  const normalized = (query || '').trim();
  if (!normalized) return null;
  const leadingTrtId = normalized.match(/^\d{2,4}(?:-\d+){2,}/)?.[0] ?? null;
  const candidates = [normalized, leadingTrtId].filter((item, index, items): item is string => (
    Boolean(item) && items.indexOf(item) === index
  ));
  for (const candidate of candidates) {
    try {
      const results = await searchTedial(candidate);
      if (results[0]) {
        return results[0];
      }
    } catch {
      // Try the next candidate; Tedial session errors are surfaced by the caller state.
    }
  }
  return null;
}

function AuthenticatedApp({ onSignOut }: AuthenticatedAppProps) {
  const [activeWorkspace, setActiveWorkspace] = useState<WorkspaceKey>('analysis');
  const [asrJob, setAsrJob] = useState<AsrJob | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [selectedMediaName, setSelectedMediaName] = useState<string | null>(null);
  const [selectedMediaSourcePath, setSelectedMediaSourcePath] = useState<string | null>(null);
  const [selectedClipId, setSelectedClipId] = useState<string | null>(null);
  const [selectedTedialItem, setSelectedTedialItem] = useState<TedialSearchResult | null>(null);
  const [selectedTedialAudioTrack, setSelectedTedialAudioTrack] = useState<TedialAudioTrack>(0);
  const [selectedTedialChannelMode, setSelectedTedialChannelMode] = useState<TedialAsrChannelMode>(DEFAULT_TEDIAL_CHANNEL_MODE);
  const [isStartingAsr, setIsStartingAsr] = useState(false);
  const [rangeAsrState, setRangeAsrState] = useState<RangeAsrState | null>(null);
  const [isDeletingGeneratedData, setIsDeletingGeneratedData] = useState(false);
  const [mediaPreviewUrl, setMediaPreviewUrl] = useState<string | null>(null);
  const [mediaType, setMediaType] = useState<string | null>(null);
  const [mediaDurationHint, setMediaDurationHint] = useState<number | null>(null);
  const [playback, setPlayback] = useState<PlaybackState>({ currentTime: 0, duration: 0, isPlaying: false });
  const [seekRequest, setSeekRequest] = useState<SeekRequest | null>(null);
  const [selectedSegmentIndex, setSelectedSegmentIndex] = useState<number | null>(null);
  const [analysisProfile, setAnalysisProfile] = useState<AnalysisProfile>('stt');
  const [isLiveSttBusy, setIsLiveSttBusy] = useState(false);
  const [isTranslatingAll, setIsTranslatingAll] = useState(false);
  const [segmentTranslations, setSegmentTranslations] = useState<Record<number, SegmentTranslationState>>({});
  const [enabledAsrChannels, setEnabledAsrChannels] = useState<AsrChannelState>(() => defaultAsrChannelState());
  const [autoLoadRecentEnabled, setAutoLoadRecentEnabled] = useState(true);

  const prepareSelectedMedia = useCallback((file: File) => {
    setAutoLoadRecentEnabled(false);
    setUploadError(null);
    setRangeAsrState(null);
    clearLastSessionSnapshot();
    setAsrJob(null);
    setSegmentTranslations({});
    setEnabledAsrChannels(defaultAsrChannelState());
    setSelectedFile(file);
    setSelectedMediaName(file.name);
    setSelectedMediaSourcePath(localFileSourcePath(file) || file.name);
    setSelectedClipId(null);
    setSelectedTedialItem(null);
    setSelectedTedialAudioTrack(0);
    setSelectedTedialChannelMode(DEFAULT_TEDIAL_CHANNEL_MODE);
    setSelectedSegmentIndex(null);
    setIsLiveSttBusy(false);
    setPlayback({ currentTime: 0, duration: 0, isPlaying: false });
    setSeekRequest(null);
    setMediaType(mediaTypeForFile(file));
    setMediaDurationHint(null);
    setMediaPreviewUrl((currentUrl) => {
      if (currentUrl?.startsWith('blob:')) {
        URL.revokeObjectURL(currentUrl);
      }
      return URL.createObjectURL(file);
    });
  }, []);

  const handleUpload = useCallback((file: File) => {
    prepareSelectedMedia(file);
  }, [prepareSelectedMedia]);

  const startAsrForFile = useCallback(async (file: File) => {
    setUploadError(null);
    setIsStartingAsr(true);
    setRangeAsrState(null);
    setAsrJob(null);
    setSegmentTranslations({});
    setSelectedSegmentIndex(null);
    try {
      // film/dizi + OCR'lı profiller → TAM pipeline (OCR künye + ASR + PDF); stt/haber → ASR-only
      const job = profileRunsOcr(analysisProfile)
        ? await startPipelineJob(file, analysisProfile)
        : await startAsrJob(file, analysisProfile);
      setAsrJob(job);
      setSelectedClipId(job.clip_id ?? null);
      return job;
    } catch (error) {
      setUploadError(error instanceof Error ? error.message : 'ASR yükleme hatası');
      throw error;
    } finally {
      setIsStartingAsr(false);
    }
  }, [analysisProfile]);

  const applyTedialImportResult = useCallback((result: TedialMediaImportResult | TedialImportResult) => {
    const importedJob = 'job' in result ? result.job : null;
    setAutoLoadRecentEnabled(false);
    setUploadError(null);
    setAsrJob(importedJob);
    setSegmentTranslations({});
    setEnabledAsrChannels(defaultAsrChannelState());
    setSelectedFile(null);
    setSelectedMediaName(result.filename);
    setSelectedMediaSourcePath(importedJob?.original_source_path || 'Tedial');
    setSelectedClipId(importedJob?.clip_id ?? null);
    setSelectedTedialItem(result.item);
    setSelectedTedialAudioTrack(result.audioTrack);
    setSelectedTedialChannelMode(result.channelMode);
    setSelectedSegmentIndex(null);
    setIsLiveSttBusy(false);
    setPlayback({ currentTime: 0, duration: 0, isPlaying: false });
    setSeekRequest(null);
    setMediaType(result.mediaType);
    setMediaDurationHint(tedialDurationSeconds(result.item));
    setMediaPreviewUrl((currentUrl) => {
      if (currentUrl?.startsWith('blob:')) {
        URL.revokeObjectURL(currentUrl);
      }
      return result.streamUrl;
    });
  }, []);

  const startAsrForTedial = useCallback(async (item: TedialSearchResult) => {
    setUploadError(null);
    setIsStartingAsr(true);
    setRangeAsrState(null);
    setAsrJob(null);
    setSegmentTranslations({});
    setEnabledAsrChannels(defaultAsrChannelState());
    setSelectedSegmentIndex(null);
    try {
      // film/dizi + OCR'lı profiller → Tedial videoda da TAM pipeline (OCR künye + ASR + PDF),
      // tıpkı yüklemede olduğu gibi; stt/haber → ASR-only.
      if (profileRunsOcr(analysisProfile)) {
        const job = await startTedialPipelineJob(item, {
          audioTrack: selectedTedialAudioTrack,
          channelMode: selectedTedialChannelMode,
          analysisProfile,
        });
        setAsrJob(job);
        setSelectedClipId(job.clip_id ?? null);
        return job;
      }
      const result = await startTedialAsrJob(item, {
        audioTrack: selectedTedialAudioTrack,
        channelMode: selectedTedialChannelMode,
      });
      applyTedialImportResult(result);
      return result.job;
    } catch (error) {
      setUploadError(error instanceof Error ? error.message : 'Tedial STT başlatma hatası');
      throw error;
    } finally {
      setIsStartingAsr(false);
    }
  }, [analysisProfile, applyTedialImportResult, selectedTedialAudioTrack, selectedTedialChannelMode]);

  const startAsrForClip = useCallback(async (clipId: string) => {
    setUploadError(null);
    setIsStartingAsr(true);
    setRangeAsrState(null);
    setAsrJob(null);
    setSegmentTranslations({});
    setEnabledAsrChannels(defaultAsrChannelState());
    setSelectedSegmentIndex(null);
    try {
      const job = await reprocessClipAsr(clipId, analysisProfile);
      setAsrJob(job);
      setSelectedClipId(job.clip_id ?? clipId);
      setSelectedMediaName(job.filename);
      setSelectedMediaSourcePath(job.original_source_path || job.input_path || job.summary?.input_path || null);
      setMediaType(inferMediaType(job.filename));
      setMediaDurationHint(job.summary?.audio_duration ?? null);
      setMediaPreviewUrl((currentUrl) => {
        if (currentUrl?.startsWith('blob:')) {
          URL.revokeObjectURL(currentUrl);
        }
        return `/api/jobs/${encodeURIComponent(job.job_id)}/media`;
      });
      return job;
    } catch (error) {
      setUploadError(error instanceof Error ? error.message : 'Klipten ASR tekrar başlatma hatası');
      throw error;
    } finally {
      setIsStartingAsr(false);
    }
  }, [analysisProfile]);

  const handleStartAsr = useCallback(async () => {
    if (!selectedFile && !selectedTedialItem && !selectedClipId) {
      setUploadError('STT başlatmak için önce medya yükle.');
      return;
    }

    if (isLiveSttBusy) {
      setUploadError('Canlı STT Preview çalışırken Başlat kapalı.');
      return;
    }

    if (selectedFile) {
      await startAsrForFile(selectedFile).catch(() => undefined);
      return;
    }
    if (selectedTedialItem) {
      await startAsrForTedial(selectedTedialItem).catch(() => undefined);
      return;
    }
    if (selectedClipId) {
      await startAsrForClip(selectedClipId).catch(() => undefined);
    }
  }, [analysisProfile, isLiveSttBusy, selectedClipId, selectedFile, selectedTedialItem, startAsrForClip, startAsrForFile, startAsrForTedial]);

  const handleStartAsrRange = useCallback(async (from: number, to: number) => {
    const start = Math.max(0, Math.min(from, to));
    const end = Math.max(from, to);
    if (end <= start) {
      setUploadError('Geçerli bir in/out aralığı seç.');
      return;
    }
    if (isLiveSttBusy) {
      setUploadError('Canlı STT Preview çalışırken Başlat kapalı.');
      return;
    }

    setUploadError(null);
    setRangeAsrState({ start, end, jobId: null, starting: true });
    setIsStartingAsr(true);
    setAsrJob(null);
    setSegmentTranslations({});
    setSelectedSegmentIndex(null);
    try {
      if (selectedTedialItem) {
        const result = await startTedialAsrRangeJob(selectedTedialItem, { start, end }, {
          audioTrack: selectedTedialAudioTrack,
          channelMode: selectedTedialChannelMode,
          analysisProfile,
        });
        applyTedialImportResult(result);
        setRangeAsrState({ start, end, jobId: result.job.job_id, starting: false });
        return;
      }
      const clipId = selectedClipId ?? (selectedFile ? (await prepareClip(selectedFile)).clip_id : null);
      if (clipId) {
        if (!selectedClipId) setSelectedClipId(clipId);
        const job = await processClipAsrRange(clipId, { start, end }, analysisProfile);
        setRangeAsrState({ start, end, jobId: job.job_id, starting: false });
        setAsrJob(job);
        setSelectedClipId(job.clip_id ?? clipId);
        if (!selectedFile) {
          setSelectedTedialItem(null);
          setSelectedMediaName(job.filename);
          setSelectedMediaSourcePath(job.original_source_path || job.input_path || job.summary?.input_path || null);
          setPlayback({ currentTime: 0, duration: 0, isPlaying: false });
          setSeekRequest(null);
          setMediaType(inferMediaType(job.filename));
          setMediaDurationHint(Math.max(0, end - start));
          setMediaPreviewUrl((currentUrl) => {
            if (currentUrl?.startsWith('blob:')) {
              URL.revokeObjectURL(currentUrl);
            }
            return `/api/jobs/${encodeURIComponent(job.job_id)}/media`;
          });
        }
        return;
      }
      setUploadError('Aralık STT için medya yükle veya Tedial klibi seç.');
      setRangeAsrState(null);
    } catch (error) {
      setUploadError(error instanceof Error ? error.message : 'Aralık STT başlatma hatası');
      setRangeAsrState(null);
    } finally {
      setIsStartingAsr(false);
    }
  }, [
    analysisProfile,
    applyTedialImportResult,
    isLiveSttBusy,
    selectedClipId,
    selectedFile,
    selectedTedialAudioTrack,
    selectedTedialChannelMode,
    selectedTedialItem,
  ]);

  const handlePermanentDeleteGeneratedData = useCallback(async (kind: ClipGeneratedDataKind) => {
    const clipId = asrJob?.clip_id ?? selectedClipId;
    if (!clipId) {
      setUploadError('Kalıcı silme için klip kaydı bulunamadı.');
      throw new Error('clip_not_found');
    }
    setUploadError(null);
    setIsDeletingGeneratedData(true);
    try {
      await deleteClipGeneratedData(clipId, kind);
      if (kind === 'asr') {
        setAsrJob(null);
        setSegmentTranslations({});
        setSelectedSegmentIndex(null);
        setSelectedClipId(clipId);
        setMediaPreviewUrl((currentUrl) => {
          if (currentUrl?.startsWith('blob:')) {
            URL.revokeObjectURL(currentUrl);
          }
          return `/api/clips/${encodeURIComponent(clipId)}/media?preview_ts=${Date.now()}`;
        });
      } else if (asrJob) {
        try {
          setAsrJob(await fetchAsrJob(asrJob.job_id));
        } catch {
          setAsrJob({ ...asrJob });
        }
      }
      setUploadError(null);
    } catch (error) {
      setUploadError(error instanceof Error ? error.message : 'Kalıcı silme başarısız oldu.');
      throw error;
    } finally {
      setIsDeletingGeneratedData(false);
    }
  }, [asrJob, selectedClipId]);

  const handleTedialImport = useCallback(async (result: TedialMediaImportResult) => {
    setActiveWorkspace('analysis');
    setAnalysisProfile('stt');
    setRangeAsrState(null);
    applyTedialImportResult(result);
  }, [applyTedialImportResult]);

  const handleOpenHistoricalJob = useCallback((job: AsrJob) => {
    setAutoLoadRecentEnabled(false);
    setUploadError(null);
    setRangeAsrState(null);
    setAsrJob(job);
    setSegmentTranslations({});
    setEnabledAsrChannels(defaultAsrChannelState());
    setSelectedFile(null);
    setSelectedMediaName(job.filename);
    setSelectedMediaSourcePath(job.original_source_path || job.input_path || job.summary?.input_path || null);
    setSelectedClipId(job.clip_id ?? null);
    setSelectedTedialItem(null);
    setSelectedTedialAudioTrack(0);
    setSelectedTedialChannelMode(DEFAULT_TEDIAL_CHANNEL_MODE);
    setSelectedSegmentIndex(null);
    setIsLiveSttBusy(false);
    setPlayback({ currentTime: 0, duration: 0, isPlaying: false });
    setSeekRequest(null);
    setMediaType(inferMediaType(job.filename));
    setMediaDurationHint(job.summary?.audio_duration ?? null);
    setMediaPreviewUrl((currentUrl) => {
      if (currentUrl?.startsWith('blob:')) {
        URL.revokeObjectURL(currentUrl);
      }
      return `/api/jobs/${encodeURIComponent(job.job_id)}/media`;
    });
    setAnalysisProfile('stt');
    setActiveWorkspace('analysis');
  }, []);

  const handleOpenQueuedMedia = useCallback(async (request: FlowQueuedMediaRequest) => {
    setAutoLoadRecentEnabled(false);
    if (request.source === 'upload' && request.file) {
      setActiveWorkspace('analysis');
      prepareSelectedMedia(request.file);
      return;
    }

    if (request.source === 'upload' && request.storedMediaUrl) {
      setUploadError(null);
      setRangeAsrState(null);
      setAsrJob(null);
      setSegmentTranslations({});
      setEnabledAsrChannels(defaultAsrChannelState());
      setSelectedFile(null);
      setSelectedMediaName(request.name);
      setSelectedMediaSourcePath(request.sourcePath || request.storedMediaUrl);
      setSelectedClipId(null);
      setSelectedTedialItem(null);
      setSelectedTedialAudioTrack(0);
      setSelectedTedialChannelMode(DEFAULT_TEDIAL_CHANNEL_MODE);
      setSelectedSegmentIndex(null);
      setIsLiveSttBusy(false);
      setPlayback({ currentTime: 0, duration: 0, isPlaying: false });
      setSeekRequest(null);
      setMediaType(request.mediaType || inferMediaType(request.name));
      setMediaDurationHint(null);
      setMediaPreviewUrl((currentUrl) => {
        if (currentUrl?.startsWith('blob:')) {
          URL.revokeObjectURL(currentUrl);
        }
        const separator = request.storedMediaUrl!.includes('?') ? '&' : '?';
        return `${request.storedMediaUrl}${separator}preview_ts=${Date.now()}`;
      });
      setActiveWorkspace('analysis');
      return;
    }

    if (request.source === 'tedial') {
      const tedialItem = request.tedialItem ?? await resolveTedialQueueItem(request.tedialQuery || request.name);
      const manifestUrl = tedialItem ? tedialManifestUrl(tedialItem, 0) : '';
      if (!tedialItem || !manifestUrl) {
        setUploadError('Tedial klibi playerda açılamadı: manifest bilgisi bulunamadı. Eski medya temizlendi.');
        setRangeAsrState(null);
        setAsrJob(null);
        setSelectedFile(null);
        setSelectedClipId(null);
        setSelectedTedialItem(null);
        setSelectedMediaName(request.name || 'Tedial klip');
        setSelectedMediaSourcePath('Tedial');
        setMediaType(null);
        setMediaDurationHint(null);
        setMediaPreviewUrl((currentUrl) => {
          if (currentUrl?.startsWith('blob:')) {
            URL.revokeObjectURL(currentUrl);
          }
          return null;
        });
        setActiveWorkspace('analysis');
        return;
      }

      setUploadError(null);
      setRangeAsrState(null);
      setAsrJob(null);
      setSegmentTranslations({});
      setEnabledAsrChannels(defaultAsrChannelState());
      setSelectedFile(null);
      setSelectedMediaName(request.name || tedialItem.title || tedialItem.trt_id || tedialItem.asset_id || 'Tedial klip');
      setSelectedMediaSourcePath('Tedial');
      setSelectedClipId(null);
      setSelectedTedialItem(tedialItem);
      setSelectedTedialAudioTrack(0);
      setSelectedTedialChannelMode(DEFAULT_TEDIAL_CHANNEL_MODE);
      setSelectedSegmentIndex(null);
      setIsLiveSttBusy(false);
      setPlayback({ currentTime: 0, duration: 0, isPlaying: false });
      setSeekRequest(null);
      setMediaType('application/dash+xml');
      setMediaDurationHint(tedialDurationSeconds(tedialItem));
      setMediaPreviewUrl((currentUrl) => {
        if (currentUrl?.startsWith('blob:')) {
          URL.revokeObjectURL(currentUrl);
        }
        const separator = manifestUrl.includes('?') ? '&' : '?';
        return `${manifestUrl}${separator}preview_ts=${Date.now()}`;
      });
      setActiveWorkspace('analysis');
      return;
    }

    if (request.job) {
      handleOpenHistoricalJob(request.job);
    }
  }, [handleOpenHistoricalJob, prepareSelectedMedia]);

  const handleResetMedia = useCallback(() => {
    setAutoLoadRecentEnabled(false);
    setUploadError(null);
    setRangeAsrState(null);
    clearLastSessionSnapshot();
    setAsrJob(null);
    setSegmentTranslations({});
    setEnabledAsrChannels(defaultAsrChannelState());
    setSelectedFile(null);
    setSelectedMediaName(null);
    setSelectedMediaSourcePath(null);
    setSelectedClipId(null);
    setSelectedTedialItem(null);
    setSelectedTedialAudioTrack(0);
    setSelectedTedialChannelMode(DEFAULT_TEDIAL_CHANNEL_MODE);
    setSelectedSegmentIndex(null);
    setIsLiveSttBusy(false);
    setPlayback({ currentTime: 0, duration: 0, isPlaying: false });
    setSeekRequest(null);
    setMediaType(null);
    setMediaDurationHint(null);
    setMediaPreviewUrl((currentUrl) => {
      if (currentUrl?.startsWith('blob:')) {
        URL.revokeObjectURL(currentUrl);
      }
      return null;
    });
  }, []);

  const handleOpenJobLog = useCallback((job: AsrJob) => {
    setRangeAsrState(null);
    setAsrJob(job);
    setSelectedMediaName(job.filename);
    setSelectedMediaSourcePath(job.original_source_path || job.input_path || job.summary?.input_path || null);
    setSelectedFile(null);
    setSelectedClipId(job.clip_id ?? null);
    setSelectedTedialItem(null);
    setSelectedSegmentIndex(null);
    setActiveWorkspace('logs');
  }, []);

  const handleProfileChange = useCallback((profile: AnalysisProfile) => {
    setAnalysisProfile(profile);
    if (profile !== 'stt') {
      setIsLiveSttBusy(false);
    }
  }, []);

  const handleSeek = useCallback((time: number) => {
    setSeekRequest({ id: Date.now(), time });
    setPlayback((current) => ({ ...current, currentTime: time }));
  }, []);

  const handleToggleAsrChannel = useCallback((channel: AsrChannelKey) => {
    setEnabledAsrChannels((current) => {
      const next = {
        ...current,
        [channel]: !current[channel],
      };
      if (!next.L && !next.R) {
        next[channel] = true;
      }
      return next;
    });
  }, []);

  const handleSelectSegment = useCallback((index: number) => {
    const segment = asrJob?.segments?.[index];
    if (!segment) {
      return;
    }
    setSelectedSegmentIndex(index);
    handleSeek(segment.start);
  }, [asrJob?.segments, handleSeek]);

  const handleTranslateSegment = useCallback(async (index: number) => {
    const job = asrJob;
    const segment = job?.segments?.[index];
    if (!job || !segment) {
      return;
    }

    setSegmentTranslations((current) => ({
      ...current,
      [index]: { status: 'loading' },
    }));
    try {
      const result = await translateAsrSegment(job.job_id, index, segment);
      setSegmentTranslations((current) => ({
        ...current,
        [index]: { status: 'done', result },
      }));
    } catch (error) {
      setSegmentTranslations((current) => ({
        ...current,
        [index]: {
          status: 'error',
          error: error instanceof Error ? error.message : 'Çeviri başarısız oldu.',
        },
      }));
    }
  }, [asrJob]);

  const handleTranslateAllSegments = useCallback(async () => {
    const job = asrJob;
    const segments = job?.segments ?? [];
    const targetIndexes = segments
      .map((segment, index) => ({ segment, index }))
      .filter(({ segment }) => shouldOfferTurkishTranslation(segment))
      .map(({ index }) => index);
    if (!job || targetIndexes.length === 0) {
      return;
    }

    setIsTranslatingAll(true);
    setSegmentTranslations((current) => {
      const next = { ...current };
      targetIndexes.forEach((index) => {
        next[index] = { status: 'loading' };
      });
      return next;
    });
    try {
      const results = await translateAsrSegments(job.job_id, segments);
      setSegmentTranslations((current) => {
        const next = { ...current };
        Object.entries(results).forEach(([index, result]) => {
          next[Number(index)] = { status: 'done', result };
        });
        return next;
      });
    } catch (error) {
      setSegmentTranslations((current) => {
        const next = { ...current };
        targetIndexes.forEach((index) => {
          next[index] = {
            status: 'error',
            error: error instanceof Error ? error.message : 'Toplu çeviri başarısız oldu.',
          };
        });
        return next;
      });
    } finally {
      setIsTranslatingAll(false);
    }
  }, [asrJob]);

  useEffect(() => {
    setSegmentTranslations({});
    setIsTranslatingAll(false);
  }, [asrJob?.job_id]);

  useEffect(() => {
    let cancelled = false;
    if (!autoLoadRecentEnabled || asrJob || selectedFile || selectedTedialItem || mediaPreviewUrl) {
      return undefined;
    }
    setAutoLoadRecentEnabled(false);
    const snapshot = readLastSessionSnapshot();
    if (!snapshot) {
      return undefined;
    }
    if (snapshot.kind === 'job') {
      fetchAsrJob(snapshot.jobId)
        .then((job) => {
          if (!cancelled) {
            handleOpenHistoricalJob(job);
            setActiveWorkspace(snapshot.activeWorkspace ?? 'analysis');
          }
        })
        .catch(() => {
          clearLastSessionSnapshot();
        });
    } else {
      try {
        const result = openTedialMediaInMitas(snapshot.item, {
          audioTrack: snapshot.audioTrack,
          channelMode: snapshot.channelMode,
        });
        if (!cancelled) {
          applyTedialImportResult(result);
          setActiveWorkspace(snapshot.activeWorkspace ?? 'analysis');
        }
      } catch {
        clearLastSessionSnapshot();
      }
    }
    return () => {
      cancelled = true;
    };
  }, [
    applyTedialImportResult,
    asrJob,
    autoLoadRecentEnabled,
    handleOpenHistoricalJob,
    mediaPreviewUrl,
    selectedFile,
    selectedTedialItem,
  ]);

  useEffect(() => {
    if (!mediaPreviewUrl) {
      return;
    }
    if (asrJob?.job_id) {
      writeLastSessionSnapshot({
        kind: 'job',
        jobId: asrJob.job_id,
        activeWorkspace,
      });
      return;
    }
    if (selectedTedialItem) {
      writeLastSessionSnapshot({
        kind: 'tedial',
        item: selectedTedialItem,
        audioTrack: selectedTedialAudioTrack,
        channelMode: selectedTedialChannelMode,
        activeWorkspace,
      });
    }
  }, [
    activeWorkspace,
    asrJob?.job_id,
    mediaPreviewUrl,
    selectedTedialAudioTrack,
    selectedTedialChannelMode,
    selectedTedialItem,
  ]);

  useEffect(() => {
    if (!asrJob || mediaPreviewUrl || selectedFile || selectedTedialItem) {
      return;
    }
    setSelectedMediaName(asrJob.filename);
    setSelectedMediaSourcePath(asrJob.original_source_path || asrJob.input_path || asrJob.summary?.input_path || null);
    setSelectedClipId(asrJob.clip_id ?? null);
    setMediaType(inferMediaType(asrJob.filename));
    setMediaDurationHint(asrJob.summary?.audio_duration ?? null);
    setMediaPreviewUrl((currentUrl) => {
      if (currentUrl?.startsWith('blob:')) {
        URL.revokeObjectURL(currentUrl);
      }
      return `/api/jobs/${encodeURIComponent(asrJob.job_id)}/media`;
    });
  }, [asrJob, mediaPreviewUrl, selectedFile, selectedTedialItem]);

  useEffect(() => {
    const segments = asrJob?.segments ?? [];
    if (!segments.length) {
      if (selectedSegmentIndex !== null) {
        setSelectedSegmentIndex(null);
      }
      return;
    }

    const activeIndex = segments.findIndex((segment) => (
      playback.currentTime >= segment.start && playback.currentTime <= segment.end
    ));
    if (activeIndex !== selectedSegmentIndex) {
      setSelectedSegmentIndex(activeIndex === -1 ? null : activeIndex);
    }
  }, [asrJob?.segments, playback.currentTime, selectedSegmentIndex]);

  useEffect(() => {
    if (!asrJob || isAsrJobFinished(asrJob)) {
      return undefined;
    }

    const interval = window.setInterval(async () => {
      try {
        setAsrJob(await fetchAsrJob(asrJob.job_id));
      } catch (error) {
        setUploadError(error instanceof Error ? error.message : 'ASR durum sorgusu başarısız');
      }
    }, 2500);

    return () => window.clearInterval(interval);
  }, [asrJob]);

  useEffect(() => {
    return () => {
      if (mediaPreviewUrl?.startsWith('blob:')) {
        URL.revokeObjectURL(mediaPreviewUrl);
      }
    };
  }, [mediaPreviewUrl]);

  const generatedDataAvailability = generatedDataAvailabilityForJob(asrJob);
  const activeRangeJob = rangeAsrState?.jobId && asrJob?.job_id === rangeAsrState.jobId ? asrJob : null;
  const activeAsrProcessStatus: HeaderProcessStatus | null = isStartingAsr || asrJob
    ? {
        label: isStartingAsr
          ? 'STT başlatılıyor'
          : asrJob?.status === 'queued'
            ? 'STT kuyrukta'
            : asrJob?.status === 'running'
              ? 'STT çalışıyor'
              : asrJob?.status === 'failed'
                ? 'STT hata'
                : 'STT/ASR',
        percent: Math.max(0, Math.min(100, Math.round(asrJob?.progress_percent ?? (isStartingAsr ? 3 : 0)))),
        active: isStartingAsr || asrJob?.status === 'queued' || asrJob?.status === 'running',
      }
    : null;
  const processStatus: HeaderProcessStatus | null = rangeAsrState
    ? {
        label: rangeAsrState.starting
          ? 'Aralık STT hazırlanıyor'
          : activeRangeJob?.status === 'queued'
            ? 'Aralık STT kuyrukta'
            : activeRangeJob?.status === 'running'
              ? 'Aralık STT çalışıyor'
              : activeRangeJob?.status === 'done'
                ? 'Aralık STT'
                : activeRangeJob?.status === 'partial'
                  ? 'Aralık STT'
                  : activeRangeJob?.status === 'failed'
                    ? 'Aralık STT hata'
                    : 'Aralık STT başlatıldı',
        percent: Math.max(0, Math.min(100, Math.round(activeRangeJob?.progress_percent ?? (rangeAsrState.starting ? 3 : 5)))),
        active: rangeAsrState.starting || activeRangeJob?.status === 'queued' || activeRangeJob?.status === 'running',
      }
    : activeAsrProcessStatus;

  return (
    <div className="flex flex-col h-screen w-full bg-app-shell text-foreground-default overflow-hidden font-sans selection:bg-info-subtle relative">
      <Tabs value={activeWorkspace} onValueChange={(value) => setActiveWorkspace(value as WorkspaceKey)} className="flex flex-col h-full w-full">
        {/* Global Shell Top Bar */}
        <div className="relative grid h-14 shrink-0 grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] items-center gap-5 border-b border-border-subtle bg-app-shell px-4">
          <div className="flex min-w-0 items-center gap-5">
            <div className="flex items-center gap-3 shrink-0">
              <RestartButton />
            </div>

            <TopProfileControls
              analysisProfile={analysisProfile}
              onAnalysisProfileChange={handleProfileChange}
            />
          </div>

          {activeWorkspace === 'analysis' ? (
            <div className="relative flex items-center justify-self-center select-none">
              <img src="/mitas-new-wordmark.png" alt="MITAS" className="h-[62px] w-auto object-contain" />
              <span className="absolute right-[14px] bottom-2 text-[10px] font-mono text-foreground-muted">v2.2</span>
            </div>
          ) : (
            <TabsList className="relative z-10 flex h-9 shrink-0 items-center justify-center gap-1 overflow-hidden rounded-sm border border-border-mitas bg-surface/70 p-1 shadow-sm">
              <TabsTrigger
                value="analysis"
                className="h-7 rounded-sm border border-transparent px-4 py-0 text-xs data-[state=active]:border-info-border data-[state=active]:bg-info-subtle data-[state=active]:text-info data-[state=active]:shadow-sm text-foreground-muted hover:border-border-subtle hover:bg-app-shell/70 hover:text-foreground-strong"
              >
                Mitas
              </TabsTrigger>
              <TabsTrigger
                value="tedial"
                className="h-7 rounded-sm border border-transparent px-4 py-0 text-xs data-[state=active]:border-info-border data-[state=active]:bg-info-subtle data-[state=active]:text-info data-[state=active]:shadow-sm text-foreground-muted hover:border-border-subtle hover:bg-app-shell/70 hover:text-foreground-strong"
              >
                Tedial
              </TabsTrigger>
              <TabsTrigger
                value="facebank"
                className="h-7 rounded-sm border border-transparent px-4 py-0 text-xs data-[state=active]:border-info-border data-[state=active]:bg-info-subtle data-[state=active]:text-info data-[state=active]:shadow-sm text-foreground-disabled hover:border-border-subtle hover:bg-app-shell/70 hover:text-foreground-muted"
              >
                Banka <Lock className="h-2.5 w-2.5 ml-1.5 opacity-50" />
              </TabsTrigger>
              <TabsTrigger
                value="logs"
                className="h-7 rounded-sm border border-transparent px-4 py-0 text-xs data-[state=active]:border-info-border data-[state=active]:bg-info-subtle data-[state=active]:text-info data-[state=active]:shadow-sm text-foreground-muted hover:border-border-subtle hover:bg-app-shell/70 hover:text-foreground-strong"
              >
                Log
              </TabsTrigger>
            </TabsList>
          )}

          <div className="flex min-w-0 items-center justify-end gap-4">
            <SysInfoBar processStatus={processStatus} />
            <div className="w-px h-4 bg-border-mitas" />
            <div className="flex items-center gap-3 text-xs text-foreground-muted font-medium">
              <span>Yönetici</span>
              <div className="h-7 w-7 bg-surface-elevated rounded-full border border-border-mitas flex items-center justify-center text-[10px] text-foreground-default">
                YÖ
              </div>
              <Button
                type="button"
                variant="ghost"
                size="icon-xs"
                onClick={onSignOut}
                aria-label="Çıkış"
                title="Çıkış"
                className="text-foreground-muted hover:text-foreground-strong"
              >
                <LogOut className="h-3.5 w-3.5" />
              </Button>
            </div>
          </div>
        </div>

        {/* Workspaces */}
        <div className="flex-1 overflow-hidden relative bg-app-shell">
          <TabsContent value="analysis" className="h-full w-full p-0 m-0 outline-none data-[state=inactive]:hidden flex-col flex border-none">
            <AnalysisWorkspace
              asrJob={asrJob}
              uploadError={uploadError}
              selectedFileName={selectedMediaName}
              selectedSourcePath={selectedMediaSourcePath}
              isStartingAsr={isStartingAsr}
              isLiveSttBusy={isLiveSttBusy}
              analysisProfile={analysisProfile}
              isSttPreviewEnabled={false}
              mediaPreviewUrl={mediaPreviewUrl}
              mediaType={mediaType}
              mediaDurationHint={mediaDurationHint}
              playback={playback}
              seekRequest={seekRequest}
              enabledAsrChannels={enabledAsrChannels}
              selectedSegmentIndex={selectedSegmentIndex}
              isTranslatingAll={isTranslatingAll}
              segmentTranslations={segmentTranslations}
              onUpload={handleUpload}
              onStartAsr={handleStartAsr}
              onStartAsrRange={handleStartAsrRange}
              onResetMedia={handleResetMedia}
              generatedDataAvailability={generatedDataAvailability}
              isDeletingGeneratedData={isDeletingGeneratedData}
              onPermanentDeleteGeneratedData={handlePermanentDeleteGeneratedData}
              onLiveSttBusyChange={setIsLiveSttBusy}
              onPlaybackChange={setPlayback}
              onSeek={handleSeek}
              onToggleAsrChannel={handleToggleAsrChannel}
              onSelectSegment={handleSelectSegment}
              onTranslateSegment={handleTranslateSegment}
              onTranslateAllSegments={handleTranslateAllSegments}
              onOpenQueuedMedia={handleOpenQueuedMedia}
            />
          </TabsContent>
          <TabsContent value="tedial" className="h-full w-full p-0 m-0 outline-none data-[state=inactive]:hidden flex-col flex border-none">
            <TedialWorkspace onImportToMitas={handleTedialImport} onOpenJobLog={handleOpenJobLog} />
          </TabsContent>
          <TabsContent value="facebank" className="h-full w-full p-0 m-0 outline-none data-[state=inactive]:hidden flex-col flex border-none">
            <FaceBankWorkspace />
          </TabsContent>
          <TabsContent value="logs" className="h-full w-full p-0 m-0 outline-none data-[state=inactive]:hidden flex-col flex border-none">
            <JobLogWorkspace currentJobId={asrJob?.job_id} onOpenJob={handleOpenHistoricalJob} />
          </TabsContent>
        </div>
      </Tabs>
    </div>
  );
}

export default function App() {
  const [accessState, setAccessState] = useState<'checking' | 'locked' | 'unlocked'>('checking');

  useEffect(() => {
    let cancelled = false;
    fetchMitasAccessSession()
      .then((session) => {
        if (!cancelled) {
          setAccessState(session.authenticated ? 'unlocked' : 'locked');
        }
      })
      .catch(() => {
        if (!cancelled) {
          setAccessState('locked');
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const handleAccessGranted = useCallback(() => {
    setAccessState('unlocked');
  }, []);

  const handleSignOut = useCallback(() => {
    void logoutMitasAccess().finally(() => setAccessState('locked'));
  }, []);

  if (accessState === 'checking') {
    return (
      <main className="flex h-screen w-full items-center justify-center bg-app-shell text-foreground-default font-sans">
        <div className="text-xs font-mono uppercase tracking-wider text-foreground-muted">MITAS</div>
      </main>
    );
  }

  if (accessState === 'locked') {
    return <AccessGate onAccessGranted={handleAccessGranted} />;
  }

  return <AuthenticatedApp onSignOut={handleSignOut} />;
}
