import { useState, useEffect } from 'react';

interface SysInfo {
  cpu: number;
  ram: number;
  gpu: number;
}

function StatChip({ label, value }: { label: string; value: number }) {
  const color =
    value < 0   ? 'text-foreground-disabled'
    : value >= 90 ? 'text-danger'
    : value >= 70 ? 'text-warning-strong'
    : 'text-foreground-muted';

  return (
    <span className="tabular-nums">
      <span className="text-foreground-disabled">{label}: </span>
      <span className={`font-semibold ${color}`}>{value < 0 ? '—' : `%${value}`}</span>
    </span>
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
    <div className="flex items-center gap-3 text-[10px] font-mono text-foreground-muted select-none shrink-0">
      <span className="tabular-nums text-foreground-default font-medium">{dateStr} {timeStr}</span>
      <div className="w-px h-3 bg-border-mitas" />
      <StatChip label="CPU" value={info.cpu} />
      <StatChip label="GPU" value={info.gpu} />
      <StatChip label="RAM" value={info.ram} />
    </div>
  );
}
