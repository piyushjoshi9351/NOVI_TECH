import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { api, esc, prettyDate, PP_CATS, ringColor, safeHttpUrl } from "../../api";
import { scopeMeta } from "../../parentAccess";
import { EmptyState, Pill, showLoader } from "../../ui";
import { ParentAvatar } from "./ParentAvatar";

/* One tab per section, mirroring the student app's nav (Dashboard / My DNA /
 * Careers / Roadmap / Passport / ...). Every tab is backed by a real field in the
 * allowlisted parent schema -- no tab exists just to fill the bar. The three
 * consent scopes map onto groups of tabs rather than one tab each, because a
 * parent thinks in topics (goals, passport, careers), not in permissions. */
const TABS = [
  { id: "overview", label: "Overview", scope: "basic" },
  { id: "journey", label: "Journey", scope: "basic" },
  { id: "goals", label: "Goals", scope: "basic" },
  { id: "passport", label: "Passport", scope: "insights" },
  { id: "interests", label: "Interests", scope: "insights" },
  { id: "careers", label: "Careers", scope: "insights" },
  { id: "strengths", label: "Strengths", scope: "insights" },
  { id: "growth", label: "Growth", scope: "memory" },
];

/** Show a number, or an honest dash when we genuinely don't know it.
 *  Never render a 0 for missing data -- "0%" reads as a verdict on the child. */
function num(v) {
  return typeof v === "number" && Number.isFinite(v) ? v : null;
}

function pctText(v) {
  const n = num(v);
  return n === null ? "Not enough data yet" : `${Math.round(n)}%`;
}

/**
 * The parent dashboard: one child at a time, one tab per consent section.
 *
 * Shape decisions worth knowing:
 *
 * * **Tabs, like the student app.** Overview / Insights / Growth history each get
 *   their own tab so a parent can go straight to one area, the same way a student
 *   navigates by nav entry. The active tab lives in the URL (`?tab=`) so a tab is
 *   linkable, survives a refresh and works with the back button.
 * * **A locked tab is still a tab.** It stays visible and clickable, showing why
 *   it is empty. Hiding it would leave a parent wondering whether the feature
 *   exists, and clicking a locked tab costs nothing and discloses nothing.
 * * **One child at a time, switchable.** `student_id` comes from the link list,
 *   which only discloses it once a link is active, so there is no way to page
 *   this view onto someone who hasn't consented.
 * * **No request is spent on a section we already know is unshared.** We read
 *   `scopes` from the link and skip the fetch, which keeps the consent decision
 *   on the client purely as an optimisation -- the server gates regardless.
 * * Everything rendered here comes from an allowlisted parent schema. There is
 *   no chat, no Letta memory, no check-in text, no passport titles and no
 *   day-to-day task list to render even if the API grew one.
 */
