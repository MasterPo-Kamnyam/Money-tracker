import logging
import os
from contextlib import asynccontextmanager
from datetime import date
from typing import Optional
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field


APP_NAME = os.getenv("APP_NAME", "Money Tracker")
APP_VERSION = os.getenv("APP_VERSION", "1.0.0")
DEFAULT_CURRENCY = os.getenv("DEFAULT_CURRENCY", "RUB")
MAX_EXPENSE_AMOUNT = float(os.getenv("MAX_EXPENSE_AMOUNT", "1000000000"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("expense_tracker")

@asynccontextmanager
async def lifespan(_app: FastAPI):
    logger.info("%s v%s запущена, валюта по умолчанию: %s", APP_NAME, APP_VERSION, DEFAULT_CURRENCY)
    yield
    logger.info("%s остановлена", APP_NAME)


app = FastAPI(title=APP_NAME, version=APP_VERSION, lifespan=lifespan)
expenses: dict[int, dict] = {}
next_id = 1


class ExpenseIn(BaseModel):
    description: str = Field(min_length=1, max_length=200)
    amount: float = Field(gt=0)
    category: str = Field(min_length=1, max_length=50)
    spent_on: Optional[date] = None


class Expense(ExpenseIn):
    id: int
    currency: str


@app.middleware("http")
async def log_requests(request, call_next):
    logger.info("Запрос: %s %s", request.method, request.url.path)
    response = await call_next(request)
    logger.info("Ответ: %s %s -> %s", request.method, request.url.path, response.status_code)
    return response


@app.get("/")
def root():
    return FileResponse("static/index.html")


@app.get("/api")
def api_info():
    return {"app": APP_NAME, "version": APP_VERSION, "docs": "/docs"}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/version")
def version():
    return {"app": APP_NAME, "version": APP_VERSION}


@app.post("/expenses", response_model=Expense, status_code=201)
def create_expense(item: ExpenseIn):
    global next_id
    if item.amount > MAX_EXPENSE_AMOUNT:
        raise HTTPException(
            status_code=422,
            detail=f"Сумма превышает максимум {MAX_EXPENSE_AMOUNT} {DEFAULT_CURRENCY}",
        )
    expense = {
        "id": next_id,
        "description": item.description,
        "amount": item.amount,
        "category": item.category,
        "spent_on": item.spent_on or date.today(),
        "currency": DEFAULT_CURRENCY,
    }
    expenses[next_id] = expense
    logger.info("Добавлена трата id=%s: %s на %s %s", next_id, item.description, item.amount, DEFAULT_CURRENCY)
    next_id += 1
    return expense


@app.get("/expenses", response_model=list[Expense])
def list_expenses(category: Optional[str] = Query(default=None)):
    result = list(expenses.values())
    if category:
        result = [e for e in result if e["category"].lower() == category.lower()]
    return result


@app.get("/expenses/{expense_id}", response_model=Expense)
def get_expense(expense_id: int):
    if expense_id not in expenses:
        raise HTTPException(status_code=404, detail="Трата не найдена")
    return expenses[expense_id]


@app.delete("/expenses/{expense_id}", status_code=204)
def delete_expense(expense_id: int):
    if expense_id not in expenses:
        raise HTTPException(status_code=404, detail="Трата не найдена")
    removed = expenses.pop(expense_id)
    logger.info("Удалена трата id=%s: %s", expense_id, removed["description"])


@app.get("/expenses/summary/by-category")
def summary_by_category():
    summary: dict[str, dict] = {}
    for e in expenses.values():
        cat = e["category"]
        if cat not in summary:
            summary[cat] = {"total": 0.0, "count": 0}
        summary[cat]["total"] += e["amount"]
        summary[cat]["count"] += 1
    logger.info("Запрошена статистика по категориям: %s категорий", len(summary))
    return {"currency": DEFAULT_CURRENCY, "categories": summary}


app.mount("/static", StaticFiles(directory="static"), name="static")
