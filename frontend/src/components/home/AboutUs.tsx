// "use client";

// import Image from "next/image";
// import Link from "next/link";
// import { motion } from "framer-motion";
// import Reveal from "@/components/ui/Reveal";
// import Magnetic from "@/components/ui/Magnetic";

// type FooterLink = string | { label: string; href: string };

// const footerColumns: { title: string; links: FooterLink[] }[] = [
//   {
//     title: "For Students",
//     links: ["How It Works", "Career Explorer", "University Explorer", "AI Roadmap", "Career Passport"],
//   },
//   {
//     title: "For Parents",
//     links: ["Parent Dashboard", "How We Help", "Resources", "Guides"],
//   },
//   {
//     title: "Company",
//     links: ["About Us", "Blog", "Careers", "Contact Us"],
//   },
//   {
//     title: "Legal",
//     links: [
//       { label: "Privacy Policy", href: "/privacy" },
//       { label: "Terms of Service", href: "/terms" },
//       { label: "Cookie Policy", href: "/cookies" },
//     ],
//   },
// ];

// const socials = [
//   {
//     label: "Instagram",
//     path: "M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zm0-2.163c-3.259 0-3.667.014-4.947.072-4.358.2-6.78 2.618-6.98 6.98-.059 1.281-.073 1.689-.073 4.948 0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98 1.281.058 1.689.072 4.948.072 3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98-1.281-.059-1.69-.073-4.949-.073zm0 5.838c-3.403 0-6.162 2.759-6.162 6.162s2.759 6.163 6.162 6.163 6.162-2.759 6.162-6.163c0-3.403-2.759-6.162-6.162-6.162zm0 10.162c-2.209 0-4-1.79-4-4 0-2.209 1.791-4 4-4s4 1.791 4 4c0 2.21-1.791 4-4 4zm6.406-11.845c-.796 0-1.441.645-1.441 1.44s.645 1.44 1.441 1.44c.795 0 1.439-.645 1.439-1.44s-.644-1.44-1.439-1.44z",
//   },
//   {
//     label: "YouTube",
//     path: "M19.615 3.184c-3.604-.246-11.631-.245-15.23 0-3.897.266-4.356 2.62-4.385 8.816.029 6.185.484 8.549 4.385 8.816 3.6.245 11.626.246 15.23 0 3.897-.266 4.356-2.62 4.385-8.816-.029-6.185-.484-8.549-4.385-8.816zm-10.615 12.816v-8l8 3.993-8 4.007z",
//   },
//   {
//     label: "LinkedIn",
//     path: "M4.98 3.5c0 1.381-1.11 2.5-2.48 2.5s-2.48-1.119-2.48-2.5c0-1.38 1.11-2.5 2.48-2.5s2.48 1.12 2.48 2.5zm.02 4.5h-5v16h5v-16zm7.982 0h-4.968v16h4.969v-8.399c0-4.67 6.029-5.052 6.029 0v8.399h4.988v-10.131c0-7.88-8.922-7.593-11.018-3.714v-2.155z",
//   },
//   {
//     label: "Twitter",
//     path: "M24 4.557c-.883.392-1.832.656-2.828.775 1.017-.609 1.798-1.574 2.165-2.724-.951.564-2.005.974-3.127 1.195-.897-.957-2.178-1.555-3.594-1.555-3.179 0-5.515 2.966-4.797 6.045-4.091-.205-7.719-2.165-10.148-5.144-1.29 2.213-.669 5.108 1.523 6.574-.806-.026-1.566-.247-2.229-.616-.054 2.281 1.581 4.415 3.949 4.89-.693.188-1.452.232-2.224.084.626 1.956 2.444 3.379 4.6 3.419-2.07 1.623-4.678 2.348-7.29 2.04 2.179 1.397 4.768 2.212 7.548 2.212 9.142 0 14.307-7.721 13.995-14.646.962-.695 1.797-1.562 2.457-2.549z",
//   },
// ];

// export default function AboutUs() {
//   return (
//     <>
//       <section id="about-us" className="relative overflow-hidden pb-24 pt-8">
//         <div className="mx-auto max-w-[1400px] px-6">
//           <div className="relative overflow-hidden rounded-3xl border border-border-soft bg-gradient-to-br from-primary/[0.08] via-background to-accent/[0.05]">
//             <div className="pointer-events-none absolute inset-0 bg-dots opacity-20 [mask-image:radial-gradient(ellipse_50%_50%_at_100%_0%,#000_10%,transparent_60%)]" />
//             <div className="grid items-center gap-8 p-8 lg:grid-cols-2">
//               <div className="order-2 relative flex justify-center lg:order-1 lg:justify-start">
//                 <div className="pointer-events-none absolute top-1/2 left-1/2 size-80 -translate-x-1/2 -translate-y-1/2 rounded-full bg-primary/20 blur-3xl" />
//                 <div className="animate-float-slow relative mx-auto h-[300px] w-full max-w-md sm:h-[400px]">
//                   <Image
//                     src="/3dboy.png"
//                     alt="Novi AI Mentor"
//                     fill
//                     priority
//                     className="object-contain drop-shadow-2xl"
//                   />
//                 </div>
//               </div>

