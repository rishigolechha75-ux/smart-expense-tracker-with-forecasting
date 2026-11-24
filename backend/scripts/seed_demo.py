"""Create a local demo account filled with 18 months of sample expenses and budgets.

Usage:
    python scripts/seed_demo.py
Then log in at http://localhost:5173 with:
    email:    demo@example.com
    password: demo-password

For local development only.
"""

from __future__ import annotations

import random
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import delete, select  # noqa: E402

from app.database import Base, SessionLocal, engine  # noqa: E402
from app.demo_data import generate_history  # noqa: E402
from app.models import Budget, Expense, User  # noqa: E402
from app.security import hash_password  # noqa: E402

DEMO_EMAIL = "demo@example.com"
DEMO_PASSWORD = "demo-password"
DEMO_BUDGETS = {"Groceries": 6000, "Food & Dining": 5000, "Shopping": 6000, "Transport": 3000, "Entertainment": 2000}


def main() -> None:
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
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
        print(f"Demo account ready: {DEMO_EMAIL} / {DEMO_PASSWORD} ({len(history)} expenses)")


if __name__ == "__main__":
    main()
