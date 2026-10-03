import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { api, esc } from "../../api";
import { useAuth } from "../../auth";
import {
  GENERIC_INVITE_MESSAGE,
  STATUS_LABEL,
  STATUS_TONE,
  isActive,
  isPending,
  isRevoked,
  linkName,
  pendingHeadline,
  scopeMeta,
} from "../../parentAccess";
import { EmptyState, Pill, showLoader, toast } from "../../ui";
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
  const [email, setEmail] = useState("");
  // "children" (default) or "request". Kept in the URL so the tab is linkable,
  // survives a refresh, and works with the back button.
  const router = useRouter();
  const params = useSearchParams();
  const view = params.get("tab") === "request" ? "request" : "children";
  const setView = useCallback(
    (next) => router.push(next === "children" ? "?tab=children" : "?tab=request", { scroll: false }),
    [router]
  );
  const [busy, setBusy] = useState(false);

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

  const request = async (e) => {
    e.preventDefault();
    const target = email.trim();
    if (!target) return;
    setBusy(true);
    try {
      const res = await api("/parent/links", {
        method: "POST",
        body: JSON.stringify({ student_email: target }),
      });
      // Always the same sentence — the backend does not reveal whether the
      // email is registered, and neither do we.
      toast(res?.message || GENERIC_INVITE_MESSAGE, "info");
      setEmail("");
      await load();
    } catch (ex) { toast(ex.message, "err"); }
    finally { setBusy(false); }
  };

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
          <button
            className="btn"
            onClick={() => setView("request")}
            disabled={view === "request"}
          >
            Request access
          </button>
        </div>
      </div>

      {/* Two tabs rather than one long page: browsing your children and asking
          for a new one are different jobs, and the request form is a one-shot
          action that shouldn't sit above the list you came to read. The tab is
          in the URL so it's linkable and survives a refresh. */}
      <div className="pd-tabs" role="tablist" aria-label="Parent sections">
        <button
          role="tab"
          aria-selected={view === "children"}
          className={`pd-tab${view === "children" ? " on" : ""}`}
          onClick={() => setView("children")}
        >
          <span className="pd-tab-label">
            Your children{total ? ` · ${total}` : ""}
          </span>
        </button>
        <button
          role="tab"
          aria-selected={view === "request"}
          className={`pd-tab${view === "request" ? " on" : ""}`}
          onClick={() => setView("request")}
        >
          <span className="pd-tab-label">Request access</span>
        </button>
      </div>

      {view === "request" ? (
        <div className="ln-grid">
          <div className="ln-main">
            <section className="ln-section">
              <div className="card">
                <h2 style={{ margin: 0 }}>Request access to another student</h2>
                <p className="small muted">
                  Enter the email they signed up with. They&apos;ll get a request and
                  choose what to share — nothing is visible to you before that.
                </p>
                <form className="pd-request-row" onSubmit={request}>
                  <input
                    aria-label="Student email"
                    placeholder="child@school.edu"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    type="email"
                    autoComplete="off"
                  />
                  <button className="btn" disabled={busy}>
                    {busy ? "Sending…" : "Send request"}
                  </button>
                </form>
              </div>
            </section>
          </div>
          <aside className="ln-rail">
            <div className="card ln-card">
              <div className="ln-card-head">
                <span className="ln-ico" aria-hidden="true">🔒</span>
                <h3>What you&apos;ll see</h3>
              </div>
              <p className="small muted">
                Nothing until they approve. After that you still only see the sections
                they choose — and they can turn any of them off again at any time.
              </p>
            </div>
          </aside>
        </div>
      ) : null}

      {view === "children" ? (
      <>
      {!active.length && !pending.length && !revoked.length ? (
        <EmptyState
          title="No students yet"
          sub="Send a request above using the email your child signed up with."
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
          <div className="section-title pd-sec-gap">Awaiting approval</div>
          <div className="pd-grid">
            {pending.map((link) => (
              <div key={link.id} className="card pd-card pd-card-wait">
                <div className="between">
                  <h3 style={{ margin: 0 }}>{esc(pendingHeadline(link))}</h3>
                  <Pill label={STATUS_LABEL.pending} tone={STATUS_TONE.pending} />
                </div>
                <p className="small muted">
                  We&apos;ve asked them to confirm and choose what to share. You&apos;ll
                  see their progress here as soon as they say yes.
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
      </>
      ) : null}
    </div>
  );
}