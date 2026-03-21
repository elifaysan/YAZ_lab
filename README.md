# YazLab II - Proje 1

Bu depo, mikroservis mimarisi + Dispatcher (API Gateway) gereksinimleri icin baslangic iskeletidir.

## Mimari

- `dispatcher`: Tek giris noktasi, yonlendirme + yetkilendirme + merkezi loglama
- `auth_service`: Oturum acma/JWT uretimi
- `product_service`: Urun CRUD mikroservisi
- `report_service`: Basit rapor mikroservisi
- Her servis icin ayri MongoDB konteyneri (veri izolasyonu)

## Hizli Baslangic

1. Docker Desktop kurulu ve acik olsun.
2. Proje kokunde:

```bash
docker compose up --build
```

3. Dispatcher uzerinden ornek istek:

```bash
curl -X POST http://localhost:8000/auth/login -H "Content-Type: application/json" -d "{\"username\":\"admin\",\"password\":\"admin123\"}"
```

## Dispatcher TDD Notu

Dispatcher testleri `dispatcher/tests/` altinda tutulur ve once test yazilip sonra kod gelistirilir.
