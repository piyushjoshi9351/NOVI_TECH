"use client";

import { useState } from "react";
import { api } from "../../api";
import { useAuth } from "../../auth";
import { destinationFor, passwordError, passwordSettingsMessage } from "../../authFlow";
import { useRouter } from "next/navigation";

export default function PasswordChangeForm({ firstLogin = false }) {
  const { login, user } = useAuth();
  const router = useRouter();
  const [current, setCurrent] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);

  const submit = async (event) => {
    event.preventDefault();
    if (busy) return;
    setError("");
    setSaved(false);
    const validation = passwordError(current, true) || passwordError(password);
    if (validation) { setError(validation); return; }
    if (password === current) { setError("Choose a different password from your current password."); return; }
    if (password !== confirm) { setError("The new passwords do not match."); return; }
    const next = new URLSearchParams(window.location.search).get("next");
    setBusy(true);
    try {
      const result = await api("/auth/change-password", {
        method: "POST",
        body: JSON.stringify({ current_password: current, new_password: password }),
      });
      setCurrent(""); setPassword(""); setConfirm("");
      // The old token was invalidated. Store its replacement before /auth/me.
      const me = await login(result.access_token, result.user, { keepReady: !firstLogin });
      if (firstLogin) router.replace(destinationFor(me, next));
      else setSaved(true);
    } catch (ex) {
      setError(ex.message || "Unable to change your password.");
    } finally {
      setCurrent(""); setPassword(""); setConfirm("");
      setBusy(false);
    }
  };

  const message = passwordSettingsMessage(user);
  if (message) return <p className="small muted" role="status">{message}</p>;
  return (
    <form onSubmit={submit} className="mt">
      <fieldset disabled={busy} style={{ border: 0, padding: 0, margin: 0 }}>
        <div className="field"><label htmlFor="current-password">{firstLogin ? "Temporary password" : "Current password"}</label><input id="current-password" type="password" autoComplete="current-password" required maxLength={72} value={current} onChange={(event) => setCurrent(event.target.value)} /></div>
        <div className="field"><label htmlFor="new-password">New password</label><input id="new-password" type="password" autoComplete="new-password" required minLength={8} maxLength={72} value={password} onChange={(event) => setPassword(event.target.value)} /></div>
        <div className="field"><label htmlFor="confirm-password">Confirm new password</label><input id="confirm-password" type="password" autoComplete="new-password" required minLength={8} maxLength={72} value={confirm} onChange={(event) => setConfirm(event.target.value)} /></div>
        <p className="small muted">Use at least 8 characters and at most 72 bytes. Your new password must be different.</p>
        {error ? <div className="error-banner mt" role="alert">{error}</div> : null}
        {saved ? <p role="status">Password changed. Your earlier sessions are signed out.</p> : null}
        <button type="submit" className="btn mt">{busy ? "Saving…" : firstLogin ? "Set my password" : "Change password"}</button>
      </fieldset>
    </form>
  );
}
