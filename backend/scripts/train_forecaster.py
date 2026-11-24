"""Generate synthetic training data, compare forecasting methods and save the model.

Steps:
  1. Simulate ``--users`` people with ``--months`` months of transactions each
     and save their monthly totals to data/synthetic_monthly_totals.csv.
  2. Split users 80/20. Train the ML models on the first group.
  3. Backtest every method on the held-out users: one-step-ahead forecasts over
     each user's last 12 months (rolling origin).
  4. Save the best model to models/forecaster.joblib and metrics to reports/.

Usage:
    python scripts/train_forecaster.py
    python scripts/train_forecaster.py --users 400 --months 36 --seed 7
"""

from __future__ import annotations

import argparse
import random
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.demo_data import generate_history  # noqa: E402
from app.forecasting import (  # noqa: E402
    BASELINES,
    MODEL_PATH,
    TRAINING_DATA,
    backtest,
    candidate_models,
    dump_metrics,
    fit_forecaster,
)

REPORTS = Path(__file__).resolve().parent.parent / "reports"


def simulate(users: int, months: int, seed: int) -> pd.DataFrame:
    rng = random.Random(seed)
    end = date(2025, 12, 31)
    rows = []
    for user_id in range(users):
        frame = pd.DataFrame(
            [(t.date, t.amount) for t in generate_history(rng, months=months, end=end)],
            columns=["date", "amount"],
        )
        totals = frame.groupby(pd.to_datetime(frame["date"]).dt.to_period("M"))["amount"].sum()
        rows.extend((user_id, str(p), round(v, 2)) for p, v in totals.items())
    return pd.DataFrame(rows, columns=["user_id", "month", "total"])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--users", type=int, default=300)
    parser.add_argument("--months", type=int, default=36)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    monthly = simulate(args.users, args.months, args.seed)
    TRAINING_DATA.parent.mkdir(parents=True, exist_ok=True)
    monthly.to_csv(TRAINING_DATA, index=False)
    print(f"Simulated {args.users} users x {args.months} months -> {TRAINING_DATA}")

    users = monthly["user_id"].unique()
    train_users = set(users[: int(len(users) * 0.8)])
    train = monthly[monthly["user_id"].isin(train_users)]
    test = monthly[~monthly["user_id"].isin(train_users)]

    results, fitted = {}, {}
    for name, fn in BASELINES.items():
        results[name], _ = backtest(test, fn)
    for name in candidate_models():
        forecaster = fit_forecaster(train, name)
        results[name], rel = backtest(test, forecaster.predict_next)
        forecaster.error_quantiles = (float(np.quantile(rel, 0.1)), float(np.quantile(rel, 0.9)))
        fitted[name] = forecaster

    print(f"\nOne-step-ahead backtest on {len(test['user_id'].unique())} held-out users (last 12 months each)\n")
    print(f"{'Method':<40}{'MAPE':>8}{'Median APE':>12}{'MAE (INR)':>12}")
    for name, m in sorted(results.items(), key=lambda kv: kv[1]["MAPE"]):
        print(f"{name:<40}{m['MAPE']:>7.1f}%{m['median_APE']:>11.1f}%{m['MAE']:>12,.0f}")

    best = min(fitted, key=lambda n: results[n]["MAPE"])
    chosen = fitted[best]
    chosen.metrics = results
    chosen.save(MODEL_PATH)
    print(f"\nSaved {best} -> {MODEL_PATH}")
    print(f"80% prediction interval (relative error): {chosen.error_quantiles[0]:+.1%} to {chosen.error_quantiles[1]:+.1%}")

    dump_metrics(
        REPORTS / "forecast_metrics.json",
        {
            "users_simulated": args.users,
            "months_per_user": args.months,
            "held_out_users": int(len(test["user_id"].unique())),
            "evaluation": "one-step-ahead rolling origin over each held-out user's last 12 months",
            "results": results,
            "chosen_model": best,
            "interval_80pct_relative_error": [round(q, 4) for q in chosen.error_quantiles],
        },
    )
    print(f"Saved metrics -> {REPORTS / 'forecast_metrics.json'}")


if __name__ == "__main__":
    main()
