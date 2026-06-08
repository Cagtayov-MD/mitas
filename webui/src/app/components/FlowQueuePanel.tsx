import {
  AlertCircle,
  CheckCircle2,
  Clock3,
  FileVideo,
  Loader2,
  Play,
  Search,
  UploadCloud,
  X,
} from 'lucide-react';
import { useEffect, useRef, useState, type ChangeEvent, type DragEvent } from 'react';
import { Badge, Button, ScrollArea } from './ui';
import {
  ANALYSIS_PROFILE_OPTIONS,
  analysisProfileLabel,
  localFileSourcePath,
  type AnalysisProfile,
  type AsrJob,
} from '../asr-api';
import { searchTedial, type TedialSearchResult } from '../tedial-api';
import { Select, SelectContent, SelectItem, SelectTrigger } from './ui/select';
import {
  ContextMenu,
  ContextMenuContent,
  ContextMenuItem,
  ContextMenuRadioGroup,
  ContextMenuRadioItem,
  ContextMenuSeparator,
  ContextMenuTrigger,
} from './ui/context-menu';

type FlowItemStatus = 'waiting' | 'running' | 'done' | 'partial' | 'failed' | 'stopped';
type FlowItemSource = 'upload' | 'tedial';
type FlowStopMode = 'none' | 'safe' | 'force';

interface FlowQueueItem {
  id: string;
  source: FlowItemSource;
  name: string;
  profile: AnalysisProfile;
  status: FlowItemStatus;
  file?: File;
  sourcePath?: string;
  storedMediaUrl?: string;
  storedMediaPath?: string;
  mediaType?: string;
  sizeBytes?: number;
  tedialItem?: TedialSearchResult;
  job?: AsrJob;
  message?: string;
}

export interface FlowQueuedMediaRequest {
  source: FlowItemSource;
  name: string;
  file?: File;
  storedMediaUrl?: string;
  mediaType?: string;
  sourcePath?: string;
  tedialItem?: TedialSearchResult;
  tedialQuery?: string;
  job?: AsrJob;
}

interface FlowQueuePanelProps {
  onOpenMedia: (request: FlowQueuedMediaRequest) => void;
}

interface PersistedFlowQueueState {
  id: string;
  updatedAt: string;
  bulkProfile: AnalysisProfile;
  items: FlowQueueItem[];
}

const STATUS_META: Record<FlowItemStatus, { label: string; variant: 'secondary' | 'outline' | 'success' | 'warning' | 'danger' }> = {
  waiting: { label: 'Bekliyor', variant: 'warning' },
  running: { label: 'İşleniyor', variant: 'outline' },
  done: { label: 'Tamamlandı', variant: 'success' },
  partial: { label: 'Kısmi', variant: 'warning' },
  failed: { label: 'Hata', variant: 'danger' },
  stopped: { label: 'Durduruldu', variant: 'secondary' },
};

