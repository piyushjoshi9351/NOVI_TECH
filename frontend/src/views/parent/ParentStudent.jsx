import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { api, esc, prettyDate } from "../../api";
import { scopeMeta } from "../../parentAccess";
import { EmptyState, Pill, Ring, showLoader } from "../../ui";

const SECTIONS = [
  { id: "basic", scope: "basic", endpoint: "overview", label: "Overview" },
  { id: "insights", scope: "insights", endpoint: "insights", label: "Insights" },
  { id: "memory", scope: "memory", endpoint: "memory", label: "Memory" },
];

/**
 * One student's page: three independently-gated sections.
 *
 * Each fetch is independent — a 403 on one section (the student never shared
 * it) is rendered as an explanation, not an error, and never blocks the others.
 * No raw chat is requested or rendered here, and letta_agent_id is neither
 * requested nor displayed: the backend never sends it.
 */
export default function ParentStudent() {
  const { studentId } = useParams();
  const [links, setLinks] = useState(null);
  const [tab, setTab] = useState("basic");
  const [state, setState] = useState({});       // tab -> {loading, data, denied, error}
  const [fatal, setFatal] = useState(null);

  useEffect(() => {
    let alive = true;
    showLoader(true);
    api("/parent/students")
      .then((d) => { if (alive) setLinks(d?.links || []); })
      .catch((ex) => { if (alive) setFatal(ex.message); })
      .finally(() => showLoader(false));
    return () => { alive = false; };
  }, []);

  // Resolve the tab from the link list, then load exactly that section.
  useEffect(() => {
    if (!links) return;
    const active = links.find((l) => String(l.student_id) === String(studentId) && l.status === "active")
      || links.find((l) => String(l.student_id) === String(studentId));
    if (!active) {
      // No link at all (or it was revoked) — the backend would 404 anyway.
      setFatal("This student is not shared with you.");
      return;
    }
    const granted = SECTIONS.filter((s) => (active.scopes || []).includes(s.scope));
    // Keep whatever tab is open as long as it's a real section, so a parent can
    // deliberately click into a locked one and read why.
    const current = SECTIONS.find((s) => s.id === tab) || granted[0] || SECTIONS[0];
    if (current.id !== tab) { setTab(current.id); return; }

    if (!granted.includes(current)) {
      // Already known to be unshared: don't spend a request we know will 403.
      // (The 403 branch below still covers a scope revoked while this is open.)
      setState((s) => ({ ...s, [tab]: { loading: false, denied: true } }));
      return;
    }

    let alive = true;
    setState((s) => ({ ...s, [tab]: { ...(s[tab] || {}), loading: true } }));
    api(`/parent/students/${studentId}/${current.endpoint}`)
      .then((data) => { if (alive) setState((s) => ({ ...s, [tab]: { loading: false, data } })); })
      .catch((ex) => {
        if (!alive) return;
        const denied = ex.status === 403;
        setState((s) => ({ ...s, [tab]: { loading: false, denied, error: ex.message } }));
      });
    return () => { alive = false; };
  }, [links, studentId, tab]);

  if (fatal) {
    return (
      <EmptyState
        title="Nothing to show here"
        sub={fatal}
      />
    );
  }
  if (!links) return null;

  const active = links.find((l) => String(l.student_id) === String(studentId) && l.status === "active");
  const any = links.find((l) => String(l.student_id) === String(studentId));
  if (!any) {
    return <EmptyState title="Nothing to show here" sub="This student is not shared with you." />;
  }
  if (!active) {
    return (
      <div className="pd-wrap">
        <div className="pd-hero">
          <div className="eyebrow">Parent space</div>
          <h1>Not shared yet</h1>
          <p>
            This student hasn&apos;t approved your request
            {any.status === "revoked" ? " — access was withdrawn" : ""}. Nothing about
            their progress is available until they do.
          </p>
          <Link href="/parent" className="btn" style={{ marginTop: 14, display: "inline-block" }}>
            ← Back to your children
          </Link>
        </div>
      </div>
    );
  }

  const granted = SECTIONS.filter((s) => (active.scopes || []).includes(s.scope));
  const cur = state[tab] || {};

  return (
    <div className="pd-wrap">
      <Link href="/parent" className="small muted pd-back">← All children</Link>

      <div className="pd-hero">
        <div className="eyebrow">Grade {active.student?.grade ?? "—"}</div>
        <h1>{esc(active.student?.first_name || "Your child")}</h1>
        <p>
          {esc(active.label || "Child")} · sharing{" "}
          {(active.scopes || []).map((s) => (scopeMeta(s)?.label || s).toLowerCase()).join(", ")}
        </p>
        <div className="row pd-scopes">
          {["basic", "insights", "memory"].map((id) => (
            <span key={id} className={`chip ${(active.scopes || []).includes(id) ? "acc" : ""}`}>
              {(active.scopes || []).includes(id) ? "✓ " : ""}{scopeMeta(id)?.label || id}
            </span>
          ))}
        </div>
      </div>

      {/* Every section stays listed so a locked one can explain itself. */}
      <div className="pd-tabs">
        {SECTIONS.map((s) => (
          <button
            key={s.id}
            className={`pd-tab ${tab === s.id ? "on" : ""}`}
            onClick={() => setTab(s.id)}
          >
            {s.label}
            {granted.includes(s) ? "" : " 🔒"}
          </button>
        ))}
      </div>

      {cur.loading ? <div className="card"><p className="muted small">Loading…</p></div> : null}

      {!cur.loading && cur.denied ? <NotShared scope={tab} /> : null}

      {!cur.loading && !cur.denied && cur.error ? (
        <EmptyState title="Could not load this section" sub={cur.error} />
      ) : null}

      {!cur.loading && !cur.denied && cur.data ? (
        <>
          {tab === "basic" ? <Overview data={cur.data} /> : null}
          {tab === "insights" ? <Insights data={cur.data} /> : null}
          {tab === "memory" ? <Memory data={cur.data} /> : null}
        </>
      ) : null}
    </div>
  );
}

