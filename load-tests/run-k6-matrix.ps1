$ErrorActionPreference = "Stop"

$baseUrl = $env:BASE_URL
if (-not $baseUrl) { $baseUrl = "http://localhost:8000" }

$k6Cmd = Get-Command k6 -ErrorAction SilentlyContinue
if (-not $k6Cmd -and (Test-Path "C:\Program Files\k6\k6.exe")) {
  $k6Cmd = "C:\Program Files\k6\k6.exe"
}
if (-not $k6Cmd) {
  throw "k6 bulunamadi. Yeni terminal acip tekrar deneyin."
}

$targets = @(50, 100, 200, 500)
$stageSeconds = 45
$resultPath = ".\load-tests\k6-matrix-results.csv"
$rows = @()

foreach ($vus in $targets) {
  $summaryPath = ".\load-tests\k6-summary-$vus.json"
  Write-Host "Calisiyor: VUS=$vus"

  & $k6Cmd run `
    --env BASE_URL=$baseUrl `
    --env USERNAME=admin `
    --env PASSWORD=admin123 `
    --env TARGET_VUS=$vus `
    --env STAGE_SECONDS=$stageSeconds `
    --summary-export $summaryPath `
    ".\load-tests\k6-fixed.js" | Out-Null

  $summary = Get-Content $summaryPath | ConvertFrom-Json
  $avg = [math]::Round($summary.metrics.http_req_duration.avg, 2)
  $p95 = [math]::Round($summary.metrics.http_req_duration."p(95)", 2)
  $failedRate = [math]::Round(($summary.metrics.http_req_failed.value * 100), 2)

  $rows += [pscustomobject]@{
    vus = $vus
    avg_ms = $avg
    p95_ms = $p95
    error_rate_percent = $failedRate
  }
}

$rows | Export-Csv -NoTypeInformation -Encoding UTF8 $resultPath
Write-Host "Tamamlandi: $resultPath"
Write-Host "Sonuclar:"
$rows | Format-Table -AutoSize
