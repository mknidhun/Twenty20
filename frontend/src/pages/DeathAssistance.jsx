import { useEffect, useState } from "react";
import api, { formatError } from "@/utils/api";
import { DEATH } from "@/constants/testIds";
import { Plus, X } from "@phosphor-icons/react";
import { useAuth } from "@/contexts/AuthContext";

const STATUS_MAP = {
  pending: "badge-pending", approved: "badge-approved", delivered: "badge-paid"
};

function AddDialog({ members, onSave, onClose }) {
  const [form, setForm] = useState({
    deceased_name: "", member_id: "", family_details: "",
    address: "", contact_person: "", date_of_death: ""
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      await api.post("/death-assistance", form);
      onSave();
    } catch (err) {
      setError(formatError(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-stone-900/40 p-4">
      <div className="bg-white rounded-lg shadow-lg w-full max-w-md max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between px-5 py-4 border-b border-stone-200 sticky top-0 bg-white">
          <h3 className="font-semibold text-stone-900 font-heading">Record Death Assistance</h3>
          <button onClick={onClose} className="text-stone-400 hover:text-stone-600"><X size={18} /></button>
        </div>
        <form onSubmit={handleSubmit} className="p-5 space-y-4">
          <div>
            <label className="block text-sm font-medium text-stone-700 mb-1">Deceased Name *</label>
            <input required value={form.deceased_name} onChange={e => setForm(p => ({...p, deceased_name: e.target.value}))}
              className="w-full border border-stone-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-700/30 focus:border-green-700" />
          </div>
          <div>
            <label className="block text-sm font-medium text-stone-700 mb-1">Linked Member (optional)</label>
            <select value={form.member_id} onChange={e => setForm(p => ({...p, member_id: e.target.value}))}
              className="w-full border border-stone-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-700/30 focus:border-green-700">
              <option value="">— Not a member —</option>
              {members.map(m => <option key={m.id} value={m.id}>{m.member_id} — {m.name}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-stone-700 mb-1">Date of Death *</label>
            <input type="date" required value={form.date_of_death} onChange={e => setForm(p => ({...p, date_of_death: e.target.value}))}
              className="w-full border border-stone-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-700/30 focus:border-green-700" />
          </div>
          <div>
            <label className="block text-sm font-medium text-stone-700 mb-1">Contact Person *</label>
            <input required value={form.contact_person} onChange={e => setForm(p => ({...p, contact_person: e.target.value}))}
              className="w-full border border-stone-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-700/30 focus:border-green-700" />
          </div>
          <div>
            <label className="block text-sm font-medium text-stone-700 mb-1">Address *</label>
            <textarea required value={form.address} onChange={e => setForm(p => ({...p, address: e.target.value}))} rows={2}
              className="w-full border border-stone-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-700/30 focus:border-green-700" />
          </div>
          <div>
            <label className="block text-sm font-medium text-stone-700 mb-1">Family Details *</label>
            <textarea required value={form.family_details} onChange={e => setForm(p => ({...p, family_details: e.target.value}))} rows={2}
              className="w-full border border-stone-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-700/30 focus:border-green-700" />
          </div>
          {error && <p className="text-red-600 text-sm bg-red-50 border border-red-200 rounded px-3 py-2">{error}</p>}
          <div className="flex gap-3">
            <button type="button" onClick={onClose} className="flex-1 px-4 py-2 border border-stone-300 text-stone-700 rounded-md text-sm hover:bg-stone-50">Cancel</button>
            <button type="submit" disabled={loading}
              className="flex-1 px-4 py-2 bg-green-800 text-white rounded-md text-sm font-medium hover:bg-green-900 disabled:opacity-60">
              {loading ? "Saving..." : "Save Record"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

function UpdateDialog({ caseItem, onSave, onClose }) {
  const [form, setForm] = useState({
    status: caseItem.status,
    grocery_kit_value: caseItem.grocery_kit_value || "",
    delivery_date: caseItem.delivery_date || "",
    remarks: caseItem.remarks || ""
  });
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      await api.put(`/death-assistance/${caseItem.id}`, {
        status: form.status,
        grocery_kit_value: form.grocery_kit_value ? parseFloat(form.grocery_kit_value) : undefined,
        delivery_date: form.delivery_date || undefined,
        remarks: form.remarks || undefined
      });
      onSave();
    } catch (err) {
      alert(formatError(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-stone-900/40 p-4">
      <div className="bg-white rounded-lg shadow-lg w-full max-w-sm">
        <div className="flex items-center justify-between px-5 py-4 border-b border-stone-200">
          <h3 className="font-semibold text-stone-900 font-heading">Update Case</h3>
          <button onClick={onClose} className="text-stone-400 hover:text-stone-600"><X size={18} /></button>
        </div>
        <form onSubmit={handleSubmit} className="p-5 space-y-4">
          <div>
            <label className="block text-sm font-medium text-stone-700 mb-1">Status</label>
            <select value={form.status} onChange={e => setForm(p => ({...p, status: e.target.value}))}
              className="w-full border border-stone-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-700/30">
              <option value="pending">Pending</option>
              <option value="approved">Approved</option>
              <option value="delivered">Delivered</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-stone-700 mb-1">Grocery Kit Value (₹)</label>
            <input type="number" value={form.grocery_kit_value} onChange={e => setForm(p => ({...p, grocery_kit_value: e.target.value}))}
              className="w-full border border-stone-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-700/30" />
          </div>
          <div>
            <label className="block text-sm font-medium text-stone-700 mb-1">Delivery Date</label>
            <input type="date" value={form.delivery_date} onChange={e => setForm(p => ({...p, delivery_date: e.target.value}))}
              className="w-full border border-stone-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-700/30" />
          </div>
          <div>
            <label className="block text-sm font-medium text-stone-700 mb-1">Remarks</label>
            <textarea value={form.remarks} onChange={e => setForm(p => ({...p, remarks: e.target.value}))} rows={2}
              className="w-full border border-stone-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-700/30" />
          </div>
          <div className="flex gap-3">
            <button type="button" onClick={onClose} className="flex-1 px-4 py-2 border border-stone-300 text-stone-700 rounded-md text-sm hover:bg-stone-50">Cancel</button>
            <button type="submit" disabled={loading}
              className="flex-1 px-4 py-2 bg-green-800 text-white rounded-md text-sm font-medium hover:bg-green-900 disabled:opacity-60">
              {loading ? "Updating..." : "Update"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default function DeathAssistance() {
  const { user } = useAuth();
  const [cases, setCases] = useState([]);
  const [members, setMembers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [dialog, setDialog] = useState(null);

  const load = () => {
    setLoading(true);
    Promise.all([api.get("/death-assistance"), api.get("/members")])
      .then(([c, m]) => { setCases(c.data); setMembers(m.data); })
      .finally(() => setLoading(false));
  };
  useEffect(load, []);

  const canWrite = ["super_admin","president","secretary","treasurer","committee_member"].includes(user?.role);

  return (
    <div className="p-6 space-y-5">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold text-stone-900 font-heading">Death Assistance</h1>
          <p className="text-stone-500 text-sm">Grocery aid and support for bereaved families</p>
        </div>
        {canWrite && (
          <button onClick={() => setDialog("add")} data-testid={DEATH.addButton}
            className="flex items-center gap-2 bg-green-800 text-white px-4 py-2 rounded-md text-sm font-medium hover:bg-green-900 transition-colors">
            <Plus size={16} weight="bold" /> Record Case
          </button>
        )}
      </div>

      <div className="grid grid-cols-3 gap-4">
        {["pending","approved","delivered"].map(st => (
          <div key={st} className="stat-card">
            <p className="text-xs font-semibold uppercase tracking-wide text-stone-500 mb-1 capitalize">{st}</p>
            <p className="text-2xl font-bold text-stone-900 font-heading">{cases.filter(c => c.status === st).length}</p>
          </div>
        ))}
      </div>

      <div className="bg-white border border-stone-200 rounded-lg overflow-hidden" data-testid={DEATH.table}>
        {loading ? <div className="p-8 text-center text-stone-400">Loading...</div> :
          cases.length === 0 ? <div className="p-8 text-center text-stone-400">No death assistance cases</div> : (
            <div className="overflow-x-auto">
              <table className="w-full data-table">
                <thead>
                  <tr>
                    <th>Deceased Name</th>
                    <th>Date of Death</th>
                    <th>Contact Person</th>
                    <th>Grocery Kit (₹)</th>
                    <th>Delivery Date</th>
                    <th>Status</th>
                    <th>Remarks</th>
                    {canWrite && <th>Actions</th>}
                  </tr>
                </thead>
                <tbody>
                  {cases.map(c => (
                    <tr key={c.id}>
                      <td className="font-medium text-stone-900">{c.deceased_name}</td>
                      <td>{c.date_of_death ? new Date(c.date_of_death).toLocaleDateString("en-IN") : "-"}</td>
                      <td>{c.contact_person}</td>
                      <td>{c.grocery_kit_value ? `₹${c.grocery_kit_value?.toLocaleString("en-IN")}` : "-"}</td>
                      <td>{c.delivery_date ? new Date(c.delivery_date).toLocaleDateString("en-IN") : "-"}</td>
                      <td>
                        <span className={`inline-flex px-2 py-0.5 text-xs font-medium rounded border ${STATUS_MAP[c.status]}`}>
                          {c.status}
                        </span>
                      </td>
                      <td className="text-stone-500 max-w-xs truncate">{c.remarks || "-"}</td>
                      {canWrite && (
                        <td>
                          {c.status !== "delivered" && (
                            <button onClick={() => setDialog(c)}
                              className="px-2.5 py-1 text-xs bg-stone-100 text-stone-700 rounded hover:bg-stone-200">
                              Update
                            </button>
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

      {dialog === "add" && <AddDialog members={members} onSave={() => { setDialog(null); load(); }} onClose={() => setDialog(null)} />}
      {dialog && dialog !== "add" && (
        <UpdateDialog caseItem={dialog} onSave={() => { setDialog(null); load(); }} onClose={() => setDialog(null)} />
      )}
    </div>
  );
}
