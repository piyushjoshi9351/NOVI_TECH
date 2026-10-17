/** Shared password policy and ordered authentication destinations. */
export const ROLE_HOME = { parent: "/parent", student: "/dashboard" };
export const ADD_CHILD = "/parent/add-child";
export const FIRST_LOGIN = "/first-login";

export function passwordError(password, existing = false) {
  if (!password) return "Enter your password.";
  if (!existing && [...password].length < 8) return "Use at least 8 characters.";
  if (new TextEncoder().encode(password).length > 72) return "Use at most 72 bytes (some characters use more than one byte).";
  return "";
}

export function passwordSettingsMessage(user) {
  if (user?.has_local_password === true) return "";
  return user?.has_local_password === false
    ? "This account uses Google sign-in. Manage your password in your Google account."
    : "Your sign-in method has not been confirmed yet. Sign in with email and password to enable password settings, or continue using Google.";
}

export async function googleDestination(token, login, next) {
  // login stores the callback JWT and fetches fresh /auth/me. The returned
  // identity reflects Google's takeover of a temporary-password account.
  return destinationFor(await login(token), next);
}

/** Only local, known app routes may be used as return destinations. */
export function safeNext(value, role) {
  if (typeof value !== "string" || !value.startsWith("/") || value.startsWith("//")) return "";
  try {
    const decoded = decodeURIComponent(value);
    if (/[\\\s\u0000-\u001f]/.test(decoded) || decoded.startsWith("//")) return "";
    const url = new URL(value, "https://novi.local");
    if (url.origin !== "https://novi.local") return "";
    if ([...url.searchParams.keys()].some((key) => /token|password|secret|code/i.test(key))) return "";
    const path = url.pathname;
    const parentPath = /^\/parent(?:\/(?:\d+|add-child|settings))?\/?$/.test(path) || path === "/advisor" || path === "/overview";
    const studentPath = /^\/(?:dashboard|chat|dna|careers|universities|roadmap|passport|checkin|profile|onboarding|first-login)\/?$/.test(path)
      || /^\/(?:career|university)\/[^/]+\/?$/.test(path);
    if (!(role === "parent" ? parentPath : role === "student" ? studentPath : parentPath || studentPath)) return "";
    return url.pathname + url.search + url.hash;
  } catch (_) {
    return "";
  }
}

export function setupPath(user) {
  if (user?.role === "student" && user.must_change_password) return FIRST_LOGIN;
  if (user?.role === "student" && !user.onboarding_completed) return "/onboarding";
  if (user?.role === "parent" && user.needs_child_setup) return ADD_CHILD;
  return "";
}

export function withNext(path, next) {
  return next ? `${path}?next=${encodeURIComponent(next)}` : path;
}

export function destinationFor(user, next) {
  const home = ROLE_HOME[user?.role] || "/dashboard";
  let target = safeNext(next, user?.role);
  // A session may expire during setup. Recover the original destination from
  // that setup URL rather than losing it on the next login.
  for (let depth = 0; depth < 4 && target; depth++) {
    const url = new URL(target, "https://novi.local");
    if (![FIRST_LOGIN, "/onboarding", ADD_CHILD].includes(url.pathname)) break;
    const nested = url.searchParams.get("next");
    if (!nested) break;
    target = safeNext(nested, user?.role);
  }
  const setup = setupPath(user);
  if (setup) return withNext(setup, target && ![FIRST_LOGIN, "/onboarding", ADD_CHILD].includes(target.split("?")[0]) ? target : "");
  if ([FIRST_LOGIN, "/onboarding"].includes(target.split("?")[0])) return home;
  return target || home;
}

export function redirectFor({ token, user, pathname, search = "", requiredRole }) {
  const next = new URLSearchParams(search).get("next");
  if (!token || !user) return withNext("/login", safeNext(pathname + search));
  const setup = setupPath(user);
  if (setup && pathname !== setup) return destinationFor(user, next || pathname + search);
  if (setup) return "";
  if (requiredRole && user.role !== requiredRole) return destinationFor(user, next);
  if (!safeNext(pathname, user.role) || pathname === FIRST_LOGIN || pathname === "/onboarding") return destinationFor(user, next);
  return "";
}
