import json
import os
from typing import Optional

import httpx
from fastapi import FastAPI, Header, HTTPException, Request, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.responses import JSONResponse
from jose import JWTError, jwt
from pymongo import MongoClient

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
async def log_all_requests(request: Request, call_next):
    response = await call_next(request)
    traffic_logs.insert_one(
        {
            "path": request.url.path,
            "method": request.method,
            "status_code": response.status_code,
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
