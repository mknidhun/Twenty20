import { useEffect, useState } from "react";
import api, { formatError } from "@/utils/api";
import { COMMITTEE } from "@/constants/testIds";
import { Plus, X, UserPlus, Trash, ArrowsLeftRight } from "@phosphor-icons/react";
import { useAuth } from "@/contexts/AuthContext";

const POSITIONS = ["President", "Vice President", "Secretary", "Joint Secretary", "Treasurer", "Executive Member"];

const DOCS_CHECKLIST = [
  "Minutes Book", "Membership Register", "Cashbook Register",
  "Bank Passbook / Statement", "Benefit Applications File",
  "Receipt Book", "Voucher Files", "Previous Audit Reports",
];
const REGS_CHECKLIST = [
  "Member Photo Register", "Meeting Register", "Benefit Register",
  "Medical Aid Register", "Death Assistance Register", "Collection Register",
];

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

function HandoverDialog({ onSave, onClose }) {
  const now = new Date();
  const [form, setForm] = useState({
    from_year: now.getFullYear() - 1,
    to_year: now.getFullYear(),
    handover_date: now.toISOString().split("T")[0],
    fund_balance: "",
    documents_checklist: DOCS_CHECKLIST.map(item => ({ item, checked: false })),
    registers_checklist: REGS_CHECKLIST.map(item => ({ item, checked: false })),
    outstanding_items: "",
    notes: "",
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const toggleDoc = (i) => setForm(p => ({
    ...p,
    documents_checklist: p.documents_checklist.map((d, idx) => idx === i ? { ...d, checked: !d.checked } : d)
  }));
  const toggleReg = (i) => setForm(p => ({
    ...p,
    registers_checklist: p.registers_checklist.map((r, idx) => idx === i ? { ...r, checked: !r.checked } : r)
  }));

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!form.fund_balance) { setError("Fund balance is required"); return; }
    setLoading(true);
    setError("");
    try {
      await api.post("/committee/handovers", { ...form, fund_balance: parseFloat(form.fund_balance) });
      onSave();
    } catch (err) {
      setError(formatError(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-stone-900/40 p-4">
      <div className="bg-white rounded-lg shadow-lg w-full max-w-xl max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between px-5 py-4 border-b border-stone-200 sticky top-0 bg-white">
          <h3 className="font-semibold text-stone-900 font-heading">Record Committee Handover</h3>
          <button onClick={onClose} className="text-stone-400 hover:text-stone-600"><X size={18} /></button>
        </div>
        <form onSubmit={handleSubmit} className="p-5 space-y-5">
          {/* Years + Date + Balance */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium text-stone-700 mb-1">Outgoing Committee Year</label>
              <input type="number" value={form.from_year} onChange={e => setForm(p => ({...p, from_year: +e.target.value}))}
                className="w-full border border-stone-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-700/30" />
            </div>
            <div>
              <label className="block text-sm font-medium text-stone-700 mb-1">Incoming Committee Year</label>
              <input type="number" value={form.to_year} onChange={e => setForm(p => ({...p, to_year: +e.target.value}))}
                className="w-full border border-stone-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-700/30" />
            </div>
            <div>
              <label className="block text-sm font-medium text-stone-700 mb-1">Handover Date *</label>
              <input type="date" required value={form.handover_date} onChange={e => setForm(p => ({...p, handover_date: e.target.value}))}
                className="w-full border border-stone-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-700/30" />
            </div>
            <div>
              <label className="block text-sm font-medium text-stone-700 mb-1">Fund Balance at Handover (Rs) *</label>
              <input type="number" step="0.01" min="0" required value={form.fund_balance}
                onChange={e => setForm(p => ({...p, fund_balance: e.target.value}))}
                placeholder="0.00"
                className="w-full border border-stone-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-700/30" />
            </div>
          </div>

          {/* Documents Checklist */}
          <div>
            <label className="block text-sm font-medium text-stone-700 mb-2">Documents Handed Over</label>
            <div className="grid grid-cols-2 gap-2">
              {form.documents_checklist.map((d, i) => (
                <label key={i} className="flex items-center gap-2 cursor-pointer">
                  <input type="checkbox" checked={d.checked} onChange={() => toggleDoc(i)}
                    data-testid={`doc-check-${i}`}
                    className="w-4 h-4 accent-green-700" />
                  <span className="text-sm text-stone-700">{d.item}</span>
                </label>
              ))}
            </div>
          </div>

          {/* Registers Checklist */}
          <div>
            <label className="block text-sm font-medium text-stone-700 mb-2">Registers Handed Over</label>
            <div className="grid grid-cols-2 gap-2">
              {form.registers_checklist.map((r, i) => (
                <label key={i} className="flex items-center gap-2 cursor-pointer">
                  <input type="checkbox" checked={r.checked} onChange={() => toggleReg(i)}
                    data-testid={`reg-check-${i}`}
                    className="w-4 h-4 accent-green-700" />
                  <span className="text-sm text-stone-700">{r.item}</span>
                </label>
              ))}
            </div>
          </div>

          {/* Outstanding Items */}
          <div>
            <label className="block text-sm font-medium text-stone-700 mb-1">Outstanding / Pending Items</label>
            <textarea value={form.outstanding_items} onChange={e => setForm(p => ({...p, outstanding_items: e.target.value}))} rows={2}
              placeholder="List any pending cases, unresolved issues, outstanding payments..."
              className="w-full border border-stone-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-700/30" />
          </div>

          {/* Notes */}
          <div>
            <label className="block text-sm font-medium text-stone-700 mb-1">Additional Notes</label>
            <textarea value={form.notes} onChange={e => setForm(p => ({...p, notes: e.target.value}))} rows={2}
              placeholder="Any remarks about the handover..."
              className="w-full border border-stone-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-700/30" />
          </div>

          {error && <p className="text-red-600 text-sm bg-red-50 border border-red-200 rounded px-3 py-2">{error}</p>}
          <div className="flex gap-3">
            <button type="button" onClick={onClose} className="flex-1 px-4 py-2 border border-stone-300 text-stone-700 rounded-md text-sm hover:bg-stone-50">Cancel</button>
            <button type="submit" disabled={loading} data-testid="submit-handover-btn"
              className="flex-1 px-4 py-2 bg-green-800 text-white rounded-md text-sm font-medium hover:bg-green-900 disabled:opacity-60">
              {loading ? "Saving..." : "Record Handover"}
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
  const [handovers, setHandovers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [dialog, setDialog] = useState(false);
  const [showHandover, setShowHandover] = useState(false);
  const [expanded, setExpanded] = useState(null);
  const [tab, setTab] = useState("committees"); // "committees" | "handovers"

  const canWrite = ["super_admin","president","secretary"].includes(user?.role);

  const load = () => {
    setLoading(true);
    Promise.all([
      api.get("/committee"),
      api.get("/committee/handovers"),
    ]).then(([c, h]) => {
      setCommittees(c.data);
      setHandovers(h.data);
    }).finally(() => setLoading(false));
  };
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
          <p className="text-stone-500 text-sm">Executive committee structure and handover records</p>
        </div>
        {canWrite && (
          <div className="flex gap-2">
            {tab === "handovers" ? (
              <button onClick={() => setShowHandover(true)} data-testid="record-handover-btn"
                className="flex items-center gap-2 bg-green-800 text-white px-4 py-2 rounded-md text-sm font-medium hover:bg-green-900 transition-colors">
                <ArrowsLeftRight size={16} weight="bold" /> Record Handover
              </button>
            ) : (
              <button onClick={() => setDialog(true)} data-testid={COMMITTEE.addButton}
                className="flex items-center gap-2 bg-green-800 text-white px-4 py-2 rounded-md text-sm font-medium hover:bg-green-900 transition-colors">
                <Plus size={16} weight="bold" /> Form Committee
              </button>
            )}
          </div>
        )}
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-stone-200">
        {["committees", "handovers"].map(t => (
          <button key={t} onClick={() => setTab(t)}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors capitalize ${
              tab === t ? "border-green-700 text-green-800" : "border-transparent text-stone-500 hover:text-stone-700"
            }`}>
            {t === "committees" ? `Committees (${committees.length})` : `Handover Records (${handovers.length})`}
          </button>
        ))}
      </div>

      {loading ? <div className="p-8 text-center text-stone-400">Loading...</div> : (
        <>
          {/* Committees Tab */}
          {tab === "committees" && (
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
            )
          )}

          {/* Handovers Tab */}
          {tab === "handovers" && (
            handovers.length === 0 ? (
              <div className="bg-white border border-stone-200 rounded-lg p-8 text-center text-stone-400">
                No handover records yet. Record a handover when a committee term ends.
              </div>
            ) : (
              <div className="space-y-4" data-testid="handovers-list">
                {handovers.map(h => (
                  <div key={h.id} className="bg-white border border-stone-200 rounded-lg p-5 space-y-4">
                    <div className="flex items-start justify-between">
                      <div>
                        <p className="font-semibold text-stone-900 font-heading text-base">
                          Committee {h.from_year} → {h.to_year}
                        </p>
                        <p className="text-xs text-stone-500 mt-0.5">
                          Handover on {h.handover_date ? new Date(h.handover_date).toLocaleDateString("en-IN", {day:"numeric",month:"long",year:"numeric"}) : "—"} · Recorded by {h.recorded_by_name}
                        </p>
                      </div>
                      <div className="bg-green-50 border border-green-200 rounded-md px-3 py-1.5 text-center">
                        <p className="text-xs text-green-600 font-medium">Fund Balance</p>
                        <p className="text-lg font-bold text-green-800 font-heading">₹{h.fund_balance?.toLocaleString("en-IN")}</p>
                      </div>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <div>
                        <p className="text-xs font-semibold uppercase tracking-wide text-stone-500 mb-2">Documents</p>
                        <div className="space-y-1">
                          {(h.documents_checklist || []).map((d, i) => (
                            <div key={i} className="flex items-center gap-2">
                              <span className={`w-4 h-4 rounded flex-shrink-0 flex items-center justify-center text-xs ${d.checked ? "bg-green-100 text-green-700" : "bg-stone-100 text-stone-400"}`}>
                                {d.checked ? "✓" : "—"}
                              </span>
                              <span className={`text-sm ${d.checked ? "text-stone-700" : "text-stone-400 line-through"}`}>{d.item}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                      <div>
                        <p className="text-xs font-semibold uppercase tracking-wide text-stone-500 mb-2">Registers</p>
                        <div className="space-y-1">
                          {(h.registers_checklist || []).map((r, i) => (
                            <div key={i} className="flex items-center gap-2">
                              <span className={`w-4 h-4 rounded flex-shrink-0 flex items-center justify-center text-xs ${r.checked ? "bg-green-100 text-green-700" : "bg-stone-100 text-stone-400"}`}>
                                {r.checked ? "✓" : "—"}
                              </span>
                              <span className={`text-sm ${r.checked ? "text-stone-700" : "text-stone-400 line-through"}`}>{r.item}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>

                    {h.outstanding_items && (
                      <div>
                        <p className="text-xs font-semibold uppercase tracking-wide text-stone-500 mb-1">Outstanding Items</p>
                        <p className="text-sm text-amber-800 bg-amber-50 border border-amber-200 rounded p-3">{h.outstanding_items}</p>
                      </div>
                    )}
                    {h.notes && (
                      <div>
                        <p className="text-xs font-semibold uppercase tracking-wide text-stone-500 mb-1">Notes</p>
                        <p className="text-sm text-stone-600">{h.notes}</p>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )
          )}
        </>
      )}

      {dialog && <CommitteeDialog onSave={() => { setDialog(false); load(); }} onClose={() => setDialog(false)} />}
      {showHandover && <HandoverDialog onSave={() => { setShowHandover(false); load(); }} onClose={() => setShowHandover(false)} />}
    </div>
  );
}
