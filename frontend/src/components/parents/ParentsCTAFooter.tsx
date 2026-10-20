"use client";

import Image from "next/image";
import Link from "next/link";
import { motion } from "framer-motion";
import { ArrowUpRight, CheckCircle2, Sparkles, Users } from "lucide-react";
import Reveal from "@/components/ui/Reveal";
import Magnetic from "@/components/ui/Magnetic";
import { useTheme } from "@/components/ui/ThemeProvider";

const ease = [0.22, 1, 0.36, 1] as const;

const checks = [
  "It's free to get started",
  "Built around your child's goals",
  "Stay informed without pressure",
];

const footerLinks = {
  "For Students": [
    { label: "How It Works", href: "/#how-it-works" },
    { label: "Career Explorer", href: "/careers" },
    { label: "University Explorer", href: "/universities" },
    { label: "AI Roadmap", href: "/for-students" },
  ],
  "For Parents": [
    { label: "Parent Dashboard", href: "/for-parents" },
    { label: "How We Help", href: "/for-parents" },
    { label: "Resources", href: "/for-parents" },
  ],
  Company: [
    { label: "About Us", href: "/#about" },
    { label: "Blog", href: "/coming-soon" },
    { label: "Careers", href: "/careers" },
    { label: "Contact Us", href: "/coming-soon" },
  ],
  Legal: [
    { label: "Privacy Policy", href: "/privacy" },
    { label: "Terms of Service", href: "/terms" },
    { label: "Cookie Policy", href: "/cookies" },
  ],
};

export default function ParentsCTAFooter() {
  const { theme } = useTheme();

  return (
    <>
      <section className="relative overflow-hidden bg-background pb-24 pt-8">
        <div className="mx-auto max-w-7xl px-6">
          <Reveal>
            <div className="relative overflow-hidden rounded-3xl border border-border-soft bg-surface p-8 sm:p-12">
              <div className="pointer-events-none absolute inset-0 bg-dots opacity-15" />
              <div className="orb -top-20 -right-20 size-60 bg-primary/25" />
              <div className="orb -bottom-20 -left-20 size-60 bg-accent/20" />

              <div className="relative z-10 grid items-center gap-10 lg:grid-cols-2">
                <div className="order-2 flex justify-center lg:order-1">
                  <motion.div
                    animate={{ y: [0, -8, 0] }}
                    transition={{ duration: 4, repeat: Infinity, ease }}
                    className="relative"
                  >
                    <div className="relative size-60 overflow-hidden rounded-full border border-border-soft sm:size-72">
                      <Image
                        src="/3dboy.png"
                        alt="Novi parent guidance"
                        fill
                        priority
                        className="object-contain drop-shadow-2xl"
                      />
                    </div>
                    <motion.span
                      animate={{ rotate: 360 }}
                      transition={{ duration: 20, repeat: Infinity, ease: "linear" }}
                      className="absolute inset-0 -m-4 rounded-full"
                      style={{
                        background: `conic-gradient(from 0deg, transparent, ${theme === "dark" ? "rgba(124,109,242,0.3)" : "rgba(108,92,231,0.25)"}, transparent, ${theme === "dark" ? "rgba(45,217,191,0.3)" : "rgba(18,201,178,0.25)"}, transparent)`,
                      }}
                    />
                  </motion.div>
                </div>

                <div className="order-1 space-y-6 lg:order-2">
                  <div className="inline-flex items-center gap-2 rounded-full bg-primary/10 px-3 py-1.5 text-xs font-semibold text-primary">
                    <Sparkles className="size-3.5" /> Start your journey
                  </div>
                  <h2 className="font-display text-3xl font-bold leading-[1.1] text-foreground sm:text-4xl lg:text-5xl">
                    A clearer path for them.
                    <br className="hidden sm:block" />
                    <span className="text-gradient">
                      Greater confidence for you.
                    </span>
                  </h2>
                  <p className="max-w-md text-sm leading-relaxed text-muted">
                    Novi helps your child explore, reflect and take ownership of their decisions—with you supporting the journey.
                  </p>
                  <div className="flex flex-wrap gap-3">
                    <Magnetic strength={12}>
                      <Link
                        href="/signup"
                        className="btn-shine inline-flex items-center gap-2 rounded-full bg-primary px-7 py-3 text-sm font-semibold text-primary-foreground transition-all hover:-translate-y-0.5 hover:shadow-lg"
                      >
                        Explore Novi for parents
                        <ArrowUpRight className="size-4" />
                      </Link>
                    </Magnetic>
                    <Link
                      href="/for-students"
                      className="inline-flex items-center gap-2 rounded-full border border-border-soft px-7 py-3 text-sm font-semibold text-muted transition-colors hover:border-primary/50 hover:text-foreground"
                    >
                      <Users className="size-4 text-primary" />
                      Explore Student Dashboard
                    </Link>
                  </div>
                  <div className="flex flex-wrap gap-x-5 gap-y-2 pt-2">
                    {checks.map((c) => (
                      <span
                        key={c}
                        className="flex items-center gap-2 text-xs text-muted"
                      >
                        <CheckCircle2 className="size-3.5 text-accent" />
                        {c}
                      </span>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          </Reveal>
        </div>
      </section>

      <footer className="border-t border-border-soft bg-surface py-16">
        <div className="mx-auto max-w-7xl px-6">
          <div className="grid gap-10 sm:grid-cols-2 lg:grid-cols-6">
            <div className="sm:col-span-2">
              <Link href="/" className="flex items-center gap-2">
                <div className="relative size-8 overflow-hidden rounded-lg">
                  <Image
                    src="/icon.png"
                    alt="Novi logo"
                    fill
                    sizes="32px"
                    className="object-contain"
                  />
                </div>
                <span className="font-display text-lg font-bold">Novi</span>
              </Link>
              <p className="mt-3 max-w-xs text-xs leading-relaxed text-muted">
                The AI-powered Operating System for Student Success. Guide
                yourself from Grade 9 to your dream university.
              </p>
              <div className="mt-4 flex gap-3">
                {["Instagram", "YouTube", "LinkedIn", "Twitter"].map((s) => (
                  <Link
                    key={s}
                    href="/coming-soon"
                    className="grid size-8 place-items-center rounded-lg border border-border-soft text-[10px] font-bold text-muted transition-colors hover:border-primary/50 hover:text-foreground"
                  >
                    {s[0]}
                  </Link>
                ))}
              </div>
            </div>

            {Object.entries(footerLinks).map(([title, links]) => (
              <div key={title}>
                <h4 className="mb-3 text-xs font-bold uppercase tracking-wider text-muted">
                  {title}
                </h4>
                <ul className="space-y-2">
                  {links.map((link) => (
                    <li key={link.label}>
                      <Link
                        href={link.href}
                        className="text-xs text-muted transition-colors hover:text-primary"
                      >
                        {link.label}
                      </Link>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>

          <div className="mt-12 flex flex-col items-center justify-between gap-4 border-t border-border-soft pt-8 sm:flex-row">
            <p className="text-[10px] text-muted">
              © {new Date().getFullYear()} Novi. All rights reserved.
            </p>
            <div className="flex gap-4 text-[10px] text-muted">
              <Link href="/privacy" className="hover:text-foreground">
                Privacy
              </Link>
              <Link href="/terms" className="hover:text-foreground">
                Terms
              </Link>
              <Link href="/cookies" className="hover:text-foreground">
                Cookies
              </Link>
            </div>
          </div>
        </div>
      </footer>
    </>
  );
}
