"use client";

import { Suspense } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Bot, GraduationCap, LayoutDashboard, LogOut, Users } from "lucide-react";
import Gate from "@/Gate";
import { useAuth } from "@/auth";
import "../../../static/styles.css";
import "@/views/admin/admin.css";

const adminNav = [
  ["/admin", "Dashboard", LayoutDashboard],
  ["/admin/students", "Students", GraduationCap],
  ["/admin/parents", "Parents", Users],
  ["/admin/ai-mentors", "AI Mentors", Bot],
];

function AdminShell({ children }) {
  const pathname = usePathname();
  const { user, logout } = useAuth();
  const name = user?.first_name || user?.email || "Admin";

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-copy">
            <span className="brand-name">NOVI</span>
            <span className="brand-tag">Admin Console</span>
          </span>
        </div>

        <nav className="nav">
          {adminNav.map(([href, label, Icon]) => {
            const active = href === "/admin" ? pathname === href : pathname.startsWith(`${href}/`) || pathname === href;
            return (
              <Link key={href} href={href} className={active ? "active" : ""}>
                <Icon className="nav-ico" size={18} strokeWidth={2} />
                <span className="nav-label">{label}</span>
              </Link>
            );
          })}
        </nav>

        <div className="sidebar-foot">
          <div className="sidebar-user">
            <b>{name}</b>
          </div>
          <div className="sidebar-actions">
            <button className="logout-btn" onClick={logout}>
              <LogOut size={16} strokeWidth={2} />
              <span>Logout</span>
            </button>
          </div>
        </div>
      </aside>

      <main className="view">{children}</main>
    </div>
  );
}

export default function AdminLayout({ children }) {
  return (
    <Suspense fallback={<p role="status">Loading admin console…</p>}>
      <Gate requiredRole="admin">
        <AdminShell>{children}</AdminShell>
      </Gate>
    </Suspense>
  );
}
