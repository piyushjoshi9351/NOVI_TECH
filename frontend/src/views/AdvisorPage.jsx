import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { api, esc } from "../api";
import { showLoader, toast } from "../ui";

/** Matches MAX_ADVISOR_QUESTION on the backend. Enforced here too so we don't
 *  spend a round trip (or a rate-limit slot) on a question that will 422. */
const MAX_Q = 800;
/** Matches MAX_ADVISOR_HISTORY_TURNS on the backend. */
const MAX_TURNS = 12;

const STARTERS = [
  { label: "What's captured their attention lately?", icon: "✦" },
  { label: "How can I encourage them without taking over?", icon: "◈" },
  { label: "What could we do together this month?", icon: "◆" },
  { label: "What should I check in about right now?", icon: "◇" },
];

/** Scope label shown in the consent strip. */
function scopeLabel(s) {
  if (s === "memory") return "growth history";
  if (s === "insights") return "insights";
  return s;
}

/**
 * Render a safe subset of markdown: paragraphs, "- " bullets, and **bold**.
 *
 * Deliberately NOT dangerouslySetInnerHTML and no markdown library. Novi's
 * answers are LLM text, so this stays a whitelist of transforms over already
 * escaped output rather than a raw HTML sink.
 */
function RichText({ text }) {
  const blocks = String(text ?? "").split(/\n{2,}/).filter((b) => b.trim());
  return (
    <>
      {blocks.map((block, bi) => {
        const lines = block.split("\n").filter((l) => l.trim());
        const bulletish = lines.every((l) => /^\s*[-*•]\s+/.test(l));
        if (bulletish) {
          return (
            <ul key={bi} className="ch-bullets">
              {lines.map((l, li) => (
                <li key={li}>{inline(l.replace(/^\s*[-*•]\s+/, ""))}</li>
              ))}
            </ul>
          );
        }
        return <p key={bi}>{lines.map((l, li) => inline(l, li))}</p>;
      })}
    </>
  );
}

/** Inline **bold** only. Returns nodes, never HTML. */
function inline(line, keyBase = 0) {
  const out = [];
  const re = /\*\*([^*]+)\*\*/g;
  let last = 0;
  let m;
  let n = 0;
  while ((m = re.exec(line)) !== null) {
    if (m.index > last) out.push(line.slice(last, m.index));
    out.push(<strong key={`${keyBase}b${n++}`}>{m[1]}</strong>);
    last = m.index + m[0].length;
  }
  if (last < line.length) out.push(line.slice(last));
  return out.length ? out : line;
}

function clockOf(ts) {
  try {
    return new Date(ts).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
  } catch {
    return "";
  }
}

/**
 * Parent Advisor — a chat application over the existing `/parents/advisor`
 * endpoint.
 *
 * The properties this screen is built around:
 *
 * * **Session-local.** Threads live in React state for this tab only. Nothing is
 *   persisted, so a parent's questions never enter the student's record.
 * * **Consent-scoped.** Novi answers only from the sections the student chose to
 *   share. The strip above the thread says exactly what that is, per child, so
 *   the parent can see the boundary rather than guess at it. Asking about
 *   something unshared gets "that's between you and them" — the correct answer,
 *   not a limitation to apologise for.
 * * **Conversational.** Prior turns are sent as bounded `history` so follow-ups
 *   ("and robotics?") work. The backend uses them for that one answer and
 *   discards them; only `parent`/`novi` roles are accepted.
 * * **One thread per child.** Switching children switches thread, so a question
 *   about one child is never answered in the context of another.
 * * **Rate limited.** 20 questions a minute per parent, so the composer is
 *   disabled while one is in flight rather than letting a double-click burn the
 *   window.
 */
