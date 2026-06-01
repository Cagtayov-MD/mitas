import { Header } from './Header';
import { VideoPlayer } from './VideoPlayer';
import { Timeline } from './Timeline';
import { Sidebar } from './Sidebar';
import type { AnalysisProfile, AsrChannelKey, AsrChannelState, AsrJob, ClipGeneratedDataKind, PlaybackState, SeekRequest, SegmentTranslationState } from '../asr-api';
import type { FlowQueuedMediaRequest } from './FlowQueuePanel';
import { formatClock } from '../asr-api';
import { useLiveSttPreview } from '../live-stt-preview';
import { useCallback, useEffect, useState } from 'react';
import { AlertTriangle, X } from 'lucide-react';

interface AnalysisWorkspaceProps {
  asrJob: AsrJob | null;
  uploadError: string | null;
  selectedFileName: string | null;
  selectedSourcePath: string | null;
  isStartingAsr: boolean;
  isLiveSttBusy: boolean;
  analysisProfile: AnalysisProfile;
  isSttPreviewEnabled: boolean;
  mediaPreviewUrl: string | null;
  mediaType: string | null;
  mediaDurationHint: number | null;
  playback: PlaybackState;
  seekRequest: SeekRequest | null;
  enabledAsrChannels: AsrChannelState;
  selectedSegmentIndex: number | null;
  isTranslatingAll: boolean;
  segmentTranslations: Record<number, SegmentTranslationState>;
  onUpload: (file: File) => void;
  onStartAsr: () => void;
  onStartAsrRange: (from: number, to: number) => void;
  onResetMedia: () => void;
  generatedDataAvailability: Record<ClipGeneratedDataKind, boolean>;
  isDeletingGeneratedData: boolean;
  onPermanentDeleteGeneratedData: (kind: ClipGeneratedDataKind) => Promise<void>;
  onLiveSttBusyChange: (isBusy: boolean) => void;
  onPlaybackChange: (playback: PlaybackState) => void;
  onSeek: (time: number) => void;
  onToggleAsrChannel: (channel: AsrChannelKey) => void;
  onSelectSegment: (index: number) => void;
  onTranslateSegment: (index: number) => void;
  onTranslateAllSegments: () => void;
  onOpenQueuedMedia: (request: FlowQueuedMediaRequest) => void;
}

