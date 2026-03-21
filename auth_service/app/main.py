import os
from datetime import datetime, timedelta

from fastapi import FastAPI, Header, HTTPException
from jose import jwt
from pydantic import BaseModel
from pymongo import MongoClient

app = FastAPI(title="Auth Service")

DB_URI = os.getenv("DB_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "auth_db")
JWT_SECRET = os.getenv("JWT_SECRET", "super-secret-key")
INTERNAL_SERVICE_TOKEN = os.getenv("INTERNAL_SERVICE_TOKEN", "internal-only-token")

mongo_client = MongoClient(DB_URI)
db = mongo_client[DB_NAME]
users = db["users"]


class LoginRequest(BaseModel):
    username: str
    password: str


@app.on_event("startup")
def seed_users() -> None:
    if users.count_documents({}) == 0:
        users.insert_many(
            [
                {"username": "admin", "password": "admin123", "role": "admin"},
                {"username": "user", "password": "user123", "role": "user"},
            ]
        )


@app.post("/internal/login")
def login(payload: LoginRequest, x_internal_token: str = Header(default="")):
    if x_internal_token != INTERNAL_SERVICE_TOKEN:
        raise HTTPException(status_code=403, detail="Forbidden")
    user = users.find_one({"username": payload.username, "password": payload.password})
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = jwt.encode(
        {
            "sub": payload.username,
            "role": user["role"],
            "exp": datetime.utcnow() + timedelta(hours=2),
        },
        JWT_SECRET,
        algorithm="HS256",
    )
    return {"access_token": token, "token_type": "bearer"}