export default function AdvisorPage() {
  const [links, setLinks] = useState(null);
  const [childId, setChildId] = useState(null);
  // { [studentId]: [{ id, role, text, at }] }
  const [threads, setThreads] = useState({});
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  const [copied, setCopied] = useState(null);

  const scrollRef = useRef(null);
  const inputRef = useRef(null);
  const activeKey = childId == null ? null : String(childId);
  const thread = useMemo(() => (activeKey ? threads[activeKey] || [] : []), [threads, activeKey]);

  useEffect(() => {
    let alive = true;
    api("/parent/students")
      .then((d) => {
        if (!alive) return;
        const active = (d?.links || []).filter((l) => l.status === "active");
        setLinks(active);
        setChildId(active[0]?.student_id ?? null);
      })
      .catch((ex) => { if (alive) setLinks([]); toast(ex.message); });
    return () => { alive = false; };
  }, []);

  // Pin to the newest message, but only when the thread actually grows.
  const threadLen = thread.length;
  useLayoutEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [threadLen, busy, activeKey]);

  const child = useMemo(
    () => (links || []).find((l) => String(l.student_id) === activeKey) || links?.[0] || null,
    [links, activeKey]
  );
  const shared = (child?.scopes || []).filter((s) => s !== "basic");

  const tooLong = q.trim().length > MAX_Q;
  const canAsk = Boolean(child) && q.trim().length > 0 && !tooLong && !busy;

  const ask = useCallback(async (text) => {
    const question = (text ?? q).trim();
    const kid = child?.student_id;
    // Bail if there is nothing to send, no child to ask about, or a request is
    // already in flight (the 20/min limiter means a double-click is expensive).
    if (!question || busy || kid == null) return;

    // Snapshot prior turns before appending, so we never echo the new question
    // back into its own context. Oldest-first, then the most recent N.
    const prior = threads[String(kid)] || [];
    const history = prior
      .slice(-MAX_TURNS)
      .map((m) => ({ role: m.role === "parent" ? "parent" : "novi", content: m.text }));

    const now = Date.now();
    const mine = { id: `p${now}`, role: "parent", text: question, at: now };
    setThreads((t) => ({ ...t, [String(kid)]: [...(t[String(kid)] || []), mine] }));
    setQ("");
    setBusy(true);
    showLoader(true);

    try {
      const r = await api("/parents/advisor", {
        method: "POST",
        body: JSON.stringify({ question, child_id: kid, history }),
      });
      const text2 = r.answer || "";
      setThreads((t) => ({
        ...t,
        [String(kid)]: [...(t[String(kid)] || []), { id: `n${now}`, role: "novi", text: text2, at: Date.now() }],
      }));
    } catch (ex) {
      toast(ex.message);
    } finally {
      setBusy(false);
      showLoader(false);
      inputRef.current?.focus();
    }
  }, [busy, child, q, threads]);

  const clear = () => {
    if (!activeKey || !thread.length) return;
    setThreads((t) => ({ ...t, [activeKey]: [] }));
    setCopied(null);
    inputRef.current?.focus();
  };

  const copy = async (id, text) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(id);
      setTimeout(() => setCopied(null), 1600);
    } catch {
      toast("Couldn't copy — select the text instead.", "bad");
    }
  };

  // "/" focuses the composer, like every other chat app.
  useEffect(() => {
    const onKey = (e) => {
      if (e.key === "/" && document.activeElement?.tagName !== "TEXTAREA" &&
          document.activeElement?.tagName !== "INPUT") {
        e.preventDefault();
        inputRef.current?.focus();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  if (links && !links.length) {
    return (
      <div className="pd-wrap">
        <div className="pd-hero">
          <div className="eyebrow">Parent Advisor</div>
          <h1>Nothing to advise on yet</h1>
          <p>
            Once a student approves your request, Novi can answer questions using only
            the parts of their journey they choose to share with you.
          </p>
        </div>
      </div>
    );
  }

  const name = child?.student?.first_name || "your child";

  return (
    <div className="ch">
      {/* ---------------------------------------------------------- header */}
      <header className="ch-head">
        <div className="ch-head-id">
          <span className="ch-avatar" aria-hidden="true">N</span>
          <div>
            <div className="ch-title">Novi</div>
            <div className="ch-sub">
              {child ? <>Answers about <b>{esc(name)}</b></> : "Parent advisor"}
            </div>
          </div>
        </div>

        <div className="ch-head-act">
          {links?.length > 1 ? (
            <div className="pd-switch" role="tablist" aria-label="Choose a child">
              {links.map((l) => {
                const on = String(l.student_id) === activeKey;
                return (
                  <button
                    key={l.id}
                    role="tab"
                    aria-selected={on}
                    className={`pd-switch-btn ${on ? "on" : ""}`}
                    onClick={() => { setChildId(l.student_id); setCopied(null); }}
                  >
                    {esc(l.student?.first_name || "Child")}
                  </button>
                );
              })}
            </div>
          ) : null}
          <button className="ch-icon-btn" onClick={clear} disabled={!thread.length} title="Clear this conversation">
            <svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true">
              <path d="M4 7h16M9 7V5h6v2m-8 0 1 13h8l1-13" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
            <span className="ch-sr">Clear conversation</span>
          </button>
        </div>
      </header>

      {/* -------------------------------------------------- consent boundary */}
      {child ? (
        <div className="ch-consent">
          <span className="ch-consent-ico" aria-hidden="true">◈</span>
          {shared.length ? (
            <>
              <b>{esc(name)}</b> has shared{" "}
              {shared.map((s, i) => (
                <span key={s}>
                  {i > 0 ? " and " : ""}<b>{scopeLabel(s)}</b>
                </span>
              ))}{" "}
              with you. Novi answers from those only.
            </>
          ) : (
            <>
              Only the <b>basic overview</b> is shared with you, so answers will be
              general. More detail unlocks as {esc(name)} chooses to share more.
            </>
          )}
        </div>
      ) : null}

      {/* --------------------------------------------------------- thread */}
      <div className="ch-scroll" ref={scrollRef}>
        {!thread.length ? (
          <div className="ch-intro">
            <div className="ch-intro-mark" aria-hidden="true">N</div>
            <h2>
              {child ? <>Ask about {esc(name)}</> : "Ask Novi"}
            </h2>
            <p>
              I answer from the parts of {child ? esc(name) : "their journey"} your
              child chose to share — never their private conversations with me, their
              reflections, or their diary.
            </p>
            <div className="ch-starters">
              {STARTERS.map((s) => (
                <button key={s.label} className="ch-starter" onClick={() => ask(s.label)} disabled={busy}>
                  <span className="ch-starter-ico" aria-hidden="true">{s.icon}</span>
                  <span>{s.label}</span>
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div className="ch-msgs">
            {thread.map((m) => (
              <div key={m.id} className={`ch-msg ${m.role}`}>
                {m.role === "novi" ? <span className="ch-msg-av" aria-hidden="true">N</span> : null}
                <div className="ch-bubble">
                  {m.role === "novi" ? <RichText text={m.text} /> : esc(m.text)}
                  <div className="ch-msg-foot">
                    <span>{clockOf(m.at)}</span>
                    <button
                      className="ch-copy"
                      onClick={() => copy(m.id, m.text)}
                      title="Copy this answer"
                    >
                      {copied === m.id ? "Copied" : "Copy"}
                    </button>
                  </div>
                </div>
              </div>
            ))}

            {busy ? (
              <div className="ch-msg novi">
                <span className="ch-msg-av" aria-hidden="true">N</span>
                <div className="ch-bubble ch-typing" aria-label="Novi is thinking">
                  <i /><i /><i />
                </div>
              </div>
            ) : null}
          </div>
        )}
      </div>

      {/* ------------------------------------------------------- composer */}
      <div className="ch-compose">
        {tooLong ? (
          <div className="ch-warn">
            Keep it under {MAX_Q} characters ({q.trim().length} so far).
          </div>
        ) : null}
        <div className="ch-compose-row">
          <textarea
            ref={inputRef}
            className="ch-input"
            rows={1}
            placeholder={child ? `Ask Novi about ${name}…` : "Ask Novi…"}
            aria-label="Ask Novi a question"
            value={q}
            disabled={busy}
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey && canAsk) {
                e.preventDefault();
                ask();
              }
            }}
          />
          <button className="ch-send" onClick={() => ask()} disabled={!canAsk} aria-label="Send">
            {busy ? (
              <span className="ch-spin" aria-hidden="true" />
            ) : (
              <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
                <path d="M4 12h15m0 0-6-6m6 6-6 6" fill="none" stroke="currentColor"
                      strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            )}
          </button>
        </div>
        <div className="ch-note">
          <span>Kept in this tab only — never saved to your child&apos;s record.</span>
          <span className="ch-kbd"><b>Enter</b> send · <b>Shift+Enter</b> newline · <b>/</b> to focus</span>
        </div>
      </div>
    </div>
  );
}