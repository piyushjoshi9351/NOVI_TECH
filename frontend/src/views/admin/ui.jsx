"use client";

export function formatDate(value) {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "—" : date.toLocaleString();
}

export function PageHeader({ title, subtitle, children }) {
  return (
    <div className="admin-head">
      <div>
        <h1 className="admin-title">{title}</h1>
        {subtitle ? <p className="admin-sub">{subtitle}</p> : null}
      </div>
      {children}
    </div>
  );
}

export function StatusBadge({ status }) {
  const key = String(status || "not_created");
  const label = key === "not_created" ? "Not created" : key.charAt(0).toUpperCase() + key.slice(1);
  return <span className={`admin-badge badge-${key}`}>{label}</span>;
}

export function ActiveBadge({ active }) {
  return (
    <span className={`admin-badge ${active ? "badge-active" : "badge-failed"}`}>
      {active ? "Active" : "Inactive"}
    </span>
  );
}

export function ErrorNote({ error }) {
  return error ? <p className="admin-error" role="alert">{error}</p> : null;
}

export function Pagination({ page, pages, onPage, busy }) {
  return (
    <div className="admin-pager">
      <button className="admin-btn" disabled={busy || page <= 1} onClick={() => onPage(page - 1)}>
        Previous
      </button>
      <span>Page {page} of {Math.max(pages, 1)}</span>
      <button className="admin-btn" disabled={busy || page >= pages} onClick={() => onPage(page + 1)}>
        Next
      </button>
    </div>
  );
}