/** 403 from require_scope: not an error, just a boundary the student set. */
function NotShared({ scope }) {
  const meta = scopeMeta(scope);
  return (
    <div className="card pd-notshared">
      <div className="pd-notshared-ico" aria-hidden="true">🔒</div>
      <h3>The student hasn&apos;t shared this</h3>
      <p className="small muted">
        {meta?.blurb || "This section isn't shared with you."} They can turn it on any
        time from their own Parent access settings.
      </p>
    </div>
  );
}

function Overview({ data }) {
  const w = data.this_week || {};
  const goals = data.active_goals || [];
  const passport = data.recent_passport || [];
  const roadmap = data.upcoming_roadmap || [];

  return (
    <>
      <div className="pd-stats">
        <div className="card pd-stat">
          <div className="pd-week-num">{w.completed_count ?? 0}<span>/{w.total_count ?? 0}</span></div>
          <div><div className="stat-label">This week</div>
            <div className="small muted">Priorities done</div></div>
        </div>
        <div className="card pd-stat">
          <div className="pd-week-num">{goals.length}</div>
          <div><div className="stat-label">Active goals</div>
            <div className="small muted">What they're working toward</div></div>
        </div>
        <div className="card pd-stat">
          <div className="pd-week-num">{data.school || "—"}</div>
          <div><div className="stat-label">School</div>
            <div className="small muted">Where they study</div></div>
        </div>
      </div>

      <div className="section-title pd-sec-gap">This week</div>
      <div className="card">
        <div className="small muted">Week of {prettyDate(w.week_start) || "—"}</div>
        {(w.priorities || []).length ? (
          <ul className="pd-list">
            {w.priorities.map((p, i) => <li key={i}>{esc(String(p))}</li>)}
          </ul>
        ) : <p className="small muted">No priorities set for this week.</p>}
      </div>

      <div className="section-title pd-sec-gap">Active goals</div>
      {goals.length ? (
        <div className="pd-grid">
          {goals.map((g) => (
            <div className="card" key={g.id}>
              <div className="between">
                <h3 style={{ margin: 0 }}>{esc(g.title || "")}</h3>
                {g.status ? <Pill label={String(g.status)} tone="mid" /> : null}
              </div>
              <div className="small muted mt">
                {[g.category, g.target_date ? `by ${prettyDate(g.target_date)}` : null]
                  .filter(Boolean).join(" · ") || "No category set"}
              </div>
            </div>
          ))}
        </div>
      ) : <div className="card"><p className="small muted">No active goals yet.</p></div>}

      <div className="section-title pd-sec-gap">Recent passport</div>
      {passport.length ? (
        <div className="pd-grid">
          {passport.map((p) => (
            <div className="card" key={p.id}>
              <h3 style={{ margin: 0 }}>{esc(p.title || "")}</h3>
              <div className="small muted mt">{esc(p.category || "")}{p.date_achieved ? ` · ${prettyDate(p.date_achieved)}` : ""}</div>
            </div>
          ))}
        </div>
      ) : <div className="card"><p className="small muted">Nothing added to their passport yet.</p></div>}

      <div className="section-title pd-sec-gap">Coming up</div>
      {roadmap.length ? (
        <div className="pd-grid">
          {roadmap.map((r) => (
            <div className="card" key={r.id}>
              <div className="between">
                <h3 style={{ margin: 0 }}>{esc(r.title || "")}</h3>
                {r.completed ? <Pill label="Done" tone="good" /> : null}
              </div>
              <div className="small muted mt">
                {[r.stage, r.grade ? `Grade ${r.grade}` : null, r.category]
                  .filter(Boolean).join(" · ") || "No stage set"}
              </div>
            </div>
          ))}
        </div>
      ) : <div className="card"><p className="small muted">No upcoming roadmap steps.</p></div>}
    </>
  );
}

