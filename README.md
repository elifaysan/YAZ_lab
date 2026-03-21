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

## API Contract (RMM Seviye 2)

Tum dis dunya istekleri yalnizca Dispatcher uzerinden yapilir.

### Auth

- `POST /auth/login`
  - Request:
    - `{"username":"admin","password":"admin123"}`
  - Responses:
    - `200`: `{"access_token":"...","token_type":"bearer"}`
    - `401`: gecersiz kimlik bilgisi
    - `400`: gecersiz JSON
    - `503`: auth servisi ulasilamaz

### Products

- `GET /products`
  - Header: `Authorization: Bearer <token>`
  - Responses: `200`, `401`, `403`, `503`

- `GET /products/{id}`
  - Header: `Authorization: Bearer <token>`
  - Responses: `200`, `401`, `403`, `404`, `503`

- `POST /products`
  - Header: `Authorization: Bearer <token>`
  - Request:
    - `{"name":"Kalem","price":10.5,"stock":100}`
  - Responses: `200`, `400`, `401`, `403`, `503`

- `PUT /products/{id}`
  - Header: `Authorization: Bearer <token>`
  - Request:
    - `{"name":"Kalem","price":12.0,"stock":80}`
  - Responses: `200`, `400`, `401`, `403`, `404`, `503`

- `DELETE /products/{id}`
  - Header: `Authorization: Bearer <token>`
  - Responses: `200`, `401`, `403`, `404`, `503`

### Reports

- `GET /reports`
  - Header: `Authorization: Bearer <token>`
  - Responses: `200`, `401`, `403`, `503`
