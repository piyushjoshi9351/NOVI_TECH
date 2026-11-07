"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import Gate from "@/Gate";
import { api } from "@/api";
import { ActiveBadge, ErrorNote, PageHeader, StatusBadge, formatDate } from "@/views/admin/ui";

export default function AdminStudentDetailPage() {
  return (
    <Gate requiredRole="admin">
      <StudentDetail />
    </Gate>
  );
}

function StudentDetail() {
  const { id } = useParams();
  const [student, setStudent] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const result = await api(`/admin/students/${id}`, { fresh: true });
        if (!cancelled) setStudent(result);
      } catch (ex) {
        if (!cancelled) setError(ex.message || "Could not load this student.");
      }
    }
    load();
    return () => { cancelled = true; };
  }, [id]);

  return (
    <div className="admin-page">
      <PageHeader title={student?.name || "Student"} subtitle="Account detail and linked parents.">
        <Link className="admin-btn" href="/admin/students">Back to students</Link>
      </PageHeader>
      <ErrorNote error={error} />

      {student ? (
        <>
          <div className="admin-detail-grid">
            <div className="admin-detail"><div className="k">Email</div><div className="v">{student.email}</div></div>
            <div className="admin-detail"><div className="k">Grade</div><div className="v">{student.grade ?? "—"}</div></div>
            <div className="admin-detail"><div className="k">School</div><div className="v">{student.school || "—"}</div></div>
            <div className="admin-detail"><div className="k">Status</div><div className="v"><ActiveBadge active={student.is_active} /></div></div>
            <div className="admin-detail"><div className="k">Registered</div><div className="v">{formatDate(student.created_at)}</div></div>
          </div>

          <section>
            <h2 className="admin-title" style={{ fontSize: 19 }}>Linked parents</h2>
            <p className="admin-sub">All parent-student links for this account, including pending or revoked history.</p>
            <div className="admin-table-wrap" style={{ marginTop: 12 }}>
              <table className="admin-table">
                <thead>
                  <tr><th>Name</th><th>Email</th><th>Link status</th><th>Linked</th></tr>
                </thead>
                <tbody>
                  {student.linked_parents.map((parent) => (
                    <tr key={parent.id}>
                      <td><Link href={`/admin/parents/${parent.id}`}>{parent.name}</Link></td>
                      <td>{parent.email}</td>
                      <td><StatusBadge status={parent.status} /></td>
                      <td>{formatDate(parent.linked_at)}</td>
                    </tr>
                  ))}
                  {student.linked_parents.length === 0 ? (
                    <tr><td colSpan={4} className="admin-muted">No parent links.</td></tr>
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
