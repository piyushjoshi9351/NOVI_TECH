"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function OverviewPage() {
  const router = useRouter();
  useEffect(() => { router.replace("/parent"); }, [router]);
  return <p role="status">Opening your parent dashboard…</p>;
}
