"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowRight, Check, Loader2, Send, Sparkles, Volume2, VolumeX, X } from "lucide-react";
import { api, initials } from "../api";
import { useAuth } from "../auth";
import { toast } from "../ui";
import { stopAll, speakText, onSpeakStateChange, VOICE_KEY } from "../speech";

const GREETING =
  "Hi, I'm Novi 👋\n\nBefore I start helping you, I want to get to know you.\nThere are no right or wrong answers. You don't need to know what you want to become.\nJust be yourself — I'll figure out the rest.";

const WELCOME_PATH = "https://novi.socratic.school";

export default function OnboardingPage() {
  const { user, refreshUser } = useAuth();
  const router = useRouter();
  const [flow, setFlow] = useState(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [draft, setDraft] = useState("");
  const [selected, setSelected] = useState([]);
  const [voiceOn, setVoiceOn] = useState(() => {
    if (typeof window === "undefined") return false;
    const stored = window.localStorage.getItem(VOICE_KEY);
    return stored === "1";
  });
  const [speaking, setSpeaking] = useState(false);
  const [introDone, setIntroDone] = useState(false);
  const logRef = useRef(null);
  const voiceOnRef = useRef(voiceOn);
  voiceOnRef.current = voiceOn;
  // Number of flagged empathy-reply bubbles already read aloud. Seeded on the
  // initial load (-1 = not yet seeded) so historical replies are never re-spoken
  // on a reload; only a reply that arrives after submitting a new answer gets
  // spoken, chained in front of the next question.
  const naviSpoken = useRef(-1);

  const firstName = user?.first_name?.split(" ")[0] || "there";

  const apply = useCallback((res) => {
    setFlow(res);
    if (res && res.error) toast(res.error, "err");
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      let state = await api("/onboarding/flow");
      if (!state.started) state = await api("/onboarding/flow/start", { method: "POST", body: "{}" });
      apply(state);
    } catch (ex) {
      toast(ex.message, "err");
    } finally {
      setLoading(false);
    }
  }, [apply]);

  useEffect(() => {
    load();
  }, [load]);

  // keep the conversation scrolled to the latest message
  useEffect(() => {
    const el = logRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [flow?.transcript?.length, loading, busy]);

  useEffect(() => {
    setSelected([]);
    setDraft("");
  }, [flow?.current?.id]);

  // Onboarding is finished: refresh the auth user so the app unlocks the
  // dashboard/nav, then hand over to the dashboard (short pause so the
  // completion summary stays readable).
  useEffect(() => {
    if (!flow?.done) return;
    refreshUser();
    const t = window.setTimeout(() => router.replace("/dashboard"), 1600);
    return () => window.clearTimeout(t);
  }, [flow?.done, refreshUser, router]);

  useEffect(() => () => stopAll(), []);

  // Track when Novi's voice is actually playing so the orb can glow/talk.
  useEffect(() => onSpeakStateChange(setSpeaking), []);

  const submit = useCallback(
    async (body) => {
      if (busy) return;
      setBusy(true);
      try {
        const res = await api("/onboarding/flow/answer", {
          method: "POST",
          body: JSON.stringify(body),
        });
        apply(res);
      } catch (ex) {
        toast(ex.message, "err");
      } finally {
        setBusy(false);
      }
    },
    [busy, apply],
  );

  const skip = useCallback(async () => {
    if (busy || !flow?.current) return;
    setBusy(true);
    try {
      const res = await api("/onboarding/flow/skip", {
        method: "POST",
        body: JSON.stringify({ step_id: flow.current.id }),
      });
      apply(res);
    } catch (ex) {
      toast(ex.message, "err");
    } finally {
      setBusy(false);
    }
  }, [busy, flow, apply]);

  // ---- voice: playback (server-rendered audio with a browser fallback) ----
  const warnedSpeech = useRef(false);
  const playQuestion = useCallback((text, onDone, onInterrupt) => {
    if (!text) {
      if (onDone) onDone();
      return;
    }
    if (!voiceOnRef.current) return; // voice off — never start speech
    speakText(text, {
      onDone,
      onInterrupt,
      onError: () => {
        if (warnedSpeech.current) return;
        warnedSpeech.current = true;
        toast("Novi's voice couldn't start here — you can always read the questions", "err");
      },
    });
  }, []);

  // Read the greeting first, then the current question — unless the greeting
  // is cut short (answering), or the step moved on while it played.
  const stepIdRef = useRef(null);
  stepIdRef.current = flow?.current?.id;
  const readGreetingThenQuestion = useCallback(() => {
    const q = flow?.current?.question;
    const stepId = flow?.current?.id;
    if (!q) {
      playQuestion(GREETING);
      return;
    }
    playQuestion(GREETING, () => {
      if (!voiceOnRef.current || stepIdRef.current !== stepId) return;
      playQuestion(q);
    });
  }, [flow, playQuestion]);

  // Speak the current question whenever it changes (only while voice is on),
  // reading any flagged empathy-reply bubbles first. On the very first view the
  // greeting is read first, then the first question.
  const freshGreeting = flow && !loading && !flow?.done && (flow.transcript || []).length === 0;
  const spokeGreeting = useRef(false);
  useEffect(() => {
    const replies = (flow?.transcript || []).filter((m) => m.role === "assistant" && m.reply);
    if (naviSpoken.current === -1) naviSpoken.current = replies.length;

    if (freshGreeting && voiceOn && !spokeGreeting.current) {
      spokeGreeting.current = true;
      readGreetingThenQuestion();
      return;
    }
    if (freshGreeting || !voiceOn) return;

    const q = flow?.current?.question;
    // A new empathy reply arrived with this step change: read it aloud first,
    // chained into the next question.
    if (replies.length > naviSpoken.current) {
      const pending = replies.slice(naviSpoken.current);
      naviSpoken.current = replies.length;
      const speakChain = (i) => {
        if (i >= pending.length) {
          if (q && stepIdRef.current === flow?.current?.id) playQuestion(q);
          return;
        }
        playQuestion(pending[i].content, () => speakChain(i + 1));
      };
      speakChain(0);
      return;
    }
    if (q) playQuestion(q);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [freshGreeting, flow?.current?.id, playQuestion, readGreetingThenQuestion]);

  const toggleVoice = () => {
    const next = !voiceOn;
    voiceOnRef.current = next;
    setVoiceOn(next);
    try {
      window.localStorage.setItem(VOICE_KEY, next ? "1" : "0");
    } catch (_) {
      /* ignore */
    }
    if (next) {
      if (flow && !flow.done && (flow.transcript || []).length === 0) {
        readGreetingThenQuestion();
      } else if (flow?.current?.question) {
        playQuestion(flow.current.question);
      }
    } else {
      stopAll();
    }
  };

  // Turning voice off (or unmounting) cuts playback, in-flight speak and mic.
  useEffect(() => {
    if (!voiceOn) stopAll();
  }, [voiceOn]);

  useEffect(
    () => () => {
      stopAll();
    },
    [],
  );

  if (loading) {
    return (
      <div className="chat-shell onboard">
        <div className="chat-main ob-loading">
          <Loader2 size={22} className="spin" />
        </div>
      </div>
    );
  }

  if (flow?.done) return <Reveal flow={flow} firstName={firstName} />;

  const cur = flow?.current;
  const transcript = flow?.transcript || [];
  const percent = flow?.percent ?? 0;
  const fresh = transcript.length === 0;
  const kind = cur?.kind || "free";
  const isMulti = kind === "multi";
  const isSingle = kind === "single";
  const selectedSafe = selected;

  const sendFree = () => {
    if (!draft.trim()) return;
    submit({ step_id: cur.id, answer: draft.trim() });
  };

  const pickSingle = (opt) => submit({ step_id: cur.id, answer: opt });
  const toggleMulti = (opt) => {
    if (selectedSafe.includes(opt)) {
      setSelected(selectedSafe.filter((o) => o !== opt));
    } else if (!cur.max_select || selectedSafe.length < cur.max_select) {
      setSelected([...selectedSafe, opt]);
    } else if (cur.max_select) {
      toast(`Pick up to ${cur.max_select}`, "err");
    }
  };
  const confirmMulti = () => {
    if (!selectedSafe.length) return;
    submit({ step_id: cur.id, values: selectedSafe, answer: selectedSafe.join(", ") });
  };

  return (
    <div className="chat-shell onboard">
      <section className="chat-main ob-main">
        {fresh && !introDone ? <NoviIntro name={firstName} onComplete={() => setIntroDone(true)} /> : null}
        <header className="chat-head">
          <NoviOrb speaking={speaking} active={voiceOn} />
          <div className="chat-head-info">
            <div className="chat-head-name">Get to know you</div>
            <div className="chat-head-status">
              <span className="chat-dot" aria-hidden="true" />
              {speaking ? "Novi is speaking" : cur?.section || "Novi is listening"}
            </div>
          </div>
          <div className="chat-head-actions">
            <button
              type="button"
              className={`chat-head-btn${voiceOn ? " on" : ""}`}
              onClick={toggleVoice}
              title={voiceOn ? "Turn voice off" : "Turn voice on"}
              aria-pressed={voiceOn}
            >
              {voiceOn ? <Volume2 size={15} /> : <VolumeX size={15} />}
              Voice
            </button>
          </div>
          <div className="ob-progress-wrap" aria-label={`${percent}% complete`}>
            <div className="ob-progress-track">
              <div className="ob-progress-bar" style={{ width: `${percent}%` }} />
            </div>
            <span className="ob-progress-label">{percent}%</span>
          </div>
        </header>

        <div className="chat-log ob-log" ref={logRef} role="log" aria-live="polite">
          {fresh ? (
            <div className="chat-row novi">
              <div className="chat-avatar" aria-hidden="true">N</div>
              <div className="chat-stack">
                <div className="chat-bubble ob-greeting">{GREETING}</div>
              </div>
            </div>
          ) : null}

          {transcript.map((m, i) => {
            const mine = m.role === "user";
            return (
              <div className={`chat-row ${mine ? "user" : "novi"}`} key={`t-${i}`}>
                <div className="chat-avatar" aria-hidden="true">
                  {mine ? initials(user?.first_name || "You") : "N"}
                </div>
                <div className="chat-stack">
                  <div className={`chat-bubble${m.skipped ? " ob-skipped" : ""}`}>{m.content}</div>
                </div>
              </div>
            );
          })}

          {cur ? (
            <div className="chat-row novi">
              <div className="chat-avatar" aria-hidden="true">N</div>
              <div className="chat-stack">
                <div className="chat-bubble">{cur.question}</div>
              </div>
            </div>
          ) : null}

          {busy ? (
            <div className="chat-row novi">
              <div className="chat-avatar" aria-hidden="true">N</div>
              <div className="chat-stack">
                <div className="chat-bubble">
                  <span className="chat-typing" aria-label="Novi is thinking">
                    <i /><i /><i />
                  </span>
                </div>
              </div>
            </div>
          ) : null}
        </div>

        <div className="ob-composer">
          {isMulti ? (
            <MultiPicker
              cur={cur}
              selected={selectedSafe}
              toggle={toggleMulti}
              confirm={confirmMulti}
              busy={busy}
            />
          ) : isSingle ? (
            <SinglePicker cur={cur} pick={pickSingle} busy={busy} />
          ) : (
            <FreeComposer
              cur={cur}
              draft={draft}
              setDraft={setDraft}
              send={sendFree}
              skip={skip}
              busy={busy}
            />
          )}
        </div>
      </section>
    </div>
  );
}

function SinglePicker({ cur, pick, busy }) {
  return (
    <>
      {cur.hint && <div className="ob-hint ob-hint-top">{cur.hint}</div>}
      <div className="ob-chips">
        {cur.options.map((opt, i) => (
          <button
            type="button"
            key={i}
            className="ob-chip"
            onClick={() => pick(opt)}
            disabled={busy}
          >
            <span className="ob-chip-box" />
            <span>{opt}</span>
          </button>
        ))}
      </div>
    </>
  );
}

function MultiPicker({ cur, selected, toggle, confirm, busy }) {
  return (
    <>
      <div className="ob-chips">
        {cur.options.map((opt, i) => {
          const on = selected.includes(opt);
          return (
            <button
              type="button"
              key={i}
              className={`ob-chip${on ? " on" : ""}`}
              onClick={() => toggle(opt)}
              disabled={busy}
            >
              {on ? <Check size={14} /> : <span className="ob-chip-box" />}
              <span>{opt}</span>
            </button>
          );
        })}
      </div>
      <div className="ob-chips-foot">
        <span className="ob-hint">
          {cur.max_select
            ? `${selected.length}/${cur.max_select} selected`
            : `${selected.length} selected`}
        </span>
        <button
          type="button"
          className="ob-continue"
          disabled={!selected.length || busy}
          onClick={confirm}
        >
          {busy ? (
            <Loader2 size={15} className="spin" />
          ) : (
            <>
              Continue <ArrowRight size={15} />
            </>
          )}
        </button>
      </div>
    </>
  );
}

function FreeComposer({ cur, draft, setDraft, send, skip, busy }) {
  return (
    <>
      {cur.hint && !draft && <div className="ob-hint ob-hint-top">{cur.hint}</div>}
      <div className="chat-composer-inner ob-free-row">
        <textarea
          className="chat-textarea"
          rows={1}
          placeholder="Type your answer…"
          value={draft}
          onChange={(e) => {
            setDraft(e.target.value);
            const el = e.target;
            el.style.height = "auto";
            el.style.height = `${Math.min(el.scrollHeight, 130)}px`;
          }}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              send();
            }
          }}
          aria-label="Your answer"
          autoFocus
        />
        <button
          type="button"
          className="chat-send"
          onClick={send}
          disabled={!draft.trim() || busy}
          aria-label="Send answer"
          title="Send"
        >
          {busy ? <Loader2 size={16} className="spin" /> : <Send size={16} />}
        </button>
      </div>
      {cur.optional ? (
        <button type="button" className="ob-skip" onClick={skip} disabled={busy}>
          <X size={13} /> Skip this one
        </button>
      ) : null}
    </>
  );
}