export function AnalysisWorkspace({
  asrJob,
  uploadError,
  selectedFileName,
  selectedSourcePath,
  isStartingAsr,
  isLiveSttBusy,
  analysisProfile,
  isSttPreviewEnabled,
  mediaPreviewUrl,
  mediaType,
  mediaDurationHint,
  playback,
  seekRequest,
  enabledAsrChannels,
  selectedSegmentIndex,
  isTranslatingAll,
  segmentTranslations,
  onUpload,
  onStartAsr,
  onStartAsrRange,
  onResetMedia,
  generatedDataAvailability,
  isDeletingGeneratedData,
  onPermanentDeleteGeneratedData,
  onLiveSttBusyChange,
  onPlaybackChange,
  onSeek,
  onToggleAsrChannel,
  onSelectSegment,
  onTranslateSegment,
  onTranslateAllSegments,
  onOpenQueuedMedia,
}: AnalysisWorkspaceProps) {
  const [mediaElement, setMediaElement] = useState<HTMLMediaElement | null>(null);
  const [mediaResolution, setMediaResolution] = useState<string | null>(null);
  const [inPoint, setInPoint] = useState<number | null>(null);
  const [outPoint, setOutPoint] = useState<number | null>(null);
  const [dismissedWarningJobId, setDismissedWarningJobId] = useState<string | null>(null);
  const [rightPanelMode, setRightPanelMode] = useState<'modules' | 'flow'>('modules');
  const isLivePreviewEnabled = isSttPreviewEnabled && analysisProfile === 'stt' && Boolean(mediaPreviewUrl);
  const livePreview = useLiveSttPreview({
    enabled: isLivePreviewEnabled,
    mediaElement,
    mediaKey: mediaPreviewUrl,
    playback,
    seekRequest,
    onBusyChange: onLiveSttBusyChange,
  });
  const handleMediaElementChange = useCallback((element: HTMLMediaElement | null) => {
    setMediaElement(element);
  }, []);

  useEffect(() => {
    setMediaResolution(null);
  }, [mediaPreviewUrl]);

  const handleTranslateRange = useCallback((from: number, to: number) => {
    if (!asrJob) return;
    asrJob.segments.forEach((seg, idx) => {
      if (seg.start < to && seg.end > from) {
        onTranslateSegment(idx);
      }
    });
  }, [asrJob, onTranslateSegment]);

  const handleSetInPoint = useCallback((t: number | null) => setInPoint(t), []);
  const handleSetOutPoint = useCallback((t: number | null) => setOutPoint(t), []);

  const uncoveredRanges = asrJob?.summary?.safety?.diagnostics?.uncovered_vad_ranges ?? [];
  const isPartial = asrJob?.status === 'partial';
  const showPartialWarning = isPartial && dismissedWarningJobId !== asrJob?.job_id;

  return (
    <div className="flex flex-col h-full w-full">
      <Header
        asrJob={asrJob}
        uploadError={uploadError}
        selectedFileName={selectedFileName}
        selectedSourcePath={selectedSourcePath}
        isStartingAsr={isStartingAsr}
        isLiveSttBusy={isLiveSttBusy}
        analysisProfile={analysisProfile}
        rightPanelMode={rightPanelMode}
        playback={playback}
        mediaResolution={mediaResolution}
        onUpload={onUpload}
        onStartAsr={onStartAsr}
        onResetMedia={onResetMedia}
        generatedDataAvailability={generatedDataAvailability}
        isDeletingGeneratedData={isDeletingGeneratedData}
        onPermanentDeleteGeneratedData={onPermanentDeleteGeneratedData}
        onRightPanelModeChange={setRightPanelMode}
      />
      {showPartialWarning && (
        <div className="shrink-0 flex items-start gap-2 px-4 py-2 bg-warning-subtle border-b border-warning-border text-warning text-[11px] font-semibold">
          <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-warning-strong" />
          <div className="flex flex-col gap-0.5 min-w-0">
            {uncoveredRanges.length > 0 ? (
              <>
                <span>
                  {uncoveredRanges.length === 1
                    ? '1 bölgede konuşma algılandı ama transkript edilemedi:'
                    : `${uncoveredRanges.length} bölgede konuşma algılandı ama transkript edilemedi:`}
                </span>
                <span className="font-mono text-[10px] text-warning-strong">
                  {uncoveredRanges.map((r, i) => (
                    <span key={i}>
                      {i > 0 ? ' · ' : ''}
                      {formatClock(r.start)}–{formatClock(r.end)} (≈{Math.round(r.speech_seconds)} sn konuşma)
                    </span>
                  ))}
                </span>
              </>
            ) : (
              <span>
                Transkript eksik — bazı konuşma bölgeleri kapsanamamış olabilir.
              </span>
            )}
            {asrJob?.summary?.safety?.failure_reason && (
              <span className="text-[10px] text-warning/70 font-mono">Sebep: {asrJob.summary.safety.failure_reason}</span>
            )}
          </div>
          <button
            type="button"
            className="ml-auto -mr-1 flex h-6 w-6 shrink-0 items-center justify-center rounded-sm text-warning hover:bg-warning-subtle hover:text-warning-strong focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-warning-strong"
            title="Uyarıyı kapat"
            aria-label="Uyarıyı kapat"
            onClick={() => setDismissedWarningJobId(asrJob?.job_id ?? null)}
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      )}
      <div className="flex flex-1 overflow-hidden">
        <div className="flex flex-col flex-1 min-w-0">
          <VideoPlayer
            asrJob={asrJob}
            selectedFileName={selectedFileName}
            analysisProfile={analysisProfile}
            isSttPreviewEnabled={isSttPreviewEnabled}
            mediaPreviewUrl={mediaPreviewUrl}
            mediaType={mediaType}
            mediaDurationHint={mediaDurationHint}
            playback={playback}
            seekRequest={seekRequest}
            enabledAsrChannels={enabledAsrChannels}
            onPlaybackChange={onPlaybackChange}
            onSeek={onSeek}
            onMediaElementChange={handleMediaElementChange}
            onMediaResolutionChange={setMediaResolution}
          />
          <Timeline
            asrJob={asrJob}
            playback={playback}
            enabledAsrChannels={enabledAsrChannels}
            selectedSegmentIndex={selectedSegmentIndex}
            inPoint={inPoint}
            outPoint={outPoint}
            onSeek={onSeek}
            onSetInPoint={handleSetInPoint}
            onSetOutPoint={handleSetOutPoint}
            onToggleAsrChannel={onToggleAsrChannel}
            onSelectSegment={onSelectSegment}
            onTranslateRange={handleTranslateRange}
            onStartAsrRange={onStartAsrRange}
            isStartingAsrRange={isStartingAsr}
          />
        </div>
        <Sidebar
          asrJob={asrJob}
          hasMedia={Boolean(mediaPreviewUrl)}
          isSttPreviewEnabled={isLivePreviewEnabled}
          livePreview={livePreview}
          enabledAsrChannels={enabledAsrChannels}
          selectedSegmentIndex={selectedSegmentIndex}
          isTranslatingAll={isTranslatingAll}
          segmentTranslations={segmentTranslations}
          panelMode={rightPanelMode}
          onSelectSegment={onSelectSegment}
          onTranslateSegment={onTranslateSegment}
          onTranslateAllSegments={onTranslateAllSegments}
          onOpenQueuedMedia={onOpenQueuedMedia}
        />
      </div>
    </div>
  );
}
