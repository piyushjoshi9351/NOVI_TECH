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

/** Scope ids are the backend's. "basic" can never be switched off.
 *
 *  The id stays `memory` on purpose: it is the key already stored on every
 *  existing consent, so renaming the id would silently revoke it. Only the
 *  human-facing label changed -- "Long-term memory" promised a summary and
 *  highlights, which is exactly what the backend used to hand over from Letta
 *  (LLM-written paraphrases of the student's own conversations). What it
 *  actually serves now is milestones and a confidence trend from the student's
 *  own growth tables. The wording below describes that, so the consent the
 *  student gives is the consent they actually get. */
export const SCOPES = [
  {
    id: "basic",
    label: "Basic overview",
    blurb: "Their grade, current focus, goals, passport counts and journey stage.",
    locked: true,
  },
  {
    id: "insights",
    label: "Insights",
    blurb:
      "Interests, strengths and career areas Novi has spotted — plus the passport " +
      "entries they've added, including what they've written about them.",
    locked: false,
  },
  {
    id: "memory",
    label: "Growth history",
    blurb: "Milestones they've completed and how their confidence has changed. Not their conversations or anything they tell Novi in private.",
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