export default function ParentStudent({ studentId }) {
  const [links, setLinks] = useState(null);
  const [data, setData] = useState({});       // endpoint -> payload | error
  const [fatal, setFatal] = useState(null);
  const router = useRouter();
  const params = useSearchParams();
  const tab = params.get("tab") || "overview";
  const setTab = useCallback(
    // push, not replace: each tab is its own history entry, so the browser back
    // button walks back through the tabs the way a student app's nav does.
    (next) => router.push(next === "overview" ? "?tab=overview" : `?tab=${next}`, { scroll: false }),
    [router]
  );

  useEffect(() => {
    let alive = true;
    showLoader(true);
    api("/parent/students")
      .then((d) => {
        if (!alive) return;
        const list = d?.links || [];
        setLinks(list);
      })
      .catch((ex) => { if (alive) setFatal(ex.message); })
      .finally(() => showLoader(false));
    return () => { alive = false; };
  }, []);

  const activeLinks = (links || []).filter((l) => l.status === "active");
  // The URL decides which child is shown, so a bookmark, a reload or the back
  // button all land on the same child. Falling back to the first active link
  // covers a stale or hand-edited id.
  const link =
    activeLinks.find((l) => String(l.student_id) === String(studentId)) || activeLinks[0] || null;
  const scopes = link?.scopes || [];
  const granted = (scope) => scopes.includes(scope);

  // Load only the sections this child actually shares.
  const load = useCallback((studentId, want) => {
    const ends = [];
    if (want("basic")) ends.push("overview");
    if (want("insights")) ends.push("insights");
    if (want("memory")) ends.push("memory");

    setData({});
    ends.forEach((endpoint) => {
      api(`/parent/students/${studentId}/${endpoint}`)
        .then((payload) => setData((d) => ({ ...d, [endpoint]: { data: payload } })))
        .catch((ex) => setData((d) => ({ ...d, [endpoint]: { error: ex.message, status: ex.status } })));
    });
  }, []);

  useEffect(() => {
    if (!link?.student_id) return;
    load(link.student_id, granted);
    // `scopes` is derived from `link`, so re-running on the resolved link object
    // is enough to catch a consent change on refetch.
  }, [link?.student_id, scopes.join(","), load]); // eslint-disable-line react-hooks/exhaustive-deps

  const selectChild = useCallback(
    (id) => router.push(`/parent/${id}${tab === "overview" ? "" : `?tab=${tab}`}`, { scroll: false }),
    [router, tab]
  );

  if (fatal) return <EmptyState title="Couldn't load your children" sub={fatal} />;
  if (!links) return null;

  if (!activeLinks.length) {
    return (
      <div className="pd-wrap">
        <div className="pd-hero">
          <div className="eyebrow">Parent space</div>
          <h1>No children shared yet</h1>
          <p>
            Nothing to show until a student approves your request. You&apos;ll see their
            progress here once they do, and only the sections they choose to share.
          </p>
          <Link href="/parent" className="btn pd-hero-btn">Request access</Link>
        </div>
      </div>
    );
  }

  const name = esc(link.student?.first_name || "Your child");
  const grade = num(link.student?.grade);
  const pending = links.filter((l) => l.status === "pending").length;

  return (
    <div className="dash-wrap pd-wrap">
      {/* ------------------------------------------------------- page header
          Built from the student dashboard's own primitives (.dash-top /
          .dash-kick / .dash-hi / .dash-sub) rather than a parallel set of
          .pd-* styles, so the parent area reads as the same product. */}
      <div className="dash-top">
        <ParentAvatar studentId={link.student_id} name={name} size={54} className="dash-avatar" />
        <div className="dash-intro">
          <div className="dash-kick">
            {activeLinks.length > 1 ? `${activeLinks.length} children` : "Your child"}
            {grade !== null ? ` · Grade ${grade}` : ""}
          </div>
          <h1 className="dash-hi">{name}</h1>
          <p className="dash-sub">
            {pending
              ? `${pending} request${pending === 1 ? "" : "s"} awaiting approval. `
              : ""}
            Sharing {scopes.map((s) => scopeMeta(s)?.label || s).join(", ").toLowerCase()}.
          </p>
        </div>
        <div className="dash-tools">
          <Link href="/parent" className="btn btn-ghost">← My Children</Link>
        </div>
      </div>

      {/* Child switcher: one pill per child, same component as the student's
          header chips, so switching reads as a filter rather than a mode. */}
      {activeLinks.length > 1 ? (
        <div className="dash-chips" role="tablist" aria-label="Choose a child">
          {activeLinks.map((l) => (
            <button
              key={l.id}
              role="tab"
              aria-selected={String(l.student_id) === String(link.student_id)}
              className={`chip-soft pd-child ${String(l.student_id) === String(link.student_id) ? "on" : ""}`}
              onClick={() => selectChild(l.student_id)}
            >
              {esc(l.student?.first_name || "Child")}
              {l.student?.grade ? ` · G${l.student.grade}` : ""}
            </button>
          ))}
        </div>
      ) : null}

      {/* ------------------------------------------------------------- tabs */}
      <div className="pd-tabs" role="tablist" aria-label="Dashboard sections">
        {TABS.map((t) => {
          const on = tab === t.id;
          const locked = t.scope && !granted(t.scope);
          return (
            <button
              key={t.id}
              role="tab"
              aria-selected={on}
              className={`pd-tab${on ? " on" : ""}${locked ? " locked" : ""}`}
              onClick={() => setTab(t.id)}
            >
              <span className="pd-tab-label">{t.label}</span>
              {locked ? <span className="pd-tab-lock" title="Not shared with you">🔒</span> : null}
            </button>
          );
        })}
        <span className="pd-tabs-fill" />
        <Link href="/advisor" className="pd-tab pd-tab-chat">
          <span className="pd-tab-label">Ask Novi about {name}</span>
          <svg viewBox="0 0 24 24" width="15" height="15" aria-hidden="true">
            <path d="M4 12h15m0 0-6-6m6 6-6 6" fill="none" stroke="currentColor"
                  strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </Link>
      </div>

      {/* At-a-glance strip, shown on Overview only -- it summarises all three
          sections, so repeating it on every tab would be noise. Every tile is
          consent-gated: an unshared section shows a dash, never a number. */}
      {tab === "overview" && granted("basic") ? (
        <StatStrip
          overview={data.overview?.data}
          insights={granted("insights") ? data.insights?.data : null}
          growth={granted("memory") ? data.memory?.data?.growth : null}
          childId={link.student_id}
          name={link.student?.first_name || "your child"}
        />
      ) : null}

      {/* ------------------------------------------------------ active tab
          One section per tab, each backed by its own fields in the allowlisted
          schema. A tab whose scope isn't granted explains itself rather than
          disappearing, so a parent can still discover the feature exists. */}
      {(() => {
        const need = { basic: "overview", insights: "insights", memory: "memory" };
        const spec = TABS.find((t) => t.id === tab) || TABS[0];
        const endpoint = need[spec.scope];
        if (!granted(spec.scope)) {
          return <NotShared scope={spec.scope} name={name} tab={spec.label} />;
        }
        return (
          <Section entry={data[endpoint]}>
            {(d) => {
              switch (spec.id) {
                case "overview": return <OverviewSection data={d.basic || {}} name={name} />;
                case "journey": return <JourneySection data={d.basic || {}} />;
                case "goals": return <GoalsSection data={d.basic || {}} />;
                case "passport": return <PassportSection insights={d} name={name} />;
                case "interests": return <InterestsSection data={d} />;
                case "careers": return <CareersSection data={d} />;
                case "strengths": return <StrengthsSection data={d} />;
                case "growth": return <GrowthSection data={d.growth} name={name} />;
                default: return null;
              }
            }}
          </Section>
        );
      })()}

    </div>
  );
}

