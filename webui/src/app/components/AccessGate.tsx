import type { FormEvent } from 'react';
import { useEffect, useId, useRef, useState } from 'react';
import { LockKeyhole, LogIn } from 'lucide-react';
import { isValidMitasAccess, loginMitasAccess } from '../auth';
import { Button } from './ui';

interface AccessGateProps {
  onAccessGranted: () => void;
}

export function AccessGate({ onAccessGranted }: AccessGateProps) {
  const usernameId = useId();
  const pwIdId = useId();
  const errorId = useId();
  const usernameInputRef = useRef<HTMLInputElement | null>(null);
  const [username, setUsername] = useState('');
  const [pwId, setPwId] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isIntroComplete, setIsIntroComplete] = useState(false);

  useEffect(() => {
    const timer = window.setTimeout(() => setIsIntroComplete(true), 1300);
    return () => window.clearTimeout(timer);
  }, []);

  useEffect(() => {
    if (isIntroComplete) {
      usernameInputRef.current?.focus();
    }
  }, [isIntroComplete]);

  const isFormDisabled = isSubmitting || !isIntroComplete;

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    if (!isValidMitasAccess(username, pwId)) {
      setError('Giriş reddedildi.');
      setPwId('');
      return;
    }

    setIsSubmitting(true);
    try {
      await loginMitasAccess(username, pwId);
      onAccessGranted();
    } catch (loginError) {
      setError(loginError instanceof Error ? loginError.message : 'Giriş reddedildi.');
      setPwId('');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <main className="flex h-screen w-full items-center justify-center overflow-hidden bg-app-shell px-4 text-foreground-default font-sans selection:bg-info-subtle">
      <form
        onSubmit={handleSubmit}
        className="relative min-h-[640px] w-full max-w-[640px] overflow-hidden rounded-sm border border-border-mitas bg-surface/80 p-6 shadow-2xl shadow-black/40"
      >
        <div className="relative z-20 flex h-14 items-center justify-center">
          <img
            src="/mitas-new-wordmark.png"
            alt="MITAS"
            className="h-10 w-auto object-contain drop-shadow-glow-info"
            draggable={false}
          />
        </div>

        <div className="absolute inset-x-6 top-[92px] z-0 flex justify-center">
          <div
            className={`flex h-[360px] w-full max-w-[540px] items-center justify-center rounded-sm border border-info-border bg-black/35 p-10 shadow-2xl shadow-info-strong/20 transition-opacity duration-700 ease-out ${
              isIntroComplete ? 'opacity-[0.35]' : 'opacity-100'
            }`}
          >
            <img
              src="/mitas-logo.png"
              alt="MITAS"
              className="h-full w-full rounded-sm object-contain drop-shadow-glow-info-strong"
              draggable={false}
            />
          </div>
        </div>

        <div
          className={`absolute bottom-6 left-1/2 z-10 w-[calc(100%-3rem)] max-w-[392px] -translate-x-1/2 rounded-sm border border-border-subtle bg-app-shell/90 p-4 shadow-xl shadow-black/35 backdrop-blur-sm transition-all duration-700 ease-out ${
            isIntroComplete ? 'translate-y-0 opacity-100' : 'pointer-events-none translate-y-8 opacity-0'
          }`}
        >
          <div className="mb-4 border-b border-border-subtle pb-3 text-center">
            <h1 className="text-[15px] font-bold tracking-widest text-foreground-strong">MITAS</h1>
            <div className="mt-1 flex items-center justify-center gap-1.5 text-[10px] font-mono uppercase tracking-wider text-foreground-muted">
              <LockKeyhole className="h-3 w-3" />
              <span>Yetkili girişi</span>
            </div>
          </div>

          <div className="space-y-3">
            <label className="block text-xs font-medium text-foreground-muted" htmlFor={usernameId}>
              Kullanıcı adı
            </label>
            <input
              id={usernameId}
              ref={usernameInputRef}
              value={username}
              disabled={isFormDisabled}
              onChange={(event) => {
                setUsername(event.target.value);
                setError(null);
              }}
              autoComplete="username"
              className="h-9 w-full rounded-sm border border-border-mitas bg-app-shell px-3 text-sm text-foreground-strong outline-none transition-colors placeholder:text-foreground-disabled focus:border-info-border"
            />

            <label className="block text-xs font-medium text-foreground-muted" htmlFor={pwIdId}>
              PW ID
            </label>
            <input
              id={pwIdId}
              value={pwId}
              disabled={isFormDisabled}
              onChange={(event) => {
                setPwId(event.target.value);
                setError(null);
              }}
              type="password"
              autoComplete="current-password"
              aria-invalid={Boolean(error)}
              aria-describedby={error ? errorId : undefined}
              className="h-9 w-full rounded-sm border border-border-mitas bg-app-shell px-3 text-sm text-foreground-strong outline-none transition-colors placeholder:text-foreground-disabled focus:border-info-border"
            />
          </div>

          <div className="mt-4 min-h-5">
            {error ? (
              <p id={errorId} className="text-xs font-medium text-danger">
                {error}
              </p>
            ) : null}
          </div>

          <Button type="submit" className="mt-2 w-full gap-2" size="default" disabled={isFormDisabled}>
            <LogIn className="h-4 w-4" />
            Giriş
          </Button>
        </div>
      </form>
    </main>
  );
}
