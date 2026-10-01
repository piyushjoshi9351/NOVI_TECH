import { useEffect, useId, useRef, useState } from "react";
import { Link } from "next/link";
import { ringColor } from "./api";

/* ------------------------------------------------------------------ loader */
let _loaderTimer = null;
let _setLoaderVisible = null;

export function showLoader(b) {
  clearTimeout(_loaderTimer);
  if (b) _loaderTimer = setTimeout(() => _setLoaderVisible && _setLoaderVisible(true), 150);
  else _setLoaderVisible && _setLoaderVisible(false);
}

export function Loader() {
  const [visible, setVisible] = useState(false);
  useEffect(() => {
    _setLoaderVisible = setVisible;
    return () => { _setLoaderVisible = null; };
  }, []);
  return (
    <div id="loader" className={visible ? "loader" : "loader hidden"}>
      <div className="brand-mark">N</div>
      <p>NOVI is thinking…</p>
    </div>
  );
}

/* ------------------------------------------------------------------ toasts */
let _emitToast = null;
let _toastSeq = 0;

export function toast(msg, tone = "ok") {
  if (_emitToast) _emitToast(msg, tone);
}

export function ToastHost() {
  const [items, setItems] = useState([]);
  useEffect(() => {
_emitToast = (msg, tone) => {
        const id = ++_toastSeq;
        // Plain text, rendered as a text child. esc() no longer produces HTML
        // entities, so this must not go through dangerouslySetInnerHTML.
        setItems((arr) => [...arr, { id, msg: String(msg ?? ""), tone }]);
      setTimeout(() => setItems((arr) => arr.map((i) => (i.id === id ? { ...i, out: true } : i))), 2800);
      setTimeout(() => setItems((arr) => arr.filter((i) => i.id !== id)), 3100);
    };
    return () => { _emitToast = null; };
  }, []);
  if (!items.length) return null;
  const icons = { ok: "✓", err: "⚠", info: "✦" };
  return (
    <div className="toasts">
      {items.map((i) => (
        <div key={i.id} className={`toast ${i.tone}${i.out ? " out" : ""}`}>
          <span className="t-ico">{icons[i.tone] || icons.ok}</span>
          <span>{i.msg}</span>
        </div>
      ))}
    </div>
  );
}

/* ------------------------------------------------------------------ ring chart (svg donut) */
export function Ring({ pct, label = "", size = 56 }) {
  const uid = useId().replace(/:/g, "").replace(/[^a-zA-Z0-9]/g, "");
  const r = (size - 8) / 2, c = 2 * Math.PI * r, off = c * (1 - Math.min(100, Math.max(0, pct)) / 100);
  return (
    <div className="ring-w" style={{ width: size, height: size }}>
      <svg width={size} height={size}>
        <defs>
          <linearGradient id={`ring-grad-${uid}`} x1="0" y1="0" x2="1" y2="1">
            <stop offset="0" stopColor="#8b6cff" />
            <stop offset="1" stopColor="#4ac7f0" />
          </linearGradient>
        </defs>
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="rgba(255,255,255,0.07)" strokeWidth="7" />
        <circle
          cx={size / 2} cy={size / 2} r={r} fill="none"
          stroke={`url(#ring-grad-${uid})`} strokeWidth="7" strokeLinecap="round"
          strokeDasharray={c.toFixed(1)} strokeDashoffset={off.toFixed(1)}
          style={{ transition: "stroke-dashoffset .8s cubic-bezier(.16,1,.3,1)" }}
        />
      </svg>
      <span className="ring-val" style={{ color: ringColor(pct) }}>{label || Math.round(pct) + "%"}</span>
    </div>
  );
}

/* bar (progress track / fill) */
export function Bar({ v, color }) {
  return (
    <div className="progress-track">
      <div className="progress-fill" style={{ width: `${Math.min(100, Math.max(0, v))}%`, background: color || ringColor(v) }} />
    </div>
  );
}

