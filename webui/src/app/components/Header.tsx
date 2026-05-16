import { Activity, Download, Eye, LayoutGrid, ListTodo, Play, UploadCloud } from 'lucide-react';
import { Button, Badge } from './ui';
import { Checkbox } from './ui/checkbox';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select';
import { useRef, type ChangeEvent } from 'react';
import {
  ANALYSIS_PROFILE_OPTIONS,
  analysisProfileLabel,
  formatClock,
  type AnalysisProfile,
  type AsrJob,
  type PlaybackState,
} from '../asr-api';

interface HeaderProps {
  asrJob: AsrJob | null;
  uploadError: string | null;
  selectedFileName: string | null;
  isStartingAsr: boolean;
  isLiveSttBusy: boolean;
  analysisProfile: AnalysisProfile;
  isSttPreviewEnabled: boolean;
  playback: PlaybackState;
  onUpload: (file: File) => void;
  onStartAsr: () => void;
  onAnalysisProfileChange: (profile: AnalysisProfile) => void;
  onSttPreviewEnabledChange: (enabled: boolean) => void;
}

const STATUS_TEXT: Record<AsrJob['status'], string> = {
  queued: 'Kuyrukta',
  running: 'Çalışıyor',
  done: 'Tamamlandı',
  partial: 'Kısmi Sonuç',
  failed: 'Hata',
};

