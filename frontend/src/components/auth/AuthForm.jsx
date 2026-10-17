"use client";

import { useState } from "react";
import Link from "next/link";

export default function AuthForm({ form, mode }) {
  const [visible, setVisible] = useState(false);
  const isLogin = mode === "login";
  const fieldClass = "space-y-1.5";
  const inputClass = "w-full rounded-xl border border-border-soft bg-background/40 px-4 py-3 text-sm";
  const buttonClass = "w-full rounded-xl bg-primary px-6 py-3 text-sm font-bold text-primary-foreground disabled:opacity-60";
  return (
    <>
      <h2 className="font-display text-2xl font-bold">{isLogin ? "Welcome back" : "Create your parent account"}</h2>
      <p className="mt-2 text-sm text-muted">
        {isLogin ? "Parents and students can sign in below." : "Sign up first, then create an account for each child."}
      </p>
      {isLogin ? (
        <div className="flex gap-2" style={{ margin: "18px 0" }} aria-label="Log in as">
          {["parent", "student"].map((role) => (
            <button type="button" key={role} disabled={form.busy} aria-pressed={form.role === role} onClick={() => form.chooseRole(role)} className={`rounded-xl border px-5 py-2 text-sm ${form.role === role ? "border-primary bg-primary/15" : "border-border-soft"}`}>
              {role === "parent" ? "Parent" : "Student"}
            </button>
          ))}
        </div>
      ) : null}
      <button type="button" disabled={form.busy} onClick={form.handleGoogle} className="mt-4 w-full rounded-xl border border-border-soft px-6 py-3 text-sm font-bold" style={{ width: "100%" }}>
        Continue with Google
      </button>
      <form onSubmit={form.handleSubmit} className="mt-5 space-y-4">
        <fieldset disabled={form.busy} style={{ border: 0, padding: 0, margin: 0 }} className="space-y-4">
          {!isLogin ? <div className={fieldClass}>
            <label htmlFor="auth-name">Your name</label>
            <input id="auth-name" name="name" autoComplete="name" required maxLength={100} value={form.name} onChange={(e) => form.setName(e.target.value)} className={inputClass} />
          </div> : null}
          <div className={fieldClass}>
            <label htmlFor="auth-email">Email</label>
            <input id="auth-email" name="email" type="email" autoComplete="email" required value={form.email} onChange={(e) => form.setEmail(e.target.value)} className={inputClass} />
          </div>
          <div className={fieldClass}>
            <label htmlFor="auth-password">Password</label>
            <input id="auth-password" name="password" type={visible ? "text" : "password"} autoComplete={isLogin ? "current-password" : "new-password"} required minLength={isLogin ? undefined : 8} maxLength={72} value={form.password} onChange={(e) => form.setPassword(e.target.value)} className={inputClass} />
            <button type="button" onClick={() => setVisible(!visible)} className="text-xs text-muted underline">{visible ? "Hide password" : "Show password"}</button>
          </div>
          {!isLogin ? <p className="text-xs text-muted">Use at least 8 characters and at most 72 bytes.</p> : null}
          {form.error ? <div role="alert" className="rounded-xl border border-red-500/30 p-3 text-sm text-red-500">
            {form.error}
            {form.mismatch ? <button type="button" onClick={() => form.chooseRole(form.mismatch)} className="underline">Try {form.mismatch} login</button> : null}
          </div> : null}
          <button type="submit" className={buttonClass} style={{ width: "100%", marginTop: 12 }}>
            {form.busy ? "Please wait…" : isLogin ? "Log in" : "Create parent account"}
          </button>
        </fieldset>
      </form>
      <p className="mt-5 text-sm text-muted">
        {isLogin ? <>New here? <Link href={form.otherHref}>Create a parent account</Link>. Students use the account their parent created.</> : <>Already have an account? <Link href={form.otherHref}>Log in</Link>.</>}
      </p>
    </>
  );
}
