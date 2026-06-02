import { Activity, ChevronDown, Download, Info, Lock, Play, RotateCcw, Trash2, UploadCloud } from 'lucide-react';
import { Button, Badge, TabsList, TabsTrigger } from './ui';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from './ui/dropdown-menu';
import { useRef, useState, type ChangeEvent } from 'react';
import {
  analysisProfileLabel,
  formatClock,
  type AnalysisProfile,
  type AsrJob,
  type AsrSegment,
  type ClipGeneratedDataKind,
  type PlaybackState,
} from '../asr-api';

interface HeaderProps {
  asrJob: AsrJob | null;
  uploadError: string | null;
  selectedFileName: string | null;
  selectedSourcePath: string | null;
  isStartingAsr: boolean;
  isLiveSttBusy: boolean;
  analysisProfile: AnalysisProfile;
  rightPanelMode: 'modules' | 'flow';
  playback: PlaybackState;
  mediaResolution: string | null;
  onUpload: (file: File) => void;
  onStartAsr: () => void;
  onResetMedia: () => void;
  generatedDataAvailability: Record<ClipGeneratedDataKind, boolean>;
  isDeletingGeneratedData: boolean;
  onPermanentDeleteGeneratedData: (kind: ClipGeneratedDataKind) => Promise<void>;
  onRightPanelModeChange: (mode: 'modules' | 'flow') => void;
}

export interface HeaderProcessStatus {
  label: string;
  percent: number;
  active: boolean;
}

const STATUS_TEXT: Record<AsrJob['status'], string> = {
  queued: 'Kuyrukta',
  running: 'Çalışıyor',
  done: 'STT/ASR',
  partial: 'Kısmi Sonuç',
  failed: 'Hata',
};

const GENERATED_DATA_OPTIONS: Array<{ kind: ClipGeneratedDataKind; label: string }> = [
  { kind: 'asr', label: 'ASR' },
  { kind: 'ocr', label: 'OCR' },
  { kind: 'face', label: 'Yüz' },
  { kind: 'tag', label: 'Etiket' },
];

