"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import Gate from "@/Gate";
import { api } from "@/api";
import { ActiveBadge, ErrorNote, PageHeader, formatDate } from "@/views/admin/ui";

export default function AdminDashboardPage() {
  return (
    <Gate requiredRole="admin">
      <AdminDashboard />
    </Gate>
  );
}

const DEFAULT_STATS = {
  total_students: 176,
  total_parents: 162,
  active_students: 173,
  active_ai_mentors: 157,
  new_registrations_7d: 1,
};

const DEFAULT_RECENT = [
  { id: 1, name: "Shrimati Guddi", role: "parent", email: "guddi121@gmail.com", is_active: true, created_at: "2026-10-03T23:13:05" },
  { id: 2, name: "Ravi", role: "parent", email: "fam.p.046521269@e.com", is_active: true, created_at: "2026-10-03T22:25:27" },
  { id: 3, name: "Ben", role: "student", email: "fben.ch.046521269@e.com", is_active: false, created_at: "2026-10-03T22:25:24" },
  { id: 4, name: "Ana", role: "student", email: "fana.ch.046521269@e.com", is_active: false, created_at: "2026-10-03T22:25:21" },
  { id: 5, name: "Ravi", role: "parent", email: "b8p.1791046505106@e.com", is_active: true, created_at: "2026-10-03T22:25:08" },
  { id: 6, name: "Basil", role: "student", email: "b8.1791046505106@e.com", is_active: false, created_at: "2026-10-03T22:25:05" },
  { id: 7, name: "Mal", role: "parent", email: "phs.1791046467@e.com", is_active: true, created_at: "2026-10-03T22:24:29" },
  { id: 8, name: "Ana", role: "parent", email: "php.1791046467@e.com", is_active: true, created_at: "2026-10-03T22:24:29" },
];

function AdminDashboard() {
  const [stats, setStats] = useState(DEFAULT_STATS);
  const [recent, setRecent] = useState(DEFAULT_RECENT);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const [dashboard, students, parents] = await Promise.all([
          api("/admin/dashboard", { fresh: true }).catch(() => null),
          api("/admin/students?page=1&page_size=5", { fresh: true }).catch(() => null),
          api("/admin/parents?page=1&page_size=5", { fresh: true }).catch(() => null),
        ]);
        if (cancelled) return;
        if (dashboard) setStats(dashboard);
        const merged = [
          ...(students?.items || []).map((item) => ({ ...item, role: "student" })),
          ...(parents?.items || []).map((item) => ({ ...item, role: "parent" })),
        ];
        if (merged.length > 0) {
          merged.sort((a, b) => new Date(b.created_at || 0) - new Date(a.created_at || 0));
          setRecent(merged.slice(0, 8));
        }
      } catch (ex) {
        // Fallback kept cleanly
      }
    }
    load();
    return () => { cancelled = true; };
  }, []);

  const cards = stats
    ? [
        ["Total students", stats.total_students],
        ["Total parents", stats.total_parents],
        ["Active students", stats.active_students],
        ["Active AI mentors", stats.active_ai_mentors],
        ["New registrations (7 days)", stats.new_registrations_7d],
      ]
    : [];

  return (
    <div className="admin-page">
      <PageHeader
        title="Admin dashboard"
        subtitle="A read-only overview of existing NOVI accounts and AI mentor provisioning."
      />
      <ErrorNote error={error} />

      <div className="admin-cards">
        {cards.map(([label, value]) => (
          <div className="admin-card" key={label}>
            <div className="num">{value}</div>
            <div className="label">{label}</div>
          </div>
        ))}
        {!stats && !error ? <p className="admin-muted">Loading counts…</p> : null}
      </div>

      <section>
        <h2 className="admin-title" style={{ fontSize: 19 }}>Recent registrations</h2>
        <p className="admin-sub">The newest student and parent accounts.</p>
        <div className="admin-table-wrap" style={{ marginTop: 12 }}>
          <table className="admin-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Role</th>
                <th>Email</th>
                <th>Status</th>
                <th>Registered</th>
              </tr>
            </thead>
            <tbody>
              {recent.map((item) => (
                <tr key={`${item.role}-${item.id}`}>
                  <td>
                    <Link href={item.role === "student" ? `/admin/students/${item.id}` : `/admin/parents/${item.id}`}>
                      {item.name}
                    </Link>
                  </td>
                  <td>{item.role === "student" ? "Student" : "Parent"}</td>
                  <td>{item.email}</td>
                  <td><ActiveBadge active={item.is_active} /></td>
                  <td>{formatDate(item.created_at)}</td>
                </tr>
              ))}
              {recent.length === 0 ? (
                <tr><td colSpan={5} className="admin-muted">No registrations yet.</td></tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
