"""Generate realistic synthetic expense histories.

Used for two things:
  * seeding a demo account so the dashboard has data to show, and
  * creating many synthetic users to train and backtest the forecasting model.

The generator models patterns seen in real personal spending (amounts in INR):
fixed rent with yearly increases, weekly groceries, summer electricity bills,
festive-season (Oct/Nov) shopping, semester fees in January and July,
occasional travel, slow lifestyle inflation and random one-off spikes.
"""

from __future__ import annotations

import calendar
import random
from dataclasses import dataclass
from datetime import date
from typing import List, Optional

DESCRIPTIONS = {
    "Rent": ["Monthly rent"],
    "Groceries": ["BigBasket order", "Vegetables and fruits", "Kirana store", "Supermarket", "Milk and bread"],
    "Food & Dining": ["Swiggy", "Zomato", "Cafe with friends", "Lunch at office", "Dinner out", "Chai and snacks"],
    "Transport": ["Uber", "Ola", "Metro card recharge", "Petrol", "Auto rickshaw", "Rapido"],
    "Utilities": ["Electricity bill", "Mobile recharge", "Broadband", "Water bill", "Gas cylinder"],
    "Shopping": ["Amazon", "Flipkart", "Myntra", "Clothes", "Electronics accessory", "Home items"],
    "Entertainment": ["Movie tickets", "Netflix", "Spotify", "Concert", "Gaming"],
    "Health": ["Pharmacy", "Doctor consultation", "Gym membership", "Lab tests"],
    "Education": ["Semester fees", "Online course", "Books", "Exam fee"],
    "Travel": ["Train tickets", "Flight tickets", "Hotel booking", "Weekend trip"],
    "Other": ["Gift", "Donation", "Haircut", "Laundry"],
}

PAYMENT_WEIGHTS = {"UPI": 0.6, "Card": 0.25, "Cash": 0.1, "Net Banking": 0.05}


@dataclass
class Transaction:
    date: date
    category: str
    amount: float
    description: str
    payment_method: str


@dataclass
class Profile:
    """Spending habits of one synthetic person."""

    rent: float
    grocery_trip: float
    dining_rate: float      # dining transactions per month
    dining_spend: float
    shopping_level: float
    travel_prob: float
    student: bool
    monthly_growth: float   # lifestyle inflation per month
    noise: float

    @classmethod
    def random(cls, rng: random.Random) -> "Profile":
        scale = rng.choice([0.6, 0.8, 1.0, 1.0, 1.3, 1.7])
        return cls(
            rent=round(rng.uniform(7000, 22000) * scale, -2),
            grocery_trip=rng.uniform(500, 1400) * scale,
            dining_rate=rng.uniform(4, 16),
            dining_spend=rng.uniform(200, 650) * scale,
            shopping_level=rng.uniform(1500, 6000) * scale,
            travel_prob=rng.uniform(0.08, 0.3),
            student=rng.random() < 0.35,
            monthly_growth=rng.uniform(-0.002, 0.012),
            noise=rng.uniform(0.15, 0.35),
        )


def _add_months(d: date, months: int) -> date:
    month_index = d.year * 12 + d.month - 1 + months
    return date(month_index // 12, month_index % 12 + 1, 1)


def _payment(rng: random.Random) -> str:
    return rng.choices(list(PAYMENT_WEIGHTS), weights=list(PAYMENT_WEIGHTS.values()))[0]


def generate_history(
    rng: random.Random,
    months: int = 18,
    end: Optional[date] = None,
    profile: Optional[Profile] = None,
) -> List[Transaction]:
    """Return transactions for ``months`` months ending on ``end`` (inclusive)."""
    end = end or date.today()
    profile = profile or Profile.random(rng)
    first_month = _add_months(date(end.year, end.month, 1), -(months - 1))
    transactions: List[Transaction] = []

    def add(day: date, category: str, amount: float) -> None:
        if day <= end and amount > 0:
            transactions.append(
                Transaction(day, category, round(amount, 2), rng.choice(DESCRIPTIONS[category]), _payment(rng))
            )

    for i in range(months):
        month_start = _add_months(first_month, i)
        y, m = month_start.year, month_start.month
        days = calendar.monthrange(y, m)[1]
        growth = (1 + profile.monthly_growth) ** i

        def day(lo: int = 1, hi: int = days) -> date:
            return date(y, m, rng.randint(lo, min(hi, days)))

        def jitter(value: float) -> float:
            return value * max(0.2, rng.gauss(1, profile.noise))

        # Rent: fixed, paid early in the month, increases ~8% each April
        years_of_tenure = sum(1 for k in range(1, i + 1) if _add_months(first_month, k).month == 4)
        add(day(1, 5), "Rent", profile.rent * (1.08 ** years_of_tenure))

        # Groceries: about weekly
        for _ in range(rng.randint(3, 6)):
            add(day(), "Groceries", jitter(profile.grocery_trip * growth))

        # Dining: more in festive months and December
        festive = 1.35 if m in (10, 11, 12) else 1.0
        for _ in range(max(1, int(rng.gauss(profile.dining_rate * festive, 2)))):
            add(day(), "Food & Dining", jitter(profile.dining_spend * growth))

        # Transport: many small trips
        for _ in range(rng.randint(8, 20)):
            add(day(), "Transport", jitter(rng.uniform(60, 350)))

        # Utilities: electricity peaks in summer (Apr-Jun) with AC use
        summer = {4: 1.5, 5: 1.8, 6: 1.6}.get(m, 1.0)
        add(day(5, 12), "Utilities", jitter(1100 * summer * growth))
        add(day(1, 28), "Utilities", 299 + rng.choice([0, 0, 100]))  # mobile
        add(day(1, 28), "Utilities", 799)  # broadband

        # Shopping: big spike in festive season (Diwali), sales in January and July
        shopping_season = {10: 2.6, 11: 1.9, 1: 1.3, 7: 1.3}.get(m, 1.0)
        for _ in range(rng.randint(1, 4)):
            add(day(), "Shopping", jitter(profile.shopping_level * shopping_season * growth / 2.5))

        # Entertainment: subscriptions + outings
        add(day(1, 5), "Entertainment", 199)
        for _ in range(rng.randint(0, 3)):
            add(day(), "Entertainment", jitter(450))

        # Health: gym monthly, occasional medical
        if rng.random() < 0.6:
            add(day(1, 7), "Health", 1200)
        if rng.random() < 0.3:
            add(day(), "Health", jitter(900))

        # Education: semester fees in January and July for students
        if profile.student and m in (1, 7):
            add(day(5, 20), "Education", rng.uniform(25000, 60000))
        elif rng.random() < 0.15:
            add(day(), "Education", jitter(1500))

        # Travel: more likely in May and December
        travel_prob = profile.travel_prob * (2.0 if m in (5, 12) else 1.0)
        if rng.random() < travel_prob:
            add(day(), "Travel", jitter(rng.uniform(3000, 15000)))

        # One-off spikes (gifts, repairs) and miscellaneous
        if rng.random() < 0.08:
            add(day(), "Other", rng.uniform(3000, 12000))
        for _ in range(rng.randint(0, 2)):
            add(day(), "Other", jitter(400))

    transactions.sort(key=lambda t: t.date)
    return transactions