export function Header({
  asrJob,
  uploadError,
  selectedFileName,
  selectedSourcePath,
  isStartingAsr,
  isLiveSttBusy,
  analysisProfile,
  rightPanelMode,
  playback,
  mediaResolution,
  onUpload,
  onStartAsr,
  onResetMedia,
  generatedDataAvailability,
  isDeletingGeneratedData,
  onPermanentDeleteGeneratedData,
  onRightPanelModeChange,
}: HeaderProps) {
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [deleteMenuOpen, setDeleteMenuOpen] = useState(false);
  const [pendingDeleteKind, setPendingDeleteKind] = useState<ClipGeneratedDataKind | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const duration = playback.duration || asrJob?.summary?.audio_duration;
  const isAsrBusy = isStartingAsr || isLiveSttBusy || asrJob?.status === 'queued' || asrJob?.status === 'running';
  const progressPercent = Math.max(0, Math.min(100, Math.round(asrJob?.progress_percent ?? (isStartingAsr ? 3 : 0))));
  const elapsedSeconds = asrJob?.elapsed_seconds ?? 0;
  const isSttSelected = true;
  const isMediaReadyForAsr = Boolean(selectedFileName && !asrJob && !isStartingAsr);
  const hasDeletableGeneratedData = Object.values(generatedDataAvailability).some(Boolean);
  const selectedProfileLabel = analysisProfileLabel(analysisProfile);
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
  const modelBadgeVariant: 'secondary' | 'success' | 'warning' | 'danger' | 'outline' =
    uploadError || asrJob?.status === 'failed'
      ? 'danger'
      : asrJob?.status === 'partial'
        ? 'warning'
        : asrJob?.status === 'done'
          ? 'success'
          : isAsrBusy
            ? 'outline'
            : 'secondary';
  const jobMessage = uploadError
    ? `Hata: ${uploadError}`
    : isStartingAsr
      ? 'STT işi başlatılıyor.'
      : isLiveSttBusy
        ? 'Canlı STT Preview player sesini dinliyor.'
      : asrJob?.message || (selectedFileName ? '' : 'Medya yükle; konuşmadan metne işlemi STT seçilince başlar.');

  const handleExport = () => {
    if (!asrJob || !asrJob.segments.length) return;
    const { segments, filename, summary, profile } = asrJob;

    const channelOf = (s: AsrSegment): 'L' | 'R' | null => {
      const v = String(s.channel ?? '').trim().toUpperCase();
      if (v === 'L' || v === 'LEFT' || v === '1' || v === 'KANAL 1') return 'L';
      if (v === 'R' || v === 'RIGHT' || v === '2' || v === 'KANAL 2') return 'R';
      return null;
    };

    const hasL = segments.some(s => channelOf(s) === 'L');
    const hasR = segments.some(s => channelOf(s) === 'R');
    const isStereo = hasL && hasR;

    const sorted = [...segments].sort((a, b) => a.start - b.start);
    const exportedAt = new Date().toLocaleString('tr-TR');
    const durStr = formatClock(summary?.audio_duration);
    const modelStr = summary?.model_name ?? profile ?? '—';
    const sep = '─'.repeat(60);

    const header = [
      `MITAS Transkript — ${filename}`,
      `Süre: ${durStr} | Model: ${modelStr} | Profil: ${profile ?? '—'}`,
      isStereo ? 'Kanal Modu: Stereo (Kanal 1 + Kanal 2 iç içe)' : 'Kanal Modu: Mono',
      `Dışa aktarılma tarihi: ${exportedAt}`,
      sep,
      '',
    ].join('\n');

    const lines = sorted.map(s => {
      const time = `[${formatClock(s.start)} → ${formatClock(s.end)}]`;
      const ch = isStereo ? `  [${channelOf(s) === 'L' ? 'Kanal 1' : channelOf(s) === 'R' ? 'Kanal 2' : '?    '}]` : '';
      return `${time}${ch}  ${s.text.trim()}`;
    });

    const content = header + lines.join('\n');
    const blob = new Blob([content], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${filename.replace(/\.[^/.]+$/, '')}_transkript.txt`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const handleFileChange = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) {
      onUpload(file);
      event.target.value = '';
    }
  };

  const requestPermanentDelete = (kind: ClipGeneratedDataKind) => {
    setDeleteError(null);
    setPendingDeleteKind(kind);
  };

  const confirmPermanentDelete = async () => {
    if (!pendingDeleteKind) return;
    setDeleteError(null);
    try {
      await onPermanentDeleteGeneratedData(pendingDeleteKind);
      setDeleteMenuOpen(false);
      setPendingDeleteKind(null);
    } catch (error) {
      setDeleteError(error instanceof Error ? error.message : 'Kalıcı silme başarısız oldu.');
    }
  };

  return (
    <header className="flex flex-col shrink-0">
      {/* Main Header */}
      <div className="grid grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] items-center gap-4 px-4 py-2 bg-app-shell border-b border-border-subtle">
        <div className="flex min-w-0 items-center gap-6">
          <div className="flex min-w-0 flex-col">
            <div className="flex items-center gap-2">
              <span className="truncate text-sm font-semibold text-foreground-strong">
                {asrJob?.filename || selectedFileName || ''}
              </span>
              {statusText !== 'Medya hazır' && statusText !== 'Medya bekleniyor' && (
                <Badge variant={asrJob?.status === 'failed' ? 'danger' : asrJob?.status === 'partial' ? 'warning' : asrJob?.status === 'done' ? 'success' : isSttSelected ? 'outline' : 'warning'}>
                  {statusText}
                </Badge>
              )}
            </div>
          </div>
        </div>

        <TabsList className="justify-self-center flex h-8 shrink-0 items-center gap-0.5 overflow-hidden rounded-sm border border-border-mitas bg-surface/70 p-0.5 shadow-sm">
          {(
            [
              { value: 'analysis', label: 'Mitas' },
              { value: 'tedial', label: 'Tedial' },
              { value: 'facebank', label: 'Banka', locked: true },
              { value: 'logs', label: 'Log' },
            ] as Array<{ value: 'analysis' | 'tedial' | 'facebank' | 'logs'; label: string; locked?: boolean }>
          ).map(({ value, label, locked }) => (
            <TabsTrigger
              key={value}
              value={value}
              className="inline-flex h-7 items-center justify-center rounded-sm border border-transparent px-3 py-0 text-xs font-bold uppercase tracking-wider transition-colors data-[state=active]:border-info-border data-[state=active]:bg-info-subtle data-[state=active]:text-info data-[state=active]:shadow-sm text-foreground-muted hover:border-border-subtle hover:bg-app-shell/70 hover:text-foreground-strong"
            >
              {label}{locked ? <Lock className="h-2.5 w-2.5 ml-1 opacity-50" /> : null}
            </TabsTrigger>
          ))}
        </TabsList>

        <div className="flex items-center justify-end gap-3">
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
          <Button
            variant="outline"
            size="sm"
            className="gap-2"
            disabled={!asrJob?.segments?.length}
            onClick={handleExport}
          >
            <Download className="h-3.5 w-3.5 text-foreground-muted" />
            Dışa Aktar
          </Button>
          <Button
            variant="outline"
            size="sm"
            className="gap-2"
            disabled={!selectedFileName && !asrJob}
            onClick={onResetMedia}
            title="Ekrandaki klibi ve player durumunu temizle"
          >
            <RotateCcw className="h-3.5 w-3.5 text-foreground-muted" />
            Sıfırla
          </Button>
          <DropdownMenu
            open={deleteMenuOpen}
            onOpenChange={(open) => {
              setDeleteMenuOpen(open);
              if (!open) {
                setPendingDeleteKind(null);
                setDeleteError(null);
              }
            }}
          >
            <DropdownMenuTrigger asChild>
              <Button
                variant="danger"
                size="sm"
                className="gap-2"
                disabled={!hasDeletableGeneratedData || isAsrBusy || isDeletingGeneratedData}
                title={hasDeletableGeneratedData ? 'Üretilmiş modül verisini kalıcı sil' : 'Bu klipte silinecek üretilmiş veri yok'}
              >
                <Trash2 className="h-3.5 w-3.5" />
                {isDeletingGeneratedData ? 'Siliniyor' : 'Kalıcı Sil'}
                <ChevronDown className="h-3 w-3" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-72 rounded-sm border-border-mitas bg-app-shell p-2 text-foreground-default">
              {!pendingDeleteKind ? (
                <>
                  <DropdownMenuLabel className="px-2 py-1 text-[10px] font-semibold uppercase tracking-wider text-danger">
                    Hangi data silinsin?
                  </DropdownMenuLabel>
                  {GENERATED_DATA_OPTIONS.map((option) => {
                    const enabled = generatedDataAvailability[option.kind];
                    return (
                      <DropdownMenuItem
                        key={option.kind}
                        disabled={!enabled || isDeletingGeneratedData}
                        onSelect={(event) => {
                          event.preventDefault();
                          requestPermanentDelete(option.kind);
                        }}
                        className="text-xs focus:bg-danger-subtle focus:text-danger data-[disabled]:text-foreground-disabled"
                      >
                        <span className={enabled ? 'font-semibold' : ''}>{option.label}</span>
                        {!enabled ? <span className="ml-auto text-[10px] text-foreground-muted">veri yok</span> : null}
                      </DropdownMenuItem>
                    );
                  })}
                </>
              ) : (
                <div className="space-y-2 p-1">
                  <div className="rounded-sm border border-danger/40 bg-danger-subtle/35 p-2 text-xs text-danger">
                    <div className="font-semibold">{generatedDataOptionLabel(pendingDeleteKind)} tamamen silmek istediğinize emin misiniz?</div>
                    <div className="mt-1 text-[10px] text-danger/80">Bu işlem üretilmiş veriyi diskteki klipten kaldırır.</div>
                  </div>
                  {deleteError ? <div className="text-[10px] text-danger">{deleteError}</div> : null}
                  <div className="grid grid-cols-2 gap-2">
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      disabled={isDeletingGeneratedData}
                      onClick={() => {
                        setPendingDeleteKind(null);
                        setDeleteError(null);
                      }}
                    >
                      Hayır
                    </Button>
                    <Button
                      type="button"
                      variant="danger"
                      size="sm"
                      disabled={isDeletingGeneratedData}
                      onClick={() => void confirmPermanentDelete()}
                    >
                      Evet, sil
                    </Button>
                  </div>
                </div>
              )}
              <DropdownMenuSeparator className="bg-border-subtle" />
              <div className="px-2 pb-1 text-[10px] text-foreground-muted">
                Sadece veri bulunan modüller aktifleşir.
              </div>
            </DropdownMenuContent>
          </DropdownMenu>
          <Button
            size="sm"
            className="gap-2 bg-info-strong hover:bg-info text-white border-transparent"
            disabled={!selectedFileName || !isSttSelected || isAsrBusy}
            onClick={onStartAsr}
            title={isLiveSttBusy ? 'Canlı STT Preview çalışırken başlatılmaz' : 'İşlemi başlat'}
          >
            <Play className="h-3.5 w-3.5" />
            {isStartingAsr ? 'Başlatılıyor' : asrJob ? 'Tekrar Başlat' : 'Başlat'}
          </Button>
        </div>
      </div>

      {/* Models Bar */}
      <div className="grid grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] items-center gap-4 px-4 py-1.5 bg-app-shell border-b border-border-subtle/50">
        <div className="flex min-w-0 items-center gap-2">
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="outline" size="xs" className="gap-1.5 text-foreground-muted">
                <Info className="h-3 w-3" />
                Bilgi
                <ChevronDown className="h-3 w-3" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="start" className="w-96 rounded-sm border-border-mitas bg-app-shell p-2 text-foreground-default">
              <div className="rounded-sm border border-border-subtle bg-surface/35">
                <div className="border-b border-border-subtle px-2 py-1.5 text-[10px] font-semibold uppercase tracking-wider text-foreground-strong">
                  Klip Bilgisi
                </div>
                <div className="p-2">
                  <ModuleInfoRow label="Dosya" value={asrJob?.filename || selectedFileName || '-'} />
                  <ModuleInfoRow label="Kaynak" value={asrJob?.original_source_path || selectedSourcePath || asrJob?.input_path || asrJob?.summary?.input_path || '-'} />
                  <ModuleInfoRow label="Durum" value={asrJob?.status || (selectedFileName ? 'medya hazır' : 'bekleniyor')} />
                  <ModuleInfoRow label="Çözünürlük" value={mediaResolution || '-'} />
                  <ModuleInfoRow label="Süre" value={formatClock(duration)} />
                  <ModuleInfoRow label="Profil" value={selectedProfileLabel} />
                  <ModuleInfoRow label="Temiz segment" value={String(asrJob?.summary?.clean_segments ?? asrJob?.segments?.length ?? 0)} />
                </div>
              </div>

              <div className="mt-2 rounded-sm border border-border-subtle bg-surface/25">
                <div className="border-b border-border-subtle px-2 py-1.5 text-[10px] font-semibold uppercase tracking-wider text-foreground-strong">
                  Kanıt Özeti
                </div>
                <div className="p-2">
                  <ModuleInfoRow label="ASR" value={asrJob ? `${asrJob.segments.length} transcript segmenti` : '-'} />
                  <ModuleInfoRow label="VAD" value={asrJob ? `${asrJob.summary?.raw_segments ?? 0} ham segment` : '-'} />
                  <ModuleInfoRow label="Güven" value={asrJob?.summary?.safety?.safe === false ? 'kontrol gerekli' : asrJob ? 'normal' : '-'} />
                </div>
              </div>
            </DropdownMenuContent>
          </DropdownMenu>
          <Badge variant={modelBadgeVariant}>STT/ASR: {modelName}</Badge>
          <div className="flex items-center gap-1.5 text-[10px] font-mono ml-1">
            <Activity className={`h-3 w-3 shrink-0 ${asrJob?.status === 'running' ? 'animate-pulse text-info' : uploadError || asrJob?.status === 'failed' ? 'text-danger' : 'text-foreground-disabled'}`} />
            <span className={`max-w-[260px] truncate ${uploadError || asrJob?.status === 'failed' ? 'text-danger' : isMediaReadyForAsr ? 'font-semibold text-info' : 'text-foreground-muted'}`}>
              {jobMessage}
            </span>
            {asrJob && (
              <div className="flex items-center gap-1.5 shrink-0" title={formatElapsedShort(elapsedSeconds)}>
                <div className="w-14 h-1 bg-surface-elevated rounded-full overflow-hidden shrink-0">
                  <div
                    className={`h-full rounded-full transition-[width] duration-500 ${uploadError || asrJob.status === 'failed' ? 'bg-danger-strong' : 'bg-info-strong'}`}
                    style={{ width: `${progressPercent}%` }}
                  />
                </div>
              </div>
            )}
          </div>
        </div>

        <div className="justify-self-center flex items-center gap-3">
          <span className="font-mono text-info font-bold text-lg tracking-wider drop-shadow-glow-info tabular-nums">
            {formatClock(playback.currentTime)} / {formatClock(duration)}
          </span>
        </div>

        <div className="justify-self-end flex h-9 shrink-0 items-center justify-center gap-1 overflow-hidden rounded-sm border border-border-mitas bg-surface/70 p-1 shadow-sm">
          <button
            type="button"
            onClick={() => onRightPanelModeChange('modules')}
            className={`inline-flex h-7 items-center justify-center rounded-sm border px-4 py-0 text-sm font-bold uppercase tracking-wider transition-colors ${
              rightPanelMode === 'modules'
                ? 'border-info-border bg-info-subtle text-info shadow-sm'
                : 'border-transparent text-foreground-muted hover:border-border-subtle hover:bg-app-shell/70 hover:text-foreground-strong'
            }`}
          >
            Modüller
          </button>
          <button
            type="button"
            onClick={() => onRightPanelModeChange('flow')}
            className={`inline-flex h-7 items-center justify-center rounded-sm border px-4 py-0 text-sm font-bold uppercase tracking-wider transition-colors ${
              rightPanelMode === 'flow'
                ? 'border-info-border bg-info-subtle text-info shadow-sm'
                : 'border-transparent text-foreground-muted hover:border-border-subtle hover:bg-app-shell/70 hover:text-foreground-strong'
            }`}
          >
            Akış
          </button>
        </div>
      </div>
    </header>
  );
}

function ModuleInfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="grid grid-cols-[92px_minmax(0,1fr)] gap-2 py-1 text-[11px]">
      <span className="truncate uppercase tracking-wider text-foreground-muted">{label}</span>
      <span className="min-w-0 truncate font-mono text-[10px] text-foreground-default" title={value}>
        {value || '-'}
      </span>
    </div>
  );
}

function generatedDataOptionLabel(kind: ClipGeneratedDataKind): string {
  return GENERATED_DATA_OPTIONS.find((option) => option.kind === kind)?.label ?? kind.toUpperCase();
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

