import os

from fastapi import FastAPI, Header, HTTPException
from pymongo import MongoClient

app = FastAPI(title="Report Service")

DB_URI = os.getenv("DB_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "report_db")
INTERNAL_SERVICE_TOKEN = os.getenv("INTERNAL_SERVICE_TOKEN", "internal-only-token")

mongo_client = MongoClient(DB_URI)
db = mongo_client[DB_NAME]
report_logs = db["report_logs"]


@app.on_event("startup")
def seed_report_data() -> None:
    if report_logs.count_documents({}) == 0:
        report_logs.insert_many(
            [
                {"event": "daily_sales", "value": 12},
                {"event": "daily_users", "value": 53},
            ]
        )


@app.get("/internal/reports")
def get_reports(x_internal_token: str = Header(default="")):
    if x_internal_token != INTERNAL_SERVICE_TOKEN:
        raise HTTPException(status_code=403, detail="Forbidden")
    return {"reports": list(report_logs.find({}, {"_id": 0}))}