/** Loading + error wrapper, so every card handles failure the same way.
 *  `entry` is `{ data }`, `{ error, status }` or undefined while in flight. */
function Section({ entry, children }) {
  if (!entry) return <div className="card"><p className="muted small">Loading…</p></div>;
  if (entry.error) {
    return (
      <EmptyState
        title="Couldn't load this section"
        sub={entry.status === 404
          ? "This student is no longer shared with you."
          : entry.error}
      />
    );
  }
  return <>{children(entry.data)}</>;
}

/** "Where things stand" summary. Built from the student dashboard's .dash-tiles
 *  so the parent area inherits the same tile language instead of a lookalike.
 *  Renders a dash for anything not shared, so the strip can never imply more
 *  than the child has consented to. */
function StatStrip({ overview, insights, growth, childId, name }) {
  const b = overview?.basic || null;
  const strength = num(b?.profile_strength);
  const readiness = num(b?.university_readiness);
  const done = num(growth?.milestones_completed);
  const change = growth?.trend_change;
  const direction = b?.career_direction;

  const tone = (v, good, warn) => (v == null ? "" : v >= good ? "good" : v >= warn ? "warn" : "low");

  const tiles = [
    {
      ico: "◔",
      label: "Profile strength",
      value: strength == null ? "—" : `${strength}%`,
      sub: strength == null ? "Not enough data yet" : "How much is filled in",
      tone: tone(strength, 70, 40),
    },
    {
      ico: "◎",
      label: "University readiness",
      value: readiness == null ? "—" : `${readiness}%`,
      sub: readiness == null ? "No matches shared yet" : "From their top matches",
      tone: tone(readiness, 70, 0),
    },
    {
      ico: "✦",
      label: "Milestones done",
      value: done == null ? "—" : String(done),
      sub: change == null ? "From growth history" : `${change > 0 ? "+" : ""}${change} confidence trend`,
      tone: change == null ? "" : change > 0 ? "good" : change < 0 ? "low" : "",
    },
    {
      ico: "→",
      label: "Direction",
      value: direction || (insights?.status ? esc(insights.status) : "—"),
      sub: "Where they're heading",
      text: true,
    },
  ];

  return (
    <>
      <div className="dash-tiles">
        {tiles.map((t) => (
          <div className="dash-tile pd-tile" key={t.label}>
            <div className="dash-tile-top">
              <span className="dash-tile-ico" aria-hidden="true">{t.ico}</span>
              <span className="dash-tile-label">{t.label}</span>
            </div>
            <div className={`dash-tile-val ${t.tone ? `t-${t.tone}` : ""} ${t.text ? "sm" : ""}`}>
              {t.value}
            </div>
            <div className="dash-tile-sub">{t.sub}</div>
          </div>
        ))}
      </div>

      {/* The chat entry point gets the same hero treatment the student dashboard
          gives its focus card, because "ask about this page" is the primary
          action here -- not a fifth statistic. */}
      <Link href="/advisor" className="focus-card pd-chatcard">
        <div className="focus-body">
          <span className="focus-lab">Ask Novi</span>
          <h3 className="focus-title">Questions about {esc(name)}&apos;s progress?</h3>
          <p className="focus-why">
            Novi answers from the sections {esc(name)} has shared with you — and nothing else.
          </p>
        </div>
        <div className="focus-side">
          <span className="pd-chatcard-go">
            Open chat
            <svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true">
              <path d="M4 12h15m0 0-6-6m6 6-6 6" fill="none" stroke="currentColor"
                    strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </span>
        </div>
      </Link>
    </>
  );
}

