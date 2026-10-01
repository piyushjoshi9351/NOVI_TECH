import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ArrowDown, Check, Copy, PanelLeft, Plus, Search, Send, Square } from "lucide-react";
import { api, initials, streamChat } from "../api";
import { useAuth } from "../auth";
import { EmptyState, showLoader, toast } from "../ui";
import Markdown from "./chat/Markdown";

function fmtAgo(iso) {
  if (!iso) return "";
  const then = new Date(iso).getTime();
  if (isNaN(then)) return String(iso).slice(0, 10);
  const diff = Date.now() - then;
  if (diff < 6e4) return "just now";
  if (diff < 36e5) return `${Math.floor(diff / 6e4)}m`;
  if (diff < 864e5) return `${Math.floor(diff / 36e5)}h`;
  if (diff < 864e5 * 7) return `${Math.floor(diff / 864e5)}d`;
  return String(iso).slice(0, 10);
}

function msgTime(value) {
  if (!value) return "";
  const d = new Date(value);
  return isNaN(d) ? "" : d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function dayBucket(iso) {
  if (!iso) return "Earlier";
  const d = new Date(iso);
  if (isNaN(d)) return "Earlier";
  const now = new Date();
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const startOfDay = new Date(d.getFullYear(), d.getMonth(), d.getDate());
  const days = Math.round((startOfToday - startOfDay) / 864e5);
  if (days <= 0) return "Today";
  if (days === 1) return "Yesterday";
  if (days < 7) return "This week";
  return "Earlier";
}

const SUGGESTIONS = [
  { icon: "🧭", title: "Find my direction", prompt: "What career fits my strengths?" },
  { icon: "📚", title: "What to focus on", prompt: "Which subjects should I focus on this term?" },
  { icon: "🗓️", title: "Plan my month", prompt: "What should I be doing this month?" },
  { icon: "🎓", title: "University fit", prompt: "Show me universities that fit me." },
  { icon: "🏆", title: "Build my profile", prompt: "Help me build a strong profile for my goals." },
];

export default function ChatPage() {
  const { user } = useAuth();
  const [convos, setConvos] = useState([]);
  const [activeId, setActiveId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [draft, setDraft] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [streamText, setStreamText] = useState("");
  const [query, setQuery] = useState("");
  const [loadError, setLoadError] = useState(null);
  const [showJump, setShowJump] = useState(false);
  const [railOpen, setRailOpen] = useState(false);
  const [copiedId, setCopiedId] = useState(null);

  const logRef = useRef(null);
  const taRef = useRef(null);
  const abortRef = useRef(null);
  const streamRef = useRef("");
  const nearBottomRef = useRef(true);

  const userName = user?.first_name || user?.name || "You";
  const firstName = String(user?.first_name || user?.name || "there").split(" ")[0];

  const refreshConvos = useCallback(async () => {
    try {
      setConvos(await api("/chat/conversations", { fresh: true }));
    } catch (_) {
      /* best-effort refresh */
    }
  }, []);

  const openConversation = useCallback(async (id) => {
    abortRef.current?.abort();
    setActiveId(id);
    setRailOpen(false);
    nearBottomRef.current = true;
    try {
      setMessages(await api(`/chat/conversations/${id}/messages`));
    } catch (ex) {
      setMessages([]);
      toast(ex.message, "err");
    }
  }, []);

  useEffect(() => {
    let alive = true;
    showLoader(true);
    api("/chat/conversations")
      .then((list) => {
        if (!alive) return;
        setConvos(list);
        if (list.length) {
          setActiveId(list[0].id);
          return api(`/chat/conversations/${list[0].id}/messages`);
        }
      })
      .then((msgs) => {
        if (alive && msgs) setMessages(msgs);
      })
      .catch((ex) => {
        if (alive) setLoadError(ex.message);
      })
      .finally(() => showLoader(false));
    return () => {
      alive = false;
      abortRef.current?.abort();
    };
  }, []);

  useEffect(() => {
    if (!nearBottomRef.current) return;
    const el = logRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages, streamText]);

  const onLogScroll = () => {
    const el = logRef.current;
    if (!el) return;
    const near = el.scrollHeight - el.scrollTop - el.clientHeight < 140;
    nearBottomRef.current = near;
    setShowJump(!near);
  };

  const scrollToBottom = () => {
    const el = logRef.current;
    if (el) el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
    nearBottomRef.current = true;
    setShowJump(false);
  };

  const resizeTextarea = () => {
    const el = taRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 168)}px`;
  };

  const appendAssistant = useCallback((content, extra = {}) => {
    setMessages((prev) => [
      ...prev,
      {
        id: `local-${Date.now()}-${prev.length}`,
        role: "assistant",
        content,
        created_at: new Date().toISOString(),
        ...extra,
      },
    ]);
  }, []);

  const send = useCallback(
    async (raw) => {
      const value = (raw ?? draft).trim();
      if (!value || streaming) return;

      setDraft("");
      requestAnimationFrame(resizeTextarea);
      setMessages((prev) => [
        ...prev,
        { id: `local-${Date.now()}`, role: "user", content: value, created_at: new Date().toISOString() },
      ]);
      setStreaming(true);
      setStreamText("");
      streamRef.current = "";
      nearBottomRef.current = true;

      const controller = new AbortController();
      abortRef.current = controller;
      try {
        await streamChat({
          message: value,
          conversation_id: activeId,
          signal: controller.signal,
          onEvent: (event) => {
            if (event.type === "meta") {
              if (event.conversation_id != null) setActiveId(event.conversation_id);
            } else if (event.type === "delta") {
              streamRef.current += event.text || "";
              setStreamText(streamRef.current);
            }
          },
        });
        if (streamRef.current.trim()) appendAssistant(streamRef.current);
        refreshConvos();
      } catch (ex) {
        if (ex.name === "AbortError") {
          if (streamRef.current.trim()) appendAssistant(streamRef.current, { stopped: true });
        } else {
          appendAssistant(`⚠️ ${ex.message}`, { isError: true });
          toast(ex.message, "err");
        }
      } finally {
        setStreaming(false);
        setStreamText("");
        streamRef.current = "";
        abortRef.current = null;
        requestAnimationFrame(() => taRef.current?.focus());
      }
    },
    [draft, activeId, streaming, appendAssistant, refreshConvos],
  );

  const stop = () => abortRef.current?.abort();

  const newChat = () => {
    abortRef.current?.abort();
    setActiveId(null);
    setMessages([]);
    setDraft("");
    setRailOpen(false);
    nearBottomRef.current = true;
    requestAnimationFrame(() => taRef.current?.focus());
  };

  const copyMessage = async (id, text) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedId(id);
      setTimeout(() => setCopiedId((c) => (c === id ? null : c)), 1600);
    } catch (_) {
      toast("Couldn't copy to clipboard", "err");
    }
  };

  const groups = useMemo(() => {
    const q = query.trim().toLowerCase();
    const list = q ? convos.filter((c) => (c.title || "").toLowerCase().includes(q)) : convos;
    const out = [];
    const buckets = new Map();
    list.forEach((c) => {
      const label = dayBucket(c.updated_at);
      if (!buckets.has(label)) {
        buckets.set(label, []);
        out.push([label, buckets.get(label)]);
      }
      buckets.get(label).push(c);
    });
    return out;
  }, [convos, query]);

  if (loadError && !messages.length) return <EmptyState title="Chat unavailable" sub={loadError} />;

  return (
    <div className="chat-shell">
      {railOpen ? <div className="chat-scrim" onClick={() => setRailOpen(false)} /> : null}

      <aside className={`chat-side${railOpen ? " open" : ""}`} aria-label="Conversations">
        <div className="chat-side-head">
          <span className="chat-eyebrow">Conversations</span>
          <button type="button" className="chat-new" onClick={newChat}>
            <Plus size={15} strokeWidth={2.6} />
            New
          </button>
        </div>

        <label className="chat-search">
          <Search size={15} aria-hidden="true" />
          <input
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search chats…"
            aria-label="Search conversations"
          />
        </label>

        <div className="chat-convs">
          {groups.length ? (
            groups.map(([label, items]) => (
              <div key={label} className="chat-group">
                <div className="chat-group-label">{label}</div>
                {items.map((c) => (
                  <button
                    type="button"
                    key={c.id}
                    className={`chat-conv${c.id === activeId ? " active" : ""}`}
                    onClick={() => openConversation(c.id)}
                  >
                    <span className="chat-conv-title">{c.title || "New chat"}</span>
                    <span className="chat-conv-sub">
                      <span className="chat-conv-snippet">{c.last_message || "No messages yet"}</span>
                      <span className="chat-conv-time">{fmtAgo(c.updated_at)}</span>
                    </span>
                  </button>
                ))}
              </div>
            ))
          ) : (
            <p className="chat-conv-empty">
              {query ? "No chats match that search." : "No conversations yet — say hi below."}
            </p>
          )}
        </div>
      </aside>

      <section className="chat-main">
        <header className="chat-head">
          <button type="button" className="chat-rail-btn" onClick={() => setRailOpen(true)} aria-label="Show conversations">
            <PanelLeft size={18} />
          </button>
          <div className="chat-avatar" aria-hidden="true">
            N
          </div>
          <div className="chat-head-info">
            <div className="chat-head-name">Novi</div>
            <div className="chat-head-status">
              <span className="chat-dot" aria-hidden="true" />
              {streaming ? "Typing…" : "Always remembers your journey"}
            </div>
          </div>
          <div className="chat-head-actions">
            <button type="button" className="chat-head-btn" onClick={newChat}>
              <Plus size={15} />
              <span>New chat</span>
            </button>
          </div>
        </header>

        <div className="chat-log" ref={logRef} onScroll={onLogScroll} role="log" aria-live="polite" aria-label="Conversation">
          {messages.length
            ? messages.map((m, i) => {
                const mine = m.role === "user";
                const time = msgTime(m.created_at || m.createdAt || m.timestamp);
                return (
                  <div className={`chat-row ${mine ? "user" : "novi"}`} key={m.id ?? `m-${i}`}>
                    <div className="chat-avatar" aria-hidden="true">
                      {mine ? initials(userName) : "N"}
                    </div>
                    <div className="chat-stack">
                      <div className={`chat-bubble${m.isError ? " is-error" : ""}`}>
                        {mine ? m.content : <Markdown text={m.content} />}
                      </div>
                      <div className="chat-bubble-foot">
                        {time ? (
                          <span className="chat-time">
                            {m.stopped ? "stopped · " : ""}
                            {time}
                          </span>
                        ) : null}
                        {!mine && !m.isError ? (
                          <button
                            type="button"
                            className="chat-copy"
                            onClick={() => copyMessage(m.id, m.content)}
                            aria-label="Copy reply"
                          >
                            {copiedId === m.id ? <Check size={13} /> : <Copy size={13} />}
                            {copiedId === m.id ? "Copied" : "Copy"}
                          </button>
                        ) : null}
                      </div>
                    </div>
                  </div>
                );
              })
            : (
              <div className="chat-welcome">
                <div className="chat-welcome-mark" aria-hidden="true">
                  N
                </div>
                <h2>Hey {firstName} 👋</h2>
                <p>
                  I'm Novi, your guide. I already know your DNA, roadmap and check-ins — so ask me anything, or start with
                  one of these.
                </p>
                <div className="chat-sugg-grid">
                  {SUGGESTIONS.map((s) => (
                    <button type="button" key={s.title} className="chat-sugg" onClick={() => send(s.prompt)}>
                      <span className="chat-sugg-ico" aria-hidden="true">
                        {s.icon}
                      </span>
                      <span className="chat-sugg-title">{s.title}</span>
                      <span className="chat-sugg-sub">{s.prompt}</span>
                    </button>
                  ))}
                </div>
              </div>
            )}

          {streaming ? (
            <div className="chat-row novi">
              <div className="chat-avatar" aria-hidden="true">
                N
              </div>
              <div className="chat-stack">
                <div className="chat-bubble">
                  {streamText ? (
                    <span className="chat-stream-text">{streamText}</span>
                  ) : (
                    <span className="chat-typing" aria-label="Novi is typing">
                      <i />
                      <i />
                      <i />
                    </span>
                  )}
                  <span className="chat-cursor" aria-hidden="true" />
                </div>
              </div>
            </div>
          ) : null}
        </div>

        {showJump ? (
          <button type="button" className="chat-jump" onClick={scrollToBottom}>
            <ArrowDown size={14} />
            New messages
          </button>
        ) : null}

        <div className="chat-composer">
          <div className="chat-composer-inner">
            <textarea
              ref={taRef}
              className="chat-textarea"
              rows={1}
              placeholder="Message Novi…"
              value={draft}
              onChange={(e) => {
                setDraft(e.target.value);
                resizeTextarea();
              }}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  send();
                }
              }}
              aria-label="Message Novi"
            />
            {streaming ? (
              <button type="button" className="chat-stop" onClick={stop} aria-label="Stop generating" title="Stop generating">
                <Square size={15} fill="currentColor" />
              </button>
            ) : (
              <button
                type="button"
                className="chat-send"
                onClick={() => send()}
                disabled={!draft.trim()}
                aria-label="Send message"
                title="Send"
              >
                <Send size={17} />
              </button>
            )}
          </div>
          <div className="chat-composer-hint">
            <span>Novi can make mistakes — double-check anything important.</span>
            <span className="chat-hint-keys">
              <kbd>Enter</kbd> to send · <kbd>Shift</kbd> + <kbd>Enter</kbd> for a new line
            </span>
          </div>
        </div>
      </section>
    </div>
  );
}
