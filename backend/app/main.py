"""FastAPI application.

Run locally:
    uvicorn app.main:app --reload
API docs: http://localhost:8000/docs
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import __version__
from .config import settings
from .database import Base, SessionLocal, engine
from .demo_account import DEMO_EMAIL, DEMO_PASSWORD, reset_demo_account
from .forecasting import load_or_train
from .routers import auth, expenses, insights
from .static_site import mount_frontend


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    app.state.forecaster = load_or_train()
    if settings.demo_mode:
        with SessionLocal() as db:
            reset_demo_account(db)
    yield


app = FastAPI(
    title="Smart Expense Tracker with Forecasting",
    description="Track expenses, set budgets and forecast future spending with machine learning.",
    version=__version__,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(expenses.router)
app.include_router(insights.router)


@app.get("/api/health", tags=["meta"])
def health():
    return {"status": "ok", "version": __version__}


@app.get("/api/demo", tags=["meta"])
def demo_info():
    """Login details of the public demo account (only when DEMO_MODE is on)."""
    if not settings.demo_mode:
        return {"enabled": False}
    return {"enabled": True, "email": DEMO_EMAIL, "password": DEMO_PASSWORD}


# Must come last: serves the React app for every path not handled above.
mount_frontend(app)
