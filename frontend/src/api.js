/* ------------------------------------------------------------------ *
 * NOVI React frontend — API client with the same cached-GET semantics
 * as the original vanilla app: 15s warm cache, stale-while-revalidate,
 * in-flight dedupe and write-based invalidation.
 * ------------------------------------------------------------------ */

export const API = "/api/v1";

let _token = null;
export function setApiToken(t) { _token = t; }
export function getApiToken() {
  if (_token === null && typeof window !== "undefined") _token = window.localStorage.getItem("novi_token");
  return _token;
}

const _apiCache = new Map();     // "GET /path" -> { data, ts }
const _apiInflight = new Map();  // "GET /path" -> Promise
let _apiGen = 0;                 // bumped on every write, so stale reads can't re-cache
const API_TTL = 15000;

function _headers() {
  const h = { "Content-Type": "application/json" };
  if (getApiToken()) h.Authorization = `Bearer ${getApiToken()}`;
  return h;
}

export function clearApiCache() { _apiCache.clear(); _apiInflight.clear(); _apiGen++; }

const _blobUrls = new Map();

/* Binary counterpart to `api`. Returns an object URL for an image endpoint,
   or null when there is nothing to show -- including 404, which is a normal
   outcome for a child with no photo, so it is cached as null rather than
   retried on every render. Object URLs are revoked on logout. */
export function apiImage(path) {
  if (_blobUrls.has(path)) return _blobUrls.get(path);
  if (!getApiToken()) return null;
  const p = fetch(API + path, { headers: _headers(), signal: AbortSignal.timeout(30000) })
    .then((res) => (res.ok ? res.blob() : null))
    .then((blob) => (blob ? URL.createObjectURL(blob) : null))
    .catch(() => null);
  _blobUrls.set(path, p);
  return p;
}

export function revokeImageUrls() {
  for (const p of _blobUrls.values()) {
    Promise.resolve(p).then((u) => { if (u) URL.revokeObjectURL(u); }).catch(() => {});
  }
  _blobUrls.clear();
}

function _revalidate(path, opts, key) {
  const gen = _apiGen;
  const p = fetch(API + path, { ...opts, headers: _headers() })
    .then((r) => (r.ok ? r.json() : null))
    .then((d) => { if (d !== null && gen === _apiGen) _apiCache.set(key, { data: d, ts: Date.now() }); })
    .catch(() => {});
  _apiInflight.set(key, p);
  p.finally(() => { if (_apiInflight.get(key) === p) _apiInflight.delete(key); });
}

/* opts.fresh forces a real network read, bypassing the warm cache. Explicit
   refresh buttons need it: without it they'd re-read their own cached GET and
   look like they did nothing. */
export async function api(path, opts = {}) {
  const method = (opts.method || "GET").toUpperCase();
  const fresh = !!opts.fresh;
  const key = method + " " + path;

  if (method !== "GET") {
    clearApiCache(); // a change happened — reads must refetch
  } else if (fresh) {
    _apiCache.delete(key);
  } else {
    const hit = _apiCache.get(key);
    if (hit && Date.now() - hit.ts < API_TTL) return hit.data;   // warm: instant
    // Expired reads must return the newly fetched value to the caller.  // stale: instant + refresh behind
    if (_apiInflight.has(key)) return _apiInflight.get(key);     // dedupe parallel calls
  }

  const gen = _apiGen;
  const { fresh: _ignored, ...fetchOpts } = opts;
  const run = async () => {
    const res = await fetch(API + path, { ...fetchOpts, signal: opts.signal || AbortSignal.timeout(110000), headers: _headers() });
    let data = null;
    try { data = await res.json(); } catch (_) {}
    if (!res.ok) {
      // FastAPI puts a string in `detail` for HTTPException but a LIST of
      // objects for 422 validation errors, so normalise both into a sentence.
      const d = data && data.detail;
      let msg;
      if (typeof d === "string") msg = d;
      else if (Array.isArray(d)) msg = d.map((e) => e && e.msg).filter(Boolean).join(" ");
      else msg = `Request failed (${res.status})`;
      const err = new Error(msg);
      // `status` lets a caller tell a scope denial (403) from a real failure
      // without string-matching the message. Additive: `message` is unchanged.
      err.status = res.status;
      err.detail = d;
      throw err;
    }
    if (method === "GET" && gen === _apiGen) _apiCache.set(key, { data, ts: Date.now() });
    if (method !== "GET") clearApiCache();
    return data;
  };

  const p = run().finally(() => { if (method === "GET" && _apiInflight.get(key) === p) _apiInflight.delete(key); });
  if (method === "GET") _apiInflight.set(key, p);
  return p;
}

