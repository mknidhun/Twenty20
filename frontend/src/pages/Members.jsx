import { useEffect, useState } from "react";
import api, { formatError } from "@/utils/api";
import { useAuth } from "@/contexts/AuthContext";
import { MEMBERS } from "@/constants/testIds";
import { Plus, MagnifyingGlass, PencilSimple, Trash, X } from "@phosphor-icons/react";

const STATUS_COLORS = {
  active: "badge-active", inactive: "badge-inactive",
  resigned: "badge-resigned", deceased: "badge-deceased"
};

const CANWRITE = ["super_admin", "secretary", "treasurer"];

function MemberForm({ initial, onSave, onClose }) {
  const [form, setForm] = useState(initial || {
    name: "", mobile: "", address: "", joining_date: new Date().toISOString().split("T")[0],
    status: "active", aadhaar: ""
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const f = (k, v) => setForm(p => ({ ...p, [k]: v }));

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      if (initial?.id) {
        await api.put(`/members/${initial.id}`, form);
      } else {
        await api.post("/members", form);
      }
      onSave();
    } catch (err) {
      setError(formatError(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-stone-900/40 p-4">
      <div className="bg-white rounded-lg shadow-lg w-full max-w-md" data-testid={MEMBERS.addForm}>
        <div className="flex items-center justify-between px-5 py-4 border-b border-stone-200">
          <h3 className="font-semibold text-stone-900 font-heading">{initial?.id ? "Edit Member" : "Add New Member"}</h3>
          <button onClick={onClose} className="text-stone-400 hover:text-stone-600"><X size={18} /></button>
        </div>
        <form onSubmit={handleSubmit} className="p-5 space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="col-span-2">
              <label className="block text-sm font-medium text-stone-700 mb-1">Full Name *</label>
              <input required value={form.name} onChange={e => f("name", e.target.value)}
                className="w-full border border-stone-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-700/30 focus:border-green-700" />
            </div>
            <div>
              <label className="block text-sm font-medium text-stone-700 mb-1">Mobile *</label>
              <input required value={form.mobile} onChange={e => f("mobile", e.target.value)}
                className="w-full border border-stone-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-700/30 focus:border-green-700" />
            </div>
            <div>
              <label className="block text-sm font-medium text-stone-700 mb-1">Joining Date *</label>
              <input type="date" required value={form.joining_date} onChange={e => f("joining_date", e.target.value)}
                className="w-full border border-stone-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-700/30 focus:border-green-700" />
            </div>
            <div className="col-span-2">
              <label className="block text-sm font-medium text-stone-700 mb-1">Address *</label>
              <textarea required value={form.address} onChange={e => f("address", e.target.value)} rows={2}
                className="w-full border border-stone-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-700/30 focus:border-green-700" />
            </div>
            <div>
              <label className="block text-sm font-medium text-stone-700 mb-1">Status</label>
              <select value={form.status} onChange={e => f("status", e.target.value)}
                className="w-full border border-stone-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-700/30 focus:border-green-700">
                <option value="active">Active</option>
                <option value="inactive">Inactive</option>
                <option value="resigned">Resigned</option>
                <option value="deceased">Deceased</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-stone-700 mb-1">Aadhaar (optional)</label>
              <input value={form.aadhaar} onChange={e => f("aadhaar", e.target.value)}
                className="w-full border border-stone-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-700/30 focus:border-green-700" />
            </div>
          </div>
          {error && <p className="text-red-600 text-sm bg-red-50 border border-red-200 rounded px-3 py-2">{error}</p>}
          <div className="flex gap-3 pt-1">
            <button type="button" onClick={onClose} className="flex-1 px-4 py-2 border border-stone-300 text-stone-700 rounded-md text-sm hover:bg-stone-50 transition-colors">Cancel</button>
            <button type="submit" disabled={loading} data-testid={MEMBERS.submitForm}
              className="flex-1 px-4 py-2 bg-green-800 text-white rounded-md text-sm font-medium hover:bg-green-900 transition-colors disabled:opacity-60">
              {loading ? "Saving..." : "Save Member"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default function Members() {
  const { user } = useAuth();
  const [members, setMembers] = useState([]);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [dialog, setDialog] = useState(null); // null | "add" | member obj
  const [statusFilter, setStatusFilter] = useState("all");

  const canWrite = CANWRITE.includes(user?.role);
  const canDelete = user?.role === "super_admin";

  const load = () => {
    setLoading(true);
    api.get("/members").then(r => setMembers(r.data)).finally(() => setLoading(false));
  };
  useEffect(load, []);

  const handleDelete = async (id) => {
    if (!window.confirm("Delete this member?")) return;
    await api.delete(`/members/${id}`);
    load();
  };

  const filtered = members.filter(m => {
    const matchSearch = m.name.toLowerCase().includes(search.toLowerCase()) ||
      m.member_id?.toLowerCase().includes(search.toLowerCase()) ||
      m.mobile?.includes(search);
    const matchStatus = statusFilter === "all" || m.status === statusFilter;
    return matchSearch && matchStatus;
  });

  return (
    <div className="p-6 space-y-5">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold text-stone-900 font-heading">Members</h1>
          <p className="text-stone-500 text-sm">{members.length} total members</p>
        </div>
        {canWrite && (
          <button onClick={() => setDialog("add")} data-testid={MEMBERS.addButton}
            className="flex items-center gap-2 bg-green-800 text-white px-4 py-2 rounded-md text-sm font-medium hover:bg-green-900 transition-colors active:scale-[0.98]">
            <Plus size={16} weight="bold" /> Add Member
          </button>
        )}
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-3">
        <div className="relative flex-1 min-w-[200px]">
          <MagnifyingGlass size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-stone-400" />
          <input
            value={search} onChange={e => setSearch(e.target.value)}
            placeholder="Search by name, ID or mobile..."
            data-testid={MEMBERS.searchInput}
            className="w-full pl-9 pr-4 py-2 border border-stone-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-green-700/30 focus:border-green-700 bg-white"
          />
        </div>
        <select value={statusFilter} onChange={e => setStatusFilter(e.target.value)}
          className="border border-stone-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-700/30 focus:border-green-700 bg-white">
          <option value="all">All Status</option>
          <option value="active">Active</option>
          <option value="inactive">Inactive</option>
          <option value="resigned">Resigned</option>
          <option value="deceased">Deceased</option>
        </select>
      </div>

      {/* Table */}
      <div className="bg-white border border-stone-200 rounded-lg overflow-hidden" data-testid={MEMBERS.table}>
        {loading ? (
          <div className="p-8 text-center text-stone-400">Loading members...</div>
        ) : filtered.length === 0 ? (
          <div className="p-8 text-center text-stone-400">
            {search ? "No members match your search" : "No members yet. Add your first member!"}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full data-table">
              <thead>
                <tr>
                  <th className="text-left">Member ID</th>
                  <th className="text-left">Name</th>
                  <th className="text-left">Mobile</th>
                  <th className="text-left">Address</th>
                  <th className="text-left">Joining Date</th>
                  <th className="text-left">Status</th>
                  {canWrite && <th className="text-right">Actions</th>}
                </tr>
              </thead>
              <tbody>
                {filtered.map(m => (
                  <tr key={m.id} data-testid={MEMBERS.memberRow}>
                    <td><span className="font-mono text-xs bg-stone-100 px-2 py-0.5 rounded">{m.member_id}</span></td>
                    <td className="font-medium text-stone-900">{m.name}</td>
                    <td className="text-stone-600">{m.mobile}</td>
                    <td className="text-stone-500 max-w-xs truncate">{m.address}</td>
                    <td>{m.joining_date ? new Date(m.joining_date).toLocaleDateString("en-IN") : "-"}</td>
                    <td>
                      <span className={`inline-flex px-2 py-0.5 text-xs font-medium rounded border ${STATUS_COLORS[m.status] || "badge-pending"}`}>
                        {m.status}
                      </span>
                    </td>
                    {canWrite && (
                      <td className="text-right">
                        <div className="flex items-center justify-end gap-2">
                          <button onClick={() => setDialog(m)} data-testid={MEMBERS.editButton}
                            className="p-1.5 text-stone-400 hover:text-green-700 hover:bg-green-50 rounded transition-colors">
                            <PencilSimple size={15} />
                          </button>
                          {canDelete && (
                            <button onClick={() => handleDelete(m.id)} data-testid={MEMBERS.deleteButton}
                              className="p-1.5 text-stone-400 hover:text-red-600 hover:bg-red-50 rounded transition-colors">
                              <Trash size={15} />
                            </button>
                          )}
                        </div>
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
        <MemberForm
          initial={dialog === "add" ? null : dialog}
          onSave={() => { setDialog(null); load(); }}
          onClose={() => setDialog(null)}
        />
      )}
    </div>
  );
}
