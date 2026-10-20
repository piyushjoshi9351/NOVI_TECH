"use client";

import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import {
  ArrowLeft,
  ArrowRight,
  ArrowUpRight,
  CheckCircle2,
  ShieldCheck,
  TrendingUp,
} from "lucide-react";
import Reveal from "@/components/ui/Reveal";
import TiltCard from "@/components/ui/TiltCard";

const testimonials = [
  {
    quote:
      "Novi helped my son discover high-impact CS research tracks we had no idea existed. His confidence skyrocketed.",
    author: "Aarav Sharma",
    role: "Parent of Grade 11 Student",
    metric: "Stanford Applicant",
  },
  {
    quote:
      "I used to constantly check up on deadlines. Now I just open Novi once a week to see green checkmarks. Complete peace of mind.",
    author: "Priya Menon",
    role: "Parent of Grade 12 Student",
    metric: "100% On-Track",
  },
  {
    quote:
      "The clarity Novi provides to families makes our counseling sessions 10x more productive and goal-oriented.",
    author: "Dr. Marcus Vance",
    role: "Director of College Counseling",
    metric: "Partner School",
  },
];

const focusGoals = [
  { title: "AI Research Paper Draft", status: "In Progress", category: "Academic" },
  { title: "Competitive Algorithmic Training", status: "Completed", category: "Skills" },
  { title: "SAT Mathematics Refinement", status: "Scheduled", category: "Testing" },
];

function StatsCard({
  label,
  value,
  delta,
  accent,
}: {
  label: string;
  value: string;
  delta?: string;
  accent: string;
}) {
  const numeric = parseInt(value, 10);
  return (
    <div className="space-y-2 rounded-2xl border border-border-soft bg-background/40 p-4">
      <span className="block text-[10px] font-bold uppercase tracking-wider text-muted">
        {label}
      </span>
      <div className="flex items-baseline justify-between">
        <span className="font-display text-2xl font-bold text-primary">
          {value}
          <span className="text-sm text-muted">%</span>
        </span>
        {delta && (
          <span className="text-[10px] font-semibold text-emerald-400">
            {delta}
          </span>
        )}
      </div>
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-border-soft">
        <motion.div
          initial={{ width: 0 }}
          whileInView={{ width: `${numeric}%` }}
          viewport={{ once: true }}
          transition={{ duration: 1.2, ease: "easeOut", delay: 0.3 }}
          className={`h-full rounded-full bg-gradient-to-r ${accent}`}
        />
      </div>
    </div>
  );
}

