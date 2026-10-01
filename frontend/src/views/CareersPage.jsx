import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, esc, getDnaContext, ringColor } from "../api";
import { EmptyState, Kicker, showLoader, toast } from "../ui";

export default function CareersPage() {
  const router = useRouter();
  const [dctx, setDctx] = useState(null);
  const [list, setList] = useState([]);
  const [categories, setCategories] = useState([]);
  const [savedMatches, setSavedMatches] = useState([]);
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("");
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState("");
  const [aiAnswer, setAiAnswer] = useState("");

  useEffect(() => {
    let alive = true;
    showLoader(true);
    Promise.all([
      getDnaContext(),
      api("/careers?limit=50"),
      api("/careers/categories"),
      api("/careers/matches").catch(() => []),
    ])
      .then(([d, l, c, m]) => { if (alive) { setDctx(d); setList(l || []); setCategories(c || []); setSavedMatches(m || []); } })
      .catch((ex) => { if (alive) setError(ex.message); })
      .finally(() => showLoader(false));
    return () => { alive = false; };
  }, []);

  if (error) return <EmptyState title="Careers unavailable" sub={error} />;

  const matchMap = {};
  (savedMatches || []).forEach((m) => { matchMap[m.career.slug] = m.score; });

  const matchCard = (m, i) => (
    <div key={m.career.slug} className="list-item mb" style={{ cursor: "pointer" }} onClick={() => router.push(`/career/${m.career.slug}`)}>
      <div className="row">
        <div className="num-badge">{i + 1}</div>
        <div style={{ flex: 1 }}><b>{m.career.emoji} {esc(m.career.title)}</b>
          <div className="small muted">matches parts of your DNA</div></div>
        <b style={{ color: ringColor(m.score) }}>{Math.round(m.score)}%</b>
      </div>
      <ul className="plain mt">{(m.reasons || []).map((r, j) => <li className="small" key={j}>{esc(r)}</li>)}</ul>
    </div>
  );

  const applyFilters = () => {
    const t = query.toLowerCase();
    return list.filter((c) => {
      const inCat = !category || c.category === category;
      const haystack = `${c.title} ${c.summary} ${c.category} ${(c.skills || []).join(" ")}`.toLowerCase();
      const inQuery = !t || haystack.includes(t);
      return inCat && inQuery;
    });
  };

  const filtered = applyFilters();

  const matchWithAI = async () => {
    setBusy(true);
    setActionError("");
    try {
      const res = await api("/careers/match", { method: "POST", body: JSON.stringify({ limit: 8 }) });
      setSavedMatches(res || []);
      toast("Here are your top matches ✨");
    } catch (ex) { setActionError(ex.message); toast(ex.message); }
    finally { setBusy(false); }
  };

  const refreshFromChats = async () => {
    setBusy(true);
    setActionError("");
    try {
      await api("/dna/refresh", { method: "POST" });
      const res = await api("/careers/match", { method: "POST", body: JSON.stringify({ limit: 8 }) });
      setSavedMatches(res || []);
      setDctx(await getDnaContext());
      setAiAnswer("");
      toast("Career matches updated from your chats");
    } catch (ex) { setActionError(ex.message); toast(ex.message, "err"); }
    finally { setBusy(false); }
  };

  const askAI = async () => {
    const top = savedMatches[0]?.career;
    if (!top) { setActionError("Find your career matches first, then ask AI about your top match."); return; }
    setBusy(true);
    setActionError("");
    try {
      const result = await api(`/careers/${encodeURIComponent(top.slug)}/advice`);
      setAiAnswer([result.fit_statement, ...(result.next_steps || []).map((s) => `• ${s.title}: ${s.why}`)].filter(Boolean).join("\n\n"));
    } catch (ex) { setActionError(ex.message); toast(ex.message, "err"); }
    finally { setBusy(false); }
  };

  return (
    <>
      {busy && <p role="status">Working on your request…</p>}
      {actionError && <p role="alert">{actionError}</p>}
      <div className="hero"><Kicker>Explore verified paths</Kicker><h1>Career Explorer</h1><p>There are thousands of careers you've never heard of. Novi surfaces the ones that could be <b style={{ color: "var(--text)" }}>you</b>.</p></div>
      <div className="card mb">
        <div className="career-search">
          <input id="career-q" placeholder="Search careers, interests or skills — try ‘AI’, ‘design’, ‘finance’…" value={query} onChange={(e) => setQuery(e.target.value)} />
          <button className="btn" id="career-match" onClick={matchWithAI} disabled={busy}>Find my matches</button>
          <button className="btn-ghost" onClick={refreshFromChats} disabled={busy}>Refresh from chats</button>
          <button className="btn-ghost" onClick={askAI} disabled={busy}>Ask AI</button>
        </div>
        <div className="cat-row">
          <button className={`cat-pill ${category === "" ? "on" : ""}`} onClick={() => setCategory("")}>All</button>
          {(categories || []).map((c) => <button key={c} className={`cat-pill ${category === c ? "on" : ""}`} onClick={() => setCategory(c)}>{c}</button>)}
        </div>
        <div id="match-result" className="mt">
          {aiAnswer ? <div className="card mb" style={{ whiteSpace: "pre-wrap" }} role="status">{aiAnswer}</div> : null}
          {(savedMatches || []).length ? <><div className="section-title">Matches based on your DNA</div>{savedMatches.map(matchCard)}</> : null}
        </div>
      </div>
      <div className="career-grid" id="career-grid">
        {filtered.map((c) => (
          <div key={c.slug} className="card career-card" onClick={() => router.push(`/career/${c.slug}`)}>
            <div className="career-top">
              <div className="career-emoji">{c.emoji}</div>
              {matchMap[c.slug] !== undefined
                ? <span className="pill mid" title="AI match score">{Math.round(matchMap[c.slug])}% match</span>
                : <span className="pill" style={{ background: "var(--panel-2)", color: "var(--muted)" }}>{esc(c.category)}</span>}
            </div>
            <div className="cc-title">{esc(c.title)}</div>
            <div className="cc-meta">{esc(c.salary_range || c.category)}</div>
            <p className="cc-summary">{esc(c.summary)}</p>
            <div className="cc-foot">
              {matchMap[c.slug] !== undefined ? <div className="progress-track"><div className="progress-fill" style={{ width: `${matchMap[c.slug]}%`, background: ringColor(matchMap[c.slug]) }} /></div> : null}
              <span className="small muted">View career →</span>
            </div>
          </div>
        ))}
      </div>
    </>
  );
}
