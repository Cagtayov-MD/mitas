# MITAS WebUI Yerel Kurulum Durumu

Tarih: 2026-05-14  
Makine: Windows 10 Pro 10.0.19045  
Proje yolu: `E:\MITAS\.claude\worktrees\wonderful-vaughan-884d20\webui`

## Son Durum

MITAS WebUI yerel makinede gerçek ASR backend ile ayağa kalktı.

Aktif adres:

```text
http://localhost:5173/
```

ASR backend:

```text
http://127.0.0.1:8787/
```

Dev server arka planda çalışıyor. Vite logu:

```text
VITE v6.3.5 ready in 2892 ms
Local: http://localhost:5173/
```

Backend health:

```json
{
  "ok": true,
  "modules": {
    "asr": "enabled",
    "ocr": "disabled",
    "face": "disabled",
    "tag": "disabled",
    "logo": "disabled"
  },
  "models": {
    "large-v3": true,
    "large-v3-turbo": true
  }
}
```

## Yapılanlar

1. Node.js LTS kurulumu `winget` ile denendi.

   Sonuç: Node paketi zaten kurulu bulundu; `winget` daha yeni sürüm olmadığını bildirdi.

2. PATH mevcut PowerShell oturumunda tazelendi.

   Komut:

   ```powershell
   $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
   ```

3. Node ve npm doğrulandı.

   Sonuç:

   ```text
   node: v24.15.0
   npm: 11.12.1
   ```

4. Corepack üzerinden pnpm hazırlandı.

   İlk `corepack enable` denemesi `C:\Program Files\nodejs` içine shim yazarken `EPERM` verdi. Bunun yerine Corepack shim'leri kullanıcı PATH'indeki npm dizinine yazıldı:

   ```powershell
   corepack enable --install-directory $env:APPDATA\npm
   corepack prepare pnpm@latest --activate
   ```

5. pnpm doğrulandı.

   Sonuç:

   ```text
   pnpm: 11.1.2
   ```

6. Bağımlılıklar pnpm ile kuruldu.

   Komut:

   ```powershell
   pnpm install
   ```

   Sonuç:

   ```text
   Done in 1.7s using pnpm v11.1.2
   ```

   `pnpm-lock.yaml` oluştu.

7. pnpm 11 build-script onayı çözüldü.

   `pnpm install` ilk denemede şu uyarıyla durdu:

   ```text
   [ERR_PNPM_IGNORED_BUILDS] Ignored build scripts: @tailwindcss/oxide@4.1.12, esbuild@0.25.12
   ```

   `pnpm-workspace.yaml` içinde bu iki beklenen build bağımlılığı onaylandı:

   ```yaml
   allowBuilds:
     '@tailwindcss/oxide': true
     esbuild: true
   ```

8. TypeScript doğrulaması geçti.

   Komut:

   ```powershell
   pnpm type-check
   ```

   Sonuç:

   ```text
   tsc --noEmit
   ```

   Çıkış kodu 0.

9. Dev server başlatıldı.

   Komut:

   ```powershell
   pnpm dev
   ```

   Sonuç:

   ```text
   VITE v6.3.5 ready
   Local: http://localhost:5173/
   ```

10. HTTP erişimi doğrulandı.

    Sonuç:

    ```text
    http://localhost:5173/ -> 200
    ```

11. Varsayılan tarayıcıda WebUI açıldı.

    Komut:

    ```powershell
    Start-Process http://localhost:5173/
    ```

12. ASR-only FastAPI backend eklendi ve başlatıldı.

    Dosya:

    ```text
    E:\MITAS\core\api\asr_server.py
    ```

    Backend yalnızca ASR işi başlatır. OCR, Face, Tag ve Logo modülleri endpoint tarafından çağrılmaz.

13. WebUI upload akışı mock'tan gerçek backend'e bağlandı.

    Akış:

    ```text
    Yükle -> POST /api/asr/transcribe -> GET /api/jobs/{job_id} polling -> transcript/segments/timeline
    ```

14. Gerçek model smoke testi yapıldı.

    Test klip:

    ```text
    E:\MITAS\testklipler\trt_haber (3).mp4
    ```

    Sonuç:

    ```text
    job_id: asr-5afebbaadf83
    model: large-v3-turbo
    duration: 75.418s
    clean_segments: 10
    clean_words: 128
    quality_drops: 0
    status: done
    ```

    Transcript çıktısı:

    ```text
    E:\MITAS\outputs\webui_asr_jobs\asr-5afebbaadf83\run\transcript_review.md
    ```

## Çözülen Hatalar

### TypeScript hatası

İlk denemede `src/imports/pasted_text/ai-media-archive-app.tsx` dosyasından çok sayıda TSX parse hatası gelmişti. Devam sırasında dosyanın artık mevcut olmadığı ve `tsconfig.json` içinde `src/imports/**` klasörünün zaten exclude edildiği görüldü. Type-check yeniden çalıştırıldığında temiz geçti.

### Corepack shim izni

`corepack enable`, `C:\Program Files\nodejs` altında shim yazmak istediği için `EPERM` verdi. Kullanıcı PATH'indeki npm dizinine shim yazılarak çözüldü.

### pnpm build script onayı

pnpm 11, `@tailwindcss/oxide` ve `esbuild` build script'lerini açık onay olmadan çalıştırmadı. `pnpm-workspace.yaml` içine izin eklenerek çözüldü.

### Dev server `spawn EPERM`

İlk dev server denemesi sandbox içinde `esbuild.exe` spawn ederken `EPERM` verdi. Dev server sandbox dışında arka plan süreç olarak başlatılınca Vite başarıyla ayağa kalktı.

## UI Kriterleri

Kaynak bileşenlerde ve çalışan uygulama yapısında şu sinyaller doğrulandı:

- Koyu tema: `bg-app-shell`, MITAS dark token'ları
- Cyan glow'lu logo: `bg-info-strong`, `shadow-glow-info`
- `MITAS SYSTEMS` yazısı
- `Analiz İstasyonu` başlığı
- Sağda `w-[450px]` ASR/transcript sidebar
- Altta 8 track timeline
- `Konuşma (ASR)` aktif info/cyan track
- WIP track'lerde `Yapım Aşamasında` tooltip'i ve `Lock` ikonu
- Amber `DEMO MODU` rozeti
- `Yükle` butonu gerçek ASR backend'e dosya gönderiyor
- Sağdaki ASR transcript paneli gerçek `segments` çıktısını gösteriyor
- Timeline ASR blokları gerçek segment başlangıç/bitiş sürelerinden çiziliyor
- OCR/Face kontrolleri disabled kalıyor ve backend tarafından çalıştırılmıyor

## Oluşan Dosyalar

Kurulum/çalıştırma sırasında oluşan önemli dosyalar:

```text
pnpm-lock.yaml
pnpm-workspace.yaml
SETUP_STATUS.md
dev-server.pnpm.log
dev-server.pnpm.err.log
E:\MITAS\core\api\asr_server.py
E:\MITAS\outputs\webui_asr_backend.log
E:\MITAS\outputs\webui_asr_jobs\...
```

`package-lock.json`, pnpm başarıyla çalışır hale geldikten sonra karışıklık yaratmaması için kaldırıldı.
