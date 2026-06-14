import {
  AlertCircle,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Clock3,
  FileVideo,
  FolderOpen,
  Loader2,
  Play,
  Search,
  X,
} from 'lucide-react';
import { useEffect, useRef, useState, type DragEvent } from 'react';
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
  uploading?: boolean;
  clipId?: string;  // sunucu worker'in pipeline media_id'si — canli adim-logu (/api/events?media_id) icin
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
  browseSignal?: number;  // Header'daki "Gözat" butonundan artan sayaç → gözat tarayıcısını aç
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

export function FlowQueuePanel({ onOpenMedia, browseSignal }: FlowQueuePanelProps) {
  const itemsRef = useRef<FlowQueueItem[]>([]);
  const isProcessingRef = useRef(false);
  const stopModeRef = useRef<FlowStopMode>('none');
  const hasLoadedPersistedQueueRef = useRef(false);
  const skipNextPersistenceEffectRef = useRef(true);
  const uploadsRef = useRef<Map<string, Promise<void>>>(new Map());  // devam eden klip yüklemeleri (id → söz); Başlat bunları bekler
  const lastPctRef = useRef<Record<string, number>>({});            // son raporlanan tam yüzde — gereksiz render önler
  const isPreparingRef = useRef(false);                              // Başlat yüklemeleri beklerken poll'un isProcessing'i ezmesini engeller
  const [items, setItems] = useState<FlowQueueItem[]>([]);
  const [uploadProgress, setUploadProgress] = useState<Record<string, number>>({});  // SADECE görsel — kalıcılaştırılmaz
  const [selectedIds, setSelectedIds] = useState<Set<string>>(() => new Set());
  const [bulkProfile, setBulkProfile] = useState<AnalysisProfile>('film_dizi');
  const [tedialQuery, setTedialQuery] = useState('');
  const [tedialCandidate, setTedialCandidate] = useState<TedialSearchResult | null>(null);
  const [lastTedialQuery, setLastTedialQuery] = useState('');
  const [tedialSearchState, setTedialSearchState] = useState<'idle' | 'searching' | 'found' | 'missing' | 'error'>('idle');
  const [tedialMessage, setTedialMessage] = useState('');
  const [isDragActive, setIsDragActive] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [isPreparing, setIsPreparing] = useState(false);
  const [stopMode, setStopMode] = useState<FlowStopMode>('none');
  const [persistenceStatus, setPersistenceStatus] = useState<'loading' | 'saved' | 'error'>('loading');
  const [localDirBusy, setLocalDirBusy] = useState(false);
  const [selectedFilms, setSelectedFilms] = useState<Set<string>>(() => new Set());  // gözatta tek tek seçilen videolar (klasör başına)
  const [browseOpen, setBrowseOpen] = useState(false);
  const [browsePath, setBrowsePath] = useState('');
  const [browseLoading, setBrowseLoading] = useState(false);
  const [browseData, setBrowseData] = useState<{ path: string; parent: string | null; dirs: string[]; films: string[]; film_count: number } | null>(null);

  useEffect(() => {
    let cancelled = false;
    // SUNUCU worker durumunu da çek: koşuyorsa server queue.json OTORİTEDİR. Yenileme/remount'ta
    // 'running' öğeyi 'stopped'a çevirip geri-YAZMA → worker'ı ezme ("İşleniyor" iken "Durduruldu" görünme).
    Promise.all([
      loadFlowQueueState(),
      fetch('/api/flow-queue/worker', { cache: 'no-store' })
        .then((response) => (response.ok ? response.json() : null))
        .then((worker) => Boolean(worker?.running))
        .catch(() => false),
    ])
      .then(([state, workerRunning]) => {
        if (cancelled) return;
        const restoredItems = (state?.items ?? []).map((item) => restorePersistedFlowItem(item, workerRunning));
        const restoredBulkProfile = state?.bulkProfile ?? 'film_dizi';
        itemsRef.current = restoredItems;
        setItems(restoredItems);
        if (state?.bulkProfile) {
          setBulkProfile(restoredBulkProfile);
        }
        // F5: SERVER = tek otorite — UI yükleme/yenilemede durumu GERİ-YAZMAZ (writeback desync'i biter).
        // Kuyruk yalnız enqueue/stop/retry/clear endpoint'leriyle değişir; UI okur + komut gönderir.
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

  // itemsRef.current'i SENKRON güncelle (React state flush'ını bekleme). Başlat, yüklemeler
  // bittiği an itemsRef'ten storedMediaPath'i okuyup sunucuya yazıyor — flush gecikmesi yarış yaratmasın.
  const updateItems = (updater: (current: FlowQueueItem[]) => FlowQueueItem[]) => {
    const next = updater(itemsRef.current);
    itemsRef.current = next;
    setItems(next);
    if (hasLoadedPersistedQueueRef.current && !isProcessingRef.current) {
      saveFlowQueueState({ items: next, bulkProfile })
        .then(() => setPersistenceStatus('saved'))
        .catch(() => setPersistenceStatus('error'));
    }
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
        const serverItems: Array<{ id: string; status?: FlowItemStatus; message?: string; clipId?: string }> = Array.isArray(q?.items) ? q.items : [];
        if (serverItems.length) {
          const byId = new Map(serverItems.map((s) => [s.id, s] as const));
          const next = itemsRef.current.map((it) => {
            if (it.uploading) return it;  // aktif yükleme — yerel "Yükleniyor" durumunu sunucu durumuyla ezme
            const s = byId.get(it.id);
            return s ? { ...it, status: (s.status as FlowItemStatus) ?? it.status, message: s.message ?? it.message, clipId: s.clipId ?? it.clipId } : it;
          });
          itemsRef.current = next;
          setItems(next);
        }
      }
      // Başlat yüklemeleri beklerken (isPreparing) worker henüz koşmaz → poll isProcessing'i false'a
      // çekip guard'ları açmasın / çift-Başlat'a izin vermesin.
      if (!isPreparingRef.current) {
        isProcessingRef.current = running;
        setIsProcessing(running);
        if (!running && stopModeRef.current !== 'none') {
          stopModeRef.current = 'none';
          setStopMode('none');
        }
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
    const nextItems: FlowQueueItem[] = files.map((file) => ({
      id: `upload-${Date.now()}-${Math.random().toString(16).slice(2)}`,
      source: 'upload' as const,
      name: file.name,
      profile: bulkProfile,
      status: 'waiting' as const,
      file,
      sourcePath: uploadSourcePath(file),
      mediaType: mediaTypeForQueueFile(file),
      sizeBytes: file.size,
      uploading: true,           // klip sunucuya kopyalanıyor — Başlat bunu bekler
      message: 'Yükleniyor…',
    }));
    updateItems((current) => [...current, ...nextItems]);
    nextItems.forEach((item) => {
      const file = item.file;
      if (!file) return;
      const uploadPromise = persistQueueUpload(item.id, file, (pct) => {
        const rounded = Math.round(pct);
        if (lastPctRef.current[item.id] === rounded) return;  // sadece yüzde değişince güncelle
        lastPctRef.current[item.id] = rounded;
        setUploadProgress((current) => ({ ...current, [item.id]: rounded }));  // ayrı state — kalıcılaştırılmaz
      })
        .then((stored) => {
          updateItems((current) => current.map((currentItem) => currentItem.id === item.id
            ? { ...withStoredUploadMedia({ ...currentItem, uploading: false }, stored), message: formatBytes(stored.size_bytes) }
            : currentItem));
        })
        .catch((error) => {
          // Yükleme başarısızsa NET hata + 'failed' → worker'a yarım/yolsuz öğe gitmez ("Video bulunamadı" gizemini önler).
          updateItems((current) => current.map((currentItem) => currentItem.id === item.id
            ? { ...currentItem, uploading: false, status: 'failed', message: `Yükleme başarısız: ${error instanceof Error ? error.message : 'hata'}` }
            : currentItem));
        })
        .finally(() => {
          uploadsRef.current.delete(item.id);
          delete lastPctRef.current[item.id];
          setUploadProgress((current) => {
            if (!(item.id in current)) return current;
            const next = { ...current };
            delete next[item.id];
            return next;
          });
        });
      uploadsRef.current.set(item.id, uploadPromise);
    });
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
    // F6: terminal öğeleri hem yerel görünümden hem SUNUCU kuyruğundan sil (server-otorite temizlik).
    const terminal = new Set(['done', 'partial', 'failed', 'stopped']);
    updateItems((current) => current.filter((item) => !terminal.has(item.status)));
    void fetch('/api/flow-queue/clear', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ all: false }),
    }).catch(() => {});
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
    isPreparingRef.current = true;
    setIsPreparing(true);
    let started = false;
    try {
      // 1) DEVAM EDEN YÜKLEMELERİ BİTİR — "yükle → hemen Başlat" yarışını kapatır.
      //    Klip sunucuya kopyalanmadan worker'a gidilirse storedMediaPath yok → "Video bulunamadı".
      if (uploadsRef.current.size > 0) {
        await Promise.allSettled([...uploadsRef.current.values()]);
      }
      // 2) Hâlâ sunucu-yolu olmayan upload öğelerini NET mesajla 'failed' yap (worker'a gönderme).
      const unresolvedIds = new Set(
        itemsRef.current
          .filter((it) => it.status === 'waiting' && it.source === 'upload' && !it.storedMediaPath && !it.storedMediaUrl)
          .map((it) => it.id),
      );
      if (unresolvedIds.size > 0) {
        updateItems((current) => current.map((it) => unresolvedIds.has(it.id)
          ? { ...it, status: 'failed', uploading: false, message: 'Yükleme tamamlanamadı — dosyayı tekrar ekleyin.' }
          : it));
      }
      // 3) Başlatılacak gerçek bekleyen iş kaldı mı?
      if (!itemsRef.current.some((it) => it.status === 'waiting')) {
        return;  // hepsi yarım/başarısız — worker'ı boşuna başlatma
      }
      // 4) Kuyruğu sunucuya yaz (worker queue.json'dan okur) + SUNUCU-TARAFI worker'ı başlat.
      await saveFlowQueueServerState({
        id: FLOW_QUEUE_STATE_ID,
        updatedAt: new Date().toISOString(),
        bulkProfile,
        items: itemsRef.current.map(toFallbackFlowItem),
      });
      await fetch('/api/flow-queue/run', { method: 'POST' });
      started = true;
      await pollServerQueue();
    } catch {
      // başlatılamazsa pollServerQueue gerçek durumu yansıtır
    } finally {
      isPreparingRef.current = false;
      setIsPreparing(false);
      if (!started) {
        // Worker başlamadı (başlatacak iş yok / hata) → butonu serbest bırak.
        isProcessingRef.current = false;
        setIsProcessing(false);
      }
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
    // SUNUCU worker'ı durdur + çalışan pipeline'ı process-AĞACIYLA öldür (gerçek "net kes").
    // F3: stop'a {force:true} → worker alt-sürecini taskkill /T /F; abort da _pipeline_proc'u öldürür (F2).
    void fetch('/api/flow-queue/stop', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ force: true }),
    }).catch(() => {});
    void fetch('/api/pipeline/abort', { method: 'POST' }).catch(() => {});
  };

  // (eski client-tarafı processItem KALDIRILDI — kuyruk artık SUNUCU worker'da koşuyor: /api/flow-queue/run)

  const selectedCount = selectedIds.size;
  const pendingCount = items.filter((item) => item.status === 'waiting').length;
  const uploadingCount = items.filter((item) => item.uploading).length;
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
  // Klasörün TAMAMINI (dir) ya da SEÇİLİ videoları (paths) PATH ile kuyruğa ekle (UPLOAD YOK).
  const enqueueLocal = async (opts: { dir?: string; paths?: string[] }) => {
    const dir = (opts.dir ?? '').trim();
    const paths = opts.paths ?? [];
    if ((!dir && paths.length === 0) || localDirBusy) return;
    setLocalDirBusy(true);
    try {
      const body: Record<string, unknown> = { profile: bulkProfile, replace: false };
      if (dir) body.dir = dir;
      if (paths.length) body.paths = paths;
      const res = await fetch('/api/flow-queue/enqueue-local', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        window.alert(`Eklenemedi: ${data?.detail ?? res.status}`);
        return;
      }
      window.alert(`${data.added} video PATH ile eklendi (upload yok). Toplam: ${data.total}. Worker başladı.`);
      setSelectedFilms(new Set());
      setBrowseOpen(false);
    } catch (err) {
      window.alert(`Eklenemedi: ${String(err)}`);
    } finally {
      setLocalDirBusy(false);
    }
  };

  // Server-tarafı klasör gezgini (localhost = kullanıcının makinesi): sürücü/klasör tıkla, film say, ekle.
  const fsBrowse = async (path: string) => {
    setBrowseLoading(true);
    try {
      const res = await fetch(`/api/fs/browse?path=${encodeURIComponent(path)}`, { cache: 'no-store' });
      if (!res.ok) { window.alert('Klasör açılamadı'); return; }
      const data = await res.json();
      setBrowseData(data);
      setBrowsePath(data.path ?? '');
      setSelectedFilms(new Set());  // klasör değişti → seçimi temizle (seçim klasöre özel)
    } catch (err) {
      window.alert(`Gezgin hatası: ${String(err)}`);
    } finally {
      setBrowseLoading(false);
    }
  };
  const openBrowser = () => { setBrowseOpen(true); void fsBrowse(browseData?.path ?? ''); };
  const joinPath = (base: string, name: string) => (base ? base.replace(/[\\/]+$/, '') + '\\' : '') + name;

  // Header'daki tek "Gözat" butonu (browseSignal sayacı artar) → gözat tarayıcısını aç.
  useEffect(() => {
    if (browseSignal && browseSignal > 0) {
      openBrowser();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [browseSignal]);

  return (
    <div className="flex h-full min-h-0 w-full min-w-0 max-w-full flex-col overflow-hidden bg-app-shell">
      <div className="border-b border-border-subtle bg-surface/40 p-2.5">
        {/* Kaynak ekleme TEK noktadan: Header'daki "Gözat" butonu (browseSignal) bu tarayıcıyı açar. */}
        {browseOpen ? (
          <div className="mt-1.5 rounded-sm border border-border-mitas bg-app-shell/60 p-2">
            <div className="mb-1 flex items-center gap-1">
              <Button size="xs" variant="ghost" className="px-1" onClick={() => setBrowseOpen(false)} title="Kapat">
                <X className="h-3 w-3" />
              </Button>
              <input
                type="text"
                value={browsePath}
                onChange={(event) => setBrowsePath(event.target.value)}
                onKeyDown={(event) => { if (event.key === 'Enter') void fsBrowse(browsePath); }}
                placeholder="Örn: E:\filmler  veya  V:\klasör  (UNC için eşlenmiş sürücü harfi)"
                className="h-7 min-w-0 flex-1 rounded-sm border border-border-mitas bg-app-shell/80 px-2 text-[11px] text-foreground-default placeholder:text-foreground-muted"
              />
              <Button size="xs" variant="outline" className="px-2" onClick={() => void fsBrowse(browsePath)}>Git</Button>
            </div>
            {/* UNC yolu için bilgi notu */}
            {(browsePath.startsWith('\\') || browsePath.startsWith('/')) ? (
              <div className="mb-1 rounded-sm bg-warning-subtle/40 px-2 py-1 text-[10px] text-warning">
                UNC yolu (\\sunucu\paylaşım) doğrudan erişilemiyor olabilir. Sürücü harfiyle eşlenmiş yolu kullanın —
                örn. \\depo01cifs...\sas_h264 → V:\
              </div>
            ) : null}
            <ScrollArea className="max-h-52">
              <div className="flex flex-col gap-0.5 pr-1">
                {browseData?.parent != null ? (
                  <button type="button" className="rounded-sm px-1.5 py-1 text-left text-[11px] text-foreground-muted hover:bg-surface-elevated" onClick={() => void fsBrowse(browseData?.parent ?? '')}>
                    ↑ üst klasör
                  </button>
                ) : null}
                {browseLoading ? <span className="px-1.5 py-1 text-[11px] text-foreground-muted">Yükleniyor…</span> : null}
                {(browseData?.dirs ?? []).map((dirName) => (
                  <button
                    type="button"
                    key={dirName}
                    className="flex items-center gap-1 rounded-sm px-1.5 py-1 text-left text-[11px] hover:bg-surface-elevated"
                    onClick={() => void fsBrowse(joinPath(browseData?.path ?? '', dirName))}
                  >
                    <FolderOpen className="h-3 w-3 shrink-0" />
                    <span className="truncate">{dirName}</span>
                  </button>
                ))}
                {(browseData?.films ?? []).length > 0 ? (
                  <div className="mt-0.5 border-t border-border-subtle pt-0.5">
                    <button
                      type="button"
                      className="mb-0.5 w-full rounded-sm px-1.5 py-0.5 text-left text-[10px] font-semibold text-foreground-muted hover:bg-surface-elevated"
                      onClick={() => {
                        const all = browseData?.films ?? [];
                        setSelectedFilms((current) => current.size === all.length ? new Set() : new Set(all));
                      }}
                    >
                      {selectedFilms.size === (browseData?.films?.length ?? 0) && (browseData?.films?.length ?? 0) > 0 ? '☑ Seçimi bırak' : '☐ Tümünü seç'} — {browseData?.film_count ?? 0} video {selectedFilms.size > 0 ? `(${selectedFilms.size} seçili)` : ''}
                    </button>
                    {(browseData?.films ?? []).map((filmName) => (
                      <label
                        key={filmName}
                        className="flex cursor-pointer items-center gap-1 rounded-sm px-1.5 py-0.5 text-[10px] text-foreground-muted hover:bg-surface-elevated"
                        title={filmName}
                      >
                        <input
                          type="checkbox"
                          checked={selectedFilms.has(filmName)}
                          onChange={() => setSelectedFilms((current) => {
                            const next = new Set(current);
                            if (next.has(filmName)) { next.delete(filmName); } else { next.add(filmName); }
                            return next;
                          })}
                          className="shrink-0"
                        />
                        <FileVideo className="h-2.5 w-2.5 shrink-0 text-info" />
                        <span className="truncate">{filmName}</span>
                      </label>
                    ))}
                  </div>
                ) : null}
                {!browseLoading && (browseData?.dirs?.length ?? 0) === 0 && (browseData?.film_count ?? 0) === 0 ? (
                  <span className="px-1.5 py-1 text-[11px] text-foreground-muted">(boş — desteklenen format: mp4, mxf, mkv, avi, mov)</span>
                ) : null}
              </div>
            </ScrollArea>
            {selectedFilms.size > 0 ? (
              <Button
                size="sm"
                className="mt-1.5 w-full justify-center gap-1 px-2"
                disabled={localDirBusy}
                onClick={() => void enqueueLocal({ paths: [...selectedFilms].map((name) => joinPath(browseData?.path ?? '', name)) })}
              >
                {localDirBusy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Play className="h-3.5 w-3.5" />}
                Seçili videoları ekle ({selectedFilms.size})
              </Button>
            ) : (
              <Button
                size="sm"
                className="mt-1.5 w-full justify-center gap-1 px-2"
                disabled={!browseData?.path || (browseData?.film_count ?? 0) === 0 || localDirBusy}
                onClick={() => void enqueueLocal({ dir: browseData?.path })}
              >
                {localDirBusy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Play className="h-3.5 w-3.5" />}
                Bu klasörü ekle ({browseData?.film_count ?? 0} film)
              </Button>
            )}
          </div>
        ) : null}
        <div className="mt-1.5 grid grid-cols-3 gap-1.5">
          <Button size="sm" className="w-full justify-center gap-1 px-1.5" onClick={processQueue} disabled={isProcessing || pendingCount === 0} title={uploadingCount > 0 ? 'Yüklemeler bitince otomatik başlar' : undefined}>
            {isProcessing ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Play className="h-3.5 w-3.5" />}
            {isPreparing ? 'Hazırlanıyor…' : uploadingCount > 0 ? `Başlat (${uploadingCount} yükleniyor)` : 'Başlat'}
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
              uploadPct={uploadProgress[item.id]}
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
  uploadPct,
  selected,
  contextRemoveCount,
  onToggleSelected,
  onRemove,
  onContextRemove,
  onAssignProfile,
  onOpen,
}: {
  item: FlowQueueItem;
  uploadPct?: number;
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
  const detailLine = flowItemDetail(item, uploadPct);
  const sourceLabel = item.source === 'tedial' ? 'Tedial' : 'Yüklenen';
  const isRunning = item.status === 'running';
  const clipId = item.clipId || deriveClipId(item.name);  // sunucu yoksa dosya adından türet (pipeline sanitize ile aynı)
  const [expanded, setExpanded] = useState(isRunning);
  // Çalışmaya başlayınca adım-logunu kendiliğinden aç + bu koşunun başlangıç anını yakala (eski koşu olaylarını ele)
  const runSinceRef = useRef<string | undefined>(undefined);
  useEffect(() => {
    if (isRunning) {
      setExpanded(true);
      if (!runSinceRef.current) {
        runSinceRef.current = new Date(Date.now() - 8000).toISOString();  // 8 sn pay: media_imported gibi ilk olayları da içine al
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isRunning]);
  const logActive = isRunning || item.status === 'waiting';
  return (
    <ContextMenu>
      <ContextMenuTrigger asChild>
        <div className={`rounded-sm border px-2 py-1.5 ${selected ? 'border-info-border bg-info-subtle/30' : 'border-border-subtle bg-surface/45'}`}>
          <div className="grid grid-cols-[auto_minmax(0,1fr)_auto] items-start gap-2">
            <input type="checkbox" checked={selected} onChange={onToggleSelected} className="mt-0.5" />
            <div className="min-w-0">
              <div className="flex min-w-0 items-center gap-1.5">
                <div className="min-w-0 truncate text-xs font-semibold leading-5 text-foreground-strong" title={item.name}>{item.name}</div>
                {item.uploading ? <Loader2 className="h-3.5 w-3.5 shrink-0 animate-spin text-info" /> : <StatusIcon status={item.status} />}
                <Badge variant={item.uploading ? 'outline' : meta.variant} className="shrink-0 px-1.5 py-0 text-[9px]">{item.uploading ? 'Yükleniyor' : meta.label}</Badge>
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
          {/* Canlı adım-logu: VİTOS gibi her aşama tek tek görünür (filme-bağlı /api/events?media_id). */}
          <button
            type="button"
            onClick={() => setExpanded((v) => !v)}
            className="mt-1 flex w-full items-center gap-1 rounded-sm px-0.5 py-0.5 text-[10px] text-foreground-muted transition-colors hover:text-foreground-strong"
          >
            {expanded ? <ChevronDown className="h-3 w-3 shrink-0" /> : <ChevronRight className="h-3 w-3 shrink-0" />}
            <span className="font-semibold">Adımlar</span>
            {isRunning ? <span className="h-1.5 w-1.5 shrink-0 animate-pulse rounded-full bg-info" /> : null}
          </button>
          {expanded ? (
            <FlowItemLog clipId={clipId} active={logActive} since={runSinceRef.current} />
          ) : null}
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

function flowItemDetail(item: FlowQueueItem, uploadPct?: number): string {
  if (item.source === 'upload') {
    if (item.uploading) {
      const size = item.file ? formatBytes(item.file.size) : item.sizeBytes ? formatBytes(item.sizeBytes) : '';
      const pctText = typeof uploadPct === 'number' ? ` %${uploadPct}` : '…';
      return `Yükleniyor${pctText}${size ? ` · ${size}` : ''}`;
    }
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

function persistQueueUpload(
  itemId: string,
  file: File,
  onProgress?: (pct: number) => void,
): Promise<{
  stored_media_url: string;
  stored_media_path: string;
  size_bytes: number;
}> {
  // XHR (fetch DEĞİL): yükleme ilerlemesi (upload.onprogress) yalnız XHR'de var → büyük klipte
  // kullanıcı "Yükleniyor %x" görür ve Başlat bu söz bitene kadar bekler.
  const params = new URLSearchParams({ filename: file.name });
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open('POST', `/api/flow-queue/uploads/${encodeURIComponent(itemId)}?${params.toString()}`);
    xhr.setRequestHeader('content-type', file.type || 'application/octet-stream');
    xhr.upload.onprogress = (event) => {
      if (onProgress && event.lengthComputable && event.total > 0) {
        onProgress((event.loaded / event.total) * 100);
      }
    };
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          resolve(JSON.parse(xhr.responseText));
        } catch {
          reject(new Error('Yükleme yanıtı çözümlenemedi'));
        }
      } else {
        reject(new Error(xhr.responseText || `Yükleme başarısız (HTTP ${xhr.status})`));
      }
    };
    xhr.onerror = () => reject(new Error('Ağ hatası — yükleme tamamlanamadı'));
    xhr.onabort = () => reject(new Error('Yükleme iptal edildi'));
    xhr.send(file);
  });
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

// ---------------------------------------------------------------------------
// Canlı adım-logu (per-film) — VİTOS tarzı: her pipeline aşaması tek tek, sıralı,
// renkli, süreli. Pipeline zaten zengin olayları system_events.jsonl'e media_id ile
// yazıyor; burada o filmin olaylarını /api/events?media_id ile canlı çekip gösteriyoruz.
// ---------------------------------------------------------------------------

type LogTone = 'info' | 'success' | 'warn' | 'error' | 'progress' | 'muted';

const TONE_CLASS: Record<LogTone, string> = {
  info: 'text-info',
  success: 'text-success',
  warn: 'text-warning',
  error: 'text-danger',
  progress: 'text-info',
  muted: 'text-foreground-muted',
};

// olay türü → insan-okunur aşama etiketi + renk tonu (VİTOS'un [n/6] AŞAMA satırlarının karşılığı)
const KIND_META: Record<string, { label: string; tone: LogTone }> = {
  media_imported: { label: 'İçe alındı', tone: 'info' },
  cozumleme_completed: { label: 'Çözümleme', tone: 'success' },
  cozumleme_failed: { label: 'Çözümleme', tone: 'error' },
  credit_detect_opening: { label: 'Jenerik (giriş)', tone: 'info' },
  credit_detect_closing: { label: 'Jenerik (çıkış)', tone: 'info' },
  credit_detect_skip: { label: 'Jenerik tespit', tone: 'warn' },
  ocr_started: { label: 'OCR başladı', tone: 'info' },
  ocr_completed: { label: 'OCR künye', tone: 'success' },
  ocr_partial: { label: 'OCR künye', tone: 'warn' },
  ocr_failed: { label: 'OCR künye', tone: 'error' },
  asr_started: { label: 'ASR başladı', tone: 'info' },
  asr_progress: { label: 'ASR ilerleme', tone: 'progress' },
  asr_completed: { label: 'ASR bitti', tone: 'success' },
  asr_partial: { label: 'ASR bitti', tone: 'warn' },
  asr_failed: { label: 'ASR', tone: 'error' },
  asr_skipped_kurtce: { label: 'ASR atlandı', tone: 'warn' },
  credit_text_completed: { label: 'Künye metin', tone: 'success' },
  credit_text_failed: { label: 'Künye metin', tone: 'warn' },
  credit_qc1_red: { label: 'QC1 RED', tone: 'warn' },
  credit_vl_fallback: { label: 'gemma4 VL', tone: 'info' },
  credit_vl_failed: { label: 'gemma4 VL', tone: 'warn' },
  credit_qc1_failed: { label: 'QC1 KONTROL', tone: 'error' },
  credit_qc1_passed: { label: 'QC1 PASS', tone: 'success' },
  ozet_completed: { label: 'Özet', tone: 'success' },
  ozet_internet: { label: 'Özet (internet)', tone: 'info' },
  ozet_atlandi: { label: 'Özet atlandı', tone: 'muted' },
  pdf_completed: { label: 'PDF', tone: 'success' },
  pdf_partial: { label: 'PDF', tone: 'warn' },
  pdf_failed: { label: 'PDF', tone: 'error' },
  v4_finalize_completed: { label: 'Final (v4)', tone: 'success' },
  v4_finalize_skipped: { label: 'Final (v4)', tone: 'muted' },
  v4_finalize_failed: { label: 'Final (v4)', tone: 'warn' },
  qwen_final_qc: { label: 'Son kontrol', tone: 'info' },
  qwen_final_qc_skipped: { label: 'Son kontrol', tone: 'muted' },
  routed_hazir: { label: '✓ HAZIR', tone: 'success' },
  routed_kontrol: { label: '⚠ KONTROL', tone: 'warn' },
  surface_failed: { label: 'Yüzeyleme', tone: 'warn' },
  flow_item_done: { label: 'Tamamlandı', tone: 'success' },
  flow_item_skipped: { label: 'Atlandı', tone: 'muted' },
  flow_item_failed: { label: 'Başarısız', tone: 'error' },
  flow_item_stopped: { label: 'Durduruldu', tone: 'warn' },
};

interface PipeEvent {
  event_id?: string;
  ts?: string;
  kind?: string;
  level?: string;
  module?: string;
  summary?: string;
  duration_seconds?: number;
  detail?: { percent?: number; [key: string]: unknown };
}

function kindMeta(kind: string, level: string): { label: string; tone: LogTone } {
  const hit = KIND_META[kind];
  if (hit) return hit;
  const tone: LogTone = level === 'error' ? 'error' : level === 'warn' || level === 'warning' ? 'warn' : 'muted';
  const label = (kind || 'olay').replace(/_/g, ' ');
  return { label: label.charAt(0).toUpperCase() + label.slice(1), tone };
}

function fmtClock(ts?: string): string {
  if (!ts) return '--:--:--';
  const d = new Date(ts);
  return Number.isNaN(d.getTime()) ? '--:--:--' : d.toLocaleTimeString('tr-TR', { hour12: false });
}

// "AHLAT.mp4: OCR kunye 187 satir" → "OCR kunye 187 satir" (per-film logda dosya adı tekrarı gereksiz)
function cleanSummary(summary?: string): string {
  if (!summary) return '';
  return summary.replace(/^.*?\.(mp4|mkv|mov|avi|mxf|m4v|webm)\s*(?::|için|icin)\s*/i, '');
}

// pipeline media_id = sanitize(video.stem); dosya adından aynı kuralla türet (sunucu clipId yoksa yedek)
function deriveClipId(name: string): string {
  const stem = (name || '').replace(/\.[^./\\]+$/, '');
  return stem.replace(/[^A-Za-z0-9._-]+/g, '_').replace(/^[._-]+|[._-]+$/g, '');
}

function FlowItemLog({ clipId, active, since }: { clipId: string; active: boolean; since?: string }) {
  const [events, setEvents] = useState<PipeEvent[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const stickRef = useRef(true);  // kullanıcı en alttaysa yeni olayda otomatik kaydır

  useEffect(() => {
    if (!clipId) return;
    let cancelled = false;
    const poll = async () => {
      try {
        const params = new URLSearchParams({ media_id: clipId, limit: '150' });
        if (since) params.set('since', since);
        const r = await fetch(`/api/events?${params.toString()}`, { cache: 'no-store' });
        if (!r.ok) { if (!cancelled) setErr(`HTTP ${r.status}`); return; }
        const d = await r.json();
        if (cancelled) return;
        const evs: PipeEvent[] = Array.isArray(d.events) ? d.events : [];
        evs.reverse();  // API newest-first → kronolojik (eski→yeni, akış gibi)
        setEvents(evs);
        setErr(null);
      } catch {
        if (!cancelled) setErr('bağlantı');
      }
    };
    void poll();
    const id = window.setInterval(poll, active ? 1500 : 6000);
    return () => { cancelled = true; window.clearInterval(id); };
  }, [clipId, active, since]);

  useEffect(() => {
    const el = scrollRef.current;
    if (el && stickRef.current) el.scrollTop = el.scrollHeight;
  }, [events]);

  if (!clipId) {
    return <div className="mt-1 rounded-sm border border-border-subtle bg-app-shell/70 px-2 py-1.5 text-[10px] text-foreground-muted">Bu öğe için adım-logu yok.</div>;
  }

  return (
    <div
      ref={scrollRef}
      onScroll={(event) => {
        const el = event.currentTarget;
        stickRef.current = el.scrollHeight - el.scrollTop - el.clientHeight < 24;
      }}
      className="mt-1 max-h-48 overflow-y-auto rounded-sm border border-border-subtle bg-app-shell/70 p-1.5 font-mono text-[10px] leading-4"
    >
      {events.length === 0 ? (
        <div className="px-1 py-1 text-foreground-muted">{active ? 'Adımlar bekleniyor…' : err ? `log: ${err}` : 'Kayıtlı adım yok.'}</div>
      ) : (
        events.map((e, i) => {
          const m = kindMeta(e.kind || '', e.level || 'info');
          const pct = e.detail && typeof e.detail.percent === 'number' ? e.detail.percent : undefined;
          return (
            <div key={e.event_id || `${i}-${e.ts || ''}`} className="flex items-start gap-1.5 px-0.5 py-0.5">
              <span className="shrink-0 tabular-nums text-foreground-disabled">{fmtClock(e.ts)}</span>
              <span className={`shrink-0 ${TONE_CLASS[m.tone]}`}>●</span>
              <span className={`w-[88px] shrink-0 truncate font-semibold ${TONE_CLASS[m.tone]}`} title={m.label}>{m.label}</span>
              <span className="min-w-0 flex-1 break-words text-foreground-default">{cleanSummary(e.summary)}</span>
              {typeof pct === 'number' ? (
                <span className="shrink-0 tabular-nums text-info">%{pct}</span>
              ) : typeof e.duration_seconds === 'number' ? (
                <span className="shrink-0 tabular-nums text-foreground-disabled">{e.duration_seconds.toFixed(1)}s</span>
              ) : null}
            </div>
          );
        })
      )}
    </div>
  );
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
    uploading: undefined,  // geçici bayrak — kalıcı duruma yazma
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

function restorePersistedFlowItem(item: FlowQueueItem, workerRunning = false): FlowQueueItem {
  const source: FlowItemSource = item.source || (item.tedialItem || item.id?.startsWith('tedial-') ? 'tedial' : 'upload');
  const restored = { ...item, source, uploading: undefined };  // yenilemede aktif yükleme olamaz
  if (restored.status === 'running') {
    if (workerRunning) {
      // SUNUCU worker hâlâ koşuyor — 'running' KORU; poll 2 sn'de gerçek (server) durumu getirir.
      return restored;
    }
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
