# MITAS servislerini DOĞRU app + TAM env ile (yeniden) başlatır.
#   8787 = core.api.asr_server:app          (ASR + Sonnet özet)
#   8765 = core.api.tedial.app:create_app   (Tedial + auto-login)   --factory
# İkisi de venvs\asr python ile; TÜM MITAS_/ANTHROPIC_/OPENAI_ User (kalıcı) env'leri yüklenir.
# Böylece hiçbir restart env düşürmez ve 8765 ASLA asr_server ile açılmaz.
#
# Kullanım:   pwsh -ExecutionPolicy Bypass -File E:\MITAS\scripts\start_mitas.ps1
# NOT: 8765/8787'deki mevcut uvicorn'ları durdurup yeniden başlatır (çalışan ASR işi varsa kesilir).

$ErrorActionPreference = 'Continue'
$ROOT = 'E:\MITAS'
$PY   = Join-Path $ROOT 'venvs\asr\Scripts\python.exe'
$LOGD = Join-Path $ROOT 'outputs'

Write-Host '== 1) Kalıcı (User) env yükleniyor: MITAS_/ANTHROPIC_/OPENAI_  (PATH gibi sistem env DOKUNULMAZ) =='
[Environment]::GetEnvironmentVariables('User').GetEnumerator() |
  Where-Object { $_.Key -match '^(MITAS_|ANTHROPIC_|OPENAI_)' } |
  ForEach-Object { Set-Item -Path ("Env:" + $_.Key) -Value $_.Value; Write-Host ("   + " + $_.Key) }

Write-Host '== 1b) QC2 + perf defaultlari (User env onceliklidir; yoksa AKTIF varsayilan) =='
# QC2 = kunye temizleme/dogrulama (garble-kapisi + yonetmen KB-fill + web/kopru kimlik). Uretimde AKTIF.
if (-not $env:MITAS_QC2)               { $env:MITAS_QC2 = '1';               Write-Host '   + MITAS_QC2=1 (default AKTIF)' }
if (-not $env:MITAS_QC2_WEB)           { $env:MITAS_QC2_WEB = '1';           Write-Host '   + MITAS_QC2_WEB=1 (default AKTIF)' }
# CREDIT_DETECT = jenerik GIRIS/CIKIS sinirini OpusCreditDetector ile dinamik bul (sabit 180/240s pencere
# kadroyu kacirir: KARAYIP lead kadro 8116-8420s'de, sabit pencere 8419s+ yalnizca kuyrugu aliyordu).
# No-regress: pencereyi yalnizca GENISLETIR (sabit tabanin altina inmez); CLIP footage'i zaten suzer. Uretimde AKTIF.
if (-not $env:MITAS_CREDIT_DETECT)     { $env:MITAS_CREDIT_DETECT = '1';     Write-Host '   + MITAS_CREDIT_DETECT=1 (default AKTIF)' }
# KB_CAST_ADD = kimlik kesinken (OCR-teyitli yon + >=3 siki cast) eksik kadroyu KB'den EKLE (asla ezme, OCR onde). AKTIF.
if (-not $env:MITAS_KB_CAST_ADD)       { $env:MITAS_KB_CAST_ADD = '1';       Write-Host '   + MITAS_KB_CAST_ADD=1 (default AKTIF)' }
# OCR GLM-consensus = doymus ollama'da takiliyor (15dk darbogaz); uretimde KAPALI.
if (-not $env:MITAS_OCR_GLM_CONSENSUS) { $env:MITAS_OCR_GLM_CONSENSUS = '0'; Write-Host '   + MITAS_OCR_GLM_CONSENSUS=0 (default)' }

Write-Host '== 2) Mevcut 8765/8787 uvicorn/asr_server/tedial süreçleri GÜÇLÜ durduruluyor (zombi/shim dahil) =='
$kill = @{}
# (a) komut-satırı eşleşmesi: port VE/VEYA app adı (shim/zombi de yakalanır)
Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
  Where-Object { $_.CommandLine -match '--port 87(65|87)\b' -or $_.CommandLine -match 'asr_server:app' -or $_.CommandLine -match 'tedial\.app' } |
  ForEach-Object { $kill[$_.ProcessId] = $true }
# (b) portu GERÇEKTE tutan süreç (cmdline kaçsa bile)
foreach ($p in 8787, 8765) {
  foreach ($op in (Get-NetTCPConnection -State Listen -LocalPort $p -ErrorAction SilentlyContinue).OwningProcess) {
    if ($op) { $kill[$op] = $true }
  }
}
foreach ($k in $kill.Keys) { Write-Host ("   x PID " + $k); Stop-Process -Id $k -Force -ErrorAction SilentlyContinue }
# (c) portlar boşalana kadar bekle (max ~5 sn) — yeni başlatma 'port in use' yememeli
foreach ($p in 8787, 8765) {
  for ($i = 0; $i -lt 25; $i++) {
    if (-not (Get-NetTCPConnection -State Listen -LocalPort $p -ErrorAction SilentlyContinue)) { break }
    Start-Sleep -Milliseconds 200
  }
}

Write-Host '== 3) Servisler DOĞRU app ile başlatılıyor (detached) =='
function Start-Svc([int]$Port, [string]$App, [string[]]$Extra) {
  $a = @('-m', 'uvicorn', $App) + $Extra + @('--host', '127.0.0.1', '--port', "$Port")
  Start-Process -FilePath $PY -ArgumentList $a -WorkingDirectory $ROOT -WindowStyle Hidden `
    -RedirectStandardOutput (Join-Path $LOGD "svc_$Port.log") `
    -RedirectStandardError  (Join-Path $LOGD "svc_$Port.err.log") | Out-Null
  Write-Host ("   -> 127.0.0.1:$Port  =  $App " + ($Extra -join ' '))
}
Start-Svc 8787 'core.api.asr_server:app'        @()
Start-Svc 8765 'core.api.tedial.app:create_app' @('--factory')

Write-Host '== 4) Doğrulama =='
Start-Sleep -Seconds 4
foreach ($p in 8787, 8765) {
  $lp = (Get-NetTCPConnection -State Listen -LocalPort $p -ErrorAction SilentlyContinue).OwningProcess
  if ($lp) {
    $c = (Get-CimInstance Win32_Process -Filter "ProcessId=$lp" -ErrorAction SilentlyContinue).CommandLine
    $app = if ($c -match 'tedial') { 'tedial.app' } elseif ($c -match 'asr_server') { 'asr_server' } else { '?' }
    Write-Host ("   $p OK  PID $lp  ($app)")
  } else { Write-Host "   $p DOWN!" }
}
Write-Host 'Bitti. WebUI: http://localhost:5173  |  Tedial servis: http://127.0.0.1:8765/tedial'