//               <div className="relative z-10 order-1 lg:order-2">
//                 <Reveal>
//                   <h2 className="font-display text-4xl font-bold leading-[1.1] tracking-tight sm:text-5xl lg:text-6xl">
//                     The future doesn&apos;t come with a map.{" "}
//                     <br className="hidden sm:block" />
//                     Let&apos;s build yours.
//                   </h2>
//                 </Reveal>
//                 <Reveal delay={0.1}>
//                   <h3 className="text-gradient mb-8 mt-4 font-display text-3xl font-bold sm:text-4xl lg:text-5xl">
//                     Start discovering what makes you unique, where your interests could take you and what you can do next.
//                   </h3>
//                 </Reveal>
//                 <Reveal delay={0.2}>
//                   <div className="flex flex-col gap-6 lg:flex-row lg:items-center">
//                     <Magnetic strength={14}>
//                       <a
//                         href="/signup"
//                         className="btn-shine group inline-flex items-center justify-center gap-2 rounded-full bg-primary px-8 py-3.5 text-sm font-semibold text-primary-foreground transition-all hover:-translate-y-0.5 hover:shadow-lg lg:w-auto"
//                       >
//                         Start your Novi journey
//                         <motion.span
//                           animate={{ x: [0, 4, 0] }}
//                           transition={{
//                             duration: 1.6,
//                             repeat: Infinity,
//                             ease: "easeInOut",
//                           }}
//                         >
//                           →
//                         </motion.span>
//                       </a>
//                     </Magnetic>
//                     <ul className="flex flex-wrap gap-x-5 gap-y-2 text-sm text-foreground/70">
//                       {[
//                         "It's free to get started",
//                         "No credit card required",
//                         "Takes less than 5 minutes",
//                       ].map((item) => (
//                         <li
//                           key={item}
//                           className="flex items-center gap-2 transition-colors hover:text-foreground"
//                         >
//                           <span className="grid size-4 place-items-center rounded-full bg-green-500/20 text-[10px] text-green-500">
//                             ✓
//                           </span>
//                           {item}
//                         </li>
//                       ))}
//                     </ul>
//                   </div>
//                 </Reveal>
//               </div>
//             </div>
//           </div>
//         </div>
//       </section>

//       <footer className="border-t border-border-soft">
//         <div className="mx-auto max-w-[1400px] px-6 pt-12 pb-8">
//           <div className="grid grid-cols-2 gap-8 md:grid-cols-3 lg:grid-cols-6">
//             <div className="col-span-2">
//               <LogoMark />
//               <p className="mt-4 mb-6 max-w-xs text-sm leading-relaxed text-muted">
//                 The AI mentor and operating system for students from Grade 9 to
//                 their dream university.
//               </p>
//               <div className="flex items-center gap-4">
//                 {socials.map((s) => (
//                   <a
//                     key={s.label}
//                     href="#"
//                     aria-label={s.label}
//                     className="grid size-9 place-items-center rounded-full border border-border-soft text-muted transition-colors hover:border-primary/30 hover:text-primary"
//                   >
//                     <svg
//                       viewBox="0 0 24 24"
//                       className="size-4"
//                       fill="currentColor"
//                       aria-hidden="true"
//                     >
//                       <path d={s.path} />
//                     </svg>
//                   </a>
//                 ))}
//               </div>
//             </div>

//             {footerColumns.map((col) => (
//               <div key={col.title}>
//                 <h4 className="text-sm font-semibold">{col.title}</h4>
//                 <ul className="mt-4 space-y-2 text-sm text-muted">
//                   {col.links.map((link) => {
//                     const label = typeof link === "string" ? link : link.label;
//                     const href = typeof link === "string" ? "#" : link.href;
//                     return (
//                       <li key={label}>
//                         <Link
//                           href={href}
//                           className="transition-colors hover:text-primary"
//                         >
//                           {label}
//                         </Link>
//                       </li>
//                     );
//                   })}
//                 </ul>
//               </div>
//             ))}

