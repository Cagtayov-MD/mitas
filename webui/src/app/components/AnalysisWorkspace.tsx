import { Header } from './Header';
import { VideoPlayer } from './VideoPlayer';
import { Timeline } from './Timeline';
import { Sidebar } from './Sidebar';
import type { AnalysisProfile, AsrChannelKey, AsrChannelState, AsrJob, PlaybackState, SeekRequest, SegmentTranslationState } from '../asr-api';
import { useLiveSttPreview } from '../live-stt-preview';
import { useCallback, useState } from 'react';

interface AnalysisWorkspaceProps {
  asrJob: AsrJob | null;
  uploadError: string | null;
  selectedFileName: string | null;
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
  onAnalysisProfileChange: (profile: AnalysisProfile) => void;
  onSttPreviewEnabledChange: (enabled: boolean) => void;
  onLiveSttBusyChange: (isBusy: boolean) => void;
  onPlaybackChange: (playback: PlaybackState) => void;
  onSeek: (time: number) => void;
  onToggleAsrChannel: (channel: AsrChannelKey) => void;
  onSelectSegment: (index: number) => void;
  onTranslateSegment: (index: number) => void;
  onTranslateAllSegments: () => void;
}

export function AnalysisWorkspace({
  asrJob,
  uploadError,
  selectedFileName,
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
  onAnalysisProfileChange,
  onSttPreviewEnabledChange,
  onLiveSttBusyChange,
  onPlaybackChange,
  onSeek,
  onToggleAsrChannel,
  onSelectSegment,
  onTranslateSegment,
  onTranslateAllSegments,
}: AnalysisWorkspaceProps) {
  const [mediaElement, setMediaElement] = useState<HTMLMediaElement | null>(null);
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

  return (
    <div className="flex flex-col h-full w-full">
      <Header
        asrJob={asrJob}
        uploadError={uploadError}
        selectedFileName={selectedFileName}
        isStartingAsr={isStartingAsr}
        isLiveSttBusy={isLiveSttBusy}
        analysisProfile={analysisProfile}
        isSttPreviewEnabled={isSttPreviewEnabled}
        playback={playback}
        onUpload={onUpload}
        onStartAsr={onStartAsr}
        onAnalysisProfileChange={onAnalysisProfileChange}
        onSttPreviewEnabledChange={onSttPreviewEnabledChange}
      />
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
          />
          <Timeline
            asrJob={asrJob}
            playback={playback}
            enabledAsrChannels={enabledAsrChannels}
            selectedSegmentIndex={selectedSegmentIndex}
            onSeek={onSeek}
            onToggleAsrChannel={onToggleAsrChannel}
            onSelectSegment={onSelectSegment}
          />
        </div>
        <Sidebar
          asrJob={asrJob}
          uploadError={uploadError}
          hasMedia={Boolean(mediaPreviewUrl)}
          isSttPreviewEnabled={isLivePreviewEnabled}
          livePreview={livePreview}
          enabledAsrChannels={enabledAsrChannels}
          selectedSegmentIndex={selectedSegmentIndex}
          isTranslatingAll={isTranslatingAll}
          segmentTranslations={segmentTranslations}
          onSelectSegment={onSelectSegment}
          onTranslateSegment={onTranslateSegment}
          onTranslateAllSegments={onTranslateAllSegments}
        />
      </div>
    </div>
  );
}
