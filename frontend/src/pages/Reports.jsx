import { useEffect, useState } from "react";
import api from "@/utils/api";
import { useAuth } from "@/contexts/AuthContext";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, PieChart, Pie, Cell, Legend } from "recharts";
import { FileXls, FilePdf } from "@phosphor-icons/react";

const MONTHS = ["","Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
const COLORS = ["hsl(var(--chart-1))","hsl(var(--chart-2))","hsl(var(--chart-3))","hsl(var(--chart-4))","hsl(var(--chart-5))","hsl(var(--accent))"];

export default function Reports() {
  const { user } = useAuth();
  const [memberReport, setMemberReport] = useState(null);
  const [contribReport, setContribReport] = useState(null);
  const [benefitReport, setBenefitReport] = useState(null);
  const [year, setYear] = useState(new Date().getFullYear());
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState(null);
  const years = Array.from({length: 5}, (_, i) => new Date().getFullYear() - i);

  useEffect(() => {
    setLoading(true);
    Promise.all([
      api.get("/reports/members"),
      api.get(`/reports/contributions/${year}`),
      api.get("/reports/benefits")
    ]).then(([m, c, b]) => {
      setMemberReport(m.data);
      setContribReport(c.data);
      setBenefitReport(b.data);
    }).finally(() => setLoading(false));
  }, [year]);

  const handleExport = async (type) => {
    setExporting(type);
    try {
      const resp = await api.get(`/reports/export/${type}?year=${year}`, { responseType: "blob" });
      const ext = type === "excel" ? "xlsx" : "pdf";
      const mime = type === "excel"
        ? "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        : "application/pdf";
      const url = URL.createObjectURL(new Blob([resp.data], { type: mime }));
      const a = document.createElement("a");
      a.href = url;
      a.download = `Twenty20_Wariyad_Report_${year}.${ext}`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      alert(`Export failed: ${err.message}`);
    } finally {
      setExporting(null);
    }
  };

  if (loading) return <div className="p-8 text-center text-muted-foreground/70">Loading reports...</div>;

  const memberPieData = memberReport ? [
    { name: "Active", value: memberReport.active },
    { name: "Inactive", value: memberReport.inactive },
    { name: "Resigned", value: memberReport.resigned },
    { name: "Deceased", value: memberReport.deceased },
  ].filter(d => d.value > 0) : [];

  const benefitData = benefitReport ? [
    { name: "Marriage", count: benefitReport.marriage_count, amount: benefitReport.marriage_total },
    { name: "Housewarming", count: benefitReport.housewarming_count, amount: benefitReport.housewarming_total },
    { name: "Medical Aid", count: benefitReport.medical_count, amount: benefitReport.medical_total },
  ] : [];

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold text-foreground font-heading">Reports</h1>
          <p className="text-muted-foreground text-sm">Financial and membership analytics</p>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <select value={year} onChange={e => setYear(+e.target.value)}
            className="border border-input rounded-md px-3 py-2 text-sm bg-card focus:outline-none focus:ring-2 focus:ring-ring/30">
            {years.map(y => <option key={y} value={y}>{y}</option>)}
          </select>
          <button
            onClick={() => handleExport("excel")}
            disabled={exporting === "excel"}
            data-testid="export-excel-btn"
            className="flex items-center gap-1.5 px-3 py-2 bg-primary text-primary-foreground text-sm font-medium rounded-md hover:bg-primary/90 disabled:opacity-50 transition-colors"
          >
            <FileXls size={16} />
            {exporting === "excel" ? "Exporting..." : "Export Excel"}
          </button>
          <button
            onClick={() => handleExport("pdf")}
            disabled={exporting === "pdf"}
            data-testid="export-pdf-btn"
            className="flex items-center gap-1.5 px-3 py-2 bg-destructive text-destructive-foreground text-sm font-medium rounded-md hover:bg-destructive/90 disabled:opacity-50 transition-colors"
          >
            <FilePdf size={16} />
            {exporting === "pdf" ? "Exporting..." : "Export PDF"}
          </button>
        </div>
      </div>

      {/* Membership Stats */}
      <div className="bg-card border border-border rounded-lg p-5">
        <h3 className="font-semibold text-foreground font-heading mb-4">Membership Overview</h3>
        <div className="flex flex-col md:flex-row gap-6 items-center">
          <div className="flex-1 grid grid-cols-2 gap-3">
            {memberReport && Object.entries({
              "Total Members": memberReport.total,
              "Active": memberReport.active,
              "Inactive": memberReport.inactive,
              "Resigned": memberReport.resigned,
              "Deceased": memberReport.deceased,
            }).map(([label, value]) => (
              <div key={label} className="bg-muted/50 rounded-md px-4 py-3">
                <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{label}</p>
                <p className="text-2xl font-bold text-foreground font-heading">{value}</p>
              </div>
            ))}
          </div>
          {memberPieData.length > 0 && (
            <div className="w-64 h-48">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie data={memberPieData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={70} label>
                    {memberPieData.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                  </Pie>
                  <Legend iconType="circle" iconSize={8} wrapperStyle={{ fontSize: 11 }} />
                </PieChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>
      </div>

      {/* Monthly Contribution Chart */}
      <div className="bg-card border border-border rounded-lg p-5">
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-semibold text-foreground font-heading">Contribution Report — {year}</h3>
          <div className="text-right">
            <p className="text-xs text-muted-foreground">Annual Total</p>
            <p className="font-bold text-primary">₹{contribReport?.total?.toLocaleString("en-IN") || 0}</p>
          </div>
        </div>
        <ResponsiveContainer width="100%" height={220}>
          <BarChart data={contribReport?.monthly || []} margin={{ top: 0, right: 0, bottom: 0, left: 0 }}>
            <XAxis dataKey="month" tickFormatter={(m) => MONTHS[m]} tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }} axisLine={false} tickLine={false} />
            <YAxis tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }} axisLine={false} tickLine={false} tickFormatter={(v) => `₹${v/1000}k`} />
            <Tooltip
              formatter={(v, n) => n === "total" ? [`₹${v.toLocaleString("en-IN")}`, "Amount"] : [v, "Members"]}
              labelFormatter={(m) => MONTHS[m]}
              contentStyle={{ background: "hsl(var(--card))", color: "hsl(var(--foreground))", border: "1px solid hsl(var(--border))", borderRadius: 6, fontSize: 12 }}
            />
            <Bar dataKey="total" name="total" fill="hsl(var(--chart-1))" radius={[4,4,0,0]} />
            <Bar dataKey="count" name="count" fill="hsl(var(--chart-2))" radius={[4,4,0,0]} />
          </BarChart>
        </ResponsiveContainer>
        <p className="text-xs text-muted-foreground/70 mt-2">Green = Amount (₹), Amber = No. of members</p>
      </div>

      {/* Benefits Summary */}
      <div className="bg-card border border-border rounded-lg p-5">
        <h3 className="font-semibold text-foreground font-heading mb-4">Benefits Disbursed (All Time)</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {benefitData.map((b) => (
            <div key={b.name} className="border border-border rounded-lg p-4">
              <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-2">{b.name}</p>
              <p className="text-2xl font-bold text-foreground font-heading">{b.count}</p>
              <p className="text-sm text-muted-foreground mt-1">₹{b.amount?.toLocaleString("en-IN")} total disbursed</p>
            </div>
          ))}
          <div className="border border-border rounded-lg p-4">
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-2">Death Assistance</p>
            <p className="text-2xl font-bold text-foreground font-heading">{benefitReport?.death_count || 0}</p>
            <p className="text-sm text-muted-foreground mt-1">Cases delivered</p>
          </div>
        </div>
      </div>
    </div>
  );
}
