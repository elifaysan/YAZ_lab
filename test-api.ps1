$ErrorActionPreference = "Stop"

$baseUrl = "http://localhost:8000"

Write-Host "1) Login ve token alma..."
$loginBody = @{
  username = "admin"
  password = "admin123"
} | ConvertTo-Json

$login = Invoke-RestMethod `
  -Method Post `
  -Uri "$baseUrl/auth/login" `
  -ContentType "application/json" `
  -Body $loginBody

$token = $login.access_token
if (-not $token) {
  throw "Token alinamadi."
}
Write-Host "Token alindi."

$headers = @{ Authorization = "Bearer $token" }

Write-Host "2) Urun olusturma..."
$productBody = @{
  name = "Kalem"
  price = 12.5
  stock = 30
} | ConvertTo-Json

$created = Invoke-RestMethod `
  -Method Post `
  -Uri "$baseUrl/products" `
  -Headers $headers `
  -ContentType "application/json" `
  -Body $productBody

Write-Host "Olusan urun id: $($created.id)"

Write-Host "3) Urunleri listeleme..."
$list = Invoke-RestMethod -Method Get -Uri "$baseUrl/products" -Headers $headers
Write-Host "Toplam urun sayisi: $($list.items.Count)"

Write-Host "4) Tek urun getirme..."
$id = $created.id
$single = Invoke-RestMethod -Method Get -Uri "$baseUrl/products/$id" -Headers $headers
Write-Host "Tek urun: $($single.name) / $($single.price)"

Write-Host "5) Raporlari cekme..."
$reports = Invoke-RestMethod -Method Get -Uri "$baseUrl/reports" -Headers $headers
Write-Host "Rapor kaydi sayisi: $($reports.reports.Count)"

Write-Host "Tamamlandi."
