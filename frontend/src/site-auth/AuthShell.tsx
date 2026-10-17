"use client";

import { Loader2 } from "lucide-react";
import Logo from "@/components/ui/Logo";
import AuthForm from "@/components/auth/AuthForm";
import { useAuthForm } from "@/useAuthForm";

export default function AuthShell({ mode }: { mode: "login" | "register" }) {
  const form = useAuthForm(mode);
  if (!form.checked) return <div className="flex min-h-screen items-center justify-center bg-background"><Loader2 className="size-6 animate-spin text-primary" aria-label="Loading account" /></div>;
  return (
    <div className="relative min-h-screen overflow-hidden bg-background">
      <div className="orb -top-40 left-1/3 size-[38rem] bg-primary/10" />
      <div className="relative mx-auto grid min-h-screen w-full max-w-6xl items-center gap-12 px-6 py-28 lg:grid-cols-2">
        <div className="hidden space-y-6 lg:block">
          <Logo />
          <h1 className="font-display text-5xl font-bold tracking-tight">
            {form.role === "parent" ? "Help your child take the next step." : "Your journey continues here."}
          </h1>
          <p className="max-w-md text-lg text-muted">
            {form.role === "parent" ? "Create your parent account, add your children, and follow their progress. Their conversations with Novi stay private." : "Sign in with the account your parent created, or your existing student account."}
          </p>
        </div>
        <div className="mx-auto w-full max-w-md rounded-3xl border border-border-soft bg-surface p-7 shadow-xl sm:p-8">
          <div className="mb-6 lg:hidden"><Logo /></div>
          <AuthForm form={form} mode={mode} />
        </div>
      </div>
    </div>
  );
}
