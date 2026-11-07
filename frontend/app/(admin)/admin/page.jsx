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

function AdminDashboard() {
  const [stats, setStats] = useState(null);
  const [recent, setRecent] = useState([]);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const [dashboard, students, parents] = await Promise.all([
          api("/admin/dashboard", { fresh: true }),
          api("/admin/students?page=1&page_size=5", { fresh: true }),
          api("/admin/parents?page=1&page_size=5", { fresh: true }),
        ]);
        if (cancelled) return;
        setStats(dashboard);
        const merged = [
          ...(students?.items || []).map((item) => ({ ...item, role: "student" })),
          ...(parents?.items || []).map((item) => ({ ...item, role: "parent" })),
        ];
        merged.sort((a, b) => new Date(b.created_at || 0) - new Date(a.created_at || 0));
        setRecent(merged.slice(0, 8));
      } catch (ex) {
        if (!cancelled) setError(ex.message || "Could not load the dashboard.");
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
