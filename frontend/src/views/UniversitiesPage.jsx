import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { api, esc, getDnaContext, ringColor } from "../api";
import { EmptyState, Kicker, showLoader, toast } from "../ui";

export default function UniversitiesPage() {
  const router = useRouter();
  const [dctx, setDctx] = useState(null);
  const [meta, setMeta] = useState({ filters: { countries: [], courses: [], subjects: [], university_types: [], bounds: {} } });
  const [rows, setRows] = useState([]);
  const [recommended, setRecommended] = useState([]);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState("");
  const [aiAnswer, setAiAnswer] = useState("");

  // filter inputs (single source of truth)
  const [vals, setVals] = useState({ country: "", course: "", subject: "", university_type: "", min_rank: "", max_fees: "", entry_query: "", scholarships: false });
  const [applied, setApplied] = useState([]); // [{key,label}] shown as chips
  const [countMsg, setCountMsg] = useState(null);
  const [gridExtra, setGridExtra] = useState(null); // relaxed/empty card element
  const [results, setResults] = useState([]);

  const debounceTimer = useRef(null);

  useEffect(() => {
    let alive = true;
    showLoader(true);
    Promise.all([
      getDnaContext(),
      api("/universities/filters"),
      api("/universities?limit=30"),
      api("/universities/recommended").catch(() => []),
    ])
      .then(([d, f, r, rec]) => {
        if (!alive) return;
        setDctx(d);
        setMeta({ filters: f });
        setRows(r || []);
        setResults(r || []);
        setRecommended(rec || []);
        setCountMsg(`Showing ${(r || []).length} universities`);
      })
      .catch((ex) => { if (alive) setError(ex.message); })
      .finally(() => showLoader(false));
    return () => { alive = false; clearTimeout(debounceTimer.current); };
  }, []);

  if (error) return <EmptyState title="Universities unavailable" sub={error} />;
  if (!rows) return null;

  const filters = meta.filters || {};
  const fmt = (n) => Number(n).toLocaleString("en-US");
  const rb = (filters.bounds || {}).ranking || { max: 50 };
  const fb = (filters.bounds || {}).fees || { max: 50000 };
  const rankSteps = (() => { const out = []; for (let n = 10; n < rb.max; n += 10) out.push(n); out.push(rb.max); return out; })();
  const feeSteps = (() => { const out = []; for (let n = 5000; n < fb.max; n += 5000) out.push(n); out.push(fb.max); return out; })();
  const opts = (valsList) => [<option key="all" value="">All</option>, ...(valsList || []).map((c, i) => <option key={`${c}-${i}`} value={c}>{c}</option>)];

  const uniCard = (u) => {
    const courses = u.courses || [];
    const extra = courses.filter((c) => c !== u.course);
    return (
      <div key={u.slug} className="card list-item u-card" data-slug={u.slug} style={{ cursor: "pointer" }} onClick={() => router.push(`/university/${u.slug}`)}>
        <div className="between"><h3>{esc(u.name)}</h3><span className={`pill ${u.ranking <= 10 ? "good" : "mid"}`}>#{u.ranking || "—"}</span></div>
        <p className="small mt"><b>{esc(u.course)}</b> · {esc(u.city)}, {esc(u.country)}</p>
        {courses.length > 1 ? (
          <div className="u-courses">
            <span className="tag">{courses.length} courses</span>
            {extra.slice(0, 2).map((c) => <span className="tag tag-soft" key={c}>{esc(c)}</span>)}
            {extra.length > 2 ? <span className="tag tag-soft">+{extra.length - 2} more</span> : null}
          </div>
        ) : null}
        <div className="u-tags">
          <span className="tag">{esc(u.university_type || "")}</span>
          <span className="tag">{u.fees_per_year ? "~$" + fmt(u.fees_per_year) + "/yr" : "Fees vary"}</span>
          {u.scholarships ? <span className="tag tag-good">Scholarships</span> : null}
        </div>
      </div>
    );
  };

  const uniReadinessCard = (m) => (
    <div key={m.university?.slug || m.id} className="card list-item" style={{ cursor: "pointer" }} onClick={() => m.university?.slug && router.push(`/university/${m.university.slug}`)}>
      <div className="between"><h3>{esc((m.university || {}).name || "")}</h3><span className="pill mid">#{(m.university || {}).ranking || "—"}</span></div>
      <div className="row mt"><div className="progress-track" style={{ flex: 1 }}><div className="progress-fill" style={{ width: `${m.readiness}%`, background: ringColor(m.readiness) }} /></div><b style={{ color: ringColor(m.readiness) }}>{Math.round(m.readiness)}%</b></div>
      {m.reason ? <p className="small muted mt">{esc(m.reason)}</p> : null}
    </div>
  );

  const uniCombos = (n, k) => {
    const out = [], cur = [];
    const walk = (start) => {
      if (cur.length === k) { out.push([...cur]); return; }
      for (let i = start; i < n; i++) { cur.push(i); walk(i + 1); cur.pop(); }
    };
    walk(0);
    return out;
  };

  const uniClosest = async (activeList, params) => {
    let tries = 0;
    for (let size = 1; size <= Math.min(activeList.length, 3); size++) {
      let best = null;
      for (const combo of uniCombos(activeList.length, size)) {
        if (++tries > 60) break;
        const p = new URLSearchParams(params); combo.forEach((i) => p.delete(activeList[i].key));
        let r = [];
        try { r = await api(`/universities?${p}`); } catch (_) {}
        if (r.length && (!best || r.length > best.rows.length)) best = { removed: combo.map((i) => activeList[i]), rows: r };
      }
      if (best) return best;
      if (tries > 60) break;
    }
    return null;
  };

  const setVal = (key, value) => setVals((v) => ({ ...v, [key]: value }));

  const applyFilters = async (nextVals) => {
    const params = new URLSearchParams({ limit: "30" });
    const active = [];
    const push = (key, param, value, label) => { params.set(param, value); active.push({ key, label }); };

    const cty = nextVals.country, crs = nextVals.course.trim(), sub = nextVals.subject,
      typ = nextVals.university_type, rk = nextVals.min_rank, fe = nextVals.max_fees;
    const en = nextVals.entry_query.trim();
    const sc = nextVals.scholarships;
    if (cty) push("country", "country", cty, cty);
    if (crs) push("course", "course", crs, crs);
    if (sub) push("subject", "subject", sub, sub);
    if (typ) push("university_type", "university_type", typ, typ);
    if (rk) push("min_rank", "min_rank", rk, "Top " + rk);
    if (fe) push("max_fees", "max_fees", fe, "Under $" + fmt(Number(fe)));
    if (en) push("entry_query", "entry_query", en, `“${en}”`);
    if (sc) push("scholarships", "scholarships", "true", "Scholarships");

    setApplied(active);
    try {
      const newRows = await api(`/universities?${params}`);
      setResults(newRows);
      if (newRows.length) {
        setCountMsg(newRows.length === 1 ? <><b>1</b> university found</> : <>Showing <b>{newRows.length}</b> universities</>);
        setGridExtra(null);
      } else {
        const relax = await uniClosest(active, params);
        if (relax) {
          setCountMsg(<>No exact match · showing <b>{relax.rows.length}</b> closest</>);
          setGridExtra(
            <div className="card u-empty" style={{ gridColumn: "1/-1" }} key="empty">
              <h3>No exact matches for those filters</h3>
              <p className="small muted mt">Here are the closest programs — we relaxed <b>{relax.removed.map((r) => esc(r.label)).join("</b>, <b>")}</b>.</p>
              <button className="btn-ghost small mt" onClick={() => {
                relax.removed.forEach((r) => setVal(r.key, r.key === "scholarships" ? false : ""));
                applyFilters({ ...nextVals, ...Object.fromEntries(relax.removed.map((r) => [r.key, r.key === "scholarships" ? false : ""])) });
              }}>Keep these filters</button>
            </div>
          );
        } else {
          setCountMsg(null);
          setGridExtra(
            <div className="card u-empty" style={{ gridColumn: "1/-1" }} key="empty">
              <h3>No universities match</h3>
              <p className="small muted mt">{active.length ? "Try removing some filters." : "Try widening your filters."}</p>
              <button className="btn-ghost small mt" onClick={resetAll}>Clear all filters</button>
            </div>
          );
        }
      }
    } catch (_) { /* keep current grid on transient errors */ }
  };

  const resetAll = () => {
    const cleared = { country: "", course: "", subject: "", university_type: "", min_rank: "", max_fees: "", entry_query: "", scholarships: false };
    setVals(cleared);
    setApplied([]);
    applyFilters(cleared);
  };

  const changeAndApply = (key, value) => {
    const next = { ...vals, [key]: value };
    setVals(next);
    applyFilters(next);
  };

  const debounced = (key) => (e) => {
    const value = e.target.value;
    setVals((v) => ({ ...v, [key]: value }));
    clearTimeout(debounceTimer.current);
    debounceTimer.current = setTimeout(() => applyFilters({ ...vals, [key]: value }), 350);
  };

  const removeFilter = (key) => {
    const value = key === "scholarships" ? false : "";
    changeAndApply(key, value);
  };

  const refreshFromChats = async () => {
    setBusy(true);
    setActionError("");
    try {
      await api("/dna/refresh", { method: "POST" });
      setRecommended(await api("/universities/recommended"));
      setDctx(await getDnaContext());
      setAiAnswer("");
      toast("University recommendations updated from your chats");
    } catch (ex) { setActionError(ex.message); toast(ex.message, "err"); }
    finally { setBusy(false); }
  };

  const askAI = async () => {
    setBusy(true);
    setActionError("");
    try {
      const result = await api("/universities/advice", { method: "POST", body: JSON.stringify({ question: "Which university fits my interests and goals, and what should I verify before applying?", subject: vals.subject || null }) });
      setAiAnswer(result.answer || "No advice available yet.");
    } catch (ex) { setActionError(ex.message); toast(ex.message, "err"); }
    finally { setBusy(false); }
  };

  return (
    <>
      {busy && <p role="status">Working on your request…</p>}
      {actionError && <p role="alert">{actionError}</p>}
      <div className="hero"><Kicker>Find your program</Kicker><h1>University Explorer</h1><p>Global programs, weighted to your DNA and your readiness.</p></div>
      <div className="row mb">
        <button className="btn-ghost" onClick={refreshFromChats} disabled={busy}>Refresh from chats</button>
        <button className="btn" onClick={askAI} disabled={busy}>Ask AI</button>
      </div>
      {aiAnswer ? <div className="card mb" style={{ whiteSpace: "pre-wrap" }} role="status">{aiAnswer}</div> : null}
      {(recommended || []).length ? (
        <div className="card mb">
          <h2>Recommended for you</h2><p className="small muted">Ranked by alignment with your Career DNA</p>
          <div className="cols mt" style={{ gridTemplateColumns: "repeat(auto-fill,minmax(220px,1fr))", gap: 10 }}>
            {recommended.map(uniReadinessCard)}
          </div>
        </div>
      ) : null}
      <div className="card mb u-filters">
        <div className="between mb">
          <div><h2 style={{ marginBottom: 2 }}>Filters</h2><p className="small muted" id="uni-count">{countMsg}</p></div>
          <button className="btn-ghost small" id="uni-reset" onClick={resetAll}>Reset all</button>
        </div>
        <div className="filter-grid">
          <div className="field"><label>Country</label><select id="uni-country" value={vals.country} onChange={(e) => changeAndApply("country", e.target.value)}>{opts(filters.countries)}</select></div>
          <div className="field"><label>Course <span className="opt">· {(filters.courses || []).length} available</span></label>
            <input id="uni-course" list="uni-course-list" type="text" placeholder="Type to search all courses…" value={vals.course} onChange={debounced("course")} />
            <datalist id="uni-course-list">{(filters.courses || []).map((c, i) => <option key={i} value={c} />)}</datalist>
          </div>
          <div className="field"><label>Subject</label><select id="uni-subject" value={vals.subject} onChange={(e) => changeAndApply("subject", e.target.value)}>{opts(filters.subjects)}</select></div>
          <div className="field"><label>University type</label><select id="uni-type" value={vals.university_type} onChange={(e) => changeAndApply("university_type", e.target.value)}>{opts(filters.university_types)}</select></div>
          <div className="field"><label>Ranking</label><select id="uni-rank" value={vals.min_rank} onChange={(e) => changeAndApply("min_rank", e.target.value)}><option value="">Any ranking</option>{rankSteps.map((n) => <option key={n} value={n}>Top {n}</option>)}</select></div>
          <div className="field"><label>Max fees / year</label><select id="uni-fees" value={vals.max_fees} onChange={(e) => changeAndApply("max_fees", e.target.value)}><option value="">Any fees</option>{feeSteps.map((n) => <option key={n} value={n}>Under ${fmt(n)}</option>)}</select></div>
          <div className="field"><label>Entry requirements</label><input id="uni-entry" type="text" placeholder="e.g. SAT, JEE, IELTS…" value={vals.entry_query} onChange={debounced("entry_query")} /></div>
          <label className="uni-check"><input type="checkbox" id="uni-scholarships" checked={vals.scholarships} onChange={(e) => changeAndApply("scholarships", e.target.checked)} /><span>Scholarships available</span></label>
        </div>
        <div className="u-active" id="uni-active">
          {applied.length ? (
            <>
              {applied.map((a) => <button key={a.key} className="u-achip" onClick={() => removeFilter(a.key)}>{esc(a.label)}<span>×</span></button>)}
              <button className="u-achip-clear" onClick={resetAll}>Clear all</button>
            </>
          ) : null}
        </div>
      </div>
      <div className="cols" id="uni-grid">
        {gridExtra}
        {results.map(uniCard)}
      </div>
    </>
  );
}