function Insights({ data }) {
  const rows = [
    ["Top interests", data.top_interests],
    ["Strengths", data.strengths],
    ["Career zones", data.career_zones],
  ];
  return (
    <>
      <div className="pd-stats">
        <div className="card pd-stat">
          <Ring pct={data.profile_strength || 0} label={pct(data.profile_strength)} />
          <div><div className="stat-label">Profile strength</div>
            <div className="small muted">How complete their story is</div></div>
        </div>
        <div className="card pd-stat">
          <Ring pct={data.university_readiness || 0} label={pct(data.university_readiness)} />
          <div><div className="stat-label">University readiness</div>
            <div className="small muted">Their current score</div></div>
        </div>
      </div>

      {rows.map(([title, items]) => (
        <div key={title}>
          <div className="section-title pd-sec-gap">{title}</div>
          <div className="card">
            {(items || []).length ? (
              <div className="row pd-scopes">
                {items.map((t, i) => <span key={`${t}-${i}`} className="chip acc">{esc(String(t))}</span>)}
              </div>
            ) : <p className="small muted">Nothing here yet.</p>}
          </div>
        </div>
      ))}

      <div className="section-title pd-sec-gap">Top career matches</div>
      {(data.top_career_matches || []).length ? (
        <div className="card">
          <div className="row pd-scopes">
            {data.top_career_matches.map((t, i) => (
              <span key={`${t}-${i}`} className="chip acc">{esc(String(t))}</span>
            ))}
          </div>
        </div>
      ) : <div className="card"><p className="small muted">No matches ranked yet.</p></div>}
    </>
  );
}

function Memory({ data }) {
  // `available` is false when long-term memory is switched off server-side.
  // That is a quiet empty state, not an error.
  if (!data.available) {
    return (
      <div className="card">
        <h3>No long-term memory yet</h3>
        <p className="small muted">
          Novi hasn&apos;t stored anything worth sharing for this student yet. This
          fills in as they use Novi — and it is never a transcript of their chats.
        </p>
      </div>
    );
  }

  return (
    <>
      {data.summary ? (
        <>
          <div className="section-title pd-sec-gap">What Novi remembers</div>
          <div className="card"><p className="pd-summary">{esc(data.summary)}</p></div>
        </>
      ) : null}

      <div className="section-title pd-sec-gap">Highlights</div>
      {(data.passages || []).length ? (
        <div className="pd-list-plain">
          {data.passages.map((p, i) => (
            <div className="card" key={p.id ?? i}>
              <div className="small muted">{esc(p.created_at ? prettyDate(p.created_at) : "")}</div>
              <p className="mt">{esc(p.text || "")}</p>
            </div>
          ))}
        </div>
      ) : (
        <div className="card"><p className="small muted">Nothing to show yet.</p></div>
      )}
    </>
  );
}

const pct = (v) => (typeof v === "number" ? `${Math.round(v)}%` : "—");