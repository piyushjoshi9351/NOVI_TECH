"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import Gate from "@/Gate";
import { api } from "@/api";
import { ActiveBadge, ErrorNote, PageHeader, Pagination, formatDate } from "@/views/admin/ui";

const PAGE_SIZE = 20;

export default function AdminStudentsPage() {
  return (
    <Gate requiredRole="admin">
      <StudentsTable />
    </Gate>
  );
}

function StudentsTable() {
  const [search, setSearch] = useState("");
  const [appliedSearch, setAppliedSearch] = useState("");
  const [page, setPage] = useState(1);
  const [data, setData] = useState({ items: [], total: 0, pages: 0 });
  const [busy, setBusy] = useState(false);
  const [actionId, setActionId] = useState(null);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setBusy(true);
    setError("");
    try {
      const result = await api(
        `/admin/students?search=${encodeURIComponent(appliedSearch)}&page=${page}&page_size=${PAGE_SIZE}`,
        { fresh: true },
      );
      setData(result);
    } catch (ex) {
      setError(ex.message || "Could not load students.");
    } finally {
      setBusy(false);
    }
  }, [appliedSearch, page]);

  useEffect(() => { load(); }, [load]);

  async function toggleActive(student) {
    setActionId(student.id);
    setError("");
    try {
      await api(`/admin/students/${student.id}/status`, {
        method: "PATCH",
        body: JSON.stringify({ is_active: !student.is_active }),
      });
      await load();
    } catch (ex) {
      setError(ex.message || "Could not update the student.");
    } finally {
      setActionId(null);
    }
  }

  return (
    <div className="admin-page">
      <PageHeader title="Students" subtitle={`${data.total} student account${data.total === 1 ? "" : "s"} in total.`} />

      <form
        className="admin-toolbar"
        onSubmit={(event) => {
          event.preventDefault();
          setPage(1);
          setAppliedSearch(search.trim());
        }}
      >
        <input
          className="admin-input"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder="Search name or email"
          aria-label="Search students"
        />
        <button className="admin-btn primary" type="submit" disabled={busy}>Search</button>
        {appliedSearch ? (
          <button
            className="admin-btn"
            type="button"
            onClick={() => { setSearch(""); setAppliedSearch(""); setPage(1); }}
          >
            Clear
          </button>
        ) : null}
      </form>

      <ErrorNote error={error} />

      <div className="admin-table-wrap">
        <table className="admin-table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Email</th>
              <th>Grade</th>
              <th>School</th>
              <th>Status</th>
              <th>Parent linked</th>
              <th>Registered</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            {data.items.map((student) => (
              <tr key={student.id}>
                <td><Link href={`/admin/students/${student.id}`}>{student.name}</Link></td>
                <td>{student.email}</td>
                <td>{student.grade ?? "—"}</td>
                <td>{student.school || "—"}</td>
                <td><ActiveBadge active={student.is_active} /></td>
                <td>{student.has_linked_parent ? "Yes" : "No"}</td>
                <td>{formatDate(student.created_at)}</td>
                <td>
                  <button
                    className={`admin-btn${student.is_active ? " danger" : ""}`}
                    disabled={actionId === student.id}
                    onClick={() => toggleActive(student)}
                  >
                    {actionId === student.id ? "Saving…" : student.is_active ? "Deactivate" : "Activate"}
                  </button>
                </td>
              </tr>
            ))}
            {data.items.length === 0 ? (
              <tr><td colSpan={8} className="admin-muted">{busy ? "Loading…" : "No students match this search."}</td></tr>
            ) : null}
          </tbody>
        </table>
      </div>

      <Pagination page={page} pages={data.pages} onPage={setPage} busy={busy} />
    </div>
  );
}
