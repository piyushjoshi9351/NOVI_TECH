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
  },
  {
    title: "02. Explore possibilities",
    description: "Discover careers that align with your unique profile, including options you may never have considered—and understand why they might suit you.",
  },
  {
    title: "03. Build your roadmap",
    description: "Get personalised next steps for the coming 12 months, from skills and projects to subject choices, courses and further exploration.",
  },
  {
    title: "04. Build your Career Passport",
    description: "Keep your evolving interests, skills, projects, achievements and aspirations in one place as your future takes shape.",
  },
];

const benefits = [
  { title: "Know yourself", description: "Discover your interests, strengths and motivations." },
  { title: "Think beyond the obvious", description: "Explore emerging careers and new possibilities." },
  { title: "Know your next step", description: "Turn big ambitions into manageable actions." },
  { title: "Build your story", description: "Bring together your skills, projects and achievements." },
];

const differences = [
  ["One-time career assessment", "An evolving discovery journey"],
  ["Generic career lists", "Personalised possibilities with explanations"],
  ["Information without direction", "Actionable next steps"],
  ["Focus on a single career decision", "Support across Grades 9–12"],
  ["Achievements scattered everywhere", "A persistent Career Passport"],
];

export function TheProblem() {
  return (
    <section className="relative py-24 px-6">
      <div className="mx-auto max-w-7xl">
        <Reveal>
          <h2 className="font-display text-4xl font-bold leading-[1.08] tracking-tight sm:text-5xl">
            The world is changing. The way we plan for the future should change too.
          </h2>
          <p className="mt-6 max-w-3xl text-lg leading-relaxed text-muted">
            Students are asked to make important decisions about subjects, careers and universities before they fully understand their options.
          </p>
        </Reveal>
        <div className="mt-12 grid gap-4 sm:grid-cols-2">
          {problems.map((problem) => (
            <Reveal key={problem} className="rounded-3xl border border-border-soft bg-surface p-7 text-muted">
              {problem}
            </Reveal>
          ))}
        </div>
        <Reveal>
          <p className="mt-8 text-xl font-semibold text-gradient">Novi turns confusion into clarity—and clarity into action.</p>
        </Reveal>
      </div>
    </section>
  );
}

export function NoviJourney() {
  return (
    <section className="relative py-24 px-6">
      <div className="mx-auto max-w-7xl">
        <Reveal>
          <h2 className="font-display text-4xl font-bold sm:text-5xl">How Novi Works</h2>
        </Reveal>
        <div className="mt-12 grid gap-4 md:grid-cols-2">
          {journey.map((step) => (
            <Reveal key={step.title} className="rounded-3xl border border-border-soft bg-surface p-7">
              <h3 className="font-display text-xl font-bold text-primary">{step.title}</h3>
              <p className="mt-4 leading-relaxed text-muted">{step.description}</p>
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  );
}

export function EverythingStartsWithYou() {
  return (
    <section className="relative py-24 px-6">
      <div className="mx-auto max-w-7xl">
        <Reveal>
          <h2 className="font-display text-4xl font-bold sm:text-5xl">Not another career test. A better way to discover yourself.</h2>
          <p className="mt-6 max-w-3xl text-lg leading-relaxed text-muted">
            Novi doesn&apos;t believe that one test or one conversation can define your future. Your interests change. You discover new strengths. Your ambitions evolve. Novi grows with you.
          </p>
        </Reveal>
        <div className="mt-12 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {benefits.map((benefit) => (
            <Reveal key={benefit.title} className="rounded-3xl border border-border-soft bg-surface p-7">
              <h3 className="font-display text-xl font-bold">{benefit.title}</h3>
              <p className="mt-4 text-muted">{benefit.description}</p>
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  );
}

export function CareerPassport() {
  return (
    <section className="relative py-24 px-6">
      <Reveal className="mx-auto max-w-7xl rounded-3xl border border-border-soft bg-surface p-8 sm:p-12">
        <h2 className="font-display text-4xl font-bold sm:text-5xl">More than a profile. A story of who you&apos;re becoming.</h2>
        <p className="mt-6 max-w-3xl text-lg leading-relaxed text-muted">
          Every student has a story that goes beyond marks and exam results. The Novi Career Passport helps bring that story together—interests, strengths, skills, projects, achievements and evolving aspirations. As you discover more about yourself, your Career Passport evolves with you.
        </p>
        <p className="mt-6 text-xl font-semibold text-gradient">Your future should reflect more than just your grades.</p>
      </Reveal>
    </section>
  );
}

export function NoviDifference() {
  return (
    <section className="relative py-24 px-6">
      <div className="mx-auto max-w-7xl">
        <Reveal>
          <h2 className="font-display text-4xl font-bold sm:text-5xl">The Novi Difference</h2>
        </Reveal>
        <Reveal className="mt-12 overflow-x-auto rounded-3xl border border-border-soft bg-surface">
          <table className="w-full min-w-[520px] text-left">
            <thead className="border-b border-border-soft text-primary">
              <tr><th className="p-6 font-semibold">Traditional approach</th><th className="p-6 font-semibold">The Novi approach</th></tr>
            </thead>
            <tbody>
              {differences.map(([traditional, novi]) => (
                <tr key={traditional} className="border-b border-border-soft last:border-0">
                  <td className="p-6 text-muted">{traditional}</td><td className="p-6 font-medium">{novi}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Reveal>
        <Reveal>
          <p className="mt-8 text-muted">Novi is a continuous companion, not a replacement for teachers, parents or professional counsellors.</p>
        </Reveal>
      </div>
    </section>
  );
}