//             <div>
//               <h4 className="text-sm font-semibold">Stay updated with Novi</h4>
//               <form className="mt-4 flex items-center overflow-hidden rounded-full border border-border-soft bg-background/50 transition-colors focus-within:border-primary/50">
//                 <input
//                   type="email"
//                   placeholder="Enter your email"
//                   aria-label="Enter your email"
//                   className="flex-1 bg-transparent px-4 py-2.5 text-sm outline-none placeholder:text-muted"
//                 />
//                 <button
//                   type="submit"
//                   className="grid size-10 shrink-0 place-items-center bg-primary text-white transition-colors hover:bg-primary/90"
//                 >
//                   →
//                 </button>
//               </form>
//             </div>
//           </div>

//           <div className="mt-8 border-t border-border-soft pt-6 text-center text-sm text-muted">
//             © 2024 Novi. All rights reserved.
//           </div>
//         </div>
//       </footer>
//     </>
//   );
// }

// function LogoMark() {
//   return (
//     <div className="flex items-center gap-2.5">
//       <span className="relative grid size-9 place-items-center overflow-hidden rounded-xl shadow-glow">
//         <Image
//           src="/icon.png"
//           alt="Novi logo"
//           fill
//           sizes="36px"
//           className="object-contain"
//         />
//       </span>
//       <span className="font-display text-2xl font-bold">Novi</span>
//     </div>
//   );
// }














"use client";

import Image from "next/image";
import Link from "next/link";
import { motion } from "framer-motion";
import Reveal from "@/components/ui/Reveal";
import Magnetic from "@/components/ui/Magnetic";

type FooterLink = string | { label: string; href: string };

const footerColumns: { title: string; links: FooterLink[] }[] = [
  {
    title: "For Students",
    links: ["How It Works", "Career Explorer", "University Explorer", "AI Roadmap", "Career Passport"],
  },
  {
    title: "For Parents",
    links: ["Parent Dashboard", "How We Help", "Resources", "Guides"],
  },
  {
    title: "Company",
    links: ["About Us", "Blog", "Careers", "Contact Us"],
  },
  {
    title: "Legal",
    links: [
      { label: "Privacy Policy", href: "/privacy" },
      { label: "Terms of Service", href: "/terms" },
      { label: "Cookie Policy", href: "/cookies" },
    ],
  },
];

const socials = [
  {
    label: "Instagram",
    path: "M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zm0-2.163c-3.259 0-3.667.014-4.947.072-4.358.2-6.78 2.618-6.98 6.98-.059 1.281-.073 1.689-.073 4.948 0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98 1.281.058 1.689.072 4.948.072 3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98-1.281-.059-1.69-.073-4.949-.073zm0 5.838c-3.403 0-6.162 2.759-6.162 6.162s2.759 6.163 6.162 6.163 6.162-2.759 6.162-6.163c0-3.403-2.759-6.162-6.162-6.162zm0 10.162c-2.209 0-4-1.79-4-4 0-2.209 1.791-4 4-4s4 1.791 4 4c0 2.21-1.791 4-4 4zm6.406-11.845c-.796 0-1.441.645-1.441 1.44s.645 1.44 1.441 1.44c.795 0 1.439-.645 1.439-1.44s-.644-1.44-1.439-1.44z",
  },
  {
    label: "YouTube",
    path: "M19.615 3.184c-3.604-.246-11.631-.245-15.23 0-3.897.266-4.356 2.62-4.385 8.816.029 6.185.484 8.549 4.385 8.816 3.6.245 11.626.246 15.23 0 3.897-.266 4.356-2.62 4.385-8.816-.029-6.185-.484-8.549-4.385-8.816zm-10.615 12.816v-8l8 3.993-8 4.007z",
  },
  {
    label: "LinkedIn",
    path: "M4.98 3.5c0 1.381-1.11 2.5-2.48 2.5s-2.48-1.119-2.48-2.5c0-1.38 1.11-2.5 2.48-2.5s2.48 1.12 2.48 2.5zm.02 4.5h-5v16h5v-16zm7.982 0h-4.968v16h4.969v-8.399c0-4.67 6.029-5.052 6.029 0v8.399h4.988v-10.131c0-7.88-8.922-7.593-11.018-3.714v-2.155z",
  },
  {
    label: "Twitter",
    path: "M24 4.557c-.883.392-1.832.656-2.828.775 1.017-.609 1.798-1.574 2.165-2.724-.951.564-2.005.974-3.127 1.195-.897-.957-2.178-1.555-3.594-1.555-3.179 0-5.515 2.966-4.797 6.045-4.091-.205-7.719-2.165-10.148-5.144-1.29 2.213-.669 5.108 1.523 6.574-.806-.026-1.566-.247-2.229-.616-.054 2.281 1.581 4.415 3.949 4.89-.693.188-1.452.232-2.224.084.626 1.956 2.444 3.379 4.6 3.419-2.07 1.623-4.678 2.348-7.29 2.04 2.179 1.397 4.768 2.212 7.548 2.212 9.142 0 14.307-7.721 13.995-14.646.962-.695 1.797-1.562 2.457-2.549z",
  },
];

