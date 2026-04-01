import json
import os
import time
from typing import Optional

import httpx
from fastapi import FastAPI, Header, HTTPException, Query, Request, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.responses import HTMLResponse, JSONResponse
from jose import JWTError, jwt
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from pymongo import MongoClient
from starlette.responses import Response

app = FastAPI(title="Dispatcher")
bearer_scheme = HTTPBearer(auto_error=False)

DB_URI = os.getenv("DISPATCHER_DB_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("DISPATCHER_DB_NAME", "dispatcher_db")
JWT_SECRET = os.getenv("JWT_SECRET", "super-secret-key")
INTERNAL_SERVICE_TOKEN = os.getenv("INTERNAL_SERVICE_TOKEN", "internal-only-token")

AUTH_SERVICE_URL = os.getenv("AUTH_SERVICE_URL", "http://localhost:8001")
PRODUCT_SERVICE_URL = os.getenv("PRODUCT_SERVICE_URL", "http://localhost:8002")
REPORT_SERVICE_URL = os.getenv("REPORT_SERVICE_URL", "http://localhost:8003")

mongo_client = MongoClient(DB_URI)
db = mongo_client[DB_NAME]
traffic_logs = db["traffic_logs"]
access_rules = db["access_rules"]

HTTP_REQUESTS = Counter(
    "dispatcher_http_requests_total",
    "Dispatcher uzerinden gecen HTTP istek sayisi",
    ["method", "path_group", "status"],
)
HTTP_DURATION = Histogram(
    "dispatcher_http_request_duration_seconds",
    "Dispatcher istek suresi (saniye)",
    ["method", "path_group"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0),
)


def path_group(path: str) -> str:
    if path.startswith("/auth"):
        return "auth"
    if path.startswith("/products"):
        return "products"
    if path.startswith("/reports"):
        return "reports"
    if path.startswith("/dispatcher"):
        return "dispatcher"
    if path == "/metrics":
        return "metrics"
    return "other"


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except JWTError as exc:
        raise HTTPException(status_code=401, detail="Invalid token") from exc


def authorize(role: str, path: str) -> bool:
    rule = access_rules.find_one({"role": role, "path_prefix": {"$regex": f"^{path}"}})
    if rule:
        return True
    # Baslangic icin admin tum endpointlere ulasabilir.
    return role == "admin"


@app.on_event("startup")
def startup_seed() -> None:
    if access_rules.count_documents({}) == 0:
        access_rules.insert_many(
            [
                {"role": "admin", "path_prefix": "/products"},
                {"role": "admin", "path_prefix": "/reports"},
                {"role": "user", "path_prefix": "/products"},
            ]
        )


@app.middleware("http")
async def metrics_and_traffic_log(request: Request, call_next):
    group = path_group(request.url.path)
    start = time.perf_counter()
    response = await call_next(request)
    duration = time.perf_counter() - start
    status = str(response.status_code)
    HTTP_DURATION.labels(method=request.method, path_group=group).observe(duration)
    HTTP_REQUESTS.labels(method=request.method, path_group=group, status=status).inc()
    if request.url.path != "/metrics":
        traffic_logs.insert_one(
            {
                "path": request.url.path,
                "method": request.method,
                "status_code": response.status_code,
                "duration_ms": round(duration * 1000, 2),
            }
        )
    return response


async def forward_request(base_url: str, path: str, method: str, json_body: Optional[dict], headers: dict):
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.request(
                method=method,
                url=f"{base_url}{path}",
                json=json_body,
                headers=headers,
            )
        except httpx.RequestError:
            raise HTTPException(status_code=503, detail="Service unavailable")
    if not resp.content:
        return JSONResponse(status_code=resp.status_code, content={})
    try:
        payload = resp.json()
    except json.JSONDecodeError:
        payload = {"message": resp.text}
    return JSONResponse(status_code=resp.status_code, content=payload)


@app.get("/metrics")
def prometheus_metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


def _resolve_bearer_token(
    authorization: Optional[str],
    credentials: Optional[HTTPAuthorizationCredentials],
) -> Optional[str]:
    if authorization and authorization.startswith("Bearer "):
        return authorization.replace("Bearer ", "")
    if credentials and credentials.scheme.lower() == "bearer":
        return credentials.credentials
    return None


@app.get("/dispatcher/traffic-table", response_class=HTMLResponse)
async def traffic_log_table(
    authorization: Optional[str] = Header(default=None),
    credentials: Optional[HTTPAuthorizationCredentials] = Security(bearer_scheme),
    limit: int = Query(default=200, ge=1, le=500),
):
    token = _resolve_bearer_token(authorization, credentials)
    if not token:
        raise HTTPException(status_code=401, detail="Missing token")
    claims = decode_token(token)
    if claims.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    rows = list(
        traffic_logs.find({}, {"_id": 1, "path": 1, "method": 1, "status_code": 1, "duration_ms": 1})
        .sort("_id", -1)
        .limit(limit)
    )
    tr_html = ""
    for doc in rows:
        rid = str(doc.get("_id", ""))
        p = doc.get("path", "")
        m = doc.get("method", "")
        sc = doc.get("status_code", "")
        dm = doc.get("duration_ms", "")
        tr_html += f"<tr><td>{rid}</td><td>{m}</td><td>{p}</td><td>{sc}</td><td>{dm}</td></tr>"
    html = f"""<!DOCTYPE html>
<html lang="tr"><head><meta charset="utf-8"/><title>Dispatcher Trafik Loglari</title>
<style>
body {{ font-family: system-ui, sans-serif; margin: 16px; }}
table {{ border-collapse: collapse; width: 100%; }}
th, td {{ border: 1px solid #ccc; padding: 8px; text-align: left; }}
th {{ background: #f0f0f0; }}
</style></head><body>
<h1>Dispatcher — son 200 istek</h1>
<table><thead><tr><th>Id</th><th>Method</th><th>Path</th><th>Status</th><th>Sure (ms)</th></tr></thead>
<tbody>{tr_html}</tbody></table>
</body></html>"""
    return HTMLResponse(content=html)


@app.post("/auth/login")
async def login(request: Request):
    try:
        body = await request.json()
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON body") from exc
    return await forward_request(AUTH_SERVICE_URL, "/internal/login", "POST", body, {"X-Internal-Token": INTERNAL_SERVICE_TOKEN})


@app.api_route("/products{full_path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def products_proxy(
    full_path: str,
    request: Request,
    authorization: Optional[str] = Header(default=None),
    credentials: Optional[HTTPAuthorizationCredentials] = Security(bearer_scheme),
):
    token = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization.replace("Bearer ", "")
    elif credentials and credentials.scheme.lower() == "bearer":
        token = credentials.credentials
    if not token:
        raise HTTPException(status_code=401, detail="Missing token")
    claims = decode_token(token)
    if not authorize(claims.get("role", ""), "/products"):
        raise HTTPException(status_code=403, detail="Forbidden")
    body = None
    if request.method in {"POST", "PUT"}:
        try:
            body = await request.json()
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=400, detail="Invalid JSON body") from exc
    return await forward_request(
        PRODUCT_SERVICE_URL,
        f"/internal/products{full_path}",
        request.method,
        body,
        {"X-Internal-Token": INTERNAL_SERVICE_TOKEN},
    )


@app.get("/reports")
async def reports_proxy(
    authorization: Optional[str] = Header(default=None),
    credentials: Optional[HTTPAuthorizationCredentials] = Security(bearer_scheme),
):
    token = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization.replace("Bearer ", "")
    elif credentials and credentials.scheme.lower() == "bearer":
        token = credentials.credentials
    if not token:
        raise HTTPException(status_code=401, detail="Missing token")
    claims = decode_token(token)
    if not authorize(claims.get("role", ""), "/reports"):
        raise HTTPException(status_code=403, detail="Forbidden")
    return await forward_request(
        REPORT_SERVICE_URL,
        "/internal/reports",
        "GET",
        None,
        {"X-Internal-Token": INTERNAL_SERVICE_TOKEN},
    )
