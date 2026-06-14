import { useEffect, useState } from "react";
import api, { formatError } from "@/utils/api";
import { useAuth } from "@/contexts/AuthContext";
import { Gear, FloppyDisk, CheckCircle } from "@phosphor-icons/react";

export default function Settings() {
  const { user } = useAuth();
  const [form, setForm] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);

  const canEdit = ["super_admin", "treasurer"].includes(user?.role);

  useEffect(() => {
    api.get("/settings")
      .then(r => setForm({
        standard_rate: r.data.standard_rate,
        intro_rate: r.data.intro_rate,
        intro_months: r.data.intro_months,
      }))
      .catch(e => setError(formatError(e)))
      .finally(() => setLoading(false));
  }, []);

  const save = async (e) => {
    e.preventDefault();
    setSaving(true); setError(""); setSaved(false);
    try {
      await api.put("/settings", {
        standard_rate: parseFloat(form.standard_rate),
        intro_rate: parseFloat(form.intro_rate),
        intro_months: parseInt(form.intro_months, 10),
      });
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
    } catch (err) {
      setError(formatError(err));
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <div className="p-6 text-muted-foreground/70">Loading…</div>;
  if (!form) return <div className="p-6 text-destructive">{error || "Failed to load settings"}</div>;

  const field = (key, label, hint, type = "number") => (
    <div>
      <label className="block text-sm font-medium text-foreground mb-1">{label}</label>
      <div className="relative">
        {type === "number" && key !== "intro_months" && (
          <span className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground text-sm">₹</span>
        )}
        <input type={type} value={form[key]} disabled={!canEdit}
          onChange={e => setForm(p => ({ ...p, [key]: e.target.value }))}
          className={`w-full border border-input rounded-md py-2.5 text-sm bg-card focus:outline-none focus:ring-2 focus:ring-ring/30 focus:border-primary disabled:opacity-60 ${key !== "intro_months" ? "pl-7 pr-3" : "px-3"}`} />
      </div>
      <p className="text-xs text-muted-foreground mt-1">{hint}</p>
    </div>
  );

  return (
    <div className="p-6 space-y-5 max-w-xl">
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center"><Gear size={20} className="text-primary" /></div>
        <div>
          <h1 className="text-2xl font-bold text-foreground font-heading">Settings</h1>
          <p className="text-muted-foreground text-sm">Contribution rates &amp; new-member policy</p>
        </div>
      </div>

      <form onSubmit={save} className="bg-card border border-border rounded-lg p-6 space-y-5">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">Monthly Contribution Rates</h2>
        {field("standard_rate", "Standard monthly rate", "The regular monthly contribution for established members.")}
        {field("intro_rate", "New-member intro rate", "Higher rate charged to new members during their introductory period.")}
        {field("intro_months", "Intro period (months)", "How many months a new member pays the intro rate before dropping to standard.")}

        {error && <p className="text-destructive text-sm bg-destructive/10 border border-destructive/30 rounded px-3 py-2">{error}</p>}

        {canEdit && (
          <div className="flex items-center gap-3 pt-2">
            <button type="submit" disabled={saving}
              className="inline-flex items-center gap-2 px-4 py-2.5 bg-primary text-primary-foreground rounded-md text-sm font-medium hover:bg-primary/90 disabled:opacity-60">
              <FloppyDisk size={16} /> {saving ? "Saving…" : "Save changes"}
            </button>
            {saved && <span className="inline-flex items-center gap-1 text-sm text-emerald-600"><CheckCircle size={16} weight="fill" /> Saved</span>}
          </div>
        )}
        {!canEdit && <p className="text-xs text-muted-foreground">Only super admin and treasurer can change these settings.</p>}
      </form>
    </div>
  );
}