/* ------------------------------------------------------------------ streaming chat
 * Server-sent events over fetch (EventSource can't POST). Parses the `data:`
 * frames the backend emits and hands each decoded event to `onEvent`.
 * Throws on transport errors and on {"type":"error"} frames.
 */
export async function streamChat({ message, conversation_id = null, signal, onEvent }) {
  clearApiCache(); // a conversation is about to change — drop cached GETs
  const res = await fetch(API + "/chat/stream", {
    method: "POST",
    headers: { ..._headers(), Accept: "text/event-stream" },
    body: JSON.stringify({ message, conversation_id }),
    signal,
  });
  if (!res.ok || !res.body) {
    let detail = `Request failed (${res.status})`;
    try { const j = await res.json(); if (j && j.detail) detail = j.detail; } catch (_) {}
    throw new Error(detail);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  const handleFrame = (frame) => {
    const line = frame.split("\n").find((l) => l.startsWith("data:"));
    if (!line) return;
    const payload = line.slice(5).trim();
    if (!payload) return;
    let event;
    try { event = JSON.parse(payload); } catch (_) { return; }
    if (event.type === "error") throw new Error(event.error || "Stream interrupted");
    if (onEvent) onEvent(event);
  };

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, "\n");
    let idx;
    while ((idx = buffer.indexOf("\n\n")) !== -1) {
      handleFrame(buffer.slice(0, idx));
      buffer = buffer.slice(idx + 2);
    }
  }
  if (buffer.trim()) handleFrame(buffer);
}

/* ------------------------------------------------------------------ helpers */
/* React escapes text children and attribute values for us, so this must NOT
   pre-escape to HTML entities. Doing so rendered entities literally (a real
   apostrophe showed up as the text "&#39;"). It only normalises to a string. */
export function esc(s) { return String(s ?? ""); }

export const MOODS = { great: "😄", good: "🙂", okay: "😕", low: "😞" };
export const moodIcon = (m) => MOODS[m] || "🙂";

export function ringColor(v) { return v >= 70 ? "var(--good)" : v >= 40 ? "var(--warn)" : "var(--bad)"; }

export function bellTime() { const h = new Date().getHours(); return h < 12 ? "morning" : h < 17 ? "afternoon" : "evening"; }

export function initials(name) {
  const p = String(name || "NOVI").trim().split(/\s+/).filter(Boolean);
  return (p[0]?.[0] || "N").toUpperCase() + (p[1]?.[0] || "").toUpperCase();
}

export function fmtJoined(iso) {
  if (!iso) return "NOVI member";
  const d = new Date(iso);
  return isNaN(d) ? "NOVI member" : `Joined ${d.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" })}`;
}

export function safeHttpUrl(u) {
  const s = String(u || "").trim();
  return /^https?:\/\//i.test(s) ? s : null;
}

export function prettyDate(d) {
  if (!d) return "";
  const dt = new Date(String(d).length === 10 ? d + "T00:00:00" : d);
  return isNaN(dt) ? String(d) : dt.toLocaleDateString([], { year: "numeric", month: "short", day: "numeric" });
}

/* DNA context — memoised once per session, like the vanilla app */
let _dnaCtx = null;
export function refreshDnaContext() { _dnaCtx = null; }

export async function getDnaContext() {
  try { _dnaCtx = await api("/dna/context"); } catch (_) { _dnaCtx = { filled: false }; }
  return _dnaCtx;
}

