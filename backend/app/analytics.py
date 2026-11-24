"""Spending summaries, budget tracking, forecasts and insights for one user."""

from __future__ import annotations

import calendar
from collections import defaultdict
from datetime import date, timedelta
from typing import Dict, List, Optional, Tuple

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from .categories import CATEGORIES
from .forecasting import Forecaster, monthly_series
from .models import Budget, Expense

# Categories paid roughly once a month; the rest are spread across the month
LUMPY_CATEGORIES = {"Rent", "Education", "Travel"}


def month_bounds(month: str) -> Tuple[date, date]:
    """'2025-03' -> (2025-03-01, 2025-03-31)."""
    year, mon = map(int, month.split("-"))
    return date(year, mon, 1), date(year, mon, calendar.monthrange(year, mon)[1])


def previous_month(month: str) -> str:
    return str(pd.Period(month, freq="M") - 1)


def _expenses_between(db: Session, user_id: int, start: date, end: date) -> List[Expense]:
    stmt = (
        select(Expense)
        .where(Expense.user_id == user_id, Expense.date >= start, Expense.date <= end)
        .order_by(Expense.date)
    )
    return list(db.scalars(stmt))


def _all_expenses(db: Session, user_id: int) -> List[Expense]:
    return list(db.scalars(select(Expense).where(Expense.user_id == user_id).order_by(Expense.date)))


def month_summary(db: Session, user_id: int, month: str, today: Optional[date] = None) -> dict:
    today = today or date.today()
    start, end = month_bounds(month)
    expenses = _expenses_between(db, user_id, start, end)
    prev_start, prev_end = month_bounds(previous_month(month))
    previous_total = sum(float(e.amount) for e in _expenses_between(db, user_id, prev_start, prev_end))

    total = sum(float(e.amount) for e in expenses)
    by_category: Dict[str, float] = defaultdict(float)
    daily: Dict[date, float] = defaultdict(float)
    for e in expenses:
        by_category[e.category] += float(e.amount)
        daily[e.date] += float(e.amount)

    days_counted = (min(end, today) - start).days + 1 if start <= today else 0
    return {
        "month": month,
        "total": round(total, 2),
        "transactions": len(expenses),
        "previous_month_total": round(previous_total, 2),
        "change_percent": round((total - previous_total) / previous_total * 100, 1) if previous_total else None,
        "average_daily": round(total / days_counted, 2) if days_counted > 0 else 0.0,
        "by_category": [
            {"category": c, "amount": round(a, 2), "share": round(a / total, 4) if total else 0.0}
            for c, a in sorted(by_category.items(), key=lambda kv: kv[1], reverse=True)
        ],
        "daily": [
            {"date": d, "amount": round(daily.get(d, 0.0), 2)}
            for d in (start + timedelta(days=i) for i in range((min(end, today) - start).days + 1))
        ] if start <= today else [],
        "top_expenses": sorted(expenses, key=lambda e: float(e.amount), reverse=True)[:5],
    }


def monthly_history(db: Session, user_id: int, months: int = 12, today: Optional[date] = None) -> List[dict]:
    """Totals per month (and per category) for the last ``months`` months, including this one."""
    today = today or date.today()
    current = pd.Period(today, freq="M")
    first = current - (months - 1)
    start, _ = month_bounds(str(first))
    expenses = _expenses_between(db, user_id, start, today)
    table: Dict[str, Dict[str, float]] = {str(first + i): defaultdict(float) for i in range(months)}
    for e in expenses:
        table[str(pd.Period(e.date, freq="M"))][e.category] += float(e.amount)
    return [
        {"month": m, "total": round(sum(cats.values()), 2), "by_category": {c: round(v, 2) for c, v in cats.items()}}
        for m, cats in table.items()
    ]


def budget_status(db: Session, user_id: int, month: str) -> List[dict]:
    start, end = month_bounds(month)
    spent: Dict[str, float] = defaultdict(float)
    for e in _expenses_between(db, user_id, start, end):
        spent[e.category] += float(e.amount)
    budgets = db.scalars(select(Budget).where(Budget.user_id == user_id)).all()
    out = []
    for b in sorted(budgets, key=lambda b: CATEGORIES.index(b.category)):
        limit = float(b.monthly_limit)
        used = spent.get(b.category, 0.0)
        pct = used / limit * 100 if limit else 0.0
        out.append(
            {
                "category": b.category,
                "monthly_limit": round(limit, 2),
                "spent": round(used, 2),
                "remaining": round(limit - used, 2),
                "percent_used": round(pct, 1),
                "status": "over" if pct > 100 else "warning" if pct >= 80 else "ok",
            }
        )
    return out


def _category_matrix(expenses: List[Expense], months: pd.PeriodIndex) -> pd.DataFrame:
    frame = pd.DataFrame(
        [(pd.Period(e.date, freq="M"), e.category, float(e.amount)) for e in expenses],
        columns=["month", "category", "amount"],
    )
    if frame.empty:
        return pd.DataFrame(index=months)
    pivot = frame.pivot_table(index="month", columns="category", values="amount", aggfunc="sum")
    return pivot.reindex(months, fill_value=0.0).fillna(0.0)


