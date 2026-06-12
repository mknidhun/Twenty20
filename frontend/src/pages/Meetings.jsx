import { useEffect, useState } from "react";
import api, { formatError } from "@/utils/api";
import { MEETINGS } from "@/constants/testIds";
import { Plus, X, CalendarBlank, CheckCircle, Trash, FilePdf } from "@phosphor-icons/react";
import { useAuth } from "@/contexts/AuthContext";

const MEETING_TYPES = ["executive", "annual_general", "emergency"];
const STATUS_MAP = {
  scheduled: "badge-pending", completed: "badge-paid", cancelled: "badge-rejected"
};
const TYPE_LABELS = { executive: "Executive Committee", annual_general: "Annual General Body", emergency: "Emergency" };
const RESOLUTION_STATUSES = ["passed", "failed", "tabled"];

function MeetingDialog({ onSave, onClose }) {
  const [form, setForm] = useState({
    meeting_type: "executive",
    title: "",
    scheduled_date: new Date().toISOString().split("T")[0],
    agenda: "",
    attendees: []
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      await api.post("/meetings", form);
      onSave();
    } catch (err) {
      setError(formatError(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
      <div className="bg-card rounded-lg shadow-lg w-full max-w-md max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between px-5 py-4 border-b border-border sticky top-0 bg-card">
          <h3 className="font-semibold text-foreground font-heading">Schedule Meeting</h3>
          <button onClick={onClose} className="text-muted-foreground/70 hover:text-foreground"><X size={18} /></button>
        </div>
        <form onSubmit={handleSubmit} className="p-5 space-y-4">
          <div>
            <label className="block text-sm font-medium text-foreground mb-1">Meeting Type *</label>
            <select required value={form.meeting_type} onChange={e => setForm(p => ({...p, meeting_type: e.target.value}))}
              className="w-full border border-input rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring/30 focus:border-primary">
              {MEETING_TYPES.map(t => <option key={t} value={t}>{TYPE_LABELS[t]}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-foreground mb-1">Title *</label>
            <input required value={form.title} onChange={e => setForm(p => ({...p, title: e.target.value}))}
              className="w-full border border-input rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring/30 focus:border-primary" />
          </div>
          <div>
            <label className="block text-sm font-medium text-foreground mb-1">Date *</label>
            <input type="date" required value={form.scheduled_date} onChange={e => setForm(p => ({...p, scheduled_date: e.target.value}))}
              className="w-full border border-input rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring/30 focus:border-primary" />
          </div>
          <div>
            <label className="block text-sm font-medium text-foreground mb-1">Agenda *</label>
            <textarea required value={form.agenda} onChange={e => setForm(p => ({...p, agenda: e.target.value}))} rows={3}
              placeholder="List the agenda items..."
              className="w-full border border-input rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring/30 focus:border-primary" />
          </div>
          {error && <p className="text-destructive text-sm bg-destructive/10 border border-destructive/30 rounded px-3 py-2">{error}</p>}
          <div className="flex gap-3">
            <button type="button" onClick={onClose} className="flex-1 px-4 py-2 border border-input text-foreground rounded-md text-sm hover:bg-muted/60">Cancel</button>
            <button type="submit" disabled={loading}
              className="flex-1 px-4 py-2 bg-primary text-primary-foreground rounded-md text-sm font-medium hover:bg-primary/90 disabled:opacity-60">
              {loading ? "Scheduling..." : "Schedule Meeting"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

function MinutesDialog({ meeting, onSave, onClose }) {
  const [form, setForm] = useState({
    minutes: meeting.minutes || "",
    status: meeting.status || "scheduled",
    resolutions_list: meeting.resolutions_list || []
  });
  const [loading, setLoading] = useState(false);

  const addResolution = () => setForm(p => ({
    ...p, resolutions_list: [...p.resolutions_list, { text: "", status: "passed" }]
  }));
  const removeResolution = (i) => setForm(p => ({
    ...p, resolutions_list: p.resolutions_list.filter((_, idx) => idx !== i)
  }));
  const updateResolution = (i, k, v) => setForm(p => ({
    ...p,
    resolutions_list: p.resolutions_list.map((r, idx) => idx === i ? { ...r, [k]: v } : r)
  }));

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      await api.put(`/meetings/${meeting.id}`, form);
      onSave();
    } catch (err) {
      alert(formatError(err));
    } finally {
      setLoading(false);
    }
  };

  const statusColors = { passed: "text-primary bg-primary/10 border-primary/25", failed: "text-destructive bg-destructive/10 border-destructive/30", tabled: "text-amber-600 dark:text-amber-400 bg-amber-500/10 border-amber-500/30" };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
      <div className="bg-card rounded-lg shadow-lg w-full max-w-xl max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between px-5 py-4 border-b border-border sticky top-0 bg-card">
          <h3 className="font-semibold text-foreground font-heading">Minutes — {meeting.title}</h3>
          <button onClick={onClose} className="text-muted-foreground/70 hover:text-foreground"><X size={18} /></button>
        </div>
        <form onSubmit={handleSubmit} className="p-5 space-y-4">
          <div>
            <label className="block text-sm font-medium text-foreground mb-1">Status</label>
            <select value={form.status} onChange={e => setForm(p => ({...p, status: e.target.value}))}
              className="w-full border border-input rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring/30">
              <option value="scheduled">Scheduled</option>
              <option value="completed">Completed</option>
              <option value="cancelled">Cancelled</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-foreground mb-1">Minutes of Meeting</label>
            <textarea value={form.minutes} onChange={e => setForm(p => ({...p, minutes: e.target.value}))} rows={4}
              placeholder="Record the proceedings of the meeting..."
              className="w-full border border-input rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring/30" />
          </div>

          {/* Structured Resolutions */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="text-sm font-medium text-foreground">Resolutions</label>
              <button type="button" onClick={addResolution}
                className="flex items-center gap-1 text-xs text-primary hover:text-primary font-medium">
                <Plus size={13} weight="bold" /> Add Resolution
              </button>
            </div>
            {form.resolutions_list.length === 0 ? (
              <p className="text-xs text-muted-foreground/70 italic">No resolutions yet. Click "Add Resolution" to begin.</p>
            ) : (
              <div className="space-y-2">
                {form.resolutions_list.map((res, i) => (
                  <div key={i} className="flex gap-2 items-start">
                    <span className="text-xs font-bold text-muted-foreground/70 mt-2.5 w-5 flex-shrink-0">{i+1}.</span>
                    <input
                      value={res.text}
                      onChange={e => updateResolution(i, "text", e.target.value)}
                      placeholder="Resolution text..."
                      data-testid={`resolution-text-${i}`}
                      className="flex-1 border border-input rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring/30"
                    />
                    <select
                      value={res.status}
                      onChange={e => updateResolution(i, "status", e.target.value)}
                      data-testid={`resolution-status-${i}`}
                      className={`border rounded-md px-2 py-2 text-xs font-medium focus:outline-none ${statusColors[res.status]}`}
                    >
                      {RESOLUTION_STATUSES.map(s => <option key={s} value={s}>{s.charAt(0).toUpperCase()+s.slice(1)}</option>)}
                    </select>
                    <button type="button" onClick={() => removeResolution(i)}
                      className="p-2 text-muted-foreground/70 hover:text-destructive hover:bg-destructive/10 rounded transition-colors flex-shrink-0">
                      <Trash size={13} />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="flex gap-3">
            <button type="button" onClick={onClose} className="flex-1 px-4 py-2 border border-input text-foreground rounded-md text-sm hover:bg-muted/60">Cancel</button>
            <button type="submit" disabled={loading}
              className="flex-1 px-4 py-2 bg-primary text-primary-foreground rounded-md text-sm font-medium hover:bg-primary/90 disabled:opacity-60">
              {loading ? "Saving..." : "Save Minutes"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default function Meetings() {
  const { user } = useAuth();
  const [meetings, setMeetings] = useState([]);
  const [loading, setLoading] = useState(true);
  const [dialog, setDialog] = useState(null);
  const [filterStatus, setFilterStatus] = useState("all");

  const canWrite = ["super_admin","president","secretary"].includes(user?.role);

  const load = () => { setLoading(true); api.get("/meetings").then(r => setMeetings(r.data)).finally(() => setLoading(false)); };
  useEffect(load, []);

  const handleDelete = async (id) => {
    if (!window.confirm("Delete this meeting?")) return;
    await api.delete(`/meetings/${id}`);
    load();
  };

  const handleDownloadMinutes = async (m) => {
    try {
      const resp = await api.get(`/meetings/${m.id}/minutes-pdf`, { responseType: "blob" });
      const url = URL.createObjectURL(new Blob([resp.data], { type: "application/pdf" }));
      const a = document.createElement("a");
      a.href = url;
      a.download = `Minutes_${m.title.replace(/ /g,"_").slice(0,30)}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
    } catch { alert("Failed to download minutes PDF"); }
  };

  const filtered = meetings.filter(m => filterStatus === "all" || m.status === filterStatus);

  return (
    <div className="p-6 space-y-5">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold text-foreground font-heading">Meetings</h1>
          <p className="text-muted-foreground text-sm">Schedule and track committee meetings</p>
        </div>
        {canWrite && (
          <button onClick={() => setDialog("new")} data-testid={MEETINGS.addButton}
            className="flex items-center gap-2 bg-primary text-primary-foreground px-4 py-2 rounded-md text-sm font-medium hover:bg-primary/90 transition-colors">
            <Plus size={16} weight="bold" /> Schedule Meeting
          </button>
        )}
      </div>

      <div className="grid grid-cols-3 gap-4">
        {["scheduled","completed","cancelled"].map(st => (
          <div key={st} className="stat-card">
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-1 capitalize">{st}</p>
            <p className="text-2xl font-bold text-foreground font-heading">{meetings.filter(m => m.status === st).length}</p>
          </div>
        ))}
      </div>

      <div className="flex gap-3">
        <select value={filterStatus} onChange={e => setFilterStatus(e.target.value)}
          className="border border-input rounded-md px-3 py-2 text-sm bg-card focus:outline-none focus:ring-2 focus:ring-ring/30">
          <option value="all">All Meetings</option>
          <option value="scheduled">Scheduled</option>
          <option value="completed">Completed</option>
          <option value="cancelled">Cancelled</option>
        </select>
      </div>

      <div className="bg-card border border-border rounded-lg overflow-hidden" data-testid={MEETINGS.table}>
        {loading ? <div className="p-8 text-center text-muted-foreground/70">Loading...</div> :
          filtered.length === 0 ? <div className="p-8 text-center text-muted-foreground/70">No meetings found</div> : (
            <div className="overflow-x-auto">
              <table className="w-full data-table">
                <thead>
                  <tr>
                    <th>Title</th>
                    <th>Type</th>
                    <th>Date</th>
                    <th>Resolutions</th>
                    <th>Status</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map(m => (
                    <tr key={m.id}>
                      <td className="font-medium text-foreground">{m.title}</td>
                      <td>
                        <span className="text-xs bg-muted px-2 py-0.5 rounded">{TYPE_LABELS[m.meeting_type] || m.meeting_type}</span>
                      </td>
                      <td>{m.scheduled_date ? new Date(m.scheduled_date).toLocaleDateString("en-IN") : "-"}</td>
                      <td>
                        {m.resolutions_list && m.resolutions_list.length > 0 ? (
                          <span className="text-xs text-muted-foreground">{m.resolutions_list.length} resolution{m.resolutions_list.length > 1 ? "s" : ""} ({m.resolutions_list.filter(r=>r.status==="passed").length} passed)</span>
                        ) : (
                          <span className="text-xs text-muted-foreground/70 italic">—</span>
                        )}
                      </td>
                      <td>
                        <span className={`inline-flex px-2 py-0.5 text-xs font-medium rounded border ${STATUS_MAP[m.status]}`}>
                          {m.status}
                        </span>
                      </td>
                      <td>
                        <div className="flex gap-1.5">
                          {canWrite && (
                            <button onClick={() => setDialog(m)}
                              className="px-2.5 py-1 text-xs bg-muted text-foreground rounded hover:bg-muted">
                              Minutes
                            </button>
                          )}
                          <button onClick={() => handleDownloadMinutes(m)}
                            data-testid="minutes-pdf-btn"
                            title="Download Minutes PDF"
                            className="p-1.5 text-muted-foreground/70 hover:text-destructive hover:bg-destructive/10 rounded transition-colors">
                            <FilePdf size={14} />
                          </button>
                          {canWrite && user?.role === "super_admin" && (
                            <button onClick={() => handleDelete(m.id)}
                              className="p-1.5 text-muted-foreground/70 hover:text-destructive hover:bg-destructive/10 rounded transition-colors">
                              <X size={13} />
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
      </div>

      {dialog === "new" && <MeetingDialog onSave={() => { setDialog(null); load(); }} onClose={() => setDialog(null)} />}
      {dialog && dialog !== "new" && (
        <MinutesDialog meeting={dialog} onSave={() => { setDialog(null); load(); }} onClose={() => setDialog(null)} />
      )}
    </div>
  );
}
