"use client";

import PasswordChangeForm from "../../components/auth/PasswordChangeForm";
import { useAuth } from "../../auth";

export default function ParentSettings() {
  const { user } = useAuth();
  return <div className="dash-wrap" style={{ maxWidth: 720, margin: "0 auto" }}>
    <h1>Parent settings</h1>
    <p className="muted">{user.email}</p>
    <section className="card"><h2>Change password</h2>
      <p className="small muted">Manage how you sign in to your parent account.</p>
      <PasswordChangeForm />
    </section>
  </div>;
}
