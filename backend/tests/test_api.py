"""API tests: authentication, expenses, budgets, analytics and forecasting."""

from datetime import date, timedelta

import pytest

TODAY = date.today()


def expense(amount=250.0, category="Groceries", days_ago=0, **extra):
    return {
        "amount": amount,
        "category": category,
        "description": extra.get("description", "test"),
        "payment_method": extra.get("payment_method", "UPI"),
        "date": (TODAY - timedelta(days=days_ago)).isoformat(),
    }


# --- auth --------------------------------------------------------------------

def test_health(client):
    assert client.get("/api/health").json()["status"] == "ok"


def test_register_login_and_me(client):
    payload = {"name": "Asha", "email": "Asha@Example.com", "password": "correct-horse"}
    assert client.post("/api/auth/register", json=payload).status_code == 201

    login = client.post("/api/auth/login", json={"email": "asha@example.com", "password": "correct-horse"})
    assert login.status_code == 200
    token = login.json()["access_token"]
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.json()["email"] == "asha@example.com"
    assert "password_hash" not in me.json()


def test_duplicate_email_rejected(client):
    payload = {"name": "Dup", "email": "dup@example.com", "password": "password123"}
    client.post("/api/auth/register", json=payload)
    assert client.post("/api/auth/register", json=payload).status_code == 409


def test_wrong_password_rejected(client):
    client.post("/api/auth/register", json={"name": "W", "email": "w@example.com", "password": "password123"})
    r = client.post("/api/auth/login", json={"email": "w@example.com", "password": "wrong-password"})
    assert r.status_code == 401


@pytest.mark.parametrize("password", ["short", ""])
def test_weak_password_rejected(client, password):
    r = client.post("/api/auth/register", json={"name": "X", "email": "x@example.com", "password": password})
    assert r.status_code == 422


@pytest.mark.parametrize("header", [None, "Bearer not-a-token", "Basic abc"])
def test_protected_routes_need_valid_token(client, header):
    headers = {"Authorization": header} if header else {}
    assert client.get("/api/expenses", headers=headers).status_code == 401


# --- expenses ----------------------------------------------------------------

def test_expense_crud(client, make_user):
    headers, _ = make_user()
    created = client.post("/api/expenses", json=expense(199.99), headers=headers)
    assert created.status_code == 201
    expense_id = created.json()["id"]

    updated = client.put(f"/api/expenses/{expense_id}", json=expense(300, "Transport"), headers=headers)
    assert updated.json()["category"] == "Transport"
    assert updated.json()["amount"] == 300.0

    page = client.get("/api/expenses", headers=headers).json()
    assert page["total"] == 1 and page["total_amount"] == 300.0

    assert client.delete(f"/api/expenses/{expense_id}", headers=headers).status_code == 204
    assert client.get("/api/expenses", headers=headers).json()["total"] == 0


@pytest.mark.parametrize(
    "bad",
    [
        {"amount": -5},
        {"amount": 0},
        {"category": "Crypto"},
        {"payment_method": "Barter"},
        {"date": (TODAY + timedelta(days=3)).isoformat()},
    ],
)
def test_invalid_expenses_rejected(client, make_user, bad):
    headers, _ = make_user()
    assert client.post("/api/expenses", json={**expense(), **bad}, headers=headers).status_code == 422


def test_users_cannot_see_or_edit_each_others_expenses(client, make_user):
    alice, _ = make_user("Alice")
    bob, _ = make_user("Bob")
    expense_id = client.post("/api/expenses", json=expense(), headers=alice).json()["id"]

    assert client.get("/api/expenses", headers=bob).json()["total"] == 0
    assert client.put(f"/api/expenses/{expense_id}", json=expense(1), headers=bob).status_code == 404
    assert client.delete(f"/api/expenses/{expense_id}", headers=bob).status_code == 404


def test_filters_and_pagination(client, make_user):
    headers, _ = make_user()
    for i in range(5):
        client.post("/api/expenses", json=expense(100 + i, "Groceries", days_ago=i, description=f"veg {i}"), headers=headers)
    client.post("/api/expenses", json=expense(999, "Travel", description="train"), headers=headers)

    groceries = client.get("/api/expenses", params={"category": "Groceries"}, headers=headers).json()
    assert groceries["total"] == 5 and groceries["total_amount"] == 510.0

    searched = client.get("/api/expenses", params={"search": "TRAIN"}, headers=headers).json()
    assert [e["amount"] for e in searched["items"]] == [999.0]

    first_page = client.get("/api/expenses", params={"limit": 2}, headers=headers).json()
    assert len(first_page["items"]) == 2 and first_page["total"] == 6


