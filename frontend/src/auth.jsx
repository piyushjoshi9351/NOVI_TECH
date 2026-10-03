"use client";
import { createContext, useContext, useEffect, useState } from "react";
import { api, clearApiCache, setApiToken, resetWarmAll, revokeImageUrls } from "./api";

const AuthCtx = createContext(null);

export function AuthProvider({ children }) {
  const [token, setToken] = useState(null);
  const [user, setUser] = useState(null);
  const [ready, setReady] = useState(false);

  // The token response carries a role, but /auth/me is the authority (the role
  // lives in the database and can never be chosen by a client). We set state
  // immediately so nothing flashes, then reconcile against /auth/me and return
  // the authoritative user — callers can await login() to route on the REAL
  // role rather than on whichever tab the person picked.
  const login = async (tk, u) => {
    localStorage.setItem("novi_token", tk);
    if (u) localStorage.setItem("novi_user", JSON.stringify(u));
    setApiToken(tk);
    setToken(tk);
    if (u) setUser(u);
    resetWarmAll();
    clearApiCache();
    revokeImageUrls();
    try {
      const me = await api("/auth/me");
      if (me) {
        localStorage.setItem("novi_user", JSON.stringify(me));
        setUser(me);
      }
      return me || u || null;
    } catch (_) {
      return u || null;
    }
  };

  const logout = () => {
    localStorage.removeItem("novi_token");
    localStorage.removeItem("novi_user");
    setApiToken(null);
    setToken(null);
    setUser(null);
    resetWarmAll();
    clearApiCache();
    revokeImageUrls();
    if (typeof window !== "undefined") window.location.href = "/signup";
  };

  const patchUser = (u) => {
    localStorage.setItem("novi_user", JSON.stringify(u));
    setUser(u);
  };

  const refreshUser = async (opts = {}) => {
    try {
      // opts.fresh is required right after a write, otherwise the 15s GET
      // cache can hand back the pre-write profile.
      const me = await api("/auth/me", opts);
      if (me) {
        localStorage.setItem("novi_user", JSON.stringify(me));
        setUser(me);
      }
      return me;
    } catch (_) {
      return null;
    }
  };

  useEffect(() => {
    if (typeof window === "undefined") return;
    const tk = window.localStorage.getItem("novi_token");
    let u = null;
    try { u = JSON.parse(window.localStorage.getItem("novi_user") || "null"); } catch (_) {}
    if (!tk) { setReady(true); return; }
    setApiToken(tk);
    setToken(tk);
    setUser(u);
    api("/auth/me")
      .then((me) => {
        window.localStorage.setItem("novi_user", JSON.stringify(me));
        setUser(me);
      })
      .catch(() => { logout(); })
      .finally(() => setReady(true));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const value = { token, user, role: user?.role || null, ready, login, logout, patchUser, refreshUser };
  return <AuthCtx.Provider value={value}>{children}</AuthCtx.Provider>;
}

export function useAuth() { return useContext(AuthCtx); }