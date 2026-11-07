"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import Gate from "@/Gate";
import { api } from "@/api";
import { ActiveBadge, ErrorNote, PageHeader, StatusBadge, formatDate } from "@/views/admin/ui";

export default function AdminParentDetailPage() {
  return (
    <Gate requiredRole="admin">
      <ParentDetail />
    </Gate>
  );
}

function ParentDetail() {
  const { id } = useParams();
  const [parent, setParent] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const result = await api(`/admin/parents/${id}`, { fresh: true });
        if (!cancelled) setParent(result);
      } catch (ex) {
        if (!cancelled) setError(ex.message || "Could not load this parent.");
      }
    }
    load();
    return () => { cancelled = true; };
  }, [id]);

  return (
    <div className="admin-page">
      <PageHeader title={parent?.name || "Parent"} subtitle="Account detail and linked children.">
        <Link className="admin-btn" href="/admin/parents">Back to parents</Link>
      </PageHeader>
      <ErrorNote error={error} />

      {parent ? (
        <>
          <div className="admin-detail-grid">
            <div className="admin-detail"><div className="k">Email</div><div className="v">{parent.email}</div></div>
            <div className="admin-detail"><div className="k">Status</div><div className="v"><ActiveBadge active={parent.is_active} /></div></div>
            <div className="admin-detail"><div className="k">Linked children</div><div className="v">{parent.linked_children_count}</div></div>
            <div className="admin-detail"><div className="k">Registered</div><div className="v">{formatDate(parent.created_at)}</div></div>
          </div>

          <section>
            <h2 className="admin-title" style={{ fontSize: 19 }}>Linked children</h2>
            <p className="admin-sub">All parent-student links for this account, including pending or revoked history.</p>
            <div className="admin-table-wrap" style={{ marginTop: 12 }}>
              <table className="admin-table">
                <thead>
                  <tr><th>Name</th><th>Email</th><th>Grade</th><th>Link status</th><th>Linked</th></tr>
                </thead>
                <tbody>
                  {parent.linked_children.map((child) => (
                    <tr key={child.id}>
                      <td><Link href={`/admin/students/${child.id}`}>{child.name}</Link></td>
                      <td>{child.email}</td>
                      <td>{child.grade ?? "—"}</td>
                      <td><StatusBadge status={child.status} /></td>
                      <td>{formatDate(child.linked_at)}</td>
                    </tr>
                  ))}
                  {parent.linked_children.length === 0 ? (
                    <tr><td colSpan={5} className="admin-muted">No child links.</td></tr>
                  ) : null}
                </tbody>
              </table>
            </div>
          </section>
        </>
      ) : !error ? <p className="admin-muted">Loading…</p> : null}
    </div>
  );
}
