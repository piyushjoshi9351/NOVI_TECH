"use client";

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import {
  Baby, BookMarked, Briefcase, CalendarCheck, Dna, GraduationCap, LayoutDashboard, LogOut, Map, MessageCircle, Moon, Sparkles, Sun, UserRound,
} from "lucide-react";
import { useAuth } from "./auth";
import { redirectFor, setupPath } from "./authFlow";
import { applyTheme, bootAppearance, getTheme, setPrefKey, warmAllRoutes } from "./api";
import { Loader, toast, ToastHost } from "./ui";

const studentNav = [
  ["dashboard", "Dashboard"], ["chat", "Chat"], ["dna", "My DNA"],
  ["careers", "Careers"], ["universities", "Universities"],
  ["roadmap", "Roadmap"], ["passport", "Passport"], ["checkin", "Check-in"],
  ["profile", "Profile"],
];
/* A parent gets its own navigation. Note there is deliberately no "Overview"
 * entry pointing at /overview: that route renders the *student* OverviewPage,
 * so linking a parent there would hand them a student dashboard. The parent's
 * dashboard lives at /parent, which is also where the per-section tabs are. */
const parentNav = [
  ["parent", "My Children"], ["advisor", "Ask Novi"],
  ["parent/add-child", "Add child"], ["parent/settings", "Settings"],
];

const NAV_ICONS = {
  dashboard: LayoutDashboard,
  chat: MessageCircle,
  dna: Dna,
  careers: Briefcase,
  universities: GraduationCap,
  roadmap: Map,
  passport: BookMarked,
  checkin: CalendarCheck,
  profile: UserRound,
  overview: LayoutDashboard,
  advisor: Sparkles,
  parent: Baby,
  "parent/add-child": Baby,
  "parent/settings": UserRound,
};

function ThemeToggle() {
  const [dark, setDark] = useState(() => typeof window === "undefined" || getTheme() === "dark");
  return (
    <button
      className="tb-theme"
      title={dark ? "Switch to light mode" : "Switch to dark mode"}
      aria-label={dark ? "Switch to light mode" : "Switch to dark mode"}
      onClick={() => {
        const next = dark ? "light" : "dark";
        applyTheme(next);
        setPrefKey("theme", next);
        setDark(next === "dark");
        const html = document.documentElement;
        html.classList.add("theme-anim");
        window.setTimeout(() => html.classList.remove("theme-anim"), 420);
      }}
    >
      {dark ? <Sun size={18} strokeWidth={1.8} /> : <Moon size={18} strokeWidth={1.8} />}
    </button>
  );
}

function Sidebar() {
  const { user, logout } = useAuth();
  const pathname = usePathname();
  const items = user && user.role === "parent" ? parentNav : studentNav;
  const name = user?.first_name || user?.name || user?.email || "NOVI";
  const grade = user?.grade ? `Grade ${user.grade}` : "";
  return (
    <aside className="sidebar">
      <div className="brand">
        <span className="brand-mark">
          <svg viewBox="0 0 24 24" width="21" height="21" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round">
            <path d="M4 16.5 9.2 10l4 3.2L19.5 5" />
            <path d="M15.2 5H19.5v4.3" />
          </svg>
        </span>
        <span className="brand-copy">
          <span className="brand-name">NOVI</span>
          <span className="brand-tag">Your Success OS</span>
        </span>
      </div>

      <nav className="nav">
        {items.map(([key, label]) => {
          const Icon = NAV_ICONS[key] || MessageCircle;
          // prefix match, so /parent/<studentId> still lights up "My Children"
          const active = pathname === `/${key}` || (key === "parent" ? /^\/parent\/\d+/.test(pathname) : pathname.startsWith(`/${key}/`));
          return (
            <Link key={key} href={`/${key}`} className={active ? "active" : ""}>
              <Icon className="nav-ico" size={18} strokeWidth={2} />
              <span className="nav-label">{label}</span>
            </Link>
          );
        })}
      </nav>

      <div className="sidebar-foot">
        <div className="sidebar-user">
          <b>{name}</b>
          {grade ? <span className="sidebar-grade"> · {grade}</span> : null}
        </div>
        <div className="sidebar-actions">
          <ThemeToggle />
          <button className="logout-btn" onClick={() => { logout(); toast("Signed out — see you soon 👋", "info"); }}>
            <LogOut size={16} strokeWidth={2} />
            <span>Log out</span>
          </button>
        </div>
      </div>
    </aside>
  );
}

function ScrollToTop() {
  const pathname = usePathname();
  useEffect(() => { window.scrollTo(0, 0); }, [pathname]);
  return null;
}

export function RootShell({ children }) {
  const { token, user, ready } = useAuth();
  const pathname = usePathname();
  const router = useRouter();
  const search = useSearchParams().toString();
  const redirect = redirectFor({ token, user, pathname, search });
  const setup = setupPath(user);
  useEffect(() => {
    // appearance + route pre-warm only ever make sense in the browser
    bootAppearance();
  }, []);
  useEffect(() => {
    if (!ready || !token || !user?.role || setup || redirect) return;
    warmAllRoutes();
  }, [ready, token, user?.role, setup, redirect]);

  // A student who hasn't finished onboarding sees ONLY the onboarding flow —
  // no dashboard, no nav, no other route — until it is complete.
  // (Declared before the early returns so every render calls the same hooks.)
  useEffect(() => {
    if (ready && redirect) router.replace(redirect);
  }, [ready, redirect, router]);

  const isChat = pathname === "/chat";

  if (!ready) return (
    <div className="app">
      <p role="status">Loading account…</p>
      <Loader />
      <ToastHost />
    </div>
  );

  // The public /login route owns authentication UI. Keep the app shell empty
  // while navigating there after logout or session expiry.
  if (!token || !user || redirect) return null;

  // A student who hasn't finished onboarding sees ONLY the onboarding flow —
  // no dashboard, no nav, no other route — until it is complete.
  if (setup && user.role === "student") {
    return (
      <div className="app app-onboarding">
        <ScrollToTop />
        <main id="view" className="view">
          {children}
        </main>
        <ToastHost />
      </div>
    );
  }

  return (
    <div className="app">
      <ScrollToTop />
      <Sidebar />
      <main id="view" className={`view${isChat ? " chat-page" : ""}`}>
        {children}
      </main>
      <ToastHost />
    </div>
  );
}

export default function AppShell({ children }) {
  return (
    <Suspense fallback={<p role="status">Loading account…</p>}>
      <RootShell>{children}</RootShell>
    </Suspense>
  );
}
