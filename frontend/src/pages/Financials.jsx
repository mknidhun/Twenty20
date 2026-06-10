import { useEffect, useState } from "react";
import api, { formatError } from "@/utils/api";
import { CASHBOOK } from "@/constants/testIds";
import { Plus, X, ArrowUp, ArrowDown } from "@phosphor-icons/react";
import { useAuth } from "@/contexts/AuthContext";

const CATEGORIES = [
  "contribution", "donation", "marriage_benefit", "housewarming_benefit",
  "medical_aid", "death_assistance", "admin_expense", "other_income", "other_expense"
];

function AddEntryDialog({ onSave, onClose }) {
  const [form, setForm] = useState({
    entry_type: "credit", category: "donation",
    description: "", amount: "", date: new Date().toISOString().split("T")[0]
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      await api.post("/cashbook", { ...form, amount: parseFloat(form.amount) });
      onSave();
    } catch (err) {
      setError(formatError(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-stone-900/40 p-4">
      <div className="bg-white rounded-lg shadow-lg w-full max-w-sm">
        <div className="flex items-center justify-between px-5 py-4 border-b border-stone-200">
          <h3 className="font-semibold text-stone-900 font-heading">Add Cashbook Entry</h3>
          <button onClick={onClose} className="text-stone-400 hover:text-stone-600"><X size={18} /></button>
        </div>
        <form onSubmit={handleSubmit} className="p-5 space-y-4">
          <div className="grid grid-cols-2 gap-1 p-1 bg-stone-100 rounded-md">
            <button type="button" onClick={() => setForm(p => ({...p, entry_type: "credit"}))}
              className={`py-2 rounded text-sm font-medium transition-colors ${form.entry_type === "credit" ? "bg-white text-green-800 shadow-sm" : "text-stone-500 hover:text-stone-700"}`}>
              Credit (Income)
            </button>
            <button type="button" onClick={() => setForm(p => ({...p, entry_type: "debit"}))}
              className={`py-2 rounded text-sm font-medium transition-colors ${form.entry_type === "debit" ? "bg-white text-red-700 shadow-sm" : "text-stone-500 hover:text-stone-700"}`}>
              Debit (Expense)
            </button>
          </div>
          <div>
            <label className="block text-sm font-medium text-stone-700 mb-1">Category *</label>
            <select required value={form.category} onChange={e => setForm(p => ({...p, category: e.target.value}))}
              className="w-full border border-stone-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-700/30 focus:border-green-700">
              {CATEGORIES.map(c => <option key={c} value={c}>{c.replace(/_/g, " ").replace(/\b\w/g, l => l.toUpperCase())}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-stone-700 mb-1">Description *</label>
            <input required value={form.description} onChange={e => setForm(p => ({...p, description: e.target.value}))}
              className="w-full border border-stone-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-700/30 focus:border-green-700" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium text-stone-700 mb-1">Amount (₹) *</label>
              <input type="number" required value={form.amount} onChange={e => setForm(p => ({...p, amount: e.target.value}))}
                className="w-full border border-stone-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-700/30 focus:border-green-700" />
            </div>
            <div>
              <label className="block text-sm font-medium text-stone-700 mb-1">Date *</label>
              <input type="date" required value={form.date} onChange={e => setForm(p => ({...p, date: e.target.value}))}
                className="w-full border border-stone-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-700/30 focus:border-green-700" />
            </div>
          </div>
          {error && <p className="text-red-600 text-sm bg-red-50 border border-red-200 rounded px-3 py-2">{error}</p>}
          <div className="flex gap-3">
            <button type="button" onClick={onClose} className="flex-1 px-4 py-2 border border-stone-300 text-stone-700 rounded-md text-sm hover:bg-stone-50">Cancel</button>
            <button type="submit" disabled={loading} data-testid={CASHBOOK.addButton}
              className="flex-1 px-4 py-2 bg-green-800 text-white rounded-md text-sm font-medium hover:bg-green-900 disabled:opacity-60">
              {loading ? "Adding..." : "Add Entry"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default function Financials() {
  const { user } = useAuth();
  const [entries, setEntries] = useState([]);
  const [loading, setLoading] = useState(true);
  const [dialog, setDialog] = useState(false);
  const [filterType, setFilterType] = useState("all");

  const canWrite = ["super_admin","treasurer"].includes(user?.role);
  const canDelete = ["super_admin","treasurer"].includes(user?.role);

  const load = () => { setLoading(true); api.get("/cashbook").then(r => setEntries(r.data)).finally(() => setLoading(false)); };
  useEffect(load, []);

  const handleDelete = async (id) => {
    if (!window.confirm("Delete this entry?")) return;
    await api.delete(`/cashbook/${id}`);
    load();
  };

  const filtered = entries.filter(e => filterType === "all" || e.entry_type === filterType);
  const totalCredit = entries.filter(e => e.entry_type === "credit").reduce((s, e) => s + e.amount, 0);
  const totalDebit = entries.filter(e => e.entry_type === "debit").reduce((s, e) => s + e.amount, 0);
  const balance = entries.length > 0 ? entries[0].running_balance : 0; // entries are reversed (newest first)

  return (
    <div className="p-6 space-y-5">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold text-stone-900 font-heading">Cashbook</h1>
          <p className="text-stone-500 text-sm">Financial ledger & transactions</p>
        </div>
        {canWrite && (
          <button onClick={() => setDialog(true)} data-testid={CASHBOOK.addButton}
            className="flex items-center gap-2 bg-green-800 text-white px-4 py-2 rounded-md text-sm font-medium hover:bg-green-900 transition-colors">
            <Plus size={16} weight="bold" /> Add Entry
          </button>
        )}
      </div>

      {/* Summary */}
      <div className="grid grid-cols-3 gap-4">
        <div className="stat-card">
          <p className="text-xs font-semibold uppercase tracking-wide text-stone-500 mb-1">Total Income</p>
          <p className="text-xl font-bold text-green-800 font-heading flex items-center gap-1">
            <ArrowDown size={16} className="text-green-700" /> ₹{totalCredit.toLocaleString("en-IN")}
          </p>
        </div>
        <div className="stat-card">
          <p className="text-xs font-semibold uppercase tracking-wide text-stone-500 mb-1">Total Expense</p>
          <p className="text-xl font-bold text-red-700 font-heading flex items-center gap-1">
            <ArrowUp size={16} className="text-red-600" /> ₹{totalDebit.toLocaleString("en-IN")}
          </p>
        </div>
        <div className="stat-card" data-testid={CASHBOOK.balance}>
          <p className="text-xs font-semibold uppercase tracking-wide text-stone-500 mb-1">Current Balance</p>
          <p className={`text-xl font-bold font-heading ${balance >= 0 ? "text-green-800" : "text-red-700"}`}>
            ₹{Math.abs(balance).toLocaleString("en-IN")}
          </p>
          <p className="text-xs text-stone-400">{balance < 0 ? "Deficit" : "Surplus"}</p>
        </div>
      </div>

      {/* Filter */}
      <div className="flex gap-3">
        <select value={filterType} onChange={e => setFilterType(e.target.value)}
          className="border border-stone-300 rounded-md px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-green-700/30">
          <option value="all">All Entries</option>
          <option value="credit">Credits (Income)</option>
          <option value="debit">Debits (Expense)</option>
        </select>
      </div>

      <div className="bg-white border border-stone-200 rounded-lg overflow-hidden" data-testid={CASHBOOK.table}>
        {loading ? <div className="p-8 text-center text-stone-400">Loading...</div> :
          filtered.length === 0 ? <div className="p-8 text-center text-stone-400">No cashbook entries</div> : (
            <div className="overflow-x-auto">
              <table className="w-full data-table">
                <thead>
                  <tr>
                    <th>Voucher #</th>
                    <th>Date</th>
                    <th>Description</th>
                    <th>Category</th>
                    <th className="text-right">Credit</th>
                    <th className="text-right">Debit</th>
                    <th className="text-right">Balance</th>
                    {canDelete && <th></th>}
                  </tr>
                </thead>
                <tbody>
                  {filtered.map(e => (
                    <tr key={e.id}>
                      <td><span className="font-mono text-xs bg-stone-100 px-2 py-0.5 rounded">{e.voucher_number}</span></td>
                      <td>{e.date ? new Date(e.date).toLocaleDateString("en-IN") : "-"}</td>
                      <td className="max-w-xs">{e.description}</td>
                      <td className="capitalize text-stone-500 text-xs">{e.category?.replace(/_/g, " ")}</td>
                      <td className="text-right">
                        {e.entry_type === "credit" ? (
                          <span className="text-green-700 font-medium">₹{e.amount?.toLocaleString("en-IN")}</span>
                        ) : "-"}
                      </td>
                      <td className="text-right">
                        {e.entry_type === "debit" ? (
                          <span className="text-red-600 font-medium">₹{e.amount?.toLocaleString("en-IN")}</span>
                        ) : "-"}
                      </td>
                      <td className="text-right">
                        <span className={`font-semibold ${e.running_balance >= 0 ? "text-stone-700" : "text-red-600"}`}>
                          ₹{e.running_balance?.toLocaleString("en-IN")}
                        </span>
                      </td>
                      {canDelete && (
                        <td>
                          <button onClick={() => handleDelete(e.id)}
                            className="p-1 text-stone-300 hover:text-red-500 hover:bg-red-50 rounded transition-colors">
                            <X size={14} />
                          </button>
                        </td>
                      )}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
      </div>

      {dialog && <AddEntryDialog onSave={() => { setDialog(false); load(); }} onClose={() => setDialog(false)} />}
    </div>
  );
}
