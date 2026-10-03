import { useEffect, useState } from "react";
import { Sparkles, Zap, BookOpen, Target, Compass, Heart } from "lucide-react";
import { api, esc } from "../api";
import { EmptyState, Kicker, Pill, showLoader, toast } from "../ui";

const FIELDS = [
  ["interests", "Interests", "robotics, AI, music…"],
  ["subjects", "Subjects you enjoy", "maths, computer science…"],
  ["strengths", "Strengths", "coding, teamwork…"],
  ["development_areas", "Want to grow in", "public speaking…"],
  ["goals", "Career goals", "build an AI company"],
  ["values", "Values", "creativity, impact…"],
];

const MAP_GRID = [
  ["interests", "Interests"], ["strengths", "Strengths"], ["subjects", "Subjects"],
  ["goals", "Goals"], ["career_zones", "Career zones"], ["values", "Values"],
];

/* Order the frozen snapshot payload the same way the profile shows DNA, so a
   snapshot reads like a little time capsule rather than a raw JSON dump. */
const SNAP_FIELDS = [
  ["interests", "Interests"], ["strengths", "Strengths"], ["traits", "Traits"],
  ["subjects", "Subjects"], ["skills", "Skills"], ["motivations", "Motivations"],
  ["development_areas", "Want to grow in"], ["career_zones", "Career zones"],
  ["values", "Values"], ["goals", "Goals"],
];

const DNA_ICONS = {
  interests: Sparkles,
  strengths: Zap,
  subjects: BookOpen,
  goals: Target,
  career_zones: Compass,
  values: Heart,
};

