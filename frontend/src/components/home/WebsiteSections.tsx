'use client'
import { useState, useRef } from 'react'
import { motion, useScroll, useTransform, AnimatePresence } from 'framer-motion'
import Reveal from "@/components/ui/Reveal";

const problems = [
  "Too many career possibilities, and no clear starting point.",
  "Too much information about courses and universities, and too little personal guidance.",
  "Pressure to choose the “right” career before discovering what genuinely fits.",
  "Parents trying to help, often without knowing how careers and opportunities are evolving.",
];

const journey = [
  {
    title: "01. Discover your Career DNA",
    description: "Understand your interests, strengths, favourite subjects, activities, ambitions and what matters to you through a guided conversation.",
    icon: "✦",
    color: "from-emerald-400 to-teal-400",
    borderColor: "border-emerald-500/50",
    glowColor: "rgba(16,185,129,0.3)",
  },
  {
    title: "02. Explore possibilities",
    description: "Discover careers that align with your unique profile, including options you may never have considered—and understand why they might suit you.",
    icon: "⌕",
    color: "from-blue-400 to-cyan-400",
    borderColor: "border-blue-500/50",
    glowColor: "rgba(59,130,246,0.3)",
  },
  {
    title: "03. Build your roadmap",
    description: "Get personalised next steps for the coming 12 months, from skills and projects to subject choices, courses and further exploration.",
    icon: "↗",
    color: "from-purple-400 to-pink-400",
    borderColor: "border-purple-500/50",
    glowColor: "rgba(168,85,247,0.3)",
  },
  {
    title: "04. Build your Career Passport",
    description: "Keep your evolving interests, skills, projects, achievements and aspirations in one place as your future takes shape.",
    icon: "◎",
    color: "from-orange-400 to-red-400",
    borderColor: "border-orange-500/50",
    glowColor: "rgba(251,146,60,0.3)",
  },
];

const benefits = [
  { title: "Know yourself", description: "Discover your interests, strengths and motivations.", icon: "✦" },
  { title: "Think beyond the obvious", description: "Explore emerging careers and new possibilities.", icon: "⌕" },
  { title: "Know your next step", description: "Turn big ambitions into manageable actions.", icon: "↗" },
  { title: "Build your story", description: "Bring together your skills, projects and achievements.", icon: "◎" },
];

const differences = [
  {
    traditional: "One-time career assessment",
    novi: "An evolving discovery journey",
    gradient: "from-emerald-400 to-teal-400",
    glow: "rgba(16,185,129,0.15)",
    border: "border-emerald-500/30",
    text: "text-emerald-400",
    bg: "bg-emerald-500/10"
  },
  {
    traditional: "Generic career lists",
    novi: "Personalised possibilities with explanations",
    gradient: "from-blue-400 to-cyan-400",
    glow: "rgba(59,130,246,0.15)",
    border: "border-blue-500/30",
    text: "text-blue-400",
    bg: "bg-blue-500/10"
  },
  {
    traditional: "Information without direction",
    novi: "Actionable next steps",
    gradient: "from-purple-400 to-fuchsia-400",
    glow: "rgba(168,85,247,0.15)",
    border: "border-purple-500/30",
    text: "text-purple-400",
    bg: "bg-purple-500/10"
  },
  {
    traditional: "Focus on a single career decision",
    novi: "Support across Grades 9–12",
    gradient: "from-orange-400 to-amber-400",
    glow: "rgba(251,146,60,0.15)",
    border: "border-orange-500/30",
    text: "text-orange-400",
    bg: "bg-orange-500/10"
  },
  {
    traditional: "Achievements scattered everywhere",
    novi: "A persistent Career Passport",
    gradient: "from-indigo-400 to-violet-400",
    glow: "rgba(99,102,241,0.15)",
    border: "border-indigo-500/30",
    text: "text-indigo-400",
    bg: "bg-indigo-500/10",
    span: "md:col-span-2" 
  },
];

