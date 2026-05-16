import { Tabs, TabsList, TabsTrigger, TabsContent } from './components/ui';
import { AnalysisWorkspace } from './components/AnalysisWorkspace';
import { SysInfoBar } from './components/SysInfoBar';
import { FaceBankWorkspace } from './components/FaceBankWorkspace';
import { Archive, Database, MonitorPlay, Lock } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';
import { TedialWorkspace } from './components/TedialWorkspace';
import {
  startTedialAsrJob,
  tedialDurationSeconds,
  type TedialAsrChannelMode,
  type TedialAudioTrack,
  type TedialImportResult,
  type TedialSearchResult,
} from './tedial-api';
import {
  fetchAsrJob,
  fetchRecentAsrJobs,
  defaultAsrChannelState,
  isAsrJobFinished,
  shouldOfferTurkishTranslation,
  startAsrJob,
  translateAsrSegment,
  translateAsrSegments,
  type AnalysisProfile,
  type AsrChannelKey,
  type AsrChannelState,
  type AsrJob,
  type PlaybackState,
  type SeekRequest,
  type SegmentTranslationState,
} from './asr-api';

export default function App() {
  const [activeWorkspace, setActiveWorkspace] = useState<'analysis' | 'tedial' | 'facebank'>('analysis');
  const [asrJob, setAsrJob] = useState<AsrJob | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [selectedMediaName, setSelectedMediaName] = useState<string | null>(null);
  const [selectedTedialItem, setSelectedTedialItem] = useState<TedialSearchResult | null>(null);
  const [selectedTedialAudioTrack, setSelectedTedialAudioTrack] = useState<TedialAudioTrack>(0);
  const [selectedTedialChannelMode, setSelectedTedialChannelMode] = useState<TedialAsrChannelMode>('split');
  const [isStartingAsr, setIsStartingAsr] = useState(false);
  const [mediaPreviewUrl, setMediaPreviewUrl] = useState<string | null>(null);
  const [mediaType, setMediaType] = useState<string | null>(null);
  const [mediaDurationHint, setMediaDurationHint] = useState<number | null>(null);
  const [playback, setPlayback] = useState<PlaybackState>({ currentTime: 0, duration: 0, isPlaying: false });
  const [seekRequest, setSeekRequest] = useState<SeekRequest | null>(null);
  const [selectedSegmentIndex, setSelectedSegmentIndex] = useState<number | null>(null);
  const [analysisProfile, setAnalysisProfile] = useState<AnalysisProfile>('stt');
  const [isSttPreviewEnabled, setIsSttPreviewEnabled] = useState(false);
  const [isLiveSttBusy, setIsLiveSttBusy] = useState(false);
  const [isTranslatingAll, setIsTranslatingAll] = useState(false);
  const [segmentTranslations, setSegmentTranslations] = useState<Record<number, SegmentTranslationState>>({});
  const [enabledAsrChannels, setEnabledAsrChannels] = useState<AsrChannelState>(() => defaultAsrChannelState());

  const prepareSelectedMedia = useCallback((file: File) => {
    setUploadError(null);
    setAsrJob(null);
    setSegmentTranslations({});
    setEnabledAsrChannels(defaultAsrChannelState());
    setSelectedFile(file);
    setSelectedMediaName(file.name);
    setSelectedTedialItem(null);
    setSelectedTedialAudioTrack(0);
    setSelectedTedialChannelMode('split');
    setSelectedSegmentIndex(null);
    setIsLiveSttBusy(false);
    setPlayback({ currentTime: 0, duration: 0, isPlaying: false });
    setSeekRequest(null);
    setMediaType(file.type || null);
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
    setAsrJob(null);
    setSegmentTranslations({});
    setSelectedSegmentIndex(null);
    try {
      const job = await startAsrJob(file);
      setAsrJob(job);
      return job;
    } catch (error) {
      setUploadError(error instanceof Error ? error.message : 'ASR yükleme hatası');
      throw error;
    } finally {
      setIsStartingAsr(false);
    }
  }, []);

  const applyTedialImportResult = useCallback((result: TedialImportResult) => {
    setUploadError(null);
    setAsrJob(result.job);
    setSegmentTranslations({});
    setEnabledAsrChannels(defaultAsrChannelState());
    setSelectedFile(null);
    setSelectedMediaName(result.filename);
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
    setAsrJob(null);
    setSegmentTranslations({});
    setEnabledAsrChannels(defaultAsrChannelState());
    setSelectedSegmentIndex(null);
    try {
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
  }, [applyTedialImportResult, selectedTedialAudioTrack, selectedTedialChannelMode]);

  const handleStartAsr = useCallback(async () => {
    if (!selectedFile && !selectedTedialItem) {
      setUploadError('STT başlatmak için önce medya yükle.');
      return;
    }

    if (analysisProfile !== 'stt') {
      setUploadError('Konuşmadan metne işlemi için önce STT profilini seç.');
      return;
    }
    if (isLiveSttBusy) {
      setUploadError('Canlı STT Preview çalışırken STT Başlat kapalı.');
      return;
    }

    if (selectedFile) {
      await startAsrForFile(selectedFile).catch(() => undefined);
      return;
    }
    if (selectedTedialItem) {
      await startAsrForTedial(selectedTedialItem).catch(() => undefined);
    }
  }, [analysisProfile, isLiveSttBusy, selectedFile, selectedTedialItem, startAsrForFile, startAsrForTedial]);

  const handleTedialImport = useCallback(async (result: TedialImportResult) => {
    setActiveWorkspace('analysis');
    setAnalysisProfile('stt');
    applyTedialImportResult(result);
  }, [applyTedialImportResult]);

  const handleProfileChange = useCallback((profile: AnalysisProfile) => {
    setAnalysisProfile(profile);
    if (profile !== 'stt') {
      setIsSttPreviewEnabled(false);
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
    if (asrJob || selectedFile) {
      return undefined;
    }
    fetchRecentAsrJobs(1)
      .then((jobs) => {
        if (!cancelled && jobs[0]) {
          setAsrJob(jobs[0]);
        }
      })
      .catch(() => {
        // Son job yüklenemezse UI boş açılır; kullanıcı yeni medya yükleyebilir.
      });
    return () => {
      cancelled = true;
    };
  }, [asrJob, selectedFile]);

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

  return (
    <div className="flex flex-col h-screen w-full bg-app-shell text-foreground-default overflow-hidden font-sans selection:bg-info-subtle relative">
      <Tabs value={activeWorkspace} onValueChange={(value) => setActiveWorkspace(value as 'analysis' | 'tedial' | 'facebank')} className="flex flex-col h-full w-full">
        {/* Global Shell Top Bar */}
        <div className="h-14 border-b border-border-subtle bg-app-shell flex items-center justify-between px-4 shrink-0">
          <div className="flex items-center gap-3">
             <div className="h-7 w-7 bg-info-strong rounded-sm flex items-center justify-center shadow-glow-info">
                <MonitorPlay className="h-4 w-4 text-white" />
             </div>
             <div className="flex flex-col justify-center">
               <span className="font-bold text-foreground-strong tracking-widest text-[13px] leading-tight">
                 MITAS <span className="text-foreground-muted font-normal">SYSTEMS</span>
               </span>
               <span className="text-[9px] font-mono text-foreground-muted leading-tight">v0.1 — geliştirme aşaması</span>
             </div>
          </div>

          <TabsList className="bg-transparent h-full border-none p-0 flex gap-4">
            <TabsTrigger
              value="analysis"
              className="h-full rounded-none border-b-[3px] border-transparent data-[state=active]:border-info-strong data-[state=active]:bg-surface/30 data-[state=active]:text-info text-foreground-muted hover:text-foreground-strong hover:bg-surface/50 text-xs px-4"
            >
              <MonitorPlay className="h-3.5 w-3.5 mr-2" />
              Analiz İstasyonu
            </TabsTrigger>
            <TabsTrigger
              value="tedial"
              className="h-full rounded-none border-b-[3px] border-transparent data-[state=active]:border-info-strong data-[state=active]:bg-surface/30 data-[state=active]:text-info text-foreground-muted hover:text-foreground-strong hover:bg-surface/50 text-xs px-4"
            >
              <Archive className="h-3.5 w-3.5 mr-2" />
              Tedial
            </TabsTrigger>
            <TabsTrigger
              value="facebank"
              className="h-full rounded-none border-b-[3px] border-transparent data-[state=active]:border-info-strong data-[state=active]:bg-surface/30 data-[state=active]:text-info text-foreground-disabled hover:text-foreground-muted hover:bg-surface/50 text-xs px-4"
            >
              <Database className="h-3.5 w-3.5 mr-2" />
              Yüz Bankası <Lock className="h-2.5 w-2.5 ml-1.5 opacity-50" />
            </TabsTrigger>
          </TabsList>

          <div className="flex items-center gap-4">
            <SysInfoBar />
            <div className="w-px h-4 bg-border-mitas" />
            <div className="flex items-center gap-3 text-xs text-foreground-muted font-medium">
              <span>Yönetici</span>
              <div className="h-7 w-7 bg-surface-elevated rounded-full border border-border-mitas flex items-center justify-center text-[10px] text-foreground-default">
                YÖ
              </div>
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
              isStartingAsr={isStartingAsr}
              isLiveSttBusy={isLiveSttBusy}
              analysisProfile={analysisProfile}
              isSttPreviewEnabled={isSttPreviewEnabled}
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
              onAnalysisProfileChange={handleProfileChange}
              onSttPreviewEnabledChange={setIsSttPreviewEnabled}
              onLiveSttBusyChange={setIsLiveSttBusy}
              onPlaybackChange={setPlayback}
              onSeek={handleSeek}
              onToggleAsrChannel={handleToggleAsrChannel}
              onSelectSegment={handleSelectSegment}
              onTranslateSegment={handleTranslateSegment}
              onTranslateAllSegments={handleTranslateAllSegments}
            />
          </TabsContent>
          <TabsContent value="tedial" className="h-full w-full p-0 m-0 outline-none data-[state=inactive]:hidden flex-col flex border-none">
            <TedialWorkspace onImportToMitas={handleTedialImport} />
          </TabsContent>
          <TabsContent value="facebank" className="h-full w-full p-0 m-0 outline-none data-[state=inactive]:hidden flex-col flex border-none">
            <FaceBankWorkspace />
          </TabsContent>
        </div>
      </Tabs>

      {/* Absolute Version Text Bottom Right */}
      <div className="absolute bottom-1 right-2 text-[9px] text-foreground-disabled font-mono pointer-events-none z-50 bg-app-shell/80 px-1 rounded">
        MITAS UI v0.2 — ASR odaklı — Yapım aşamasındaki modüller v0.X'te aktif olacak
      </div>
    </div>
  );
}
