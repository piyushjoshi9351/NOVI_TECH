import { useEffect, useRef, useState } from "react";
import { Bell, BookOpen, Check, CreditCard, Link as LinkIcon, LogOut, Palette, Shield, Sparkles, UserRound, Users } from "lucide-react";
import { api, applyAccent, applyTheme, esc, fmtJoined, getTheme, initials, NOVI_ACCENTS, PS_NOTIFS, readPrefs, refreshDnaContext, savePrefs } from "../api";
import { useAuth } from "../auth";
import { EmptyState, showLoader, toast } from "../ui";
import ParentAccess from "./student/ParentAccess";

const PS_TAGS = [
  ["interests", "Interests", "Coding, cricket, music…", "What you genuinely enjoy — Novi weighs it in every match."],
  ["career_zones", "Career zones", "Technology, Sports Analytics…", "The fields you see yourself working in someday."],
  ["strengths", "Strengths", "Problem solving, teamwork…", "What you're good at. Say it plainly — it counts."],
  ["subjects", "Subjects", "Maths, computer science…", "School subjects you actually like."],
];

const PS_ICON = { profile: UserRound, academic: BookOpen, security: Shield, notifications: Bell, appearance: Palette, integrations: LinkIcon, billing: CreditCard, parents: Users };

const PS_TABS = [
  ["profile", "Profile"],
  ["academic", "Academic"],
  ["parents", "Parent access"],
  ["security", "Security"],
  ["notifications", "Notifications"],
  ["appearance", "Appearance"],
  ["integrations", "Integrations"],
  ["billing", "Billing"],
];

function SidebarIcon({ name, active }) {
  const Icon = PS_ICON[name];
  return (
    <Icon
      size={24}
      strokeWidth={1.8}
      className={active ? "ps-ico-icon on" : "ps-ico-icon"}
      aria-hidden="true"
    />
  );
}

let _psTab = "profile";