/* Reusable animated section shell with the scroll fade + glow orb from the reference */
function SectionShell({ children, id, glow = "emerald" }: { children: React.ReactNode; id?: string; glow?: string }) {
  const ref = useRef<HTMLElement>(null);
  const { scrollYProgress } = useScroll({ target: ref, offset: ["start end", "end start"] });
  const opacity = useTransform(scrollYProgress, [0, 0.2, 0.8, 1], [0.5, 1, 1, 0.5]);
  const scale = useTransform(scrollYProgress, [0, 0.2, 0.8, 1], [0.96, 1, 1, 0.96]);
  const orbClass =
    glow === "emerald" ? "bg-emerald-500/5" : glow === "blue" ? "bg-blue-500/5" : glow === "purple" ? "bg-purple-500/5" : "bg-cyan-500/5";

  return (
    <section ref={ref} id={id} className="relative py-16 sm:py-24 px-6 overflow-hidden">
      <div className="absolute inset-0 pointer-events-none">
        <div className={`absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[400px] ${orbClass} rounded-full blur-3xl`} />
      </div>
      <motion.div style={{ opacity, scale }} className="max-w-7xl mx-auto relative z-10">
        {children}
      </motion.div>
    </section>
  );
}

/* Reusable eyebrow pill */
function Eyebrow({ children }: { children: React.ReactNode }) {
  return (
    <motion.span
      initial={{ opacity: 0, scale: 0.5 }}
      whileInView={{ opacity: 1, scale: 1 }}
      viewport={{ once: true }}
      transition={{ delay: 0.2, type: "spring", stiffness: 200 }}
      className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-[11px] font-bold uppercase tracking-[0.18em] mb-5"
    >
      <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
      {children}
    </motion.span>
  );
}

/* Reusable headline with the gradient word */
function Headline({ children }: { children: React.ReactNode }) {
  return (
    <motion.h2
      initial={{ opacity: 0, y: 40, scale: 0.85 }}
      whileInView={{ opacity: 1, y: 0, scale: 1 }}
      viewport={{ once: true }}
      transition={{ delay: 0.15, duration: 0.8, type: "spring", stiffness: 80, damping: 12 }}
      className="text-4xl sm:text-5xl lg:text-6xl font-bold leading-[1.05] tracking-tight"
    >
      {children}
    </motion.h2>
  );
}

/* ============ THE PROBLEM ============ */
export function TheProblem() {
  return (
    <SectionShell id="the-problem" glow="emerald">
      <div className="max-w-3xl mb-12">
        <Eyebrow>The Challenge</Eyebrow>
        <Headline>
          The world is changing.{" "}
          <span className="bg-gradient-to-r from-emerald-400 via-cyan-400 to-blue-400 bg-clip-text text-transparent">
            The way we plan for the future
          </span>{" "}
          should change too.
        </Headline>
        <motion.p
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ delay: 0.4, duration: 0.6 }}
          className="mt-6 max-w-2xl text-lg sm:text-xl text-foreground/50 leading-relaxed"
        >
          Students are asked to make important decisions about subjects, careers and universities before they fully understand their options.
        </motion.p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        {problems.map((problem, i) => (
          <motion.div
            key={problem}
            initial={{ opacity: 0, y: 40 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ delay: 0.1 * i, duration: 0.6, type: "spring", stiffness: 90 }}
            whileHover={{ y: -4 }}
            className="group relative overflow-hidden rounded-3xl border border-white/10 bg-surface/60 backdrop-blur-sm p-7 text-foreground/60 transition-all duration-500 hover:border-emerald-500/40 hover:bg-surface/80"
          >
            <div className="absolute top-0 right-0 w-32 h-32 rounded-full bg-emerald-500/10 blur-3xl opacity-0 group-hover:opacity-100 transition-opacity duration-500 pointer-events-none" />
            <div className="relative z-10 flex gap-4 items-start">
              <span className="w-8 h-8 shrink-0 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 flex items-center justify-center text-xs font-bold">
                {String(i + 1).padStart(2, "0")}
              </span>
              <p className="leading-relaxed">{problem}</p>
            </div>
          </motion.div>
        ))}
      </div>

      <motion.p
        initial={{ opacity: 0, y: 30 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true }}
        transition={{ delay: 0.4, duration: 0.6, type: "spring" }}
        className="mt-10 text-xl sm:text-2xl font-semibold bg-gradient-to-r from-emerald-400 via-cyan-400 to-blue-400 bg-clip-text text-transparent"
      >
        Novi turns confusion into clarity—and clarity into action.
      </motion.p>
    </SectionShell>
  );
}