/* ------------------------------------------------------------------ prefetch */
const ROUTE_WARM = {
  dashboard: ["/dashboard"],
  chat: ["/chat/conversations"],
  dna: ["/dna", "/dna/context"],
  careers: ["/careers?limit=50", "/careers/categories", "/careers/matches", "/dna/context"],
  universities: ["/universities?limit=30", "/universities/filters", "/universities/recommended", "/dna/context"],
  roadmap: ["/roadmap/tasks", "/roadmap/goals", "/roadmap/priorities", "/roadmap", "/dna/context"],
  passport: ["/passport", "/passport/completion", "/dna/context"],
  checkin: ["/checkins/current", "/checkins", "/checkins/graph", "/checkins/planner/day", "/dna/context"],
  overview: ["/parents/dashboard"],
  parent: ["/parent/students"],
  profile: ["/auth/me", "/dna", "/auth/links"],
};

let _warmAllStarted = false;
export function resetWarmAll() { _warmAllStarted = false; }

export function warmRoute(key) {
  if (!getApiToken()) return;
  (ROUTE_WARM[key] || []).forEach((p) => { if (!_apiCache.has("GET " + p)) api(p).catch(() => {}); });
}

const PARENT_ROUTES = new Set(["parent", "overview"]);

export function warmAllRoutes(role) {
  if (_warmAllStarted || !getApiToken()) return;
  _warmAllStarted = true;
  const keys = Object.keys(ROUTE_WARM).filter((k) => role !== "parent" || PARENT_ROUTES.has(k));
  let i = 0;
  const step = () => {
    if (!getApiToken() || i >= keys.length) return;
    warmRoute(keys[i++]);
    setTimeout(step, 220);
  };
  setTimeout(step, 500);
}

/* ------------------------------------------------------------------ consts shared across pages */
export const STAGE_META = {
  discover: { icon: "🔍", label: "Discover Yourself", desc: "Interests, strengths and the foundation of your story." },
  explore: { icon: "🧭", label: "Explore & Experiment", desc: "Broaden horizons, test ideas and build habits." },
  build: { icon: "🛠️", label: "Build Your Profile", desc: "Create projects and evidence of your skill." },
  apply: { icon: "🚀", label: "Apply With Confidence", desc: "Applications, decisions and the next chapter." },
  foundations: { icon: "⚡", label: "Short-term · do this now", desc: "Your immediate next steps from what you told Novi." },
};

export const PP_CATS = {
  projects: { icon: "🛠️", label: "Projects", tag: "Show what you built.", rgb: "139,108,255" },
  competitions: { icon: "🏆", label: "Competitions", tag: "Show what you challenged yourself with.", rgb: "251,191,36" },
  certifications: { icon: "🎓", label: "Certifications", tag: "Show what you've learned.", rgb: "52,211,153" },
  leadership: { icon: "🙌", label: "Leadership", tag: "Show how you've contributed.", rgb: "244,114,182" },
  research: { icon: "🔬", label: "Research", tag: "Show how you've explored.", rgb: "74,199,240" },
  activities: { icon: "🎯", label: "Activities", tag: "Show what makes you, you.", rgb: "251,146,60" },
  achievements: { icon: "⭐", label: "Achievements", tag: "Show what you've earned.", rgb: "167,139,250" },
};
export const PP_ORDER = ["projects", "competitions", "certifications", "leadership", "research", "activities"];

export const PP_LEVELS = [
  { min: 0, name: "Rookie", emoji: "🌱", tip: "Every legend starts somewhere. Add your first win — it takes a minute." },
  { min: 25, name: "Explorer", emoji: "🚀", tip: "Nice start! Keep collecting to level up." },
  { min: 50, name: "Rising Star", emoji: "⭐", tip: "You're building a strong profile. Here's what would make it even stronger." },
  { min: 75, name: "Legend", emoji: "🏆", tip: "Standout profile! Time to polish it and show it off." },
];

export function ppLevel(score) {
  let lv = PP_LEVELS[0], i = 0;
  PP_LEVELS.forEach((l, idx) => { if (score >= l.min) { lv = l; i = idx; } });
  return { ...lv, next: PP_LEVELS[i + 1] || null };
}

export function ppGuessCat(text) {
  const t = String(text || "").toLowerCase();
  if (/competi|olymp|hackathon|contest/.test(t)) return "competitions";
  if (/certif|course|learn|training|bootcamp/.test(t)) return "certifications";
  if (/leader|club|volunteer|president|team captain/.test(t)) return "leadership";
  if (/research|paper|study|experiment|lab/.test(t)) return "research";
  if (/activit|sport|music|art|dance|theatre|volunteer/.test(t)) return "activities";
  return "projects";
}

