"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "./auth";

/** Where each role belongs once authenticated. */
export const ROLE_HOME = { parent: "/parent", student: "/dashboard" };

export default function Gate({ page, requiredRole, children }) {
  const { user, role, token, ready } = useAuth();
  const router = useRouter();

  // requiredRole is the strong assertion used by the new /parent area: a
  // student there is bounced to their own home, a parent to the parent area.
  // Everything else falls back to the original page-based rules.
  const wrongRole = !!requiredRole && !!role && role !== requiredRole;

  useEffect(() => {
    if (!ready) return;
    if (!token || !user) {
      router.replace(`/login?next=${encodeURIComponent(page || "")}`);
      return;
    }
    if (wrongRole) {
      router.replace(ROLE_HOME[role] || "/dashboard");
      return;
    }
    if (requiredRole) return;

    const isParent = role === "parent";
    if (isParent) {
      // Parents have no business on a student route; send them to their own area
      // rather than the legacy parent overview page.
      if (page !== "overview" && page !== "advisor" && page !== "parent") {
        router.replace(ROLE_HOME.parent);
      }
      return;
    }
    // Students must finish onboarding before anything else opens up. Until they
    // do, /onboarding is the ONLY page — every other route bounces back there.
    if (!user.onboarding_completed) {
      if (page !== "onboarding") router.replace("/onboarding");
    } else if (page === "onboarding") {
      // A completed student has no onboarding tab/flow left — go to the dashboard.
      router.replace("/dashboard");
    }
  }, [ready, token, user, role, page, requiredRole, wrongRole, router]);

  if (!ready || !token || !user) return null;
  if (wrongRole) return null;
  if (requiredRole) return children;

  const isParent = role === "parent";
  if (isParent) {
    if (page !== "overview" && page !== "advisor" && page !== "parent") return null;
    return children;
  }
  if (!user.onboarding_completed) {
    if (page !== "onboarding") return null;
    return children;
  }
  if (page === "overview" || page === "advisor" || page === "parent") return null;
  return children;
}