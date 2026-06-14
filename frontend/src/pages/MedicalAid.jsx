import { useEffect, useState } from "react";
import api, { formatError } from "@/utils/api";
import { MEDICAL } from "@/constants/testIds";
import { Plus, X } from "@phosphor-icons/react";
import { useAuth } from "@/contexts/AuthContext";

const STATUS_MAP = {
  pending: "badge-pending", under_review: "badge-under_review",
  approved: "badge-approved", rejected: "badge-rejected", paid: "badge-paid"
};
const STATUS_LABELS = {
  pending: "Pending", under_review: "Under Review",
  approved: "Approved", rejected: "Rejected", paid: "Paid"
};

function ApplyDialog({ onSave, onClose }) {
  const [form, setForm] = useState({
    applicant_name: "", contact: "", address: "",
    medical_condition: "", hospital: "", estimated_expense: "", notes: ""
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      await api.post("/medical-aid", { ...form, estimated_expense: parseFloat(form.estimated_expense) });
      onSave();
    } catch (err) {
      setError(formatError(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
      <div className="bg-card rounded-lg shadow-lg w-full max-w-lg max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between px-5 py-4 border-b border-border sticky top-0 bg-card">
          <h3 className="font-semibold text-foreground font-heading">Apply for Medical Aid</h3>
          <button onClick={onClose} className="text-muted-foreground/70 hover:text-foreground" aria-label="Close medical aid form" title="Close"><X size={18} /></button>
        </div>
        <form onSubmit={handleSubmit} className="p-5 space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="col-span-2">
              <label className="block text-sm font-medium text-foreground mb-1">Applicant Name *</label>
              <input required value={form.applicant_name} onChange={e => setForm(p => ({...p, applicant_name: e.target.value}))}
                className="w-full border border-input rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring/30 focus:border-primary" />
            </div>
            <div>
              <label className="block text-sm font-medium text-foreground mb-1">Contact *</label>
              <input required value={form.contact} onChange={e => setForm(p => ({...p, contact: e.target.value}))}
                className="w-full border border-input rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring/30 focus:border-primary" />
            </div>
            <div>
              <label className="block text-sm font-medium text-foreground mb-1">Estimated Expense (₹) *</label>
              <input type="number" required value={form.estimated_expense} onChange={e => setForm(p => ({...p, estimated_expense: e.target.value}))}
                className="w-full border border-input rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring/30 focus:border-primary" />
            </div>
            <div className="col-span-2">
              <label className="block text-sm font-medium text-foreground mb-1">Address *</label>
              <textarea required value={form.address} onChange={e => setForm(p => ({...p, address: e.target.value}))} rows={2}
                className="w-full border border-input rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring/30 focus:border-primary" />
            </div>
            <div>
              <label className="block text-sm font-medium text-foreground mb-1">Medical Condition *</label>
              <input required value={form.medical_condition} onChange={e => setForm(p => ({...p, medical_condition: e.target.value}))}
                className="w-full border border-input rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring/30 focus:border-primary" />
            </div>
            <div>
              <label className="block text-sm font-medium text-foreground mb-1">Hospital *</label>
              <input required value={form.hospital} onChange={e => setForm(p => ({...p, hospital: e.target.value}))}
                className="w-full border border-input rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring/30 focus:border-primary" />
            </div>
            <div className="col-span-2">
              <label className="block text-sm font-medium text-foreground mb-1">Additional Notes</label>
              <textarea value={form.notes} onChange={e => setForm(p => ({...p, notes: e.target.value}))} rows={2}
                className="w-full border border-input rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring/30 focus:border-primary" />
            </div>
          </div>
          {error && <p className="text-destructive text-sm bg-destructive/10 border border-destructive/30 rounded px-3 py-2">{error}</p>}
          <div className="flex gap-3">
            <button type="button" onClick={onClose} className="flex-1 px-4 py-2 border border-input text-foreground rounded-md text-sm hover:bg-muted/60">Cancel</button>
            <button type="submit" disabled={loading}
              className="flex-1 px-4 py-2 bg-primary text-primary-foreground rounded-md text-sm font-medium hover:bg-primary/90 disabled:opacity-60">
              {loading ? "Submitting..." : "Submit Application"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

function UpdateDialog({ aid, onSave, onClose, userRole }) {
  const [form, setForm] = useState({ status: aid.status, recommended_amount: aid.recommended_amount || "", notes: aid.notes || "" });
  const [loading, setLoading] = useState(false);

  const statusOptions = {
    super_admin: ["pending","under_review","approved","rejected","paid"],
    president: ["under_review","approved","rejected"],
    secretary: ["under_review"],
    treasurer: ["paid"],
    committee_member: ["under_review","approved","rejected"],
  };
  const opts = statusOptions[userRole] || [];

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      await api.put(`/medical-aid/${aid.id}`, {
        status: form.status,
        recommended_amount: form.recommended_amount ? parseFloat(form.recommended_amount) : undefined,
        notes: form.notes || undefined
      });
      onSave();
    } catch (err) {
      alert(formatError(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
      <div className="bg-card rounded-lg shadow-lg w-full max-w-sm">
        <div className="flex items-center justify-between px-5 py-4 border-b border-border">
          <h3 className="font-semibold text-foreground font-heading">Update Application</h3>
          <button onClick={onClose} className="text-muted-foreground/70 hover:text-foreground" aria-label="Close medical aid dialog" title="Close"><X size={18} /></button>
        </div>
        <form onSubmit={handleSubmit} className="p-5 space-y-4">
          <div>
            <label className="block text-sm font-medium text-foreground mb-1">Status</label>
            <select value={form.status} onChange={e => setForm(p => ({...p, status: e.target.value}))}
              className="w-full border border-input rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring/30">
              {opts.map(o => <option key={o} value={o}>{STATUS_LABELS[o]}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-foreground mb-1">Recommended Amount (₹)</label>
            <input type="number" value={form.recommended_amount} onChange={e => setForm(p => ({...p, recommended_amount: e.target.value}))}
              className="w-full border border-input rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring/30" />
          </div>
          <div>
            <label className="block text-sm font-medium text-foreground mb-1">Notes</label>
            <textarea value={form.notes} onChange={e => setForm(p => ({...p, notes: e.target.value}))} rows={2}
              className="w-full border border-input rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring/30" />
          </div>
          <div className="flex gap-3">
            <button type="button" onClick={onClose} className="flex-1 px-4 py-2 border border-input text-foreground rounded-md text-sm hover:bg-muted/60">Cancel</button>
            <button type="submit" disabled={loading}
              className="flex-1 px-4 py-2 bg-primary text-primary-foreground rounded-md text-sm font-medium hover:bg-primary/90 disabled:opacity-60">
              {loading ? "Updating..." : "Update"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default function MedicalAid() {
  const { user } = useAuth();
  const [aids, setAids] = useState([]);
  const [loading, setLoading] = useState(true);
  const [dialog, setDialog] = useState(null); // null | "add" | aid object

  const load = () => { setLoading(true); api.get("/medical-aid").then(r => setAids(r.data)).finally(() => setLoading(false)); };
  useEffect(load, []);

  return (
    <div className="p-6 space-y-5">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold text-foreground font-heading">Medical Aid</h1>
          <p className="text-muted-foreground text-sm">Track medical assistance requests</p>
        </div>
        <button onClick={() => setDialog("add")} data-testid={MEDICAL.addButton}
          className="flex items-center gap-2 bg-primary text-primary-foreground px-4 py-2 rounded-md text-sm font-medium hover:bg-primary/90 transition-colors">
          <Plus size={16} weight="bold" /> Apply for Medical Aid
        </button>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {["pending","under_review","approved","paid"].map(st => (
          <div key={st} className="stat-card">
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-1">{STATUS_LABELS[st]}</p>
            <p className="text-2xl font-bold text-foreground font-heading">{aids.filter(a => a.status === st).length}</p>
          </div>
        ))}
      </div>

      <div className="bg-card border border-border rounded-lg overflow-hidden" data-testid={MEDICAL.table}>
        {loading ? <div className="p-8 text-center text-muted-foreground/70">Loading...</div> :
          aids.length === 0 ? <div className="p-8 text-center text-muted-foreground/70">No medical aid applications</div> : (
            <div className="overflow-x-auto">
              <table className="w-full data-table">
                <thead>
                  <tr>
                    <th>Applicant</th>
                    <th>Contact</th>
                    <th>Condition</th>
                    <th>Hospital</th>
                    <th>Estimated</th>
                    <th>Recommended</th>
                    <th>Status</th>
                    <th>Date</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {aids.map(a => (
                    <tr key={a.id}>
                      <td className="font-medium text-foreground">{a.applicant_name}</td>
                      <td>{a.contact}</td>
                      <td className="max-w-xs truncate">{a.medical_condition}</td>
                      <td>{a.hospital}</td>
                      <td>₹{a.estimated_expense?.toLocaleString("en-IN")}</td>
                      <td>{a.recommended_amount ? `₹${a.recommended_amount?.toLocaleString("en-IN")}` : "-"}</td>
                      <td>
                        <span data-testid={MEDICAL.statusBadge}
                          className={`inline-flex px-2 py-0.5 text-xs font-medium rounded border ${STATUS_MAP[a.status]}`}>
                          {STATUS_LABELS[a.status]}
                        </span>
                      </td>
                      <td>{a.created_at ? new Date(a.created_at).toLocaleDateString("en-IN") : "-"}</td>
                      <td>
                        {["super_admin","president","secretary","treasurer","committee_member"].includes(user?.role) && a.status !== "paid" && (
                          <button onClick={() => setDialog(a)}
                            className="px-2.5 py-1 text-xs bg-muted text-foreground rounded hover:bg-muted">
                            Update
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

      {dialog === "add" && <ApplyDialog onSave={() => { setDialog(null); load(); }} onClose={() => setDialog(null)} />}
      {dialog && dialog !== "add" && (
        <UpdateDialog aid={dialog} userRole={user?.role} onSave={() => { setDialog(null); load(); }} onClose={() => setDialog(null)} />
      )}
    </div>
  );
}
