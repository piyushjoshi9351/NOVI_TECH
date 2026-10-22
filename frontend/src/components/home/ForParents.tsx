"use client";

import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  ArrowUpRight,
  CheckCircle2,
  ShieldCheck,
  TrendingUp,
  Star,
  ArrowRight,
} from "lucide-react";
import Link from "next/link";
import Reveal from "@/components/ui/Reveal";
import TiltCard from "@/components/ui/TiltCard";

// --- Data ---

const focusGoals = [
  { title: "AI Research Paper Draft", status: "In Progress", category: "Academic" },
  { title: "Competitive Algorithmic Training", status: "Completed", category: "Skills" },
  { title: "SAT Mathematics Refinement", status: "Scheduled", category: "Testing" },
];

const testimonials = [
  {
    quote:
      "Novi helped me understand what my child actually needs, without turning every conversation into a discussion.",
    name: "Arjun",
    role: "Parent",
  },
  {
    quote:
      "The monthly insights from Novi are incredibly helpful. We know how to support, not what to push.",
    name: "Meera",
    role: "Parent",
  },
  {
    quote:
      "Finally a platform that keeps us informed but gives our child the space to explore and grow.",
    name: "Priya",
    role: "Parent",
  },
];

const schools = [
  { initials: "SX", name: "St. Xavier's", location: "Mumbai" },
  { initials: "VV", name: "Vasant Valley", location: "New Delhi" },
  { initials: "DPS", name: "DPS", location: "Delhi Public School" },
  { initials: "OIS", name: "Oakridge", location: "International School" },
  { initials: "PWS", name: "Pathways", location: "World School" },
  { initials: "TIS", name: "The International", location: "Bangalore" },
  { initials: "BIS", name: "Bishop's", location: "Pune" },
  { initials: "RVS", name: "Rishi Valley", location: "Andhra Pradesh" },
  { initials: "CIS", name: "CIS", location: "Chennai" },
  { initials: "HIS", name: "Harrow", location: "Bangalore" },
  { initials: "AIS", name: "American Embassy", location: "New Delhi" },
  { initials: "BMS", name: "Bombay Scottish", location: "Mumbai" },
  { initials: "MIS", name: "Mayo College", location: "Ajmer" },
  { initials: "WIS", name: "Woodstock", location: "Mussoorie" },
  { initials: "GDS", name: "Good Shepherd", location: "Ooty" },
  { initials: "DPS", name: "DPS Bangalore", location: "Bangalore" },
];