export function m3DateRange(a, b) {
  if (!a && !b) return "Not scheduled";
  if (a && b) return `${prettyDate(a)} → ${prettyDate(b)}`;
  return prettyDate(a || b);
}

export function m3AdaptLabel(a) {
  switch (a.action_type) {
    case "add_task": return `Add task “${(a.task && a.task.title) || "new task"}”`;
    case "skip_task": return "Skip a pending task";
    case "reschedule_task": return `Move a task to ${prettyDate(a.new_target_date)}`;
    case "adjust_priority": return `Set a task to ${a.new_priority} priority`;
    case "reschedule_roadmap": return `Move the plan deadline to ${prettyDate(a.new_target_date)}`;
    default: return a.action_type || "update";
  }
}

/* ------------------------------------------------------------------ accent + prefs (device-only) */
export const NOVI_ACCENTS = {
  aurora: { a: "#8b6cff", a2: "#4ac7f0", name: "Aurora", emoji: "🪻" },
  ocean: { a: "#38bdf8", a2: "#34d399", name: "Ocean", emoji: "🌊" },
  ember: { a: "#fb923c", a2: "#f87171", name: "Ember", emoji: "🔥" },
  mint: { a: "#34d399", a2: "#a3e635", name: "Mint", emoji: "🌿" },
  rose: { a: "#f472b6", a2: "#a78bfa", name: "Rose", emoji: "🌷" },
};

export const PS_NOTIFS = [
  ["checkin_reminders", "Weekly check-in reminders", "A gentle nudge when it's time for your weekly reflection."],
  ["career_alerts", "Career match alerts", "New careers and matches that light up your DNA."],
  ["goal_nudges", "Goal & roadmap nudges", "When a goal is at risk or a roadmap step is due."],
  ["parent_updates", "Parent progress summary", "A calm monthly summary your parent sees after linking."],
  ["digest", "NOVI digest", "A monthly recap of your wins, skills and progress."],
];

export const PS_DEFAULTS = { checkin_reminders: true, career_alerts: true, goal_nudges: true, parent_updates: true, digest: false, appearance: "aurora", theme: null };

function hexToRgba(hex, alpha) {
  const n = parseInt(hex.slice(1), 16);
  return `rgba(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}, ${alpha})`;
}

export function applyAccent(key) {
  const acc = NOVI_ACCENTS[key] || NOVI_ACCENTS.aurora;
  const s = document.documentElement.style;
  s.setProperty("--accent", acc.a);
  s.setProperty("--accent-2", acc.a2);
  s.setProperty("--grad", `linear-gradient(135deg, ${acc.a} 0%, ${acc.a2} 100%)`);
  s.setProperty("--grad-soft", `linear-gradient(135deg, ${hexToRgba(acc.a, 0.16)}, ${hexToRgba(acc.a2, 0.1)})`);
  s.setProperty("--glow", `0 0 0 1px ${hexToRgba(acc.a, 0.35)}, 0 10px 34px ${hexToRgba(acc.a, 0.28)}`);
}

export function readPrefs() {
  return { ...PS_DEFAULTS, ...(JSON.parse(localStorage.getItem("novi_prefs") || "{}") || {}) };
}

export function savePrefs(prefs) {
  localStorage.setItem("novi_prefs", JSON.stringify(prefs));
  return prefs;
}

export function bootAppearance() {
  try {
    const prefs = readPrefs();
    if (prefs.appearance) applyAccent(prefs.appearance);
    applyTheme(prefs.theme);
  } catch (_) {}
}

export function setPrefKey(key, value) {
  const p = readPrefs();
  p[key] = value;
  savePrefs(p);
  return p;
}

function systemTheme() {
  return typeof window !== "undefined" && window.matchMedia && window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
}

export function applyTheme(theme) {
  const t = theme === "light" || theme === "dark" ? theme : systemTheme();
  document.documentElement.setAttribute("data-theme", t);
  const m = document.querySelector('meta[name="theme-color"]');
  if (m) m.setAttribute("content", t === "light" ? "#f3f5fb" : "#060a13");
  return t;
}

export function getTheme() {
  const p = readPrefs();
  return p.theme === "light" || p.theme === "dark" ? p.theme : systemTheme();
}