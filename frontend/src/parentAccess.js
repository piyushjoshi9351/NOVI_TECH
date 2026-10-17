/** Relationship states and scope labels shared by parent/student screens. */
export const SCOPES = [
  { id: "basic", label: "Basic overview", blurb: "Basic identity and progress, goals, passport counts and journey stage. Included while the parent link is active.", locked: true },
  { id: "insights", label: "Insights", blurb: "Structured interests, strengths, career areas and parent-safe passport summaries. Private chat evidence is excluded.", locked: false },
  { id: "memory", label: "Growth history", blurb: "Completed milestones and confidence trends. Chats, check-in text and Letta memory stay private.", locked: false },
];

export const scopeMeta = (id) => SCOPES.find((scope) => scope.id === id);
export const isPending = (link) => link?.status === "pending";
export const isActive = (link) => link?.status === "active";
export const isRevoked = (link) => link?.status === "revoked";
export const isParentCreated = (link) => link?.activation_source === "parent_created";

export function linkName(link) {
  if (link?.student?.first_name) return link.student.first_name;
  if (link?.invited_email_first_name) return link.invited_email_first_name;
  if (link?.label && link.label.toLowerCase() !== "child") return link.label;
  return "Your child";
}

export const pendingHeadline = () => "Legacy pending connection";
export const STATUS_TONE = { active: "good", pending: "warn", revoked: "bad" };
export const STATUS_LABEL = { active: "Connected", pending: "Legacy pending", revoked: "Access removed" };

export const ACCOUNT_STATES = {
  account_created: { label: "Account created", detail: "The account is connected. Setup history is limited; progress appears as your child continues with Novi." },
  awaiting_first_login: { label: "Awaiting first login", detail: "The account is created and basic sharing is connected. Give your child their email and temporary password so they can sign in." },
  onboarding_in_progress: { label: "Onboarding in progress", detail: "Your child has signed in and is completing password setup or onboarding. Their progress will appear as they get started." },
  active: { label: "Active", detail: "Your child has completed onboarding. This view follows their current sharing settings." },
};

export function accountState(link) {
  return ACCOUNT_STATES[link?.account_state] || ACCOUNT_STATES.account_created;
}
