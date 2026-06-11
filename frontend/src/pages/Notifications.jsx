import { useState } from "react";
import api from "@/utils/api";
import { useAuth } from "@/contexts/AuthContext";
import { Bell, Warning, CheckCircle, PaperPlaneTilt, Users, Phone } from "@phosphor-icons/react";

const MONTHS = ["","January","February","March","April","May","June",
                "July","August","September","October","November","December"];

export default function Notifications() {
  const { user } = useAuth();
  const now = new Date();
  const [month, setMonth] = useState(now.getMonth() + 1);
  const [year, setYear] = useState(now.getFullYear());
  const [defaulters, setDefaulters] = useState(null);
  const [loading, setLoading] = useState(false);
  const [sendLoading, setSendLoading] = useState(false);
  const [sendResult, setSendResult] = useState(null);
  const [customMsg, setCustomMsg] = useState("");

  const years = Array.from({ length: 5 }, (_, i) => now.getFullYear() - i);

  const fetchDefaulters = async () => {
    setLoading(true);
    setSendResult(null);
    setDefaulters(null);
    try {
      const res = await api.get(`/notifications/defaulters?month=${month}&year=${year}`);
      setDefaulters(res.data);
    } catch (err) {
      alert("Failed to fetch defaulters");
    } finally {
      setLoading(false);
    }
  };

  const handleSend = async () => {
    if (!defaulters || defaulters.total_defaulters === 0) return;
    const confirmed = window.confirm(
      `Send ${defaulters.twilio_enabled ? "SMS & WhatsApp" : "mock"} reminders to ${defaulters.total_defaulters} defaulters for ${MONTHS[month]} ${year}?`
    );
    if (!confirmed) return;
    setSendLoading(true);
    try {
      const res = await api.post("/notifications/send-reminders", {
        month, year,
        message: customMsg.trim() || null,
      });
      setSendResult(res.data);
    } catch (err) {
      alert("Failed to send reminders");
    } finally {
      setSendLoading(false);
    }
  };

  const canAccess = ["super_admin", "president", "secretary", "treasurer"].includes(user?.role);
  if (!canAccess) {
    return (
      <div className="p-8 text-center text-stone-500">
        You do not have permission to access this page.
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6 max-w-4xl mx-auto">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-stone-900 font-heading flex items-center gap-2">
          <Bell size={24} weight="duotone" className="text-green-700" />
          Notifications
        </h1>
        <p className="text-stone-500 text-sm mt-0.5">
          Send monthly contribution reminders to defaulters via SMS & WhatsApp
        </p>
      </div>

      {/* Controls */}
      <div className="bg-white border border-stone-200 rounded-lg p-5 space-y-4">
        <h3 className="font-semibold text-stone-900 font-heading text-sm uppercase tracking-wide">
          Check Defaulters
        </h3>
        <div className="flex flex-wrap items-end gap-3">
          <div className="space-y-1">
            <label className="text-xs font-medium text-stone-500 uppercase tracking-wide">Month</label>
            <select
              value={month}
              onChange={e => setMonth(+e.target.value)}
              data-testid="notif-month-select"
              className="border border-stone-300 rounded-md px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-green-700/30"
            >
              {MONTHS.slice(1).map((m, i) => (
                <option key={i + 1} value={i + 1}>{m}</option>
              ))}
            </select>
          </div>
          <div className="space-y-1">
            <label className="text-xs font-medium text-stone-500 uppercase tracking-wide">Year</label>
            <select
              value={year}
              onChange={e => setYear(+e.target.value)}
              data-testid="notif-year-select"
              className="border border-stone-300 rounded-md px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-green-700/30"
            >
              {years.map(y => <option key={y} value={y}>{y}</option>)}
            </select>
          </div>
          <button
            onClick={fetchDefaulters}
            disabled={loading}
            data-testid="check-defaulters-btn"
            className="px-4 py-2 bg-green-800 text-white text-sm font-medium rounded-md hover:bg-green-900 disabled:opacity-50 transition-colors flex items-center gap-2"
          >
            <Users size={16} />
            {loading ? "Checking..." : "Check Defaulters"}
          </button>
        </div>
      </div>

      {/* Defaulters Result */}
      {defaulters && (
        <div className="bg-white border border-stone-200 rounded-lg p-5 space-y-4" data-testid="defaulters-result">
          {/* Stats row */}
          <div className="grid grid-cols-3 gap-3">
            <div className="bg-stone-50 rounded-md p-3 text-center">
              <p className="text-xs font-semibold uppercase tracking-wide text-stone-500">Active Members</p>
              <p className="text-2xl font-bold text-stone-900 font-heading">{defaulters.total_active}</p>
            </div>
            <div className="bg-green-50 rounded-md p-3 text-center">
              <p className="text-xs font-semibold uppercase tracking-wide text-green-700">Paid</p>
              <p className="text-2xl font-bold text-green-800 font-heading">{defaulters.total_paid}</p>
            </div>
            <div className="bg-red-50 rounded-md p-3 text-center">
              <p className="text-xs font-semibold uppercase tracking-wide text-red-600">Defaulters</p>
              <p className="text-2xl font-bold text-red-700 font-heading">{defaulters.total_defaulters}</p>
            </div>
          </div>

          {/* Twilio mode badge */}
          <div className={`flex items-center gap-2 px-3 py-2 rounded-md text-xs font-medium border ${
            defaulters.twilio_enabled
              ? "bg-green-50 border-green-200 text-green-800"
              : "bg-amber-50 border-amber-200 text-amber-800"
          }`}>
            {defaulters.twilio_enabled ? (
              <><CheckCircle size={14} weight="fill" /> Twilio configured — real SMS & WhatsApp will be sent</>
            ) : (
              <><Warning size={14} weight="fill" /> Twilio not configured — running in mock mode (messages will be logged, not sent). Add credentials to backend/.env to enable real sending.</>
            )}
          </div>

          {/* Defaulters list */}
          {defaulters.total_defaulters > 0 ? (
            <>
              <div className="space-y-1">
                <h4 className="text-sm font-semibold text-stone-700">
                  Defaulters for {MONTHS[defaulters.month]} {defaulters.year}
                </h4>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm" data-testid="defaulters-table">
                    <thead>
                      <tr className="border-b border-stone-200">
                        <th className="text-left py-2 px-3 text-xs font-semibold uppercase tracking-wide text-stone-500">Member ID</th>
                        <th className="text-left py-2 px-3 text-xs font-semibold uppercase tracking-wide text-stone-500">Name</th>
                        <th className="text-left py-2 px-3 text-xs font-semibold uppercase tracking-wide text-stone-500">Mobile</th>
                      </tr>
                    </thead>
                    <tbody>
                      {defaulters.defaulters.map((d) => (
                        <tr key={d.member_id} className="border-b border-stone-100 hover:bg-stone-50">
                          <td className="py-2 px-3 font-mono text-xs text-stone-500">{d.member_code}</td>
                          <td className="py-2 px-3 font-medium text-stone-900">{d.name}</td>
                          <td className="py-2 px-3 text-stone-600 flex items-center gap-1">
                            <Phone size={12} /> {d.mobile || "—"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Custom message */}
              <div className="space-y-1.5">
                <label className="text-xs font-medium text-stone-500 uppercase tracking-wide">
                  Custom Message (optional — leave blank for default)
                </label>
                <textarea
                  value={customMsg}
                  onChange={e => setCustomMsg(e.target.value)}
                  data-testid="custom-message-input"
                  rows={3}
                  placeholder="Dear Member, your monthly contribution of Rs.100 for ... is pending."
                  className="w-full border border-stone-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-700/30 resize-none"
                />
              </div>

              <button
                onClick={handleSend}
                disabled={sendLoading}
                data-testid="send-reminders-btn"
                className="px-5 py-2.5 bg-green-800 text-white text-sm font-medium rounded-md hover:bg-green-900 disabled:opacity-50 transition-colors flex items-center gap-2"
              >
                <PaperPlaneTilt size={16} />
                {sendLoading ? "Sending..." : `Send Reminders to ${defaulters.total_defaulters} Defaulters`}
              </button>
            </>
          ) : (
            <div className="flex items-center gap-3 bg-green-50 border border-green-200 rounded-md p-4">
              <CheckCircle size={20} weight="fill" className="text-green-700" />
              <p className="text-sm text-green-800 font-medium">
                All active members have paid for {MONTHS[defaulters.month]} {defaulters.year}.
              </p>
            </div>
          )}
        </div>
      )}

      {/* Send Result */}
      {sendResult && (
        <div className="bg-white border border-stone-200 rounded-lg p-5 space-y-3" data-testid="send-result">
          <div className={`flex items-start gap-3 p-3 rounded-md border ${
            sendResult.mode === "live" ? "bg-green-50 border-green-200" : "bg-amber-50 border-amber-200"
          }`}>
            {sendResult.mode === "live"
              ? <CheckCircle size={18} weight="fill" className="text-green-700 mt-0.5 flex-shrink-0" />
              : <Warning size={18} weight="fill" className="text-amber-600 mt-0.5 flex-shrink-0" />
            }
            <p className="text-sm font-medium text-stone-800">{sendResult.message}</p>
          </div>

          {sendResult.results && sendResult.results.length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b border-stone-200">
                    <th className="text-left py-1.5 px-2 font-semibold text-stone-500">Member</th>
                    <th className="text-left py-1.5 px-2 font-semibold text-stone-500">Phone</th>
                    <th className="text-center py-1.5 px-2 font-semibold text-stone-500">SMS</th>
                    <th className="text-center py-1.5 px-2 font-semibold text-stone-500">WhatsApp</th>
                  </tr>
                </thead>
                <tbody>
                  {sendResult.results.map((r, i) => (
                    <tr key={i} className="border-b border-stone-100">
                      <td className="py-1.5 px-2 font-medium">{r.member}</td>
                      <td className="py-1.5 px-2 text-stone-500">{r.phone}</td>
                      <td className="py-1.5 px-2 text-center">
                        <span className={`px-1.5 py-0.5 rounded text-xs font-medium ${
                          r.sms === "sent" ? "bg-green-100 text-green-700" :
                          r.sms === "mock" ? "bg-amber-100 text-amber-700" :
                          "bg-red-100 text-red-700"
                        }`}>{r.sms}</span>
                      </td>
                      <td className="py-1.5 px-2 text-center">
                        <span className={`px-1.5 py-0.5 rounded text-xs font-medium ${
                          r.whatsapp === "sent" ? "bg-green-100 text-green-700" :
                          r.whatsapp === "mock" ? "bg-amber-100 text-amber-700" :
                          "bg-red-100 text-red-700"
                        }`}>{r.whatsapp}</span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
