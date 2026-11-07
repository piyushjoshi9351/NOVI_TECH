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

function ParentsTable() {
  const [page, setPage] = useState(1);
  const [data, setData] = useState({ items: [], total: 0, pages: 0 });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setBusy(true);
    setError("");
    try {
      const result = await api(`/admin/parents?page=${page}&page_size=${PAGE_SIZE}`, { fresh: true });
      setData(result);
    } catch (ex) {
      setError(ex.message || "Could not load parents.");
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
