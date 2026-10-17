"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "../../api";
import { useAuth } from "../../auth";
import { destinationFor, passwordError } from "../../authFlow";

export default function AddChild() {
  const { user, patchUser, refreshUser } = useAuth();
  const router = useRouter();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [created, setCreated] = useState(null);

  const submit = async (event) => {
    event.preventDefault();
    if (busy) return;
    setError("");
    const validation = passwordError(password);
    if (validation) { setError(validation); return; }
    if (!name.trim()) { setError("Enter your child's name."); return; }
    if (email.trim().toLowerCase() === user.email.toLowerCase()) { setError("Use a different email from your parent account."); return; }
    setBusy(true);
    const body = JSON.stringify({ name: name.trim(), email: email.trim(), password });
    // Keep the credential only in this request, never in saved identity/state.
    setPassword("");
    setCreated(null);
    try {
      const receipt = await api("/parent/students", { method: "POST", body });
      setCreated({ name: receipt.name });
      setName("");
      setEmail("");
      // A committed active link proves setup is complete even if identity
      // refresh is temporarily unavailable. Never replace the parent's JWT.
      patchUser({ ...user, needs_child_setup: false });
      await refreshUser({ fresh: true });
    } catch (ex) {
      setError(ex.status === 409 ? "That email already has an account. Use a different email; the existing account has not been changed." : ex.message);
    } finally {
      setPassword("");
      setBusy(false);
    }
  };

  const continueHome = async () => {
    const me = await refreshUser({ fresh: true });
    const next = new URLSearchParams(window.location.search).get("next");
    router.push(destinationFor(me || user, next));
  };

  return (
    <div className="dash-wrap pd-wrap" style={{ maxWidth: 720, margin: "0 auto" }}>
      <div className="dash-top"><div className="dash-intro">
        <div className="dash-kick">Parent space</div>
        <h1 className="dash-hi">Add child</h1>
        <p className="dash-sub">Create your child’s student account. You can add another child here at any time.</p>
      </div></div>
      <div className="card">
        <p className="small muted">Give your child the email and temporary password yourself. We do not send or display their password. They will set their own password when they first sign in.</p>
        <p className="small muted">Basic progress is connected immediately. Your child controls additional sharing; their conversations with Novi stay private.</p>
        {created ? <div className="notice-banner mt" role="status">
          <b>{created.name}’s account is ready.</b> Give them the email and temporary password you chose. You can add another child below.
          <div className="mt"><button type="button" className="btn" onClick={continueHome}>Continue</button></div>
        </div> : null}
        {error ? <div className="error-banner mt" role="alert">{error}</div> : null}
        <form onSubmit={submit} className="mt" autoComplete="off">
          <fieldset disabled={busy} style={{ border: 0, padding: 0, margin: 0 }}>
            <div className="field"><label htmlFor="child-name">Child’s name</label><input id="child-name" name="child-name" required maxLength={100} autoComplete="off" value={name} onChange={(event) => setName(event.target.value)} /></div>
            <div className="field"><label htmlFor="child-email">Child’s email</label><input id="child-email" name="child-email" type="email" required autoComplete="off" value={email} onChange={(event) => setEmail(event.target.value)} /></div>
            <div className="field"><label htmlFor="child-password">Temporary password</label><input id="child-password" name="child-password" type="password" required minLength={8} maxLength={72} autoComplete="new-password" value={password} onChange={(event) => setPassword(event.target.value)} /></div>
            <p className="small muted">Use at least 8 characters and at most 72 bytes. Choose a different password from your own.</p>
            <button className="btn" type="submit">{busy ? "Creating account…" : "Create child account"}</button>
          </fieldset>
        </form>
      </div>
    </div>
  );
}
