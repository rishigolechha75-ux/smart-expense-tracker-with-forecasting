"""Budgets, analytics and forecasting endpoints."""

from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import analytics
from ..database import get_db
from ..models import Budget, User
from ..schemas import BudgetIn, BudgetOut, ForecastResponse, MonthlyPoint, MonthSummary
from ..security import get_current_user

router = APIRouter(prefix="/api", tags=["insights"])

MONTH_PATTERN = r"^\d{4}-(0[1-9]|1[0-2])$"


def _month(value: Optional[str]) -> str:
    return value or date.today().strftime("%Y-%m")


@router.get("/budgets", response_model=List[BudgetOut])
def list_budgets(
    month: Optional[str] = Query(None, pattern=MONTH_PATTERN),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return analytics.budget_status(db, user.id, _month(month))


@router.put("/budgets", response_model=List[BudgetOut])
def set_budget(body: BudgetIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    budget = db.scalar(select(Budget).where(Budget.user_id == user.id, Budget.category == body.category))
    if budget is None:
        db.add(Budget(user_id=user.id, category=body.category, monthly_limit=body.monthly_limit))
    else:
        budget.monthly_limit = body.monthly_limit
    db.commit()
    return analytics.budget_status(db, user.id, _month(None))


@router.delete("/budgets/{category}", status_code=status.HTTP_204_NO_CONTENT)
def delete_budget(category: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    budget = db.scalar(select(Budget).where(Budget.user_id == user.id, Budget.category == category))
    if budget is None:
        raise HTTPException(404, "No budget for this category")
    db.delete(budget)
    db.commit()


@router.get("/analytics/summary", response_model=MonthSummary)
def summary(
    month: Optional[str] = Query(None, pattern=MONTH_PATTERN),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return analytics.month_summary(db, user.id, _month(month))


@router.get("/analytics/monthly", response_model=List[MonthlyPoint])
def monthly(
    months: int = Query(12, ge=1, le=36),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return analytics.monthly_history(db, user.id, months)


@router.get("/forecast", response_model=ForecastResponse)
def forecast(
    request: Request,
    horizon: int = Query(3, ge=1, le=6),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return analytics.forecast(db, user.id, request.app.state.forecaster, horizon)
