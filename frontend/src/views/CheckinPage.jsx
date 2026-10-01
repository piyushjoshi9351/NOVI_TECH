import { useEffect, useState } from "react";
import { api, getDnaContext, MOODS, moodIcon } from "../api";
import { EmptyState, Kicker, Pill, showLoader, toast } from "../ui";
import ContributionHeatmap from "./checkin/ContributionHeatmap";
import PlannerPage from "./planner/PlannerPage";
import "./checkin.css";

const CK_FIELDS = [
  ["accomplishments", "What did you accomplish this week?", "e.g. Finished my Python project"],
  ["learnings", "What did you learn?", "e.g. Pandas for data analysis"],
  ["challenges", "What was challenging?", "e.g. Balancing tests and coding"],
  ["pride", "What are you proud of?", "e.g. Led a team demo"],
  ["next_week", "What would you like to do better next week?", "e.g. Start my AI project proposal"],
];

function countItems(value) {
  if (!value) return 0;
  return String(value).split(",").map((s) => s.trim()).filter(Boolean).length;
}

export default function CheckinPage() {
  const [dctx, setDctx] = useState(null);
  const [cur, setCur] = useState(null);
  const [draft, setDraft] = useState({});
  const [error, setError] = useState(null);
  const [showPlanner, setShowPlanner] = useState(false);

  const load = () =>
    Promise.all([getDnaContext(), api("/checkins/current")]).then(([d, c]) => {
      setDctx(d);
      setCur(c);
      const dr = {};
      ["accomplishments", "learnings", "challenges", "pride", "next_week", "energy"].forEach((k) => {
        if (c[k]) dr[k] = c[k];
      });
      if (c.mood) dr.mood = c.mood;
      setDraft(dr);
    });

  

  useEffect(() => {
    let alive = true;
    showLoader(true);
    load()
      .catch((ex) => { if (alive) setError(ex.message); })
      .finally(() => showLoader(false));
    return () => { alive = false; };
  }, []);

  if (error) return <EmptyState title="Check-in unavailable" sub={error} />;
  if (!cur) return null;

  const ai = cur.ai_summary && typeof cur.ai_summary === "object" ? cur.ai_summary : null;
  const stats = {
    wins: ai && Number.isFinite(ai.wins) ? ai.wins : countItems(draft.accomplishments),
    skills: ai && Array.isArray(ai.new_skills) ? ai.new_skills.length : countItems(draft.learnings),
    milestones: ai && Array.isArray(ai.milestones) ? ai.milestones.length : 0,
    priorities: ai && Array.isArray(ai.priorities_next_week) ? ai.priorities_next_week.length : countItems(draft.next_week),
  };

  const set = (k, v) => setDraft((d) => ({ ...d, [k]: v }));

  const collect = () => {
    const p = {};
    Object.entries(draft).forEach(([k, v]) => {
      if (v === "" || v === undefined || v === null) return;
      p[k] = k === "mood" ? v : k === "energy" ? Number(v) : String(v);
    });
    return p;
  };

  const save = async () => {
    showLoader(true);
    try {
      await api("/checkins", { method: "POST", body: JSON.stringify(collect()) });
      await load();
      toast("Check-in saved ✓");
    } catch (ex) {
      toast(ex.message);
    } finally {
      showLoader(false);
    }
  };

  const summarize = async () => {
    showLoader(true);
    try {
      await api("/checkins/summarize", { method: "POST" });
      await load();
      toast("Week summarised ✨");
    } catch (ex) {
      toast(ex.message);
    } finally {
      showLoader(false);
    }
  };

  return (
    <>
      <div className="hero">
        <Kicker>Your weekly pulse</Kicker>
        <h1>Weekly Check-in</h1>
        <p>Your weekly pulse with Novi — honest answers make your mentoring sharper.</p>
      </div>
      <div className="novi-box ck-novi">
        <span className="novi-avatar">N</span>
        <div className="ck-novi-copy">
          <b>Novi</b>
          <p>Hey! Let’s look back at your week.</p>
        </div>
      </div>

      <div className="card mb">
        <div className="between">
          <h2>Week of {cur.week_start || ""}</h2>
          {cur.status ? <Pill label={cur.status} tone="mid" /> : null}
        </div>
      </div>

      <ContributionHeatmap />

      <div className="checkin-grid">
        {CK_FIELDS.map(([k, l, ph]) => (
          <div className="card" key={k}>
            <h3>{l}</h3>
            <textarea
              className="mt"
              style={{ minHeight: 110 }}
              placeholder={ph}
              value={draft[k] || ""}
              onChange={(e) => set(k, e.target.value)}
            />
          </div>
        ))}
        <div className="card">
          <h3>Mood</h3>
          <div className="mood-grid mt">
            {Object.keys(MOODS).map((m) => (
              <button key={m} type="button" className={`mood-btn ${draft.mood === m ? "on" : ""}`} onClick={() => set("mood", m)}>
                {moodIcon(m)} {m}
              </button>
            ))}
          </div>
        </div>
        <div className="card">
          <h3>Energy (1-10)</h3>
          <input type="number" min="1" max="10" className="mt" value={draft.energy || ""} onChange={(e) => set("energy", e.target.value)} />
        </div>
      </div>

      <div className="row mt">
        <button className="btn" onClick={save}>Save check-in</button>
        <button className="btn-ghost" onClick={summarize}>Summarize with AI</button>
      </div>

      <div className="ck-summary">
        <div className="ck-summary-head">
          <span className="novi-avatar">N</span>
          <div>
            <h2>Your Week with Novi</h2>
            <p>{ai?.dna_alignment || "Answer the questions above and Novi will turn them into your week in review."}</p>
          </div>
        </div>

        <div className="ck-stats">
          <div className="ck-stat"><b>{stats.wins}</b><span>{stats.wins === 1 ? "win" : "wins"}</span></div>
          <div className="ck-stat"><b>{stats.skills}</b><span>new {stats.skills === 1 ? "skill" : "skills"}</span></div>
          <div className="ck-stat"><b>{stats.milestones}</b><span>{stats.milestones === 1 ? "milestone completed" : "milestones completed"}</span></div>
          <div className="ck-stat"><b>{stats.priorities}</b><span>{stats.priorities === 1 ? "priority for next week" : "priorities for next week"}</span></div>
        </div>

        <button className="ck-cta" onClick={() => setShowPlanner((v) => !v)}>
          {showPlanner ? "Hide My Planner" : "See My Progress →"}
        </button>
      </div>

      {showPlanner ? (
        <div className="ck-planner">
          <PlannerPage />
        </div>
      ) : null}
    </>
  );
}