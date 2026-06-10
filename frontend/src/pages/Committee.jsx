import { useEffect, useState } from "react";
import api, { formatError } from "@/utils/api";
import { COMMITTEE } from "@/constants/testIds";
import { Plus, X, UserPlus, Trash } from "@phosphor-icons/react";
import { useAuth } from "@/contexts/AuthContext";

const POSITIONS = ["President", "Vice President", "Secretary", "Joint Secretary", "Treasurer", "Executive Member"];

function CommitteeDialog({ onSave, onClose }) {
  const now = new Date();
  const [form, setForm] = useState({
    year: now.getFullYear(),
    start_date: `${now.getFullYear()}-01-01`,
    end_date: `${now.getFullYear()}-12-31`,
    positions: [{ position: "President", member_name: "" }]
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const addPosition = () => setForm(p => ({...p, positions: [...p.positions, { position: "Executive Member", member_name: "" }]}));
  const removePosition = (i) => setForm(p => ({...p, positions: p.positions.filter((_, idx) => idx !== i)}));
  const updatePosition = (i, k, v) => setForm(p => ({
    ...p,
    positions: p.positions.map((pos, idx) => idx === i ? {...pos, [k]: v} : pos)
  }));

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      await api.post("/committee", form);
      onSave();
    } catch (err) {
      setError(formatError(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-stone-900/40 p-4">
      <div className="bg-white rounded-lg shadow-lg w-full max-w-lg max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between px-5 py-4 border-b border-stone-200 sticky top-0 bg-white">
          <h3 className="font-semibold text-stone-900 font-heading">Form New Committee</h3>
          <button onClick={onClose} className="text-stone-400 hover:text-stone-600"><X size={18} /></button>
        </div>
        <form onSubmit={handleSubmit} className="p-5 space-y-4">
          <div className="grid grid-cols-3 gap-3">
            <div>
              <label className="block text-sm font-medium text-stone-700 mb-1">Year *</label>
              <input type="number" required value={form.year} onChange={e => setForm(p => ({...p, year: +e.target.value}))}
                className="w-full border border-stone-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-700/30 focus:border-green-700" />
            </div>
            <div>
              <label className="block text-sm font-medium text-stone-700 mb-1">Start Date</label>
              <input type="date" value={form.start_date} onChange={e => setForm(p => ({...p, start_date: e.target.value}))}
                className="w-full border border-stone-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-700/30 focus:border-green-700" />
            </div>
            <div>
              <label className="block text-sm font-medium text-stone-700 mb-1">End Date</label>
              <input type="date" value={form.end_date} onChange={e => setForm(p => ({...p, end_date: e.target.value}))}
                className="w-full border border-stone-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-700/30 focus:border-green-700" />
            </div>
          </div>

          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="text-sm font-medium text-stone-700">Committee Positions</label>
              <button type="button" onClick={addPosition}
                className="flex items-center gap-1 text-xs text-green-700 hover:text-green-900 font-medium">
                <UserPlus size={14} /> Add Position
              </button>
            </div>
            <div className="space-y-2">
              {form.positions.map((pos, i) => (
                <div key={i} className="flex gap-2 items-start">
                  <select value={pos.position} onChange={e => updatePosition(i, "position", e.target.value)}
                    className="flex-1 border border-stone-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-700/30">
                    {POSITIONS.map(p => <option key={p} value={p}>{p}</option>)}
                  </select>
                  <input placeholder="Member name"
                    value={pos.member_name} onChange={e => updatePosition(i, "member_name", e.target.value)}
                    className="flex-1 border border-stone-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-700/30" />
                  {form.positions.length > 1 && (
                    <button type="button" onClick={() => removePosition(i)}
                      className="p-2 text-stone-400 hover:text-red-600 hover:bg-red-50 rounded transition-colors">
                      <Trash size={14} />
                    </button>
                  )}
                </div>
              ))}
            </div>
          </div>

          {error && <p className="text-red-600 text-sm bg-red-50 border border-red-200 rounded px-3 py-2">{error}</p>}
          <div className="flex gap-3">
            <button type="button" onClick={onClose} className="flex-1 px-4 py-2 border border-stone-300 text-stone-700 rounded-md text-sm hover:bg-stone-50">Cancel</button>
            <button type="submit" disabled={loading}
              className="flex-1 px-4 py-2 bg-green-800 text-white rounded-md text-sm font-medium hover:bg-green-900 disabled:opacity-60">
              {loading ? "Saving..." : "Create Committee"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default function Committee() {
  const { user } = useAuth();
  const [committees, setCommittees] = useState([]);
  const [loading, setLoading] = useState(true);
  const [dialog, setDialog] = useState(false);
  const [expanded, setExpanded] = useState(null);

  const canWrite = ["super_admin","president","secretary"].includes(user?.role);

  const load = () => { setLoading(true); api.get("/committee").then(r => setCommittees(r.data)).finally(() => setLoading(false)); };
  useEffect(load, []);

  const handleDelete = async (id) => {
    if (!window.confirm("Delete this committee record?")) return;
    await api.delete(`/committee/${id}`);
    load();
  };

  return (
    <div className="p-6 space-y-5">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold text-stone-900 font-heading">Committee Management</h1>
          <p className="text-stone-500 text-sm">Executive committee structure by year</p>
        </div>
        {canWrite && (
          <button onClick={() => setDialog(true)} data-testid={COMMITTEE.addButton}
            className="flex items-center gap-2 bg-green-800 text-white px-4 py-2 rounded-md text-sm font-medium hover:bg-green-900 transition-colors">
            <Plus size={16} weight="bold" /> Form Committee
          </button>
        )}
      </div>

      {loading ? <div className="p-8 text-center text-stone-400">Loading...</div> :
        committees.length === 0 ? (
          <div className="bg-white border border-stone-200 rounded-lg p-8 text-center text-stone-400">
            No committees recorded yet
          </div>
        ) : (
          <div className="space-y-4" data-testid={COMMITTEE.table}>
            {committees.map(c => (
              <div key={c.id} className="bg-white border border-stone-200 rounded-lg overflow-hidden">
                <div
                  className="flex items-center justify-between px-5 py-4 cursor-pointer hover:bg-stone-50 transition-colors"
                  onClick={() => setExpanded(expanded === c.id ? null : c.id)}
                >
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 bg-green-50 rounded-full flex items-center justify-center text-green-800 font-bold text-sm">
                      {c.year}
                    </div>
                    <div>
                      <p className="font-semibold text-stone-900 font-heading">Committee {c.year}</p>
                      <p className="text-xs text-stone-500">
                        {c.start_date ? new Date(c.start_date).toLocaleDateString("en-IN") : ""} — {c.end_date ? new Date(c.end_date).toLocaleDateString("en-IN") : ""}
                        · {c.positions?.length} members
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className={`px-2 py-0.5 text-xs font-medium rounded border ${c.is_active ? "badge-active" : "badge-inactive"}`}>
                      {c.is_active ? "Active" : "Inactive"}
                    </span>
                    {canWrite && user?.role === "super_admin" && (
                      <button onClick={(e) => { e.stopPropagation(); handleDelete(c.id); }}
                        className="p-1.5 text-stone-400 hover:text-red-600 hover:bg-red-50 rounded transition-colors">
                        <Trash size={14} />
                      </button>
                    )}
                  </div>
                </div>
                {expanded === c.id && c.positions && (
                  <div className="border-t border-stone-100 px-5 py-4">
                    <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                      {c.positions.map((pos, i) => (
                        <div key={i} className="bg-stone-50 rounded-md px-3 py-2.5">
                          <p className="text-xs font-semibold text-stone-500 uppercase tracking-wide">{pos.position}</p>
                          <p className="text-sm font-medium text-stone-900 mt-0.5">{pos.member_name || "—"}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}

      {dialog && <CommitteeDialog onSave={() => { setDialog(false); load(); }} onClose={() => setDialog(false)} />}
    </div>
  );
}