export default function ForParents() {
  const [testimonialIndex, setTestimonialIndex] = useState(0);
  const active = testimonials[testimonialIndex];

  return (
    <section id="for-parents" className="relative overflow-hidden py-24">
      <div className="orb top-1/3 -right-24 size-[28rem] bg-accent/20" />
      <div className="orb bottom-0 -left-24 size-[28rem] bg-primary/20" />

      <div className="relative mx-auto max-w-7xl px-6">
        <div className="grid items-center gap-12 lg:grid-cols-12">
          <div className="space-y-6 lg:col-span-7">
            <Reveal>
              <span className="inline-flex items-center gap-2 rounded-full border border-cyan-500/20 bg-cyan-500/10 px-4 py-1.5 text-xs font-semibold uppercase tracking-wide text-cyan-400">
                <ShieldCheck className="size-4" /> Parent Guidance System
              </span>
            </Reveal>

            <Reveal delay={0.08}>
              <h2 className="font-display text-4xl font-bold leading-[1.08] tracking-tight sm:text-5xl lg:text-6xl">
                Be their guide,{" "}
                <span className="animate-gradient bg-gradient-to-r from-cyan-400 to-teal-300 bg-clip-text text-transparent">
                  not their decision-maker.
                </span>
              </h2>
            </Reveal>

            <Reveal delay={0.16}>
              <p className="max-w-xl text-lg leading-relaxed text-muted">
                Your child doesn&apos;t need you to have every answer. They need you to help them ask the right questions. Novi helps you explore changing career opportunities together and support more informed decisions.
              </p>
            </Reveal>

            <Reveal delay={0.22}>
              <a
                href="/for-parents"
                className="group btn-shine inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-indigo-600 to-primary px-6 py-3.5 text-sm font-semibold text-white shadow-xl transition-all hover:-translate-y-0.5 hover:from-indigo-500 hover:to-primary/90"
              >
                Discover Novi for parents
                <ArrowUpRight className="size-4 transition-transform group-hover:translate-x-0.5 group-hover:-translate-y-0.5" />
              </a>
            </Reveal>
          </div>

          <Reveal delay={0.12} className="lg:col-span-5">
            <TiltCard
              className="rounded-3xl border border-border-soft bg-surface p-6 shadow-2xl sm:p-8"
              glow="rgba(99, 102, 241, 0.2)"
            >
              <div className="mb-6 flex items-center justify-between border-b border-border-soft pb-6">
                <div className="flex items-center gap-3.5">
                  <div className="grid size-12 place-items-center rounded-2xl bg-gradient-to-br from-indigo-500 to-primary font-display text-lg font-bold text-white shadow-lg">
                    R
                  </div>
                  <div>
                    <h3 className="font-display text-lg font-bold leading-snug">
                      Riya&apos;s Profile Hub
                    </h3>
                    <p className="text-xs font-medium text-muted">
                      Grade 11 • Target CS 2027
                    </p>
                  </div>
                </div>
                <span className="flex items-center gap-1 rounded-full border border-emerald-500/20 bg-emerald-500/10 px-3 py-1 text-xs font-semibold text-emerald-400">
                  <TrendingUp className="size-3.5" /> On Track
                </span>
              </div>

              <div className="mb-6 grid grid-cols-2 gap-4">
                <StatsCard
                  label="Profile Strength"
                  value="78"
                  delta="+4% this wk"
                  accent="from-primary to-primary-light"
                />
                <StatsCard
                  label="Uni Readiness"
                  value="71"
                  delta="On Schedule"
                  accent="from-accent to-cyan-400"
                />
              </div>

              <div className="space-y-3">
                <p className="text-xs font-semibold uppercase tracking-wider text-muted">
                  Active Monthly Objectives
                </p>
                {focusGoals.map((goal) => (
                  <motion.div
                    key={goal.title}
                    whileHover={{ x: 4 }}
                    transition={{ type: "spring", stiffness: 300, damping: 20 }}
                    className="flex items-center justify-between rounded-xl border border-border-soft bg-background/20 p-3.5 transition-colors hover:border-primary/30"
                  >
                    <div className="flex items-center gap-3">
                      <CheckCircle2
                        className={`size-4 ${
                          goal.status === "Completed"
                            ? "text-emerald-400"
                            : "text-primary"
                        }`}
                      />
                      <span className="text-xs font-medium">{goal.title}</span>
                    </div>
                    <span className="rounded bg-border-soft px-2 py-0.5 font-mono text-[10px] font-semibold text-muted">
                      {goal.category}
                    </span>
                  </motion.div>
                ))}
              </div>
            </TiltCard>
          </Reveal>
        </div>

        <div className="mt-28 text-center">
          <Reveal>
            <h3 className="font-display text-3xl font-bold sm:text-4xl">
              Trusted by students, loved by parents, preferred by schools.
            </h3>
          </Reveal>

          <Reveal delay={0.1}>
            <div className="relative mx-auto mt-12 max-w-2xl">
              <div className="relative min-h-[260px] overflow-hidden rounded-3xl border border-border-soft bg-surface p-8 shadow-2xl">
                <div className="pointer-events-none absolute top-0 left-1/2 h-32 w-2/3 -translate-x-1/2 bg-gradient-to-b from-indigo-500/20 to-transparent blur-2xl" />
                <AnimatePresence mode="wait">
                  <motion.blockquote
                    key={testimonialIndex}
                    initial={{ opacity: 0, x: 40 }}
                    animate={{ opacity: 1, x: 0 }}
                    exit={{ opacity: 0, x: -40 }}
                    transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
                  >
                    <span className="block font-serif text-6xl leading-none text-primary/30">
                      “
                    </span>
                    <p className="mt-2 pb-8 leading-relaxed text-foreground/85">
                      {active.quote}
                    </p>
                    <div className="flex flex-col items-start justify-between gap-4 border-t border-border-soft pt-6 text-left sm:flex-row sm:items-center">
                      <div>
                        <p className="text-sm font-bold text-foreground/90">
                          - {active.author}
                        </p>
                        <p className="mt-1 text-xs text-muted">{active.role}</p>
                      </div>
                      <span className="rounded-full border border-indigo-500/30 bg-indigo-500/10 px-2.5 py-1 text-[10px] font-bold text-indigo-400">
                        {active.metric}
                      </span>
                    </div>
                  </motion.blockquote>
                </AnimatePresence>
              </div>
            </div>
          </Reveal>

          <Reveal delay={0.15}>
            <div className="mt-8 flex items-center justify-center gap-6">
              <motion.button
                whileHover={{ scale: 1.1 }}
                whileTap={{ scale: 0.9 }}
                type="button"
                onClick={() =>
                  setTestimonialIndex(
                    (prev) => (prev - 1 + testimonials.length) % testimonials.length
                  )
                }
                className="group grid size-12 place-items-center rounded-full border border-indigo-500/30 text-indigo-400 transition-colors hover:bg-indigo-500 hover:text-white"
                aria-label="Previous testimonial"
              >
                <ArrowLeft className="size-5 transition-transform group-hover:-translate-x-0.5" />
              </motion.button>

              <div className="flex gap-2">
                {testimonials.map((_, idx) => (
                  <button
                    key={idx}
                    type="button"
                    onClick={() => setTestimonialIndex(idx)}
                    className={`h-2 rounded-full transition-all duration-500 ${
                      idx === testimonialIndex
                        ? "w-8 bg-indigo-400"
                        : "w-2 bg-border-soft hover:bg-indigo-400/40"
                    }`}
                    aria-label={`Testimonial ${idx + 1}`}
                  />
                ))}
              </div>

              <motion.button
                whileHover={{ scale: 1.1 }}
                whileTap={{ scale: 0.9 }}
                type="button"
                onClick={() =>
                  setTestimonialIndex(
                    (prev) => (prev + 1) % testimonials.length
                  )
                }
                className="group grid size-12 place-items-center rounded-full border border-indigo-500/30 text-indigo-400 transition-colors hover:bg-indigo-500 hover:text-white"
                aria-label="Next testimonial"
              >
                <ArrowRight className="size-5 transition-transform group-hover:translate-x-0.5" />
              </motion.button>
            </div>
          </Reveal>
        </div>
      </div>
    </section>
  );
}
