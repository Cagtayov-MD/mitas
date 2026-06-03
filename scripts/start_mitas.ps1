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

Write-Host '== 2) Mevcut 8765/8787 uvicorn süreçleri durduruluyor =='
Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
  Where-Object { $_.CommandLine -match '--port 87(65|87)\b' } |
  ForEach-Object { Write-Host ("   x PID " + $_.ProcessId); Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
Start-Sleep -Seconds 1

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