/* ============ NOVI JOURNEY (interactive expand cards, like reference) ============ */
export function NoviJourney() {
  const [active, setActive] = useState(0);

  return (
    <SectionShell id="novi-journey" glow="blue">
      <div className="max-w-3xl mb-12">
        <Eyebrow>How Novi Works</Eyebrow>
        <Headline>
          A guided path from{" "}
          <span className="bg-gradient-to-r from-emerald-400 via-cyan-400 to-blue-400 bg-clip-text text-transparent">
            discovery to direction.
          </span>
        </Headline>
      </div>

      <div className="flex flex-col lg:flex-row gap-4 lg:items-stretch">
        {journey.map((step, index) => {
          const isActive = active === index;
          return (
            <motion.button
              key={step.title}
              type="button"
              onClick={() => setActive(index)}
              layout
              transition={{ type: "spring", stiffness: 200, damping: 25 }}
              className={`group relative overflow-hidden text-left rounded-3xl border transition-all duration-500 flex flex-col w-full lg:w-auto ${
                isActive
                  ? `lg:flex-[3] bg-surface/90 ${step.borderColor} shadow-2xl`
                  : `lg:flex-1 bg-surface/40 border-white/10 hover:border-white/20 opacity-70 lg:opacity-100 lg:hover:opacity-100`
              }`}
            >
              {isActive && (
                <div
                  className="absolute top-0 right-0 w-40 h-40 rounded-full blur-3xl opacity-20 pointer-events-none"
                  style={{ backgroundColor: step.glowColor }}
                />
              )}
              <div className="flex items-center gap-4 p-5 pb-0 relative z-10">
                <div
                  className={`w-12 h-12 rounded-2xl flex items-center justify-center text-lg font-bold shrink-0 transition-all duration-500 ${
                    isActive
                      ? `bg-gradient-to-r ${step.color} text-white`
                      : "bg-background border border-white/10 text-emerald-400"
                  }`}
                >
                  {step.icon}
                </div>
                <div className="min-w-0">
                  <h3
                    className={`text-lg font-bold truncate transition-colors ${
                      isActive ? "text-foreground" : "text-foreground/80 group-hover:text-emerald-400"
                    }`}
                  >
                    {step.title}
                  </h3>
                </div>
              </div>
              <div className="p-5 relative z-10">
                <AnimatePresence initial={false}>
                  {isActive ? (
                    <motion.p
                      key="desc"
                      initial={{ opacity: 0, height: 0 }}
                      animate={{ opacity: 1, height: "auto" }}
                      exit={{ opacity: 0, height: 0 }}
                      transition={{ duration: 0.45, ease: [0.22, 1, 0.36, 1] }}
                      className="overflow-hidden text-sm leading-relaxed text-foreground/70"
                    >
                      {step.description}
                    </motion.p>
                  ) : (
                    <p className="text-sm leading-relaxed text-foreground/45">
                      {step.description.split(" ").slice(0, 8).join(" ")}…
                    </p>
                  )}
                </AnimatePresence>
                <div
                  className={`mt-4 text-xs font-semibold flex items-center gap-1 transition-all duration-300 ${
                    isActive ? "text-emerald-400" : "text-foreground/30 group-hover:text-emerald-400"
                  }`}
                >
                  {isActive ? (
                    <motion.span
                      initial={{ opacity: 0, x: -5 }}
                      animate={{ opacity: 1, x: 0 }}
                      className="flex items-center gap-1"
                    >
                      <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                      Active stage
                    </motion.span>
                  ) : (
                    "View stage"
                  )}
                  <motion.span animate={{ x: isActive ? 3 : 0 }} className="transition-transform duration-300 group-hover:translate-x-1">
                    →
                  </motion.span>
                </div>
              </div>
            </motion.button>
          );
        })}
      </div>
    </SectionShell>
  );
}

