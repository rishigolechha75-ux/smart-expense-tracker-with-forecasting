"""Database tables."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import List

from sqlalchemy import Date, DateTime, ForeignKey, Index, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100))
    password_hash: Mapped[str] = mapped_column(String(255))
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    expenses: Mapped[List["Expense"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    budgets: Mapped[List["Budget"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Expense(Base):
    __tablename__ = "expenses"
    __table_args__ = (Index("ix_expenses_user_date", "user_id", "date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    category: Mapped[str] = mapped_column(String(50))
    description: Mapped[str] = mapped_column(String(255), default="")
    payment_method: Mapped[str] = mapped_column(String(30), default="UPI")
    date: Mapped[date] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    user: Mapped[User] = relationship(back_populates="expenses")


class Budget(Base):
    __tablename__ = "budgets"
    __table_args__ = (UniqueConstraint("user_id", "category", name="uq_budget_user_category"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    category: Mapped[str] = mapped_column(String(50))
    monthly_limit: Mapped[Decimal] = mapped_column(Numeric(12, 2))

    user: Mapped[User] = relationship(back_populates="budgets")
