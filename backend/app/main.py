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
from .database import Base, engine
from .forecasting import load_or_train
from .routers import auth, expenses, insights


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    app.state.forecaster = load_or_train()
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
