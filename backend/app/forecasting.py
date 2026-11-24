"""Monthly spending forecasts.

Model
-----
A single *global* regression model is trained on the monthly totals of many
(synthetic) users. Every feature is divided by the user's recent spending
level (mean of the last 6 months), so the same model works for a student
spending 15k a month and a family spending 1.5 lakh.

Features for predicting month t:
    lag1..lag3       totals of the three previous months / level
    lag12            same month last year / level (or mean of lag1..3 if unknown)
    has_lag12        1 if a year of history exists
    month_sin/cos    month of the year, encoded cyclically
    festive          1 for October/November (Diwali season)

Target: total of month t / level.

Users with fewer than ``MIN_MONTHS_FOR_MODEL`` complete months get a moving
average forecast instead. Prediction intervals come from the empirical
distribution of relative errors in the backtest.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.linear_model import Ridge

BACKEND_DIR = Path(__file__).resolve().parent.parent
TRAINING_DATA = BACKEND_DIR / "data" / "synthetic_monthly_totals.csv"
MODEL_PATH = BACKEND_DIR / "models" / "forecaster.joblib"

MIN_MONTHS_FOR_MODEL = 6
FEATURE_NAMES = ["lag1", "lag2", "lag3", "lag12", "has_lag12", "month_sin", "month_cos", "festive"]


def make_features(history: Sequence[float], target_month: int) -> Tuple[np.ndarray, float]:
    """Build the feature vector for the month after ``history``.

    ``history`` holds monthly totals in time order (at least 6 values) and
    ``target_month`` is the calendar month (1-12) being predicted.
    Returns ``(features, level)``.
    """
    h = np.asarray(history, dtype=float)
    level = float(h[-6:].mean()) or 1.0
    lag1, lag2, lag3 = h[-1] / level, h[-2] / level, h[-3] / level
    has_lag12 = len(h) >= 12
    lag12 = h[-12] / level if has_lag12 else (lag1 + lag2 + lag3) / 3
    angle = 2 * np.pi * (target_month - 1) / 12
    features = np.array(
        [lag1, lag2, lag3, lag12, float(has_lag12), np.sin(angle), np.cos(angle), float(target_month in (10, 11))]
    )
    return features, level


def build_training_set(monthly: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray]:
    """Turn a (user_id, month, total) frame into a supervised learning set."""
    rows, targets = [], []
    for _, group in monthly.sort_values("month").groupby("user_id"):
        totals = group["total"].to_numpy(dtype=float)
        months = pd.PeriodIndex(group["month"], freq="M").month.to_numpy()
        for t in range(MIN_MONTHS_FOR_MODEL, len(totals)):
            x, level = make_features(totals[:t], int(months[t]))
            rows.append(x)
            targets.append(totals[t] / level)
    return np.vstack(rows), np.array(targets)


def candidate_models() -> Dict[str, object]:
    return {
        "Ridge regression": Ridge(alpha=1.0),
        "Gradient boosting": GradientBoostingRegressor(
            n_estimators=300, max_depth=3, learning_rate=0.05, subsample=0.8, random_state=0
        ),
    }


# --- simple baselines (also used as fallbacks) --------------------------------

def naive_last(history: Sequence[float], target_month: int) -> float:
    return float(history[-1])


def moving_average(history: Sequence[float], target_month: int, k: int = 3) -> float:
    return float(np.mean(history[-k:]))


def seasonal_naive(history: Sequence[float], target_month: int) -> float:
    return float(history[-12]) if len(history) >= 12 else moving_average(history, target_month)


BASELINES = {
    "Last month (naive)": naive_last,
    "3-month moving average": moving_average,
    "Same month last year (seasonal naive)": seasonal_naive,
}


@dataclass
class Forecaster:
    model: object
    name: str
    # quantiles of relative error (actual / predicted - 1) from the backtest
    error_quantiles: Tuple[float, float] = (-0.15, 0.15)
    metrics: Dict[str, Dict[str, float]] = field(default_factory=dict)

    def predict_next(self, history: Sequence[float], target_month: int) -> float:
        if len(history) < MIN_MONTHS_FOR_MODEL:
            return moving_average(history, target_month, k=min(3, len(history)))
        x, level = make_features(history, target_month)
        return max(0.0, float(self.model.predict(x.reshape(1, -1))[0]) * level)

    def forecast(self, history: Sequence[float], first_month: pd.Period, horizon: int = 3) -> List[dict]:
        """Recursive multi-step forecast with widening prediction intervals."""
        values = list(history)
        low_q, high_q = self.error_quantiles
        out = []
        for step in range(horizon):
            period = first_month + step
            prediction = self.predict_next(values, period.month)
            widen = np.sqrt(step + 1)
            out.append(
                {
                    "month": str(period),
                    "predicted": round(prediction, 2),
                    "lower": round(max(0.0, prediction * (1 + low_q * widen)), 2),
                    "upper": round(prediction * (1 + high_q * widen), 2),
                }
            )
            values.append(prediction)
        return out

    @property
    def method_description(self) -> str:
        return f"{self.name} (global model on normalised monthly totals)"

    def save(self, path: Path = MODEL_PATH) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self, path)


def fit_forecaster(monthly: pd.DataFrame, model_name: str = "Gradient boosting") -> Forecaster:
    x, y = build_training_set(monthly)
    model = candidate_models()[model_name]
    model.fit(x, y)
    return Forecaster(model=model, name=model_name)


def backtest(
    monthly: pd.DataFrame, predict, last_n_months: int = 12
) -> Tuple[Dict[str, float], np.ndarray]:
    """One-step-ahead rolling-origin backtest over each user's last ``last_n_months``.

    ``predict(history, target_month)`` returns a forecast. Returns metrics and
    the array of relative errors (actual / predicted - 1).
    """
    abs_pct, abs_err, rel = [], [], []
    for _, group in monthly.sort_values("month").groupby("user_id"):
        totals = group["total"].to_numpy(dtype=float)
        months = pd.PeriodIndex(group["month"], freq="M").month.to_numpy()
        for t in range(max(MIN_MONTHS_FOR_MODEL, len(totals) - last_n_months), len(totals)):
            prediction = predict(totals[:t], int(months[t]))
            actual = totals[t]
            abs_err.append(abs(actual - prediction))
            abs_pct.append(abs(actual - prediction) / actual)
            rel.append(actual / prediction - 1 if prediction > 0 else 0.0)
    metrics = {
        "MAPE": round(float(np.mean(abs_pct)) * 100, 2),
        "median_APE": round(float(np.median(abs_pct)) * 100, 2),
        "MAE": round(float(np.mean(abs_err)), 2),
    }
    return metrics, np.array(rel)


def load_training_data(path: Path = TRAINING_DATA) -> pd.DataFrame:
    return pd.read_csv(path)


def load_or_train(path: Path = MODEL_PATH) -> Forecaster:
    """Load the saved forecaster, or train one from the bundled synthetic data."""
    if path.exists():
        return joblib.load(path)
    monthly = load_training_data()
    users = monthly["user_id"].unique()
    train_users = set(users[: int(len(users) * 0.8)])
    train = monthly[monthly["user_id"].isin(train_users)]
    test = monthly[~monthly["user_id"].isin(train_users)]
    forecaster = fit_forecaster(train)
    metrics, rel = backtest(test, forecaster.predict_next)
    forecaster.error_quantiles = (float(np.quantile(rel, 0.1)), float(np.quantile(rel, 0.9)))
    forecaster.metrics = {forecaster.name: metrics}
    forecaster.save(path)
    return forecaster


def monthly_series(dates: Sequence, amounts: Sequence[float], end: Optional[pd.Period] = None) -> pd.Series:
    """Aggregate transactions into a gap-free monthly total series."""
    if len(dates) == 0:
        return pd.Series(dtype=float)
    frame = pd.DataFrame({"date": pd.to_datetime(list(dates)), "amount": list(map(float, amounts))})
    totals = frame.groupby(frame["date"].dt.to_period("M"))["amount"].sum()
    end = end or totals.index.max()
    full = pd.period_range(totals.index.min(), end, freq="M")
    return totals.reindex(full, fill_value=0.0)


def dump_metrics(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2))