function NotShared({ scope, name, tab }) {
  const meta = scopeMeta(scope);
  return (
    <div className="card pd-notshared">
      <div className="pd-notshared-ico" aria-hidden="true">🔒</div>
      <h3>{esc(name)} hasn&apos;t shared {tab ? `their ${tab.toLowerCase()}` : "this"}</h3>
      <p className="small muted">
        {meta?.blurb || "This section isn't shared with you."} They can change this any
        time from their own Parent access settings.
      </p>
    </div>
  );
}

/* ------------------------------------------------------------ shared blocks */
/** The standard "section + card" shape used by every tab, so all eight read as
 *  one page rather than eight bespoke layouts. */
function Block({ title, count, children }) {
  return (
    <section className="ln-section">
      <div className="ln-section-head">
        <h2 className="ln-section-title">{title}</h2>
        {count !== undefined ? <span className="dash-tile-sub">{count}</span> : null}
      </div>
      <div className="card">{children}</div>
    </section>
  );
}

/** Chip cloud for a list of short labels (interests, strengths, categories). */
function Chips({ items, accent = true }) {
  return (
    <div className="row pd-scopes" style={{ marginTop: 0 }}>
      {items.map((t, i) => (
        <span key={`${t}-${i}`} className={`chip ${accent ? "acc" : ""}`}>{esc(String(t))}</span>
      ))}
    </div>
  );
}

/** Row list used for goals and milestones (`.dash-rows` is the student's own). */
function Rows({ items, render, done = false }) {
  return (
    <div className="dash-rows">
      {items.map((it, i) => (
        <div className="dash-row" key={it.id ?? i} style={{ cursor: "default" }}>
          <span
            className="dash-check"
            aria-hidden="true"
            style={done ? { background: "var(--grad)", borderColor: "transparent" } : undefined}
          >
            {done ? "✓" : ""}
          </span>
          <span className="dash-row-body">{render(it, i)}</span>
        </div>
      ))}
    </div>
  );
}

