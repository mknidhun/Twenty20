import { useEffect, useState } from "react";
import api, { formatError } from "@/utils/api";
import { useAuth } from "@/contexts/AuthContext";
import { Plus, X, PencilSimple, Trash } from "@phosphor-icons/react";

const ROLES = ["super_admin","president","secretary","treasurer","committee_member","auditor","member"];
const ROLE_LABELS = {
  super_admin: "Super Admin", president: "President", secretary: "Secretary",
  treasurer: "Treasurer", committee_member: "Committee Member",
  auditor: "Auditor", member: "Member"
};
const ROLE_BADGE = {
  super_admin: "bg-purple-50 text-purple-800 border-purple-200",
  president: "bg-green-50 text-green-800 border-green-200",
  secretary: "bg-blue-50 text-blue-800 border-blue-200",
  treasurer: "bg-amber-50 text-amber-800 border-amber-200",
  committee_member: "bg-stone-100 text-stone-700 border-stone-200",
  auditor: "bg-sky-50 text-sky-700 border-sky-200",
  member: "bg-stone-50 text-stone-600 border-stone-200",
};

function UserDialog({ initial, members, onSave, onClose }) {
  const [form, setForm] = useState(initial ? {
    name: initial.name, email: initial.email, role: initial.role, password: "", member_id: initial.member_id || ""
  } : { name: "", email: "", password: "", role: "member", member_id: "" });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      if (initial?.id) {
        await api.put(`/users/${initial.id}`, { name: form.name, role: form.role });
      } else {
        await api.post("/users", { ...form, member_id: form.member_id || undefined });
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
      <div className="bg-white rounded-lg shadow-lg w-full max-w-md">
        <div className="flex items-center justify-between px-5 py-4 border-b border-stone-200">
          <h3 className="font-semibold text-stone-900 font-heading">{initial?.id ? "Edit User" : "Add User"}</h3>
          <button onClick={onClose} className="text-stone-400 hover:text-stone-600"><X size={18} /></button>
        </div>
        <form onSubmit={handleSubmit} className="p-5 space-y-4">
          <div>
            <label className="block text-sm font-medium text-stone-700 mb-1">Full Name *</label>
            <input required value={form.name} onChange={e => setForm(p => ({...p, name: e.target.value}))}
              className="w-full border border-stone-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-700/30 focus:border-green-700" />
          </div>
          {!initial?.id && (
            <div>
              <label className="block text-sm font-medium text-stone-700 mb-1">Email *</label>
              <input type="email" required value={form.email} onChange={e => setForm(p => ({...p, email: e.target.value}))}
                className="w-full border border-stone-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-700/30 focus:border-green-700" />
            </div>
          )}
          {!initial?.id && (
            <div>
              <label className="block text-sm font-medium text-stone-700 mb-1">Password *</label>
              <input type="password" required value={form.password} onChange={e => setForm(p => ({...p, password: e.target.value}))}
                className="w-full border border-stone-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-700/30 focus:border-green-700" />
            </div>
          )}
          <div>
            <label className="block text-sm font-medium text-stone-700 mb-1">Role *</label>
            <select required value={form.role} onChange={e => setForm(p => ({...p, role: e.target.value}))}
              className="w-full border border-stone-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-700/30 focus:border-green-700">
              {ROLES.map(r => <option key={r} value={r}>{ROLE_LABELS[r]}</option>)}
            </select>
          </div>
          {form.role === "member" && !initial?.id && (
            <div>
              <label className="block text-sm font-medium text-stone-700 mb-1">Link to Member (optional)</label>
              <select value={form.member_id} onChange={e => setForm(p => ({...p, member_id: e.target.value}))}
                className="w-full border border-stone-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-700/30 focus:border-green-700">
                <option value="">— Not linked —</option>
                {members.filter(m => m.status === "active").map(m => (
                  <option key={m.id} value={m.id}>{m.member_id} — {m.name}</option>
                ))}
              </select>
            </div>
          )}
          {error && <p className="text-red-600 text-sm bg-red-50 border border-red-200 rounded px-3 py-2">{error}</p>}
          <div className="flex gap-3">
            <button type="button" onClick={onClose} className="flex-1 px-4 py-2 border border-stone-300 text-stone-700 rounded-md text-sm hover:bg-stone-50">Cancel</button>
            <button type="submit" disabled={loading}
              className="flex-1 px-4 py-2 bg-green-800 text-white rounded-md text-sm font-medium hover:bg-green-900 disabled:opacity-60">
              {loading ? "Saving..." : "Save User"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default function Users() {
  const { user } = useAuth();
  const [users, setUsers] = useState([]);
  const [members, setMembers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [dialog, setDialog] = useState(null);
  const canAccess = ["super_admin","secretary"].includes(user?.role);

  const load = () => {
    if (!canAccess) return;
    setLoading(true);
    Promise.all([api.get("/users"), api.get("/members")])
      .then(([u, m]) => { setUsers(u.data); setMembers(m.data); })
      .finally(() => setLoading(false));
  };
  useEffect(load, [canAccess]);

  if (!canAccess) {
    return (
      <div className="p-6">
        <div className="bg-red-50 border border-red-200 rounded-lg p-6 text-center">
          <p className="text-red-700 font-medium">Access Restricted</p>
          <p className="text-red-600 text-sm mt-1">You don't have permission to manage users.</p>
        </div>
      </div>
    );
  }

  const handleDelete = async (id) => {
    if (!window.confirm("Delete this user?")) return;
    await api.delete(`/users/${id}`);
    load();
  };

  return (
    <div className="p-6 space-y-5">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold text-stone-900 font-heading">User Management</h1>
          <p className="text-stone-500 text-sm">Manage system access and roles</p>
        </div>
        <button onClick={() => setDialog("new")} data-testid="add-user-button"
          className="flex items-center gap-2 bg-green-800 text-white px-4 py-2 rounded-md text-sm font-medium hover:bg-green-900 transition-colors">
          <Plus size={16} weight="bold" /> Add User
        </button>
      </div>

      <div className="bg-white border border-stone-200 rounded-lg overflow-hidden" data-testid="users-table">
        {loading ? <div className="p-8 text-center text-stone-400">Loading...</div> :
          users.length === 0 ? <div className="p-8 text-center text-stone-400">No users found</div> : (
            <div className="overflow-x-auto">
              <table className="w-full data-table">
                <thead>
                  <tr>
                    <th>Name</th>
                    <th>Email</th>
                    <th>Role</th>
                    <th>Member ID</th>
                    <th>Status</th>
                    <th>Created</th>
                    {user?.role === "super_admin" && <th className="text-right">Actions</th>}
                  </tr>
                </thead>
                <tbody>
                  {users.map(u => (
                    <tr key={u.id}>
                      <td className="font-medium text-stone-900">{u.name}</td>
                      <td className="text-stone-600">{u.email}</td>
                      <td>
                        <span className={`inline-flex px-2 py-0.5 text-xs font-medium rounded border ${ROLE_BADGE[u.role] || "bg-stone-100 text-stone-600 border-stone-200"}`}>
                          {ROLE_LABELS[u.role] || u.role}
                        </span>
                      </td>
                      <td className="text-stone-500 text-xs">{u.member_id ? <span className="font-mono bg-stone-100 px-1.5 py-0.5 rounded">{u.member_id}</span> : "-"}</td>
                      <td>
                        <span className={`inline-flex px-2 py-0.5 text-xs font-medium rounded border ${u.is_active ? "badge-active" : "badge-inactive"}`}>
                          {u.is_active ? "Active" : "Inactive"}
                        </span>
                      </td>
                      <td>{u.created_at ? new Date(u.created_at).toLocaleDateString("en-IN") : "-"}</td>
                      {user?.role === "super_admin" && (
                        <td className="text-right">
                          <div className="flex items-center justify-end gap-2">
                            <button onClick={() => setDialog(u)}
                              className="p-1.5 text-stone-400 hover:text-green-700 hover:bg-green-50 rounded transition-colors">
                              <PencilSimple size={15} />
                            </button>
                            {u.id !== user.id && (
                              <button onClick={() => handleDelete(u.id)}
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

      {dialog === "new" && <UserDialog members={members} onSave={() => { setDialog(null); load(); }} onClose={() => setDialog(null)} />}
      {dialog && dialog !== "new" && (
        <UserDialog initial={dialog} members={members} onSave={() => { setDialog(null); load(); }} onClose={() => setDialog(null)} />
      )}
    </div>
  );
}
