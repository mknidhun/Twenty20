import { Outlet, NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import { useState } from "react";
import {
  HouseLine, Users, CurrencyInr, HandHeart, FirstAid,
  Skull, Notebook, UsersThree, CalendarBlank, ChartBar,
  SignOut, List, X, UserGear, ShieldStar
} from "@phosphor-icons/react";
import { LAYOUT, AUTH } from "@/constants/testIds";

const NAV = [
  { to: "/dashboard",        label: "Dashboard",       icon: HouseLine,     roles: ["super_admin","president","secretary","treasurer","committee_member","auditor","member"] },
  { to: "/members",          label: "Members",         icon: Users,         roles: ["super_admin","president","secretary","treasurer","committee_member","auditor"] },
  { to: "/contributions",    label: "Contributions",   icon: CurrencyInr,   roles: ["super_admin","treasurer","member"] },
  { to: "/benefits",         label: "Benefits",        icon: HandHeart,     roles: ["super_admin","president","secretary","treasurer","committee_member","member"] },
  { to: "/medical-aid",      label: "Medical Aid",     icon: FirstAid,      roles: ["super_admin","president","secretary","committee_member","member"] },
  { to: "/death-assistance", label: "Death Assistance",icon: Skull,         roles: ["super_admin","president","secretary","committee_member","treasurer"] },
  { to: "/financials",       label: "Cashbook",        icon: Notebook,      roles: ["super_admin","president","treasurer","auditor"] },
  { to: "/committee",        label: "Committee",       icon: UsersThree,    roles: ["super_admin","president","secretary"] },
  { to: "/meetings",         label: "Meetings",        icon: CalendarBlank, roles: ["super_admin","president","secretary","committee_member"] },
  { to: "/reports",          label: "Reports",         icon: ChartBar,      roles: ["super_admin","president","treasurer","secretary","auditor"] },
  { to: "/users",            label: "User Management", icon: UserGear,      roles: ["super_admin","secretary"] },
];

const ROLE_LABELS = {
  super_admin: "Super Admin", president: "President", secretary: "Secretary",
  treasurer: "Treasurer", committee_member: "Committee", auditor: "Auditor", member: "Member"
};

export default function Layout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [mobileOpen, setMobileOpen] = useState(false);

  const visibleNav = NAV.filter(n => n.roles.includes(user?.role));

  const handleLogout = async () => {
    await logout();
    navigate("/login");
  };

  const SidebarContent = () => (
    <div className="flex flex-col h-full">
      {/* Brand */}
      <div className="p-5 border-b border-stone-100">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 bg-green-800 rounded-md flex items-center justify-center">
            <ShieldStar size={18} weight="fill" color="white" />
          </div>
          <div>
            <div className="text-sm font-bold text-stone-900 leading-tight font-heading">Twenty20</div>
            <div className="text-xs text-stone-500">Wariyad</div>
          </div>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 p-3 overflow-y-auto" data-testid={LAYOUT.sidebar}>
        <div className="space-y-0.5">
          {visibleNav.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              onClick={() => setMobileOpen(false)}
              className={({ isActive }) => `sidebar-link ${isActive ? "active" : ""}`}
            >
              <Icon size={18} weight="duotone" className="sidebar-icon flex-shrink-0" />
              <span>{label}</span>
            </NavLink>
          ))}
        </div>
      </nav>

      {/* User section */}
      <div className="p-4 border-t border-stone-100">
        <div className="flex items-center justify-between" data-testid={LAYOUT.userMenu}>
          <div className="min-w-0">
            <p className="text-sm font-semibold text-stone-800 truncate">{user?.name}</p>
            <p className="text-xs text-stone-500">{ROLE_LABELS[user?.role] || user?.role}</p>
          </div>
          <button
            onClick={handleLogout}
            data-testid={AUTH.logoutButton}
            className="p-2 text-stone-400 hover:text-red-600 hover:bg-red-50 rounded-md transition-colors"
            title="Logout"
          >
            <SignOut size={16} />
          </button>
        </div>
      </div>
    </div>
  );

  return (
    <div className="flex h-screen bg-stone-50 overflow-hidden">
      {/* Desktop sidebar */}
      <aside className="hidden md:flex flex-col w-56 bg-white border-r border-stone-200 flex-shrink-0">
        <SidebarContent />
      </aside>

      {/* Mobile sidebar overlay */}
      {mobileOpen && (
        <div className="fixed inset-0 z-50 md:hidden">
          <div className="absolute inset-0 bg-stone-900/40" onClick={() => setMobileOpen(false)} />
          <aside className="absolute left-0 top-0 bottom-0 w-64 bg-white shadow-xl">
            <SidebarContent />
          </aside>
        </div>
      )}

      {/* Main content */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Top bar */}
        <header className="bg-white border-b border-stone-200 px-4 md:px-6 py-3 flex items-center justify-between flex-shrink-0">
          <button
            className="md:hidden p-2 text-stone-600 hover:bg-stone-100 rounded-md"
            onClick={() => setMobileOpen(true)}
            data-testid={LAYOUT.mobileMenuToggle}
          >
            <List size={20} />
          </button>
          <div className="flex items-center gap-2 md:hidden">
            <div className="w-6 h-6 bg-green-800 rounded flex items-center justify-center">
              <ShieldStar size={14} weight="fill" color="white" />
            </div>
            <span className="text-sm font-bold text-stone-800">Twenty20 Wariyad</span>
          </div>
          <div className="hidden md:block">
            <span className="text-sm text-stone-500">
              {new Date().toLocaleDateString("en-IN", { weekday: "long", year: "numeric", month: "long", day: "numeric" })}
            </span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-full bg-green-800 flex items-center justify-center text-white text-xs font-bold">
              {user?.name?.[0]?.toUpperCase()}
            </div>
            <span className="hidden sm:block text-sm font-medium text-stone-700">{user?.name}</span>
          </div>
        </header>

        {/* Page content */}
        <main className="flex-1 overflow-y-auto">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
