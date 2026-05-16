import { Database, DownloadCloud, LogIn, RefreshCw, Search, SplitSquareHorizontal, Volume2, XCircle } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { Badge, Button, ScrollArea } from './ui';
import {
  autoLoginTedialSession,
  fetchTedialSession,
  forgetTedialSession,
  searchTedial,
  startTedialAsrJob,
  startTedialSession,
  tedialDurationSeconds,
  tedialKeyframeProxyUrl,
  type TedialAsrChannelMode,
  type TedialAudioTrack,
  type TedialImportResult,
  type TedialSearchResult,
  type TedialSession,
} from '../tedial-api';

interface TedialWorkspaceProps {
  onImportToMitas: (result: TedialImportResult) => Promise<void>;
}

const STATUS_LABEL: Record<TedialSession['status'], string> = {
  disconnected: 'Bağlı değil',
  connecting: 'Bağlanıyor',
  connected: 'Bağlı',
  expired: 'Süresi doldu',
  error: 'Hata',
};

export function TedialWorkspace({ onImportToMitas }: TedialWorkspaceProps) {
  const [session, setSession] = useState<TedialSession | null>(null);
  const [remember, setRemember] = useState(true);
  const [query, setQuery] = useState('34-*');
  const [items, setItems] = useState<TedialSearchResult[]>([]);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [message, setMessage] = useState('Hazır');
  const [isSearching, setIsSearching] = useState(false);
  const [isImporting, setIsImporting] = useState(false);
  const [audioTrack, setAudioTrack] = useState<TedialAudioTrack>(0);
  const [channelMode, setChannelMode] = useState<TedialAsrChannelMode>('split');

  const selected = items[selectedIndex] ?? null;
  const keyframeUrl = useMemo(() => selected ? tedialKeyframeProxyUrl(selected) : null, [selected]);

  useEffect(() => {
    fetchTedialSession(true)
      .then(setSession)
      .catch((error) => setMessage(error instanceof Error ? error.message : 'Tedial durumu alınamadı'));
  }, []);

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
    setMessage(`MITAS stream + STT başlatılıyor · Kanal ${audioTrack + 1}`);
    try {
      const result = await startTedialAsrJob(selected, { audioTrack, channelMode });
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
                <div className="p-6 text-center text-xs text-foreground-muted">Sonuç yok</div>
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

        <section className="flex min-w-0 flex-col">
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
              <div className="flex h-8 items-center rounded-sm border border-border-subtle bg-app-shell/70 p-0.5" title="ASR kanal çözümleme modu">
                <SplitSquareHorizontal className="mx-1.5 h-3.5 w-3.5 text-foreground-muted" />
                {([
                  ['split', '1+2'],
                  ['auto', 'Auto'],
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
                {isImporting ? 'Başlatılıyor' : 'MITAS’ta Aç + STT'}
              </Button>
            </div>
          </div>

          <div className="grid flex-1 grid-rows-[minmax(240px,1fr)_auto] gap-3 p-4">
            <div className="flex items-center justify-center overflow-hidden rounded-sm border border-border-subtle bg-black">
              {keyframeUrl ? (
                <img src={keyframeUrl} alt="" className="max-h-full max-w-full object-contain" />
              ) : (
                <div className="text-xs text-foreground-muted">Önizleme yok</div>
              )}
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
