const inr = new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 });
const inrExact = new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", minimumFractionDigits: 2 });

export const money = (value) => inr.format(value || 0);
export const moneyExact = (value) => inrExact.format(value || 0);

// compact axis labels: 12500 -> "12.5k", 150000 -> "1.5L"
export function compact(value) {
  if (value >= 100000) return `${(value / 100000).toFixed(1).replace(/\.0$/, "")}L`;
  if (value >= 1000) return `${(value / 1000).toFixed(1).replace(/\.0$/, "")}k`;
  return String(Math.round(value));
}

export function monthLabel(month) {
  const [y, m] = month.split("-").map(Number);
  return new Date(y, m - 1, 1).toLocaleDateString("en-IN", { month: "short", year: "2-digit" });
}

export function longMonth(month) {
  const [y, m] = month.split("-").map(Number);
  return new Date(y, m - 1, 1).toLocaleDateString("en-IN", { month: "long", year: "numeric" });
}

export function currentMonth() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

export function shiftMonth(month, delta) {
  const [y, m] = month.split("-").map(Number);
  const d = new Date(y, m - 1 + delta, 1);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

export function today() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

// Fixed colour per category so charts stay consistent across pages
export const CATEGORY_COLORS = {
  Rent: "#8c5a3c",
  Groceries: "#5b8a4a",
  "Food & Dining": "#c2662d",
  Transport: "#3d6f8f",
  Utilities: "#c9a227",
  Shopping: "#a8435c",
  Entertainment: "#6c5a9c",
  Health: "#3f9488",
  Education: "#4f5d8a",
  Travel: "#d08b5b",
  Other: "#8a8578",
};
