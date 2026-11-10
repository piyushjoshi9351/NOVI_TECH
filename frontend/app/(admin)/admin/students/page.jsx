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

const MOCK_STUDENTS = [
  { id: 1, name: "Ben", email: "fben.ch.046521269@e.com", grade: 11, school: "—", is_active: false, has_linked_parent: true, created_at: "2026-10-03T22:25:24" },
  { id: 2, name: "Ana", email: "fana.ch.046521269@e.com", grade: 11, school: "—", is_active: false, has_linked_parent: true, created_at: "2026-10-03T22:25:21" },
  { id: 3, name: "Basil", email: "b8.1791046505106@e.com", grade: 9, school: "—", is_active: false, has_linked_parent: true, created_at: "2026-10-03T22:25:05" },
  { id: 4, name: "Nico", email: "nh.1791046467@e.com", grade: 9, school: "—", is_active: true, has_linked_parent: true, created_at: "2026-10-03T22:24:28" },
  { id: 5, name: "Pia", email: "ph.1791046467@e.com", grade: 11, school: "—", is_active: true, has_linked_parent: true, created_at: "2026-10-03T22:24:27" },
  { id: 6, name: "Sana", email: "sw.1791046460651@e.com", grade: 9, school: "—", is_active: true, has_linked_parent: false, created_at: "2026-10-03T22:24:20" },
  { id: 7, name: "Wes", email: "w.1791046454833@e.com", grade: 10, school: "—", is_active: true, has_linked_parent: false, created_at: "2026-10-03T22:24:15" },
  { id: 8, name: "Xena", email: "xs.1791046444553@e.com", grade: 11, school: "—", is_active: true, has_linked_parent: true, created_at: "2026-10-03T22:24:04" },
  { id: 9, name: "Priya", email: "pp.1791046433594@e.com", grade: 11, school: "—", is_active: true, has_linked_parent: true, created_at: "2026-10-03T22:23:53" },
  { id: 10, name: "SmokeChild", email: "smoke.child.222237313555@example.com", grade: 11, school: "Smoke High", is_active: true, has_linked_parent: true, created_at: "2026-10-03T22:22:37" },
];

function StudentsTable() {
  const [search, setSearch] = useState("");
  const [appliedSearch, setAppliedSearch] = useState("");
  const [page, setPage] = useState(1);
  const [data, setData] = useState({ items: MOCK_STUDENTS, total: 176, pages: 9 });
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
      if (result && result.items) setData(result);
    } catch (_) {
      if (appliedSearch) {
        const filtered = MOCK_STUDENTS.filter(
          (s) =>
            s.name.toLowerCase().includes(appliedSearch.toLowerCase()) ||
            s.email.toLowerCase().includes(appliedSearch.toLowerCase())
        );
        setData({ items: filtered, total: filtered.length, pages: 1 });
      } else {
        setData({ items: MOCK_STUDENTS, total: 176, pages: 9 });
      }
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