function NoviOrb({ speaking, active }) {
  // A rich, chrome-like voice blob. While Novi talks it blooms large with a
  // liquid SVG goo, fast jaw-pulsing core, expanding ripples and floating
  // sparks; when silent it animates back down to a calm resting orb.
  const mode = speaking ? "talking" : active ? "on" : "";
  const label = speaking ? "Novi is speaking" : "Novi";
  return (
    <div className={`ob-orb${mode ? ` ${mode}` : ""}`} role="img" aria-label={label}>
      <span className="ob-orb-aura" aria-hidden="true" />
      <span className="ob-orb-ring" aria-hidden="true" />
      <span className="ob-orb-ring r2" aria-hidden="true" />
      <svg className="ob-orb-goo" viewBox="0 0 200 200" aria-hidden="true">
        <g transform="translate(100 100)">
          <circle className="goo-a" r="66" />
          <circle className="goo-b" r="44" />
        </g>
      </svg>
      <span className="ob-orb-core" aria-hidden="true" />
      <span className="ob-orb-ping" aria-hidden="true" />
      <img className="ob-orb-logo" src="/icon.png" alt="" aria-hidden="true" />
      <i className="ob-spark s0" aria-hidden="true" />
      <i className="ob-spark s1" aria-hidden="true" />
      <i className="ob-spark s2" aria-hidden="true" />
      <i className="ob-spark s3" aria-hidden="true" />
      <i className="ob-spark s4" aria-hidden="true" />
      <i className="ob-spark s5" aria-hidden="true" />
    </div>
  );
}