export default function DnaPage() {
  const [refreshing, setRefreshing] = useState(false);
  const [refreshMessage, setRefreshMessage] = useState("");
  const [dna, setDna] = useState(null);
  const [inputs, setInputs] = useState({});
  const [error, setError] = useState(null);
  const [snaps, setSnaps] = useState([]);
  const [snapLabel, setSnapLabel] = useState("");
  const [snapNote, setSnapNote] = useState("");
  const [editingSnap, setEditingSnap] = useState(null);   // id of row in edit mode
  const [snapBusy, setSnapBusy] = useState(false);

  const load = () => api("/dna");

  useEffect(() => {
    let alive = true;
    showLoader(true);
    load()
      .then((d) => {
        if (!alive) return;
        setDna(d);
        const init = {};
        FIELDS.forEach(([k]) => { init[k] = (d[k] || []).join(", "); });
        setInputs(init);
      })
      .catch((ex) => { if (alive) setError(ex.message); })
      .finally(() => showLoader(false));
    return () => { alive = false; };
  }, []);


  const loadSnapshots = async () => {
    try { setSnaps(await api("/dna/snapshots")); }
    catch (ex) { toast(ex.message); }
  };

  useEffect(() => { loadSnapshots(); }, []);

  const saveSnapshot = async () => {
    setSnapBusy(true);
    try {
      const created = await api("/dna/snapshots", { method: "POST", body: JSON.stringify({ label: snapLabel || "My DNA · today", note: snapNote }) });
      setSnaps(created); setSnapLabel(""); setSnapNote("");
      toast("Snapshot saved — this is you, right now ⚙️");
    } catch (ex) { toast(ex.message); }
    finally { setSnapBusy(false); }
  };

  const updateSnapshot = async (id, patch) => {
    try {
      setSnaps(await api(`/dna/snapshots/${id}`, { method: "PATCH", body: JSON.stringify(patch) }));
      setEditingSnap(null); toast("Snapshot updated");
    } catch (ex) { toast(ex.message); }
  };

  const deleteSnapshot = async (id) => {
    if (!window.confirm("Delete this snapshot forever? Older snapshots are only useful while they mean something to you.")) return;
    try { await api(`/dna/snapshots/${id}`, { method: "DELETE" }); setSnaps((s) => s.filter((x) => x.id !== id)); toast("Snapshot deleted"); }
    catch (ex) { toast(ex.message); }
  };

  const beginEdit = (s) => { setEditingSnap({ id: s.id, label: s.label || "", note: s.note || "" }); };

  if (error) return <EmptyState title="DNA unavailable" sub={error} />;
  if (!dna) return null;

  const after = async (next) => {
    const d = await load();
    setDna(d);
    const init = {};
    FIELDS.forEach(([k]) => { init[k] = (d[k] || []).join(", "); });
    setInputs(init);
    next();
  };

  const saveDna = async () => {
    const payload = {};
    FIELDS.forEach(([k]) => { payload[k] = (inputs[k] || "").split(",").map((s) => s.trim()).filter(Boolean); });
    showLoader(true);
    try { await api("/dna", { method: "PATCH", body: JSON.stringify(payload) }); toast("DNA updated ✨"); await after(() => {}); }
    catch (ex) { toast(ex.message); }
    finally { showLoader(false); }
  };

  const refreshDna = async () => {
    setRefreshing(true);
    setRefreshMessage("Reading your latest chats and updating DNA…");
    try {
      const updated = await api("/dna/refresh", { method: "POST" });
      setDna(updated);
      setInputs(Object.fromEntries(FIELDS.map(([k]) => [k, (updated[k] || []).join(", ")])));
      setRefreshMessage("DNA updated from your latest chats.");
    } catch (ex) { setRefreshMessage(ex.message); }
    finally { setRefreshing(false); }
  };

  const reflect = async (accepted, feedback) => {
    showLoader(true);
    try { await api("/dna/reflect", { method: "POST", body: JSON.stringify(accepted ? { accepted: true } : { accepted: false, feedback }) }); await after(() => {}); }
    catch (ex) { toast(ex.message); }
    finally { showLoader(false); }
  };

  const reflNo = async () => {
    const feedback = window.prompt("What feels off? Tell Novi what's more true for you:", "");
    if (feedback === null) return;
    await reflect(false, feedback);
    toast("Got it — Novi will keep learning 🧬");
  };

  const field = (k, label, ph) => (
    <div className="field">
      <label>{label}</label>
      <input value={inputs[k] || ""} placeholder={ph} onChange={(e) => setInputs((m) => ({ ...m, [k]: e.target.value }))} />
    </div>
  );

  return (
    <>
      <div className="hero"><Kicker>Your living map</Kicker><h1>My Career DNA</h1><p>The map Novi builds about who you are. Update it, or let Novi refresh it from your chats.</p></div>
      <div className="card novi-box mb">
        <h3 className="mb">Novi's reflection</h3>
        <span className="novi-avatar">N</span><span>{dna.novi_reflection ? esc(dna.novi_reflection) : "Your reflection fills here after you chat about your interests."}</span>
        <div className="row mt">
          <button className="btn" id="refl-yes" onClick={() => { reflect(true, null); toast("That makes me happy to hear 🎉"); }}>Yes, that's me ✓</button>
          <button className="btn-ghost" id="refl-no" onClick={reflNo}>Not quite</button>
        </div>
      </div>
      {dna.dna_filled ? <Pill label="DNA ready" tone="good" /> : <span className="pill">Not yet finalised</span>}
      <div className="section-title">Edit DNA</div>
      <div className="card">
        {FIELDS.map(([k, l, ph]) => field(k, l, ph))}
        <div className="row">
          <button className="btn" id="save-dna" onClick={saveDna}>Save DNA</button>
          <button className="btn-ghost" id="refresh-dna" disabled={refreshing} onClick={refreshDna}>{refreshing ? "Refreshing…" : "Refresh from chats"}</button>
          {!dna.dna_filled ? <button className="btn-ghost" id="finalize-dna" onClick={() => { reflect(true, null); toast("DNA finalised — you're ready to match 🎯"); }}>Finalize DNA ✓</button> : <span className="chip acc">DNA locked · ready for matching</span>}
        </div>
      </div>
      {refreshMessage && <p role="status">{refreshMessage}</p>}
      <div className="section-title">Currently mapped</div>
      <div className="cols dna-map">
        {MAP_GRID.map(([k, l]) => {
          const Icon = DNA_ICONS[k] || Sparkles;
          const tags = dna[k] || [];
          return (
            <div className={`card dna-card ic-${k}`} key={k}>
              <h3><span className="dna-ico"><Icon size={18} strokeWidth={1.9} /></span>{l}<span className="dna-count">{tags.length}</span></h3>
              <div className="dna-tag-row">
                {tags.length ? tags.map((t) => <span className="chip" key={t}>{esc(t)}</span>) : <span className="muted small">Not set yet</span>}
              </div>
              {tags.length ? <div className="dna-strand" /> : null}
            </div>
          );
        })}
      </div>
      <div className="section-title">Snapshots · your DNA over the years</div>
      <div className="card mb">
        <p className="muted small mb">Progress is gradual — it unfolds across many years. Keep a snapshot for each big step: save it, come back and edit the label/note in later years, and delete the ones that no longer matter.</p>
        {!dna.dna_filled ? null : (
          <div className="row mb">
            <input value={snapLabel} onChange={(e) => setSnapLabel(e.target.value)} placeholder="Label, e.g. “My DNA at 14”" />
            <input value={snapNote} onChange={(e) => setSnapNote(e.target.value)} placeholder="A note to future you (optional)" />
            <button className="btn" onClick={saveSnapshot} disabled={snapBusy}>Save snapshot ⚔</button>
          </div>
        )}
        {snaps.length === 0 ? (
          <EmptyState title="No snapshots yet" sub="Once your DNA is ready, save one to begin your timeline." />
        ) : (
          snaps.map((s) => (
            <div className="snap-card" key={s.id}>
              <div className="row between">
                <strong>{esc(s.label || "My DNA")}</strong>
                <span className="chip">{s.created_at ? new Date(s.created_at).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" }) : "now"}</span>
              </div>
              {s.note ? <p className="muted">{esc(s.note)}</p> : null}
              {s.delta && Object.values(s.delta).some((v) => v && v.length) ? (
                <div className="dna-tag-row mt">
                  {Object.entries(s.delta).flatMap(([k, v]) => v && v.length ? v.map((item) => (
                    <span className={"chip " + (k.endsWith("_added") ? "ac" : "warn")} key={k + item}>{esc(item)} {k.endsWith("_added") ? "↑" : "↓"}</span>
                  )) : [])}
                </div>
              ) : null}
              {editingSnap && editingSnap.id === s.id ? (
                /* --- inline edit: change label/note years later --- */
                <div className="snap-edit mt">
                  <input
                    value={editingSnap.label}
                    maxLength={160}
                    placeholder="Label, e.g. “My DNA at 14”"
                    onChange={(e) => setEditingSnap({ ...editingSnap, label: e.target.value })}
                  />
                  <input
                    value={editingSnap.note}
                    maxLength={2000}
                    placeholder="A note to future you (optional)"
                    onChange={(e) => setEditingSnap({ ...editingSnap, note: e.target.value })}
                  />
                  <div className="row">
                    <button
                      className="btn"
                      onClick={() => updateSnapshot(s.id, { label: editingSnap.label, note: editingSnap.note })}
                    >
                      Save
                    </button>
                    <button className="btn-ghost" onClick={() => setEditingSnap(null)}>Cancel</button>
                  </div>
                </div>
              ) : (
                <div className="row between mt">
                  <button className="btn-ghost" onClick={() => beginEdit(s)}>✎ Edit label / note</button>
                  <button className="btn-ghost snap-del" onClick={() => deleteSnapshot(s.id)}>Delete</button>
                </div>
              )}
              {/* what was frozen at this point in time */}
              <details className="snap-detail">
                <summary>What this snapshot captured</summary>
                {SNAP_FIELDS.map(([k, label]) => (
                  (s[k] || []).length ? (
                    <div className="snap-detail-row" key={k}>
                      <span className="snap-detail-label">{esc(label)}</span>
                      <span className="snap-detail-vals">
                        {(s[k] || []).map((v, i) => <span className="chip" key={i}>{esc(String(v))}</span>)}
                      </span>
                    </div>
                  ) : null
                ))}
              </details>
            </div>
          ))
        )}
      </div>
    </>
  );
}
