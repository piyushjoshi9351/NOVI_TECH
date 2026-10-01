"use client";
import { createContext, useContext, useEffect, useState } from "react";
import { api, clearApiCache, setApiToken, resetWarmAll } from "./api";

const AuthCtx = createContext(null);

export function AuthProvider({ children }) {
  const [token, setToken] = useState(null);
  const [user, setUser] = useState(null);
  const [ready, setReady] = useState(false);

  const login = (tk, u) => {
    localStorage.setItem("novi_token", tk);
    localStorage.setItem("novi_user", JSON.stringify(u));
    setApiToken(tk);
    setToken(tk);
    setUser(u);
    resetWarmAll();
    clearApiCache();
  };

  const logout = () => {
    localStorage.removeItem("novi_token");
    localStorage.removeItem("novi_user");
    setApiToken(null);
    setToken(null);
    setUser(null);
    resetWarmAll();
    clearApiCache();
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

  const value = { token, user, ready, login, logout, patchUser, refreshUser };
  return <AuthCtx.Provider value={value}>{children}</AuthCtx.Provider>;
}

export function useAuth() { return useContext(AuthCtx); }