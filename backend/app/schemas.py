"""Request and response models."""

from __future__ import annotations

import datetime as dt
from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from .categories import CATEGORIES, PAYMENT_METHODS


# --- auth --------------------------------------------------------------------

class RegisterRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: str
    currency: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


# --- expenses ----------------------------------------------------------------

class ExpenseIn(BaseModel):
    amount: float = Field(..., gt=0, le=10_000_000)
    category: str
    description: str = Field("", max_length=255)
    payment_method: str = "UPI"
    date: dt.date

    @field_validator("amount")
    @classmethod
    def round_amount(cls, value: float) -> float:
        return round(value, 2)

    @field_validator("category")
    @classmethod
    def known_category(cls, value: str) -> str:
        if value not in CATEGORIES:
            raise ValueError(f"category must be one of: {', '.join(CATEGORIES)}")
        return value

    @field_validator("payment_method")
    @classmethod
    def known_payment_method(cls, value: str) -> str:
        if value not in PAYMENT_METHODS:
            raise ValueError(f"payment_method must be one of: {', '.join(PAYMENT_METHODS)}")
        return value

    @field_validator("date")
    @classmethod
    def not_in_future(cls, value: dt.date) -> dt.date:
        if value > dt.date.today():
            raise ValueError("date cannot be in the future")
        return value


class ExpenseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    amount: float
    category: str
    description: str
    payment_method: str
    date: dt.date


class ExpensePage(BaseModel):
    items: List[ExpenseOut]
    total: int
    total_amount: float


class ImportResult(BaseModel):
    imported: int
    errors: List[str]


# --- budgets -----------------------------------------------------------------

class BudgetIn(BaseModel):
    category: str
    monthly_limit: float = Field(..., gt=0, le=10_000_000)

    @field_validator("category")
    @classmethod
    def known_category(cls, value: str) -> str:
        if value not in CATEGORIES:
            raise ValueError(f"category must be one of: {', '.join(CATEGORIES)}")
        return value


class BudgetOut(BaseModel):
    category: str
    monthly_limit: float
    spent: float
    remaining: float
    percent_used: float
    status: str  # "ok", "warning" (>= 80%), "over"


# --- analytics & forecast ----------------------------------------------------

class CategoryTotal(BaseModel):
    category: str
    amount: float
    share: float


class DailyTotal(BaseModel):
    date: dt.date
    amount: float


class MonthSummary(BaseModel):
    month: str
    total: float
    transactions: int
    previous_month_total: float
    change_percent: Optional[float]
    average_daily: float
    by_category: List[CategoryTotal]
    daily: List[DailyTotal]
    top_expenses: List[ExpenseOut]


class MonthlyPoint(BaseModel):
    month: str
    total: float
    by_category: Dict[str, float]


class ForecastPoint(BaseModel):
    month: str
    predicted: float
    lower: float
    upper: float


class CategoryForecast(BaseModel):
    category: str
    predicted: float
    average_last_3: float
    trend: str  # "up", "down" or "flat"


class MonthEndProjection(BaseModel):
    month: str
    spent_so_far: float
    days_elapsed: int
    days_in_month: int
    projected_total: float


class ForecastResponse(BaseModel):
    method: str
    months_of_history: int
    history: List[MonthlyPoint]
    forecast: List[ForecastPoint]
    next_month_by_category: List[CategoryForecast]
    current_month: Optional[MonthEndProjection]
    insights: List[str]
