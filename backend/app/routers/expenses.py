import csv
import io
import random
from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from ..categories import CATEGORIES, PAYMENT_METHODS
from ..database import get_db
from ..demo_data import generate_history
from ..models import Expense, User
from ..schemas import ExpenseIn, ExpenseOut, ExpensePage, ImportResult
from ..security import get_current_user

router = APIRouter(prefix="/api/expenses", tags=["expenses"])

MAX_IMPORT_ROWS = 5000


def _filtered(user_id: int, start, end, category, search):
    stmt = select(Expense).where(Expense.user_id == user_id)
    if start:
        stmt = stmt.where(Expense.date >= start)
    if end:
        stmt = stmt.where(Expense.date <= end)
    if category:
        stmt = stmt.where(Expense.category == category)
    if search:
        stmt = stmt.where(Expense.description.ilike(f"%{search}%"))
    return stmt


def _get_owned(db: Session, user: User, expense_id: int) -> Expense:
    expense = db.get(Expense, expense_id)
    if expense is None or expense.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Expense not found")
    return expense


@router.get("/meta")
def meta():
    return {"categories": CATEGORIES, "payment_methods": PAYMENT_METHODS}


@router.get("", response_model=ExpensePage)
def list_expenses(
    start: Optional[date] = None,
    end: Optional[date] = None,
    category: Optional[str] = None,
    search: Optional[str] = Query(None, max_length=100),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    stmt = _filtered(user.id, start, end, category, search)
    sub = stmt.subquery()
    total, total_amount = db.execute(select(func.count(), func.coalesce(func.sum(sub.c.amount), 0)).select_from(sub)).one()
    items = db.scalars(stmt.order_by(Expense.date.desc(), Expense.id.desc()).limit(limit).offset(offset)).all()
    return {"items": items, "total": total, "total_amount": float(total_amount)}


@router.post("", response_model=ExpenseOut, status_code=status.HTTP_201_CREATED)
def create_expense(body: ExpenseIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    expense = Expense(user_id=user.id, **body.model_dump())
    db.add(expense)
    db.commit()
    return expense


@router.put("/{expense_id}", response_model=ExpenseOut)
def update_expense(
    expense_id: int, body: ExpenseIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    expense = _get_owned(db, user, expense_id)
    for key, value in body.model_dump().items():
        setattr(expense, key, value)
    db.commit()
    return expense


@router.delete("/{expense_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_expense(expense_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    db.delete(_get_owned(db, user, expense_id))
    db.commit()


@router.get("/export")
def export_csv(
    start: Optional[date] = None,
    end: Optional[date] = None,
    category: Optional[str] = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = db.scalars(_filtered(user.id, start, end, category, None).order_by(Expense.date)).all()
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["date", "amount", "category", "description", "payment_method"])
    for e in rows:
        writer.writerow([e.date.isoformat(), f"{float(e.amount):.2f}", e.category, e.description, e.payment_method])
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=expenses.csv"},
    )


@router.post("/import", response_model=ImportResult)
async def import_csv(
    file: UploadFile = File(...), user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Import a CSV with columns: date (YYYY-MM-DD), amount, category, description, payment_method."""
    text = (await file.read()).decode("utf-8-sig", errors="ignore")
    reader = csv.DictReader(io.StringIO(text))
    required = {"date", "amount", "category"}
    if not reader.fieldnames or not required <= {f.strip().lower() for f in reader.fieldnames}:
        raise HTTPException(400, "CSV must have at least these columns: date, amount, category")

    imported, errors = [], []
    for line, raw in enumerate(reader, start=2):
        if line - 1 > MAX_IMPORT_ROWS:
            errors.append(f"Stopped after {MAX_IMPORT_ROWS} rows")
            break
        row = {k.strip().lower(): (v or "").strip() for k, v in raw.items() if k}
        try:
            body = ExpenseIn(
                date=datetime.strptime(row["date"], "%Y-%m-%d").date(),
                amount=float(row["amount"].replace(",", "")),
                category=row["category"],
                description=row.get("description", ""),
                payment_method=row.get("payment_method") or "UPI",
            )
        except Exception as exc:  # report the row and keep going
            message = exc.errors()[0]["msg"] if hasattr(exc, "errors") else str(exc)
            errors.append(f"Row {line}: {message}")
            continue
        imported.append(Expense(user_id=user.id, **body.model_dump()))
    db.add_all(imported)
    db.commit()
    return {"imported": len(imported), "errors": errors[:50]}


@router.post("/demo", response_model=ImportResult)
def load_demo_data(
    months: int = Query(18, ge=3, le=36),
    replace: bool = False,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Fill the account with realistic sample expenses so the dashboard can be explored."""
    if replace:
        db.execute(delete(Expense).where(Expense.user_id == user.id))
    elif db.scalar(select(func.count()).select_from(Expense).where(Expense.user_id == user.id)):
        raise HTTPException(409, "Account already has expenses. Use replace=true to overwrite them.")
    history = generate_history(random.Random(user.id), months=months, end=date.today())
    db.add_all(
        Expense(
            user_id=user.id,
            date=t.date,
            amount=t.amount,
            category=t.category,
            description=t.description,
            payment_method=t.payment_method,
        )
        for t in history
    )
    db.commit()
    return {"imported": len(history), "errors": []}
