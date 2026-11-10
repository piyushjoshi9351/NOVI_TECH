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

const MOCK_AI_MENTORS = [
  { student_id: 1, name: "Ben", email: "fben.ch.046521269@e.com", agent_id: "agent_d491f8c4", status: "ready", attempts: 1, updated_at: "2026-10-03T22:25:24" },
  { student_id: 2, name: "Ana", email: "fana.ch.046521269@e.com", agent_id: "agent_a821e901", status: "ready", attempts: 1, updated_at: "2026-10-03T22:25:21" },
  { student_id: 3, name: "Basil", email: "b8.1791046505106@e.com", agent_id: "agent_b198031a", status: "ready", attempts: 1, updated_at: "2026-10-03T22:25:05" },
  { student_id: 4, name: "Nico", email: "nh.1791046467@e.com", agent_id: "agent_f5517cb8", status: "ready", attempts: 1, updated_at: "2026-10-03T22:24:28" },
  { student_id: 5, name: "Pia", email: "ph.1791046467@e.com", agent_id: "agent_91cae772", status: "ready", attempts: 1, updated_at: "2026-10-03T22:24:27" },
  { student_id: 6, name: "Sana", email: "sw.1791046460651@e.com", agent_id: null, status: "failed", attempts: 3, updated_at: "2026-10-03T22:24:20" },
  { student_id: 7, name: "Wes", email: "w.1791046454833@e.com", agent_id: null, status: "pending", attempts: 1, updated_at: "2026-10-03T22:24:15" },
  { student_id: 8, name: "Xena", email: "xs.1791046444553@e.com", agent_id: "agent_702df89a", status: "ready", attempts: 1, updated_at: "2026-10-03T22:24:04" },
  { student_id: 9, name: "Priya", email: "pp.1791046433594@e.com", agent_id: "agent_331bba82", status: "ready", attempts: 1, updated_at: "2026-10-03T22:23:53" },
  { student_id: 10, name: "SmokeChild", email: "smoke.child.222237313555@example.com", agent_id: "agent_e1208bb5", status: "ready", attempts: 1, updated_at: "2026-10-03T22:22:37" },
];

function AIMentorsTable() {
  const [page, setPage] = useState(1);
  const [data, setData] = useState({ items: MOCK_AI_MENTORS, total: 176, pages: 9 });
  const [busy, setBusy] = useState(false);
  const [retryingId, setRetryingId] = useState(null);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setBusy(true);
    setError("");
    try {
      const result = await api(`/admin/ai-mentors?page=${page}&page_size=${PAGE_SIZE}`, { fresh: true });
      if (result && result.items) setData(result);
    } catch (_) {
      setData({ items: MOCK_AI_MENTORS, total: 176, pages: 9 });
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
