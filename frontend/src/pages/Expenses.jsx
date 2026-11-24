import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api.js";
import { CATEGORY_COLORS, currentMonth, longMonth, moneyExact, shiftMonth, today } from "../format.js";

const PAGE_SIZE = 25;

function monthRange(month) {
  const [y, m] = month.split("-").map(Number);
  const last = new Date(y, m, 0).getDate();
  return { start: `${month}-01`, end: `${month}-${String(last).padStart(2, "0")}` };
}

export default function Expenses() {
  const [meta, setMeta] = useState({ categories: [], payment_methods: [] });
  const [month, setMonth] = useState(currentMonth());
  const [category, setCategory] = useState("");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(0);
  const [data, setData] = useState({ items: [], total: 0, total_amount: 0 });
  const [editing, setEditing] = useState(null); // null | {} (new) | expense
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const fileInput = useRef(null);

  useEffect(() => {
    api.meta().then(setMeta);
  }, []);

  const filters = { ...(month ? monthRange(month) : {}), category, search };

  const load = useCallback(() => {
    api
      .listExpenses({ ...filters, limit: PAGE_SIZE, offset: page * PAGE_SIZE })
      .then(setData)
      .catch((e) => setError(e.message));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [month, category, search, page]);

  useEffect(load, [load]);
  useEffect(() => setPage(0), [month, category, search]);

  async function remove(expense) {
    if (!window.confirm(`Delete "${expense.description || expense.category}" (${moneyExact(expense.amount)})?`)) return;
    await api.deleteExpense(expense.id);
    load();
  }

  async function importFile(file) {
    setError("");
    setMessage("");
    try {
      const result = await api.importCsv(file);
      setMessage(
        `Imported ${result.imported} expense${result.imported === 1 ? "" : "s"}` +
          (result.errors.length ? `. Skipped ${result.errors.length}: ${result.errors.slice(0, 3).join("; ")}` : ".")
      );
      load();
    } catch (e) {
      setError(e.message);
    }
  }

  async function exportFile() {
    const response = await api.exportCsv({ ...(month ? monthRange(month) : {}), category });
    const url = URL.createObjectURL(await response.blob());
    const a = Object.assign(document.createElement("a"), { href: url, download: `expenses${month ? "-" + month : ""}.csv` });
    a.click();
    URL.revokeObjectURL(url);
  }

  const pages = Math.max(1, Math.ceil(data.total / PAGE_SIZE));

  return (
    <div>
      <div className="page-head">
        <div>
          <h1>Expenses</h1>
          <p className="muted">
            {data.total} expense{data.total === 1 ? "" : "s"} · {moneyExact(data.total_amount)}
          </p>
        </div>
        <div className="row">
          <button className="btn" onClick={() => fileInput.current.click()}>Import CSV</button>
          <button className="btn" onClick={exportFile}>Export CSV</button>
          <button className="btn primary" onClick={() => setEditing({})}>Add expense</button>
          <input
            ref={fileInput}
            type="file"
            accept=".csv"
            hidden
            onChange={(e) => {
              if (e.target.files[0]) importFile(e.target.files[0]);
              e.target.value = "";
            }}
          />
        </div>
      </div>

      {message && <p className="notice">{message}</p>}
      {error && <p className="error">{error}</p>}

      <div className="filters card">
        <div className="month-switch">
          <button className="btn small" onClick={() => setMonth(shiftMonth(month || currentMonth(), -1))} aria-label="Previous month">‹</button>
          <span className="month-name">{month ? longMonth(month) : "All time"}</span>
          <button className="btn small" onClick={() => setMonth(shiftMonth(month || currentMonth(), 1))} disabled={!month || month === currentMonth()} aria-label="Next month">›</button>
          <button className="btn ghost small" onClick={() => setMonth(month ? "" : currentMonth())}>
            {month ? "Show all" : "This month"}
          </button>
        </div>
        <select value={category} onChange={(e) => setCategory(e.target.value)} aria-label="Category">
          <option value="">All categories</option>
          {meta.categories.map((c) => <option key={c}>{c}</option>)}
        </select>
        <input type="search" placeholder="Search description" value={search} onChange={(e) => setSearch(e.target.value)} />
      </div>

      <div className="card table-card">
        {data.items.length === 0 ? (
          <p className="muted pad">No expenses match these filters.</p>
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>Date</th>
                <th>Description</th>
                <th>Category</th>
                <th>Paid by</th>
                <th className="num">Amount</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {data.items.map((e) => (
                <tr key={e.id}>
                  <td className="muted nowrap">{e.date}</td>
                  <td>{e.description || "-"}</td>
                  <td><span className="tag" style={{ borderColor: CATEGORY_COLORS[e.category] }}>{e.category}</span></td>
                  <td className="muted">{e.payment_method}</td>
                  <td className="num"><strong>{moneyExact(e.amount)}</strong></td>
                  <td className="actions">
                    <button className="link" onClick={() => setEditing(e)}>Edit</button>
                    <button className="link danger" onClick={() => remove(e)}>Delete</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {pages > 1 && (
          <div className="pager">
            <button className="btn small" disabled={page === 0} onClick={() => setPage(page - 1)}>Previous</button>
            <span className="muted">Page {page + 1} of {pages}</span>
            <button className="btn small" disabled={page + 1 >= pages} onClick={() => setPage(page + 1)}>Next</button>
          </div>
        )}
      </div>

      {editing && (
        <ExpenseForm
          expense={editing}
          meta={meta}
          onClose={() => setEditing(null)}
          onSaved={() => {
            setEditing(null);
            load();
          }}
        />
      )}
    </div>
  );
}

function ExpenseForm({ expense, meta, onClose, onSaved }) {
  const isNew = !expense.id;
  const [form, setForm] = useState({
    amount: expense.amount ?? "",
    category: expense.category ?? "Food & Dining",
    description: expense.description ?? "",
    payment_method: expense.payment_method ?? "UPI",
    date: expense.date ?? today(),
  });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const update = (key) => (e) => setForm({ ...form, [key]: e.target.value });

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const body = { ...form, amount: Number(form.amount) };
      if (isNew) await api.createExpense(body);
      else await api.updateExpense(expense.id, body);
      onSaved();
    } catch (err) {
      setError(err.message);
      setBusy(false);
    }
  }

  return (
    <div className="modal-backdrop" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <form className="modal card" onSubmit={submit}>
        <h2>{isNew ? "Add expense" : "Edit expense"}</h2>
        <div className="form-grid">
          <label>
            Amount (₹)
            <input type="number" min="0.01" step="0.01" value={form.amount} onChange={update("amount")} required autoFocus />
          </label>
          <label>
            Date
            <input type="date" value={form.date} max={today()} onChange={update("date")} required />
          </label>
          <label>
            Category
            <select value={form.category} onChange={update("category")}>
              {meta.categories.map((c) => <option key={c}>{c}</option>)}
            </select>
          </label>
          <label>
            Paid by
            <select value={form.payment_method} onChange={update("payment_method")}>
              {meta.payment_methods.map((p) => <option key={p}>{p}</option>)}
            </select>
          </label>
          <label className="full">
            Description
            <input value={form.description} onChange={update("description")} maxLength={255} placeholder="e.g. Groceries at DMart" />
          </label>
        </div>
        {error && <p className="error">{error}</p>}
        <div className="row end">
          <button type="button" className="btn ghost" onClick={onClose}>Cancel</button>
          <button className="btn primary" disabled={busy}>{busy ? "Saving..." : "Save"}</button>
        </div>
      </form>
    </div>
  );
}