function NoviIntro({ name, onComplete }) {
  // Entry splash for brand-new students: Novi's avatar pops in, waves, and
  // greets them before the first question is revealed.
  const [leaving, setLeaving] = useState(false);
  const firstName = name && name !== "there" ? name : "";

  const finish = () => {
    if (leaving) return;
    setLeaving(true);
    setTimeout(onComplete, 550); // wait for the fade-out
  };

  useEffect(() => {
    const t = setTimeout(finish, 3600);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className={`ob-intro${leaving ? " leave" : ""}`} aria-label="Welcome to Novi">
      <span className="ob-intro-glow" aria-hidden="true" />
      <div className="ob-intro-ava">
        <span className="ob-intro-ring" aria-hidden="true" />
        <span className="ob-intro-ring r2" aria-hidden="true" />
        <span className="ob-intro-halo" aria-hidden="true" />
        <img src="/boy.png" alt="" aria-hidden="true" />
        <span className="ob-intro-wave" aria-hidden="true">👋</span>
      </div>
      <h1 className="ob-intro-title">
        Hi, I'm Novi{firstName ? `, ${firstName}` : ""}!
      </h1>
      <p className="ob-intro-sub">Let's get to know you better.</p>
      <div className="ob-intro-dots" aria-hidden="true">
        <i /><i /><i />
      </div>
      <button type="button" className="ob-intro-cta" onClick={finish}>
        Let's get started <ArrowRight size={15} />
      </button>
    </div>
  );
}

function Reveal({ flow, firstName }) {
  const s = flow.summary || {};
  const rec = s.recommendations || {};
  const plan = s.plan_30 || [];
  const name = firstName === "there" ? "" : `${firstName}, `;
  return (
    <div className="chat-shell onboard">
      <section className="chat-main ob-main">
        <div className="ob-reveal">
          <div className="ob-reveal-hero">
            <span className="ob-reveal-mark" aria-hidden="true">
              <Sparkles size={22} />
            </span>
            <h2 className="ob-reveal-title">
              Okay… I think I'm starting to get {name}you.
            </h2>
            {s.identity ? <p className="ob-reveal-sub">Your Novi profile · {s.identity}</p> : null}
          </div>

          {s.reflection ? <div className="ob-reveal-msg">{s.reflection}</div> : null}

          <div className="ob-reveal-card">
            <div className="ob-reveal-label">Your strongest traits</div>
            <div className="ob-chiprow">
              {(s.traits || []).map((t) => (
                <span className="ob-pill" key={t}>{t}</span>
              ))}
            </div>
          </div>

          {s.explore?.length ? (
            <div className="ob-reveal-card">
              <div className="ob-reveal-label">You may enjoy exploring</div>
              <div className="ob-chiprow">
                {(s.explore || []).map((t) => (
                  <span className="ob-pill ob-pill-accent" key={t}>{t}</span>
                ))}
              </div>
            </div>
          ) : null}

          {s.focus ? (
            <div className="ob-reveal-focus">
              <span className="ob-reveal-label">Your current focus</span>
              <span className="ob-focus">{s.focus}</span>
            </div>
          ) : null}

          {rec.careers?.length ? (
            <div className="ob-reveal-card">
              <div className="ob-reveal-label">Careers worth a look</div>
              <div className="ob-recs">
                {rec.careers.map((c) => (
                  <div className="ob-rec" key={c}>
                    <ArrowRight size={14} />
                    {c}
                  </div>
                ))}
              </div>
            </div>
          ) : null}

          {rec.experiences?.length ? (
            <div className="ob-reveal-card">
              <div className="ob-reveal-label">Things to try next</div>
              <div className="ob-recs">
                {rec.experiences.map((c) => (
                  <div className="ob-rec ob-rec-soft" key={c}>
                    <Sparkles size={13} />
                    {c}
                  </div>
                ))}
              </div>
            </div>
          ) : null}

          {plan.length ? (
            <div className="ob-reveal-card">
              <div className="ob-reveal-label">Your first 30 days</div>
              <ol className="ob-plan">
                {plan.map((step, i) => (
                  <li key={i}>{step}</li>
                ))}
              </ol>
            </div>
          ) : null}

          <div className="ob-reveal-cta">
            <Link href="/dashboard" className="ob-btn ob-btn-primary">
              Continue to your dashboard <ArrowRight size={16} />
            </Link>
            <Link href="/chat" className="ob-btn">
              Chat with Novi
            </Link>
            <a href={WELCOME_PATH} className="ob-btn">
              See what you can build <Sparkles size={14} />
            </a>
          </div>
        </div>
      </section>
    </div>
  );
}