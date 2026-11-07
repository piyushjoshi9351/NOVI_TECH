"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import Gate from "@/Gate";
import { api } from "@/api";
import { ErrorNote, PageHeader, Pagination, StatusBadge, formatDate } from "@/views/admin/ui";

const PAGE_SIZE = 20;

export default function AdminAIMentorsPage() {
  return (
    <Gate requiredRole="admin">
      <AIMentorsTable />
    </Gate>
  );
}

function AIMentorsTable() {
  const [page, setPage] = useState(1);
  const [data, setData] = useState({ items: [], total: 0, pages: 0 });
  const [busy, setBusy] = useState(false);
  const [retryingId, setRetryingId] = useState(null);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setBusy(true);
    setError("");
    try {
      const result = await api(`/admin/ai-mentors?page=${page}&page_size=${PAGE_SIZE}`, { fresh: true });
      setData(result);
    } catch (ex) {
      setError(ex.message || "Could not load AI mentor statuses.");
    } finally {
      setBusy(false);
    }
  }, [page]);

  useEffect(() => { load(); }, [load]);

  async function retry(student) {
    setRetryingId(student.student_id);
    setError("");
    try {
      await api(`/admin/ai-mentors/${student.student_id}/retry`, { method: "POST" });
      await load();
    } catch (ex) {
      setError(ex.message || "Could not retry agent creation.");
    } finally {
      setRetryingId(null);
    }
  }

  return (
    <div className="admin-page">
      <PageHeader
        title="AI Mentors"
        subtitle={`${data.total} student account${data.total === 1 ? "" : "s"}. Status comes from the agent provisioning record, not only a non-null agent id.`}
      />
      <ErrorNote error={error} />

      <div className="admin-table-wrap">
        <table className="admin-table">
          <thead>
            <tr>
              <th>Student</th>
              <th>Email</th>
              <th>Agent id</th>
              <th>Status</th>
              <th>Attempts</th>
              <th>Last activity</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            {data.items.map((student) => (
              <tr key={student.student_id}>
                <td><Link href={`/admin/students/${student.student_id}`}>{student.name}</Link></td>
                <td>{student.email}</td>
                <td>{student.agent_id || "none"}</td>
                <td><StatusBadge status={student.status} /></td>
                <td>{student.attempts}</td>
                <td>{formatDate(student.updated_at)}</td>
                <td>
                  {student.status === "failed" ? (
                    <button
                      className="admin-btn"
                      disabled={retryingId === student.student_id}
                      onClick={() => retry(student)}
                    >
                      {retryingId === student.student_id ? "Retrying…" : "Retry"}
                    </button>
                  ) : <span className="admin-muted">—</span>}
                </td>
              </tr>
            ))}
            {data.items.length === 0 ? (
              <tr><td colSpan={7} className="admin-muted">{busy ? "Loading…" : "No students yet."}</td></tr>
            ) : null}
          </tbody>
        </table>
      </div>

      <Pagination page={page} pages={data.pages} onPage={setPage} busy={busy} />
    </div>
  );
}
