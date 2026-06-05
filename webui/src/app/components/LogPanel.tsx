import { useEffect, useRef, useState } from 'react';
import { Badge, ScrollArea } from './ui';

// Sistem genelinde olaylar — /api/events (system_events.jsonl), canlı (saniye saniye).
interface SysEvent {
  id?: string;
  ts?: string;
  timestamp?: string;
  kind?: string;
  level?: string;
  module?: string;
  summary?: string;
  filename?: string;
}

function fmtTime(e: SysEvent): string {
  const raw = e.ts || e.timestamp || '';
  if (!raw) return '--:--:--';
  const d = new Date(raw);
  if (Number.isNaN(d.getTime())) return '--:--:--';
  return d.toLocaleTimeString('tr-TR', { hour12: false });
}

const LEVEL_CLASS: Record<string, string> = {
  error: 'text-danger',
  warn: 'text-warning',
  warning: 'text-warning',
  info: 'text-foreground-muted',
};

export function LogPanel() {
  const [events, setEvents] = useState<SysEvent[]>([]);
  const [live, setLive] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const liveRef = useRef(true);
  liveRef.current = live;

  useEffect(() => {
    let cancelled = false;
    const poll = async () => {
      try {
        const r = await fetch('/api/events?limit=300', { cache: 'no-store' });
        if (!r.ok) {
          if (!cancelled) setErr(`HTTP ${r.status}`);
          return;
        }
        const d = await r.json();
        if (!cancelled) {
          setEvents(Array.isArray(d.events) ? d.events : []);
          setErr(null);
        }
      } catch (e) {
        if (!cancelled) setErr(e instanceof Error ? e.message : 'bağlantı hatası');
      }
    };
    void poll();
    const id = window.setInterval(() => {
      if (liveRef.current) void poll();
    }, 1500);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, []);

  return (
    <div className="flex h-full min-h-0 w-full flex-col overflow-hidden bg-app-shell">
      <div className="flex items-center justify-between gap-2 border-b border-border-subtle bg-surface/40 px-3 py-2">
        <div className="flex items-center gap-2">
          <span className={`h-2 w-2 rounded-full ${live ? 'bg-success animate-pulse' : 'bg-foreground-disabled'}`} />
          <span className="text-xs font-semibold text-foreground-strong">Sistem Logu — canlı</span>
          <Badge variant="outline" className="px-1.5 py-0 text-[10px]">{events.length}</Badge>
        </div>
        <button
          type="button"
          onClick={() => setLive((v) => !v)}
          className="rounded-sm border border-border-mitas px-2 py-0.5 text-[10px] text-foreground-muted transition-colors hover:text-foreground-strong"
        >
          {live ? 'Duraklat' : 'Canlı'}
        </button>
      </div>
      {err ? <div className="px-3 py-1 text-[10px] text-danger">log alınamadı: {err}</div> : null}
      <ScrollArea className="min-h-0 flex-1">
        <div className="divide-y divide-border-subtle/40 font-mono text-[10px] leading-4">
          {events.length === 0 ? (
            <div className="p-4 text-center text-foreground-muted">Henüz olay yok.</div>
          ) : (
            events.map((e, i) => (
              <div key={e.id || `${i}-${e.ts || ''}`} className="flex items-start gap-2 px-2.5 py-1 hover:bg-surface/40">
                <span className="shrink-0 tabular-nums text-foreground-disabled">{fmtTime(e)}</span>
                <span className={`w-9 shrink-0 uppercase ${LEVEL_CLASS[(e.level || 'info').toLowerCase()] || 'text-foreground-muted'}`}>
                  {(e.level || 'info').slice(0, 4)}
                </span>
                <span className="w-12 shrink-0 truncate text-info">{(e.module || '').slice(0, 8)}</span>
                <span className="w-24 shrink-0 truncate text-foreground-muted">{e.kind || ''}</span>
                <span className="min-w-0 flex-1 break-words text-foreground-default">{e.summary || ''}</span>
              </div>
            ))
          )}
        </div>
      </ScrollArea>
    </div>
  );
}
