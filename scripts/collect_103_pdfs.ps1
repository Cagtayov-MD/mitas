# collect_103_pdfs.ps1 — 103 klasoru toplu kosusunun BITEN filmlerini topla + denetle.
#   - Her 103 filmini TRT-ID ile Database/<clip>/_DURUM.json'a eslestirir.
#   - ASR tam (asr_status=done) VE OCR tam (ocr_lines>0) VE PDF varsa: PDF'i toplama klasorune kopyalar.
#   - karar=Hazir -> HAZIR/ ,  Kontrol -> KONTROL/ alt klasorune.
#   - manifest.csv + ozet yazar. Idempotent: istedigin kadar tekrar calistir.
param(
  [string]$Src    = '\\depo01cifs.int.trt.net.tr\sas_h264\23.05 öncesi FİLMLER\103',
  [string]$DbRoot = 'E:\MITAS\Database',
  [string]$Coll   = 'E:\MITAS\Mitas Output\103_TESLIM_20260608'
)
$ErrorActionPreference = 'SilentlyContinue'
New-Item -ItemType Directory -Force -Path $Coll,(Join-Path $Coll 'HAZIR'),(Join-Path $Coll 'KONTROL') | Out-Null

# 1) Database _DURUM.json -> trt_id ile indeksle
$durumByTrt = @{}
Get-ChildItem -LiteralPath $DbRoot -Directory | ForEach-Object {
  $dj = Join-Path $_.FullName '_DURUM.json'
  if (Test-Path -LiteralPath $dj) {
    try { $d = Get-Content -LiteralPath $dj -Raw -Encoding UTF8 | ConvertFrom-Json } catch { return }
    if ($d.trt_id) { $durumByTrt[[string]$d.trt_id] = [pscustomobject]@{ d = $d; dir = $_.FullName } }
  }
}

# 2) 103 filmleri uzerinde gec
$films = Get-ChildItem -LiteralPath $Src -File | Where-Object { $_.Extension -ieq '.mp4' } | Sort-Object Name
$rows = New-Object System.Collections.Generic.List[object]
foreach ($f in $films) {
  $trt   = if ($f.Name    -match '(\d{4}-\d{3,4}-\d-\d{4}-\d{2}-\d)') { $Matches[1] } else { '' }
  $title = if ($f.BaseName -match '\d{4}-\d{3,4}-\d-\d{4}-\d{2}-\d[-_](.+)$') { $Matches[1] } else { $f.BaseName }
  $e = if ($trt) { $durumByTrt[$trt] } else { $null }
  if (-not $e) {
    $rows.Add([pscustomobject]@{ trt=$trt; title=$title; karar='(bekliyor/yok)'; asr=''; asr_seg=''; ocr_lines=''; ocr_bucket=''; pdf_var=$false; toplandi='' }); continue
  }
  $d = $e.d
  $asrOk = ($d.asr_status -eq 'done')
  $ocrOk = ([int]$d.ocr_lines -gt 0)
  $pdfOk = ($d.pdf -and (Test-Path -LiteralPath $d.pdf))
  $dest = ''
  if ($asrOk -and $ocrOk -and $pdfOk) {
    $sub = if ($d.karar -eq 'Hazır') { 'HAZIR' } else { 'KONTROL' }
    $safe = ($title -replace '[^\w\.\-]','_')
    $dest = Join-Path (Join-Path $Coll $sub) ("$trt`_$safe.pdf")
    Copy-Item -LiteralPath $d.pdf -Destination $dest -Force
  }
  $rows.Add([pscustomobject]@{
    trt=$trt; title=$title; karar=$d.karar; asr=$d.asr_status; asr_seg=$d.asr_segments;
    ocr_lines=$d.ocr_lines; ocr_bucket=$d.ocr_bucket; pdf_var=$pdfOk; toplandi=$dest })
}

# 3) Manifest + ozet
$rows | Export-Csv -LiteralPath (Join-Path $Coll 'manifest.csv') -NoTypeInformation -Encoding UTF8
$toplam   = $rows.Count
$bitti    = ($rows | Where-Object { $_.asr -eq 'done' }).Count
$toplanan = ($rows | Where-Object { $_.toplandi }).Count
$hazir    = ($rows | Where-Object { $_.karar -eq 'Hazır' -and $_.toplandi }).Count
$kontrol  = ($rows | Where-Object { $_.karar -eq 'Kontrol' -and $_.toplandi }).Count
$asrYok   = ($rows | Where-Object { $_.asr -and $_.asr -ne 'done' }).Count
$ocrYok   = ($rows | Where-Object { $_.asr -eq 'done' -and [int]$_.ocr_lines -le 0 }).Count
Write-Host ("== 103 TOPLAMA OZETI ==")
Write-Host ("  Toplam film        : $toplam")
Write-Host ("  ASR bitti          : $bitti")
Write-Host ("  PDF TOPLANDI        : $toplanan   (HAZIR=$hazir  KONTROL=$kontrol)")
Write-Host ("  ASR eksik/hatali   : $asrYok")
Write-Host ("  OCR cikmadi (asr ok ama ocr 0): $ocrYok")
Write-Host ("  Manifest           : " + (Join-Path $Coll 'manifest.csv'))
