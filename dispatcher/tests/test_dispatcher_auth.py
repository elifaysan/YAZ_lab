import os

from fastapi.testclient import TestClient
from jose import jwt

os.environ["DISPATCHER_DB_URI"] = "mongodb://localhost:27017"

from app.main import app  # noqa: E402


client = TestClient(app)


def _token(role: str) -> str:
    return jwt.encode({"sub": "u1", "role": role}, "super-secret-key", algorithm="HS256")


def test_products_requires_token():
    response = client.get("/products")
    assert response.status_code == 401


def test_reports_requires_token():
    response = client.get("/reports")
    assert response.status_code == 401


def test_products_accepts_valid_token():
    response = client.get("/products", headers={"Authorization": f"Bearer {_token('admin')}"})
    assert response.status_code in [200, 503]