export function Header({
  asrJob,
  uploadError,
  selectedFileName,
  isStartingAsr,
  isLiveSttBusy,
  analysisProfile,
  isSttPreviewEnabled,
  playback,
  onUpload,
  onStartAsr,
  onAnalysisProfileChange,
  onSttPreviewEnabledChange,
}: HeaderProps) {
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const duration = playback.duration || asrJob?.summary?.audio_duration;
  const isAsrBusy = isStartingAsr || isLiveSttBusy || asrJob?.status === 'queued' || asrJob?.status === 'running';
  const progressPercent = Math.max(0, Math.min(100, Math.round(asrJob?.progress_percent ?? (isStartingAsr ? 3 : 0))));
  const elapsedSeconds = asrJob?.elapsed_seconds ?? 0;
  const isSttSelected = analysisProfile === 'stt';
  const isMediaReadyForAsr = Boolean(selectedFileName && !asrJob && !isStartingAsr);
  const selectedProfileLabel = analysisProfileLabel(analysisProfile);
  const mediaReadyText = selectedFileName
    ? isSttSelected
      ? `${selectedFileName} STT için hazır`
      : `${selectedFileName} yüklendi - STT için profil değiştir`
    : null;
  const statusText = isStartingAsr
    ? 'STT başlatılıyor'
    : isLiveSttBusy
      ? 'Canlı STT'
    : asrJob
      ? STATUS_TEXT[asrJob.status]
      : selectedFileName
        ? 'Medya hazır'
        : 'Medya bekleniyor';
  const modelName = asrJob?.summary?.model_name || (isAsrBusy ? 'yükleniyor' : 'başlatılmadı');
  const processMeta = asrJob
    ? `${progressPercent}% · ${formatElapsedShort(elapsedSeconds)}`
    : isStartingAsr
      ? '3% · başlıyor'
      : null;
  const jobMessage = uploadError
    ? `Hata: ${uploadError}`
    : isStartingAsr
      ? 'STT işi başlatılıyor.'
      : isLiveSttBusy
        ? 'Canlı STT Preview player sesini dinliyor.'
      : asrJob?.message || (mediaReadyText ?? 'Medya yükle; konuşmadan metne işlemi STT seçilince başlar.');

  const handleFileChange = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) {
      onUpload(file);
      event.target.value = '';
    }
  };

  return (
    <header className="flex flex-col shrink-0">
      {/* Main Header */}
      <div className="flex items-center justify-between px-4 py-2 bg-app-shell border-b border-border-subtle">
        <div className="flex items-center gap-6">
          <div className="flex items-center gap-2 text-foreground-strong">
            <LayoutGrid className="h-4 w-4 text-info-strong" />
            <h1 className="text-base font-bold tracking-tight uppercase">Analiz İstasyonu</h1>
          </div>

          <div className="h-4 w-px bg-border-subtle"></div>

          <div className="flex flex-col">
            <div className="flex items-center gap-2">
              <span className="text-sm font-semibold text-foreground-strong">
                {asrJob?.filename || selectedFileName || 'Gerçek medya yok'}
              </span>
              <Badge variant={asrJob?.status === 'failed' ? 'danger' : asrJob?.status === 'done' ? 'success' : isSttSelected ? 'outline' : 'warning'}>
                {statusText}
              </Badge>
              {processMeta ? (
                <Badge variant={asrJob?.status === 'failed' ? 'danger' : asrJob?.status === 'done' || asrJob?.status === 'partial' ? 'success' : 'secondary'}>
                  {processMeta}
                </Badge>
              ) : null}
            </div>
            {isMediaReadyForAsr && mediaReadyText && (
              <div className="mt-1 inline-flex items-center gap-2 rounded-sm border border-info-border bg-info-subtle px-2 py-1 text-[11px] font-semibold text-info">
                <span className="h-1.5 w-1.5 rounded-full bg-info-strong"></span>
                <span>{mediaReadyText}</span>
              </div>
            )}
          </div>
        </div>

        <div className="flex flex-col items-center">
          <div className="text-2xl font-mono text-info font-bold tracking-wider drop-shadow-glow-info">
            {formatClock(playback.currentTime)} / {formatClock(duration)}
          </div>
          <div className="mt-0.5 text-[9px] font-mono uppercase tracking-wider text-foreground-muted">
            İmleç / Toplam Süre
          </div>
        </div>

        <div className="flex items-center gap-3">
          <input
            ref={fileInputRef}
            type="file"
            className="hidden"
            accept="audio/*,video/*,.wav,.mp3,.mp4,.m4a,.mkv,.flac,.aac,.ogg"
            onChange={handleFileChange}
          />
          <Button
            variant="outline"
            size="sm"
            className="gap-2"
            disabled={isAsrBusy}
            onClick={() => fileInputRef.current?.click()}
          >
            <UploadCloud className="h-3.5 w-3.5 text-foreground-muted" />
            Yükle
          </Button>
          <Button variant="outline" size="sm" className="gap-2 text-warning border-warning-border hover:bg-warning-subtle" disabled>
            <ListTodo className="h-3.5 w-3.5" />
            Uyarılar ({asrJob?.summary?.quality_drops ?? 0})
          </Button>
          <Button variant="outline" size="sm" className="gap-2" disabled={!asrJob?.transcript}>
            <Download className="h-3.5 w-3.5 text-foreground-muted" />
            Dışa Aktar
          </Button>
          <Button
            size="sm"
            className="gap-2 bg-info-strong hover:bg-info text-white border-transparent"
            disabled={!selectedFileName || !isSttSelected || isAsrBusy}
            onClick={onStartAsr}
            title={isLiveSttBusy ? 'Canlı STT Preview çalışırken batch STT başlatılmaz' : isSttSelected ? 'STT işlemini başlat' : 'Konuşmadan metne için STT profilini seç'}
          >
            <Play className="h-3.5 w-3.5" />
            {isStartingAsr ? 'Başlatılıyor' : asrJob ? 'STT Tekrar' : 'STT Başlat'}
          </Button>
        </div>
      </div>

      {/* Profile / STT controls */}
      <div className="flex items-center justify-between gap-4 px-4 py-2 bg-surface/80 border-b border-border-subtle text-xs">
        <div className="flex items-center gap-3 min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-[10px] uppercase tracking-wider text-foreground-muted font-semibold">Profil</span>
            <Select value={analysisProfile} onValueChange={(value) => onAnalysisProfileChange(value as AnalysisProfile)}>
              <SelectTrigger
                size="sm"
                className="h-7 w-[220px] rounded-sm border-border-mitas bg-app-shell/80 px-2 py-1 text-xs text-foreground-default"
                title="İşlem profilini seç"
              >
                <SelectValue />
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

          <div className="h-4 w-px bg-border-subtle"></div>

          <label
            className={`inline-flex items-center gap-2 rounded-sm border px-2 py-1 ${
              isSttSelected
                ? 'border-info-border bg-info-subtle text-foreground-default'
                : 'border-border-subtle bg-app-shell/60 text-foreground-disabled'
            }`}
            title={isSttSelected ? 'Anlık çeviri/show önizlemesini aç' : 'Preview sadece STT profilinde açılır'}
          >
            <Checkbox
              checked={isSttPreviewEnabled}
              disabled={!isSttSelected}
              onCheckedChange={(checked) => onSttPreviewEnabledChange(checked === true)}
              className="border-info-border data-[state=checked]:bg-info-strong data-[state=checked]:border-info-strong"
            />
            <Eye className="h-3.5 w-3.5" />
            <span className="text-[11px] font-semibold">Preview</span>
            <span className="text-[10px] text-foreground-muted">Anlık çeviri</span>
          </label>
        </div>

        <div className="truncate text-[11px] text-foreground-muted">
          {isSttSelected
            ? 'STT seçili: konuşmadan metne işlemi ve preview akışı kullanılabilir.'
            : `${selectedProfileLabel} seçili: bu profil ileride ilgili modül akışını açacak; konuşmadan metne için STT seç.`}
        </div>
      </div>

      {/* Job Status Bar */}
      <div className="flex items-center justify-between px-4 py-1.5 bg-surface border-b border-border-subtle text-[11px] font-mono">
        <div className={`flex items-center gap-2 ${uploadError || asrJob?.status === 'failed' ? 'text-danger' : 'text-info'}`}>
          <Activity className={`h-3 w-3 ${asrJob?.status === 'running' ? 'animate-pulse' : ''}`} />
          <span className={isMediaReadyForAsr ? 'font-semibold text-info' : ''}>{jobMessage}</span>
        </div>
        <div className="flex-1 max-w-md mx-4 h-1.5 bg-surface-elevated rounded-full overflow-hidden">
          <div
            className={`h-full ${uploadError || asrJob?.status === 'failed' ? 'bg-danger-strong' : 'bg-info-strong'} rounded-full transition-[width] duration-500`}
            style={{ width: `${progressPercent}%` }}
          ></div>
        </div>
        <div className="text-foreground-muted whitespace-nowrap">
          {asrJob ? `ASR: ${progressPercent}% · ${formatElapsedLong(elapsedSeconds)}` : `Aktif profil: ${selectedProfileLabel}`}
        </div>
      </div>

      {/* Models Bar */}
      <div className="flex items-center justify-between px-4 py-1.5 bg-app-shell border-b border-border-subtle/50">
        <div className="flex items-center gap-4 text-xs font-mono text-foreground-muted">
          <span>SÜRE: {formatClock(duration)}</span>
          <span>İŞLEM: {selectedProfileLabel}</span>
          <span>ASR MOTOR: {asrJob?.profile || 'fast_with_fallback'}</span>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-[10px] uppercase font-mono text-foreground-muted mr-2">Modeller:</span>
          <Badge variant="success">STT/ASR: {modelName}</Badge>
          <Badge variant="secondary" className="opacity-50 text-foreground-muted" title="Yapım Aşamasında">FACE: —</Badge>
          <Badge variant="secondary" className="opacity-50 text-foreground-muted" title="Yapım Aşamasında">OCR: —</Badge>
          <Badge variant="secondary" className="opacity-50 text-foreground-muted" title="Yapım Aşamasında">TAG: —</Badge>
          <Badge variant="secondary" className="opacity-50 text-foreground-muted" title="Yapım Aşamasında">LOGO: —</Badge>
        </div>
      </div>
    </header>
  );
}

function formatElapsedShort(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds <= 0) {
    return '00:00';
  }
  const total = Math.floor(seconds);
  const minutes = Math.floor(total / 60);
  const secs = total % 60;
  return `${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
}

function formatElapsedLong(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds <= 0) {
    return '0 dk';
  }
  const total = Math.floor(seconds);
  const minutes = Math.floor(total / 60);
  const secs = total % 60;
  if (minutes <= 0) {
    return `${secs} sn`;
  }
  return `${minutes} dk ${secs.toString().padStart(2, '0')} sn`;
}
