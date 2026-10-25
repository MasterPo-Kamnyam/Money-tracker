from fastapi.testclient import TestClient
from app_final import app


client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_version():
    response = client.get("/version")
    assert response.status_code == 200
    data = response.json()
    assert "version" in data
    assert "app" in data


def test_create_and_get_expense():
    payload = {"description": "Кофе", "amount": 250.0, "category": "Еда"}
    created = client.post("/expenses", json=payload)
    assert created.status_code == 201
    expense_id = created.json()["id"]

    got = client.get(f"/expenses/{expense_id}")
    assert got.status_code == 200
    assert got.json()["description"] == "Кофе"
    assert got.json()["amount"] == 250.0


def test_get_missing_expense_returns_404():
    response = client.get("/expenses/999999")
    assert response.status_code == 404


def test_invalid_amount_rejected():
    payload = {"description": "Тест", "amount": -10, "category": "Еда"}
    response = client.post("/expenses", json=payload)
    assert response.status_code == 422


def test_summary_by_category():
    client.post("/expenses", json={"description": "Билет", "amount": 100.0, "category": "Транспорт"})
    response = client.get("/expenses/summary/by-category")
    assert response.status_code == 200
    data = response.json()
    assert "categories" in data
    assert data["categories"]["Транспорт"]["total"] >= 100.0
