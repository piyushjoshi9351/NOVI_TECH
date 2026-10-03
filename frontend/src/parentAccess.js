/* ------------------------------------------------------------------ *
 * Shared bits of the parent-linking contract.
 *
 * The backend is the authority: these constants only mirror what it returns so
 * the two auth screens and both areas render the same wording.
 * ------------------------------------------------------------------ */

/** MUST match app/services/parent_links.py:GENERIC_INVITE_MESSAGE.
 *  Shown whether or not the student actually has an account — it must never
 *  reveal which, or the form becomes an account-enumeration oracle. */
export const GENERIC_INVITE_MESSAGE =
  "If this student has a Novi account, we've sent them a request";

/** Where a freshly authenticated user belongs, keyed by the role /auth/me
 *  reports (never by the tab they picked on the login screen). */
export const homeForRole = (role, onboardingCompleted) =>
  role === "parent" ? "/parent" : onboardingCompleted ? "/dashboard" : "/onboarding";

/** Scope ids are the backend's. "basic" can never be switched off. */
export const SCOPES = [
  {
    id: "basic",
    label: "Basic overview",
    blurb: "Their grade, goals, passport and this week's priorities.",
    locked: true,
  },
  {
    id: "insights",
    label: "Insights",
    blurb: "Interests, strengths, career zones and match percentages.",
    locked: false,
  },
  {
    id: "memory",
    label: "Long-term memory",
    blurb: "A short summary and highlights Novi remembered. Never your conversations.",
    locked: false,
  },
];

export const scopeMeta = (id) => SCOPES.find((s) => s.id === id);

/** A link the student hasn't answered yet. */
export const isPending = (link) => link && link.status === "pending";
export const isActive = (link) => link && link.status === "active";
export const isRevoked = (link) => link && link.status === "revoked";

/** Best available name for a link. The backend hides student details until a
 *  link is active, so a pending row can legitimately have no name at all. */
export function linkName(link) {
  if (!link) return "your child";
  if (link.student && link.student.first_name) return link.student.first_name;
  if (link.invited_email_first_name) return link.invited_email_first_name;
  if (link.label && link.label.toLowerCase() !== "child") return link.label;
  return "Your child";
}

/** "Waiting for <student> to approve" */
export const pendingHeadline = (link) => `Waiting for ${linkName(link)} to approve`;

export const STATUS_TONE = { active: "good", pending: "warn", revoked: "bad" };
export const STATUS_LABEL = { active: "Connected", pending: "Awaiting approval", revoked: "Disconnected" };