/* --------------------------------------------------------------- basic tabs */
function OverviewSection({ data, name }) {
  const themes = data.dna_snapshot?.themes || [];
  return (
    <div className="ln-grid">
      <div className="ln-main">
        <Block title="Where they're heading">
          <h3 style={{ margin: 0 }}>
            {esc(data.career_direction || "Not decided yet — that's normal")}
          </h3>
          {themes.length ? (
            <div className="row pd-scopes mt">{<Chips items={themes} />}</div>
          ) : (
            <p className="small muted mt">
              Themes appear here as {esc(name)} explores what they enjoy.
            </p>
          )}
        </Block>
        <Block title="At a glance">
          <div className="row pd-scopes" style={{ marginTop: 0 }}>
            <Pill label={`Profile strength ${pctText(data.profile_strength)}`} />
            <Pill label={`Readiness ${pctText(data.university_readiness)}`} />
            {data.school ? <Pill label={esc(data.school)} /> : null}
          </div>
        </Block>
      </div>
      <aside className="ln-rail">
        <div className="card ln-card">
          <div className="ln-card-head"><span className="ln-ico">🔒</span><h3>Consent</h3></div>
          <p className="dash-tile-sub">
            This page only ever shows what {esc(name)} has chosen to share, section by
            section. They can change it any time.
          </p>
        </div>
      </aside>
    </div>
  );
}

function JourneySection({ data }) {
  const j = data.journey || {};
  const pct = num(j.roadmap_percent);
  return (
    <div className="ln-grid">
      <div className="ln-main">
        <Block title="Roadmap progress">
          {pct === null ? (
            <p className="small muted">No roadmap progress shared yet.</p>
          ) : (
            <>
              <div className="pd-rail-big">{Math.round(pct)}%</div>
              <div className="progress-track" style={{ marginTop: 12 }}>
                <div className="progress-fill" style={{ width: `${Math.max(0, Math.min(100, pct))}%` }} />
              </div>
            </>
          )}
        </Block>
      </div>
      <aside className="ln-rail">
        <div className="card ln-card">
          <div className="ln-card-head"><span className="ln-ico">🧭</span><h3>Stage</h3></div>
          <div className="dash-tile-sub">{esc(j.stage_label || "Stage not set yet")}</div>
          {j.grade !== null && j.grade !== undefined ? (
            <div className="dash-tile-sub mt">Grade {j.grade}</div>
          ) : null}
        </div>
      </aside>
    </div>
  );
}

function GoalsSection({ data }) {
  const goals = data.goals || [];
  return (
    <Block title="Goals" count={`${goals.length} active`}>
      {goals.length ? (
        <Rows
          items={goals}
          render={(g) => (
            <>
              <span className="dash-row-title">{esc(g.title || "")}</span>
              <span className="dash-row-meta">{esc(g.category || "No category set")}</span>
            </>
          )}
        />
      ) : (
        <p className="small muted">No active goals yet.</p>
      )}
    </Block>
  );
}