// --- Components ---

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
    <div className="space-y-2 rounded-2xl border border-white/10 bg-surface/40 backdrop-blur-sm p-4">
      <span className="block text-[10px] font-bold uppercase tracking-wider text-foreground/40">
        {label}
      </span>
      <div className="flex items-baseline justify-between">
        <span className="font-display text-2xl font-bold text-foreground">
          {value}
          <span className="text-sm text-foreground/40">%</span>
        </span>
        {delta && (
          <span className="text-[10px] font-semibold text-blue-400">
            {delta}
          </span>
        )}
      </div>
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-white/10">
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
  const [activeTestimonial, setActiveTestimonial] = useState(0);

  // Auto-play logic from the Testimonial file
  useEffect(() => {
    const interval = setInterval(() => {
      setActiveTestimonial((prev) => (prev + 1) % testimonials.length);
    }, 3500);
    return () => clearInterval(interval);
  }, []);

  const marqueeSchools = [...schools, ...schools];

  return (
    <section id="for-parents" className="relative overflow-hidden py-16 sm:py-24 px-6">
      {/* Theme-matched glow orbs - Updated to Blue/Indigo */}
      <div className="absolute inset-0 pointer-events-none">
        <div className="absolute top-1/3 -right-24 w-[28rem] h-[28rem] bg-blue-500/10 rounded-full blur-3xl" />
        <div className="absolute bottom-0 -left-24 w-[28rem] h-[28rem] bg-indigo-500/10 rounded-full blur-3xl" />
      </div>

      <div className="relative mx-auto max-w-7xl z-10">
        
        {/* ====== TOP SECTION: Parents Guide ====== */}
        <div className="grid items-center gap-12 lg:grid-cols-12 mb-24">
          <div className="space-y-6 lg:col-span-7">
            <Reveal>
              <motion.span
                initial={{ opacity: 0, scale: 0.5 }}
                whileInView={{ opacity: 1, scale: 1 }}
                viewport={{ once: true }}
                transition={{ delay: 0.2, type: "spring", stiffness: 200 }}
                className="inline-flex items-center gap-2 rounded-full border border-blue-500/20 bg-blue-500/10 px-4 py-1.5 text-xs font-bold uppercase tracking-[0.18em] text-blue-400"
              >
                <ShieldCheck className="size-4" /> Parent Guidance System
              </motion.span>
            </Reveal>

            <Reveal delay={0.08}>
              <motion.h2
                initial={{ opacity: 0, y: 40, scale: 0.85 }}
                whileInView={{ opacity: 1, y: 0, scale: 1 }}
                viewport={{ once: true }}
                transition={{ delay: 0.15, duration: 0.8, type: "spring", stiffness: 80, damping: 12 }}
                className="font-display text-4xl font-bold leading-[1.05] tracking-tight sm:text-5xl lg:text-6xl"
              >
                Be their guide,{" "}
                <span className="bg-gradient-to-r from-blue-400 via-indigo-400 to-purple-400 bg-clip-text text-transparent inline-block">
                  not their decision-maker.
                </span>
              </motion.h2>
            </Reveal>

            <Reveal delay={0.16}>
              <motion.p
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: 0.3, duration: 0.6 }}
                className="max-w-xl text-lg leading-relaxed text-foreground/50"
              >
                Your child doesn&apos;t need you to have every answer. They need you to help them ask the right questions. Novi helps you explore changing career opportunities together and support more informed decisions.
              </motion.p>
            </Reveal>

            <Reveal delay={0.22}>
              <a
                href="/for-parents"
                className="group relative inline-flex items-center gap-2 overflow-hidden rounded-xl bg-gradient-to-r from-blue-600 to-indigo-600 px-6 py-3.5 text-sm font-semibold text-white shadow-xl transition-all duration-300 hover:-translate-y-0.5 hover:shadow-blue-500/30 hover:shadow-2xl"
              >
                <span className="absolute inset-0 -translate-x-full bg-gradient-to-r from-transparent via-white/20 to-transparent transition-transform duration-700 group-hover:translate-x-full" />
                <span className="relative z-10">Discover Novi for parents</span>
                <ArrowUpRight className="relative z-10 size-4 transition-transform group-hover:translate-x-0.5 group-hover:-translate-y-0.5" />
              </a>
            </Reveal>
          </div>

          <Reveal delay={0.12} className="lg:col-span-5">
            <TiltCard
              className="rounded-3xl border border-white/10 bg-surface/60 backdrop-blur-sm p-6 shadow-2xl sm:p-8"
              glow="rgba(59, 130, 246, 0.2)" // Updated to Blue glow
            >
              <div className="mb-6 flex items-center justify-between border-b border-white/10 pb-6">
                <div className="flex items-center gap-3.5">
                  <div className="grid size-12 place-items-center rounded-2xl bg-gradient-to-br from-blue-500 to-indigo-500 font-display text-lg font-bold text-white shadow-lg">
                    R
                  </div>
                  <div>
                    <h3 className="font-display text-lg font-bold leading-snug">
                      Riya&apos;s Profile Hub
                    </h3>
                    <p className="text-xs font-medium text-foreground/40">
                      Grade 11 • Target CS 2027
                    </p>
                  </div>
                </div>
                <span className="flex items-center gap-1 rounded-full border border-blue-500/20 bg-blue-500/10 px-3 py-1 text-xs font-semibold text-blue-400">
                  <TrendingUp className="size-3.5" /> On Track
                </span>
              </div>

              <div className="mb-6 grid grid-cols-2 gap-4">
                <StatsCard
                  label="Profile Strength"
                  value="78"
                  delta="+4% this wk"
                  accent="from-blue-400 to-indigo-400"
                />
                <StatsCard
                  label="Uni Readiness"
                  value="71"
                  delta="On Schedule"
                  accent="from-sky-400 to-blue-500"
                />
              </div>

              <div className="space-y-3">
                <p className="text-xs font-semibold uppercase tracking-wider text-foreground/40">
                  Active Monthly Objectives
                </p>
                {focusGoals.map((goal) => (
                  <motion.div
                    key={goal.title}
                    whileHover={{ x: 4 }}
                    transition={{ type: "spring", stiffness: 300, damping: 20 }}
                    className="flex items-center justify-between rounded-xl border border-white/10 bg-background/20 p-3.5 transition-colors hover:border-blue-500/40"
                  >
                    <div className="flex items-center gap-3">
                      <CheckCircle2
                        className={`size-4 ${
                          goal.status === "Completed"
                            ? "text-blue-400"
                            : "text-indigo-400"
                        }`}
                      />
                      <span className="text-xs font-medium">{goal.title}</span>
                    </div>
                    <span className="rounded bg-white/5 px-2 py-0.5 font-mono text-[10px] font-semibold text-foreground/40">
                      {goal.category}
                    </span>
                  </motion.div>
                ))}
              </div>
            </TiltCard>
          </Reveal>
        </div>

        {/* ====== BOTTOM SECTION: Complete Testimonials Integration ====== */}
        <div className="relative pt-16 pb-8 border-t border-white/10">
          <div className="absolute bottom-0 left-1/2 -translate-x-1/2 w-[800px] h-[400px] bg-blue-500/[0.04] rounded-full blur-[120px] pointer-events-none" />

          <div className="max-w-7xl mx-auto relative z-10">
            {/* Header */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, amount: 0.5 }}
              transition={{ duration: 0.6, ease: "easeOut" }}
              className="text-center mb-14"
            >
              <h2 className="text-4xl sm:text-5xl font-bold text-foreground mb-3">
                Loved by{" "}
                <span className="bg-gradient-to-r from-blue-400 to-indigo-400 bg-clip-text text-transparent">
                  parents.
                </span>{" "}
                Built for students.
              </h2>
              <p className="text-base text-foreground/50 max-w-2xl mx-auto">
                Real stories from the parents and students building their futures with Novi.
              </p>
            </motion.div>

            {/* 3D Cards Carousel */}
            <div className="relative w-full max-w-5xl mx-auto h-[280px] flex items-center justify-center perspective-1000">
              <div className="relative w-full h-full flex items-center justify-center">
                <AnimatePresence mode="popLayout">
                  {testimonials.map((t, idx) => {
                    const offset = (idx - activeTestimonial + testimonials.length) % testimonials.length;
                    const position = offset === 0 ? 0 : offset === 1 ? 1 : -1;
                    const isActive = position === 0;

                    return (
                      <motion.div
                        key={idx}
                        className="absolute w-full max-w-md"
                        initial={{ opacity: 0, x: position * 220, scale: 0.7, y: 15, zIndex: 0 }}
                        animate={{
                          opacity: isActive ? 1 : 0.95,
                          x: position * 260,
                          scale: isActive ? 1 : 0.75,
                          y: isActive ? 0 : 15,
                          zIndex: isActive ? 10 : 0,
                          rotateY: position * -18,
                          filter: isActive ? "blur(0px)" : "blur(0.8px)",
                        }}
                        exit={{ opacity: 0, x: position * -220, scale: 0.7, y: 15, zIndex: 0 }}
                        transition={{ type: "spring", stiffness: 200, damping: 25 }}
                        style={{ transformStyle: "preserve-3d" }}
                      >
                        <div
                          className={`relative rounded-3xl border bg-background/80 backdrop-blur-xl pt-12 pb-7 px-7 overflow-hidden transition-all duration-500 ${
                            isActive
                              ? "border-blue-500/60 shadow-[0_0_40px_-8px_rgba(59,130,246,0.4)] dark:shadow-[0_0_50px_-8px_rgba(59,130,246,0.5)]"
                              : "border-white/20 dark:border-white/10 shadow-[0_20px_50px_rgba(0,0,0,0.1)] dark:shadow-[0_20px_50px_rgba(0,0,0,0.3)]"
                          }`}
                        >
                          {isActive && (
                            <div className="absolute top-0 left-8 right-8 h-px bg-gradient-to-r from-transparent via-blue-400 to-transparent" />
                          )}
                          <span className="absolute top-2 left-5 text-[90px] font-serif leading-none text-blue-500/20 dark:text-blue-500/30 select-none pointer-events-none">
                            &ldquo;
                          </span>
                          <p className="relative text-foreground/85 text-[15px] leading-[1.7] tracking-[-0.01em] mb-6 min-h-[80px] text-left">
                            {t.quote}
                          </p>
                          <div className="relative flex items-center gap-3 pt-4 border-t border-white/10">
                            <div className="w-10 h-10 rounded-full bg-gradient-to-br from-blue-400 to-indigo-500 flex items-center justify-center text-white text-sm font-bold shrink-0 shadow-md shadow-blue-500/20">
                              {t.name.charAt(0)}
                            </div>
                            <div className="min-w-0 text-left flex-1">
                              <div className="flex items-center gap-2 flex-wrap">
                                <p className="text-sm font-bold text-foreground truncate">
                                  {t.name}
                                </p>
                                <span className="text-[9px] font-bold uppercase tracking-wider text-blue-400 bg-blue-500/10 border border-blue-500/20 rounded-full px-2 py-0.5">
                                  Verified
                                </span>
                              </div>
                              <p className="text-[11px] text-foreground/50 truncate uppercase tracking-wider">
                                {t.role}
                              </p>
                            </div>
                          </div>
                        </div>
                      </motion.div>
                    );
                  })}
                </AnimatePresence>
              </div>
            </div>

            {/* Rating & Schools Marquee */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, amount: 0.3 }}
              transition={{ duration: 0.6, ease: "easeOut" }}
              className="mt-14 pt-8 border-t border-white/10"
            >
              <div className="flex flex-col lg:flex-row items-center gap-8 lg:gap-12">
                <div className="shrink-0 w-full lg:w-auto">
                  <div className="rounded-2xl border border-white/10 bg-white/[0.02] dark:bg-white/[0.03] px-6 py-5 text-center lg:text-left">
                    <div className="flex items-center justify-center lg:justify-start gap-3 mb-2">
                      <span className="text-4xl font-bold text-foreground">4.9/5</span>
                      <div className="flex items-center gap-1">
                        {[...Array(5)].map((_, i) => (
                          <Star key={i} className="w-5 h-5 text-yellow-400 fill-current" />
                        ))}
                      </div>
                    </div>
                    <p className="text-sm text-foreground/60">Average rating from 10,000+ students</p>
                  </div>
                </div>
                <div className="hidden lg:block w-px h-16 bg-white/10" />
                <div className="flex-1 w-full min-w-0">
                  <p className="text-[11px] font-bold uppercase tracking-widest text-foreground/40 mb-4">
                    Trusted by leading schools
                  </p>

                  <div className="relative overflow-hidden">
                    <div className="absolute left-0 top-0 bottom-0 w-16 z-10 bg-gradient-to-r from-background to-transparent pointer-events-none" />
                    <div className="absolute right-0 top-0 bottom-0 w-16 z-10 bg-gradient-to-l from-background to-transparent pointer-events-none" />

                    <div className="flex gap-4 animate-marquee-right hover:[animation-play-state:paused]">
                      {marqueeSchools.map((school, idx) => (
                        <div
                          key={idx}
                          className="shrink-0 flex items-center gap-3 rounded-2xl border border-white/10 bg-white/[0.02] dark:bg-white/[0.03] px-4 py-3 min-w-[200px] hover:border-blue-500/30 transition-colors"
                        >
                          <div className="w-10 h-10 rounded-xl bg-white/[0.05] flex items-center justify-center shrink-0">
                            <span className="text-[11px] font-bold tracking-wider text-foreground/70">
                              {school.initials}
                            </span>
                          </div>
                          <div className="min-w-0">
                            <p className="text-sm font-bold text-foreground truncate">
                              {school.name}
                            </p>
                            <p className="text-[11px] text-foreground/50 truncate">
                              {school.location}
                            </p>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            </motion.div>

            {/* CTA Button */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, amount: 0.5 }}
              transition={{ duration: 0.6, delay: 0.2, ease: "easeOut" }}
              className="mt-12 text-center"
            >
              <Link
                href="/signup"
                className="inline-flex items-center gap-2 px-7 py-3.5 rounded-2xl bg-gradient-to-r from-blue-600 to-indigo-600 hover:opacity-95 text-white font-bold text-sm transition-all duration-300 shadow-lg shadow-blue-500/30 hover:scale-[1.02] group"
              >
                Join 10,000+ students
                <ArrowRight className="w-4 h-4 transition-transform duration-300 group-hover:translate-x-1" />
              </Link>
            </motion.div>

          </div>
        </div>
      </div>
    </section>
  );
}