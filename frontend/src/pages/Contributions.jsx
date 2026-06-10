import { useEffect, useState } from "react";
import api, { formatError } from "@/utils/api";
import { useAuth } from "@/contexts/AuthContext";
import { CONTRIBUTIONS } from "@/constants/testIds";
import { CheckCircle, Clock, Plus, X, Receipt } from "@phosphor-icons/react";

const MONTHS = ["","January","February","March","April","May","June","July","August","September","October","November","December"];

function RecordPaymentDialog({ member, month, year, onSave, onClose }) {
  const [form, setForm] = useState({ amount: 100, payment_method: "cash" });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      await api.post("/contributions", {
        member_id: member.member_id,
        month, year, amount: parseFloat(form.amount),
        payment_method: form.payment_method
      });
      onSave();
    } catch (err) {
      setError(formatError(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-stone-900/40 p-4">
      <div className="bg-white rounded-lg shadow-lg w-full max-w-sm" data-testid={CONTRIBUTIONS.addForm}>
        <div className="flex items-center justify-between px-5 py-4 border-b border-stone-200">
          <div>
            <h3 className="font-semibold text-stone-900 font-heading">Record Payment</h3>
            <p className="text-xs text-stone-500">{member.member_name} — {MONTHS[month]} {year}</p>
          </div>
          <button onClick={onClose} className="text-stone-400 hover:text-stone-600"><X size={18} /></button>
        </div>
        <form onSubmit={handleSubmit} className="p-5 space-y-4">
          <div>
            <label className="block text-sm font-medium text-stone-700 mb-1">Amount (₹) *</label>
            <input type="number" required value={form.amount} onChange={e => setForm(p => ({...p, amount: e.target.value}))}
              className="w-full border border-stone-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-700/30 focus:border-green-700" />
          </div>
          <div>
            <label className="block text-sm font-medium text-stone-700 mb-1">Payment Method *</label>
            <select value={form.payment_method} onChange={e => setForm(p => ({...p, payment_method: e.target.value}))}
              className="w-full border border-stone-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-700/30 focus:border-green-700">
              <option value="cash">Cash</option>
              <option value="upi">UPI</option>
              <option value="bank_transfer">Bank Transfer</option>
            </select>
          </div>
          {error && <p className="text-red-600 text-sm bg-red-50 border border-red-200 rounded px-3 py-2">{error}</p>}
          <div className="flex gap-3">
            <button type="button" onClick={onClose} className="flex-1 px-4 py-2 border border-stone-300 text-stone-700 rounded-md text-sm hover:bg-stone-50">Cancel</button>
            <button type="submit" disabled={loading} data-testid={CONTRIBUTIONS.markPaidButton}
              className="flex-1 px-4 py-2 bg-green-800 text-white rounded-md text-sm font-medium hover:bg-green-900 disabled:opacity-60">
              {loading ? "Recording..." : "Record Payment"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default function Contributions() {
  const { user } = useAuth();
  const now = new Date();
  const [month, setMonth] = useState(now.getMonth() + 1);
  const [year, setYear] = useState(now.getFullYear());
  const [status, setStatus] = useState([]);
  const [loading, setLoading] = useState(true);
  const [dialog, setDialog] = useState(null);
  const [search, setSearch] = useState("");

  const canWrite = ["super_admin", "treasurer"].includes(user?.role);

  const load = () => {
    setLoading(true);
    api.get(`/contributions/status/${year}/${month}`)
      .then(r => setStatus(r.data))
      .finally(() => setLoading(false));
  };
  useEffect(load, [month, year]);

  const paid = status.filter(s => s.status === "paid").length;
  const pending = status.filter(s => s.status === "pending").length;
  const total = status.reduce((sum, s) => sum + (s.amount || 0), 0);

  const filtered = status.filter(s =>
    s.member_name?.toLowerCase().includes(search.toLowerCase()) ||
    s.member_code?.toLowerCase().includes(search.toLowerCase())
  );

  const years = Array.from({length: 5}, (_, i) => now.getFullYear() - i);

  return (
    <div className="p-6 space-y-5">
      <div>
        <h1 className="text-2xl font-bold text-stone-900 font-heading">Contributions</h1>
        <p className="text-stone-500 text-sm">Monthly contribution tracker</p>
      </div>

      {/* Month / Year selector */}
      <div className="flex flex-wrap gap-3 items-center">
        <select value={month} onChange={e => setMonth(+e.target.value)} data-testid={CONTRIBUTIONS.monthSelector}
          className="border border-stone-300 rounded-md px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-green-700/30">
          {MONTHS.slice(1).map((m, i) => <option key={i+1} value={i+1}>{m}</option>)}
        </select>
        <select value={year} onChange={e => setYear(+e.target.value)} data-testid={CONTRIBUTIONS.yearSelector}
          className="border border-stone-300 rounded-md px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-green-700/30">
          {years.map(y => <option key={y} value={y}>{y}</option>)}
        </select>
        <input
          placeholder="Search member..."
          value={search} onChange={e => setSearch(e.target.value)}
          className="border border-stone-300 rounded-md px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-green-700/30 w-48"
        />
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-3 gap-4">
        <div className="stat-card">
          <p className="text-xs font-semibold uppercase tracking-wide text-stone-500 mb-1">Paid</p>
          <p className="text-2xl font-bold text-green-800 font-heading">{paid}</p>
          <p className="text-xs text-stone-500">{Math.round(paid/(status.length||1)*100)}% of members</p>
        </div>
        <div className="stat-card">
          <p className="text-xs font-semibold uppercase tracking-wide text-stone-500 mb-1">Pending</p>
          <p className="text-2xl font-bold text-amber-700 font-heading">{pending}</p>
          <p className="text-xs text-stone-500">Yet to pay</p>
        </div>
        <div className="stat-card">
          <p className="text-xs font-semibold uppercase tracking-wide text-stone-500 mb-1">Collected</p>
          <p className="text-2xl font-bold text-stone-900 font-heading">₹{total.toLocaleString("en-IN")}</p>
          <p className="text-xs text-stone-500">This month</p>
        </div>
      </div>

      {/* Status table */}
      <div className="bg-white border border-stone-200 rounded-lg overflow-hidden" data-testid={CONTRIBUTIONS.statusTable}>
        {loading ? (
          <div className="p-8 text-center text-stone-400">Loading...</div>
        ) : filtered.length === 0 ? (
          <div className="p-8 text-center text-stone-400">No members found</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full data-table">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Member Name</th>
                  <th>Status</th>
                  <th>Amount</th>
                  <th>Payment Method</th>
                  <th>Receipt #</th>
                  {canWrite && <th className="text-right">Action</th>}
                </tr>
              </thead>
              <tbody>
                {filtered.map(s => (
                  <tr key={s.member_id}>
                    <td><span className="font-mono text-xs bg-stone-100 px-2 py-0.5 rounded">{s.member_code}</span></td>
                    <td className="font-medium text-stone-900">{s.member_name}</td>
                    <td>
                      <span className={`inline-flex items-center gap-1 px-2 py-0.5 text-xs font-medium rounded border ${s.status === "paid" ? "badge-paid" : "badge-pending"}`}>
                        {s.status === "paid" ? <CheckCircle size={11} /> : <Clock size={11} />}
                        {s.status}
                      </span>
                    </td>
                    <td>{s.amount ? `₹${s.amount}` : "-"}</td>
                    <td className="capitalize">{s.payment_method || "-"}</td>
                    <td>
                      {s.receipt_number ? (
                        <span className="flex items-center gap-1 text-stone-600">
                          <Receipt size={12} />{s.receipt_number}
                        </span>
                      ) : "-"}
                    </td>
                    {canWrite && (
                      <td className="text-right">
                        {s.status === "pending" ? (
                          <button
                            onClick={() => setDialog(s)}
                            className="flex items-center gap-1.5 ml-auto px-3 py-1.5 bg-green-800 text-white rounded text-xs font-medium hover:bg-green-900 transition-colors"
                          >
                            <Plus size={12} weight="bold" /> Record
                          </button>
                        ) : (
                          <span className="text-xs text-green-700 font-medium">✓ Paid</span>
                        )}
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {dialog && (
        <RecordPaymentDialog
          member={dialog} month={month} year={year}
          onSave={() => { setDialog(null); load(); }}
          onClose={() => setDialog(null)}
        />
      )}
    </div>
  );
}