function PassportSection({ insights, name }) {
  const items = insights?.passport_items || [];
  const byCategory = {};
  for (const it of items) byCategory[it.category] = (byCategory[it.category] || 0) + 1;
  const p = {
    total: items.length,
    verified: items.filter((i) => i.verified).length,
    by_category: byCategory,
  };
  const cats = Object.entries(byCategory);
  const blurb = (it) => (it.description || "").trim();

  return (
    <div className="ln-grid">
      <div className="ln-main">
        {items.length ? (
          <>
            {cats.length ? (
              <div className="row pd-scopes" style={{ marginTop: 0 }}>
                {cats.map(([c, n]) => (
                  <span key={c} className="chip">{esc(PP_CATS[c]?.label || c)} · {n}</span>
                ))}
              </div>
            ) : null}
            <div className="ln-feed">
              {items.map((it) => (
                <article className="ln-entry" key={it.id}>
                  <div className="ln-entry-ico" aria-hidden="true">
                    {esc((PP_CATS[it.category]?.icon || "🌟"))}
                  </div>
                  <div className="ln-entry-body">
                    <div className="ln-entry-top">
                      <div className="ln-entry-title">{esc(it.title)}</div>
                      {it.verified ? <span className="ln-badge" aria-label="Verified">✓</span> : null}
                    </div>
                    {blurb(it) ? <p className="ln-entry-text">{esc(it.description)}</p> : null}
                    <div className="ln-entry-foot">
                      <span className="chip">{esc(PP_CATS[it.category]?.label || it.category)}</span>
                      {it.date_achieved ? (
                        <span className="small muted">{prettyDate(it.date_achieved)}</span>
                      ) : null}
                      {safeHttpUrl(it.certificate_url) ? (
                        <a
                          className="small"
                          href={safeHttpUrl(it.certificate_url)}
                          target="_blank"
                          rel="noopener noreferrer"
                        >
                          Certificate ↗
                        </a>
                      ) : null}
                    </div>
                    {Array.isArray(it.skills) && it.skills.length ? (
                      <div className="row pd-scopes mt">
                        {it.skills.map((sk, i) => <span key={`${sk}-${i}`} className="chip acc">{esc(String(sk))}</span>)}
                      </div>
                    ) : null}
                  </div>
                </article>
              ))}
            </div>
          </>
        ) : (
          <div className="card">
            <p className="small muted">
              Nothing added to their passport yet. Entries appear here as soon as {esc(name)} adds one.
            </p>
          </div>
        )}
      </div>

      <aside className="ln-rail">
        <div className="card ln-card">
          <div className="ln-card-head">
            <span className="ln-ico" aria-hidden="true">📕</span>
            <h3>Progress</h3>
          </div>
          <div className="pd-rail-big">{p.total}</div>
          <div className="dash-tile-sub">
            item{p.total === 1 ? "" : "s"} added · {p.verified} verified
          </div>
        </div>
        <div className="card ln-card">
          <p className="dash-tile-sub">
            Entries show what {esc(name)} chose to share here. They can turn this off
            any time from their own Parent access settings.
          </p>
        </div>
      </aside>
    </div>
  );
}

/* ------------------------------------------------------------ insights tabs */
function InterestsSection({ data }) {
  const interests = data.top_interests || [];
  const focus = data.focus_areas || [];
  return (
    <div className="ln-grid">
      <div className="ln-main">
        {data.novi_insight ? (
          <div className="focus-card pd-insight">
            <div className="focus-body">
              <span className="focus-lab">What Novi notices</span>
              <p className="focus-why" style={{ fontSize: 15 }}>{esc(data.novi_insight)}</p>
            </div>
          </div>
        ) : null}
        <Block title="Top interests" count={interests.length}>
          {interests.length ? <Chips items={interests} /> : <p className="small muted">Nothing shared yet.</p>}
        </Block>
        <Block title="Focus areas" count={focus.length}>
          {focus.length ? <Chips items={focus} accent={false} /> : <p className="small muted">Nothing shared yet.</p>}
        </Block>
      </div>
      <aside className="ln-rail">
        <div className="card ln-card">
          <div className="ln-card-head"><span className="ln-ico">✦</span><h3>Status</h3></div>
          <div className="dash-tile-sub">{esc(data.status || "No status shared yet")}</div>
        </div>
      </aside>
    </div>
  );
}

function CareersSection({ data }) {
  const zones = data.career_zones || [];
  const matches = data.top_career_matches || [];
  return (
    <div className="ln-grid">
      <div className="ln-main">
        <Block title="Career areas" count={zones.length}>
          {zones.length ? <Chips items={zones} /> : <p className="small muted">Nothing shared yet.</p>}
        </Block>
        <Block title="Career matches" count={matches.length}>
          {matches.length ? <Chips items={matches} accent={false} /> : <p className="small muted">Nothing shared yet.</p>}
        </Block>
      </div>
      <aside className="ln-rail">
        <div className="card ln-card">
          <div className="ln-card-head"><span className="ln-ico">◎</span><h3>Readiness</h3></div>
          <div className="pd-rail-big">
            {num(data.university_readiness) == null ? "—" : `${data.university_readiness}%`}
          </div>
          <div className="dash-tile-sub">From their top matches</div>
        </div>
      </aside>
    </div>
  );
}