/* ============ EVERYTHING STARTS WITH YOU ============ */
export function EverythingStartsWithYou() {
  return (
    <SectionShell id="starts-with-you" glow="purple">
      <div className="max-w-3xl mb-12">
        <Eyebrow>Built around you</Eyebrow>
        <Headline>
          Not another career test.{" "}
          <span className="bg-gradient-to-r from-purple-400 via-pink-400 to-emerald-400 bg-clip-text text-transparent">
            A better way to discover yourself.
          </span>
        </Headline>
        <motion.p
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ delay: 0.35, duration: 0.6 }}
          className="mt-6 max-w-2xl text-lg sm:text-xl text-foreground/50 leading-relaxed"
        >
          Novi doesn&apos;t believe that one test or one conversation can define your future. Your interests change. You discover new strengths. Your ambitions evolve. Novi grows with you.
        </motion.p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {benefits.map((benefit, i) => (
          <motion.div
            key={benefit.title}
            initial={{ opacity: 0, y: 50, scale: 0.9 }}
            whileInView={{ opacity: 1, y: 0, scale: 1 }}
            viewport={{ once: true }}
            transition={{ delay: i * 0.1, duration: 0.6, type: "spring", stiffness: 90, damping: 14 }}
            whileHover={{ y: -6, scale: 1.02 }}
            className="group relative overflow-hidden rounded-3xl border border-white/10 bg-surface/60 backdrop-blur-sm p-7 transition-colors duration-500 hover:border-emerald-500/40"
          >
            <div className="absolute -top-8 -right-8 w-24 h-24 rounded-full bg-emerald-500/10 blur-2xl opacity-0 group-hover:opacity-100 transition-opacity duration-500 pointer-events-none" />
            <div className="relative z-10">
              <div className="w-11 h-11 rounded-xl bg-emerald-500/10 text-emerald-400 flex items-center justify-center text-lg mb-4 transition-transform duration-500 group-hover:rotate-12 group-hover:scale-110">
                {benefit.icon}
              </div>
              <h3 className="font-bold text-lg">{benefit.title}</h3>
              <p className="mt-2 text-sm text-foreground/50 leading-relaxed">{benefit.description}</p>
            </div>
          </motion.div>
        ))}
      </div>
    </SectionShell>
  );
}

/* ============ CAREER PASSPORT ============ */
export function CareerPassport() {
  return (
    <SectionShell id="career-passport" glow="cyan">
      <motion.div
        initial={{ opacity: 0, y: 40, scale: 0.96 }}
        whileInView={{ opacity: 1, y: 0, scale: 1 }}
        viewport={{ once: true }}
        transition={{ duration: 0.7, type: "spring", stiffness: 90 }}
        className="relative max-w-7xl rounded-3xl border border-emerald-500/20 bg-gradient-to-br from-emerald-500/5 via-cyan-500/5 to-transparent p-2 sm:p-12 overflow-hidden group"
      >
        <div className="absolute top-0 right-0 w-72 h-72 rounded-full bg-emerald-500/10 blur-3xl pointer-events-none" />
        <div className="absolute bottom-0 left-0 w-56 h-56 rounded-full bg-cyan-500/10 blur-3xl pointer-events-none" />

        <div className="relative z-10">
          <Eyebrow>Career Passport</Eyebrow>
          <Headline>
            More than a profile.{" "}
            <span className="bg-gradient-to-r from-emerald-400 via-cyan-400 to-blue-400 bg-clip-text text-transparent">
              A story of who you&apos;re becoming.
            </span>
          </Headline>
          <motion.p
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ delay: 0.3, duration: 0.6 }}
            className="mt-6 max-w-3xl text-lg leading-relaxed text-foreground/50"
          >
            Every student has a story that goes beyond marks and exam results. The Novi Career Passport helps bring that story together—interests, strengths, skills, projects, achievements and evolving aspirations. As you discover more about yourself, your Career Passport evolves with you.
          </motion.p>
          <motion.p
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ delay: 0.45, duration: 0.6 }}
            className="mt-6 text-xl font-semibold bg-gradient-to-r from-emerald-400 via-cyan-400 to-blue-400 bg-clip-text text-transparent"
          >
            Your future should reflect more than just your grades.
          </motion.p>
        </div>
      </motion.div>
    </SectionShell>
  );
}

