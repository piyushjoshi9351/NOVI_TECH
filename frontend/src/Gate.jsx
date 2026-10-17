"use client";

import { useEffect } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "./auth";
import { redirectFor } from "./authFlow";

export { ROLE_HOME } from "./authFlow";

export default function Gate({ requiredRole, children }) {
  const { token, user, ready } = useAuth();
  const pathname = usePathname();
  const search = useSearchParams().toString();
  const router = useRouter();
  const redirect = redirectFor({ token, user, pathname, search, requiredRole });
  useEffect(() => {
    if (ready && redirect) router.replace(redirect);
  }, [ready, redirect, router]);
  return ready && !redirect ? children : null;
}