export default function AboutUs() {
  return (
    <>
      {/* ====== REDESIGNED ABOUT US SECTION ====== */}
      <section id="about-us" className="relative overflow-hidden py-24 bg-background">
        {/* Ambient Background Glows */}
        <div className="pointer-events-none absolute top-0 left-1/4 w-[600px] h-[600px] bg-primary/10 rounded-full blur-[120px] opacity-40 mix-blend-screen" />
        <div className="pointer-events-none absolute bottom-0 right-1/4 w-[500px] h-[500px] bg-accent/10 rounded-full blur-[100px] opacity-40 mix-blend-screen" />

        <div className="mx-auto max-w-7xl px-6 relative z-10">
          
          {/* Header */}
          <div className="max-w-3xl mb-12">
            <Reveal>
              <h2 className="font-display text-4xl font-bold leading-[1.1] tracking-tight sm:text-5xl lg:text-6xl text-foreground">
                The future doesn&apos;t come with a map.{" "}
                <span className="bg-gradient-to-r from-primary via-indigo-400 to-accent bg-clip-text text-transparent block mt-2">
                  Let&apos;s build yours.
                </span>
              </h2>
            </Reveal>
          </div>

          {/* Bento Grid Layout */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 sm:gap-6">
            
            {/* Left Box: 3D Image with Gradient Border */}
            <Reveal delay={0.1} className="lg:col-span-5 flex">
              <div className="group relative w-full rounded-[2rem] p-[1px] bg-gradient-to-b from-primary/40 via-white/10 to-transparent transition-all duration-500 hover:from-primary/60 hover:via-primary/20 hover:shadow-[0_0_40px_-10px_rgba(var(--primary),0.3)]">
                <div className="relative h-full w-full overflow-hidden rounded-[2rem] bg-surface/60 backdrop-blur-xl flex items-center justify-center p-8 min-h-[400px]">
                  {/* Inner Grid Pattern */}
                  <div className="absolute inset-0 bg-[linear-gradient(to_right,#80808012_1px,transparent_1px),linear-gradient(to_bottom,#80808012_1px,transparent_1px)] bg-[size:24px_24px] [mask-image:radial-gradient(ellipse_60%_60%_at_50%_50%,#000_70%,transparent_100%)]" />
                  
                  {/* Image Glow */}
                  <div className="pointer-events-none absolute top-1/2 left-1/2 size-64 -translate-x-1/2 -translate-y-1/2 rounded-full bg-primary/30 blur-[80px] group-hover:bg-primary/40 transition-colors duration-500" />
                  
                  <div className="animate-float-slow relative w-full max-w-sm h-[300px] sm:h-[400px] z-10">
                    <Image
                      src="/3dboy.png"
                      alt="Novi AI Mentor"
                      fill
                      priority
                      className="object-contain drop-shadow-2xl transition-transform duration-700 group-hover:scale-105"
                    />
                  </div>
                </div>
              </div>
            </Reveal>

            {/* Right Side: Split into two smaller cards */}
            <div className="lg:col-span-7 flex flex-col gap-5 sm:gap-6">
              
              {/* Top Right Card: Sub-headline with subtle tint */}
              <Reveal delay={0.2} className="flex-1">
                <div className="relative h-full overflow-hidden rounded-[2rem] border border-white/10 bg-gradient-to-br from-surface/80 to-background/40 backdrop-blur-md p-8 sm:p-10 flex flex-col justify-center transition-all duration-500 hover:border-primary/30 hover:bg-surface/90">
                  {/* Decorative gradient blob in corner */}
                  <div className="absolute -top-12 -right-12 w-48 h-48 bg-accent/20 rounded-full blur-3xl" />
                  
                  <p className="relative z-10 text-2xl sm:text-3xl font-medium leading-snug text-foreground/80">
                    Start discovering <span className="text-primary font-semibold bg-primary/10 px-2 py-0.5 rounded-lg">what makes you unique</span>, where your interests could take you and what you can do next.
                  </p>
                </div>
              </Reveal>

              {/* Bottom Right Card: CTA & Checklist with distinct accent background */}
              <Reveal delay={0.3}>
                <div className="relative overflow-hidden rounded-[2rem] border border-primary/20 bg-gradient-to-r from-primary/5 via-surface/50 to-accent/5 backdrop-blur-md p-8 sm:p-10 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-8 transition-all duration-500 hover:border-primary/40 hover:shadow-[0_0_30px_-10px_rgba(var(--primary),0.2)]">
                  
                  {/* CTA Button */}
                  <Magnetic strength={14}>
                    <a
                      href="/signup"
                      className="btn-shine group relative inline-flex shrink-0 items-center justify-center gap-2 rounded-full bg-primary px-8 py-4 text-sm font-semibold text-primary-foreground transition-all hover:-translate-y-1 hover:shadow-xl hover:shadow-primary/30 z-10"
                    >
                      Start your Novi journey
                      <motion.span
                        animate={{ x: [0, 4, 0] }}
                        transition={{ duration: 1.6, repeat: Infinity, ease: "easeInOut" }}
                      >
                        →
                      </motion.span>
                    </a>
                  </Magnetic>

                  {/* Checklist */}
                  <ul className="relative z-10 flex flex-col gap-3 text-sm font-medium text-foreground/70">
                    {[
                      "It's free to get started",
                      "No credit card required",
                      "Takes less than 5 minutes",
                    ].map((item) => (
                      <li key={item} className="flex items-center gap-3 transition-colors hover:text-foreground">
                        <span className="grid size-5 shrink-0 place-items-center rounded-full bg-green-500/20 text-[11px] font-bold text-green-500 border border-green-500/30">
                          ✓
                        </span>
                        {item}
                      </li>
                    ))}
                  </ul>
                </div>
              </Reveal>

            </div>
          </div>
        </div>
      </section>

      {/* ====== FOOTER (Unchanged) ====== */}
      <footer className="border-t border-border-soft">
        <div className="mx-auto max-w-[1400px] px-6 pt-12 pb-8">
          <div className="grid grid-cols-2 gap-8 md:grid-cols-3 lg:grid-cols-6">
            <div className="col-span-2">
              <LogoMark />
              <p className="mt-4 mb-6 max-w-xs text-sm leading-relaxed text-muted">
                The AI mentor and operating system for students from Grade 9 to
                their dream university.
              </p>
              <div className="flex items-center gap-4">
                {socials.map((s) => (
                  <a
                    key={s.label}
                    href="#"
                    aria-label={s.label}
                    className="grid size-9 place-items-center rounded-full border border-border-soft text-muted transition-colors hover:border-primary/30 hover:text-primary"
                  >
                    <svg
                      viewBox="0 0 24 24"
                      className="size-4"
                      fill="currentColor"
                      aria-hidden="true"
                    >
                      <path d={s.path} />
                    </svg>
                  </a>
                ))}
              </div>
            </div>

            {footerColumns.map((col) => (
              <div key={col.title}>
                <h4 className="text-sm font-semibold">{col.title}</h4>
                <ul className="mt-4 space-y-2 text-sm text-muted">
                  {col.links.map((link) => {
                    const label = typeof link === "string" ? link : link.label;
                    const href = typeof link === "string" ? "#" : link.href;
                    return (
                      <li key={label}>
                        <Link
                          href={href}
                          className="transition-colors hover:text-primary"
                        >
                          {label}
                        </Link>
                      </li>
                    );
                  })}
                </ul>
              </div>
            ))}

            <div>
              <h4 className="text-sm font-semibold">Stay updated with Novi</h4>
              <form className="mt-4 flex items-center overflow-hidden rounded-full border border-border-soft bg-background/50 transition-colors focus-within:border-primary/50">
                <input
                  type="email"
                  placeholder="Enter your email"
                  aria-label="Enter your email"
                  className="flex-1 bg-transparent px-4 py-2.5 text-sm outline-none placeholder:text-muted"
                />
                <button
                  type="submit"
                  className="grid size-10 shrink-0 place-items-center bg-primary text-white transition-colors hover:bg-primary/90"
                >
                  →
                </button>
              </form>
            </div>
          </div>

          <div className="mt-8 border-t border-border-soft pt-6 text-center text-sm text-muted">
            © 2024 Novi. All rights reserved.
          </div>
        </div>
      </footer>
    </>
  );
}

function LogoMark() {
  return (
    <div className="flex items-center gap-2.5">
      <span className="relative grid size-9 place-items-center overflow-hidden rounded-xl shadow-glow">
        <Image
          src="/icon.png"
          alt="Novi logo"
          fill
          sizes="36px"
          className="object-contain"
        />
      </span>
      <span className="font-display text-2xl font-bold">Novi</span>
    </div>
  );
}