import { Lock } from 'lucide-react';

export function FaceBankWorkspace() {
  return (
    <div className="flex flex-col h-full w-full bg-app-shell text-foreground-default items-center justify-center p-8 text-center gap-6">
      <div className="h-24 w-24 bg-surface border border-border-subtle rounded-full flex items-center justify-center shadow-inner">
        <Lock className="h-10 w-10 text-foreground-disabled" />
      </div>

      <div className="space-y-3">
        <h2 className="text-xl font-bold text-foreground-strong">Yüz Bankası Yapım Aşamasında</h2>
        <p className="text-sm text-foreground-muted max-w-md mx-auto leading-relaxed">
          Bu modül v0.4 sürümünde aktif olacak. Şu anki sürüm ASR (konuşma → metin) modülüne odaklanmıştır.
        </p>
      </div>

      <a href="#" className="text-xs text-foreground-disabled underline hover:text-foreground-muted cursor-not-allowed mt-4">
        Yol haritasını incele
      </a>
    </div>
  );
}
