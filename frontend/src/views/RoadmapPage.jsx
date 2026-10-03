import { useCallback, useEffect, useState } from "react";
import { api, bellTime, esc, prettyDate, ringColor, STAGE_META } from "../api";
import { useAuth } from "../auth";
import { EmptyState, Kicker, Pill, showLoader, toast } from "../ui";

let _rmGoalId = null, _rmTaskFilter = "all";

export default function RoadmapPage() {
  const { user } = useAuth();
  const [base, setBase] = useState(null); // {goals, priorities, tasks}
  const [goalId, setGoalId] = useState(_rmGoalId);
  const [taskFilter, setTaskFilter] = useState(_rmTaskFilter);
  const [roadmap, setRoadmap] = useState({ goal: null, stages: {}, progress_percent: 0 });
  const [error, setError] = useState(null);
  const [goalAddOpen, setGoalAddOpen] = useState(false);
  const [goalTitle, setGoalTitle] = useState("");
  const [goalCat, setGoalCat] = useState("career");
  const [taskTitle, setTaskTitle] = useState("");
  const [taskCat, setTaskCat] = useState("build");
  const [genText, setGenText] = useState("");
  const [prioBusy, setPrioBusy] = useState(false);

  useEffect(() => {
    let alive = true;
    showLoader(true);
    Promise.all([
      api("/roadmap/goals").catch(() => []),
      api("/roadmap/priorities").catch(() => []),
      api("/roadmap/tasks").catch(() => []),
    ])
      .then(([goals, priorities, tasks]) => {
        if (!alive) return;
        const activeGoals = (goals || []).filter((g) => g.status === "active");
        setBase({ goals: goals || [], priorities: priorities || [], tasks: tasks || [] });
        if (_rmGoalId && activeGoals.some((g) => String(g.id) === String(_rmGoalId))) {
          // keep current selection
        } else {
          _rmGoalId = activeGoals.length ? activeGoals[0].id : null;
          setGoalId(_rmGoalId);
        }
      })
      .catch((ex) => { if (alive) setError(ex.message); })
      .finally(() => showLoader(false));
    return () => { alive = false; };
  }, []);

  const loadRoadmap = useCallback(async (gid) => {
    const rm = await api("/roadmap" + (gid ? `?goal_id=${gid}` : "")).catch(() => ({ goal: null, stages: {}, progress_percent: 0 }));
    setRoadmap(rm);
  }, []);

  useEffect(() => { if (base) loadRoadmap(goalId); }, [base, goalId]);

  if (error) return <EmptyState title="Roadmap unavailable" sub={error} />;
  if (!base) return null;

  const goals = base.goals || [];
  const priorities = base.priorities || [];
  const tasks = base.tasks || [];
  const activeGoals = goals.filter((g) => g.status === "active");
  const stages = roadmap.stages || {};
  const shortTerm = roadmap.short_term || [];
  const gradeKeys = Object.keys(stages).filter((g) => (stages[g] || []).length).sort((a, b) => Number(a) - Number(b));
  const allItems = [...shortTerm, ...gradeKeys.flatMap((g) => stages[g])];
  const doneCount = allItems.filter((i) => i.completed).length;
  const pct = Math.round(roadmap.progress_percent || 0);
  const prioDone = priorities.filter((p) => p.completed).length;
  const taskDone = tasks.filter((t) => t.status === "done").length;
  const goal = roadmap.goal || null;
  const firstName = ((user?.first_name || user?.name || "there")).split(" ")[0];

  const reload = async ({ msg, keepScroll = true } = {}) => {
    const y = keepScroll ? window.scrollY : 0;
    showLoader(true);
    try {
      await loadRoadmap(goalId);
      window.scrollTo(0, keepScroll ? y : 0);
      if (msg) toast(msg);
    } catch (_) {}
    showLoader(false);
  };

  const addGoal = async () => {
    const t = goalTitle.trim();
    if (!t) return;
    showLoader(true);
    try {
      const g = await api("/roadmap/goals", { method: "POST", body: JSON.stringify({ title: t, category: goalCat }) });
      _rmGoalId = g.id; setGoalId(g.id);
      const [g2, p2, t2] = await Promise.all([api("/roadmap/goals").catch(() => []), api("/roadmap/priorities").catch(() => []), api("/roadmap/tasks").catch(() => [])]);
      setBase({ goals: g2, priorities: p2, tasks: t2 });
      setGoalTitle("");
      setGoalAddOpen(false);
      toast("Goal added — generate its roadmap when you're ready ✨");
    } catch (ex) { toast(ex.message); }
    finally { showLoader(false); }
  };

  const selectGoal = (id) => {
    _rmGoalId = id;
    setGoalId(id);
    loadRoadmap(id);
  };

  const generate = async (fromText) => {
    showLoader(true);
    try {
      const body = fromText
        ? { goal_id: goalId, text: genText.trim() }
        : { goal_id: goalId };
      await api("/roadmap/generate", { method: "POST", body: JSON.stringify(body) });
      await reload({ msg: "Roadmap generated 🌱", keepScroll: false });
    } catch (ex) { toast(ex.message); }
    finally { showLoader(false); }
  };

  const markGoal = async (status) => {
    if (!window.confirm(status === "done" ? "Mark this goal as done?" : "Cancel this goal? Its roadmap items will be removed.")) return;
    try { await api(`/roadmap/goals/${goalId}`, { method: "PATCH", body: JSON.stringify({ status }) }); if (status === "cancelled") { _rmGoalId = null; setGoalId(null); } toast(status === "done" ? "Goal complete — congratulations 🎉" : "Goal cancelled"); await reload({ keepScroll: false }); }
    catch (ex) { toast(ex.message); }
  };

  const toggleTask = async (id, checked) => {
    try {
      await api(`/roadmap/tasks/${id}`, { method: "PATCH", body: JSON.stringify({ status: checked ? "done" : "active" }) });
      await reload({ msg: "Task updated ✓" });
    } catch (ex) { toast(ex.message, "err"); }
  };

  const togglePrio = async (id) => {
    try {
      await api(`/roadmap/priorities/${id}`, { method: "PATCH" });
      await reload({ msg: "Priority updated ✓" });
    } catch (ex) { toast(ex.message, "err"); }
  };

  const toggleItem = async (id) => {
    try {
      await api(`/roadmap/items/${id}`, { method: "PATCH" });
      await reload({ msg: "Step updated ✓" });
    } catch (ex) { toast(ex.message, "err"); }
  };

  const genPriorities = async () => {
    setPrioBusy(true);
    try { await api("/roadmap/priorities/generate", { method: "POST", body: JSON.stringify({}) }); await reload({ msg: "Priorities refreshed for this week ✨" }); }
    catch (ex) { toast(ex.message); }
    setPrioBusy(false);
  };

  const addTask = async () => {
    const t = taskTitle.trim();
    if (!t) return;
    showLoader(true);
    try { await api("/roadmap/tasks", { method: "POST", body: JSON.stringify({ title: t, category: taskCat }) }); setTaskTitle(""); await reload({ msg: "Task added ✓" }); }
    catch (ex) { toast(ex.message); }
    finally { showLoader(false); }
  };

  const gradeBlock = (grade) => {
    const items = stages[grade];
    const meta = STAGE_META[items[0]?.stage] || { icon: "🎯", label: "Your journey" };
    const gd = items.filter((i) => i.completed).length;
    const gp = items.length ? Math.round((gd / items.length) * 100) : 0;
    return (
      <div className="tl-grade" key={grade}>
        <div className="tl-grade-head">
          <div className="tl-grade-ico">{meta.icon}</div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div className="tl-grade-name">Grade {esc(String(grade))} · {esc(meta.label)}</div>
            <div className="tl-grade-sub small muted">{meta.desc || "Grow one step at a time."}</div>
          </div>
          <div className="tl-grade-pct"><b style={{ color: ringColor(gp) }}>{gp}%</b><span className="muted small">{gd}/{items.length}</span></div>
        </div>
        <div className="progress-track tl-progress"><div className="progress-fill" style={{ width: `${gp}%` }} /></div>
        <div className="tl-items">
          {items.map((it) => (
            <div className={`rm-item ${it.completed ? "done" : ""}`} key={it.id}>
              <label className="rm-check" title={it.completed ? "Mark as not done" : "Mark done"}>
                <input type="checkbox" checked={!!it.completed} onChange={() => toggleItem(it.id)} />
                <span className="rm-checkbox">✓</span>
              </label>
              <div className="rm-body">
                <div className="rm-top">
                  <b>{esc(it.title)}</b>
                  <span className={`rm-stage stage-${esc(it.stage)}`}>{esc(it.stage)}</span>
                  {it.completed ? <span className="pill good">done</span> : null}
                </div>
                {it.description ? <p className="small muted rm-desc">{esc(it.description)}</p> : null}
              </div>
            </div>
          ))}
        </div>
      </div>
    );
  };

  const prioRows = priorities.map((p) => (
    <div className={`prio-row ${p.completed ? "done" : ""}`} key={p.id}>
      <label className="rm-check" title="Toggle priority"><input type="checkbox" checked={!!p.completed} onChange={() => togglePrio(p.id)} /><span className="rm-checkbox">✓</span></label>
      <div className="prio-body">
        <b>{esc(p.title)}</b>
        <div className="small muted">{esc(p.skill_category)}{p.minutes ? " · " + p.minutes + " min" : ""}</div>
      </div>
    </div>
  ));

  const shownTasks = tasks.filter((t) => taskFilter === "all" ? true : taskFilter === "done" ? t.status === "done" : t.status !== "done");
  const taskRows = shownTasks.map((t) => (
    <div className={`task-row ${t.status === "done" ? "done" : ""}`} key={t.id}>
      <label className="rm-check" title="Toggle task"><input type="checkbox" checked={t.status === "done"} onChange={(e) => toggleTask(t.id, e.target.checked)} /><span className="rm-checkbox">✓</span></label>
      <div className="prio-body">
        <b>{esc(t.title)}</b>
        <div className="small muted">{esc(t.category)}{t.due_date ? " · due " + prettyDate(t.due_date) : ""}</div>
      </div>
    </div>
  ));

  return (
    <>
      <div className="hero">
        <Kicker>{`Good ${bellTime()}, ${firstName} · your plan, sequenced`}</Kicker>
        <h1>My <span className="grad">Roadmap</span></h1>
        <p>Goals become a grade-by-grade roadmap. Tick steps off — Novi carries your momentum forward.</p>
      </div>
      <div className="stats-strip">
        <div className="stat-mini"><span className="sm-ico">🎯</span><div><b>{activeGoals.length}</b><span>active goals</span></div></div>
        <div className="stat-mini"><span className="sm-ico">🗺️</span><div><b style={{ color: ringColor(pct) }}>{pct}%</b><span>roadmap done</span></div></div>
        <div className="stat-mini"><span className="sm-ico">✅</span><div><b>{prioDone}/{priorities.length}</b><span>priorities</span></div></div>
        <div className="stat-mini"><span className="sm-ico">📋</span><div><b>{taskDone}/{tasks.length}</b><span>tasks done</span></div></div>
      </div>

      <div className="rm-layout">
        <div className="rm-main">
          <div className="card mb">
            <div className="between">
              <h2>Goals</h2>
              <span className="pill mid">{activeGoals.length} active</span>
            </div>
            <div className="goal-tabs mt">
              {activeGoals.map((g) => (
                <button key={g.id} className={`goal-tab ${String(g.id) === String(goalId) ? "on" : ""}`} onClick={() => selectGoal(g.id)}>
                  <span className="gt-title">{esc(g.title)}</span>
                  <span className="pill">{esc(g.category)}</span>
                </button>
              ))}
              <button className="goal-tab add" id="goal-add-toggle" onClick={() => setGoalAddOpen((o) => !o)}>＋ New goal</button>
            </div>
            {goalAddOpen ? (
              <div id="goal-add-box" className="goal-add">
                <input id="goal-title" placeholder="e.g. Get into a top AI university" style={{ flex: 1, minWidth: 220 }} value={goalTitle} onChange={(e) => setGoalTitle(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter") addGoal(); }} />
                <select id="goal-cat" value={goalCat} onChange={(e) => setGoalCat(e.target.value)}><option value="career">Career</option><option value="university">University</option></select>
                <button className="btn" id="add-goal" onClick={addGoal}>Add</button>
                <button className="btn-ghost" id="goal-add-cancel" onClick={() => setGoalAddOpen(false)}>Cancel</button>
              </div>
            ) : null}
          </div>

          <div className="card rm-head">
            <div className="between">
              <div style={{ minWidth: 0 }}>
                {goal ? (
                  <>
                    <div className="rm-head-title"><h2>{esc(goal.title)}</h2><Pill label={esc(goal.category)} tone="mid" />{goal.status === "active" ? null : <Pill label={esc(goal.status)} tone="good" />}</div>
                    <div className="small muted mt">{doneCount} of {allItems.length} steps completed{goal.description ? " · " + esc(goal.description) : ""}</div>
                  </>
                ) : <><h2>Your combined journey</h2><div className="small muted mt">{doneCount} of {allItems.length} steps completed across all goals</div></>}
              </div>
              {goal && goal.status === "active" ? (
                <>
                  <div className="row">
                    {allItems.length ? <button className="btn-ghost small" style={{ color: "var(--bad)" }} onClick={() => markGoal("cancelled")}>delete</button> : null}
                    <button className="btn-ghost" onClick={() => markGoal("done")}>Mark done</button>
                    <button className="btn" onClick={() => generate(false)}>✨ Generate roadmap</button>
                  </div>
                  <div className="row mt gen-box">
                    <input
                      id="roadmap-text"
                      value={genText}
                      placeholder="What do you want? e.g. build an AI project and get into a top engineering college"
                      onChange={(e) => setGenText(e.target.value)}
                      onKeyDown={(e) => { if (e.key === "Enter") generate(true); }}
                      style={{ flex: 1, minWidth: 200 }}
                    />
                    <button className="btn" onClick={() => generate(true)} disabled={!genText.trim()}>⚡ Make my plan</button>
                  </div>
                </>
              ) : null}
            </div>
            {allItems.length ? (
              <div className="row between mt">
                <div className="progress-track" style={{ flex: 1 }}><div className="progress-fill" style={{ width: `${pct}%` }} /></div>
                <b style={{ color: ringColor(pct) }}>{pct}%</b>
              </div>
            ) : null}
          </div>

          {shortTerm.length ? (
            <div className="card" id="short-term-block">
              <div className="between">
                <div>
                  <h2>⚡ Short-term · do this now</h2>
                  <div className="small muted mt">{shortTerm.filter((i) => i.completed).length} of {shortTerm.length} short-term steps done</div>
                </div>
                <span className="pill mid">now</span>
              </div>
              <div className="tl-items mt">
                {shortTerm.map((it) => (
                  <div className={`rm-item ${it.completed ? "done" : ""}`} key={it.id}>
                    <label className="rm-check" title={it.completed ? "Mark as not done" : "Mark done"}>
                      <input type="checkbox" checked={!!it.completed} onChange={() => toggleItem(it.id)} />
                      <span className="rm-checkbox">✓</span>
                    </label>
                    <div className="rm-body">
                      <div className="rm-top">
                        <b>{esc(it.title)}</b>
                        <span className={`rm-stage stage-${esc(it.stage)}`}>{esc(it.stage)}</span>
                        {it.completed ? <span className="pill good">done</span> : null}
                      </div>
                      {it.description ? <p className="small muted rm-desc">{esc(it.description)}</p> : null}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ) : null}

          {gradeKeys.length ? (
            <>
              <div className="timeline">{gradeKeys.map(gradeBlock)}</div>
              <div className="legend-row">
                {Object.entries(STAGE_META).map(([k, v]) => <span className={`rm-stage stage-${k}`} key={k}>{v.icon} {esc(v.label)}</span>)}
              </div>
            </>
          ) : (goal ? (
            <div className="card">
              <div className="between"><h3>No roadmap yet</h3><button className="btn" onClick={generate}>✨ Generate your roadmap</button></div>
              <p className="small muted mt">Tell Novi your goal and it will map out a grade-by-grade plan in seconds.</p>
            </div>
          ) : (
            <div className="card"><h3>Set your first goal to start your map</h3><p className="small muted mt">Tap <b>＋ New goal</b> above, then generate its roadmap.</p></div>
          ))}
        </div>

        <div className="rm-side">
          <div className="card">
            <div className="between"><h2>This week</h2><span className="pill mid">{prioDone}/{priorities.length}</span></div>
            <p className="small muted mt">Priorities crafted for this week by Novi.</p>
            <button className="btn mt" id="prio-gen" disabled={prioBusy} onClick={genPriorities}>{prioBusy ? "Thinking…" : "✨ Generate with AI"}</button>
            <div id="prio-list" className="mt">
              {priorities.length ? prioRows : <p className="small muted">No priorities yet — generate some above.</p>}
            </div>
          </div>

          <div className="card">
            <div className="between"><h2>Tasks</h2><span className="pill mid">{taskDone}/{tasks.length}</span></div>
            <div className="row mt">
              <input id="task-title" placeholder="New task…" style={{ flex: 1 }} value={taskTitle} onChange={(e) => setTaskTitle(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter") addTask(); }} />
              <select id="task-cat" style={{ width: "auto" }} value={taskCat} onChange={(e) => setTaskCat(e.target.value)}><option>build</option><option>explore</option><option>grow</option></select>
              <button className="btn" id="add-task" onClick={addTask}>Add</button>
            </div>
            <div className="filter-tabs mt">
              {[["all", `All · ${tasks.length}`], ["active", "Active"], ["done", `Done · ${taskDone}`]].map(([k, l]) => (
                <button key={k} className={`ft ${taskFilter === k ? "on" : ""}`} onClick={() => { _rmTaskFilter = k; setTaskFilter(k); }}>{l}</button>
              ))}
            </div>
            <div id="task-list" className="mt">
              {shownTasks.length ? taskRows : <p className="small muted">No tasks match this filter.</p>}
            </div>
          </div>
        </div>
      </div>
    </>
  );
}