def test_csv_import_and_export(client, make_user):
    headers, _ = make_user()
    yesterday = (TODAY - timedelta(days=1)).isoformat()
    csv_text = (
        "date,amount,category,description,payment_method\n"
        f"{yesterday},450.50,Food & Dining,Pizza,Card\n"
        f"{yesterday},\"1,200\",Shopping,Shoes,UPI\n"
        f"{yesterday},abc,Shopping,bad amount,UPI\n"
        f"{yesterday},100,Unknown,bad category,UPI\n"
    )
    r = client.post("/api/expenses/import", files={"file": ("e.csv", csv_text, "text/csv")}, headers=headers)
    body = r.json()
    assert body["imported"] == 2
    assert len(body["errors"]) == 2 and body["errors"][0].startswith("Row 4")

    exported = client.get("/api/expenses/export", headers=headers)
    lines = exported.text.strip().splitlines()
    assert lines[0] == "date,amount,category,description,payment_method"
    assert len(lines) == 3


def test_csv_import_requires_columns(client, make_user):
    headers, _ = make_user()
    r = client.post("/api/expenses/import", files={"file": ("e.csv", "foo,bar\n1,2\n", "text/csv")}, headers=headers)
    assert r.status_code == 400


# --- budgets & analytics -----------------------------------------------------

def test_budget_status_levels(client, make_user):
    headers, _ = make_user()
    month = TODAY.strftime("%Y-%m")
    client.post("/api/expenses", json=expense(900, "Groceries", days_ago=0), headers=headers)
    client.post("/api/expenses", json=expense(1500, "Shopping", days_ago=0), headers=headers)
    client.put("/api/budgets", json={"category": "Groceries", "monthly_limit": 1000}, headers=headers)
    client.put("/api/budgets", json={"category": "Shopping", "monthly_limit": 1000}, headers=headers)
    client.put("/api/budgets", json={"category": "Transport", "monthly_limit": 1000}, headers=headers)

    budgets = {b["category"]: b for b in client.get("/api/budgets", params={"month": month}, headers=headers).json()}
    assert budgets["Groceries"]["status"] == "warning" and budgets["Groceries"]["remaining"] == 100.0
    assert budgets["Shopping"]["status"] == "over"
    assert budgets["Transport"]["status"] == "ok" and budgets["Transport"]["spent"] == 0.0

    assert client.delete("/api/budgets/Transport", headers=headers).status_code == 204
    assert len(client.get("/api/budgets", headers=headers).json()) == 2


def test_month_summary(client, make_user):
    headers, _ = make_user()
    first_of_month = TODAY.replace(day=1)
    client.post("/api/expenses", json={**expense(300, "Groceries"), "date": first_of_month.isoformat()}, headers=headers)
    client.post("/api/expenses", json={**expense(700, "Transport"), "date": first_of_month.isoformat()}, headers=headers)
    summary = client.get("/api/analytics/summary", headers=headers).json()
    assert summary["total"] == 1000.0
    assert summary["by_category"][0] == {"category": "Transport", "amount": 700.0, "share": 0.7}
    assert len(summary["daily"]) == TODAY.day


def test_invalid_month_parameter(client, make_user):
    headers, _ = make_user()
    assert client.get("/api/analytics/summary", params={"month": "2025-13"}, headers=headers).status_code == 422


# --- demo data & forecasting -------------------------------------------------

def test_forecast_without_data(client, make_user):
    headers, _ = make_user()
    body = client.get("/api/forecast", headers=headers).json()
    assert body["forecast"] == [] and body["months_of_history"] == 0


def test_demo_data_and_forecast(client, make_user):
    headers, _ = make_user()
    loaded = client.post("/api/expenses/demo", params={"months": 18}, headers=headers).json()
    assert loaded["imported"] > 500

    # loading again without replace must not duplicate data
    assert client.post("/api/expenses/demo", headers=headers).status_code == 409

    body = client.get("/api/forecast", params={"horizon": 3}, headers=headers).json()
    assert body["months_of_history"] == 17  # 18 months minus the current, incomplete one
    assert "Gradient boosting" in body["method"]
    assert len(body["forecast"]) == 3
    for point in body["forecast"]:
        assert 0 < point["lower"] <= point["predicted"] <= point["upper"]
    assert body["current_month"]["projected_total"] >= body["current_month"]["spent_so_far"]
    assert body["next_month_by_category"]

    monthly = client.get("/api/analytics/monthly", params={"months": 12}, headers=headers).json()
    assert len(monthly) == 12 and all(m["total"] > 0 for m in monthly[:-1])


def test_short_history_uses_moving_average(client, make_user):
    headers, _ = make_user()
    client.post("/api/expenses/demo", params={"months": 4}, headers=headers)
    body = client.get("/api/forecast", headers=headers).json()
    assert body["months_of_history"] == 3
    assert "moving average" in body["method"]
