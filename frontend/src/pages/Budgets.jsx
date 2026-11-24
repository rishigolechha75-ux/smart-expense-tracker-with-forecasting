import { useEffect, useState } from "react";
import { api } from "../api.js";
import { currentMonth, longMonth, money } from "../format.js";
import { BudgetBar } from "./Dashboard.jsx";

export default function Budgets() {
  const [categories, setCategories] = useState([]);
  const [budgets, setBudgets] = useState([]);
  const [averages, setAverages] = useState({});
  const [drafts, setDrafts] = useState({});
  const [error, setError] = useState("");

  useEffect(() => {
    api.meta().then((m) => setCategories(m.categories));
    api.budgets(currentMonth()).then(setBudgets).catch((e) => setError(e.message));
    // average of the last 3 complete months, as a starting point for limits
    api.monthly(4).then((months) => {
      const complete = months.slice(0, -1);
      const sums = {};
      complete.forEach((m) =>
        Object.entries(m.by_category).forEach(([c, v]) => (sums[c] = (sums[c] || 0) + v))
      );
      setAverages(Object.fromEntries(Object.entries(sums).map(([c, v]) => [c, v / Math.max(1, complete.length)])));
    });
  }, []);

  const byCategory = Object.fromEntries(budgets.map((b) => [b.category, b]));

  async function save(category) {
    const value = Number(drafts[category]);
    if (!value || value <= 0) return;
    setError("");
    try {
      setBudgets(await api.setBudget({ category, monthly_limit: value }));
      setDrafts({ ...drafts, [category]: "" });
    } catch (e) {
      setError(e.message);
    }
  }

  async function remove(category) {
    await api.deleteBudget(category);
    setBudgets(budgets.filter((b) => b.category !== category));
  }

  return (
    <div>
      <div className="page-head">
        <div>
          <h1>Budgets</h1>
          <p className="muted">Monthly limits per category · status for {longMonth(currentMonth())}</p>
        </div>
      </div>
      {error && <p className="error">{error}</p>}
      <div className="card">
        <table className="table budgets-table">
          <thead>
            <tr>
              <th>Category</th>
              <th>This month</th>
              <th className="num">3-month average</th>
              <th>Monthly limit</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {categories.map((c) => {
              const b = byCategory[c];
              return (
                <tr key={c}>
                  <td><strong>{c}</strong></td>
                  <td className="budget-cell">{b ? <BudgetBar budget={b} showLabel={false} /> : <span className="muted">No limit</span>}</td>
                  <td className="num muted">{averages[c] ? money(averages[c]) : "-"}</td>
                  <td>
                    <form
                      className="inline-form"
                      onSubmit={(e) => {
                        e.preventDefault();
                        save(c);
                      }}
                    >
                      <input
                        type="number"
                        min="1"
                        step="1"
                        placeholder={b ? String(b.monthly_limit) : averages[c] ? String(Math.round(averages[c] / 100) * 100) : "Amount"}
                        value={drafts[c] ?? ""}
                        onChange={(e) => setDrafts({ ...drafts, [c]: e.target.value })}
                        aria-label={`Monthly limit for ${c}`}
                      />
                      <button className="btn small">{b ? "Update" : "Set"}</button>
                    </form>
                  </td>
                  <td>{b && <button className="link danger" onClick={() => remove(c)}>Remove</button>}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
