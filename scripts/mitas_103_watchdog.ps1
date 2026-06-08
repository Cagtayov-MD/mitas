# mitas_103_watchdog.ps1 — 103 toplu kosusunu gece boyu SAGLIKLI tutar (20 dk'da bir, zamanlanmis gorev).
#   1) Worker dustuyse + bekleyen film varsa  -> /api/flow-queue/run (kaldigi yerden devam).
#   2) Biten filmlerin PDF'lerini toplar (collect_103_pdfs.ps1).
# Log: outputs\103_KUNYE_PDF\watchdog.log
$base = 'http://127.0.0.1:8787'
$logDir = 'E:\MITAS\Mitas Output\export'
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

# 3) OTO-RETRY: asr=failed filmleri SIFIRDAN yeniden dene (max 2). Gecici VRAM cakismasi cogu retry'da duzelir.
try {
  if ($s) {
    $retryFile = Join-Path $logDir 'retries.json'
    $retries = @{}
    if (Test-Path $retryFile) { try { (Get-Content $retryFile -Raw -Encoding UTF8 | ConvertFrom-Json).PSObject.Properties | ForEach-Object { $retries[$_.Name] = [int]$_.Value } } catch {} }
    $changed = $false
    Get-ChildItem 'E:\MITAS\Database' -Directory -ErrorAction SilentlyContinue | ForEach-Object {
      $dj = Join-Path $_.FullName '_DURUM.json'
      if (-not (Test-Path $dj)) { return }
      try { $d = Get-Content $dj -Raw -Encoding UTF8 | ConvertFrom-Json } catch { return }
      if ($d.asr_status -ne 'failed') { return }
      $trt = [string]$d.trt_id
      if (-not $trt) { return }
      $cnt = [int]($retries[$trt])
      if ($cnt -ge 2) { return }   # max 2 deneme — sonsuz dongu yok
      $fn = if ($d.video) { Split-Path -Leaf $d.video } else { '' }
      if (-not $fn) { return }
      try {
        Invoke-RestMethod -Method Post -Uri "$base/api/flow-queue/retry" -ContentType 'application/json' `
          -Body (@{ filename = $fn } | ConvertTo-Json) -WebSession $s -TimeoutSec 25 | Out-Null
        $retries[$trt] = $cnt + 1
        $changed = $true
        Log "OTO-RETRY: $fn (asr=failed) -> yeniden cozulecek (deneme $($cnt+1)/2)"
      } catch {
        Log ("OTO-RETRY HATA ($fn): " + $_.Exception.Message)
      }
    }
    if ($changed) { ($retries | ConvertTo-Json) | Out-File -FilePath $retryFile -Encoding UTF8 }
  }
} catch {
  Log ("oto-retry blok HATA: " + $_.Exception.Message)
}

# NOT: collector kaldırıldı — pipeline artık çıktıyı DOĞRUDAN Mitas Output\export\{ONAYLI,KONTROL}'a yazıyor.
