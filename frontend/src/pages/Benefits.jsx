import { useEffect, useState } from "react";
import api, { formatError } from "@/utils/api";
import { useAuth } from "@/contexts/AuthContext";
import { BENEFITS } from "@/constants/testIds";
import { Plus, X, ArrowRight, CheckCircle, XCircle } from "@phosphor-icons/react";

const STATUS_MAP = {
  pending: "badge-pending",
  secretary_verified: "badge-under_review",
  committee_approved: "badge-under_review",
  paid: "badge-paid",
  rejected: "badge-rejected"
};

const STATUS_LABELS = {
  pending: "Pending", secretary_verified: "Secretary Verified",
  committee_approved: "Committee Approved", paid: "Paid", rejected: "Rejected"
};

const BENEFIT_AMOUNTS = { marriage: 5000, housewarming: 3000 };

function ApplyDialog({ members, onSave, onClose }) {
  const [form, setForm] = useState({ member_id: "", benefit_type: "marriage", event_date: "", notes: "" });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      await api.post("/benefits", form);
      onSave();
    } catch (err) {
      setError(formatError(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-stone-900/40 p-4">
      <div className="bg-white rounded-lg shadow-lg w-full max-w-md">
        <div className="flex items-center justify-between px-5 py-4 border-b border-stone-200">
          <h3 className="font-semibold text-stone-900 font-heading">Apply for Benefit</h3>
          <button onClick={onClose} className="text-stone-400 hover:text-stone-600"><X size={18} /></button>
        </div>
        <form onSubmit={handleSubmit} className="p-5 space-y-4">
          <div>
            <label className="block text-sm font-medium text-stone-700 mb-1">Member *</label>
            <select required value={form.member_id} onChange={e => setForm(p => ({...p, member_id: e.target.value}))}
              className="w-full border border-stone-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-700/30 focus:border-green-700">
              <option value="">Select member...</option>
              {members.filter(m => m.status === "active").map(m => (
                <option key={m.id} value={m.id}>{m.member_id} — {m.name}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-stone-700 mb-1">Benefit Type *</label>
            <select required value={form.benefit_type} onChange={e => setForm(p => ({...p, benefit_type: e.target.value}))}
              className="w-full border border-stone-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-700/30 focus:border-green-700">
              <option value="marriage">Marriage Benefit (₹5,000)</option>
              <option value="housewarming">Housewarming Benefit (₹3,000)</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-stone-700 mb-1">Event Date *</label>
            <input type="date" required value={form.event_date} onChange={e => setForm(p => ({...p, event_date: e.target.value}))}
              className="w-full border border-stone-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-700/30 focus:border-green-700" />
          </div>
          <div>
            <label className="block text-sm font-medium text-stone-700 mb-1">Notes</label>
            <textarea value={form.notes} onChange={e => setForm(p => ({...p, notes: e.target.value}))} rows={2}
              className="w-full border border-stone-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-700/30 focus:border-green-700" />
          </div>
          <div className="bg-amber-50 border border-amber-200 rounded-md p-3">
            <p className="text-xs text-amber-800">
              Amount: <strong>₹{BENEFIT_AMOUNTS[form.benefit_type]?.toLocaleString("en-IN")}</strong> — Subject to committee approval
            </p>
          </div>
          {error && <p className="text-red-600 text-sm bg-red-50 border border-red-200 rounded px-3 py-2">{error}</p>}
          <div className="flex gap-3">
            <button type="button" onClick={onClose} className="flex-1 px-4 py-2 border border-stone-300 text-stone-700 rounded-md text-sm hover:bg-stone-50">Cancel</button>
            <button type="submit" disabled={loading}
              className="flex-1 px-4 py-2 bg-green-800 text-white rounded-md text-sm font-medium hover:bg-green-900 disabled:opacity-60">
              {loading ? "Applying..." : "Apply"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

function WorkflowActions({ benefit, onUpdate, userRole }) {
  const [loading, setLoading] = useState(false);
  const update = async (status, notes = "") => {
    setLoading(true);
    try {
      await api.put(`/benefits/${benefit.id}/status`, { status, notes });
      onUpdate();
    } catch (err) {
      alert(formatError(err));
    } finally {
      setLoading(false);
    }
  };

  const { status } = benefit;
  if (status === "paid" || status === "rejected") return null;

  return (
    <div className="flex gap-2 flex-wrap">
      {status === "pending" && ["super_admin","secretary"].includes(userRole) && (
        <button onClick={() => update("secretary_verified")} disabled={loading}
          className="px-2.5 py-1 text-xs bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-60">
          Verify
        </button>
      )}
      {status === "secretary_verified" && ["super_admin","president","committee_member"].includes(userRole) && (
        <button onClick={() => update("committee_approved")} disabled={loading}
          className="px-2.5 py-1 text-xs bg-green-700 text-white rounded hover:bg-green-800 disabled:opacity-60">
          Approve
        </button>
      )}
      {status === "committee_approved" && ["super_admin","treasurer"].includes(userRole) && (
        <button onClick={() => update("paid")} disabled={loading} data-testid={BENEFITS.approveButton}
          className="px-2.5 py-1 text-xs bg-green-800 text-white rounded hover:bg-green-900 disabled:opacity-60">
          Mark Paid
        </button>
      )}
      <button onClick={() => update("rejected")} disabled={loading} data-testid={BENEFITS.rejectButton}
        className="px-2.5 py-1 text-xs bg-red-100 text-red-700 rounded hover:bg-red-200 disabled:opacity-60">
        Reject
      </button>
    </div>
  );
}

export default function Benefits() {
  const { user } = useAuth();
  const [benefits, setBenefits] = useState([]);
  const [members, setMembers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [dialog, setDialog] = useState(false);
  const [filterType, setFilterType] = useState("all");
  const [filterStatus, setFilterStatus] = useState("all");

  const load = () => {
    setLoading(true);
    Promise.all([api.get("/benefits"), api.get("/members")])
      .then(([b, m]) => { setBenefits(b.data); setMembers(m.data); })
      .finally(() => setLoading(false));
  };
  useEffect(load, []);

  const filtered = benefits.filter(b =>
    (filterType === "all" || b.benefit_type === filterType) &&
    (filterStatus === "all" || b.status === filterStatus)
  );

  return (
    <div className="p-6 space-y-5">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold text-stone-900 font-heading">Benefits</h1>
          <p className="text-stone-500 text-sm">Marriage & Housewarming benefits</p>
        </div>
        <button onClick={() => setDialog(true)} data-testid={BENEFITS.addButton}
          className="flex items-center gap-2 bg-green-800 text-white px-4 py-2 rounded-md text-sm font-medium hover:bg-green-900 transition-colors">
          <Plus size={16} weight="bold" /> Apply Benefit
        </button>
      </div>

      {/* Summary */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {["pending","secretary_verified","committee_approved","paid"].map(st => (
          <div key={st} className="stat-card">
            <p className="text-xs font-semibold uppercase tracking-wide text-stone-500 mb-1">{STATUS_LABELS[st]}</p>
            <p className="text-2xl font-bold text-stone-900 font-heading">
              {benefits.filter(b => b.status === st).length}
            </p>
          </div>
        ))}
      </div>

      {/* Filters */}
      <div className="flex gap-3">
        <select value={filterType} onChange={e => setFilterType(e.target.value)}
          className="border border-stone-300 rounded-md px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-green-700/30">
          <option value="all">All Types</option>
          <option value="marriage">Marriage</option>
          <option value="housewarming">Housewarming</option>
        </select>
        <select value={filterStatus} onChange={e => setFilterStatus(e.target.value)}
          className="border border-stone-300 rounded-md px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-green-700/30">
          <option value="all">All Status</option>
          {Object.entries(STATUS_LABELS).map(([k,v]) => <option key={k} value={k}>{v}</option>)}
        </select>
      </div>

      {/* Table */}
      <div className="bg-white border border-stone-200 rounded-lg overflow-hidden" data-testid={BENEFITS.table}>
        {loading ? <div className="p-8 text-center text-stone-400">Loading...</div> :
          filtered.length === 0 ? <div className="p-8 text-center text-stone-400">No benefit applications found</div> : (
            <div className="overflow-x-auto">
              <table className="w-full data-table">
                <thead>
                  <tr>
                    <th>Member</th>
                    <th>Type</th>
                    <th>Amount</th>
                    <th>Event Date</th>
                    <th>Status</th>
                    <th>Applied On</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map(b => (
                    <tr key={b.id}>
                      <td className="font-medium text-stone-900">{b.member_name}</td>
                      <td className="capitalize">{b.benefit_type}</td>
                      <td>₹{b.amount?.toLocaleString("en-IN")}</td>
                      <td>{b.event_date ? new Date(b.event_date).toLocaleDateString("en-IN") : "-"}</td>
                      <td>
                        <span data-testid={BENEFITS.statusBadge}
                          className={`inline-flex px-2 py-0.5 text-xs font-medium rounded border ${STATUS_MAP[b.status]}`}>
                          {STATUS_LABELS[b.status]}
                        </span>
                      </td>
                      <td>{b.created_at ? new Date(b.created_at).toLocaleDateString("en-IN") : "-"}</td>
                      <td>
                        <WorkflowActions benefit={b} onUpdate={load} userRole={user?.role} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
      </div>

      {dialog && (
        <ApplyDialog members={members} onSave={() => { setDialog(false); load(); }} onClose={() => setDialog(false)} />
      )}
    </div>
  );
}