/* ============ NOVI DIFFERENCE ============ */
export function NoviDifference() {
  return (
    <SectionShell id="novi-difference" glow="blue">
      <div className="max-w-3xl mb-12">
        <Eyebrow>The Novi Difference</Eyebrow>
        <Headline>
          A different way{" "}
          <span className="bg-gradient-to-r from-emerald-400 via-cyan-400 to-blue-400 bg-clip-text text-transparent">
            to move forward.
          </span>
        </Headline>
      </div>

      {/* Reduced width and changed to a 2-column grid */}
      <div className="max-w-4xl mx-auto mt-8 grid grid-cols-1 md:grid-cols-2 gap-4 sm:gap-6">
        {differences.map((item, i) => (
          <motion.div
            key={item.traditional}
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-50px" }}
            transition={{ delay: i * 0.1, duration: 0.6, type: "spring", stiffness: 100 }}
            whileHover={{ y: -5 }}
            className={`group relative flex flex-col justify-between overflow-hidden rounded-3xl border border-white/10 bg-surface/40 backdrop-blur-sm p-6 sm:p-8 transition-all duration-500 hover:bg-surface/80 hover:shadow-2xl ${item.span || ""}`}
          >
            {/* Glow Effect on Hover */}
            <div 
              className={`absolute inset-0 bg-gradient-to-br ${item.gradient} opacity-0 group-hover:opacity-[0.05] transition-opacity duration-700 pointer-events-none`} 
            />

            {/* Top: Traditional (Dimmed) */}
            <div className="relative z-10 flex items-start gap-3 mb-6 opacity-40 group-hover:opacity-20 transition-opacity duration-500">
              <span className={`mt-0.5 rounded-full p-1 ${item.bg} ${item.text}`}>
                <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </span>
              <div>
                <span className="block text-[10px] font-bold uppercase tracking-[0.16em] text-foreground/50 mb-1">
                  Traditional Approach
                </span>
                <p className="text-sm font-medium text-foreground/70 line-through decoration-foreground/30 decoration-2">
                  {item.traditional}
                </p>
              </div>
            </div>

            {/* Middle Animated Divider */}
            <div className="relative z-10 w-full h-px bg-white/5 mb-6">
              <div className={`absolute left-0 top-1/2 -translate-y-1/2 w-8 h-8 rounded-full border border-white/10 bg-background flex items-center justify-center group-hover:scale-110 group-hover:border-${item.text.split('-')[1]}-500/50 transition-all duration-500 shadow-xl`}>
                <svg className={`w-4 h-4 text-foreground/30 group-hover:${item.text} transition-colors duration-300`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 14l-7 7m0 0l-7-7m7 7V3" />
                </svg>
              </div>
            </div>

            {/* Bottom: Novi (Highlighted) */}
            <div className="relative z-10 flex items-start gap-3">
              <span className={`mt-0.5 rounded-full p-1 bg-gradient-to-br ${item.gradient} text-white shadow-lg`}>
                <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                </svg>
              </span>
              <div>
                <span className={`block text-[10px] font-bold uppercase tracking-[0.16em] mb-1 ${item.text}`}>
                  The Novi Approach
                </span>
                <p className="text-base sm:text-lg font-semibold text-foreground transition-colors duration-300">
                  {item.novi}
                </p>
              </div>
            </div>
          </motion.div>
        ))}
      </div>

      <motion.p
        initial={{ opacity: 0, y: 20 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true }}
        transition={{ delay: 0.6, duration: 0.6 }}
        className="mt-12 text-center text-sm sm:text-base text-foreground/40 leading-relaxed max-w-2xl mx-auto"
      >
        Novi is a continuous companion, not a replacement for teachers, parents or professional counsellors.
      </motion.p>
    </SectionShell>
  );
}