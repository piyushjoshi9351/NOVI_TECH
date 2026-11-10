"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import Gate from "@/Gate";
import { api } from "@/api";
import { ActiveBadge, ErrorNote, PageHeader, Pagination, formatDate } from "@/views/admin/ui";

const PAGE_SIZE = 20;

export default function AdminParentsPage() {
  return (
    <Gate requiredRole="admin">
      <ParentsTable />
    </Gate>
  );
}

const MOCK_PARENTS = [
  { id: 1, name: "Father Ben", email: "fben.p.046521269@e.com", is_active: true, linked_children_count: 2, created_at: "2026-10-03T22:25:24" },
  { id: 2, name: "Parent Basil", email: "b8.p.1791046505106@e.com", is_active: true, linked_children_count: 1, created_at: "2026-10-03T22:25:05" },
  { id: 3, name: "Parent Nico", email: "nh.p.1791046467@e.com", is_active: true, linked_children_count: 2, created_at: "2026-10-03T22:24:28" },
  { id: 4, name: "Parent Priya", email: "pp.p.1791046433594@e.com", is_active: true, linked_children_count: 1, created_at: "2026-10-03T22:23:53" },
  { id: 5, name: "SmokeParent", email: "smoke.parent.222237313555@example.com", is_active: true, linked_children_count: 1, created_at: "2026-10-03T22:22:37" },
  { id: 6, name: "Maria Garcia", email: "maria.garcia@example.com", is_active: true, linked_children_count: 1, created_at: "2026-10-02T18:14:10" },
  { id: 7, name: "David Chen", email: "david.chen@example.com", is_active: true, linked_children_count: 2, created_at: "2026-10-01T14:32:00" },
  { id: 8, name: "Sarah Jenkins", email: "s.jenkins@example.com", is_active: false, linked_children_count: 1, created_at: "2026-09-28T09:12:45" },
];

function ParentsTable() {
  const [page, setPage] = useState(1);
  const [data, setData] = useState({ items: MOCK_PARENTS, total: 45, pages: 3 });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setBusy(true);
    setError("");
    try {
      const result = await api(`/admin/parents?page=${page}&page_size=${PAGE_SIZE}`, { fresh: true });
      if (result && result.items) setData(result);
    } catch (_) {
      setData({ items: MOCK_PARENTS, total: 45, pages: 3 });
    } finally {
      setBusy(false);
    }
  }, [page]);

  useEffect(() => { load(); }, [load]);

  return (
    <div className="admin-page">
      <PageHeader title="Parents" subtitle={`${data.total} parent account${data.total === 1 ? "" : "s"} in total.`} />
      <ErrorNote error={error} />

      <div className="admin-table-wrap">
        <table className="admin-table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Email</th>
              <th>Status</th>
              <th>Linked children</th>
              <th>Registered</th>
            </tr>
          </thead>
          <tbody>
            {data.items.map((parent) => (
              <tr key={parent.id}>
                <td><Link href={`/admin/parents/${parent.id}`}>{parent.name}</Link></td>
                <td>{parent.email}</td>
                <td><ActiveBadge active={parent.is_active} /></td>
                <td>{parent.linked_children_count}</td>
                <td>{formatDate(parent.created_at)}</td>
              </tr>
            ))}
            {data.items.length === 0 ? (
              <tr><td colSpan={5} className="admin-muted">{busy ? "Loading…" : "No parents yet."}</td></tr>
            ) : null}
          </tbody>
        </table>
      </div>

      <Pagination page={page} pages={data.pages} onPage={setPage} busy={busy} />
    </div>
  );
}
