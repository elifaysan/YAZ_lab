$ErrorActionPreference = "Stop"

$baseUrl = $env:BASE_URL
if (-not $baseUrl) { $baseUrl = "http://localhost:8000" }

Write-Host "k6 load test baslatiliyor..."
Write-Host "BASE_URL=$baseUrl"

$k6Cmd = Get-Command k6 -ErrorAction SilentlyContinue
if (-not $k6Cmd) {
  if (Test-Path "C:\Program Files\k6\k6.exe") {
    $k6Cmd = "C:\Program Files\k6\k6.exe"
  }
}
if (-not $k6Cmd) {
  throw "k6 bulunamadi. Yeni terminal acip tekrar deneyin."
}

& $k6Cmd run `
  --env BASE_URL=$baseUrl `
  --env USERNAME=admin `
  --env PASSWORD=admin123 `
  --summary-export ".\load-tests\k6-summary.json" `
  ".\load-tests\k6-load.js"

Write-Host ""
Write-Host "Test tamamlandi."
Write-Host "Ozet JSON: .\load-tests\k6-summary.json"
