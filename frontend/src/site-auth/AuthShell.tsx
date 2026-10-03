"use client";

import { useEffect, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { motion } from "framer-motion";
import { ArrowRight, Eye, EyeOff, Loader2, Sparkles } from "lucide-react";
import Logo from "@/components/ui/Logo";
import { api, clearApiCache, setApiToken } from "@/api";
import { useAuth } from "@/auth";
import { GENERIC_INVITE_MESSAGE, homeForRole } from "@/parentAccess";

type Role = "student" | "parent";

const PERKS: Record<Role, { emoji: string; title: string; desc: string }[]> = {
  student: [
    {
      emoji: "🧬",
      title: "Career DNA Profiling",
      desc: "Discover careers aligned with your strengths.",
    },
    {
      emoji: "🎓",
      title: "University Explorer",
      desc: "Compare colleges by your specific goals.",
    },
    {
      emoji: "💬",
      title: "24/7 AI Mentor",
      desc: "Your personal companion for the future.",
    },
  ],
  parent: [
    {
      emoji: "👀",
      title: "See the big picture",
      desc: "Goals, strengths and progress, on one calm page.",
    },
    {
      emoji: "🔒",
      title: "They stay in control",
      desc: "Nothing is shared until they approve it.",
    },
    {
      emoji: "🧭",
      title: "Support, not hovering",
      desc: "See where they are so you can ask better questions.",
    },
  ],
};

function GoogleG({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 48 48" aria-hidden="true" className={className}>
      <path
        fill="#FFC107"
        d="M43.611 20.083H42V20H24v8h11.303c-1.649 4.657-6.08 8-11.303 8-6.627 0-12-5.373-12-12s5.373-12 12-12c3.059 0 5.842 1.154 7.961 3.039l5.657-5.657C34.046 6.053 29.268 4 24 4 12.955 4 4 12.955 4 24s8.955 20 20 20 20-8.955 20-20c0-1.341-.138-2.65-.389-3.917z"
      />
      <path
        fill="#FF3D00"
        d="M6.306 14.691l6.571 4.819C14.655 15.108 18.961 12 24 12c3.059 0 5.842 1.154 7.961 3.039l5.657-5.657C34.046 6.053 29.268 4 24 4 16.318 4 9.656 8.337 6.306 14.691z"
      />
      <path
        fill="#4CAF50"
        d="M24 44c5.166 0 9.86-1.977 13.409-5.192l-6.19-5.238C29.211 35.091 26.715 36 24 36c-5.202 0-9.619-3.317-11.283-7.946l-6.522 5.025C9.285 40.146 16.1 44 24 44z"
      />
      <path
        fill="#1976D2"
        d="M43.611 20.083H42V20H24v8h11.303c-.792 2.237-2.231 4.166-4.087 5.571.001-.001.002-.002.003-.002l6.19 5.238C36.971 39.205 44 34 44 24c0-1.341-.138-2.65-.389-3.917z"
      />
    </svg>
  );
}

export default function AuthShell({ mode }: { mode: "login" | "register" }) {
  const router = useRouter();
  const { login } = useAuth();
  const [checked, setChecked] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [mismatch, setMismatch] = useState<Role | null>(null);
  const [notice, setNotice] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [studentEmail, setStudentEmail] = useState("");
  const [role, setRole] = useState<Role>("student");

  useEffect(() => {
    setChecked(false);
    const params = new URLSearchParams(window.location.search);
    // ?as=parent / ?as=student preselects the tab. ?mode=register is the older
    // deep link from the marketing pages and still means "parent".
    const as = params.get("as");
    if (as === "parent" || as === "student") setRole(as);
    else if (params.get("mode") === "register") setRole("parent");
    const saved = window.localStorage.getItem("novi.email") || "";
    if (saved) setEmail(saved);

    const googleError = params.get("google_error");
    if (googleError) setError("Google sign-in failed. Please try again.");

    const googleToken = params.get("google_token");
    if (googleToken) {
      window.history.replaceState({}, "", window.location.pathname);
      setApiToken(googleToken);
      clearApiCache();
      api("/auth/me")
        .then(async (me) => {
          window.localStorage.setItem("novi.email", me.email || "");
          const authed = await login(googleToken, me);
          // Role comes from /auth/me, never from the tab that was open.
          router.replace(homeForRole(authed?.role, authed?.onboarding_completed));
        })
        .catch(() => {
          setChecked(true);
          setError("Google sign-in failed. Please try again.");
        });
    } else {
      // Already signed in: ask the server who this is and send them to their own
      // home. Never assume student just because they opened the login page.
      const existing = window.localStorage.getItem("novi_token");
      if (!existing) {
        setChecked(true);
      } else {
        api("/auth/me")
          .then(async (me) => {
            const authed = await login(existing, me);
            router.replace(homeForRole(authed?.role, authed?.onboarding_completed));
          })
          .catch(() => {
            setChecked(true);
          });
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  /** Log in, then route on the role the SERVER reports — not on the selected tab. */
  const finishLogin = async (token: string, fallback: unknown) => {
    const me = await login(token, fallback);
    router.replace(homeForRole(me?.role, me?.onboarding_completed));
  };

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    setMismatch(null);
    setNotice("");

    const trimmedEmail = email.trim();
    if (!trimmedEmail || !password) {
      setError("Please enter your email and password.");
      return;
    }
    if (mode === "register") {
      if (!name.trim()) {
        setError("Please enter your name.");
        return;
      }
      if (password.length < 8) {
        setError("Password must be at least 8 characters.");
        return;
      }
      if (role === "parent" && !studentEmail.trim()) {
        setError("Please enter your child's email address.");
        return;
      }
    }

    setBusy(true);
    try {
      if (mode === "login") {
        // expected_role is a guard, not a filter: the backend trusts its own
        // record, so a 403 here only means the tab was the wrong one.
        const res = await api("/auth/login", {
          method: "POST",
          body: JSON.stringify({ email: trimmedEmail, password, expected_role: role }),
        });
        window.localStorage.setItem("novi.email", trimmedEmail);
        await finishLogin(res.access_token, res.user);
        return;
      }

      if (role === "parent") {
        // Parents are created ONLY here — /auth/signup is student-only. The
        // backend returns no token, so this does not log anyone in.
        const res = await api("/auth/parent/register", {
          method: "POST",
          body: JSON.stringify({
            name: name.trim(),
            email: trimmedEmail,
            password,
            student_email: studentEmail.trim(),
          }),
        });
        window.localStorage.setItem("novi.email", trimmedEmail);
        // The same sentence whatever the backend found, so it leaks nothing.
        setNotice(res?.message || GENERIC_INVITE_MESSAGE);
        return;
      }

      const res = await api("/auth/signup", {
        method: "POST",
        body: JSON.stringify({
          name: name.trim(),
          email: trimmedEmail,
          password,
          role: "student",
          school: null,
          grade: null,
        }),
      });
      window.localStorage.setItem("novi.email", trimmedEmail);
      await finishLogin(res.access_token, res.user);
    } catch (ex) {
      const err = ex as Error & { status?: number };
      if (mode === "login" && err.status === 403) {
        const other: Role = role === "parent" ? "student" : "parent";
        setMismatch(other);
        setError(`This account is registered as a ${other}. Try again below.`);
      } else {
        setError(err?.message || "Something went wrong.");
      }
    } finally {
      setBusy(false);
    }
  }

  if (!checked) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <Loader2 className="size-6 animate-spin text-primary" />
      </div>
    );
  }

  const isLogin = mode === "login";
  const other = isLogin ? "/signup" : "/login";

  function handleGoogle() {
    setError("");
    // The intent is signed server-side, so the Google path can't be used to
    // pick a role the account doesn't already have.
    const intent = mode === "register" ? `&intent=${role}` : "";
    window.location.href = `/api/auth/google?next=${encodeURIComponent(
      isLogin ? "/login" : "/signup",
    )}${intent}`;
  }

  return (
    <div className="relative min-h-screen overflow-hidden bg-background">
      <div className="orb -top-40 left-1/3 size-[38rem] bg-primary/10" />
      <div className="orb -bottom-40 -right-32 size-[30rem] bg-accent/8" />

      <div className="relative mx-auto flex min-h-screen w-full max-w-7xl items-center justify-center px-6 py-12">
        <div className="grid w-full items-stretch gap-8 lg:grid-cols-[1fr_1.1fr] lg:gap-16">
          <motion.div
            initial={{ opacity: 0, x: -24 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
            className="hidden flex-col justify-between lg:flex"
          >
            <div className="space-y-8">
              <Logo />
              <div className="space-y-5">
                <span className="inline-flex items-center gap-2 rounded-full border border-primary/20 bg-primary/10 px-4 py-1.5 text-xs font-bold uppercase tracking-widest text-primary">
                  <Sparkles className="size-3.5" />
                  The OS for Student Success
                </span>
                <h1 className="font-display text-4xl font-bold leading-[1.08] tracking-tight xl:text-5xl">
                  {role === "parent" ? (
                    <>
                      Support them{" "}
                      <span className="text-gradient">without hovering.</span>
                    </>
                  ) : (
                    <>
                      Your future starts{" "}
                      <span className="text-gradient">with one login.</span>
                    </>
                  )}
                </h1>
                <p className="max-w-md text-lg leading-relaxed text-muted">
                  {role === "parent"
                    ? "See goals, strengths and progress on one calm page — and only what they choose to share."
                    : "Sign in to continue your journey — from Grade 9 to your dream university and beyond."}
                </p>
              </div>
            </div>

            <div className="space-y-3">
              {(PERKS[role] || PERKS.student).map((p, i) => (
                <motion.div
                  key={p.title}
                  initial={{ opacity: 0, y: 16 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 0.15 + i * 0.1, duration: 0.5 }}
                  className="flex items-center gap-4 rounded-2xl border border-border-soft bg-surface/60 p-4"
                >
                  <span className="grid size-10 shrink-0 place-items-center rounded-xl bg-primary/10 text-xl">
                    {p.emoji}
                  </span>
                  <div>
                    <div className="text-sm font-bold">{p.title}</div>
                    <div className="text-xs text-muted">{p.desc}</div>
                  </div>
                </motion.div>
              ))}
            </div>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 24 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.08, ease: [0.22, 1, 0.36, 1] }}
            className="flex flex-col justify-center"
          >
            <div className="card-lift mx-auto w-full max-w-md rounded-3xl border border-border-soft bg-surface p-7 shadow-xl sm:p-8">
              <div className="mb-6 lg:hidden">
                <Logo />
              </div>

              <div>
                <h2 className="font-display text-2xl font-bold tracking-tight">
                  {isLogin ? "Welcome back" : "Create your account"}
                </h2>
                <p className="mt-1 text-sm text-muted">
                  {isLogin
                    ? role === "parent"
                      ? "Sign in to follow your child's progress."
                      : "Log in to continue your career journey."
                    : role === "parent"
                      ? "Create a parent account and request access."
                      : "Join Novi and let your AI mentor guide you."}
                </p>
              </div>

              <div className="mt-6 space-y-1.5">
                <span className="text-xs font-bold">{isLogin ? "Log in as" : "I am a"}</span>
                <div className="grid grid-cols-2 gap-1 rounded-xl border border-border-soft bg-background/50 p-1">
                  {(["student", "parent"] as const).map((r) => (
                    <button
                      key={r}
                      type="button"
                      onClick={() => { setRole(r); setError(""); setMismatch(null); }}
                      className={`rounded-lg px-4 py-2.5 text-sm font-semibold transition-colors ${
                        role === r
                          ? "bg-primary text-primary-foreground shadow-md shadow-primary/30"
                          : "text-muted hover:text-foreground"
                      }`}
                    >
                      {r === "student" ? "Student" : "Parent"}
                    </button>
                  ))}
                </div>
              </div>

              <button
                type="button"
                onClick={handleGoogle}
                className="mt-6 inline-flex w-full items-center justify-center gap-3 rounded-xl border border-border-soft bg-white px-6 py-3.5 text-sm font-bold text-gray-900 shadow-sm transition-all hover:-translate-y-0.5 hover:shadow-md hover:border-gray-300"
              >
                <GoogleG className="size-4.5 shrink-0" />
                Continue with Google
              </button>

              <div className="mt-5 flex items-center gap-3">
                <div className="h-px flex-1 bg-border-soft" />
                <span className="text-xs font-semibold uppercase tracking-widest text-muted">
                  or continue with email
                </span>
                <div className="h-px flex-1 bg-border-soft" />
              </div>

              <form onSubmit={handleSubmit} className="mt-6 space-y-4">
                {!isLogin && (
                  <>
                    <div className="space-y-1.5">
                      <label htmlFor="name" className="text-xs font-bold">
                        Full name
                      </label>
                      <input
                        type="text"
                        id="name"
                        required
                        autoComplete="name"
                        value={name}
                        onChange={(e) => setName(e.target.value)}
                        placeholder="Your name"
                        className="w-full rounded-xl border border-border-soft bg-background/40 px-4 py-3 text-sm outline-none transition-colors placeholder:text-muted/60 focus:border-primary/60"
                      />
                    </div>

                    {!isLogin && role === "parent" && (
                      <div className="space-y-1.5">
                        <label htmlFor="student-email" className="text-xs font-bold">
                          Your child&apos;s email
                        </label>
                        <input
                          type="email"
                          id="student-email"
                          required
                          autoComplete="off"
                          value={studentEmail}
                          onChange={(e) => setStudentEmail(e.target.value)}
                          placeholder="the email they signed up with"
                          className="w-full rounded-xl border border-border-soft bg-background/40 px-4 py-3 text-sm outline-none transition-colors placeholder:text-muted/60 focus:border-primary/60"
                        />
                        <p className="text-xs leading-relaxed text-muted">
                          They&apos;ll get a request and decide what to share. If they
                          don&apos;t have an account yet, we&apos;ll hold the request until
                          they do.
                        </p>
                        <p className="text-xs leading-relaxed text-muted/70">
                          Signing up with Google instead? We can&apos;t pass this address
                          through Google&apos;s flow, so you&apos;ll enter it on the next
                          screen instead.
                        </p>
                      </div>
                    )}
                  </>
                )}

                <div className="space-y-1.5">
                  <label htmlFor="email" className="text-xs font-bold">
                    Email
                  </label>
                  <input
                    type="email"
                    id="email"
                    required
                    autoComplete="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="you@example.com"
                    className="w-full rounded-xl border border-border-soft bg-background/40 px-4 py-3 text-sm outline-none transition-colors placeholder:text-muted/60 focus:border-primary/60"
                  />
                </div>

                <div className="space-y-1.5">
                  <label htmlFor="password" className="text-xs font-bold">
                    Password
                  </label>
                  <div className="relative">
                    <input
                      type={showPassword ? "text" : "password"}
                      id="password"
                      required
                      autoComplete={isLogin ? "current-password" : "new-password"}
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      placeholder={
                        isLogin ? "Your password" : "At least 8 characters"
                      }
                      className="w-full rounded-xl border border-border-soft bg-background/40 px-4 py-3 pr-12 text-sm outline-none transition-colors placeholder:text-muted/60 focus:border-primary/60"
                    />
                    <button
                      type="button"
                      onClick={() => setShowPassword((v) => !v)}
                      aria-label={showPassword ? "Hide password" : "Show password"}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-muted transition-colors hover:text-foreground"
                    >
                      {showPassword ? (
                        <EyeOff className="size-4" />
                      ) : (
                        <Eye className="size-4" />
                      )}
                    </button>
                  </div>
                </div>

                {notice && (
                  <div
                    role="status"
                    data-testid="invite-notice"
                    className="rounded-xl border border-primary/25 bg-primary/10 px-4 py-3 text-sm font-medium text-foreground"
                  >
                    {notice}
                    <div className="mt-3 flex flex-wrap items-center gap-2">
                      <Link
                        href="/login?as=parent"
                        className="rounded-lg bg-primary px-3 py-1.5 text-xs font-bold text-primary-foreground"
                      >
                        Sign in as Parent
                      </Link>
                      <span className="text-xs text-muted">
                        We&apos;ve only created your account so far.
                      </span>
                    </div>
                  </div>
                )}

                {error && (
                  <div
                    role="alert"
                    className="rounded-xl border border-red-500/20 bg-red-500/10 px-4 py-3 text-sm font-medium text-red-500"
                  >
                    {error}
                    {mismatch && (
                      <button
                        type="button"
                        onClick={() => { setRole(mismatch); setError(""); setMismatch(null); }}
                        className="mt-2 block font-bold underline underline-offset-2"
                      >
                        Continue as {mismatch === "parent" ? "Parent" : "Student"}
                      </button>
                    )}
                  </div>
                )}

                <button
                  type="submit"
                  disabled={busy}
                  className="btn-shine inline-flex w-full items-center justify-center gap-2 rounded-xl bg-primary px-6 py-3.5 text-sm font-bold text-primary-foreground shadow-lg shadow-primary/30 transition-all hover:-translate-y-0.5 disabled:cursor-not-allowed disabled:opacity-60 disabled:hover:translate-y-0"
                >
                  {busy ? (
                    <>
                      <Loader2 className="size-4 animate-spin" />
                      {isLogin ? "Logging in…" : "Creating account…"}
                    </>
                  ) : (
                    <>
                      {isLogin ? "Log in" : "Create account"}
                      <ArrowRight className="size-4" />
                    </>
                  )}
                </button>
              </form>

              <p className="mt-6 text-center text-sm text-muted">
                {isLogin ? (
                  <>
                    New to Novi?{" "}
                    <Link
                      href="/signup"
                      className="font-semibold text-primary hover:opacity-80"
                    >
                      Create an account
                    </Link>
                  </>
                ) : (
                  <>
                    Already have an account?{" "}
                    <Link
                      href="/login"
                      className="font-semibold text-primary hover:opacity-80"
                    >
                      Log in
                    </Link>
                  </>
                )}
              </p>
            </div>

            <p className="mx-auto mt-6 max-w-md text-center text-xs leading-relaxed text-muted lg:hidden">
              By continuing, you agree to Novi&apos;s{" "}
              <Link href="/terms" className="underline hover:opacity-80">
                Terms
              </Link>{" "}
              and{" "}
              <Link href="/privacy" className="underline hover:opacity-80">
                Privacy Policy
              </Link>
              .
            </p>
          </motion.div>
        </div>
      </div>
    </div>
  );
}