"use client";
import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import { api, clearApiCache, setApiToken, setApiIdentity, SESSION_EXPIRED, resetWarmAll, revokeImageUrls, refreshDnaContext } from "./api";

const AuthCtx = createContext(null);

export function AuthProvider({ children }) {
  const [token, setToken] = useState(null);
  const [user, setUser] = useState(null);
  const [ready, setReady] = useState(false);
  const session = useRef(0);

  const clearSession = useCallback(() => {
    session.current++;
    localStorage.removeItem("novi_token");
    localStorage.removeItem("novi_user");
    setApiToken(null);
    setToken(null);
    setUser(null);
    resetWarmAll();
    clearApiCache();
    revokeImageUrls();
    refreshDnaContext();
    setReady(true);
  }, []);

  // The token response carries a role, but /auth/me is the authority (the role
  // lives in the database and can never be chosen by a client). We set state
  // immediately so nothing flashes, then reconcile against /auth/me and return
  // the authoritative user — callers can await login() to route on the REAL
  // role rather than on whichever tab the person picked.
  const login = useCallback(async (tk, u = null, { keepReady = false } = {}) => {
    if (!tk) throw new Error("The server did not return a session.");
    const current = ++session.current;
    if (!keepReady) setReady(false);
    localStorage.setItem("novi_token", tk);
    if (u) localStorage.setItem("novi_user", JSON.stringify(u));
    else localStorage.removeItem("novi_user");
    setApiToken(tk);
    setApiIdentity(u);
    setToken(tk);
    setUser(u);
    resetWarmAll();
    clearApiCache();
    revokeImageUrls();
    refreshDnaContext();
    try {
      const me = await api("/auth/me", { fresh: true });
      if (current !== session.current) throw new Error("Session changed. Please sign in again.");
      if (me) {
        setApiIdentity(me);
        localStorage.setItem("novi_user", JSON.stringify(me));
        setUser(me);
      }
      return me || u || null;
    } catch (ex) {
      if (current !== session.current) throw ex;
      if (ex.status === 401 || !u) { clearSession(); throw ex; }
      return u;
    } finally {
      if (current === session.current) setReady(true);
    }
  }, [clearSession]);

  const logout = useCallback(() => {
    clearSession();
    if (typeof window !== "undefined") window.location.href = "/login";
  }, [clearSession]);

  const patchUser = useCallback((u) => {
    setApiIdentity(u);
    localStorage.setItem("novi_user", JSON.stringify(u));
    setUser(u);
  }, []);

  const refreshUser = useCallback(async (opts = {}) => {
    const current = session.current;
    try {
      // opts.fresh is required right after a write, otherwise the 15s GET
      // cache can hand back the pre-write profile.
      const me = await api("/auth/me", opts);
      if (current !== session.current) return null;
      if (me) {
        setApiIdentity(me);
        localStorage.setItem("novi_user", JSON.stringify(me));
        setUser(me);
      }
      return me;
    } catch (_) {
      return null;
    }
  }, []);

  useEffect(() => {
    window.addEventListener(SESSION_EXPIRED, clearSession);
    return () => window.removeEventListener(SESSION_EXPIRED, clearSession);
  }, [clearSession]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    // The callback owns this new session; do not race it with an old token.
    if (new URLSearchParams(window.location.search).has("google_token")) { setReady(true); return; }
    const current = ++session.current;
    const tk = window.localStorage.getItem("novi_token");
    let u = null;
    try { u = JSON.parse(window.localStorage.getItem("novi_user") || "null"); } catch (_) {}
    if (!tk) { setReady(true); return; }
    setApiToken(tk);
    // Cached identity is not enough to authorize background reads.
    setApiIdentity(null);
    setToken(tk);
    setUser(u);
    api("/auth/me", { fresh: true })
      .then((me) => {
        if (current !== session.current) return;
        setApiIdentity(me);
        window.localStorage.setItem("novi_user", JSON.stringify(me));
        setUser(me);
      })
      .catch(() => { if (current === session.current) clearSession(); })
      .finally(() => { if (current === session.current) setReady(true); });
    return () => { if (current === session.current) session.current++; };
  }, [clearSession]);

  const value = { token, user, role: user?.role || null, ready, login, logout, patchUser, refreshUser };
  return <AuthCtx.Provider value={value}>{children}</AuthCtx.Provider>;
}

export function useAuth() { return useContext(AuthCtx); }
