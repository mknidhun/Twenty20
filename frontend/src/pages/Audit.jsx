import { useState, useEffect } from "react";
import api from "@/utils/api";
import { useAuth } from "@/contexts/AuthContext";
import { Scales, CheckCircle, Seal, CalendarCheck } from "@phosphor-icons/react";

const MONTHS = ["","Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];

export default function Audit() {
  const { user } = useAuth();
  const now = new Date();
  const [year, setYear] = useState(now.getFullYear());
  const [report, setReport] = useState(null);
  const [signOffs, setSignOffs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [remarks, setRemarks] = useState("");
  const [signLoading, setSignLoading] = useState(false);
  const [signError, setSignError] = useState("");
  const [signSuccess, setSignSuccess] = useState(false);

  const years = Array.from({ length: 5 }, (_, i) => now.getFullYear() - i);

  const fetchData = async () => {
    setLoading(true);
    setSignError("");
    setSignSuccess(false);
    try {
      const [rRes, sRes] = await Promise.all([
        api.get(`/audit/report?year=${year}`),
        api.get("/audit/sign-offs"),
      ]);
      setReport(rRes.data);
      setSignOffs(sRes.data);
    } catch (err) {
      console.error("Failed to fetch audit data", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchData(); }, [year]);

  const alreadySigned = signOffs.some(
    s => s.year === year && s.auditor_id === user?.id
  );

  const handleSignOff = async () => {
    if (!remarks.trim()) {
      setSignError("Please enter remarks before signing off.");
      return;
    }
    setSignLoading(true);
    setSignError("");
    try {
      await api.post("/audit/sign-off", { year, remarks });
      setSignSuccess(true);
      setRemarks("");
      await fetchData();
    } catch (err) {
      setSignError(err.response?.data?.detail || "Sign-off failed. You may have already signed off for this year.");
    } finally {
      setSignLoading(false);
    }
  };

  const canAccess = ["super_admin", "president", "secretary", "treasurer", "auditor"].includes(user?.role);
  const isAuditor = user?.role === "auditor";

  if (!canAccess) {
    return (
      <div className="p-8 text-center text-muted-foreground">
        You do not have permission to access this page.
      </div>
    );
  }

  if (loading) {
    return <div className="p-8 text-center text-muted-foreground/70">Loading audit report...</div>;
  }

  const yearSignOffs = signOffs.filter(s => s.year === year);

  return (
    <div className="p-6 space-y-6 max-w-4xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold text-foreground font-heading flex items-center gap-2">
            <Scales size={24} weight="duotone" className="text-primary" />
            Annual Audit
          </h1>
          <p className="text-muted-foreground text-sm mt-0.5">
            Read-only financial summary for auditor review and sign-off
          </p>
        </div>
        <select
          value={year}
          onChange={e => setYear(+e.target.value)}
          data-testid="audit-year-select"
          className="border border-input rounded-md px-3 py-2 text-sm bg-card focus:outline-none focus:ring-2 focus:ring-ring/30"
        >
          {years.map(y => <option key={y} value={y}>{y}</option>)}
        </select>
      </div>

      {/* Annual Summary */}
      {report && (
        <div className="bg-card border border-border rounded-lg p-5 space-y-4" data-testid="audit-summary">
          <h3 className="font-semibold text-foreground font-heading text-sm uppercase tracking-wide text-primary">
            Financial Summary — {report.year}
          </h3>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
            {[
              { label: "Active Members", value: report.active_members },
              { label: `Contributions (${report.year})`, value: `₹${report.total_contributions?.toLocaleString("en-IN")}` },
              { label: "Contribution Records", value: report.contribution_count },
              { label: "Marriage Benefits", value: `${report.marriage_count} (₹${report.marriage_total?.toLocaleString("en-IN")})` },
              { label: "Housewarming Benefits", value: `${report.housewarming_count} (₹${report.housewarming_total?.toLocaleString("en-IN")})` },
              { label: "Medical Aid Cases", value: `${report.medical_aid_count} (₹${report.medical_aid_total?.toLocaleString("en-IN")})` },
              { label: "Total Credits", value: `₹${report.total_credits?.toLocaleString("en-IN")}` },
              { label: "Total Debits", value: `₹${report.total_debits?.toLocaleString("en-IN")}` },
              { label: "Closing Balance", value: `₹${report.closing_balance?.toLocaleString("en-IN")}`,
                highlight: true },
            ].map(({ label, value, highlight }) => (
              <div key={label} className={`rounded-md px-4 py-3 ${highlight ? "bg-primary/10 border border-primary/25" : "bg-muted/50"}`}>
                <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{label}</p>
                <p className={`text-lg font-bold font-heading mt-0.5 ${highlight ? "text-primary" : "text-foreground"}`}>{value}</p>
              </div>
            ))}
          </div>

          {/* Monthly breakdown */}
          {report.monthly_breakdown && report.monthly_breakdown.length > 0 && (
            <div className="space-y-2">
              <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Monthly Breakdown</h4>
              <div className="overflow-x-auto">
                <table className="w-full text-sm" data-testid="audit-monthly-table">
                  <thead>
                    <tr className="border-b border-border">
                      <th className="text-left py-2 px-3 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Month</th>
                      <th className="text-center py-2 px-3 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Members Paid</th>
                      <th className="text-right py-2 px-3 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Amount (₹)</th>
                    </tr>
                  </thead>
                  <tbody>
                    {report.monthly_breakdown.map((m) => (
                      <tr key={m.month} className="border-b border-border hover:bg-muted/60">
                        <td className="py-2 px-3 font-medium text-foreground">{MONTHS[m.month]}</td>
                        <td className="py-2 px-3 text-center text-muted-foreground">{m.count}</td>
                        <td className="py-2 px-3 text-right font-medium text-foreground">
                          ₹{m.amount?.toLocaleString("en-IN")}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Sign-offs for this year */}
      <div className="bg-card border border-border rounded-lg p-5 space-y-3">
        <h3 className="font-semibold text-foreground font-heading text-sm uppercase tracking-wide">
          Audit Sign-offs — {year}
        </h3>
        {yearSignOffs.length === 0 ? (
          <p className="text-sm text-muted-foreground/70 italic">No sign-offs recorded for {year} yet.</p>
        ) : (
          <div className="space-y-2">
            {yearSignOffs.map((s) => (
              <div key={s.id} className="flex items-start gap-3 bg-primary/10 border border-primary/25 rounded-md p-4"
                   data-testid="sign-off-record">
                <Seal size={20} weight="fill" className="text-primary mt-0.5 flex-shrink-0" />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between gap-2 flex-wrap">
                    <p className="font-semibold text-foreground text-sm">{s.auditor_name}</p>
                    <p className="text-xs text-muted-foreground flex items-center gap-1">
                      <CalendarCheck size={12} />
                      {s.signed_at ? new Date(s.signed_at).toLocaleString("en-IN", {
                        day: "numeric", month: "short", year: "numeric",
                        hour: "2-digit", minute: "2-digit"
                      }) : ""}
                    </p>
                  </div>
                  <p className="text-sm text-muted-foreground mt-1 italic">"{s.remarks}"</p>
                  <p className="text-xs text-muted-foreground/70 mt-0.5">{s.auditor_email}</p>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Sign-off Form — Auditor only */}
      {isAuditor && (
        <div className="bg-card border border-border rounded-lg p-5 space-y-4" data-testid="sign-off-form">
          <h3 className="font-semibold text-foreground font-heading text-sm uppercase tracking-wide flex items-center gap-2">
            <Seal size={16} weight="duotone" className="text-primary" />
            Auditor Sign-off
          </h3>
          {alreadySigned ? (
            <div className="flex items-center gap-3 bg-primary/10 border border-primary/25 rounded-md p-4">
              <CheckCircle size={20} weight="fill" className="text-primary" />
              <p className="text-sm text-primary font-medium">
                You have already signed off on the {year} accounts.
              </p>
            </div>
          ) : (
            <>
              <div className="space-y-1.5">
                <label className="text-sm font-medium text-foreground">
                  Audit Remarks <span className="text-destructive">*</span>
                </label>
                <textarea
                  value={remarks}
                  onChange={e => { setRemarks(e.target.value); setSignError(""); }}
                  data-testid="audit-remarks-input"
                  rows={4}
                  placeholder={`Enter your audit observations and remarks for the ${year} accounts...`}
                  className="w-full border border-input rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring/30 resize-none"
                />
              </div>
              {signError && (
                <p className="text-sm text-destructive font-medium" data-testid="sign-off-error">{signError}</p>
              )}
              {signSuccess && (
                <div className="flex items-center gap-2 text-primary text-sm font-medium">
                  <CheckCircle size={16} weight="fill" />
                  Sign-off recorded successfully.
                </div>
              )}
              <button
                onClick={handleSignOff}
                disabled={signLoading || !remarks.trim()}
                data-testid="sign-off-submit-btn"
                className="px-5 py-2.5 bg-primary text-primary-foreground text-sm font-medium rounded-md hover:bg-primary/90 disabled:opacity-50 transition-colors flex items-center gap-2"
              >
                <Seal size={16} />
                {signLoading ? "Signing..." : `Sign Off on ${year} Accounts`}
              </button>
              <p className="text-xs text-muted-foreground/70">
                By signing off, you confirm that you have reviewed the {year} financial records of Twenty20 Charity Group Wariyad and found them to be in order (or have noted your observations above).
              </p>
            </>
          )}
        </div>
      )}

      {/* All Sign-offs History */}
      {signOffs.filter(s => s.year !== year).length > 0 && (
        <div className="bg-card border border-border rounded-lg p-5 space-y-3">
          <h3 className="font-semibold text-foreground font-heading text-sm uppercase tracking-wide">
            Previous Year Sign-offs
          </h3>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border">
                  <th className="text-left py-2 px-3 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Year</th>
                  <th className="text-left py-2 px-3 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Auditor</th>
                  <th className="text-left py-2 px-3 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Remarks</th>
                  <th className="text-left py-2 px-3 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Date</th>
                </tr>
              </thead>
              <tbody>
                {signOffs.filter(s => s.year !== year).map((s) => (
                  <tr key={s.id} className="border-b border-border hover:bg-muted/60">
                    <td className="py-2 px-3 font-bold text-foreground">{s.year}</td>
                    <td className="py-2 px-3 font-medium text-foreground">{s.auditor_name}</td>
                    <td className="py-2 px-3 text-muted-foreground max-w-xs truncate italic">"{s.remarks}"</td>
                    <td className="py-2 px-3 text-xs text-muted-foreground/70">
                      {s.signed_at ? new Date(s.signed_at).toLocaleDateString("en-IN") : ""}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
