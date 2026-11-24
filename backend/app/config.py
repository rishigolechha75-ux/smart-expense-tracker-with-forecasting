"""Application settings, read from environment variables."""

from __future__ import annotations

import os
import secrets
import warnings


class Settings:
    def __init__(self) -> None:
        # SQLite needs no setup; set DATABASE_URL to use PostgreSQL, e.g.
        # postgresql+psycopg://expense:expense@localhost:5432/expense_tracker
        self.database_url = os.getenv("DATABASE_URL", "sqlite:///./expense_tracker.db")
        self.jwt_secret = os.getenv("JWT_SECRET") or self._dev_secret()
        self.jwt_algorithm = "HS256"
        self.access_token_minutes = int(os.getenv("ACCESS_TOKEN_MINUTES", "1440"))
        self.cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
        # Hosted demo: create/reset the demo account on every start
        self.demo_mode = os.getenv("DEMO_MODE", "").lower() in {"1", "true", "yes"}

    @staticmethod
    def _dev_secret() -> str:
        warnings.warn("JWT_SECRET is not set; using a random secret (tokens reset on restart).")
        return secrets.token_urlsafe(32)


settings = Settings()
