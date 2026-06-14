import { useEffect, useState } from "react";
import api, { formatError } from "@/utils/api";
import { useAuth } from "@/contexts/AuthContext";
import { CheckCircle, Clock, Plus, X, DownloadSimple, ArrowUp, ArrowDown, Wallet } from "@phosphor-icons/react";

const MONTHS = ["", "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December"];

const inr = (n) => `₹${Math.abs(Number(n) || 0).toLocaleString("en-IN")}`;

function balanceBadge(balance, status) {
  if (balance > 0) return <span className="inline-flex items-center gap-1 px-2 py-0.5 text-xs font-medium rounded border bg-sky-50 text-sky-700 border-sky-200 dark:bg-sky-950 dark:text-sky-300 dark:border-sky-800"><ArrowUp size={11} />{status}</span>;
  if (balance < 0) return <span className="inline-flex items-center gap-1 px-2 py-0.5 text-xs font-medium rounded border bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-950 dark:text-amber-300 dark:border-amber-800"><Clock size={11} />{status}</span>;
  return <span className="inline-flex items-center gap-1 px-2 py-0.5 text-xs font-medium rounded border bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950 dark:text-emerald-300 dark:border-emerald-800"><CheckCircle size={11} />Up to Date</span>;
}

/* ── Record-payment dialog: any amount, shows allocation ─────────────────── */
function RecordPaymentDialog({ row, month, year, onSave, onClose }) {
  const [form, setForm] = useState({ amount: row.rate || 100, payment_method: "cash" });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);

  const submit = async (e) => {
    e.preventDefault();
    setLoading(true); setError("");
    try {
      const res = await api.post("/contributions/pay", {
        member_id: row.member_id, month, year,
        amount: parseFloat(form.amount), payment_method: form.payment_method,
      });
      setResult(res.data);
    } catch (err) {
      setError(formatError(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
      <div className="bg-card rounded-lg shadow-lg w-full max-w-sm">
        <div className="flex items-center justify-between px-5 py-4 border-b border-border">
          <div>
            <h3 className="font-semibold text-foreground font-heading">Record Payment</h3>
            <p className="text-xs text-muted-foreground">{row.member_name} — {MONTHS[month]} {year}</p>
          </div>
          <button onClick={onClose} className="text-muted-foreground/70 hover:text-foreground"><X size={18} /></button>
        </div>

        {result ? (
          <div className="p-5 space-y-4">
            <div className="rounded-md bg-emerald-50 dark:bg-emerald-950 border border-emerald-200 dark:border-emerald-800 px-4 py-3">
              <p className="text-sm font-medium text-emerald-800 dark:text-emerald-300">Payment recorded — {inr(result.amount)}</p>
              <p className="text-xs text-emerald-700/80 dark:text-emerald-400/80 mt-0.5">Receipt {result.receipt_number}</p>
            </div>
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-2">How it was applied</p>
              <ul className="space-y-1 text-sm">
                {(result.allocation || []).map((a, i) => (
                  <li key={i} className="flex justify-between">
                    <span className="text-muted-foreground">
                      {a.kind === "arrears" ? `Arrears ${a.year === "opening" ? "(carried)" : `${a.year}-${String(a.month).padStart(2,"0")}`}`
                        : a.kind === "current" ? "This month" : "Advance credit"}
                    </span>
                    <span className="font-medium text-foreground">{inr(a.amount)}</span>
                  </li>
                ))}
              </ul>
            </div>
            <div className="flex items-center justify-between pt-2 border-t border-border">
              <span className="text-sm text-muted-foreground">New balance</span>
              <span className={`text-sm font-semibold ${result.balance < 0 ? "text-amber-600" : result.balance > 0 ? "text-sky-600" : "text-emerald-600"}`}>
                {result.balance < 0 ? `-${inr(result.balance)} due` : result.balance > 0 ? `${inr(result.balance)} advance` : "Up to date"}
              </span>
            </div>
            <button onClick={() => { onSave(); onClose(); }}
              className="w-full px-4 py-2 bg-primary text-primary-foreground rounded-md text-sm font-medium hover:bg-primary/90">Done</button>
          </div>
        ) : (
          <form onSubmit={submit} className="p-5 space-y-4">
            <div className="rounded-md bg-muted/50 px-3 py-2 text-xs text-muted-foreground flex justify-between">
              <span>Prior pending: <b className="text-amber-600">{inr(row.prior_pending)}</b></span>
              <span>Rate: <b className="text-foreground">{inr(row.rate)}</b></span>
            </div>
            <div>
              <label className="block text-sm font-medium text-foreground mb-1">Amount (₹) *</label>
              <input type="number" required min="1" value={form.amount}
                onChange={e => setForm(p => ({ ...p, amount: e.target.value }))}
                className="w-full border border-input rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring/30 focus:border-primary" />
              <p className="text-xs text-muted-foreground mt-1">Extra clears oldest arrears first, then becomes advance.</p>
            </div>
            <div>
              <label className="block text-sm font-medium text-foreground mb-1">Payment Method *</label>
              <select value={form.payment_method} onChange={e => setForm(p => ({ ...p, payment_method: e.target.value }))}
                className="w-full border border-input rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring/30 focus:border-primary">
                <option value="cash">Cash</option>
                <option value="upi">UPI</option>
                <option value="bank_transfer">Bank Transfer</option>
              </select>
            </div>
            {error && <p className="text-destructive text-sm bg-destructive/10 border border-destructive/30 rounded px-3 py-2">{error}</p>}
            <div className="flex gap-3">
              <button type="button" onClick={onClose} className="flex-1 px-4 py-2 border border-input text-foreground rounded-md text-sm hover:bg-muted/60">Cancel</button>
              <button type="submit" disabled={loading}
                className="flex-1 px-4 py-2 bg-primary text-primary-foreground rounded-md text-sm font-medium hover:bg-primary/90 disabled:opacity-60">
                {loading ? "Recording..." : "Record Payment"}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}

/* ── Per-member ledger drill-down ───────────────────────────────────────── */
function LedgerDialog({ memberId, onClose }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  useEffect(() => {
    api.get(`/contributions/ledger/${memberId}`)
      .then(r => setData(r.data))
      .catch(e => setError(formatError(e)));
  }, [memberId]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
      <div className="bg-card rounded-lg shadow-lg w-full max-w-2xl max-h-[85vh] flex flex-col">
        <div className="flex items-center justify-between px-5 py-4 border-b border-border">
          <div>
            <h3 className="font-semibold text-foreground font-heading">Member Ledger</h3>
            {data && <p className="text-xs text-muted-foreground">{data.member.name} · {data.member.member_code}</p>}
          </div>
          <button onClick={onClose} className="text-muted-foreground/70 hover:text-foreground"><X size={18} /></button>
        </div>
        <div className="overflow-auto p-2">
          {error ? <p className="p-6 text-center text-destructive text-sm">{error}</p>
            : !data ? <p className="p-6 text-center text-muted-foreground/70">Loading…</p>
            : (
              <table className="w-full data-table text-sm">
                <thead><tr>
                  <th>Month</th><th className="text-right">Prior Pending</th><th className="text-right">Advance</th>
                  <th className="text-right">Rate</th><th className="text-right">Paid</th><th className="text-right">Balance</th><th>Status</th>
                </tr></thead>
                <tbody>
                  {data.rows.map((r, i) => (
                    <tr key={i}>
                      <td className="font-medium">{MONTHS[r.month]} {r.year}</td>
                      <td className="text-right text-amber-600">{r.prior_pending ? inr(r.prior_pending) : "-"}</td>
                      <td className="text-right text-sky-600">{r.prior_advance ? inr(r.prior_advance) : "-"}</td>
                      <td className="text-right">{inr(r.rate)}</td>
                      <td className="text-right text-emerald-600">{r.paid ? inr(r.paid) : "-"}</td>
                      <td className={`text-right font-semibold ${r.balance < 0 ? "text-amber-600" : r.balance > 0 ? "text-sky-600" : "text-emerald-600"}`}>
                        {r.balance < 0 ? `-${inr(r.balance)}` : inr(r.balance)}
                      </td>
                      <td>{balanceBadge(r.balance, r.status)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
        </div>
      </div>
    </div>
  );
}

/* ── Main page ──────────────────────────────────────────────────────────── */
export default function Contributions() {
  const { user } = useAuth();
  const now = new Date();
  const [month, setMonth] = useState(now.getMonth() + 1);
  const [year, setYear] = useState(now.getFullYear());
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [payDialog, setPayDialog] = useState(null);
  const [ledgerFor, setLedgerFor] = useState(null);
  const [search, setSearch] = useState("");

  const canWrite = ["super_admin", "treasurer"].includes(user?.role);

  const load = () => {
    setLoading(true);
    api.get(`/contributions/status/${year}/${month}`)
      .then(r => setRows(r.data))
      .finally(() => setLoading(false));
  };
  useEffect(load, [month, year]);

  const upToDate = rows.filter(s => s.balance >= 0).length;
  const pending = rows.filter(s => s.balance < 0).length;
  const collected = rows.reduce((sum, s) => sum + (s.paid || 0), 0);
  const outstanding = rows.reduce((sum, s) => sum + (s.balance < 0 ? -s.balance : 0), 0);

  const filtered = rows.filter(s =>
    s.member_name?.toLowerCase().includes(search.toLowerCase()) ||
    s.member_code?.toLowerCase().includes(search.toLowerCase()));

  const years = Array.from({ length: 5 }, (_, i) => now.getFullYear() - i);

  return (
    <div className="p-6 space-y-5">
      <div>
        <h1 className="text-2xl font-bold text-foreground font-heading">Contributions</h1>
        <p className="text-muted-foreground text-sm">Monthly contribution ledger — pending, advance & balance per member</p>
      </div>

      <div className="flex flex-wrap gap-3 items-center">
        <select value={month} onChange={e => setMonth(+e.target.value)}
          className="border border-input rounded-md px-3 py-2 text-sm bg-card focus:outline-none focus:ring-2 focus:ring-ring/30">
          {MONTHS.slice(1).map((m, i) => <option key={i + 1} value={i + 1}>{m}</option>)}
        </select>
        <select value={year} onChange={e => setYear(+e.target.value)}
          className="border border-input rounded-md px-3 py-2 text-sm bg-card focus:outline-none focus:ring-2 focus:ring-ring/30">
          {years.map(y => <option key={y} value={y}>{y}</option>)}
        </select>
        <input placeholder="Search member..." value={search} onChange={e => setSearch(e.target.value)}
          className="border border-input rounded-md px-3 py-2 text-sm bg-card focus:outline-none focus:ring-2 focus:ring-ring/30 w-48" />
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="stat-card">
          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-1">Up to Date</p>
          <p className="text-2xl font-bold text-primary font-heading">{upToDate}</p>
          <p className="text-xs text-muted-foreground">{Math.round(upToDate / (rows.length || 1) * 100)}% of members</p>
        </div>
        <div className="stat-card">
          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-1">Pending</p>
          <p className="text-2xl font-bold text-amber-600 dark:text-amber-400 font-heading">{pending}</p>
          <p className="text-xs text-muted-foreground">In arrears</p>
        </div>
        <div className="stat-card">
          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-1">Collected</p>
          <p className="text-2xl font-bold text-foreground font-heading">{inr(collected)}</p>
          <p className="text-xs text-muted-foreground">This month</p>
        </div>
        <div className="stat-card">
          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-1">Outstanding</p>
          <p className="text-2xl font-bold text-amber-600 dark:text-amber-400 font-heading">{inr(outstanding)}</p>
          <p className="text-xs text-muted-foreground">Total owed this month</p>
        </div>
      </div>

      <div className="bg-card border border-border rounded-lg overflow-hidden">
        {loading ? <div className="p-8 text-center text-muted-foreground/70">Loading...</div>
          : filtered.length === 0 ? <div className="p-8 text-center text-muted-foreground/70">No members found</div>
          : (
            <div className="overflow-x-auto">
              <table className="w-full data-table">
                <thead><tr>
                  <th>ID</th><th>Member</th>
                  <th className="text-right">Prior Pending</th><th className="text-right">Advance</th>
                  <th className="text-right">Rate</th><th className="text-right">Paid</th>
                  <th className="text-right">Balance</th><th>Status</th><th className="text-right">Action</th>
                </tr></thead>
                <tbody>
                  {filtered.map(s => (
                    <tr key={s.member_id}>
                      <td><span className="font-mono text-xs bg-muted px-2 py-0.5 rounded">{s.member_code}</span></td>
                      <td>
                        <button onClick={() => setLedgerFor(s.member_id)}
                          className="font-medium text-foreground hover:text-primary hover:underline text-left">
                          {s.member_name}
                        </button>
                      </td>
                      <td className="text-right text-amber-600">{s.prior_pending ? inr(s.prior_pending) : "-"}</td>
                      <td className="text-right text-sky-600">{s.prior_advance ? inr(s.prior_advance) : "-"}</td>
                      <td className="text-right">{inr(s.rate)}</td>
                      <td className="text-right text-emerald-600">{s.paid ? inr(s.paid) : "-"}</td>
                      <td className={`text-right font-semibold ${s.balance < 0 ? "text-amber-600" : s.balance > 0 ? "text-sky-600" : "text-emerald-600"}`}>
                        {s.balance < 0 ? `-${inr(s.balance)}` : inr(s.balance)}
                      </td>
                      <td>{balanceBadge(s.balance, s.status)}</td>
                      <td className="text-right">
                        {canWrite ? (
                          <button onClick={() => setPayDialog(s)}
                            className="inline-flex items-center gap-1.5 ml-auto px-3 py-1.5 bg-primary text-primary-foreground rounded text-xs font-medium hover:bg-primary/90 transition-colors">
                            <Plus size={12} weight="bold" /> Pay
                          </button>
                        ) : (
                          <button onClick={() => setLedgerFor(s.member_id)}
                            className="inline-flex items-center gap-1 ml-auto px-2 py-1 text-xs text-muted-foreground border border-input rounded hover:bg-muted/60">
                            <Wallet size={12} /> Ledger
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
      </div>

      {payDialog && (
        <RecordPaymentDialog row={payDialog} month={month} year={year}
          onSave={load} onClose={() => setPayDialog(null)} />
      )}
      {ledgerFor && <LedgerDialog memberId={ledgerFor} onClose={() => setLedgerFor(null)} />}
    </div>
  );
}
