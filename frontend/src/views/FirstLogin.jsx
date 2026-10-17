"use client";

import PasswordChangeForm from "../components/auth/PasswordChangeForm";
import { useAuth } from "../auth";

export default function FirstLogin() {
  const { logout } = useAuth();
  return (
    <div className="auth-wrap"><div className="card" style={{ width: "100%", maxWidth: 520, margin: "auto" }}>
      <h1>Set your own password</h1>
      <p>Your parent created your account with a temporary password. Choose a password only you know before starting your journey.</p>
      <PasswordChangeForm firstLogin />
      <button type="button" className="btn ghost mt" onClick={logout}>Log out</button>
    </div></div>
  );
}
