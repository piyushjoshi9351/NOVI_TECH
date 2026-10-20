"use client";

import Link from "next/link";
import Image from "next/image";
import { ArrowUpRight, CheckCircle2, Sparkles } from "lucide-react";
import Reveal from "@/components/ui/Reveal";
import Magnetic from "@/components/ui/Magnetic";

const benefits = [
  "Real-time progress visibility",
  "AI-powered parent insights",
  "Stay involved, not in control",
];

export default function ParentsHero() {
  return (
    <section className="relative overflow-hidden pt-32 pb-24">
      <div className="orb -top-32 -right-32 size-[30rem] bg-accent/10" />
      <div className="orb bottom-0 -left-32 size-[32rem] bg-primary/20" />

      <div className="relative mx-auto max-w-7xl px-6">
        <div className="grid items-center gap-12 lg:grid-cols-12">
          <div className="space-y-7 lg:col-span-5">
            <Reveal>
              <span className="inline-flex items-center gap-2 rounded-full border border-accent/20 bg-accent/10 px-4 py-1.5 text-xs font-bold uppercase tracking-widest text-accent">
                <Sparkles className="size-3.5" /> Parent Guidance
              </span>
            </Reveal>

            <Reveal delay={0.08}>
              <h1 className="font-display text-4xl font-bold leading-[1.08] tracking-tight sm:text-5xl lg:text-6xl">
                Their future is theirs to discover.{" "}
                <span className="text-gradient">You can help them prepare for it.</span>
              </h1>
            </Reveal>

            <Reveal delay={0.16}>
              <p className="max-w-lg text-lg leading-relaxed text-muted">
                As a parent, you want your child to have the best possible future. But with careers evolving and university choices becoming increasingly complex, knowing how to guide them isn&apos;t always easy. Novi helps make that journey more structured, personal and informed.
              </p>
            </Reveal>

            <Reveal delay={0.22}>
              <div className="flex flex-wrap gap-3">
                <Magnetic strength={12}>
                  <Link
                    href="#value-grid"
                    className="btn-shine inline-flex items-center gap-2 rounded-full bg-primary px-7 py-3 text-sm font-semibold text-primary-foreground transition-all hover:-translate-y-0.5 hover:shadow-lg"
                  >
                    See How It Works
                    <ArrowUpRight className="size-4" />
                  </Link>
                </Magnetic>
                <Magnetic strength={12}>
                  <Link
                    href="/for-students"
                    className="inline-flex items-center gap-2 rounded-full border border-border-soft px-7 py-3 text-sm font-semibold text-muted transition-colors hover:border-primary/50 hover:text-foreground"
                  >
                    Student View
                  </Link>
                </Magnetic>
              </div>
            </Reveal>

            <Reveal delay={0.28}>
              <div className="flex flex-col gap-2.5 pt-2">
                {benefits.map((b) => (
                  <span
                    key={b}
                    className="flex items-center gap-2.5 text-sm text-foreground/80"
                  >
                    <CheckCircle2 className="size-4 shrink-0 text-accent" />
                    {b}
                  </span>
                ))}
              </div>
            </Reveal>
          </div>

          <Reveal delay={0.15} className="lg:col-span-7">
            <div className="relative">
              <div className="relative rounded-3xl border border-border-soft bg-surface p-6 shadow-2xl">
                <div className="pointer-events-none absolute inset-0 rounded-3xl bg-gradient-to-br from-accent/5 to-primary/5" />

                <div className="relative z-10">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <div className="grid size-10 place-items-center overflow-hidden rounded-full">
                        <Image
                          src="/riya-avatar.jpg"
                          alt="Riya"
                          width={40}
                          height={40}
                          className="size-full object-cover"
                        />
                      </div>
                      <div>
                        <p className="text-sm font-bold">Parent Dashboard</p>
                        <p className="text-[10px] text-muted">Riya · Grade 11 · Target CS 2027</p>
                      </div>
                    </div>
                    <span className="rounded-full border border-accent/20 bg-accent/10 px-3 py-1 text-[10px] font-bold text-accent">
                      On Track
                    </span>
                  </div>

                  <div className="mt-5 grid grid-cols-3 gap-3">
                    {[
                      { label: "Monthly Focus", value: "80%", desc: "Research project" },
                      { label: "Weekly Activity", value: "12", desc: "Tasks completed" },
                      { label: "Next Milestone", value: "5d", desc: "SAT practice test" },
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
                        <span className="text-[10px] text-muted">
                          {m.desc}
                        </span>
                      </div>
                    ))}
                  </div>

                  <div className="mt-5 rounded-xl border border-border-soft bg-background/40 p-3">
                    <div className="flex items-center justify-between text-xs font-semibold text-muted">
                      <span>Overall Progress</span>
                      <span className="text-primary">74%</span>
                    </div>
                    <div className="mt-2 h-2 w-full overflow-hidden rounded-full bg-border-soft">
                      <div
                        className="h-full w-[74%] rounded-full bg-gradient-to-r from-primary to-accent"
                      />
                    </div>
                  </div>

                  <div className="mt-4 space-y-2">
                    <p className="text-[10px] font-bold uppercase tracking-wider text-muted">
                      This Week&apos;s Activity
                    </p>
                    {[
                      { text: "Completed Career DNA Quiz", done: true },
                      { text: "Updated project portfolio", done: true },
                      { text: "Researched Stanford CS program", done: true },
                      { text: "Draft personal statement", done: false },
                    ].map((t) => (
                      <div
                        key={t.text}
                        className="flex items-center gap-2 rounded-lg border border-border-soft bg-background/30 px-3 py-2"
                      >
                        <span
                          className={`size-4 rounded-full border-2 ${
                            t.done
                              ? "border-accent bg-accent/20"
                              : "border-border-soft"
                          }`}
                        >
                          {t.done && (
                            <span className="flex size-full items-center justify-center text-[8px] text-accent">
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
                    src="/parents-daughter-tablet.png"
                    alt="Parent and daughter"
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