export function EmptyState({ title, sub }) {
  return (
    <div className="card">
      <h3>{title}</h3>
      {sub ? <p className="mt small">{sub}</p> : null}
    </div>
  );
}

export function Kicker({ children }) {
  return <div className="kicker">{children}</div>;
}

/* pill (span) */
export function Pill({ label, tone = "" }) {
  return <span className={`pill ${tone}`}>{label}</span>;
}

/* ------------------------------------------------------------------ DNA context bar */
const DNA_NOTES = {
  careers: (c) => (
    <>Novi builds every match and "why this could be you" from your DNA. Your strongest signal right now is <b>{c.top_zone || c.top_interest || "your interests"}</b> — start with the matches ranked highest below.</>
  ),
  universities: (c) => (
    <>The programs below are weighted toward your DNA{c.top_zone ? <>, with the strongest alignment in <b>{c.top_zone}</b></> : ""}{c.subjects && c.subjects.length ? <> and your subjects <b>{c.subjects.slice(0, 3).join(", ")}</b></> : ""}.</>
  ),
  roadmap: (c) => (
    <>Your roadmap and weekly priorities are generated around what matters to you{c.top_goal ? <> — <b>{c.top_goal}</b></> : ""}. Tick steps off and Novi carries your progress forward.</>
  ),
  passport: (c) => (
    <>Novi reads your passport as proof of your DNA. With your direction at <b>{c.top_zone || c.top_interest || "not set yet"}</b>, the highest-value additions are the ones that prove that story.</>
  ),
  checkin: (c) => (
    <>Novi weighs every check-in against the goals in your DNA{c.goals && c.goals.length ? <> — <b>{c.goals.slice(0, 2).join("</b> and <b>")}</b></> : ""}.</>
  ),
};

export function DnaBar({ c, section }) {
  if (!c || !c.filled) {
    return (
      <div className="card novi-box mb">
        <span className="novi-avatar">N</span>
        <span>Everything on this page personalises from your Career DNA.</span>
        <Link href="/dna" className="small" style={{ color: "var(--accent)" }}>Set your direction now →</Link>
      </div>
    );
  }
  const chips = [];
  if (c.top_zone) chips.push({ key: "tz", tone: "acc", label: c.top_zone });
  (c.career_zones || []).slice(1, 3).forEach((z) => chips.push({ key: `cz-${z}`, tone: "", label: z }));
  (c.interests || []).slice(0, 2).forEach((i) => chips.push({ key: `int-${i}`, tone: "", label: i }));
  return (
    <div className="card novi-box mb">
      <div className="between">
        <h3 style={{ margin: 0 }}>Based on your Career DNA</h3>
        <Link href="/dna" className="small" style={{ color: "var(--accent)" }}>View DNA →</Link>
      </div>
      <p className="small" style={{ marginTop: 8 }}>{DNA_NOTES[section] ? DNA_NOTES[section](c) : null}</p>
      {chips.length ? (
        <div className="row" style={{ marginTop: 10 }}>
          {chips.map((ch) => <span key={ch.key} className={`chip ${ch.tone}`}>{ch.label}</span>)}
        </div>
      ) : null}
    </div>
  );
}

/* ------------------------------------------------------------------ portal modal (passport sheet etc.) */
export function Modal({ onClose, children, cls = "" }) {
  const wrapRef = useRef(null);
  const prevFocus = useRef(null);
  useEffect(() => {
    prevFocus.current = document.activeElement;
    const w = wrapRef.current;
    requestAnimationFrame(() => w && w.classList.add("on"));
    const onKey = (e) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("keydown", onKey);
      if (prevFocus.current && prevFocus.current.focus) prevFocus.current.focus();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  return (
    <div className="modal-wrap" id="novi-modal" ref={wrapRef}>
      <div className="modal-bg" data-modal-close onClick={onClose} />
      <div className={`modal ${cls}`} role="dialog" aria-modal="true">{children}</div>
    </div>
  );
}