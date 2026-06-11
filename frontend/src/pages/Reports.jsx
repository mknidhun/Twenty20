import { useEffect, useState } from "react";
import api from "@/utils/api";
import { useAuth } from "@/contexts/AuthContext";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, PieChart, Pie, Cell, Legend } from "recharts";
import { FileXls, FilePdf } from "@phosphor-icons/react";

const MONTHS = ["","Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
const COLORS = ["#166534","#D97706","#DC2626","#2563EB","#7C3AED","#059669"];

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

  if (loading) return <div className="p-8 text-center text-stone-400">Loading reports...</div>;

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
          <h1 className="text-2xl font-bold text-stone-900 font-heading">Reports</h1>
          <p className="text-stone-500 text-sm">Financial and membership analytics</p>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <select value={year} onChange={e => setYear(+e.target.value)}
            className="border border-stone-300 rounded-md px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-green-700/30">
            {years.map(y => <option key={y} value={y}>{y}</option>)}
          </select>
          <button
            onClick={() => handleExport("excel")}
            disabled={exporting === "excel"}
            data-testid="export-excel-btn"
            className="flex items-center gap-1.5 px-3 py-2 bg-green-800 text-white text-sm font-medium rounded-md hover:bg-green-900 disabled:opacity-50 transition-colors"
          >
            <FileXls size={16} />
            {exporting === "excel" ? "Exporting..." : "Export Excel"}
          </button>
          <button
            onClick={() => handleExport("pdf")}
            disabled={exporting === "pdf"}
            data-testid="export-pdf-btn"
            className="flex items-center gap-1.5 px-3 py-2 bg-red-700 text-white text-sm font-medium rounded-md hover:bg-red-800 disabled:opacity-50 transition-colors"
          >
            <FilePdf size={16} />
            {exporting === "pdf" ? "Exporting..." : "Export PDF"}
          </button>
        </div>
      </div>

      {/* Membership Stats */}
      <div className="bg-white border border-stone-200 rounded-lg p-5">
        <h3 className="font-semibold text-stone-900 font-heading mb-4">Membership Overview</h3>
        <div className="flex flex-col md:flex-row gap-6 items-center">
          <div className="flex-1 grid grid-cols-2 gap-3">
            {memberReport && Object.entries({
              "Total Members": memberReport.total,
              "Active": memberReport.active,
              "Inactive": memberReport.inactive,
              "Resigned": memberReport.resigned,
              "Deceased": memberReport.deceased,
            }).map(([label, value]) => (
              <div key={label} className="bg-stone-50 rounded-md px-4 py-3">
                <p className="text-xs font-semibold uppercase tracking-wide text-stone-500">{label}</p>
                <p className="text-2xl font-bold text-stone-900 font-heading">{value}</p>
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
      <div className="bg-white border border-stone-200 rounded-lg p-5">
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-semibold text-stone-900 font-heading">Contribution Report — {year}</h3>
          <div className="text-right">
            <p className="text-xs text-stone-500">Annual Total</p>
            <p className="font-bold text-green-800">₹{contribReport?.total?.toLocaleString("en-IN") || 0}</p>
          </div>
        </div>
        <ResponsiveContainer width="100%" height={220}>
          <BarChart data={contribReport?.monthly || []} margin={{ top: 0, right: 0, bottom: 0, left: 0 }}>
            <XAxis dataKey="month" tickFormatter={(m) => MONTHS[m]} tick={{ fontSize: 11, fill: "#78716c" }} axisLine={false} tickLine={false} />
            <YAxis tick={{ fontSize: 11, fill: "#78716c" }} axisLine={false} tickLine={false} tickFormatter={(v) => `₹${v/1000}k`} />
            <Tooltip
              formatter={(v, n) => n === "total" ? [`₹${v.toLocaleString("en-IN")}`, "Amount"] : [v, "Members"]}
              labelFormatter={(m) => MONTHS[m]}
              contentStyle={{ border: "1px solid #e7e5e4", borderRadius: 6, fontSize: 12 }}
            />
            <Bar dataKey="total" name="total" fill="#166534" radius={[4,4,0,0]} />
            <Bar dataKey="count" name="count" fill="#D97706" radius={[4,4,0,0]} />
          </BarChart>
        </ResponsiveContainer>
        <p className="text-xs text-stone-400 mt-2">Green = Amount (₹), Amber = No. of members</p>
      </div>

      {/* Benefits Summary */}
      <div className="bg-white border border-stone-200 rounded-lg p-5">
        <h3 className="font-semibold text-stone-900 font-heading mb-4">Benefits Disbursed (All Time)</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {benefitData.map((b) => (
            <div key={b.name} className="border border-stone-200 rounded-lg p-4">
              <p className="text-xs font-semibold uppercase tracking-wide text-stone-500 mb-2">{b.name}</p>
              <p className="text-2xl font-bold text-stone-900 font-heading">{b.count}</p>
              <p className="text-sm text-stone-600 mt-1">₹{b.amount?.toLocaleString("en-IN")} total disbursed</p>
            </div>
          ))}
          <div className="border border-stone-200 rounded-lg p-4">
            <p className="text-xs font-semibold uppercase tracking-wide text-stone-500 mb-2">Death Assistance</p>
            <p className="text-2xl font-bold text-stone-900 font-heading">{benefitReport?.death_count || 0}</p>
            <p className="text-sm text-stone-600 mt-1">Cases delivered</p>
          </div>
        </div>
      </div>
    </div>
  );
}
