import { useState, useEffect } from 'react';

interface SysInfo {
  cpu: number;
  ram: number;
  gpu: number;
}

function StatChip({ label, value }: { label: string; value: number }) {
  const isUnknown = value < 0;
  const barColor =
    isUnknown   ? 'bg-foreground-disabled/30'
    : value >= 90 ? 'bg-danger'
    : value >= 70 ? 'bg-warning-strong'
    : 'bg-info';
  const textColor =
    isUnknown   ? 'text-foreground-disabled'
    : value >= 90 ? 'text-danger'
    : value >= 70 ? 'text-warning-strong'
    : 'text-foreground-strong';

  return (
    <div className="flex flex-col items-center gap-0.5 min-w-[48px]">
      <span className="text-[9px] uppercase tracking-wider font-semibold text-foreground-disabled">{label}</span>
      <span className={`text-base font-bold tabular-nums leading-none ${textColor}`}>
        {isUnknown ? '—' : `${value}%`}
      </span>
      {/* mini bar */}
      <div className="w-full h-0.5 bg-surface-elevated rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-1000 ${barColor}`}
          style={{ width: isUnknown ? '0%' : `${value}%` }}
        />
      </div>
    </div>
  );
}

export function SysInfoBar() {
  const [now, setNow] = useState(() => new Date());
  const [info, setInfo] = useState<SysInfo>({ cpu: -1, ram: -1, gpu: -1 });

  useEffect(() => {
    const t = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(t);
  }, []);

  useEffect(() => {
    const poll = async () => {
      try {
        const res = await fetch('/api/sysinfo');
        if (res.ok) setInfo(await res.json());
      } catch { /* backend offline */ }
    };
    poll();
    const t = setInterval(poll, 5000);
    return () => clearInterval(t);
  }, []);

  const dateStr = now.toLocaleDateString('tr-TR', { day: '2-digit', month: '2-digit', year: 'numeric' });
  const timeStr = now.toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit', second: '2-digit' });

  return (
    <div className="flex items-center gap-4 select-none shrink-0">
      {/* Date + Time */}
      <div className="flex flex-col items-end gap-0.5 min-w-[78px]">
        <span className="text-sm font-mono font-bold text-foreground-strong tabular-nums leading-tight">{timeStr}</span>
        <span className="text-[11px] font-mono font-semibold text-foreground-muted tabular-nums leading-tight">{dateStr}</span>
      </div>

      <div className="w-px h-8 bg-border-mitas" />

      {/* System stats */}
      <div className="flex items-center gap-3">
        <StatChip label="CPU" value={info.cpu} />
        <StatChip label="GPU" value={info.gpu} />
        <StatChip label="RAM" value={info.ram} />
      </div>
    </div>
  );
}
