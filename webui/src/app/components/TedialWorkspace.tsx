import { ChevronLeft, ChevronRight, Clock3, Database, DownloadCloud, FileText, LogIn, Maximize, Pause, Play, RefreshCw, Search, SkipBack, SkipForward, SplitSquareHorizontal, Square, Volume2, VolumeX, XCircle } from 'lucide-react';
import { useEffect, useMemo, useRef, useState, type PointerEvent } from 'react';
import * as dashjs from 'dashjs';
import { Badge, Button, ScrollArea } from './ui';
import { fetchRecentAsrJobs, formatClock, type AsrJob } from '../asr-api';
import {
  autoLoginTedialSession,
  DEFAULT_TEDIAL_CHANNEL_MODE,
  fetchTedialSession,
  forgetTedialSession,
  getRememberedTedialJobIds,
  openTedialMediaInMitas,
  searchTedial,
  startTedialSession,
  tedialDurationSeconds,
  tedialKeyframeProxyUrl,
  tedialManifestUrl,
  type TedialAsrChannelMode,
  type TedialAudioTrack,
  type TedialMediaImportResult,
  type TedialSearchResult,
  type TedialSession,
} from '../tedial-api';

interface TedialWorkspaceProps {
  onImportToMitas: (result: TedialMediaImportResult) => Promise<void>;
  onOpenJobLog: (job: AsrJob) => void;
}

const STATUS_LABEL: Record<TedialSession['status'], string> = {
  disconnected: 'Bağlı değil',
  connecting: 'Bağlanıyor',
  connected: 'Bağlı',
  expired: 'Süresi doldu',
  error: 'Hata',
};

