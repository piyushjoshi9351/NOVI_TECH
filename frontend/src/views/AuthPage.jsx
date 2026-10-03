import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "../api";
import { useAuth } from "../auth";
import { GENERIC_INVITE_MESSAGE, homeForRole } from "../parentAccess";
import { showLoader } from "../ui";

/**
 * The in-shell auth screen, shown when someone opens an app route without a
 * session. Same role-aware contract as the public /login + /signup screens:
 * students via /auth/signup, parents via /auth/parent/register only.
 */
export default function AuthPage() {
  const { login } = useAuth();
  const router = useRouter();
  const [loginErr, setLoginErr] = useState("");
  const [signupErr, setSignupErr] = useState("");
  const [notice, setNotice] = useState("");
  const [role, setRole] = useState("student");

  // ?as=parent deep link from the "For parents" pages. Read from the URL in an
  // effect rather than useSearchParams(), which App Router requires a Suspense
  // boundary for.
  useEffect(() => {
    if (new URLSearchParams(window.location.search).get("as") === "parent") setRole("parent");
  }, []);

  const finishLogin = async (token, user) => {
    const me = await login(token, user);
    router.replace(homeForRole(me?.role, me?.onboarding_completed));
  };

  const handleLogin = async (e) => {
    e.preventDefault();
    const fd = new FormData(e.target);
    setLoginErr("");
    showLoader(true);
    try {
      const res = await api("/auth/login", {
        method: "POST",
        body: JSON.stringify({
          email: fd.get("email"),
          password: fd.get("password"),
          expected_role: role,
        }),
      });
      await finishLogin(res.access_token, res.user);
    } catch (ex) {
      // 403 = the tab was the wrong one; offer the other rather than a dead end.
      if (ex.status === 403) setLoginErr(`${ex.message} Try the other option above.`);
      else setLoginErr(ex.message);
    } finally { showLoader(false); }
  };

  const handleSignup = async (e) => {
    e.preventDefault();
    const fd = new FormData(e.target);
    setSignupErr("");
    setNotice("");
    showLoader(true);
    try {
      if (role === "parent") {
        const student = String(fd.get("student_email") || "").trim();
        if (!student) {
          setSignupErr("Enter your child's email address.");
          showLoader(false);
          return;
        }
        const res = await api("/auth/parent/register", {
          method: "POST",
          body: JSON.stringify({
            name: fd.get("name"),
            email: fd.get("email"),
            password: fd.get("password"),
            student_email: student,
          }),
        });
        // Same sentence regardless of whether the student exists.
        setNotice(res?.message || GENERIC_INVITE_MESSAGE);
        return;
      }
      const res = await api("/auth/signup", {
        method: "POST",
        body: JSON.stringify({
          name: fd.get("name"),
          email: fd.get("email"),
          password: fd.get("password"),
          role: "student",
          school: fd.get("school") || null,
          grade: fd.get("grade") ? Number(fd.get("grade")) : null,
        }),
      });
      await finishLogin(res.access_token, res.user);
    } catch (ex) { setSignupErr(ex.message); }
    finally { showLoader(false); }
  };

  const field = (name, label, ph, type = "text") => (
    <div className="field">
      <label>{label}</label>
      <input name={name} type={type} placeholder={ph} />
    </div>
  );

  return (
    <div className="auth-wrap">
      <div className="auth-panel">
        <div className="auth-hero">
          <div className="brand-mark">N</div>
          <h1>Your AI mentor.<br />Your journey.<br />Your future.</h1>
          <p>The Operating System for Student Success — guiding you from Grade 9 to your dream university.</p>
        </div>

        <div className="card">
          <div className="between"><h2>Welcome back</h2>
            <select name="login-role" aria-label="Log in as" className="role-select" style={{ width: "auto" }} value={role} onChange={(e) => setRole(e.target.value)}>
              <option value="student">Log in as Student</option>
              <option value="parent">Log in as Parent</option>
            </select>
          </div>
          {loginErr ? <div className="error-banner mt">{loginErr}</div> : null}
          <form data-login-form className="mt" onSubmit={handleLogin}>
            {field("email", "Email", "you@school.edu", "email")}
            {field("password", "Password", "Your password", "password")}
            <button className="btn" style={{ width: "100%" }}>Log in</button>
          </form>
        </div>

        <div className="auth-divider"><span>New here? Create your account</span></div>

        <div className="card">
          <div className="between"><h2>Create account</h2>
            <select name="signup-role" aria-label="Register as" className="role-select" style={{ width: "auto" }} value={role} onChange={(e) => setRole(e.target.value)}>
              <option value="student">Register as Student</option>
              <option value="parent">Register as Parent</option>
            </select>
          </div>
          {signupErr ? <div className="error-banner mt">{signupErr}</div> : null}
          {notice ? <div className="notice-banner mt" role="status">{notice} <b>Now sign in as Parent above.</b></div> : null}
          <form data-signup-form className="mt" onSubmit={handleSignup}>
            {field("name", "Full name", "Your name")}
            {role === "student" ? <div data-student-only>{field("grade", "Grade", "e.g. 11")}</div> : null}
            {role === "student" ? field("school", "School", "Your school") : null}
            {role === "parent" ? (
              <div data-parent-only>
                {field("student_email", "Your child's email", "the email they signed up with", "email")}
                <p className="small muted">They decide what to share. Nothing is visible to you until they approve.</p>
              </div>
            ) : null}
            {field("email", "Email", "you@school.edu", "email")}
            {field("password", "Password (6+ chars)", "Create a password", "password")}
            <button className="btn" style={{ width: "100%" }}>Create account</button>
          </form>
        </div>
      </div>
    </div>
  );
}