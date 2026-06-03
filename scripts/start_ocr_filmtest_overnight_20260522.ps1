$ErrorActionPreference = "Continue"
$env:PYTHONIOENCODING = "utf-8"
$env:MITAS_OCR_ALLOW_MODEL_DOWNLOAD = "1"

Set-Location "E:\MITAS"

$Python = "E:\MITAS\venvs\ocr\Scripts\python.exe"
$Manifest = "E:\MITAS\data\ocr_filmtest_last3min_manifest_20260522.json"
$Root = "E:\MITAS\outputs\ocr_credit_experiments\filmtest_last3min_overnight_20260522_v2"
$LogDir = Join-Path $Root "logs"
$MutfakDir = "E:\MITAS\mutfak"
$MasterReport = Join-Path $MutfakDir "OCR_FILMTEST_LAST3MIN_OVERNIGHT_2026-05-22.md"

New-Item -ItemType Directory -Force -Path $Root, $LogDir, $MutfakDir | Out-Null

function Add-MasterLine {
    param([string]$Line)
    Add-Content -LiteralPath $MasterReport -Encoding UTF8 -Value $Line
}

Set-Content -LiteralPath $MasterReport -Encoding UTF8 -Value "# OCR Filmtest Last 3 Minute Overnight`n"
Add-MasterLine "- Started: $(Get-Date -Format o)"
Add-MasterLine "- Manifest: $Manifest"
Add-MasterLine "- Root: $Root"
Add-MasterLine "- EasyOCR: disabled"
Add-MasterLine "- Paddle: CPU, PP-OCRv5 detector + latin_PP-OCRv5_mobile_rec"
Add-MasterLine ""

function Run-Phase {
    param(
        [string]$Name,
        [string]$Engines,
        [double]$Fps,
        [string]$Preprocess
    )

    $PhaseOut = Join-Path $Root $Name
    $Status = Join-Path $PhaseOut "batch_status.json"
    $Report = Join-Path $MutfakDir ("OCR_FILMTEST_LAST3MIN_" + $Name.ToUpperInvariant() + "_2026-05-22.md")
    $Log = Join-Path $LogDir ($Name + ".log")

    Add-MasterLine "## $Name"
    Add-MasterLine "- Started: $(Get-Date -Format o)"
    Add-MasterLine "- Engines: $Engines"
    Add-MasterLine "- FPS: $Fps"
    Add-MasterLine "- Preprocess: $Preprocess"
    Add-MasterLine "- Report: $Report"
    Add-MasterLine "- Status: $Status"
    Add-MasterLine ""

    & $Python -m scripts.ocr_credit_batch_last_minutes `
        --manifest $Manifest `
        --output-dir $PhaseOut `
        --engines $Engines `
        --fps $Fps `
        --preprocess-mode $Preprocess `
        --allow-model-download `
        --status-path $Status `
        --report-path $Report 2>&1 | Tee-Object -FilePath $Log

    $ExitCode = $LASTEXITCODE
    Add-MasterLine "- Completed: $(Get-Date -Format o)"
    Add-MasterLine "- Exit code: $ExitCode"
    Add-MasterLine ""
}

Run-Phase -Name "phase1_allmodels_fps1_raw" -Engines "paddle,oneocr,tesseract" -Fps 1 -Preprocess "off"
Run-Phase -Name "phase2_fastmodels_fps6_raw" -Engines "oneocr,tesseract" -Fps 6 -Preprocess "off"
Run-Phase -Name "phase3_paddle_fps6_raw" -Engines "paddle" -Fps 6 -Preprocess "off"

Add-MasterLine "- Overnight script completed: $(Get-Date -Format o)"
