import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { api, esc } from "../../api";
import { useAuth } from "../../auth";
import {
  STATUS_LABEL,
  STATUS_TONE,
  isActive,
  isPending,
  isRevoked,
  linkName,
  pendingHeadline,
  scopeMeta,
} from "../../parentAccess";
import { EmptyState, Pill, showLoader } from "../../ui";
import { ParentAvatar } from "./ParentAvatar";

/**
 * Parent dashboard — every student this parent has a link to, with the ones
 * still awaiting consent shown as pending rather than hidden. Nothing about a
 * student is fetched until the backend confirms an ACTIVE link.
 */
export default function ParentDashboard() {
  const { user } = useAuth();
  const [links, setLinks] = useState(null);
  const [error, setError] = useState(null);
  const load = useCallback(async () => {
    const d = await api("/parent/students");
    setLinks(d?.links || []);
  }, []);

  useEffect(() => {
    let alive = true;
    showLoader(true);
    load()
      .catch((ex) => { if (alive) setError(ex.message); })
      .finally(() => showLoader(false));
    return () => { alive = false; };
  }, [load]);

  if (error) return <EmptyState title="Parent area unavailable" sub={error} />;
  if (!links) return null;

  const active = links.filter(isActive);
  const pending = links.filter(isPending);
  const revoked = links.filter(isRevoked);
  const firstName = (user?.first_name || "").trim();

  const total = active.length + pending.length + revoked.length;

  return (
    <div className="dash-wrap pd-wrap">
      <div className="dash-top">
        <div className="dash-intro">
          <div className="dash-kick">Parent space</div>
          <h1 className="dash-hi">{firstName ? `Hello, ${esc(firstName)}` : "Your children"}</h1>
          <p className="dash-sub">
            A calm view of where things stand — goals, strengths and progress. Your child
            controls what appears here, section by section, and can change it at any time.
          </p>
        </div>
        <div className="dash-tools">
          <Link className="btn" href="/parent/add-child">Add child</Link>
        </div>
      </div>

      <nav className="pd-tabs" aria-label="Parent sections">
        <Link href="/parent" className="pd-tab on" aria-current="page">Your children{total ? ` (${total})` : ""}</Link>
        <Link href="/parent/add-child" className="pd-tab">Add child</Link>
      </nav>

      {!active.length && !pending.length && !revoked.length ? (
        <EmptyState
          title="No students yet"
          sub="Choose Add child to create your child's account."
        />
      ) : null}

      {active.length ? (
        <div className="pd-grid">
          {active.map((link) => {
            const scopes = link.scopes || [];
            return (
              <Link
                key={link.id}
                href={link.student_id ? `/parent/${link.student_id}` : "/parent"}
                className="card pd-card"
              >
                <div className="between pd-card-top">
                  <ParentAvatar
                    studentId={link.student_id}
                    name={linkName(link)}
                    size={44}
                  />
                  <div className="pd-card-id">
                    <h3 style={{ margin: 0 }}>{esc(linkName(link))}</h3>
                    <div className="small muted">
                      Grade {link.student?.grade ?? "—"} · sharing {scopes.length} of 3 sections
                    </div>
                  </div>
                  <Pill label={STATUS_LABEL.active} tone={STATUS_TONE.active} />
                </div>
                <div className="row pd-scopes">
                  {["basic", "insights", "memory"].map((id) => (
                    <span key={id} className={`chip ${scopes.includes(id) ? "acc" : ""}`}>
                      {scopeMeta(id)?.label || id}
                    </span>
                  ))}
                </div>
                <span className="pd-open">Open →</span>
              </Link>
            );
          })}
        </div>
      ) : null}

      {pending.length ? (
        <>
          <div className="section-title pd-sec-gap">Legacy pending connections</div>
          <div className="pd-grid">
            {pending.map((link) => (
              <div key={link.id} className="card pd-card pd-card-wait">
                <div className="between">
                  <h3 style={{ margin: 0 }}>{esc(pendingHeadline(link))}</h3>
                  <Pill label={STATUS_LABEL.pending} tone={STATUS_TONE.pending} />
                </div>
                <p className="small muted">
                  This older connection is still pending. It does not grant access
                  and will not be activated automatically.
                </p>
                <div className="row pd-scopes">
                  {(link.scopes || []).map((id) => (
                    <span key={id} className="chip acc">{scopeMeta(id)?.label || id}</span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </>
      ) : null}

      {revoked.length ? (
        <>
          <div className="section-title pd-sec-gap">No longer shared</div>
          <div className="pd-grid">
            {revoked.map((link) => (
              <div key={link.id} className="card pd-card pd-card-off">
                <div className="between">
                  <h3 style={{ margin: 0 }}>{esc(linkName(link))}</h3>
                  <Pill label={STATUS_LABEL.revoked} tone={STATUS_TONE.revoked} />
                </div>
                <p className="small muted">
                  This student removed access. Their progress is no longer available to you.
                </p>
              </div>
            ))}
          </div>
        </>
      ) : null}
    </div>
  );
}
