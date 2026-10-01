import { useCallback, useEffect, useState } from "react";
import { Check, RefreshCw } from "lucide-react";
import { api } from "../../api";

const DOW = ["Mon", "", "Wed", "", "Fri", "", "Sun"];
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

function isoToday() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

/* Month label per week column: shown on the first column whose Monday falls in a
   new month, so labels never repeat or collide. */
function monthLabels(weeks) {
  return weeks.map((w) => {
    const first = w.days?.[0]?.date;
    if (!first) return "";
    const [y, m] = first.split("-").map(Number);
    if (m < 1 || m > 12) return "";
    return MONTHS[m - 1];
  });
}

function yearLabels(weeks) {
  return weeks.map((w, i) => {
    const first = w.days?.[0]?.date;
    if (!first) return "";
    const year = first.slice(0, 4);
    const prevYear = weeks[i - 1]?.days?.[0]?.date?.slice(0, 4);
    return year !== prevYear ? year : "";
  });
}

const LEVELS = [0, 1, 2, 3, 4];

const KIND_LABEL = {
  "check-in": "Daily check-in",
  chat: "Chat with Novi",
  blocks: "Planner blocks",
};

function cellLabel(cell) {
  if (cell.level === 0) return "No activity";
  const kinds = (cell.kind || "").split("+").filter(Boolean);
  if (!kinds.length) return "Activity";
  return kinds.map((k) => KIND_LABEL[k] || k).join(" + ");
}

/* Range selector. The year view is the GitHub look but reads as broken empty
   space for a new account, so the default is six months. */
const RANGES = [
  { label: "3 months", weeks: 13 },
  { label: "6 months", weeks: 26 },
  { label: "Year", weeks: 53 },
];

