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
      <div className="p-8 text-center text-stone-500">
        You do not have permission to access this page.
      </div>
    );
  }

  if (loading) {
    return <div className="p-8 text-center text-stone-400">Loading audit report...</div>;
  }

  const yearSignOffs = signOffs.filter(s => s.year === year);

  return (
    <div className="p-6 space-y-6 max-w-4xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold text-stone-900 font-heading flex items-center gap-2">
            <Scales size={24} weight="duotone" className="text-green-700" />
            Annual Audit
          </h1>
          <p className="text-stone-500 text-sm mt-0.5">
            Read-only financial summary for auditor review and sign-off
          </p>
        </div>
        <select
          value={year}
          onChange={e => setYear(+e.target.value)}
          data-testid="audit-year-select"
          className="border border-stone-300 rounded-md px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-green-700/30"
        >
          {years.map(y => <option key={y} value={y}>{y}</option>)}
        </select>
      </div>

      {/* Annual Summary */}
      {report && (
        <div className="bg-white border border-stone-200 rounded-lg p-5 space-y-4" data-testid="audit-summary">
          <h3 className="font-semibold text-stone-900 font-heading text-sm uppercase tracking-wide text-green-700">
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
              <div key={label} className={`rounded-md px-4 py-3 ${highlight ? "bg-green-50 border border-green-200" : "bg-stone-50"}`}>
                <p className="text-xs font-semibold uppercase tracking-wide text-stone-500">{label}</p>
                <p className={`text-lg font-bold font-heading mt-0.5 ${highlight ? "text-green-800" : "text-stone-900"}`}>{value}</p>
              </div>
            ))}
          </div>

          {/* Monthly breakdown */}
          {report.monthly_breakdown && report.monthly_breakdown.length > 0 && (
            <div className="space-y-2">
              <h4 className="text-xs font-semibold uppercase tracking-wide text-stone-500">Monthly Breakdown</h4>
              <div className="overflow-x-auto">
                <table className="w-full text-sm" data-testid="audit-monthly-table">
                  <thead>
                    <tr className="border-b border-stone-200">
                      <th className="text-left py-2 px-3 text-xs font-semibold uppercase tracking-wide text-stone-500">Month</th>
                      <th className="text-center py-2 px-3 text-xs font-semibold uppercase tracking-wide text-stone-500">Members Paid</th>
                      <th className="text-right py-2 px-3 text-xs font-semibold uppercase tracking-wide text-stone-500">Amount (₹)</th>
                    </tr>
                  </thead>
                  <tbody>
                    {report.monthly_breakdown.map((m) => (
                      <tr key={m.month} className="border-b border-stone-100 hover:bg-stone-50">
                        <td className="py-2 px-3 font-medium text-stone-800">{MONTHS[m.month]}</td>
                        <td className="py-2 px-3 text-center text-stone-600">{m.count}</td>
                        <td className="py-2 px-3 text-right font-medium text-stone-900">
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
      <div className="bg-white border border-stone-200 rounded-lg p-5 space-y-3">
        <h3 className="font-semibold text-stone-900 font-heading text-sm uppercase tracking-wide">
          Audit Sign-offs — {year}
        </h3>
        {yearSignOffs.length === 0 ? (
          <p className="text-sm text-stone-400 italic">No sign-offs recorded for {year} yet.</p>
        ) : (
          <div className="space-y-2">
            {yearSignOffs.map((s) => (
              <div key={s.id} className="flex items-start gap-3 bg-green-50 border border-green-200 rounded-md p-4"
                   data-testid="sign-off-record">
                <Seal size={20} weight="fill" className="text-green-700 mt-0.5 flex-shrink-0" />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between gap-2 flex-wrap">
                    <p className="font-semibold text-stone-900 text-sm">{s.auditor_name}</p>
                    <p className="text-xs text-stone-500 flex items-center gap-1">
                      <CalendarCheck size={12} />
                      {s.signed_at ? new Date(s.signed_at).toLocaleString("en-IN", {
                        day: "numeric", month: "short", year: "numeric",
                        hour: "2-digit", minute: "2-digit"
                      }) : ""}
                    </p>
                  </div>
                  <p className="text-sm text-stone-600 mt-1 italic">"{s.remarks}"</p>
                  <p className="text-xs text-stone-400 mt-0.5">{s.auditor_email}</p>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Sign-off Form — Auditor only */}
      {isAuditor && (
        <div className="bg-white border border-stone-200 rounded-lg p-5 space-y-4" data-testid="sign-off-form">
          <h3 className="font-semibold text-stone-900 font-heading text-sm uppercase tracking-wide flex items-center gap-2">
            <Seal size={16} weight="duotone" className="text-green-700" />
            Auditor Sign-off
          </h3>
          {alreadySigned ? (
            <div className="flex items-center gap-3 bg-green-50 border border-green-200 rounded-md p-4">
              <CheckCircle size={20} weight="fill" className="text-green-700" />
              <p className="text-sm text-green-800 font-medium">
                You have already signed off on the {year} accounts.
              </p>
            </div>
          ) : (
            <>
              <div className="space-y-1.5">
                <label className="text-sm font-medium text-stone-700">
                  Audit Remarks <span className="text-red-500">*</span>
                </label>
                <textarea
                  value={remarks}
                  onChange={e => { setRemarks(e.target.value); setSignError(""); }}
                  data-testid="audit-remarks-input"
                  rows={4}
                  placeholder={`Enter your audit observations and remarks for the ${year} accounts...`}
                  className="w-full border border-stone-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-700/30 resize-none"
                />
              </div>
              {signError && (
                <p className="text-sm text-red-600 font-medium" data-testid="sign-off-error">{signError}</p>
              )}
              {signSuccess && (
                <div className="flex items-center gap-2 text-green-700 text-sm font-medium">
                  <CheckCircle size={16} weight="fill" />
                  Sign-off recorded successfully.
                </div>
              )}
              <button
                onClick={handleSignOff}
                disabled={signLoading || !remarks.trim()}
                data-testid="sign-off-submit-btn"
                className="px-5 py-2.5 bg-green-800 text-white text-sm font-medium rounded-md hover:bg-green-900 disabled:opacity-50 transition-colors flex items-center gap-2"
              >
                <Seal size={16} />
                {signLoading ? "Signing..." : `Sign Off on ${year} Accounts`}
              </button>
              <p className="text-xs text-stone-400">
                By signing off, you confirm that you have reviewed the {year} financial records of Twenty20 Charity Group Wariyad and found them to be in order (or have noted your observations above).
              </p>
            </>
          )}
        </div>
      )}

      {/* All Sign-offs History */}
      {signOffs.filter(s => s.year !== year).length > 0 && (
        <div className="bg-white border border-stone-200 rounded-lg p-5 space-y-3">
          <h3 className="font-semibold text-stone-900 font-heading text-sm uppercase tracking-wide">
            Previous Year Sign-offs
          </h3>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-stone-200">
                  <th className="text-left py-2 px-3 text-xs font-semibold uppercase tracking-wide text-stone-500">Year</th>
                  <th className="text-left py-2 px-3 text-xs font-semibold uppercase tracking-wide text-stone-500">Auditor</th>
                  <th className="text-left py-2 px-3 text-xs font-semibold uppercase tracking-wide text-stone-500">Remarks</th>
                  <th className="text-left py-2 px-3 text-xs font-semibold uppercase tracking-wide text-stone-500">Date</th>
                </tr>
              </thead>
              <tbody>
                {signOffs.filter(s => s.year !== year).map((s) => (
                  <tr key={s.id} className="border-b border-stone-100 hover:bg-stone-50">
                    <td className="py-2 px-3 font-bold text-stone-700">{s.year}</td>
                    <td className="py-2 px-3 font-medium text-stone-900">{s.auditor_name}</td>
                    <td className="py-2 px-3 text-stone-600 max-w-xs truncate italic">"{s.remarks}"</td>
                    <td className="py-2 px-3 text-xs text-stone-400">
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
