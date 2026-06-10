import { useEffect, useState } from "react";
import api from "@/utils/api";
import { useAuth } from "@/contexts/AuthContext";
import { DASHBOARD } from "@/constants/testIds";
import {
  Users, CurrencyInr, HandHeart, FirstAid, Notebook,
  CalendarBlank, TrendUp, ArrowRight, CheckCircle, Clock
} from "@phosphor-icons/react";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts";

const MONTHS = ["","Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];

function StatCard({ label, value, icon: Icon, iconColor, sub, testId, trend }) {
  return (
    <div className="stat-card animate-fade-in" data-testid={testId}>
      <div className="flex items-start justify-between mb-3">
        <p className="text-xs font-semibold uppercase tracking-wide text-stone-500">{label}</p>
        <div className={`p-2 rounded-md ${iconColor}`}>
          <Icon size={18} weight="duotone" />
        </div>
      </div>
      <p className="text-2xl font-bold text-stone-900 font-heading">{value}</p>
      {sub && <p className="text-xs text-stone-500 mt-1">{sub}</p>}
      {trend && <p className="text-xs text-green-700 mt-1 flex items-center gap-1"><TrendUp size={12} />{trend}</p>}
    </div>
  );
}

export default function Dashboard() {
  const { user } = useAuth();
  const [stats, setStats] = useState(null);
  const [monthly, setMonthly] = useState([]);
  const [recent, setRecent] = useState({ recent_contributions: [], recent_benefits: [] });

  useEffect(() => {
    Promise.all([
      api.get("/dashboard/stats"),
      api.get("/dashboard/monthly-collections"),
      api.get("/dashboard/recent-activity"),
    ]).then(([s, m, r]) => {
      setStats(s.data);
      setMonthly(m.data);
      setRecent(r.data);
    }).catch(console.error);
  }, []);

  const fmt = (n) => new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 }).format(n || 0);

  if (!stats) return (
    <div className="p-8 flex items-center gap-2 text-stone-500">
      <div className="w-4 h-4 border-2 border-green-800 border-t-transparent rounded-full animate-spin" />
      Loading dashboard...
    </div>
  );

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="animate-fade-in">
        <h1 className="text-2xl font-bold text-stone-900 font-heading">
          Good {new Date().getHours() < 12 ? "morning" : new Date().getHours() < 17 ? "afternoon" : "evening"}, {user?.name?.split(" ")[0]}
        </h1>
        <p className="text-stone-500 text-sm mt-0.5">
          {MONTHS[stats.current_month]} {stats.current_year} — Here's the overview
        </p>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4" data-testid={DASHBOARD.statsGrid}>
        <StatCard
          label="Active Members" value={stats.total_members}
          icon={Users} iconColor="bg-green-50 text-green-700"
          sub={`${stats.total_all_members} total`}
          testId={DASHBOARD.totalMembers}
        />
        <StatCard
          label="Fund Balance" value={fmt(stats.fund_balance)}
          icon={Notebook} iconColor="bg-blue-50 text-blue-700"
          sub="Current balance"
          testId={DASHBOARD.fundBalance}
        />
        <StatCard
          label="Monthly Collection" value={fmt(stats.monthly_collection)}
          icon={CurrencyInr} iconColor="bg-amber-50 text-amber-700"
          sub={`${MONTHS[stats.current_month]} ${stats.current_year}`}
          testId={DASHBOARD.monthlyCollection}
        />
        <StatCard
          label="Pending Approvals"
          value={stats.pending_benefits + stats.pending_medical}
          icon={HandHeart} iconColor="bg-rose-50 text-rose-700"
          sub={`${stats.pending_benefits} benefits · ${stats.pending_medical} medical`}
          testId={DASHBOARD.pendingBenefits}
        />
      </div>

      {/* Second row stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          label="Benefits Paid" value={fmt(stats.total_benefits_paid)}
          icon={HandHeart} iconColor="bg-purple-50 text-purple-700"
          sub="All time"
        />
        <StatCard
          label="Medical Aid Paid" value={fmt(stats.total_medical_paid)}
          icon={FirstAid} iconColor="bg-red-50 text-red-700"
          sub="All time"
        />
        <StatCard
          label="Upcoming Meetings" value={stats.upcoming_meetings}
          icon={CalendarBlank} iconColor="bg-sky-50 text-sky-700"
          sub="Scheduled"
        />
        <StatCard
          label="Death Cases Pending" value={stats.pending_death}
          icon={CheckCircle} iconColor="bg-stone-100 text-stone-600"
          sub="Needs attention"
        />
      </div>

      {/* Charts + Recent Activity */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Monthly Collection Chart */}
        <div className="lg:col-span-2 bg-white border border-stone-200 rounded-lg p-5">
          <h3 className="font-semibold text-stone-900 font-heading mb-4 text-base">Monthly Collections ({stats.current_year})</h3>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={monthly} margin={{ top: 0, right: 0, bottom: 0, left: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f5f5f4" vertical={false} />
              <XAxis dataKey="month" tickFormatter={(m) => MONTHS[m]} tick={{ fontSize: 11, fill: "#78716c" }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fontSize: 11, fill: "#78716c" }} axisLine={false} tickLine={false} tickFormatter={(v) => `₹${v/1000}k`} />
              <Tooltip
                formatter={(v) => [`₹${v.toLocaleString("en-IN")}`, "Collection"]}
                labelFormatter={(m) => MONTHS[m]}
                contentStyle={{ border: "1px solid #e7e5e4", borderRadius: 6, fontSize: 12 }}
              />
              <Bar dataKey="total" fill="#166534" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Recent Activity */}
        <div className="bg-white border border-stone-200 rounded-lg p-5">
          <h3 className="font-semibold text-stone-900 font-heading mb-4 text-base flex items-center justify-between">
            Recent Activity
            <Clock size={14} className="text-stone-400" />
          </h3>
          <div className="space-y-3">
            {recent.recent_contributions.length === 0 && recent.recent_benefits.length === 0 && (
              <p className="text-sm text-stone-400 text-center py-4">No recent activity</p>
            )}
            {recent.recent_contributions.slice(0, 3).map((c) => (
              <div key={c.id} className="flex items-start gap-2.5">
                <div className="w-6 h-6 rounded-full bg-green-50 flex items-center justify-center flex-shrink-0 mt-0.5">
                  <CurrencyInr size={12} className="text-green-700" />
                </div>
                <div>
                  <p className="text-xs font-medium text-stone-700">Contribution ₹{c.amount}</p>
                  <p className="text-xs text-stone-400">{c.receipt_number} · {MONTHS[c.month]} {c.year}</p>
                </div>
              </div>
            ))}
            {recent.recent_benefits.slice(0, 3).map((b) => (
              <div key={b.id} className="flex items-start gap-2.5">
                <div className="w-6 h-6 rounded-full bg-amber-50 flex items-center justify-center flex-shrink-0 mt-0.5">
                  <HandHeart size={12} className="text-amber-700" />
                </div>
                <div>
                  <p className="text-xs font-medium text-stone-700">{b.benefit_type} benefit - {b.member_name}</p>
                  <p className="text-xs text-stone-400 capitalize">{b.status}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