function StrengthsSection({ data }) {
  const strengths = data.strengths || [];
  return (
    <div className="ln-grid">
      <div className="ln-main">
        <Block title="Strengths" count={strengths.length}>
          {strengths.length ? <Chips items={strengths} /> : <p className="small muted">Nothing shared yet.</p>}
        </Block>
      </div>
      <aside className="ln-rail">
        <div className="card ln-card">
          <div className="ln-card-head"><span className="ln-ico">◔</span><h3>Profile</h3></div>
          <div className="pd-rail-big">
            {num(data.profile_strength) == null ? "—" : `${data.profile_strength}%`}
          </div>
          <div className="dash-tile-sub">How much is filled in</div>
        </div>
      </aside>
    </div>
  );
}

/* ------------------------------------------------------------- memory tabs */
function GrowthSection({ data, name }) {
  if (!data) {
    return (
      <div className="card">
        <p className="small muted">No growth history to show yet.</p>
      </div>
    );
  }

  const milestones = data.completed_milestones || [];
  const trend = data.strength_trend || [];
  const change = num(data.trend_change);
  const done = num(data.milestones_completed);

  return (
    <div className="ln-grid">
      <div className="ln-main">
        <Block title="Confidence trend" count="Last 90 days">
          {trend.length >= 2 ? (
            <TrendChart points={trend} />
          ) : (
            <p className="small muted">
              Not enough history yet to draw a trend — a couple more check-ins and this
              fills in.
            </p>
          )}
        </Block>
        <Block title="Milestones" count={`${milestones.length} completed`}>
          {milestones.length ? (
            <Rows
              done
              items={milestones}
              render={(m, i) => (
                <>
                  <span className="dash-row-title">{esc(m.title)}</span>
                  {m.completed_at ? (
                    <span className="dash-row-meta">{prettyDate(m.completed_at)}</span>
                  ) : null}
                </>
              )}
            />
          ) : (
            <p className="small muted">No milestones completed yet.</p>
          )}
        </Block>
      </div>

      <aside className="ln-rail">
        <div className="card ln-card">
          <div className="ln-card-head"><span className="ln-ico">✦</span><h3>Totals</h3></div>
          <div className="pd-rail-big">{done ?? "—"}</div>
          <div className="dash-tile-sub">Milestones completed</div>
        </div>
        <div className="card ln-card">
          <div className="ln-card-head"><span className="ln-ico">↗</span><h3>Trend</h3></div>
          <div
            className="pd-rail-big"
            style={{ color: change === null ? undefined : ringColor(50 + change) }}
          >
            {change === null ? "—" : `${change > 0 ? "+" : ""}${change}`}
          </div>
          <div className="dash-tile-sub">Change in confidence</div>
        </div>
        <div className="card ln-card">
          <p className="dash-tile-sub">
            Milestones and confidence only — never {esc(name)}&apos;s conversations.
          </p>
        </div>
      </aside>
    </div>
  );
}

function TrendChart({ points }) {
  const W = 320;
  const H = 72;
  const PAD = 6;
  const values = points.map((p) => num(p.value) ?? 0);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;

  const x = (i) => PAD + (i * (W - PAD * 2)) / Math.max(1, points.length - 1);
  const y = (v) => H - PAD - ((v - min) / span) * (H - PAD * 2);
  const line = points.map((p, i) => `${x(i).toFixed(1)},${y(num(p.value) ?? 0).toFixed(1)}`).join(" ");
  const area = `${PAD},${H - PAD} ${line} ${x(points.length - 1).toFixed(1)},${H - PAD}`;

  return (
    <div className="card mt">
      <div className="stat-label">Confidence trend</div>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        width="100%"
        height={H}
        preserveAspectRatio="none"
        role="img"
        aria-label={`Confidence trend from ${values[0]} to ${values[values.length - 1]} over ${points.length} days`}
      >
        <polygon points={area} fill="var(--acc-soft, rgba(99,102,241,0.15))" />
        <polyline
          points={line}
          fill="none"
          stroke="var(--acc, #6366f1)"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
      <div className="between small muted">
        <span>{prettyDate(points[0].day)}</span>
        <span>{prettyDate(points[points.length - 1].day)}</span>
      </div>
    </div>
  );
}