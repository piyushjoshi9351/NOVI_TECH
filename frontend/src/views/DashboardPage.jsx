import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowRight, Check, Compass, GraduationCap, MessageCircle, ShieldCheck, Sparkles, Target, Zap } from "lucide-react";
import { api, bellTime, esc, ringColor } from "../api";
import { useAuth } from "../auth";
import { Bar, EmptyState, showLoader, toast } from "../ui";
import ContributionHeatmap from "./checkin/ContributionHeatmap";

export default function DashboardPage() {
  const { user } = useAuth();
  const router = useRouter();
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let alive = true;
    showLoader(true);
    api("/dashboard")
      .then((d) => { if (alive) setData(d); })
      .catch((ex) => { if (alive) setError(ex.message); })
      .finally(() => showLoader(false));
    return () => { alive = false; };
  }, []);

  if (error) return <EmptyState title="Could not load dashboard" sub={error} />;
  if (!data) return null;

  const p = data.progress || {};
  const firstName = (user?.first_name || user?.name || "there").trim().split(/\s+/)[0];
  const greeting = `Good ${bellTime()}, ${firstName} 👋`;
  const focus = data.today_focus || null;
  const dir = p.career_direction || "Exploring";
  const dirTone = dir === "On Track" ? "good" : dir === "Exploring" ? "warn" : "bad";
  const num = (v) => (typeof v === "number" ? Math.round(v) : typeof v === "string" && !isNaN(Number(v)) ? Math.round(Number(v)) : 0);
  const prof = num(p.profile_strength), uni = num(p.university_readiness), rm = num(p.roadmap_progress);
  const prioOpen = (data.priorities || []).filter((x) => !x.completed);
  const doAction = data.next_task ? { kind: "task", id: data.next_task.id } : prioOpen[0] ? { kind: "priority", id: prioOpen[0].id } : null;

  const dna = data.dna || {};
  const skills = dna.skills || [];
  const focusAreas = skills.length || (dna.interests || []).length;
  const prioWeek = (data.priorities || []).slice().sort((a, b) => (a.completed === b.completed ? 0 : a.completed ? 1 : -1));
  const prioDone = (data.priorities || []).filter((x) => x.completed).length;
  const matches = (data.career_matches || []).slice(0, 3);
  const recent = (data.passport || []).slice(0, 3);
  const grade = user?.grade ? `CBSE · Grade ${user.grade}` : "Your workspace";
  const todayLabel = new Date().toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric" });

  const go = (route) => () => router.push(`/${route}`);

  const tile = (route, Icon, label, value, foot) => (
    <button className="dash-tile" onClick={go(route)}>
      <div className="dash-tile-top">
        <span className="dash-tile-ico"><Icon size={18} strokeWidth={2} /></span>
        <span className="dash-tile-label">{label}</span>
      </div>
      <div className="dash-tile-val">{value}</div>
      {foot ? <div className="dash-tile-sub">{foot}</div> : null}
    </button>
  );

  const row = (title, meta, href) => (
    <Link className="dash-row" href={href} key={title}>
      <span className="dash-row-body">
        <span className="dash-row-title">{title}</span>
        {meta ? <span className="dash-row-meta">{meta}</span> : null}
      </span>
      <span className="dash-row-arrow"><ArrowRight size={15} /></span>
    </Link>
  );

  const sigRow = (label, v, href) => (
    <Link className="sig-row" href={href} key={label}>
      <span className="sig-label">{label}</span>
      <span className="sig-mid"><Bar v={v} /></span>
      <span className="sig-val">{v}%</span>
    </Link>
  );

  const markDone = async (id) => {
    showLoader(true);
    try {
      await api(`/roadmap/priorities/${id}`, { method: "PATCH" });
      toast("Nice work — knocked it out ✓");
      setData(await api("/dashboard"));
    } catch (ex) { toast(ex.message); }
    finally { showLoader(false); }
  };

  const handleDone = async () => {
    if (!doAction) return;
    showLoader(true);
    try {
      if (doAction.kind === "task") await api(`/roadmap/tasks/${doAction.id}`, { method: "PATCH", body: JSON.stringify({ status: "done" }) });
      else await api(`/roadmap/priorities/${doAction.id}`, { method: "PATCH" });
      toast("Nice work — knocked it out ✓");
      setData(await api("/dashboard"));
    } catch (ex) { toast(ex.message); }
    finally { showLoader(false); }
  };

  return (
    <div className="dash-wrap">
      <div className="dash-top">
        <div className="dash-intro">
          <div className="dash-kick">{todayLabel}</div>
          <h1 className="dash-hi">{greeting}</h1>
          <p className="dash-sub">{esc(data.novi_says || "Your workspace is ready — here's your plan.")}</p>
          <div className="dash-chips">
            <span className="chip-soft">{grade}</span>
            <span className={`pill ${dirTone}`}>{dir}</span>
          </div>
          {/* Profile photo / headline / About, sourced from the same Passport profile. */}
          {user?.profile_photo || user?.headline || user?.about_me ? (
            <div className="dash-prof">
              {user.profile_photo ? (
                <img className="dash-prof-img" src={user.profile_photo} alt="" />
              ) : null}
              <div className="dash-prof-txt">
                {user.headline ? <div className="dash-prof-head">{esc(user.headline)}</div> : null}
                {user.location ? <div className="dash-prof-loc">📍 {esc(user.location)}</div> : null}
                {user.about_me ? <p className="dash-prof-about">{esc(user.about_me)}</p> : null}
              </div>
            </div>
          ) : null}
        </div>
        <div className="dash-tools">
          <button className="btn-ghost" onClick={go("chat")}><MessageCircle size={16} /> Ask Novi</button>
          <button className="btn" onClick={go("roadmap")}>Open plan</button>
        </div>
      </div>

      <section className="focus-card">
        <div className="focus-body">
          <div className="focus-top">
            <span className="focus-lab"><Zap size={13} strokeWidth={2.4} /> Next up</span>
            {focus ? <span className="focus-chip">{rm}% through roadmap</span> : null}
          </div>
          <h2 className="focus-title">{focus ? focus.title : "Choose your next move"}</h2>
          {focus && focus.why
            ? <p className="focus-why">{focus.why}</p>
            : <p className="dash-hero-sub">Complete one focused session and Novi turns it into your next precise step.</p>}
          <div className="dash-hero-actions">
            <button className="btn" onClick={go("roadmap")}>Start focused session →</button>
            <button className="btn-ghost" onClick={go("chat")}>Ask the tutor</button>
            {doAction ? <button className="btn-ghost done" onClick={handleDone}><Check size={15} strokeWidth={2.4} /> Mark done</button> : null}
          </div>
        </div>
        <div className="focus-side">
          <div className="ring" style={{ "--ring": prof }}>
            <div className="ring-in"><b>{prof}%</b><span>profile</span></div>
          </div>
          <div className="focus-bars">
            <div className="focus-bar"><span>Roadmap</span><Bar v={rm} /></div>
            <div className="focus-bar"><span>University</span><Bar v={uni} /></div>
          </div>
        </div>
      </section>

      <div className="dash-tiles">
        {tile("roadmap", Target, "Open today", prioOpen.length, <span>of {prioWeek.length} this week</span>)}
        {tile("dna", Compass, "Focus areas", focusAreas, "mapped in your DNA")}
        {tile("passport", ShieldCheck, "Profile strength", <span style={{ color: ringColor(prof) }}>{prof}%</span>, <Bar v={prof} />)}
        {tile("universities", GraduationCap, "University readiness", <span style={{ color: ringColor(uni) }}>{uni}%</span>, <Bar v={uni} />)}
      </div>

      <div className="dash-cols">
        <section className="card dash-panel">
          <div className="between">
            <div>
              <div className="sec-kick">Today</div>
              <h2>Your plan.</h2>
            </div>
            <Link href="/roadmap" className="panel-link">+ Add task</Link>
          </div>
          {prioWeek.length
            ? (
              <>
                <div className="dash-rows">
                  {prioWeek.map((x) => (
                    <div key={x.id} className={`dash-row ${x.completed ? "is-done" : ""}`} onClick={go("roadmap")}>
                      <button className="dash-check" aria-label="Mark priority done" disabled={x.completed} onClick={(e) => { e.stopPropagation(); markDone(x.id); }}>
                        {x.completed ? <Check size={13} strokeWidth={3} /> : null}
                      </button>
                      <span className="dash-row-body">
                        <span className="dash-row-title">{x.title}</span>
                        {x.skill_category
                          ? <span className="dash-row-meta">{x.skill_category}{x.minutes ? ` · ${x.minutes} min` : ""}{x.completed ? " · done" : ""}</span>
                          : null}
                      </span>
                      <span className="dash-row-arrow"><ArrowRight size={15} /></span>
                    </div>
                  ))}
                </div>
                <div className="dash-panel-foot">
                  <span className="foot-line"><Bar v={(prioDone / Math.max(1, prioWeek.length)) * 100} /> <i>{prioDone} of {prioWeek.length} done</i></span>
                  <button className="btn-ghost" onClick={go("roadmap")}>Open roadmap →</button>
                </div>
              </>
            )
            : <p className="small mt">Nothing is scheduled for today — add your first focus block.</p>}
        </section>

        <section className="card dash-panel">
          {/* Dashboard shows a 3-month glance; Checkin keeps the 6-month default. */}
          <ContributionHeatmap weeks={13} />
        </section>

        <section className="card dash-panel">
          <div className="between">
            <div>
              <div className="sec-kick">Progress</div>
              <h2>Your learning signal.</h2>
            </div>
            <Link href="/passport" className="panel-link">Full analysis →</Link>
          </div>
          <div className="sig-rows">
            {sigRow("Profile", prof, "/passport")}
            {sigRow("University", uni, "/universities")}
            {sigRow("Roadmap", rm, "/roadmap")}
          </div>
          {matches[0] ? (
            <Link className="dash-note" href={`/career/${matches[0].career.slug}`}>
              <span className="dash-note-ico"><MessageCircle size={14} /></span>
              <span>Your strongest signal is <b>{matches[0].career.title}</b> — a {matches[0].score}% match.</span>
            </Link>
          ) : (
            <Link className="dash-note" href="/dna">
              <span className="dash-note-ico"><Sparkles size={14} /></span>
              <span>Feed your DNA to unlock career matches.</span>
            </Link>
          )}
        </section>
      </div>

      <div className="dash-cols">
        <section className="card dash-panel">
          <div className="between">
            <div>
              <div className="sec-kick">Matches</div>
              <h2>Top career matches.</h2>
            </div>
            <Link href="/careers" className="panel-link">All matches →</Link>
          </div>
          {matches.length
            ? (
              <div className="dash-rows">
                {matches.map((m) => (
                  <Link className="dash-row match" href={`/career/${m.career.slug}`} key={m.id}>
                    <span className="match-rank">{m.career.emoji || m.rank}</span>
                    <span className="dash-row-body">
                      <span className="dash-row-title">{m.career.title}</span>
                      {m.career.category ? <span className="dash-row-meta">{m.career.category}</span> : null}
                    </span>
                    <span className="match-score">
                      <b style={{ color: ringColor(m.score) }}>{m.score}%</b>
                      <span className="match-bar"><i style={{ width: `${Math.min(100, m.score)}%` }} /></span>
                    </span>
                  </Link>
                ))}
              </div>
            )
            : <p className="small mt">Complete your DNA to see how careers line up with you.</p>}
        </section>

        <section className="card dash-panel">
          <div className="between">
            <div>
              <div className="sec-kick">Recent</div>
              <h2>Pick up where you left off.</h2>
            </div>
            <Link href="/passport" className="panel-link">All →</Link>
          </div>
          {recent.length
            ? <div className="dash-rows">{recent.map((x) => row(x.title, `${x.category || "Entry"}${x.verified ? " · verified" : ""}`, "/passport"))}</div>
            : <p className="small mt">No recent activity yet — add your first passport entry.</p>}
        </section>
      </div>

      <button className="fab" title="Chat with Novi" onClick={go("chat")}><MessageCircle size={17} /> <span>Novi</span></button>
    </div>
  );
}