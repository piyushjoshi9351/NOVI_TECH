"use client";

import { useEffect, useState } from "react";
import Image from "next/image";
import Link from "next/link";
import {
  AnimatePresence,
  motion,
  useMotionValue,
  useSpring,
  useTransform,
} from "framer-motion";
import Magnetic from "@/components/ui/Magnetic";

const marqueeItems = [
  { label: "Personalized AI Mentor", emoji: "✨" },
  { label: "4-Year Journey", emoji: "🚀" },
  { label: "Career + University Guidance", emoji: "🎯" },
  { label: "Built around you", emoji: "💡" },
];

const ease = [0.22, 1, 0.36, 1] as const;

export default function Hero() {
  const [showChat, setShowChat] = useState(false);
  const [showTyping, setShowTyping] = useState(true);

  const mouseX = useMotionValue(0);
  const mouseY = useMotionValue(0);
  const rotateX = useSpring(useTransform(mouseY, [-1, 1], [8, -8]), {
    stiffness: 150,
    damping: 20,
  });
  const rotateY = useSpring(useTransform(mouseX, [-1, 1], [-8, 8]), {
    stiffness: 150,
    damping: 20,
  });

  useEffect(() => {
    const chatTimer = setTimeout(() => setShowChat(true), 1200);
    const typingTimer = setTimeout(() => setShowTyping(false), 2400);
    return () => {
      clearTimeout(chatTimer);
      clearTimeout(typingTimer);
    };
  }, []);

  return (
    <section className="relative overflow-hidden min-h-[80vh]">
      <div className="orb -top-40 -right-24 size-[38rem] bg-primary/25" />
      <div className="orb top-1/3 -left-48 size-[34rem] bg-primary/15" />
      <div className="orb -bottom-32 left-1/3 size-[30rem] bg-accent/10" />

      <div className="relative mx-auto grid max-w-7xl gap-14 px-6 pt-36 pb-16 lg:grid-cols-2 lg:items-center lg:gap-10 lg:pt-44">
        <div className="flex flex-col gap-7">
          <motion.span
            initial={{ opacity: 0, scale: 0.8 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: 0.2, duration: 0.5, ease }}
            className="inline-flex items-center gap-2 self-start rounded-full border border-green-500/30 bg-green-500/10 px-4 py-2 text-xs font-semibold uppercase tracking-wide text-green-400 shadow-[0_0_20px_rgba(74,222,128,0.15)]"
          >
            <span className="relative flex size-2">
              <span className="absolute inline-flex size-full animate-ping rounded-full bg-green-400 opacity-60" />
              <span className="relative inline-flex size-2 rounded-full bg-green-400" />
            </span>
            Made in India for the world.
          </motion.span>

          <h1 className="font-display text-4xl font-bold leading-[1.08] tracking-tight sm:text-5xl xl:text-7xl">
            {["Your future is bigger", "than one career choice."].map((line, i) => (
              <motion.span
                key={line}
                initial={{ opacity: 0, y: 30, filter: "blur(8px)" }}
                animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
                transition={{ delay: 0.3 + i * 0.18, duration: 0.7, ease }}
                className={`block ${i === 1 ? "text-gradient" : ""}`}
              >
                {line}
              </motion.span>
            ))}
          </h1>

          <motion.p
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.75, duration: 0.6, ease }}
            className="max-w-xl text-base leading-relaxed text-muted sm:text-lg"
          >
            Discover what you&apos;re good at, explore careers you didn&apos;t know existed, and build a roadmap for the future that&apos;s right for you.
          </motion.p>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.9, duration: 0.6, ease }}
            className="flex flex-col gap-3 sm:flex-row"
          >
            <Magnetic strength={12}>
              <Link
                href="/signup"
                className="btn-shine group inline-flex items-center justify-center gap-2 rounded-full bg-primary px-7 py-3.5 text-sm font-semibold text-primary-foreground transition-all hover:-translate-y-0.5 hover:shadow-lg"
              >
                Discover your future
                <svg
                  viewBox="0 0 24 24"
                  className="size-4 transition-transform duration-300 group-hover:translate-x-1"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2.5"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  aria-hidden="true"
                >
                  <path d="M13.5 4.5 21 12m0 0-7.5 7.5M21 12H3" />
                </svg>
              </Link>
            </Magnetic>
            <Magnetic strength={16}>
              <Link
                href="#for-parents"
                className="group inline-flex items-center justify-center gap-2 rounded-full border border-border-soft px-7 py-3.5 text-sm font-semibold transition-all hover:-translate-y-0.5 hover:border-primary/50 hover:bg-primary/5 hover:text-primary"
              >
                <svg
                  viewBox="0 0 24 24"
                  className="size-5 transition-transform duration-300 group-hover:scale-110"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  aria-hidden="true"
                >
                  <path d="M18 18.72a9.094 9.094 0 0 0 3.741-.479 3 3 0 0 0-4.682-2.72m.94 3.198.001.031c0 .225-.012.447-.037.666A11.944 11.944 0 0 1 12 21c-2.17 0-4.207-.576-5.963-1.584A6.062 6.062 0 0 1 6 18.719m12 0a5.971 5.971 0 0 0-.941-3.197m0 0A5.995 5.995 0 0 0 12 12.75a5.995 5.995 0 0 0-5.058 2.772m0 0a3 3 0 0 0-4.681 2.72 8.986 8.986 0 0 0 3.74.477m.94-3.197a5.971 5.971 0 0 0-.94 3.197M15 6.75a3 3 0 1 1-6 0 3 3 0 0 1 6 0Zm6 3a2.25 2.25 0 1 1-4.5 0 2.25 2.25 0 0 1 4.5 0Zm-13.5 0a2.25 2.25 0 1 1-4.5 0 2.25 2.25 0 0 1 4.5 0Z" />
                </svg>
                Explore Novi for parents
              </Link>
            </Magnetic>
          </motion.div>
        </div>

        <motion.div
          initial={{ opacity: 0, scale: 0.8 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ delay: 0.35, duration: 0.8, type: "spring", stiffness: 90 }}
          onMouseMove={(e) => {
            const { innerWidth, innerHeight } = window;
            mouseX.set((e.clientX / innerWidth) * 2 - 1);
            mouseY.set((e.clientY / innerHeight) * 2 - 1);
          }}
          className="relative mx-auto w-full max-w-[360px] sm:max-w-[480px] lg:max-w-[620px]"
        >
          <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
            <motion.div
              animate={{ scale: [1, 1.15, 1], opacity: [0.25, 0.5, 0.25] }}
              transition={{ duration: 5, repeat: Infinity, ease: "easeInOut" }}
              className="size-[70%] rounded-full bg-gradient-to-br from-primary/30 to-accent/20 blur-3xl"
            />
          </div>
          <div className="pointer-events-none absolute inset-[10%] rounded-full border border-primary/20 animate-spin-slow" />
          <div className="pointer-events-none absolute inset-[20%] rounded-full border border-accent/20 animate-spin-slow [animation-direction:reverse]" />

          <motion.div style={{ rotateX, rotateY, transformStyle: "preserve-3d" }}>
            <div className="animate-float relative aspect-square">
              <Image
                src="/3dboy.png"
                alt="Novi — AI Mentor"
                width={620}
                height={620}
                priority
                className="size-full object-contain drop-shadow-2xl"
              />
            </div>
          </motion.div>

          <AnimatePresence>
            {showChat && (
              <motion.div
                initial={{ opacity: 0, scale: 0.8, y: 20 }}
                animate={{ opacity: 1, scale: 1, y: 0 }}
                transition={{ type: "spring", stiffness: 300, damping: 20 }}
                exit={{ opacity: 0, scale: 0.8, y: 20 }}
                className="absolute -top-5 right-0 z-40 hidden max-w-[280px] md:block"
              >
                <div className="glass rounded-2xl p-4 shadow-2xl">
                  <div className="flex items-start gap-3">
                    <div className="relative grid size-10 shrink-0 place-items-center rounded-full bg-gradient-to-br from-primary to-accent-warm text-lg shadow-lg">
                      <span aria-hidden="true">👋</span>
                      <span className="absolute -right-0.5 -bottom-0.5 size-3 rounded-full border-2 border-surface bg-green-400 animate-pulse" />
                    </div>
                    <div>
                      <div className="mb-1 flex items-center gap-2">
                        <p className="text-sm font-semibold">Hi! I&apos;m Novi</p>
                        <span className="text-[10px] font-medium text-green-400">
                          Online
                        </span>
                      </div>
                      {showTyping ? (
                        <div className="flex items-center gap-1 py-1">
                          {[0, 1, 2].map((i) => (
                            <span
                              key={i}
                              className="typing-dot size-1.5 rounded-full bg-foreground/30"
                              style={{ animationDelay: `${i * 150}ms` }}
                            />
                          ))}
                        </div>
                      ) : (
                        <motion.p
                          key="msg"
                          initial={{ opacity: 0, y: 4 }}
                          animate={{ opacity: 1, y: 0 }}
                          className="text-sm leading-relaxed text-muted"
                        >
                          I&apos;m here to help you discover your best future.
                        </motion.p>
                      )}
                    </div>
                  </div>
                  {!showTyping && (
                    <div className="mt-3 flex flex-wrap gap-2">
                      <button className="rounded-full border border-primary/30 bg-primary/15 px-2.5 py-1 text-[10px] font-medium text-primary transition-colors hover:bg-primary/25">
                        Explore careers
                      </button>
                      <button className="rounded-full border border-accent/30 bg-accent/10 px-2.5 py-1 text-[10px] font-medium text-accent transition-colors hover:bg-accent/20">
                        Find strengths
                      </button>
                    </div>
                  )}
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          <div className="absolute top-[6%] -right-2 z-30 animate-float-slow sm:right-0">
            <div className="glass rounded-xl px-3 py-2 shadow-xl">
              <div className="flex items-center gap-2">
                <span className="size-2 rounded-full bg-green-400 animate-pulse" />
                <span className="text-[10px] font-bold">AI Active</span>
              </div>
            </div>
          </div>
        </motion.div>
      </div>

      <div className="relative border-y border-border-soft bg-gradient-to-r from-primary/5 via-transparent to-primary/5 py-3.5">
        <div className="overflow-hidden [mask-image:linear-gradient(90deg,transparent,#000_8%,#000_92%,transparent)]">
          <div className="marquee-track marquee-track-ltr">
            {[0, 1].map((set) => (
              <div key={set} className="flex shrink-0 items-center">
                {marqueeItems.map((item) => (
                  <div key={`${item.label}-${set}`} className="flex items-center">
                    <span className="flex items-center gap-2 px-4 text-sm font-semibold text-muted">
                      <span aria-hidden="true">{item.emoji}</span>
                      {item.label}
                    </span>
                    <span className="size-1.5 shrink-0 rounded-full bg-primary/50" />
                  </div>
                ))}
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
