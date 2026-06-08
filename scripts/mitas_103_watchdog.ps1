# mitas_103_watchdog.ps1 — 103 toplu kosusunu gece boyu SAGLIKLI tutar (20 dk'da bir, zamanlanmis gorev).
#   1) Worker dustuyse + bekleyen film varsa  -> /api/flow-queue/run (kaldigi yerden devam).
#   2) Biten filmlerin PDF'lerini toplar (collect_103_pdfs.ps1).
# Log: outputs\103_KUNYE_PDF\watchdog.log
$base = 'http://127.0.0.1:8787'
$logDir = 'E:\MITAS\Mitas Output\103_TESLIM_20260608'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$log = Join-Path $logDir 'watchdog.log'
function Log($m){ ("[" + (Get-Date -Format 'yyyy-MM-dd HH:mm:ss') + "] " + $m) | Out-File -Append -FilePath $log -Encoding UTF8 }

try {
  $s = $null
  Invoke-RestMethod -Method Post -Uri "$base/api/auth/login" -ContentType 'application/json' `
    -Body (@{ username='mitas'; pwId='verify_61' } | ConvertTo-Json) -SessionVariable s -TimeoutSec 25 | Out-Null
  $q = Invoke-RestMethod -Uri "$base/api/flow-queue" -WebSession $s -TimeoutSec 25
  $w = Invoke-RestMethod -Uri "$base/api/flow-queue/worker" -WebSession $s -TimeoutSec 25
  $waiting = @($q.items | Where-Object { $_.status -eq 'waiting' }).Count
  $running = @($q.items | Where-Object { $_.status -eq 'running' }).Count
  $done    = @($q.items | Where-Object { $_.status -eq 'done' -or $_.status -eq 'partial' }).Count
  $failed  = @($q.items | Where-Object { $_.status -eq 'failed' }).Count
  if (-not $w.running -and ($waiting -gt 0 -or $running -gt 0)) {
    # Worker dustuyse (orn. asr_server restart): yarida kalan 'running' filmi 'waiting'e cevir
    # (worker yalniz 'waiting' alir; yoksa o film takili kalir), sonra devam ettir.
    if ($running -gt 0) {
      foreach ($it in $q.items) { if ($it.status -eq 'running') { $it.status = 'waiting' } }
      Invoke-RestMethod -Method Put -Uri "$base/api/flow-queue" -ContentType 'application/json' `
        -Body ($q | ConvertTo-Json -Depth 8) -WebSession $s -TimeoutSec 25 | Out-Null
      Log "yarida kalan $running 'running' -> 'waiting' sifirlandi"
    }
    Invoke-RestMethod -Method Post -Uri "$base/api/flow-queue/run" -WebSession $s -TimeoutSec 25 | Out-Null
    Log "WORKER DOWN + bekleyen=$waiting -> /run (devam ettirildi)"
  }
  Log ("durum: bekleyen=$waiting bitti=$done hata=$failed worker=" + $w.running + " current=" + $w.current)
} catch {
  Log ("API HATA: " + $_.Exception.Message)
}

try {
  & pwsh -ExecutionPolicy Bypass -File E:\MITAS\scripts\collect_103_pdfs.ps1 *> $null
  Log "collector kosuldu"
} catch {
  Log ("collector HATA: " + $_.Exception.Message)
}
