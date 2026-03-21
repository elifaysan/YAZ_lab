import os
import sys
from pathlib import Path

from fastapi.testclient import TestClient
from jose import jwt

os.environ["DISPATCHER_DB_URI"] = "mongodb://dispatcher_db:27017"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import main  # noqa: E402
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


def test_products_rejects_invalid_token():
    response = client.get("/products", headers={"Authorization": "Bearer invalid.token.value"})
    assert response.status_code == 401


def test_reports_forbidden_for_user(monkeypatch):
    monkeypatch.setattr(main, "authorize", lambda role, path: False)
    response = client.get("/reports", headers={"Authorization": f"Bearer {_token('user')}"})
    assert response.status_code == 403


def test_products_invalid_json_returns_400():
    response = client.post(
        "/products",
        headers={"Authorization": f"Bearer {_token('admin')}", "Content-Type": "application/json"},
        content="{invalid",
    )
    assert response.status_code == 400


def test_products_returns_503_when_upstream_unreachable(monkeypatch):
    original_url = main.PRODUCT_SERVICE_URL
    monkeypatch.setattr(main, "PRODUCT_SERVICE_URL", "http://service-does-not-exist.invalid")
    response = client.get("/products", headers={"Authorization": f"Bearer {_token('admin')}"})
    assert response.status_code == 503
    monkeypatch.setattr(main, "PRODUCT_SERVICE_URL", original_url)


def test_put_products_invalid_json_returns_400():
    response = client.put(
        "/products/p-1",
        headers={"Authorization": f"Bearer {_token('admin')}", "Content-Type": "application/json"},
        content="{invalid",
    )
    assert response.status_code == 400


def test_delete_products_requires_token():
    response = client.delete("/products/p-1")
    assert response.status_code == 401


def test_delete_products_rejects_invalid_token():
    response = client.delete("/products/p-1", headers={"Authorization": "Bearer invalid.token"})
    assert response.status_code == 401
