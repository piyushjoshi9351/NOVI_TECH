"use client";

import { motion } from "framer-motion";
import Link from "next/link";
import Image from "next/image";
import { ArrowUpRight, Sparkles } from "lucide-react";
import Reveal from "@/components/ui/Reveal";
import Magnetic from "@/components/ui/Magnetic";

const stats = [
  { value: "10,000+", label: "Students guided" },
  { value: "5,000+", label: "Universities explored" },
  { value: "4.9/5", label: "Average rating" },
];

const perks = [
  "Personalized AI Mentor",
  "4-Year Journey",
  "Career + University Guidance",
  "Built around you",
];

export default function StudentsHero() {
  return (
    <section className="relative overflow-hidden pt-32 pb-24">
      <div className="orb -top-32 -right-32 size-[32rem] bg-primary/25" />
      <div className="orb bottom-0 -left-32 size-[28rem] bg-accent/10" />

      <div className="relative mx-auto max-w-7xl px-6">
        <div className="grid items-center gap-12 lg:grid-cols-12">
          <div className="space-y-7 lg:col-span-5">
            <Reveal>
              <span className="inline-flex items-center gap-2 rounded-full border border-primary/20 bg-primary/10 px-4 py-1.5 text-xs font-bold uppercase tracking-widest text-primary">
                <Sparkles className="size-3.5" /> Built for your future
              </span>
            </Reveal>

            <Reveal delay={0.08}>
              <h1 className="font-display text-4xl font-bold leading-[1.08] tracking-tight sm:text-5xl lg:text-6xl">
                Your future. Your choices.{" "}
                <span className="animate-gradient bg-gradient-to-r from-primary via-violet-400 to-indigo-400 bg-clip-text text-transparent">
                  Your journey.
                </span>
              </h1>
            </Reveal>

            <Reveal delay={0.16}>
              <p className="max-w-lg text-lg leading-relaxed text-muted">
                You don&apos;t have to know what you want to become yet. Novi helps you discover what you&apos;re good at, explore what&apos;s possible, and build a path toward your future — all at your own pace.
              </p>
            </Reveal>

            <Reveal delay={0.22}>
              <div className="flex flex-wrap gap-3">
                <Magnetic strength={12}>
                  <Link
                    href="/#how-it-works"
                    className="btn-shine inline-flex items-center gap-2 rounded-full bg-primary px-7 py-3 text-sm font-semibold text-primary-foreground transition-all hover:-translate-y-0.5 hover:shadow-lg"
                  >
                    Meet Novi
                    <ArrowUpRight className="size-4" />
                  </Link>
                </Magnetic>
                <Magnetic strength={12}>
                  <Link
                    href="#dashboard-preview"
                    className="group inline-flex items-center gap-2 rounded-full border border-border-soft px-7 py-3 text-sm font-semibold text-muted transition-colors hover:border-primary/50 hover:text-foreground"
                  >
                    Explore Student Dashboard
                    <ArrowUpRight className="size-4 transition-transform group-hover:translate-x-0.5 group-hover:-translate-y-0.5" />
                  </Link>
                </Magnetic>
              </div>
            </Reveal>

            <Reveal delay={0.28}>
              <div className="grid grid-cols-2 gap-3 pt-2">
                {perks.map((perk) => (
                  <span
                    key={perk}
                    className="flex items-center gap-2 text-xs font-medium text-muted"
                  >
                    <span className="size-1.5 rounded-full bg-accent" />
                    {perk}
                  </span>
                ))}
              </div>
            </Reveal>

            <Reveal delay={0.34}>
              <div className="flex gap-6 border-t border-border-soft pt-6">
                {stats.map((s) => (
                  <div key={s.label}>
                    <span className="font-display text-lg font-bold text-foreground">
                      {s.value}
                    </span>
                    <span className="block text-[10px] font-medium text-muted">
                      {s.label}
                    </span>
                  </div>
                ))}
              </div>
            </Reveal>
          </div>

          <Reveal delay={0.15} className="lg:col-span-7">
            <div className="relative">
              <div className="relative rounded-3xl border border-border-soft bg-surface p-6 shadow-2xl">
                <div className="pointer-events-none absolute inset-0 rounded-3xl bg-gradient-to-br from-primary/5 to-accent/5" />

                <div className="relative z-10">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <div className="grid size-10 place-items-center rounded-full bg-gradient-to-br from-primary to-accent text-sm font-bold text-primary-foreground">
                        R
                      </div>
                      <div>
                        <p className="text-sm font-bold">Riya Sharma</p>
                        <p className="text-[10px] text-muted">Grade 11 • Target CS 2027</p>
                      </div>
                    </div>
                    <span className="rounded-full border border-emerald-500/20 bg-emerald-500/10 px-3 py-1 text-[10px] font-bold text-emerald-400">
                      On Track
                    </span>
                  </div>

                  <div className="mt-6 grid grid-cols-3 gap-3">
                    {[
                      { label: "Profile Strength", value: "78%", delta: "+5%" },
                      { label: "University Readiness", value: "71%", delta: "+3%" },
                      { label: "Career Direction", value: "On Track", delta: "" },
                    ].map((m) => (
                      <div
                        key={m.label}
                        className="rounded-xl border border-border-soft bg-background/40 p-3"
                      >
                        <span className="block text-[9px] font-bold uppercase tracking-wider text-muted">
                          {m.label}
                        </span>
                        <span className="mt-1 block font-display text-lg font-bold text-primary">
                          {m.value}
                        </span>
                        {m.delta && (
                          <span className="text-[10px] font-semibold text-emerald-400">
                            {m.delta}
                          </span>
                        )}
                      </div>
                    ))}
                  </div>

                  <div className="mt-5">
                    <div className="flex items-center justify-between text-xs font-semibold text-muted">
                      <span>Roadmap Progress</span>
                      <span className="text-primary">68%</span>
                    </div>
                    <div className="mt-2 h-2 w-full overflow-hidden rounded-full bg-border-soft">
                      <motion.div
                        initial={{ width: 0 }}
                        whileInView={{ width: "68%" }}
                        viewport={{ once: true }}
                        transition={{ duration: 1.2, ease: "easeOut" }}
                        className="h-full rounded-full bg-gradient-to-r from-primary to-accent"
                      />
                    </div>
                  </div>

                  <div className="mt-5 space-y-2">
                    <p className="text-[10px] font-bold uppercase tracking-wider text-muted">
                      Today&apos;s Mission
                    </p>
                    {[
                      { text: "Complete Career DNA Quiz", done: true },
                      { text: "Update project portfolio", done: true },
                      { text: "Research Stanford CS program", done: true },
                      { text: "Draft personal statement outline", done: false },
                    ].map((t) => (
                      <div
                        key={t.text}
                        className="flex items-center gap-2 rounded-lg border border-border-soft bg-background/30 px-3 py-2"
                      >
                        <span
                          className={`size-4 rounded-full border-2 ${
                            t.done
                              ? "border-emerald-400 bg-emerald-400/20"
                              : "border-border-soft"
                          }`}
                        >
                          {t.done && (
                            <span className="flex size-full items-center justify-center text-[8px] text-emerald-400">
                              ✓
                            </span>
                          )}
                        </span>
                        <span
                          className={`text-xs ${
                            t.done ? "text-muted line-through" : "text-foreground"
                          }`}
                        >
                          {t.text}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              <div className="absolute -right-6 -bottom-6 z-20 hidden sm:block">
                <div className="relative size-80">
                  <Image
                    src="/student-mascot-girl.png"
                    alt="Student mascot"
                    fill
                    className="object-contain drop-shadow-2xl"
                  />
                </div>
              </div>
            </div>
          </Reveal>
        </div>
      </div>
    </section>
  );
}