export function FlowQueuePanel({ onOpenMedia }: FlowQueuePanelProps) {
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const directoryInputRef = useRef<HTMLInputElement | null>(null);
  const itemsRef = useRef<FlowQueueItem[]>([]);
  const isProcessingRef = useRef(false);
  const stopModeRef = useRef<FlowStopMode>('none');
  const hasLoadedPersistedQueueRef = useRef(false);
  const skipNextPersistenceEffectRef = useRef(true);
  const [items, setItems] = useState<FlowQueueItem[]>([]);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(() => new Set());
  const [bulkProfile, setBulkProfile] = useState<AnalysisProfile>('film_dizi');
  const [tedialQuery, setTedialQuery] = useState('');
  const [tedialCandidate, setTedialCandidate] = useState<TedialSearchResult | null>(null);
  const [lastTedialQuery, setLastTedialQuery] = useState('');
  const [tedialSearchState, setTedialSearchState] = useState<'idle' | 'searching' | 'found' | 'missing' | 'error'>('idle');
  const [tedialMessage, setTedialMessage] = useState('');
  const [isDragActive, setIsDragActive] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [stopMode, setStopMode] = useState<FlowStopMode>('none');
  const [persistenceStatus, setPersistenceStatus] = useState<'loading' | 'saved' | 'error'>('loading');
  const [localDir, setLocalDir] = useState('');
  const [localDirBusy, setLocalDirBusy] = useState(false);

  useEffect(() => {
    directoryInputRef.current?.setAttribute('webkitdirectory', '');
    directoryInputRef.current?.setAttribute('directory', '');
  }, []);

  useEffect(() => {
    let cancelled = false;
    loadFlowQueueState()
      .then((state) => {
        if (cancelled) return;
        const restoredItems = (state?.items ?? []).map(restorePersistedFlowItem);
        const restoredBulkProfile = state?.bulkProfile ?? 'film_dizi';
        itemsRef.current = restoredItems;
        setItems(restoredItems);
        if (state?.bulkProfile) {
          setBulkProfile(restoredBulkProfile);
        }
        if (restoredItems.length > 0) {
          void saveFlowQueueServerState({
            id: FLOW_QUEUE_STATE_ID,
            updatedAt: new Date().toISOString(),
            bulkProfile: restoredBulkProfile,
            items: restoredItems.map(toFallbackFlowItem),
          });
        }
        setPersistenceStatus('saved');
      })
      .catch(() => {
        if (!cancelled) {
          setPersistenceStatus('error');
        }
      })
      .finally(() => {
        if (!cancelled) {
          skipNextPersistenceEffectRef.current = true;
          hasLoadedPersistedQueueRef.current = true;
        }
      });

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!hasLoadedPersistedQueueRef.current) return;
    if (skipNextPersistenceEffectRef.current) {
      skipNextPersistenceEffectRef.current = false;
      return;
    }
    if (isProcessingRef.current) return;  // SUNUCU worker koşarken queue.json'a YAZMA — worker sahibi; poll-PUT yarışı (worker 'done'unu geri-sarma) önlenir
    saveFlowQueueState({ items, bulkProfile })
      .then(() => setPersistenceStatus('saved'))
      .catch(() => setPersistenceStatus('error'));
  }, [items, bulkProfile]);

  const updateItems = (updater: (current: FlowQueueItem[]) => FlowQueueItem[]) => {
    setItems((current) => {
      const next = updater(current);
      itemsRef.current = next;
      if (hasLoadedPersistedQueueRef.current && !isProcessingRef.current) {
        saveFlowQueueState({ items: next, bulkProfile })
          .then(() => setPersistenceStatus('saved'))
          .catch(() => setPersistenceStatus('error'));
      }
      return next;
    });
  };

  // SUNUCU worker durumunu izle — yenileme/kapatma sonrası YENİDEN BAĞLANIR (koşu sayfadan bağımsız sürer).
  const pollServerQueue = async () => {
    try {
      const [wr, qr] = await Promise.all([
        fetch('/api/flow-queue/worker', { cache: 'no-store' }),
        fetch('/api/flow-queue', { cache: 'no-store' }),
      ]);
      let running = false;
      if (wr.ok) {
        const w = await wr.json();
        running = Boolean(w?.running);
      }
      if (qr.ok) {
        const q = await qr.json();
        const serverItems: Array<{ id: string; status?: FlowItemStatus; message?: string }> = Array.isArray(q?.items) ? q.items : [];
        if (serverItems.length) {
          const byId = new Map(serverItems.map((s) => [s.id, s] as const));
          setItems((current) => {
            const next = current.map((it) => {
              const s = byId.get(it.id);
              return s ? { ...it, status: (s.status as FlowItemStatus) ?? it.status, message: s.message ?? it.message } : it;
            });
            itemsRef.current = next;
            return next;
          });
        }
      }
      isProcessingRef.current = running;
      setIsProcessing(running);
      if (!running && stopModeRef.current !== 'none') {
        stopModeRef.current = 'none';
        setStopMode('none');
      }
    } catch {
      /* geçici ağ hatası — sonraki tick'te tekrar */
    }
  };

  useEffect(() => {
    void pollServerQueue();
    const id = window.setInterval(() => { void pollServerQueue(); }, 2000);
    return () => window.clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const addFiles = (fileList: FileList | File[]) => {
    const files = Array.from(fileList).filter(Boolean);
    if (!files.length) return;
    const nextItems = files.map((file) => ({
      id: `upload-${Date.now()}-${Math.random().toString(16).slice(2)}`,
      source: 'upload' as const,
      name: file.name,
      profile: bulkProfile,
      status: 'waiting' as const,
      file,
      sourcePath: uploadSourcePath(file),
      mediaType: mediaTypeForQueueFile(file),
      sizeBytes: file.size,
      message: formatBytes(file.size),
    }));
    updateItems((current) => [...current, ...nextItems]);
    nextItems.forEach((item) => {
      persistQueueUpload(item.id, item.file)
        .then((stored) => {
          updateItems((current) => current.map((currentItem) => currentItem.id === item.id
            ? withStoredUploadMedia(currentItem, stored)
            : currentItem));
        })
        .catch((error) => {
          updateItems((current) => current.map((currentItem) => currentItem.id === item.id
            ? { ...currentItem, message: `Queue log kopyası yazılamadı: ${error instanceof Error ? error.message : 'hata'}` }
            : currentItem));
        });
    });
  };

  const handleFileChange = (event: ChangeEvent<HTMLInputElement>) => {
    if (event.target.files) {
      addFiles(event.target.files);
      event.target.value = '';
    }
  };

  const handleDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setIsDragActive(false);
    if (event.dataTransfer.files?.length) {
      addFiles(event.dataTransfer.files);
    }
  };

  const toggleSelected = (id: string) => {
    setSelectedIds((current) => {
      const next = new Set(current);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  const toggleAll = () => {
    setSelectedIds((current) => {
      if (items.length > 0 && current.size === items.length) {
        return new Set();
      }
      return new Set(items.map((item) => item.id));
    });
  };

  const assignProfile = (profile: AnalysisProfile, targetIds?: Set<string>) => {
    const ids = targetIds ?? selectedIds;
    updateItems((current) => current.map((item) => {
      if (ids.size > 0 && !ids.has(item.id)) {
        return item;
      }
      return { ...item, profile };
    }));
  };

  const handleBulkProfileChange = (profile: AnalysisProfile) => {
    setBulkProfile(profile);
    if (selectedIds.size > 0) {
      assignProfile(profile, selectedIds);
    }
  };

  const contextTargetIdsForItem = (item: FlowQueueItem) => {
    return selectedIds.has(item.id) && selectedIds.size > 0 ? selectedIds : new Set([item.id]);
  };

  const assignProfileFromContext = (item: FlowQueueItem, profile: AnalysisProfile) => {
    assignProfile(profile, contextTargetIdsForItem(item));
  };

  const removeItems = (ids: Set<string>) => {
    if (ids.size === 0) return;
    updateItems((current) => current.filter((item) => !ids.has(item.id)));
    setSelectedIds((current) => {
      const next = new Set(current);
      ids.forEach((id) => next.delete(id));
      return next;
    });
  };

  const removeItem = (id: string) => {
    removeItems(new Set([id]));
  };

  const removableContextIdsForItem = (item: FlowQueueItem) => {
    const targetIds = selectedIds.has(item.id) && selectedIds.size > 0 ? selectedIds : new Set([item.id]);
    return new Set(items
      .filter((candidate) => targetIds.has(candidate.id) && candidate.status !== 'running')
      .map((candidate) => candidate.id));
  };

  const clearCompleted = () => {
    updateItems((current) => current.filter((item) => item.status !== 'done' && item.status !== 'partial'));
  };

  const handleTedialSearch = async () => {
    const query = tedialQuery.trim();
    if (!query) return;
    setTedialSearchState('searching');
    setTedialCandidate(null);
    setTedialMessage('');
    try {
      const results = await searchTedial(query);
      const first = results[0] ?? null;
      setLastTedialQuery(query);
      setTedialCandidate(first);
      setTedialSearchState(first ? 'found' : 'missing');
      setTedialMessage(first ? (first.title || first.trt_id || first.asset_id || 'Tedial klip bulundu') : 'Kayıt yok');
    } catch (error) {
      setLastTedialQuery(query);
      setTedialSearchState('error');
      setTedialMessage(error instanceof Error ? error.message : 'Tedial araması başarısız');
    }
  };

  const addTedialCandidate = () => {
    if (!tedialCandidate) return;
    const name = tedialCandidate.title || tedialCandidate.trt_id || tedialCandidate.asset_id || 'Tedial klip';
    updateItems((current) => [
      ...current,
      {
        id: `tedial-${tedialCandidate.asset_id || Date.now()}-${Math.random().toString(16).slice(2)}`,
        source: 'tedial',
        name,
        profile: bulkProfile,
        status: 'waiting',
        tedialItem: tedialCandidate,
        message: tedialCandidate.trt_id || tedialCandidate.asset_id || analysisProfileLabel(bulkProfile),
      },
    ]);
    setTedialQuery('');
    setTedialCandidate(null);
    setTedialSearchState('idle');
    setTedialMessage('');
    setLastTedialQuery('');
  };

  const handleTedialEnter = async () => {
    const query = tedialQuery.trim();
    if (tedialCandidate && query && query === lastTedialQuery) {
      addTedialCandidate();
      return;
    }
    await handleTedialSearch();
  };

  const processQueue = async () => {
    if (isProcessingRef.current) return;
    stopModeRef.current = 'none';
    setStopMode('none');
    isProcessingRef.current = true;
    setIsProcessing(true);
    try {
      // Kuyruğu sunucuya yaz (worker queue.json'dan okur) + SUNUCU-TARAFI worker'ı başlat.
      await saveFlowQueueServerState({
        id: FLOW_QUEUE_STATE_ID,
        updatedAt: new Date().toISOString(),
        bulkProfile,
        items: itemsRef.current.map(toFallbackFlowItem),
      });
      await fetch('/api/flow-queue/run', { method: 'POST' });
      await pollServerQueue();
    } catch {
      // başlatılamazsa pollServerQueue gerçek durumu yansıtır
    }
  };

  const requestSafeStop = () => {
    if (!isProcessingRef.current || stopModeRef.current === 'force') return;
    stopModeRef.current = 'safe';
    setStopMode('safe');
    // Nazik: o anki film biter, kuyruk durur. "Başlat" kaldığı yerden devam eder.
    void fetch('/api/flow-queue/stop', { method: 'POST' }).catch(() => {});
  };

  const requestForceStop = () => {
    if (!isProcessingRef.current) return;
    stopModeRef.current = 'force';
    setStopMode('force');
    // SUNUCU worker'ı durdur + çalışan pipeline'ı process-AĞACIYLA öldür (gerçek "net kes")
    void fetch('/api/flow-queue/stop', { method: 'POST' }).catch(() => {});
    void fetch('/api/pipeline/abort', { method: 'POST' }).catch(() => {});
  };

  // (eski client-tarafı processItem KALDIRILDI — kuyruk artık SUNUCU worker'da koşuyor: /api/flow-queue/run)

  const selectedCount = selectedIds.size;
  const pendingCount = items.filter((item) => item.status === 'waiting').length;
  const doneCount = items.filter((item) => item.status === 'done' || item.status === 'partial').length;
  const stoppedCount = items.filter((item) => item.status === 'stopped').length;
  const canSafeStop = isProcessing && stopMode !== 'safe';
  const canForceStop = isProcessing && stopMode !== 'force';
  const persistenceLabel = persistenceStatus === 'loading'
    ? 'Yükleniyor'
    : persistenceStatus === 'error'
      ? 'Kayıt hatası'
      : 'Kalıcı';

  // YEREL KLASÖR (PATH ile, UPLOAD YOK): tarayıcı yerel dosya yolunu göremez → server-tarafı
  // okuma. /api/flow-queue/enqueue-local dizini okur, sourcePath öğeleri ekler, worker'ı başlatır.
  const enqueueLocalDir = async () => {
    const dir = localDir.trim();
    if (!dir || localDirBusy) return;
    setLocalDirBusy(true);
    try {
      const res = await fetch('/api/flow-queue/enqueue-local', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ dir, profile: bulkProfile, replace: false }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        window.alert(`Klasör eklenemedi: ${data?.detail ?? res.status}`);
        return;
      }
      window.alert(`${data.added} film PATH ile eklendi (upload yok). Toplam: ${data.total}. Worker başladı.`);
      setLocalDir('');
    } catch (err) {
      window.alert(`Klasör eklenemedi: ${String(err)}`);
    } finally {
      setLocalDirBusy(false);
    }
  };

  return (
    <div className="flex h-full min-h-0 w-full min-w-0 max-w-full flex-col overflow-hidden bg-app-shell">
      <div className="border-b border-border-subtle bg-surface/40 p-2.5">
        <div className="grid grid-cols-2 gap-1.5">
          <input
            ref={fileInputRef}
            type="file"
            multiple
            className="hidden"
            accept="audio/*,video/*,.wav,.mp3,.mp4,.m4a,.mkv,.flac,.aac,.ogg"
            onChange={handleFileChange}
          />
          <input
            ref={directoryInputRef}
            type="file"
            multiple
            className="hidden"
            accept="audio/*,video/*,.wav,.mp3,.mp4,.m4a,.mkv,.flac,.aac,.ogg"
            onChange={handleFileChange}
          />
          <Button size="sm" variant="outline" className="w-full justify-center gap-1 px-1.5" onClick={() => fileInputRef.current?.click()}>
            <UploadCloud className="h-3.5 w-3.5" />
            Yükle
          </Button>
          <Button size="sm" variant="outline" className="w-full justify-center gap-1 px-1.5" onClick={() => directoryInputRef.current?.click()}>
            Klasör
          </Button>
        </div>
        <div className="mt-1.5 grid grid-cols-[minmax(0,1fr)_auto] gap-1.5">
          <input
            type="text"
            value={localDir}
            onChange={(event) => setLocalDir(event.target.value)}
            onKeyDown={(event) => { if (event.key === 'Enter') void enqueueLocalDir(); }}
            placeholder="Yerel klasör yolu (UPLOAD YOK) — ör. E:\filmler"
            className="h-8 min-w-0 rounded-sm border border-border-mitas bg-app-shell/80 px-2 text-xs text-foreground-default placeholder:text-foreground-muted"
          />
          <Button size="sm" variant="outline" className="justify-center gap-1 whitespace-nowrap px-2" onClick={enqueueLocalDir} disabled={!localDir.trim() || localDirBusy}>
            {localDirBusy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : null}
            Klasör ekle (yol)
          </Button>
        </div>
        <div className="mt-1.5 grid grid-cols-3 gap-1.5">
          <Button size="sm" className="w-full justify-center gap-1 px-1.5" onClick={processQueue} disabled={isProcessing || pendingCount === 0}>
            {isProcessing ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Play className="h-3.5 w-3.5" />}
            Başlat
          </Button>
          <Button size="sm" variant="outline" className="w-full justify-center px-1.5" onClick={requestSafeStop} disabled={!canSafeStop}>
            {stopMode === 'safe' ? 'Duruyor' : 'Durdur'}
          </Button>
          <Button size="sm" variant="danger" className="w-full justify-center px-1.5" onClick={requestForceStop} disabled={!canForceStop}>
            Zorla durdur
          </Button>
        </div>
        <div className={`mt-1.5 grid gap-1.5 ${doneCount > 0 ? 'grid-cols-2' : 'grid-cols-1'}`}>
          <Button size="sm" variant="outline" className="w-full justify-center px-2" onClick={toggleAll} disabled={items.length === 0}>
            {selectedCount === items.length && items.length > 0 ? 'Seçimi bırak' : 'Tümünü seç'}
          </Button>
          {doneCount > 0 ? (
            <Button size="sm" variant="outline" className="w-full justify-center px-2" onClick={clearCompleted}>
              Bitenleri sil
            </Button>
          ) : null}
        </div>
        <div className="mt-2 grid grid-cols-[minmax(0,1.25fr)_minmax(140px,0.75fr)] gap-2">
          <Select value={bulkProfile} onValueChange={(value) => handleBulkProfileChange(value as AnalysisProfile)}>
            <SelectTrigger size="sm" className="h-8 rounded-sm border-border-mitas bg-app-shell/80 px-2 text-xs text-foreground-default">
              <span className="truncate font-semibold">{analysisProfileLabel(bulkProfile)}</span>
            </SelectTrigger>
            <SelectContent className="border-border-mitas bg-surface text-foreground-default">
              {ANALYSIS_PROFILE_OPTIONS.map((option) => (
                <SelectItem key={option.value} value={option.value} className="text-xs focus:bg-surface-elevated focus:text-foreground-strong">
                  {option.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Button size="sm" variant="outline" className="w-full justify-center px-2" onClick={() => assignProfile(bulkProfile)} disabled={items.length === 0}>
            {selectedCount > 0 ? `${selectedCount} seçiliye uygula` : 'Tümüne uygula'}
          </Button>
        </div>
      </div>

      <div
        className={`m-2 rounded-sm border border-dashed p-2 ${isDragActive ? 'border-info-border bg-info-subtle/40' : 'border-border-mitas bg-surface/25'}`}
        onDragOver={(event) => {
          event.preventDefault();
          setIsDragActive(true);
        }}
        onDragLeave={() => setIsDragActive(false)}
        onDrop={handleDrop}
      >
        <div className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-2">
          <div className="flex min-w-0 items-center gap-2 overflow-hidden">
            <FileVideo className="h-4 w-4 shrink-0 text-info" />
            <div className="min-w-0 truncate text-xs font-semibold text-foreground-strong">Akış kuyruğu</div>
            <Badge variant={persistenceStatus === 'error' ? 'danger' : 'outline'} className="shrink-0 whitespace-nowrap px-2">
              {persistenceLabel}
            </Badge>
          </div>
          <div className="flex shrink-0 flex-wrap items-center justify-end gap-1.5">
            <Badge variant="warning" className="shrink-0 whitespace-nowrap px-2">{pendingCount} bekliyor</Badge>
            <Badge variant="success" className="shrink-0 whitespace-nowrap px-2">{doneCount} bitti</Badge>
            {stoppedCount > 0 ? <Badge variant="secondary" className="shrink-0 whitespace-nowrap px-2">{stoppedCount} durdu</Badge> : null}
          </div>
        </div>
      </div>

      <ScrollArea className="min-h-0 flex-1">
        <div className="space-y-1.5 p-2 pt-0">
          {items.length === 0 ? (
            <div className="rounded-sm border border-border-subtle bg-surface/35 p-5 text-center text-xs text-foreground-muted">
              Kuyruk boş.
            </div>
          ) : items.map((item) => (
            <FlowQueueRow
              key={item.id}
              item={item}
              selected={selectedIds.has(item.id)}
              contextRemoveCount={removableContextIdsForItem(item).size}
              onToggleSelected={() => toggleSelected(item.id)}
              onRemove={() => removeItem(item.id)}
              onContextRemove={() => removeItems(removableContextIdsForItem(item))}
              onAssignProfile={(profile) => assignProfileFromContext(item, profile)}
              onOpen={() => onOpenMedia({
                source: item.source,
                name: item.name,
                file: item.source === 'upload' ? item.file : undefined,
                storedMediaUrl: item.source === 'upload' ? item.storedMediaUrl : undefined,
                mediaType: item.source === 'upload' ? item.mediaType : undefined,
                sourcePath: item.source === 'upload' ? displaySourcePath(item) : undefined,
                tedialItem: item.source === 'tedial' ? item.tedialItem : undefined,
                tedialQuery: item.source === 'tedial'
                  ? item.tedialItem?.trt_id || item.tedialItem?.asset_id || item.message || item.name
                  : undefined,
                job: item.job,
              })}
            />
          ))}
        </div>
      </ScrollArea>

      <div className="border-t border-border-subtle bg-surface/40 p-2">
        <div className="grid grid-cols-[minmax(0,1fr)_52px_52px] items-center gap-1.5">
          <div className="relative min-w-0 flex-1">
            <Search className="absolute left-2 top-2 h-3.5 w-3.5 text-foreground-muted" />
            <input
              value={tedialQuery}
              onChange={(event) => {
                setTedialQuery(event.target.value);
                setTedialCandidate(null);
                setTedialSearchState('idle');
                setTedialMessage('');
              }}
              onKeyDown={(event) => {
                if (event.key === 'Enter') {
                  event.preventDefault();
                  void handleTedialEnter();
                }
              }}
              className="h-8 w-full rounded-sm border border-border-mitas bg-app-shell pl-7 pr-8 text-xs text-foreground-default outline-none focus:border-info-border"
              placeholder="TRT ID / Tedial ara"
            />
            <TedialSearchIndicator state={tedialSearchState} />
          </div>
          <Button size="sm" variant="outline" className="w-full justify-center px-2" onClick={handleTedialSearch} disabled={!tedialQuery.trim() || tedialSearchState === 'searching'}>
            Ara
          </Button>
          <Button
            size="sm"
            className="w-full justify-center px-2"
            disabled={!tedialCandidate}
            onClick={addTedialCandidate}
            title="Tedial klibini kuyruğa ekler. Not: kuyruk worker'ı Tedial klibini otomatik İŞLEYEMEZ — analiz için Tedial sekmesinden Pipeline'a gönderin."
          >
            Ekle
          </Button>
        </div>
        {tedialMessage ? (
          <div className={`mt-1 truncate text-[10px] ${tedialSearchState === 'found' ? 'text-success' : tedialSearchState === 'error' ? 'text-danger' : 'text-foreground-muted'}`} title={tedialMessage}>
            {tedialMessage}
          </div>
        ) : null}
        {tedialCandidate ? (
          <div className="mt-1 flex items-start gap-1 text-[10px] leading-4 text-warning" title="Tedial klipleri kuyrukta otomatik işlenmez">
            <AlertCircle className="mt-0.5 h-3 w-3 shrink-0" />
            <span>Tedial klibi kuyrukta otomatik işlenmez. Analiz için Tedial sekmesinden Pipeline'a gönderin; buradaki öğe yalnız önizleme/açma içindir.</span>
          </div>
        ) : null}
      </div>
    </div>
  );
}

function FlowQueueRow({
  item,
  selected,
  contextRemoveCount,
  onToggleSelected,
  onRemove,
  onContextRemove,
  onAssignProfile,
  onOpen,
}: {
  item: FlowQueueItem;
  selected: boolean;
  contextRemoveCount: number;
  onToggleSelected: () => void;
  onRemove: () => void;
  onContextRemove: () => void;
  onAssignProfile: (profile: AnalysisProfile) => void;
  onOpen: () => void;
}) {
  const meta = STATUS_META[item.status];
  const isOpenable = Boolean(item.job || item.file || item.storedMediaUrl || item.tedialItem);
  const detailLine = flowItemDetail(item);
  const sourceLabel = item.source === 'tedial' ? 'Tedial' : 'Yüklenen';
  return (
    <ContextMenu>
      <ContextMenuTrigger asChild>
        <div className={`rounded-sm border px-2 py-1.5 ${selected ? 'border-info-border bg-info-subtle/30' : 'border-border-subtle bg-surface/45'}`}>
          <div className="grid grid-cols-[auto_minmax(0,1fr)_auto] items-start gap-2">
            <input type="checkbox" checked={selected} onChange={onToggleSelected} className="mt-0.5" />
            <div className="min-w-0">
              <div className="flex min-w-0 items-center gap-1.5">
                <div className="min-w-0 truncate text-xs font-semibold leading-5 text-foreground-strong" title={item.name}>{item.name}</div>
                <StatusIcon status={item.status} />
                <Badge variant={meta.variant} className="shrink-0 px-1.5 py-0 text-[9px]">{meta.label}</Badge>
              </div>
              <div className="flex min-w-0 items-center gap-1.5 text-[10px] leading-4 text-foreground-muted">
                <Badge variant="outline" className="px-1.5 py-0 text-[9px]">{sourceLabel}</Badge>
                <span className="truncate">{analysisProfileLabel(item.profile)}</span>
              </div>
              <div className="truncate text-[10px] leading-4 text-foreground-muted" title={detailLine}>{detailLine}</div>
            </div>
            <div className="flex shrink-0 items-start justify-end gap-1">
              <Button size="xs" variant="outline" disabled={!isOpenable} onClick={onOpen}>Aç</Button>
              <Button size="icon-xs" variant="ghost" onClick={onRemove} disabled={item.status === 'running'} title="Kuyruktan kaldır">
                <X className="h-3 w-3" />
              </Button>
            </div>
          </div>
        </div>
      </ContextMenuTrigger>
      <ContextMenuContent className="border-border-mitas bg-app-shell text-foreground-default">
        <ContextMenuItem disabled={!isOpenable} onSelect={onOpen} className="text-xs focus:bg-surface-elevated focus:text-foreground-strong">
          Playerda aç
        </ContextMenuItem>
        <ContextMenuItem disabled={contextRemoveCount === 0} onSelect={onContextRemove} className="text-xs text-danger focus:bg-danger-subtle focus:text-danger">
          {contextRemoveCount > 1 ? `${contextRemoveCount} seçiliyi sil` : 'Sil'}
        </ContextMenuItem>
        <ContextMenuSeparator className="bg-border-subtle" />
        <ContextMenuRadioGroup value={item.profile} onValueChange={(value) => onAssignProfile(value as AnalysisProfile)}>
          {ANALYSIS_PROFILE_OPTIONS.map((option) => (
            <ContextMenuRadioItem key={option.value} value={option.value} className="text-xs focus:bg-surface-elevated focus:text-foreground-strong">
              {option.label}
            </ContextMenuRadioItem>
          ))}
        </ContextMenuRadioGroup>
      </ContextMenuContent>
    </ContextMenu>
  );
}

function flowItemDetail(item: FlowQueueItem): string {
  if (item.source === 'upload') {
    const path = item.job?.original_source_path || item.job?.input_path || item.job?.summary?.input_path || displaySourcePath(item) || uploadSourcePath(item.file);
    const size = item.file ? formatBytes(item.file.size) : item.sizeBytes ? formatBytes(item.sizeBytes) : item.message || '-';
    const statusMessage = item.status !== 'waiting' && item.message && item.message !== size ? ` · ${item.message}` : '';
    return `${size} · Kaynak: ${path}${statusMessage}`;
  }

  const id = item.tedialItem?.trt_id || item.tedialItem?.asset_id || item.message || '-';
  const statusMessage = item.status !== 'waiting' && item.message && item.message !== id ? ` · ${item.message}` : '';
  return `${id} · Kaynak: Tedial${statusMessage}`;
}

function withStoredUploadMedia(item: FlowQueueItem, stored: {
  stored_media_url: string;
  stored_media_path: string;
  size_bytes: number;
}): FlowQueueItem {
  return {
    ...item,
    storedMediaUrl: stored.stored_media_url,
    storedMediaPath: stored.stored_media_path,
    sourcePath: shouldPreferStoredPath(item.sourcePath, item.name) ? stored.stored_media_path : item.sourcePath,
    sizeBytes: stored.size_bytes,
    message: item.message || formatBytes(stored.size_bytes),
  };
}

function displaySourcePath(item: FlowQueueItem): string | undefined {
  if (item.storedMediaPath && shouldPreferStoredPath(item.sourcePath, item.name)) {
    return item.storedMediaPath;
  }
  return item.sourcePath || item.storedMediaPath;
}

function shouldPreferStoredPath(sourcePath: string | undefined, filename: string): boolean {
  if (!sourcePath) return true;
  const normalized = sourcePath.trim();
  return !normalized || normalized === filename || normalized === 'Kaynak bilinmiyor';
}

function uploadSourcePath(file?: File): string {
  if (!file) return 'Kaynak bilinmiyor';
  const sourcePath = localFileSourcePath(file);
  if (sourcePath) return sourcePath;
  return file.name;
}

async function persistQueueUpload(itemId: string, file: File): Promise<{
  stored_media_url: string;
  stored_media_path: string;
  size_bytes: number;
}> {
  const params = new URLSearchParams({ filename: file.name });
  const response = await fetch(`/api/flow-queue/uploads/${encodeURIComponent(itemId)}?${params.toString()}`, {
    method: 'POST',
    headers: {
      'content-type': file.type || 'application/octet-stream',
    },
    body: file,
  });
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return response.json();
}

function mediaTypeForQueueFile(file: File): string | undefined {
  if (file.type && file.type !== 'application/octet-stream') return file.type;
  const ext = file.name.split('.').pop()?.toLowerCase();
  if (!ext) return undefined;
  if (['mp4', 'm4v', 'mov'].includes(ext)) return 'video/mp4';
  if (ext === 'webm') return 'video/webm';
  if (ext === 'ogg' || ext === 'ogv') return 'video/ogg';
  if (ext === 'wav') return 'audio/wav';
  if (ext === 'mp3') return 'audio/mpeg';
  if (ext === 'm4a') return 'audio/mp4';
  return undefined;
}

function StatusIcon({ status }: { status: FlowItemStatus }) {
  if (status === 'done') return <CheckCircle2 className="h-3.5 w-3.5 text-success" />;
  if (status === 'failed') return <AlertCircle className="h-3.5 w-3.5 text-danger" />;
  if (status === 'stopped') return <AlertCircle className="h-3.5 w-3.5 text-foreground-muted" />;
  if (status === 'running') return <Loader2 className="h-3.5 w-3.5 animate-spin text-info" />;
  return <Clock3 className="h-3.5 w-3.5 text-warning" />;
}

function TedialSearchIndicator({ state }: { state: 'idle' | 'searching' | 'found' | 'missing' | 'error' }) {
  if (state === 'idle') return null;
  if (state === 'searching') return <Loader2 className="absolute right-2 top-2 h-3.5 w-3.5 animate-spin text-info" />;
  if (state === 'found') return <CheckCircle2 className="absolute right-2 top-2 h-3.5 w-3.5 text-success" />;
  if (state === 'missing' || state === 'error') return <AlertCircle className="absolute right-2 top-2 h-3.5 w-3.5 text-danger" />;
  return null;
}

const FLOW_QUEUE_DB_NAME = 'mitas-flow-queue';
const FLOW_QUEUE_DB_VERSION = 1;
const FLOW_QUEUE_STORE = 'state';
const FLOW_QUEUE_STATE_ID = 'main';
const FLOW_QUEUE_FALLBACK_KEY = 'mitas.flow.queue.fallback.v1';

async function loadFlowQueueState(): Promise<PersistedFlowQueueState | null> {
  const [serverState, browserState] = await Promise.all([
    loadFlowQueueServerState(),
    loadFlowQueueBrowserState(),
  ]);
  if (serverState && browserState) {
    return chooseFlowQueueState(serverState, browserState);
  }
  return serverState ?? browserState;
}

async function loadFlowQueueBrowserState(): Promise<PersistedFlowQueueState | null> {
  try {
    const database = await openFlowQueueDatabase();
    const indexedState = await new Promise<PersistedFlowQueueState | null>((resolve, reject) => {
      const transaction = database.transaction(FLOW_QUEUE_STORE, 'readonly');
      const store = transaction.objectStore(FLOW_QUEUE_STORE);
      const request = store.get(FLOW_QUEUE_STATE_ID);
      request.onsuccess = () => resolve((request.result as PersistedFlowQueueState | undefined) ?? null);
      request.onerror = () => reject(request.error);
    });
    return indexedState ?? loadFlowQueueFallbackState();
  } catch {
    return loadFlowQueueFallbackState();
  }
}

function chooseFlowQueueState(serverState: PersistedFlowQueueState, browserState: PersistedFlowQueueState): PersistedFlowQueueState {
  const serverCount = serverState.items?.length ?? 0;
  const browserCount = browserState.items?.length ?? 0;
  if (serverCount === 0 && browserCount > 0) {
    return browserState;
  }
  if (serverCount > 0 && browserCount === 0) {
    return serverState;
  }
  return flowQueueTimestamp(browserState) > flowQueueTimestamp(serverState) ? browserState : serverState;
}

function flowQueueTimestamp(state: PersistedFlowQueueState): number {
  const value = Date.parse(state.updatedAt || '');
  return Number.isFinite(value) ? value : 0;
}

async function saveFlowQueueState(state: { items: FlowQueueItem[]; bulkProfile: AnalysisProfile }): Promise<void> {
  const payload: PersistedFlowQueueState = {
    id: FLOW_QUEUE_STATE_ID,
    updatedAt: new Date().toISOString(),
    bulkProfile: state.bulkProfile,
    items: state.items,
  };
  const metadataPayload = {
    ...payload,
    items: payload.items.map(toFallbackFlowItem),
  };
  saveFlowQueueFallbackState(metadataPayload);
  void saveFlowQueueServerState(metadataPayload);
  const database = await openFlowQueueDatabase();
  return new Promise((resolve, reject) => {
    const transaction = database.transaction(FLOW_QUEUE_STORE, 'readwrite');
    const store = transaction.objectStore(FLOW_QUEUE_STORE);
    store.put(metadataPayload);  // File objesi (büyük video) DEĞİL — sadece metadata. 50 büyük dosyada IndexedDB kota patlamasını (KAYIT HATASI) önler.
    transaction.oncomplete = () => resolve();
    transaction.onerror = () => reject(transaction.error);
    transaction.onabort = () => reject(transaction.error);
  });
}

async function loadFlowQueueServerState(): Promise<PersistedFlowQueueState | null> {
  try {
    const response = await fetch('/api/flow-queue', { cache: 'no-store' });
    if (!response.ok) return null;
    const payload = await response.json() as PersistedFlowQueueState;
    return Array.isArray(payload.items) ? payload : null;
  } catch {
    return null;
  }
}

async function saveFlowQueueServerState(state: PersistedFlowQueueState): Promise<void> {
  try {
    await fetch('/api/flow-queue', {
      method: 'PUT',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(state),
    });
  } catch {
    // Browser storage still keeps a local copy if the backend is momentarily down.
  }
}

function loadFlowQueueFallbackState(): PersistedFlowQueueState | null {
  if (typeof window === 'undefined') return null;
  try {
    const parsed = JSON.parse(window.localStorage.getItem(FLOW_QUEUE_FALLBACK_KEY) || 'null');
    if (!parsed || typeof parsed !== 'object') return null;
    const state = parsed as PersistedFlowQueueState;
    return Array.isArray(state.items) ? state : null;
  } catch {
    return null;
  }
}

function saveFlowQueueFallbackState(state: PersistedFlowQueueState) {
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.setItem(FLOW_QUEUE_FALLBACK_KEY, JSON.stringify({
      ...state,
      items: state.items.map(toFallbackFlowItem),
    }));
  } catch {
    // IndexedDB remains the primary durable store for File objects.
  }
}

function toFallbackFlowItem(item: FlowQueueItem): FlowQueueItem {
  return {
    ...item,
    file: undefined,
    job: item.job ? compactAsrJob(item.job) : undefined,
  };
}

function compactAsrJob(job: AsrJob): AsrJob {
  return {
    ...job,
    transcript: '',
    segments: [],
    logs: [],
    timeline_events: [],
  };
}

function openFlowQueueDatabase(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    if (typeof indexedDB === 'undefined') {
      reject(new Error('indexeddb_unavailable'));
      return;
    }
    const request = indexedDB.open(FLOW_QUEUE_DB_NAME, FLOW_QUEUE_DB_VERSION);
    request.onupgradeneeded = () => {
      const database = request.result;
      if (!database.objectStoreNames.contains(FLOW_QUEUE_STORE)) {
        database.createObjectStore(FLOW_QUEUE_STORE, { keyPath: 'id' });
      }
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

function restorePersistedFlowItem(item: FlowQueueItem): FlowQueueItem {
  const source: FlowItemSource = item.source || (item.tedialItem || item.id?.startsWith('tedial-') ? 'tedial' : 'upload');
  const restored = { ...item, source };
  if (restored.status === 'running') {
    return {
      ...restored,
      status: 'stopped',
      message: restored.job
        ? 'Uygulama yeniden açıldı; backend işi logda devam etmiş olabilir.'
        : 'Uygulama yeniden açıldı; tekrar başlatılabilir.',
    };
  }
  if (restored.source === 'upload' && !restored.file && !restored.job && !restored.storedMediaUrl) {
    return {
      ...restored,
      status: 'failed',
      message: 'Yerel dosya geri yüklenemedi.',
    };
  }
  return restored;
}

function formatBytes(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes <= 0) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB'];
  let value = bytes;
  let index = 0;
  while (value >= 1024 && index < units.length - 1) {
    value /= 1024;
    index += 1;
  }
  return `${value.toFixed(index === 0 ? 0 : 1)} ${units[index]}`;
}
