import os
from typing import Optional

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel
from pymongo import MongoClient

app = FastAPI(title="Product Service")

DB_URI = os.getenv("DB_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "product_db")
INTERNAL_SERVICE_TOKEN = os.getenv("INTERNAL_SERVICE_TOKEN", "internal-only-token")

mongo_client = MongoClient(DB_URI)
db = mongo_client[DB_NAME]
products = db["products"]


class ProductIn(BaseModel):
    name: str
    price: float
    stock: int


def check_internal(x_internal_token: str) -> None:
    if x_internal_token != INTERNAL_SERVICE_TOKEN:
        raise HTTPException(status_code=403, detail="Forbidden")


@app.get("/internal/products")
def list_products(x_internal_token: str = Header(default="")):
    check_internal(x_internal_token)
    docs = list(products.find({}, {"_id": 0}))
    return {"items": docs}


@app.get("/internal/products/{product_id}")
def get_product(product_id: str, x_internal_token: str = Header(default="")):
    check_internal(x_internal_token)
    item = products.find_one({"id": product_id}, {"_id": 0})
    if not item:
        raise HTTPException(status_code=404, detail="Not found")
    return item


@app.post("/internal/products")
def create_product(payload: ProductIn, x_internal_token: str = Header(default="")):
    check_internal(x_internal_token)
    doc = payload.model_dump()
    doc["id"] = f"p-{products.count_documents({}) + 1}"
    products.insert_one(doc)
    # insert_one, dict'e _id ekler; API'de Mongo tipini disari cikarmayiz.
    return {k: v for k, v in doc.items() if k != "_id"}


@app.put("/internal/products/{product_id}")
def update_product(product_id: str, payload: ProductIn, x_internal_token: str = Header(default="")):
    check_internal(x_internal_token)
    updated = products.update_one({"id": product_id}, {"$set": payload.model_dump()})
    if updated.matched_count == 0:
        raise HTTPException(status_code=404, detail="Not found")
    item: Optional[dict] = products.find_one({"id": product_id}, {"_id": 0})
    return item


@app.delete("/internal/products/{product_id}")
def delete_product(product_id: str, x_internal_token: str = Header(default="")):
    check_internal(x_internal_token)
    deleted = products.delete_one({"id": product_id})
    if deleted.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Not found")
    return {"deleted": True}
