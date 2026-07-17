# MITAS pipeline SUREC-AGACI CPU ornekleyici (SALT-OKUNUR).
# Sistem-geneli CPU, es-zamanli QC/ATLAS isleriyle kirleniyor. Bu sampler YALNIZ aktif
# mitas_pipeline surec-agacinin CPU'sunu izler -> filmin GERCEK CPU yukunu izole eder.
# Her ~5s: epoch,root_pid,n_proc,tree_cpu_pct(makine%),tree_rss_gb -> proc_samples.csv
$ErrorActionPreference = 'SilentlyContinue'
$out = 'E:\MITAS\outputs\RUN_WATCH_20260622\proc_samples.csv'
if (-not (Test-Path $out)) {
  'epoch_utc,root_pid,n_proc,tree_cpu_pct,tree_rss_gb' | Out-File -FilePath $out -Encoding ascii
}
$cores = (Get-CimInstance Win32_ComputerSystem).NumberOfLogicalProcessors
$MAXSEC = 21600
$start  = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
while ($true) {
  $now = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
  if (($now - $start) -ge $MAXSEC) { break }
  $procs = Get-CimInstance Win32_Process
  # kok: scripts/mitas_pipeline.py kosan python (asr_server/uvicorn DEGIL, COZUMLEME filmi olan)
  $root = $procs | Where-Object { $_.CommandLine -match 'mitas_pipeline' -and $_.CommandLine -match '--video|COZUMLEME|\.mp4' } | Select-Object -First 1
  if (-not $root) {
    "$now,,0,0,0" | Out-File -FilePath $out -Append -Encoding ascii
    Start-Sleep -Seconds 5; continue
  }
  # agaci BFS ile topla (ParentProcessId zinciri)
  $tree = New-Object System.Collections.Generic.HashSet[int]
  [void]$tree.Add([int]$root.ProcessId)
  $changed = $true
  while ($changed) {
    $changed = $false
    foreach ($p in $procs) {
      if ($p.ParentProcessId -and $tree.Contains([int]$p.ParentProcessId) -and -not $tree.Contains([int]$p.ProcessId)) {
        [void]$tree.Add([int]$p.ProcessId); $changed = $true
      }
    }
  }
  # perf: PID -> PercentProcessorTime (cekirdek-toplami) + WorkingSet
  $perf = Get-CimInstance Win32_PerfFormattedData_PerfProc_Process
  $cpuSum = 0.0; $rss = 0.0
  foreach ($pp in $perf) {
    if ($tree.Contains([int]$pp.IDProcess)) {
      $cpuSum += [double]$pp.PercentProcessorTime
      $rss    += [double]$pp.WorkingSet
    }
  }
  $cpuPct = [math]::Round($cpuSum / $cores, 1)          # makine yuzdesi
  $rssGb  = [math]::Round($rss / 1GB, 2)
  "$now,$($root.ProcessId),$($tree.Count),$cpuPct,$rssGb" | Out-File -FilePath $out -Append -Encoding ascii
  Start-Sleep -Seconds 5
}
