import { useEffect, useState, useRef } from "react";
import api, { formatError } from "@/utils/api";
import { useAuth } from "@/contexts/AuthContext";
import { MEMBERS } from "@/constants/testIds";
import { Plus, MagnifyingGlass, PencilSimple, Trash, X, UploadSimple, DownloadSimple, Spinner, CheckCircle, Warning, QrCode } from "@phosphor-icons/react";

const STATUS_COLORS = {
  active: "badge-active", inactive: "badge-inactive",
  resigned: "badge-resigned", deceased: "badge-deceased"
};

const CANWRITE = ["super_admin", "secretary", "treasurer"];

function ImportDialog({ onSave, onClose }) {
  const [file, setFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const fileRef = useRef();

  const downloadTemplate = () => {
    window.open(`${process.env.REACT_APP_BACKEND_URL}/api/members/import-template`, "_blank");
  };

  const handleImport = async () => {
    if (!file) return;
    setLoading(true);
    setError("");
    try {
      const fd = new FormData();
      fd.append("file", file);
      const res = await api.post("/members/import", fd, { headers: { "Content-Type": "multipart/form-data" } });
      setResult(res.data);
    } catch (err) {
      setError(formatError(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
      <div className="bg-card rounded-lg shadow-lg w-full max-w-md">
        <div className="flex items-center justify-between px-5 py-4 border-b border-border">
          <h3 className="font-semibold text-foreground font-heading">Bulk Import Members</h3>
          <button onClick={onClose} className="text-muted-foreground/70 hover:text-foreground"><X size={18} /></button>
        </div>
        <div className="p-5 space-y-4">
          {/* Template download */}
          <div className="bg-sky-500/100/10 border border-sky-500/30 rounded-md p-3 flex items-start gap-2">
            <DownloadSimple size={16} className="text-sky-600 dark:text-sky-400 flex-shrink-0 mt-0.5" />
            <div>
              <p className="text-sm font-medium text-sky-600 dark:text-sky-400">Download the template first</p>
              <p className="text-xs text-sky-600 dark:text-sky-400 mt-0.5">Fill in your data and upload the completed file.</p>
              <button onClick={downloadTemplate}
                className="mt-2 text-xs text-sky-600 dark:text-sky-400 font-semibold underline hover:text-sky-600 dark:text-sky-400 dark:hover:text-sky-300">
                Download CSV Template
              </button>
            </div>
          </div>

          {/* File upload area */}
          {!result && (
            <div
              className={`border-2 border-dashed rounded-lg p-6 text-center cursor-pointer transition-colors ${file ? "border-primary/50 bg-primary/10" : "border-input hover:border-primary/50 hover:bg-primary/5"}`}
              onClick={() => fileRef.current?.click()}
            >
              <input
                ref={fileRef}
                type="file"
                accept=".csv,.xlsx,.xls"
                className="hidden"
                data-testid="import-file-input"
                onChange={e => setFile(e.target.files[0] || null)}
              />
              {file ? (
                <div className="flex items-center justify-center gap-2 text-primary">
                  <CheckCircle size={20} weight="fill" />
                  <div>
                    <p className="text-sm font-semibold">{file.name}</p>
                    <p className="text-xs text-primary">{(file.size / 1024).toFixed(1)} KB — Click to change</p>
                  </div>
                </div>
              ) : (
                <div className="text-muted-foreground">
                  <UploadSimple size={28} className="mx-auto mb-2 text-muted-foreground/70" />
                  <p className="text-sm font-medium">Click to upload CSV or Excel file</p>
                  <p className="text-xs mt-1 text-muted-foreground/70">.csv, .xlsx, .xls — Max 5MB</p>
                </div>
              )}
            </div>
          )}

          {/* Result */}
          {result && (
            <div className="space-y-2">
              <div className="bg-primary/10 border border-primary/25 rounded-md p-3">
                <p className="text-sm font-semibold text-primary flex items-center gap-2">
                  <CheckCircle size={16} weight="fill" /> {result.imported} members imported
                </p>
                {result.skipped > 0 && <p className="text-xs text-primary mt-1">{result.skipped} empty rows skipped</p>}
              </div>
              {result.errors.length > 0 && (
                <div className="bg-amber-500/10 border border-amber-500/30 rounded-md p-3">
                  <p className="text-xs font-semibold text-amber-600 dark:text-amber-400 flex items-center gap-1 mb-1">
                    <Warning size={14} /> {result.errors.length} rows had errors:
                  </p>
                  <ul className="text-xs text-amber-600 dark:text-amber-400 space-y-0.5 max-h-24 overflow-y-auto">
                    {result.errors.map((e, i) => <li key={i}>• {e}</li>)}
                  </ul>
                </div>
              )}
            </div>
          )}

          {error && <p className="text-destructive text-sm bg-destructive/10 border border-destructive/30 rounded px-3 py-2">{error}</p>}

          <div className="flex gap-3">
            <button type="button" onClick={result ? onSave : onClose}
              className="flex-1 px-4 py-2 border border-input text-foreground rounded-md text-sm hover:bg-muted/60">
              {result ? "Close & Refresh" : "Cancel"}
            </button>
            {!result && (
              <button onClick={handleImport} disabled={!file || loading} data-testid="import-submit-button"
                className="flex-1 px-4 py-2 bg-primary text-primary-foreground rounded-md text-sm font-medium hover:bg-primary/90 disabled:opacity-60 flex items-center justify-center gap-2">
                {loading ? <><Spinner size={14} className="animate-spin" />Importing...</> : <><UploadSimple size={14} />Import</>}
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

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
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
      <div className="bg-card rounded-lg shadow-lg w-full max-w-md" data-testid={MEMBERS.addForm}>
        <div className="flex items-center justify-between px-5 py-4 border-b border-border">
          <h3 className="font-semibold text-foreground font-heading">{initial?.id ? "Edit Member" : "Add New Member"}</h3>
          <button onClick={onClose} className="text-muted-foreground/70 hover:text-foreground"><X size={18} /></button>
        </div>
        <form onSubmit={handleSubmit} className="p-5 space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="col-span-2">
              <label className="block text-sm font-medium text-foreground mb-1">Full Name *</label>
              <input required value={form.name} onChange={e => f("name", e.target.value)}
                data-testid="member-name-input"
                className="w-full border border-input rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring/30 focus:border-primary" />
            </div>
            <div>
              <label className="block text-sm font-medium text-foreground mb-1">Mobile *</label>
              <input required value={form.mobile} onChange={e => f("mobile", e.target.value)}
                data-testid="member-mobile-input"
                className="w-full border border-input rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring/30 focus:border-primary" />
            </div>
            <div>
              <label className="block text-sm font-medium text-foreground mb-1">Joining Date *</label>
              <input type="date" required value={form.joining_date} onChange={e => f("joining_date", e.target.value)}
                className="w-full border border-input rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring/30 focus:border-primary" />
            </div>
            <div className="col-span-2">
              <label className="block text-sm font-medium text-foreground mb-1">Address *</label>
              <textarea required value={form.address} onChange={e => f("address", e.target.value)} rows={2}
                className="w-full border border-input rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring/30 focus:border-primary" />
            </div>
            <div>
              <label className="block text-sm font-medium text-foreground mb-1">Status</label>
              <select value={form.status} onChange={e => f("status", e.target.value)}
                className="w-full border border-input rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring/30 focus:border-primary">
                <option value="active">Active</option>
                <option value="inactive">Inactive</option>
                <option value="resigned">Resigned</option>
                <option value="deceased">Deceased</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-foreground mb-1">Aadhaar (optional)</label>
              <input value={form.aadhaar} onChange={e => f("aadhaar", e.target.value)}
                className="w-full border border-input rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring/30 focus:border-primary" />
            </div>
          </div>
          {error && <p className="text-destructive text-sm bg-destructive/10 border border-destructive/30 rounded px-3 py-2">{error}</p>}
          <div className="flex gap-3 pt-1">
            <button type="button" onClick={onClose} className="flex-1 px-4 py-2 border border-input text-foreground rounded-md text-sm hover:bg-muted/60 transition-colors">Cancel</button>
            <button type="submit" disabled={loading} data-testid={MEMBERS.submitForm}
              className="flex-1 px-4 py-2 bg-primary text-primary-foreground rounded-md text-sm font-medium hover:bg-primary/90 transition-colors disabled:opacity-60">
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
  const [dialog, setDialog] = useState(null); // null | "add" | "import" | member obj
  const [statusFilter, setStatusFilter] = useState("all");
  const [seeding, setSeeding] = useState(false);

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

  const handleDownloadCard = async (member) => {
    try {
      const resp = await api.get(`/members/${member.id}/qr-card`, { responseType: "blob" });
      const url = URL.createObjectURL(new Blob([resp.data], { type: "application/pdf" }));
      const a = document.createElement("a");
      a.href = url;
      a.download = `MemberCard_${member.name.replace(/ /g,"_")}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      alert("Failed to download member card");
    }
  };

  const handleSeedDemo = async () => {
    if (!window.confirm("This will load 15 demo members with contribution history. Continue?")) return;
    setSeeding(true);
    try {
      const res = await api.post("/demo/seed");
      alert(res.data.message);
      load();
    } catch (err) {
      alert(formatError(err));
    } finally {
      setSeeding(false);
    }
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
          <h1 className="text-2xl font-bold text-foreground font-heading">Members</h1>
          <p className="text-muted-foreground text-sm">{members.length} total members</p>
        </div>
        {canWrite && (
          <div className="flex items-center gap-2 flex-wrap">
            {user?.role === "super_admin" && (
              <button onClick={handleSeedDemo} disabled={seeding} data-testid="seed-demo-button"
                className="flex items-center gap-2 border border-input bg-card text-foreground px-3 py-2 rounded-md text-sm font-medium hover:bg-muted/60 transition-colors disabled:opacity-60">
                {seeding ? <Spinner size={14} className="animate-spin" /> : null}
                Load Demo Data
              </button>
            )}
            <button onClick={() => setDialog("import")} data-testid="import-members-button"
              className="flex items-center gap-2 border border-primary text-primary px-4 py-2 rounded-md text-sm font-medium hover:bg-primary/10 transition-colors">
              <UploadSimple size={16} weight="bold" /> Import CSV/Excel
            </button>
            <button onClick={() => setDialog("add")} data-testid={MEMBERS.addButton}
              className="flex items-center gap-2 bg-primary text-primary-foreground px-4 py-2 rounded-md text-sm font-medium hover:bg-primary/90 transition-colors active:scale-[0.98]">
              <Plus size={16} weight="bold" /> Add Member
            </button>
          </div>
        )}
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-3">
        <div className="relative flex-1 min-w-[200px]">
          <MagnifyingGlass size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground/70" />
          <input
            value={search} onChange={e => setSearch(e.target.value)}
            placeholder="Search by name, ID or mobile..."
            data-testid={MEMBERS.searchInput}
            className="w-full pl-9 pr-4 py-2 border border-input rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-ring/30 focus:border-primary bg-card"
          />
        </div>
        <select value={statusFilter} onChange={e => setStatusFilter(e.target.value)}
          className="border border-input rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring/30 focus:border-primary bg-card">
          <option value="all">All Status</option>
          <option value="active">Active</option>
          <option value="inactive">Inactive</option>
          <option value="resigned">Resigned</option>
          <option value="deceased">Deceased</option>
        </select>
      </div>

      {/* Table */}
      <div className="bg-card border border-border rounded-lg overflow-hidden" data-testid={MEMBERS.table}>
        {loading ? (
          <div className="p-8 text-center text-muted-foreground/70">Loading members...</div>
        ) : filtered.length === 0 ? (
          <div className="p-8 text-center text-muted-foreground/70">
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
                  <th className="text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map(m => (
                  <tr key={m.id} data-testid={MEMBERS.memberRow}>
                    <td><span className="font-mono text-xs bg-muted px-2 py-0.5 rounded">{m.member_id}</span></td>
                    <td className="font-medium text-foreground">{m.name}</td>
                    <td className="text-muted-foreground">{m.mobile}</td>
                    <td className="text-muted-foreground max-w-xs truncate">{m.address}</td>
                    <td>{m.joining_date ? new Date(m.joining_date).toLocaleDateString("en-IN", {day:"2-digit",month:"short",year:"numeric"}) : "-"}</td>
                    <td>
                      <span className={`inline-flex px-2 py-0.5 text-xs font-medium rounded border ${STATUS_COLORS[m.status] || "badge-pending"}`}>
                        {m.status}
                      </span>
                    </td>
                    {canWrite && (
                      <td className="text-right">
                        <div className="flex items-center justify-end gap-2">
                          <button onClick={() => handleDownloadCard(m)} data-testid="qr-card-btn"
                            title="Download Member QR Card"
                            className="p-1.5 text-muted-foreground/70 hover:text-primary hover:bg-primary/10 rounded transition-colors">
                            <QrCode size={15} />
                          </button>
                          <button onClick={() => setDialog(m)} data-testid={MEMBERS.editButton}
                            className="p-1.5 text-muted-foreground/70 hover:text-primary hover:bg-primary/10 rounded transition-colors">
                            <PencilSimple size={15} />
                          </button>
                          {canDelete && (
                            <button onClick={() => handleDelete(m.id)} data-testid={MEMBERS.deleteButton}
                              className="p-1.5 text-muted-foreground/70 hover:text-destructive hover:bg-destructive/10 rounded transition-colors">
                              <Trash size={15} />
                            </button>
                          )}
                        </div>
                      </td>
                    )}
                    {!canWrite && (
                      <td className="text-right">
                        <button onClick={() => handleDownloadCard(m)} data-testid="qr-card-btn"
                          title="Download Member QR Card"
                          className="p-1.5 text-muted-foreground/70 hover:text-primary hover:bg-primary/10 rounded transition-colors">
                          <QrCode size={15} />
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

      {dialog === "add" && (
        <MemberForm
          initial={null}
          onSave={() => { setDialog(null); load(); }}
          onClose={() => setDialog(null)}
        />
      )}
      {dialog === "import" && (
        <ImportDialog
          onSave={() => { setDialog(null); load(); }}
          onClose={() => setDialog(null)}
        />
      )}
      {dialog && dialog !== "add" && dialog !== "import" && (
        <MemberForm
          initial={dialog}
          onSave={() => { setDialog(null); load(); }}
          onClose={() => setDialog(null)}
        />
      )}
    </div>
  );
}
