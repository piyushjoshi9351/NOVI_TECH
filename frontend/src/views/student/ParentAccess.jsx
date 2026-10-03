import { useCallback, useEffect, useState } from "react";
import { api, esc, prettyDate } from "../../api";
import {
  SCOPES,
  STATUS_LABEL,
  STATUS_TONE,
  isActive,
  isPending,
  isRevoked,
} from "../../parentAccess";
import { EmptyState, Pill, showLoader, toast } from "../../ui";

/**
 * "Parent access" — the student's side of consent.
 *
 * Nothing here is shared until they press Approve, and they can narrow or widen
 * what each parent sees at any time. `basic` is always on: it is the minimum
 * needed for a parent account to mean anything, and the backend enforces that
 * too, so the control is shown as fixed rather than as a toggle.
 */
export default function ParentAccess() {
  const [links, setLinks] = useState(null);
  const [error, setError] = useState(null);
  const [busyId, setBusyId] = useState(null);
  const [draft, setDraft] = useState({});   // linkId -> {insights, memory}

  const load = useCallback(async () => {
    const d = await api("/student/parent-links");
    const rows = d?.links || [];
    setLinks(rows);
    // Seed the toggles from what is actually stored, not from a guess.
    const next = {};
    rows.forEach((l) => {
      const s = l.scopes || [];
      next[l.id] = { insights: s.includes("insights"), memory: s.includes("memory") };
    });
    setDraft(next);
  }, []);

  useEffect(() => {
    let alive = true;
    showLoader(true);
    load()
      .catch((ex) => { if (alive) setError(ex.message); })
      .finally(() => showLoader(false));
    return () => { alive = false; };
  }, [load]);

  const approve = async (link) => {
    setBusyId(link.id);
    try {
      // Approve whatever is currently ticked, so toggling then approving is one
      // action and the parent never gets more than the student has chosen.
      const d = draft[link.id] || {};
      await api(`/student/parent-links/${link.id}/scopes`, {
        method: "PATCH",
        body: JSON.stringify({ insights: !!d.insights, memory: !!d.memory }),
      });
      await api(`/student/parent-links/${link.id}/approve`, { method: "POST" });
      toast(`You can now share your progress with ${esc(link.parent_name || "this parent")}`);
      await load();
    } catch (ex) { toast(ex.message, "err"); }
    finally { setBusyId(null); }
  };

  const revoke = async (link) => {
    setBusyId(link.id);
    try {
      await api(`/student/parent-links/${link.id}/revoke`, { method: "POST" });
      toast("Access removed.");
      await load();
    } catch (ex) { toast(ex.message, "err"); }
    finally { setBusyId(null); }
  };

  const saveScopes = async (link, next) => {
    setBusyId(link.id);
    const before = draft[link.id];
    setDraft((d) => ({ ...d, [link.id]: next }));
    try {
      await api(`/student/parent-links/${link.id}/scopes`, {
        method: "PATCH",
        body: JSON.stringify({ insights: !!next.insights, memory: !!next.memory }),
      });
      toast("Sharing updated.");
      await load();
    } catch (ex) {
      setDraft((d) => ({ ...d, [link.id]: before }));
      toast(ex.message, "err");
    }
    finally { setBusyId(null); }
  };

  if (error) return <EmptyState title="Parent access unavailable" sub={error} />;
  if (!links) return null;

  const pending = links.filter(isPending);
  const connected = links.filter(isActive);
  const gone = links.filter(isRevoked);

  return (
    <>
      <div className="ps-section-head"><span className="ps-eyebrow">Privacy</span></div>
      <p className="ps-intro">
        You decide who follows your journey and what they can see. Nothing is shared
        until you approve a request, and you can change or remove it at any time —
        your chats are never shared.
      </p>

      {!links.length ? (
        <EmptyState
          title="No parent requests"
          sub="When a parent enters your email, their request appears here for you to approve."
        />
      ) : null}

      {pending.map((link) => (
        <ParentRow
          key={link.id}
          link={link}
          draft={draft[link.id] || {}}
          busy={busyId === link.id}
          onToggle={(next) => setDraft((d) => ({ ...d, [link.id]: next }))}
          onApprove={() => approve(link)}
        />
      ))}

      {connected.length ? (
        <>
          <div className="ps-section-title">Connected parents</div>
          {connected.map((link) => (
            <ParentRow
              key={link.id}
              link={link}
              draft={draft[link.id] || {}}
              busy={busyId === link.id}
              onToggle={(next) => saveScopes(link, next)}
              onRevoke={() => revoke(link)}
            />
          ))}
        </>
      ) : null}

      {gone.length ? (
        <>
          <div className="ps-section-title">Removed</div>
          {gone.map((link) => (
            <div className="card pa-card" key={link.id}>
              <div className="between">
                <span className="pa-name">{esc(link.parent_name || "A parent")}</span>
                <Pill label={STATUS_LABEL.revoked} tone={STATUS_TONE.revoked} />
              </div>
              <p className="ps-hint">
                Requested {prettyDate(link.created_at)}. You removed their access.
              </p>
            </div>
          ))}
        </>
      ) : null}
    </>
  );
}

function ParentRow({ link, draft, busy, onToggle, onApprove, onRevoke }) {
  const pending = isPending(link);
  const revoked = isRevoked(link);
  const granted = new Set(link.scopes || []);

  return (
    <div className="card pa-card" data-link-id={link.id}>
      <div className="between">
        <span className="pa-name">
          {esc(link.parent_name || "A parent")}
          {link.label && link.label.toLowerCase() !== "child" ? (
            <span className="small muted"> · {esc(link.label)}</span>
          ) : null}
        </span>
        <Pill
          label={STATUS_LABEL[link.status] || link.status}
          tone={STATUS_TONE[link.status] || ""}
        />
      </div>

      <p className="ps-hint">
        {pending
          ? `Asked ${prettyDate(link.created_at)}. They can't see anything until you approve.`
          : revoked
            ? `Requested ${prettyDate(link.created_at)}.`
            : `Requested ${prettyDate(link.created_at)}.`}
      </p>

      <div className="pa-scopes">
        {SCOPES.map((s) => {
          const on = s.locked || granted.has(s.id);
          return (
            <label className="pa-scope" key={s.id}>
              <span className="ps-toggle">
                <input
                  type="checkbox"
                  checked={on}
                  disabled={s.locked || revoked || busy}
                  onChange={(e) => onToggle({ ...draft, [s.id]: e.target.checked })}
                />
                <span className="ps-track" />
              </span>
              <span className="pa-scope-copy">
                <span className="pa-scope-name">
                  {esc(s.label)}
                  {s.locked ? <span className="small muted"> · always on</span> : null}
                </span>
                <span className="ps-hint">{esc(s.blurb)}</span>
              </span>
            </label>
          );
        })}
      </div>

      <div className="pa-actions">
        {pending ? (
          <button className="btn" disabled={busy} onClick={onApprove}>
            {busy ? "Approving…" : "Approve & share"}
          </button>
        ) : null}
        {!revoked ? (
          <button className="btn btn-ghost" disabled={busy} onClick={onRevoke}>
            {revoked ? "Removed" : busy ? "Working…" : "Remove access"}
          </button>
        ) : null}
      </div>
    </div>
  );
}