export default function ProfilePage() {
  const { patchUser, logout } = useAuth();
  const [tab, setTab] = useState(_psTab);
  const [user, setUser] = useState(null);
  const [dna, setDna] = useState(null);
  const [tags, setTags] = useState({ interests: [], career_zones: [], strengths: [], subjects: [], goals: [] });
  const [links, setLinks] = useState(null);
  const [health, setHealth] = useState(null);
  const [accentKey, setAccentKey] = useState(() => readPrefs().appearance || "aurora");
  const [themeKey, setThemeKey] = useState(() => getTheme());
  const notifDraft = useRef({ ...readPrefs() });
  const [error, setError] = useState(null);

  useEffect(() => {
    let alive = true;
    showLoader(true);
    Promise.all([
      api("/auth/me"),
      api("/dna").catch(() => null),
      api("/auth/links").catch(() => ({ parents: [] })),
      api("/health").catch(() => null),
    ])
      .then(([me, d, l, h]) => {
        if (!alive) return;
        setUser(me);
        setDna(d || {});
        setLinks(l || { parents: [] });
        setHealth(h);
        const init = {};
        PS_TAGS.forEach(([k]) => { init[k] = [...(((d && d[k]) || []).map((s) => String(s)))]; });
        init.goals = [...(((d && d.goals) || []).map((s) => String(s)))];
        setTags(init);
      })
      .catch((ex) => { if (alive) setError(ex.message); })
      .finally(() => showLoader(false));
    return () => { alive = false; };
  }, []);

  if (error) return <EmptyState title="Profile unavailable" sub={error} />;
  if (!user) return null;

  const dnaReady = dna && dna.dna_filled;
  // Parent access only means something on a student account; parents manage
  // their own side from the parent area instead.
  const tabs = PS_TABS.filter(([key]) => {
    if (key === "academic") return user.role === "student";
    if (key === "parents") return user.role === "student";
    return true;
  });

  const addTag = (key, v) => setTags((t) => {
    const cur = t[key] || [];
    if (cur.some((c) => c.toLowerCase() === v.toLowerCase())) return t;
    return { ...t, [key]: [...cur, v] };
  });
  const removeTag = (key, v) => setTags((t) => ({ ...t, [key]: (t[key] || []).filter((c) => c !== v) }));

  const go = (key) => { _psTab = key; setTab(key); window.scrollTo(0, 0); };

  const saveProfile = async () => {
    const nameVal = document.querySelector("#ps-name")?.value || "";
    const name = nameVal.trim();
    const goals = (document.querySelector("#ps-goals")?.value || "").split("\n").map((s) => s.trim()).filter(Boolean);
    showLoader(true);
    try {
      if (user.role === "student") {
        await api("/dna", { method: "PATCH", body: JSON.stringify({
          interests: tags.interests, career_zones: tags.career_zones,
          strengths: tags.strengths, subjects: tags.subjects, goals,
        }) });
        refreshDnaContext();
        setTags((t) => ({ ...t, goals }));
        setDna((d) => ({ ...(d || {}), dna_filled: goals.length || tags.interests.length }));
      }
      await api("/auth/me", { method: "PATCH", body: JSON.stringify({ first_name: name || user.first_name || "" }) });
      const me = await api("/auth/me");
      setUser(me);
      patchUser(me);
      toast("Profile saved ✨");
    } catch (ex) { toast(ex.message); }
    finally { showLoader(false); }
  };

  const saveAcademic = async () => {
    const first = document.querySelector("#ps-first")?.value.trim() || "";
    const last = document.querySelector("#ps-last")?.value.trim() || "";
    const grade = document.querySelector("#ps-grade")?.value ? Number(document.querySelector("#ps-grade").value) : null;
    const school = document.querySelector("#ps-school")?.value || "";
    showLoader(true);
    try {
      const me = await api("/auth/me", { method: "PATCH", body: JSON.stringify({ first_name: first, last_name: last, grade, school }) });
      setUser(me);
      patchUser(me);
      toast("Academic details saved ✨");
    } catch (ex) { toast(ex.message); }
    finally { showLoader(false); }
  };

  const savePassword = async () => {
    const cur = document.querySelector("#ps-curpw")?.value || "";
    const nw = document.querySelector("#ps-newpw")?.value || "";
    const cf = document.querySelector("#ps-confpw")?.value || "";
    if (!cur) { toast("Enter your current password", "err"); return; }
    if (nw.length < 6) { toast("New password must be at least 6 characters", "err"); return; }
    if (nw !== cf) { toast("New passwords don't match", "err"); return; }
    showLoader(true);
    try {
      await api("/auth/change-password", { method: "POST", body: JSON.stringify({ current_password: cur, new_password: nw }) });
      ["#ps-curpw", "#ps-newpw", "#ps-confpw"].forEach((s) => { const el = document.querySelector(s); if (el) el.value = ""; });
      toast("Password updated 🔒");
    } catch (ex) { toast(ex.message, "err"); }
    finally { showLoader(false); }
  };

  const runAccent = (key) => {
    applyAccent(key);
    notifDraft.current.appearance = key;
    setAccentKey(key);
    toast(`${NOVI_ACCENTS[key].name} applied 🎨`);
  };

  const parents = (links && links.parents) || [];

  return (
    <>
      <div className="ps-hero">
        <div className="eyebrow">Your account</div>
        <h1>My Profile</h1>
        <p>Everything Novi knows about you, in one place. Update it anytime — it tunes every match, roadmap and recommendation.</p>
      </div>
      <hr className="ps-rule" />
      <div className="ps-layout">
        <aside className="ps-side">
          <div className="ps-side-group">
            {tabs.map(([key, label]) => (
              <button key={key} className={`ps-item ${tab === key ? "active" : ""}`} data-tab={key} onClick={() => go(key)}>
                <span className="ps-ico"><SidebarIcon name={key} active={tab === key} /></span>{label}
              </button>
            ))}
            <hr className="ps-sep" />
            <button className="ps-item danger" id="ps-signout" onClick={() => { logout(); }}>
              <span className="ps-ico"><LogOut size={24} strokeWidth={1.8} className="ps-ico-icon" aria-hidden="true" /></span>Sign out
            </button>
          </div>
        </aside>

        <section className="ps-content">
          {tab === "profile" ? (
            <>
              <div className="ps-section-head"><span className="ps-eyebrow">Profile</span></div>
              <div className="ps-ident">
                <div className="ps-avatar">{esc(initials(user.first_name || user.email || "NOVI"))}</div>
                <div className="ps-ident-copy">
                  <div className="ps-ident-name">{esc((user.first_name || user.email || "NOVI").trim())}</div>
                  <div className="ps-ident-sub">{esc(user.email || "")} · {esc(fmtJoined(user.created_at))}</div>
                </div>
                {dnaReady
                  ? <span className="chip acc">DNA ready</span>
                  : <a className="ps-dna-link" href="#/dna" onClick={() => { _psTab = tab; }}>Complete your DNA →</a>}
              </div>
              <hr className="ps-divider" />
              <div className="ps-section-title">Personal information</div>
              <div className="ps-fields">
                <div className="ps-field">
                  <label htmlFor="ps-name">Name</label>
                  <input id="ps-name" defaultValue={user.first_name || ""} placeholder="Your name" />
                </div>
                <div className="ps-field">
                  <label htmlFor="ps-email">Email</label>
                  <input id="ps-email" value={user.email || ""} disabled />
                </div>
              </div>
              <div className="ps-section-title">Your DNA</div>
              <div className="ps-fields">
                {PS_TAGS.map(([key, label, ph, hint]) => (
                  <div className="ps-field" key={key}>
                    <label>{label}</label>
                    <div className="tag-editor">
                      {(tags[key] || []).map((v) => (
                        <span className="tag-chip" key={v}>
                          {esc(v)}
                          <button type="button" className="tag-x" aria-label="Remove" onClick={() => removeTag(key, v)}>×</button>
                        </span>
                      ))}
                      <TagInput onCommit={(v) => addTag(key, v)} placeholder={ph} />
                    </div>
                    <p className="ps-hint">{hint}</p>
                  </div>
                ))}
                <div className="ps-field">
                  <label htmlFor="ps-goals">Goals</label>
                  <textarea id="ps-goals" defaultValue={(tags.goals || []).join("\n")} placeholder="One goal per line — e.g. Become a Java backend engineer" />
                  <p className="ps-hint">Your destination — Novi builds your roadmap around these.</p>
                </div>
              </div>
              <div className="ps-save"><button className="btn" onClick={saveProfile}>Save changes</button></div>
            </>
          ) : null}

          {tab === "academic" ? (
            <>
              <div className="ps-section-head"><span className="ps-eyebrow">Academic</span></div>
              <p className="ps-intro">Where you are in school — Novi tunes every recommendation to your grade and school.</p>
              <div className="ps-fields">
                <div className="ps-field">
                  <label htmlFor="ps-first">First name</label>
                  <input id="ps-first" defaultValue={user.first_name || ""} placeholder="First name" />
                </div>
                <div className="ps-field">
                  <label htmlFor="ps-last">Last name</label>
                  <input id="ps-last" defaultValue={user.last_name || ""} placeholder="Last name" />
                </div>
                <div className="ps-field">
                  <label htmlFor="ps-grade">Grade</label>
                  <select id="ps-grade" defaultValue={user.grade || ""}>
                    {["", 9, 10, 11, 12].map((g) => <option key={g} value={g}>{g ? `Grade ${g}` : "Not in school yet"}</option>)}
                  </select>
                </div>
                <div className="ps-field">
                  <label htmlFor="ps-school">School</label>
                  <input id="ps-school" defaultValue={user.school || ""} placeholder="Your school name" />
                </div>
              </div>
              <div className="ps-save"><button className="btn" onClick={saveAcademic}>Save changes</button></div>
            </>
          ) : null}

          {tab === "parents" ? <ParentAccess /> : null}

          {tab === "security" ? (
            <>
              <div className="ps-section-head"><span className="ps-eyebrow">Security</span></div>
              <p className="ps-intro">Keep your NOVI account safe. Your new password needs at least 6 characters.</p>
              <div className="ps-section-title">Change password</div>
              <div className="ps-fields">
                <div className="ps-field">
                  <label htmlFor="ps-curpw">Current password</label>
                  <input id="ps-curpw" type="password" placeholder="••••••••" autoComplete="current-password" />
                </div>
                <div className="ps-field">
                  <label htmlFor="ps-newpw">New password</label>
                  <input id="ps-newpw" type="password" placeholder="At least 6 characters" autoComplete="new-password" />
                </div>
                <div className="ps-field">
                  <label htmlFor="ps-confpw">Confirm new password</label>
                  <input id="ps-confpw" type="password" placeholder="Repeat your new password" autoComplete="new-password" />
                </div>
              </div>
              <div className="ps-save"><button className="btn" onClick={savePassword}>Update password</button></div>
              <div className="ps-section-title">Account</div>
              <div className="ps-fields">
                <div className="ps-field">
                  <label htmlFor="ps-sec-email">Email</label>
                  <input id="ps-sec-email" value={user.email || ""} disabled />
                  <p className="ps-hint">This is the address you sign in with and how a parent links to you.</p>
                </div>
              </div>
            </>
          ) : null}

          {tab === "notifications" ? (
            <>
              <div className="ps-section-head"><span className="ps-eyebrow">Notifications</span></div>
              <p className="ps-intro">Choose how NOVI keeps in touch. These preferences are stored on your device.</p>
              <div className="ps-notif-list">
                {PS_NOTIFS.map(([key, label, sub]) => (
                  <label className="ps-notif" key={key}>
                    <span className="ps-notif-copy">
                      <span className="ps-notif-name">{label}</span>
                      <span className="ps-hint">{sub}</span>
                    </span>
                    <span className="ps-toggle">
                      <input type="checkbox" data-notif={key} defaultChecked={!!notifDraft.current[key]} onChange={(e) => { notifDraft.current[key] = e.target.checked; }} />
                      <span className="ps-track"></span>
                    </span>
                  </label>
                ))}
              </div>
              <div className="ps-save"><button className="btn" onClick={() => { savePrefs(notifDraft.current); toast("Notification preferences saved 🔔"); }}>Save preferences</button></div>
            </>
          ) : null}

          {tab === "appearance" ? (
            <>
              <div className="ps-section-head"><span className="ps-eyebrow">Appearance</span></div>
              <p className="ps-intro">Pick the accent that feels like you. Changes apply instantly and are saved on your device.</p>
              <div className="ps-section-title">Theme</div>
              <div className="ps-theme-row">
                {[["dark", "Dark", "🌙"], ["light", "Light", "☀️"]].map(([key, label, icon]) => (
                  <button
                    key={key}
                    className={`ps-theme-opt ${themeKey === key ? "on" : ""}`}
                    onClick={() => {
                      applyTheme(key);
                      notifDraft.current.theme = key;
                      setThemeKey(key);
                    }}
                  >
                    <span>{icon}</span> {label}
                  </button>
                ))}
              </div>
              <div className="ps-section-title">Accent colour</div>
              <div className="ps-swatches">
                {Object.entries(NOVI_ACCENTS).map(([key, acc]) => (
                  <button key={key} className={`ps-swatch ${accentKey === key ? "on" : ""}`} data-accent={key} style={{ "--sw-a": acc.a, "--sw-a2": acc.a2 }} aria-label={acc.name} onClick={() => runAccent(key)}>
                    <span className="ps-swatch-dot">{acc.emoji}</span>
                    <span className="ps-swatch-name">{acc.name}</span>
                  </button>
                ))}
              </div>
              <div className="ps-section-title">Preview</div>
              <div className="ps-preview">
                <div className="novi-box">
                  <span className="novi-avatar">N</span>That's the NOVI you're building — <b style={{ color: "var(--text)" }}>know yourself, build your future, get there</b>.
                </div>
              </div>
            </>
          ) : null}

          {tab === "integrations" ? (
            <>
              <div className="ps-section-head"><span className="ps-eyebrow">Integrations</span></div>
              <p className="ps-intro">What NOVI is connected to — and who can follow your journey.</p>
              <div className="ps-section-title">Connected to Novi</div>
              <div className="ps-row">
                <span className="ps-ico">🧠</span>
                <span className="ps-row-body"><b>NOVI long-term memory</b><span className="ps-hint">Remembers you across Grade 9 → 12 so advice gets more personal</span></span>
                {health === null
                  ? <span className="chip" id="ps-mem-status">Checking…</span>
                  : <span className={`chip ${health && health.status === "healthy" ? "good" : "warn"}`}>{health && health.status === "healthy" ? `Memory: ${health.memory || "connected"}` : "Offline"}</span>}
              </div>
              <div className="ps-row">
                <span className="ps-ico">💬</span>
                <span className="ps-row-body"><b>Mentor chat</b><span className="ps-hint">Every conversation feeds your Career DNA</span></span>
                <span className="chip good">Active</span>
              </div>
              <div className="ps-section-title">Parents</div>
              <div className="ps-row">
                <span className="ps-ico">👨‍👩‍👧</span>
                <span className="ps-row-body"><b>Parent access</b><span className="ps-hint">A parent links to you with your email — <b>{esc(user.email || "")}</b>. Only they can start the link.</span></span>
                {parents.length
                  ? <span className={`chip ${parents.length ? "acc" : ""}`}>{parents.length === 1 ? "1 linked" : `${parents.length} linked`}</span>
                  : <span className="chip">Not linked yet</span>}
              </div>
              {parents.length ? (
                <>
                  <div className="ps-section-title">Linked parents</div>
                  {parents.map((p) => (
                    <div className="ps-row" key={p.id || p.email}>
                      <span className="ps-ico">👤</span>
                      <span className="ps-row-body"><b>{esc(p.name)}</b><span className="ps-hint">{esc(p.email)}</span></span>
                    </div>
                  ))}
                </>
              ) : null}
            </>
          ) : null}

          {tab === "billing" ? (
            <>
              <div className="ps-section-head"><span className="ps-eyebrow">Billing</span></div>
              <p className="ps-intro">NOVI is free for every student — and always will be. No cards, no trials, no surprises.</p>

              <div className="bill-card">
                <div className="bill-card-head">
                  <div className="bill-logo">N</div>
                  <div className="bill-plan-copy">
                    <div className="bill-plan-name">NOVI Free</div>
                    <div className="bill-plan-price">₹0 · forever</div>
                  </div>
                  <span className="chip good">Current plan</span>
                </div>
                <div className="bill-features">
                  <div className="bill-feat"><span className="bill-check"><Check size={14} strokeWidth={2.2} /></span><span>Unlimited AI mentor chats</span></div>
                  <div className="bill-feat"><span className="bill-check"><Check size={14} strokeWidth={2.2} /></span><span>Career DNA that learns from every conversation</span></div>
                  <div className="bill-feat"><span className="bill-check"><Check size={14} strokeWidth={2.2} /></span><span>Grade-by-grade roadmap, goals &amp; priorities</span></div>
                  <div className="bill-feat"><span className="bill-check"><Check size={14} strokeWidth={2.2} /></span><span>Career Passport and university readiness</span></div>
                  <div className="bill-feat"><span className="bill-check"><Check size={14} strokeWidth={2.2} /></span><span>Weekly check-ins and growth signals</span></div>
                  <div className="bill-feat"><span className="bill-check"><Check size={14} strokeWidth={2.2} /></span><span>Everything on all your devices</span></div>
                </div>
              </div>

              <div className="bill-pro">
                <div className="bill-pro-ico"><Sparkles size={16} strokeWidth={1.8} /></div>
                <div className="bill-pro-copy">
                  <div className="bill-pro-name">NOVI Pro — coming soon</div>
                  <div className="bill-hint">Advanced university shortlists, parent coaching and exam strategy.</div>
                </div>
                <span className="chip mid">Invite only</span>
              </div>
            </>
          ) : null}
        </section>
      </div>
    </>
  );
}

function TagInput({ onCommit, placeholder }) {
  return (
    <input
      className="tag-field"
      placeholder={placeholder}
      autoComplete="off"
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === ",") {
          e.preventDefault();
          const v = e.currentTarget.value.trim();
          if (v) { onCommit(v); e.currentTarget.value = ""; }
        }
      }}
      onBlur={(e) => {
        setTimeout(() => {
          const v = e.target.value.trim();
          if (v) { onCommit(v); e.target.value = ""; }
        }, 120);
      }}
    />
  );
}