export default function ContributionHeatmap({ weeks: initialWeeks = 26, onSelectDate }) {
  const [weeks, setWeeks] = useState(initialWeeks);
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [tip, setTip] = useState(null);
  const [busy, setBusy] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let alive = true;
    setBusy(true);
    setError(null);
    api(`/checkins/graph?weeks=${weeks}`, { fresh: reloadKey > 0 })
      .then((d) => { if (alive) setData(d); })
      .catch((ex) => { if (alive) setError(ex.message); })
      .finally(() => { if (alive) setBusy(false); });
    return () => { alive = false; };
  }, [weeks, reloadKey]);

  const refresh = useCallback(() => setReloadKey((n) => n + 1), []);

  /* The tooltip is position:fixed, so viewport rects are what it needs. */
  const showTip = (cell, el) => {
    const r = el.getBoundingClientRect();
    setTip({
      title: cellLabel(cell),
      note: cell.note || "",
      left: r.left + r.width / 2,
      top: r.top,
    });
  };

  if (error) {
    return (
      <div className="card gh-card">
        <div className="gh-head">
          <h2>Your activity</h2>
        </div>
        <p className="gh-hint">Could not load your activity grid: {error}</p>
        <button className="btn-ghost" onClick={refresh}>Try again</button>
      </div>
    );
  }

  if (!data) return null;

  const grid = data.weeks || [];
  const s = data.stats || {};
  const noActivity = (s.active_days || 0) === 0;
  const months = monthLabels(grid);
  const years = yearLabels(grid);
  const today = isoToday();
  let cellIndex = 0;

  const clickCell = (cell) => {
    if (onSelectDate) onSelectDate(cell.date);
  };

  return (
    <div className="card gh-card">
      <div className="gh-head">
        <div>
          <div className="gh-title-row">
            <h2>Your activity</h2>
            <button
              type="button"
              className="gh-refresh"
              onClick={refresh}
              disabled={busy}
              aria-label="Refresh activity grid"
              title="Refresh"
            >
              <RefreshCw size={13} className={busy ? "spin" : ""} />
            </button>
          </div>
          <p className="gh-sub">Green means you checked in, chatted, or finished a block that day.</p>
        </div>
        <div className="gh-tools">
          <div className="gh-ranges" role="tablist" aria-label="Time range">
            {RANGES.map((r) => (
              <button
                key={r.weeks}
                type="button"
                role="tab"
                aria-selected={weeks === r.weeks}
                className={`gh-range${weeks === r.weeks ? " on" : ""}`}
                onClick={() => setWeeks(r.weeks)}
              >
                {r.label}
              </button>
            ))}
          </div>
          <div className="gh-stats">
            <div className="gh-stat"><b>{s.current_streak || 0}</b><span>streak</span></div>
            <div className="gh-stat"><b>{s.best_streak || 0}</b><span>best</span></div>
            <div className="gh-stat"><b>{s.active_days || 0}</b><span>active days</span></div>
            <div className="gh-stat"><b>{s.weekly_done || 0}</b><span>weeks done</span></div>
          </div>
          </div>
      </div>

      <div className="gh-wrap">
        <div className="gh-years" style={{ "--gh-weeks": grid.length }}>
          {years.map((y, i) => <span className="gh-year" key={`y-${i}`}>{y}</span>)}
        </div>
        <div className="gh-months" style={{ "--gh-weeks": grid.length }}>
          {months.map((m, i) => <span className={`gh-month${m.length > 2 ? " long" : ""}`} key={`m-${i}`}>{m}</span>)}
        </div>

        <div className="gh-body" onMouseLeave={() => setTip(null)}>
          <div className="gh-days" aria-hidden="true">
            {DOW.map((d, i) => <span key={`d-${i}`}>{d}</span>)}
          </div>

          <div className="gh-grid" style={{ "--gh-weeks": grid.length }} role="grid" aria-label="Check-in activity by day">
            {grid.map((wk, wi) => (
              <div key={wk.week_start || wi} style={{ display: "contents" }} role="row">
                {(wk.days || []).map((cell) => {
                  const i = cellIndex++;
                  const future = cell.date > today;
                  const cls = [
                    "gh-cell",
                    cell.level > 0 ? `l${cell.level}` : "",
                    cell.date === today ? "gh-today" : "",
                    future ? "gh-future" : "",
                  ].filter(Boolean).join(" ");
                  return (
                    <span
                      key={cell.date}
                      className={cls}
                      style={{ "--i": i }}
                      role="gridcell"
                      tabIndex={0}
                      aria-label={
                        future
                          ? `${cell.date}: upcoming`
                          : `${cell.date}: ${cellLabel(cell)}${cell.level > 0 ? ` (level ${cell.level} of 4)` : ""}`
                      }
                      onMouseEnter={(e) => showTip(cell, e.currentTarget)}
                      onFocus={(e) => showTip(cell, e.currentTarget)}
                      onBlur={() => setTip(null)}
                      onClick={() => !future && clickCell(cell)}
                    />
                  );
                })}
              </div>
            ))}
          </div>

          <div
            className="gh-pop"
            style={tip ? { opacity: 1, left: tip.left, top: tip.top, transform: "translate(-50%, -100%) translateY(-8px)" } : undefined}
          >
            {tip ? (
              <>
                <b>{tip.title}</b>
                <span>{tip.note}</span>
              </>
            ) : null}
          </div>
        </div>
      </div>

      <div className="gh-wk-label">Weekly reflections</div>
      <div className="gh-wk-row">
        {grid.map((wk, wi) => (
          <span
            key={`wk-${wk.week_start || wi}`}
            className={`gh-week-dot${wk.weekly_done ? " on" : ""}`}
            title={wk.weekly_done ? `Week of ${wk.week_start} · reflection submitted` : `Week of ${wk.week_start} · no reflection`}
            aria-label={`Week of ${wk.week_start}: ${wk.weekly_done ? "reflection submitted" : "no reflection"}`}
          >
            {wk.weekly_done ? <Check size={11} strokeWidth={3} /> : null}
          </span>
        ))}
      </div>

      <div className="gh-legend">
        <span className="small">Less</span>
        {LEVELS.map((l) => <span className={`gh-cell${l > 0 ? ` l${l}` : ""}`} key={l} />)}
        <span className="small">More</span>
      </div>

      <p className="gh-hint">
          {noActivity ? (
            <>
              Nothing here yet. Your squares start filling the day you check in, chat with Novi, or finish a
              planner block.
            </>
          ) : (
            <>
              A square turns green on a day you completed a daily check-in, sent Novi a message, or finished a
              planner block. Darker means more activity.
            </>
          )}
        </p>
    </div>
  );
}