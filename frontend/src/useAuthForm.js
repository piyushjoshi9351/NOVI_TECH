"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "./api";
import { useAuth } from "./auth";
import { destinationFor, googleDestination, passwordError, safeNext, withNext } from "./authFlow";

export function useAuthForm(mode) {
  const { login, ready, token, user } = useAuth();
  const router = useRouter();
  const [checked, setChecked] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [role, setRole] = useState("parent");
  const [mismatch, setMismatch] = useState(null);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const nextRef = useRef("");
  const initialized = useRef(false);

  useEffect(() => {
    if (!ready || initialized.current) return;
    initialized.current = true;
    const params = new URLSearchParams(window.location.search);
    nextRef.current = safeNext(params.get("next"));
    if (mode === "login" && params.get("as") === "student") setRole("student");
    if (mode === "login" && params.get("mode") === "register") {
      router.replace(withNext("/signup", nextRef.current));
      return;
    }
    const googleToken = params.get("google_token");
    if (googleToken || params.has("google_error")) {
      try {
        nextRef.current = nextRef.current || safeNext(sessionStorage.getItem("novi_auth_next"));
        sessionStorage.removeItem("novi_auth_next");
      } catch (_) { /* Storage is optional; credentials are never stored here. */ }
    }
    if (googleToken) {
      params.delete("google_token");
      params.delete("google_new");
      window.history.replaceState({}, "", window.location.pathname + (params.size ? `?${params}` : ""));
      googleDestination(googleToken, login, nextRef.current)
        .then((destination) => router.replace(destination))
        .catch(() => { setError("Google sign-in failed. Please try again."); setChecked(true); });
      return;
    }
    if (params.get("google_error")) setError("Google sign-in failed. Students need an account created by their parent.");
    if (token && user) router.replace(destinationFor(user, nextRef.current));
    else setChecked(true);
  }, [ready, token, user, mode, login, router]);

  const handleSubmit = async (event) => {
    event.preventDefault();
    if (busy) return;
    setError("");
    setMismatch(null);
    const validation = passwordError(password, mode === "login");
    if (validation) { setError(validation); return; }
    if (mode === "register" && !name.trim()) { setError("Enter your name."); return; }
    setBusy(true);
    try {
      const isLogin = mode === "login";
      const result = await api(isLogin ? "/auth/login" : "/auth/parent/register", {
        method: "POST",
        body: JSON.stringify(isLogin
          ? { email: email.trim(), password, expected_role: role }
          : { name: name.trim(), email: email.trim(), password }),
      });
      const me = await login(result.access_token, result.user);
      router.replace(destinationFor(me, nextRef.current));
    } catch (ex) {
      setError(ex.message || "Unable to sign in. Please try again.");
      if (mode === "login" && ex.status === 403 && ex.message?.startsWith("This account is a ")) setMismatch(role === "parent" ? "student" : "parent");
    } finally {
      setPassword("");
      setBusy(false);
    }
  };

  const handleGoogle = () => {
    setPassword("");
    try {
      if (nextRef.current) sessionStorage.setItem("novi_auth_next", nextRef.current);
      else sessionStorage.removeItem("novi_auth_next");
    } catch (_) { /* Returning to role home is safe when storage is unavailable. */ }
    const params = new URLSearchParams({ next: mode === "login" ? "/login" : "/signup", intent: mode === "register" ? "parent" : role });
    window.location.assign(`/api/auth/google?${params}`);
  };

  const chooseRole = (value) => { setRole(value); setError(""); setMismatch(null); };
  const otherHref = withNext(mode === "login" ? "/signup" : "/login", nextRef.current);
  return { checked, busy, error, role: mode === "register" ? "parent" : role, mismatch, name, email, password, setName, setEmail, setPassword, chooseRole, handleSubmit, handleGoogle, otherHref };
}
