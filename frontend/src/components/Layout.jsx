import { Outlet, NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import { useState } from "react";
import { useTheme } from "next-themes";
import {
  HouseLine, Users, CurrencyInr, HandHeart, FirstAid,
  Skull, Notebook, UsersThree, CalendarBlank, ChartBar,
  SignOut, List, UserGear, Bell, Scales, Sun, Moon, Gear
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
  { to: "/notifications",    label: "Notifications",   icon: Bell,          roles: ["super_admin","president","secretary","treasurer"] },
  { to: "/audit",            label: "Audit",           icon: Scales,        roles: ["super_admin","president","secretary","treasurer","auditor"] },
  { to: "/users",            label: "User Management", icon: UserGear,      roles: ["super_admin","secretary"] },
  { to: "/settings",         label: "Settings",        icon: Gear,          roles: ["super_admin","treasurer"] },
];

const ROLE_LABELS = {
  super_admin: "Super Admin", president: "President", secretary: "Secretary",
  treasurer: "Treasurer", committee_member: "Committee", auditor: "Auditor", member: "Member"
};

export default function Layout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [mobileOpen, setMobileOpen] = useState(false);
  const { resolvedTheme, setTheme } = useTheme();

  const visibleNav = NAV.filter(n => n.roles.includes(user?.role));

  const handleLogout = async () => {
    await logout();
    navigate("/login");
  };

  const toggleTheme = () => setTheme(resolvedTheme === "dark" ? "light" : "dark");

  const SidebarContent = () => (
    <div className="flex flex-col h-full">
      {/* Brand */}
      <div className="p-5 border-b border-border">
        <div className="flex items-center gap-2.5">
          <div className="w-10 h-10 bg-white rounded-lg flex items-center justify-center border border-border shadow-sm flex-shrink-0">
            <img src="/logo-icon.png" alt="Twenty20 Wariyad logo" className="w-8 h-8 object-contain" data-testid="sidebar-logo" />
          </div>
          <div>
            <div className="text-sm font-bold text-foreground leading-tight font-heading tracking-tight">Twenty20</div>
            <div className="text-[11px] uppercase tracking-[0.18em] text-muted-foreground">Wariyad</div>
          </div>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 p-3 overflow-y-auto" data-testid={LAYOUT.sidebar}>
        <p className="px-3 pt-1 pb-2 text-[10px] font-bold uppercase tracking-[0.2em] text-muted-foreground/70">Menu</p>
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
      <div className="p-4 border-t border-border">
        <div className="flex items-center justify-between" data-testid={LAYOUT.userMenu}>
          <div className="flex items-center gap-2.5 min-w-0">
            <div className="w-8 h-8 rounded-full bg-primary/15 text-primary flex items-center justify-center text-xs font-bold flex-shrink-0">
              {user?.name?.[0]?.toUpperCase()}
            </div>
            <div className="min-w-0">
              <p className="text-sm font-semibold text-foreground truncate leading-relaxed">{user?.name}</p>
              <p className="text-xs text-muted-foreground">{ROLE_LABELS[user?.role] || user?.role}</p>
            </div>
          </div>
          <button
            onClick={handleLogout}
            data-testid={AUTH.logoutButton}
            className="p-2 text-muted-foreground hover:text-destructive hover:bg-destructive/10 rounded-md transition-colors"
            title="Logout"
          >
            <SignOut size={16} />
          </button>
        </div>
      </div>
    </div>
  );

  return (
    <div className="flex h-screen bg-background overflow-hidden">
      {/* Desktop sidebar */}
      <aside className="hidden md:flex flex-col w-60 bg-card border-r border-border flex-shrink-0">
        <SidebarContent />
      </aside>

      {/* Mobile sidebar overlay */}
      {mobileOpen && (
        <div className="fixed inset-0 z-50 md:hidden">
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={() => setMobileOpen(false)} />
          <aside className="absolute left-0 top-0 bottom-0 w-64 bg-card shadow-xl animate-fade-in">
            <SidebarContent />
          </aside>
        </div>
      )}

      {/* Main content */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Top bar */}
        <header className="bg-background/80 backdrop-blur-xl border-b border-border px-4 md:px-6 py-3 flex items-center justify-between flex-shrink-0 z-10">
          <button
            className="md:hidden p-2 text-muted-foreground hover:bg-muted rounded-md transition-colors"
            onClick={() => setMobileOpen(true)}
            data-testid={LAYOUT.mobileMenuToggle}
          >
            <List size={20} />
          </button>
          <div className="flex items-center gap-2 md:hidden">
            <div className="w-7 h-7 bg-white rounded-md border border-border flex items-center justify-center">
              <img src="/logo-icon.png" alt="Twenty20 Wariyad logo" className="w-5.5 h-5.5 object-contain" style={{ width: 22, height: 22 }} />
            </div>
            <span className="text-sm font-bold text-foreground font-heading">Twenty20 Wariyad</span>
          </div>
          <div className="hidden md:block">
            <span className="text-sm text-muted-foreground">
              {new Date().toLocaleDateString("en-IN", { weekday: "long", year: "numeric", month: "long", day: "numeric" })}
            </span>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={toggleTheme}
              data-testid="theme-toggle-btn"
              className="p-2 text-muted-foreground hover:text-primary hover:bg-primary/10 rounded-md transition-colors"
              title={resolvedTheme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
            >
              {resolvedTheme === "dark" ? <Sun size={18} weight="duotone" /> : <Moon size={18} weight="duotone" />}
            </button>
            <div className="flex items-center gap-2">
              <div className="w-7 h-7 rounded-full bg-primary flex items-center justify-center text-primary-foreground text-xs font-bold">
                {user?.name?.[0]?.toUpperCase()}
              </div>
              <span className="hidden sm:block text-sm font-medium text-foreground">{user?.name}</span>
            </div>
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
