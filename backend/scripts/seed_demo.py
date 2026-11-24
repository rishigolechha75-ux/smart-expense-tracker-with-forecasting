"""Create a local demo account filled with 18 months of sample expenses and budgets.

Usage:
    python scripts/seed_demo.py
Then log in at http://localhost:5173 with demo@example.com / demo-password.
For local development only.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import Base, SessionLocal, engine  # noqa: E402
from app.demo_account import DEMO_EMAIL, reset_demo_account  # noqa: E402


def main() -> None:
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        count = reset_demo_account(db)
    print(f"Demo account ready: {DEMO_EMAIL} ({count} expenses)")


if __name__ == "__main__":
    main()