export function TedialWorkspace({ onImportToMitas, onOpenJobLog }: TedialWorkspaceProps) {
  const [session, setSession] = useState<TedialSession | null>(null);
  const [remember, setRemember] = useState(true);
  const [query, setQuery] = useState('34-*');
  const [items, setItems] = useState<TedialSearchResult[]>([]);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [message, setMessage] = useState('Hazır');
  const [isSearching, setIsSearching] = useState(false);
  const [isImporting, setIsImporting] = useState(false);
  const [audioTrack, setAudioTrack] = useState<TedialAudioTrack>(0);
  const [channelMode, setChannelMode] = useState<TedialAsrChannelMode>(DEFAULT_TEDIAL_CHANNEL_MODE);
  const [recentTedialJobs, setRecentTedialJobs] = useState<AsrJob[]>([]);

  const selected = items[selectedIndex] ?? null;
  const keyframeUrl = useMemo(() => selected ? tedialKeyframeProxyUrl(selected) : null, [selected]);
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const previewFrameRef = useRef<HTMLDivElement | null>(null);
  const playerRef = useRef<dashjs.MediaPlayerClass | null>(null);
  const previewManifestUrl = useMemo(() => (selected ? tedialManifestUrl(selected, audioTrack) : ''), [selected, audioTrack]);
  const [previewPlaying, setPreviewPlaying] = useState(false);
  const [previewMuted, setPreviewMuted] = useState(false);
  const [previewTime, setPreviewTime] = useState(0);
  const [previewDuration, setPreviewDuration] = useState(0);
  // DASH süreyi geç/eksik (Infinity/NaN) verebiliyor; o durumda Tedial meta süresini yedek al.
  const previewKnownDuration = previewDuration > 0 ? previewDuration : (selected ? (tedialDurationSeconds(selected) ?? 0) : 0);
  const previewProgress = previewKnownDuration > 0 ? Math.max(0, Math.min(100, (previewTime / previewKnownDuration) * 100)) : 0;

  const seekPreviewTo = (time: number) => {
    const v = videoRef.current;
    if (!v) return;
    const target = previewKnownDuration > 0 ? Math.max(0, Math.min(previewKnownDuration, time)) : Math.max(0, time);
    v.currentTime = target;
    setPreviewTime(target);
  };
  const togglePreviewPlay = () => {
    const v = videoRef.current;
    if (!v) return;
    if (v.paused) { void v.play(); } else { v.pause(); }
  };
  const stopPreview = () => {
    seekPreviewTo(0);
    videoRef.current?.pause();
  };
  const skipPreview = (delta: number) => {
    const v = videoRef.current;
    if (!v) return;
    seekPreviewTo((v.currentTime || previewTime) + delta);
  };
  const togglePreviewMute = () => {
    const v = videoRef.current;
    if (!v) return;
    v.muted = !v.muted;
    setPreviewMuted(v.muted);
  };
  const seekPreviewFromPointer = (event: PointerEvent<HTMLDivElement>) => {
    if (previewKnownDuration <= 0) return;
    const rect = event.currentTarget.getBoundingClientRect();
    const ratio = Math.max(0, Math.min(1, (event.clientX - rect.left) / rect.width));
    seekPreviewTo(ratio * previewKnownDuration);
  };
  const enterPreviewFullscreen = () => {
    void previewFrameRef.current?.requestFullscreen?.();
  };

  useEffect(() => {
    fetchTedialSession(true)
      .then(setSession)
      .catch((error) => setMessage(error instanceof Error ? error.message : 'Tedial durumu alınamadı'));
  }, []);

  const loadRecentTedialJobs = async () => {
    const rememberedIds = new Set(getRememberedTedialJobIds());
    if (rememberedIds.size === 0) {
      setRecentTedialJobs([]);
      return;
    }
    const jobs = await fetchRecentAsrJobs(100, { compact: true });
    setRecentTedialJobs(jobs.filter((job) => rememberedIds.has(job.job_id)).slice(0, 8));
  };

  useEffect(() => {
    loadRecentTedialJobs().catch(() => undefined);
  }, []);

  // Onizleme oynaticisi: secili Tedial asset'ini ana ekrandaki gibi DASH ile oynat.
  useEffect(() => {
    const video = videoRef.current;
    if (!video || !previewManifestUrl) {
      return undefined;
    }
    setPreviewPlaying(false);
    setPreviewMuted(video.muted);
    setPreviewTime(0);
    setPreviewDuration(0);
    const player = dashjs.MediaPlayer().create();
    player.updateSettings({ streaming: { buffer: { fastSwitchEnabled: true } } });
    player.initialize(video, previewManifestUrl, false);
    playerRef.current = player;
    return () => {
      playerRef.current = null;
      player.reset();
    };
  }, [previewManifestUrl]);

  const refreshSession = async (useHealth = false) => {
    const next = await fetchTedialSession(useHealth);
    setSession(next);
    return next;
  };

  const handleConnect = async () => {
    try {
      const next = await startTedialSession(remember);
      setSession(next);
      window.open(next.login_url || 'http://127.0.0.1:8765/api/tedial/login/', 'mitas-tedial-login', 'width=1180,height=820');
      setMessage('Tedial login bekleniyor');
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Tedial bağlantısı başlatılamadı');
    }
  };

  const handleForget = async () => {
    try {
      setSession(await forgetTedialSession());
      setItems([]);
      setSelectedIndex(0);
      setMessage('Oturum kapatıldı');
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Oturum kapatılamadı');
    }
  };

  const handleAutoLogin = async () => {
    setMessage('Otomatik login deneniyor');
    try {
      const next = await autoLoginTedialSession();
      setSession(next);
      setMessage(next.status === 'connected' ? 'Otomatik login tamam' : next.auto_login_error || 'Otomatik login tamamlanamadı');
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Otomatik login başarısız');
      await refreshSession(false).catch(() => undefined);
    }
  };

  const handleSearch = async () => {
    const searchField = query.trim();
    if (!searchField) {
      return;
    }
    setIsSearching(true);
    setMessage('Aranıyor');
    try {
      const nextItems = await searchTedial(searchField);
      setItems(nextItems);
      setSelectedIndex(0);
      setMessage(`${nextItems.length} sonuç`);
      await refreshSession(false);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Tedial araması başarısız');
      await refreshSession(false).catch(() => undefined);
    } finally {
      setIsSearching(false);
    }
  };

  const handleImport = async () => {
    if (!selected) {
      return;
    }
    setIsImporting(true);
    setMessage(`MITAS'ta açılıyor · Kanal ${audioTrack + 1}`);
    try {
      const result = openTedialMediaInMitas(selected, { audioTrack, channelMode });
      await onImportToMitas(result);
      setMessage('MITAS Analiz İstasyonu açıldı');
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'MITAS import başarısız');
      await refreshSession(false).catch(() => undefined);
    } finally {
      setIsImporting(false);
    }
  };

  const sessionStatus = session?.status ?? 'disconnected';
  const isConnected = sessionStatus === 'connected';

  return (
    <div className="flex h-full min-h-0 flex-col bg-app-shell text-foreground-default">
      <header className="flex shrink-0 items-center justify-between gap-4 border-b border-border-subtle bg-app-shell px-4 py-3">
        <div className="flex items-center gap-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-sm bg-info-strong shadow-glow-info">
            <Database className="h-4 w-4 text-white" />
          </div>
          <div>
            <h1 className="text-base font-bold uppercase tracking-tight text-foreground-strong">Tedial İçerik</h1>
            <div className="mt-1 flex items-center gap-2">
              <Badge variant={isConnected ? 'success' : sessionStatus === 'expired' || sessionStatus === 'error' ? 'danger' : 'outline'}>
                {STATUS_LABEL[sessionStatus]}
              </Badge>
              <span className="text-[11px] text-foreground-muted">{session?.cookie_names?.length ?? 0} cookie</span>
              <span className="text-[11px] text-foreground-muted">{message}</span>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <label className="flex h-8 items-center gap-2 rounded-sm border border-border-mitas bg-surface/50 px-2 text-xs text-foreground-muted">
            <input type="checkbox" checked={remember} onChange={(event) => setRemember(event.target.checked)} />
            Beni hatırla
          </label>
          <Button size="sm" variant="outline" className="gap-2" onClick={() => refreshSession(true).catch((error) => setMessage(error.message))}>
            <RefreshCw className="h-3.5 w-3.5" />
            Yenile
          </Button>
          {session?.auto_login_enabled ? (
            <Button size="sm" variant="outline" className="gap-2" onClick={handleAutoLogin} disabled={!session.auto_login_configured}>
              <RefreshCw className="h-3.5 w-3.5" />
              Oto Login
            </Button>
          ) : null}
          <Button size="sm" className="gap-2" onClick={handleConnect}>
            <LogIn className="h-3.5 w-3.5" />
            Bağlan
          </Button>
          <Button size="sm" variant="outline" className="gap-2" onClick={handleForget}>
            <XCircle className="h-3.5 w-3.5" />
            Çık
          </Button>
        </div>
      </header>

      <div className="grid min-h-0 flex-1 grid-cols-[360px_minmax(0,1fr)]">
        <aside className="flex min-h-0 flex-col border-r border-border-subtle bg-surface/40">
          <form
            className="flex gap-2 border-b border-border-subtle p-3"
            onSubmit={(event) => {
              event.preventDefault();
              handleSearch();
            }}
          >
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              className="h-8 min-w-0 flex-1 rounded-sm border border-border-mitas bg-app-shell px-2 text-sm text-foreground-default outline-none focus:border-info-border"
            />
            <Button size="sm" className="gap-2" disabled={isSearching} type="submit">
              <Search className="h-3.5 w-3.5" />
              Ara
            </Button>
          </form>

          <ScrollArea className="min-h-0 flex-1">
            <div className="space-y-1 p-2">
              {items.length === 0 ? (
                <div className="space-y-2">
                  <div className="px-2 pt-2 text-[10px] font-semibold uppercase tracking-wider text-foreground-muted">
                    Son Tedial İşleri
                  </div>
                  {recentTedialJobs.length === 0 ? (
                    <div className="rounded-sm border border-border-subtle bg-app-shell/50 p-4 text-center text-xs text-foreground-muted">
                      Henüz Tedial STT işi yok. MITAS'ta açtıktan sonra ana ekranda STT başlatınca burada kalır.
                    </div>
                  ) : recentTedialJobs.map((job) => (
                    <div key={job.job_id} className="rounded-sm border border-border-subtle bg-app-shell/45 p-2">
                      <div className="flex items-start gap-2">
                        <FileText className="mt-0.5 h-3.5 w-3.5 shrink-0 text-info" />
                        <div className="min-w-0 flex-1">
                          <div className="truncate text-xs font-semibold text-foreground-strong">{job.filename}</div>
                          <div className="mt-1 flex flex-wrap items-center gap-2 text-[10px] text-foreground-muted">
                            <span>{formatTedialDate(job.created_at)}</span>
                            <span>{formatClock(job.summary?.audio_duration)}</span>
                            <span>{job.summary?.clean_segments ?? 0} seg</span>
                          </div>
                        </div>
                      </div>
                      <div className="mt-2 flex items-center justify-between gap-2">
                        <Badge variant={job.status === 'done' ? 'success' : job.status === 'failed' ? 'danger' : job.status === 'partial' ? 'warning' : 'secondary'}>
                          {job.status}
                        </Badge>
                        <Button size="xs" variant="outline" className="gap-1" onClick={() => onOpenJobLog(job)}>
                          <Clock3 className="h-3 w-3" />
                          Logda aç
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
              ) : items.map((item, index) => (
                <button
                  key={`${item.repository_id}-${item.asset_id}-${index}`}
                  type="button"
                  onClick={() => setSelectedIndex(index)}
                  className={`grid w-full grid-cols-[64px_minmax(0,1fr)] gap-2 rounded-sm border p-2 text-left transition ${
                    selectedIndex === index
                      ? 'border-info-border bg-info-subtle'
                      : 'border-border-subtle bg-app-shell/40 hover:bg-surface'
                  }`}
                >
                  <div className="aspect-video overflow-hidden rounded-sm border border-border-subtle bg-app-shell">
                    {tedialKeyframeProxyUrl(item) ? (
                      <img src={tedialKeyframeProxyUrl(item) ?? ''} alt="" className="h-full w-full object-cover" />
                    ) : null}
                  </div>
                  <div className="min-w-0">
                    <div className="truncate text-xs font-semibold text-foreground-strong">{item.title || 'Başlıksız'}</div>
                    <div className="mt-1 truncate font-mono text-[10px] text-info">{item.trt_id || '-'}</div>
                    <div className="mt-1 truncate font-mono text-[10px] text-foreground-muted">{item.asset_id || '-'}</div>
                    <div className="mt-1 text-[10px] uppercase tracking-wider text-foreground-muted">
                      {item.asset_type || '-'} · {formatTedialDuration(tedialDurationSeconds(item))}
                    </div>
                  </div>
                </button>
              ))}
            </div>
          </ScrollArea>
        </aside>

        <section className="flex min-h-0 min-w-0 flex-col overflow-hidden">
          <div className="flex items-center justify-between border-b border-border-subtle bg-surface/60 px-4 py-3">
            <div className="min-w-0">
              <h2 className="truncate text-sm font-bold text-foreground-strong">{selected?.title || 'Tedial asset seç'}</h2>
              <div className="mt-1 flex flex-wrap gap-2 font-mono text-[10px] text-foreground-muted">
                <span>repo: {selected?.repository_id || '-'}</span>
                <span>trt id: {selected?.trt_id || '-'}</span>
                <span>asset: {selected?.asset_id || '-'}</span>
                <span>sequence: {selected?.sequence_id || '-'}</span>
                <span>süre: {formatTedialDuration(tedialDurationSeconds(selected))}</span>
              </div>
            </div>
            <div className="flex shrink-0 items-center gap-2">
              <div className="flex h-8 items-center rounded-sm border border-border-subtle bg-app-shell/70 p-0.5" title="Tedial audio track seçimi">
                <Volume2 className="mx-1.5 h-3.5 w-3.5 text-foreground-muted" />
                {([0, 1] as const).map((value) => (
                  <Button
                    key={value}
                    size="xs"
                    variant={audioTrack === value ? 'secondary' : 'ghost'}
                    className="h-6 px-2 text-[10px]"
                    disabled={isImporting}
                    onClick={() => setAudioTrack(value)}
                  >
                    Kanal {value + 1}
                  </Button>
                ))}
              </div>
              <div className="flex h-8 items-center rounded-sm border border-border-subtle bg-app-shell/70 p-0.5" title="Ana ekranda STT başlatılırsa kullanılacak kanal modu">
                <SplitSquareHorizontal className="mx-1.5 h-3.5 w-3.5 text-foreground-muted" />
                {([
                  ['auto', 'Auto'],
                  ['split', '1+2'],
                ] as const).map(([value, label]) => (
                  <Button
                    key={value}
                    size="xs"
                    variant={channelMode === value ? 'secondary' : 'ghost'}
                    className="h-6 px-2 text-[10px]"
                    disabled={isImporting}
                    onClick={() => setChannelMode(value)}
                  >
                    {label}
                  </Button>
                ))}
              </div>
              <Button size="sm" className="gap-2 bg-info-strong text-white hover:bg-info" disabled={!selected || isImporting} onClick={handleImport}>
                <DownloadCloud className="h-3.5 w-3.5" />
                {isImporting ? 'Açılıyor' : 'MITAS’ta Aç'}
              </Button>
            </div>
          </div>

          <div className="grid min-h-0 flex-1 grid-rows-[minmax(0,1fr)_auto] gap-3 p-4">
            <div ref={previewFrameRef} className="flex min-h-0 flex-col overflow-hidden rounded-md border border-border-mitas bg-black">
              <div className="relative flex min-h-0 flex-1 items-center justify-center overflow-hidden bg-black">
                {selected && previewManifestUrl ? (
                  <video
                    ref={videoRef}
                    className="h-full w-full cursor-pointer object-contain bg-black"
                    playsInline
                    preload="metadata"
                    poster={keyframeUrl ?? undefined}
                    muted={previewMuted}
                    onClick={togglePreviewPlay}
                    onVolumeChange={(event) => setPreviewMuted(event.currentTarget.muted)}
                    onPlay={() => setPreviewPlaying(true)}
                    onPause={() => setPreviewPlaying(false)}
                    onEnded={() => setPreviewPlaying(false)}
                    onTimeUpdate={(event) => setPreviewTime(event.currentTarget.currentTime || 0)}
                    onDurationChange={(event) => { const d = saneSeconds(event.currentTarget.duration); if (d > 0) setPreviewDuration(d); }}
                    onLoadedMetadata={(event) => setPreviewDuration(saneSeconds(event.currentTarget.duration))}
                  />
                ) : keyframeUrl ? (
                  <img src={keyframeUrl} alt="" className="max-h-full max-w-full object-contain" />
                ) : (
                  <div className="text-xs text-foreground-muted">Önizleme yok — soldan bir Tedial sonucu seç</div>
                )}
              </div>
              <div className="flex shrink-0 flex-col gap-1.5 border-t border-border-subtle bg-app-shell px-3 py-2">
                <div className="flex items-center gap-2">
                  <div
                    className="relative h-2 flex-1 cursor-pointer overflow-hidden rounded-sm bg-surface-elevated"
                    onPointerDown={seekPreviewFromPointer}
                    onPointerMove={(event) => { if (event.buttons === 1) seekPreviewFromPointer(event); }}
                    title="Konum"
                  >
                    <div className="absolute left-0 top-0 h-full bg-info-strong" style={{ width: `${previewProgress}%` }} />
                  </div>
                  <span className="shrink-0 font-mono text-[10px] tabular-nums text-foreground-muted">
                    {formatClock(previewTime)} / {formatClock(previewKnownDuration)}
                  </span>
                </div>
                <div className="flex items-center gap-1.5">
                  <Button size="icon-xs" variant="ghost" disabled={!previewManifestUrl} onClick={() => skipPreview(-10)} title="10 sn geri">
                    <SkipBack className="h-3.5 w-3.5" />
                  </Button>
                  <Button size="icon-xs" variant="ghost" disabled={!previewManifestUrl} onClick={() => skipPreview(-1)} title="1 sn geri">
                    <ChevronLeft className="h-3.5 w-3.5" />
                  </Button>
                  <Button
                    size="icon-xs"
                    variant="default"
                    disabled={!previewManifestUrl}
                    onClick={togglePreviewPlay}
                    className="h-7 w-7 rounded-sm bg-foreground-strong text-app-shell hover:bg-foreground-strong/90"
                    title={previewPlaying ? 'Duraklat' : 'Oynat'}
                  >
                    {previewPlaying ? <Pause className="h-3.5 w-3.5" /> : <Play className="ml-0.5 h-3.5 w-3.5" />}
                  </Button>
                  <Button size="icon-xs" variant="ghost" disabled={!previewManifestUrl} onClick={stopPreview} title="Durdur">
                    <Square className="h-3.5 w-3.5" />
                  </Button>
                  <Button size="icon-xs" variant="ghost" disabled={!previewManifestUrl} onClick={() => skipPreview(1)} title="1 sn ileri">
                    <ChevronRight className="h-3.5 w-3.5" />
                  </Button>
                  <Button size="icon-xs" variant="ghost" disabled={!previewManifestUrl} onClick={() => skipPreview(10)} title="10 sn ileri">
                    <SkipForward className="h-3.5 w-3.5" />
                  </Button>
                  <div className="flex-1" />
                  <Button size="icon-xs" variant="ghost" disabled={!previewManifestUrl} onClick={togglePreviewMute} title={previewMuted ? 'Sesi aç' : 'Sesi kapat'}>
                    {previewMuted ? <VolumeX className="h-3.5 w-3.5" /> : <Volume2 className="h-3.5 w-3.5" />}
                  </Button>
                  <Button size="icon-xs" variant="ghost" disabled={!previewManifestUrl} onClick={enterPreviewFullscreen} title="Tam ekran">
                    <Maximize className="h-3.5 w-3.5" />
                  </Button>
                </div>
              </div>
            </div>
            <div className="rounded-sm border border-border-subtle bg-surface/60 p-3 text-xs text-foreground-muted">
              <div className="font-semibold uppercase tracking-wider text-foreground-strong">Durum</div>
              <div className="mt-2 flex flex-wrap gap-2">
                <Badge variant={isConnected ? 'success' : 'outline'}>{STATUS_LABEL[sessionStatus]}</Badge>
                <Badge variant="outline">{items.length} sonuç</Badge>
                <Badge variant={isImporting ? 'warning' : 'outline'}>{isImporting ? 'İçe aktarılıyor' : message}</Badge>
              </div>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}

function saneSeconds(value: number | null | undefined): number {
  if (!Number.isFinite(value ?? NaN)) {
    return 0;
  }
  const seconds = Number(value);
  // DASH bazen süreyi MAX_SAFE_INTEGER/sonsuz verir; 0 < süre < 24sa değilse yok say.
  return seconds > 0 && seconds < 24 * 60 * 60 ? seconds : 0;
}

function formatTedialDuration(seconds: number | null | undefined): string {
  if (!Number.isFinite(seconds ?? NaN)) {
    return '--:--';
  }
  const total = Math.max(0, Math.round(seconds ?? 0));
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const secs = total % 60;
  if (hours > 0) {
    return `${hours}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  }
  return `${minutes}:${secs.toString().padStart(2, '0')}`;
}

function formatTedialDate(value: string | null | undefined): string {
  if (!value) return '-';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '-';
  return new Intl.DateTimeFormat('tr-TR', {
    day: '2-digit',
    month: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date);
}
