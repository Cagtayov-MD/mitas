import { useState, useEffect, useRef } from 'react';
import { RotateCcw } from 'lucide-react';

type Phase = 'idle' | 'restarting' | 'waiting' | 'done' | 'error';

export function RestartButton() {
  const [phase, setPhase] = useState<Phase>('idle');
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const stopPoll = () => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  };

  useEffect(() => () => stopPoll(), []);

  const handleRestart = async () => {
    if (phase !== 'idle' && phase !== 'done' && phase !== 'error') return;
    setPhase('restarting');

    try {
      await fetch('/api/restart', { method: 'POST' });
    } catch {
      // server might close the connection mid-response — that's OK
    }

    // Give the process ~1s to die then start polling health
    await new Promise((r) => setTimeout(r, 1000));
    setPhase('waiting');

    let attempts = 0;
    pollRef.current = setInterval(async () => {
      attempts++;
      try {
        const res = await fetch('/api/health', { signal: AbortSignal.timeout(1500) });
        if (res.ok) {
          stopPoll();
          setPhase('done');
          setTimeout(() => setPhase('idle'), 2000);
        }
      } catch {
        // still down
      }
      if (attempts >= 30) {          // 30s timeout
        stopPoll();
        setPhase('error');
        setTimeout(() => setPhase('idle'), 4000);
      }
    }, 1000);
  };

  const label =
    phase === 'restarting' ? 'Durduruluyor…'
    : phase === 'waiting'  ? 'Bekleniyor…'
    : phase === 'done'     ? 'Hazır'
    : phase === 'error'    ? 'Hata'
    : 'Sunucuyu Yeniden Başlat';

  const spinning = phase === 'restarting' || phase === 'waiting';

  const bg =
    phase === 'done'  ? 'bg-success hover:bg-success'
    : phase === 'error' ? 'bg-warning-strong hover:bg-warning-strong'
    : 'bg-danger hover:bg-danger/80';

  return (
    <button
      onClick={handleRestart}
      disabled={spinning}
      title={label}
      className={`
        flex items-center justify-center
        h-8 w-8 rounded-sm shrink-0
        ${bg}
        text-white
        transition-colors duration-200
        disabled:opacity-70 disabled:cursor-not-allowed
        shadow-sm
      `}
    >
      <RotateCcw className={`h-4 w-4 ${spinning ? 'animate-spin' : ''}`} />
    </button>
  );
}
