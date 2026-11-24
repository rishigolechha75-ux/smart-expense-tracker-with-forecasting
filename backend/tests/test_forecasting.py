"""Unit tests for the forecasting model and synthetic data generator."""

import random
from datetime import date

import numpy as np
import pandas as pd
import pytest

from app.demo_data import generate_history
from app.forecasting import (
    MIN_MONTHS_FOR_MODEL,
    load_or_train,
    make_features,
    monthly_series,
    moving_average,
    seasonal_naive,
)


@pytest.fixture(scope="module")
def forecaster():
    return load_or_train()


def test_features_are_scale_invariant():
    history = [10_000, 12_000, 11_000, 9_000, 13_000, 12_500, 11_800]
    small, _ = make_features(history, 3)
    large, _ = make_features([v * 10 for v in history], 3)
    assert np.allclose(small, large)


def test_features_flag_festive_months_and_missing_year():
    x, _ = make_features([100] * 8, 10)
    names = dict(zip(["lag1", "lag2", "lag3", "lag12", "has_lag12", "sin", "cos", "festive"], x))
    assert names["festive"] == 1.0 and names["has_lag12"] == 0.0


def test_forecast_scales_with_spending_level(forecaster):
    history = [20_000, 21_000, 19_500, 22_000, 20_500, 21_500, 20_800, 21_200]
    low = forecaster.predict_next(history, 3)
    high = forecaster.predict_next([v * 5 for v in history], 3)
    assert high == pytest.approx(low * 5, rel=1e-6)
    assert 15_000 < low < 27_000  # stays in a sensible range for a stable history


def test_short_history_falls_back_to_moving_average(forecaster):
    history = [1000, 2000, 3000]
    assert len(history) < MIN_MONTHS_FOR_MODEL
    assert forecaster.predict_next(history, 5) == pytest.approx(2000)


def test_multi_step_forecast_intervals_widen(forecaster):
    history = [20_000 + 500 * np.sin(i) for i in range(18)]
    points = forecaster.forecast(history, pd.Period("2026-03", freq="M"), horizon=3)
    assert [p["month"] for p in points] == ["2026-03", "2026-04", "2026-05"]
    widths = [p["upper"] - p["lower"] for p in points]
    assert widths[0] < widths[-1]


def test_baselines():
    history = list(range(1, 25))
    assert moving_average(history, 1) == 23
    assert seasonal_naive(history, 1) == 13


def test_monthly_series_fills_gaps():
    series = monthly_series([date(2025, 1, 5), date(2025, 3, 2)], [100, 50])
    assert list(series.index.astype(str)) == ["2025-01", "2025-02", "2025-03"]
    assert list(series) == [100, 0, 50]


def test_generator_is_reproducible_and_realistic():
    a = generate_history(random.Random(1), months=12, end=date(2025, 12, 31))
    b = generate_history(random.Random(1), months=12, end=date(2025, 12, 31))
    assert [(t.date, t.amount) for t in a] == [(t.date, t.amount) for t in b]
    assert all(t.amount > 0 and t.date <= date(2025, 12, 31) for t in a)

    frame = pd.DataFrame([(t.date.month, t.category, t.amount) for t in a], columns=["m", "c", "a"])
    rent_months = frame[frame.c == "Rent"].m.nunique()
    assert rent_months == 12  # rent is paid every month
    shopping = frame[frame.c == "Shopping"].groupby("m").a.sum()
    assert shopping[10] > shopping.drop([10, 11]).median()  # festive season spike