def month_end_projection(
    expenses: List[Expense], complete: pd.DataFrame, today: date
) -> Optional[dict]:
    """Project this month's total from what is spent so far plus typical remaining spend."""
    current = pd.Period(today, freq="M")
    this_month = [e for e in expenses if pd.Period(e.date, freq="M") == current]
    days_in_month = calendar.monthrange(today.year, today.month)[1]
    days_elapsed = today.day
    spent_by_cat: Dict[str, float] = defaultdict(float)
    for e in this_month:
        spent_by_cat[e.category] += float(e.amount)
    spent = sum(spent_by_cat.values())
    if complete.empty:
        if not this_month:
            return None
        projected = spent / days_elapsed * days_in_month
    else:
        typical = complete.tail(3).mean()
        remaining_fraction = (days_in_month - days_elapsed) / days_in_month
        projected = spent
        for category, typical_amount in typical.items():
            already = spent_by_cat.get(category, 0.0)
            if category in LUMPY_CATEGORIES:
                # usually paid once a month; only add it if not paid yet and it is regular
                if already == 0 and (complete[category].tail(3) > 0).all():
                    projected += typical_amount
            else:
                projected += typical_amount * remaining_fraction
    return {
        "month": str(current),
        "spent_so_far": round(spent, 2),
        "days_elapsed": days_elapsed,
        "days_in_month": days_in_month,
        "projected_total": round(projected, 2),
    }


def forecast(
    db: Session, user_id: int, forecaster: Forecaster, horizon: int = 3, today: Optional[date] = None
) -> dict:
    today = today or date.today()
    expenses = _all_expenses(db, user_id)
    current = pd.Period(today, freq="M")
    last_complete = current - 1

    empty = {
        "method": "Not enough data",
        "months_of_history": 0,
        "history": [],
        "forecast": [],
        "next_month_by_category": [],
        "current_month": None,
        "insights": ["Add expenses for at least one full month to see a forecast."],
    }
    if not expenses:
        return empty

    series = monthly_series([e.date for e in expenses], [e.amount for e in expenses], end=last_complete)
    series = series[series.index <= last_complete]
    complete = _category_matrix(expenses, series.index) if len(series) else pd.DataFrame()
    projection = month_end_projection(expenses, complete, today)

    if len(series) == 0:
        result = dict(empty, current_month=projection)
        if projection:
            result["insights"] = [
                f"At your current pace you will spend about {projection['projected_total']:,.0f} this month."
            ]
        return result

    points = forecaster.forecast(series.to_numpy(), current, horizon)
    by_category = []
    for category in complete.columns:
        values = complete[category].to_numpy()
        last3 = values[-3:].mean()
        prior3 = values[-6:-3].mean() if len(values) >= 6 else last3
        recent = values[-3:]
        weights = [0.2, 0.3, 0.5][-len(recent):]
        weighted = float((recent * weights).sum() / sum(weights))
        trend = "flat"
        if prior3 > 0 and last3 > prior3 * 1.1:
            trend = "up"
        elif prior3 > 0 and last3 < prior3 * 0.9:
            trend = "down"
        if last3 > 0:
            by_category.append(
                {"category": category, "predicted": round(weighted, 2), "average_last_3": round(last3, 2), "trend": trend}
            )
    by_category.sort(key=lambda c: c["predicted"], reverse=True)

    method = (
        forecaster.method_description
        if len(series) >= 6
        else f"{min(3, len(series))}-month moving average (the ML model needs 6+ months of history)"
    )
    history = [
        {"month": str(p), "total": round(float(v), 2), "by_category": {c: round(float(complete.loc[p, c]), 2) for c in complete.columns if complete.loc[p, c] > 0}}
        for p, v in series.tail(12).items()
    ]
    return {
        "method": method,
        "months_of_history": int(len(series)),
        "history": history,
        "forecast": points,
        "next_month_by_category": by_category,
        "current_month": projection,
        "insights": _insights(series, complete, points, projection, budget_status(db, user_id, str(current))),
    }


def _insights(series, complete, points, projection, budgets) -> List[str]:
    tips: List[str] = []
    if projection and len(series) >= 3:
        avg3 = float(series.tail(3).mean())
        diff = (projection["projected_total"] - avg3) / avg3 * 100 if avg3 else 0
        if abs(diff) >= 10:
            direction = "above" if diff > 0 else "below"
            tips.append(
                f"This month is on track for {projection['projected_total']:,.0f}, "
                f"{abs(diff):.0f}% {direction} your 3-month average."
            )
    if len(complete.columns) and len(series) >= 4:
        last = complete.iloc[-1]
        baseline = complete.iloc[-4:-1].mean()
        changes = [
            (c, (last[c] - baseline[c]) / baseline[c] * 100)
            for c in complete.columns
            if baseline[c] >= 1000 and c not in LUMPY_CATEGORIES
        ]
        if changes:
            category, change = max(changes, key=lambda kv: abs(kv[1]))
            if abs(change) >= 20:
                word = "up" if change > 0 else "down"
                tips.append(f"{category} spending was {word} {abs(change):.0f}% last month compared with the 3 months before.")
    if len(points) > 1 and len(series) >= 3:
        nxt = points[1]["predicted"]  # points[0] is the current, incomplete month
        avg3 = float(series.tail(3).mean())
        if avg3 and abs(nxt - avg3) / avg3 >= 0.1:
            word = "higher" if nxt > avg3 else "lower"
            tips.append(f"Next month is forecast at {nxt:,.0f}, {abs(nxt - avg3) / avg3 * 100:.0f}% {word} than your recent average.")
    over = [b["category"] for b in budgets if b["status"] == "over"]
    warn = [b["category"] for b in budgets if b["status"] == "warning"]
    if over:
        tips.append(f"Over budget this month: {', '.join(over)}.")
    if warn:
        tips.append(f"Above 80% of budget: {', '.join(warn)}.")
    return tips
