"""A ready-made demo account with 18 months of sample expenses and budgets.

Created by ``scripts/seed_demo.py`` for local use, and automatically on
startup when ``DEMO_MODE=1`` (used by the hosted demo).
"""

from __future__ import annotations

import random
from datetime import date

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .demo_data import generate_history
from .models import Budget, Expense, User
from .security import hash_password

DEMO_EMAIL = "demo@example.com"
DEMO_PASSWORD = "demo-password"
DEMO_BUDGETS = {"Groceries": 6000, "Food & Dining": 5000, "Shopping": 6000, "Transport": 3000, "Entertainment": 2000}


def reset_demo_account(db: Session) -> int:
    """Create (or reset) the demo account. Returns the number of expenses added."""
    user = db.scalar(select(User).where(User.email == DEMO_EMAIL))
    if user is None:
        user = User(name="Demo User", email=DEMO_EMAIL, password_hash=hash_password(DEMO_PASSWORD))
        db.add(user)
        db.flush()
    db.execute(delete(Expense).where(Expense.user_id == user.id))
    db.execute(delete(Budget).where(Budget.user_id == user.id))
    history = generate_history(random.Random(2024), months=18, end=date.today())
    db.add_all(
        Expense(user_id=user.id, date=t.date, amount=t.amount, category=t.category,
                description=t.description, payment_method=t.payment_method)
        for t in history
    )
    db.add_all(Budget(user_id=user.id, category=c, monthly_limit=v) for c, v in DEMO_BUDGETS.items())
    db.commit()
    return len(history)
