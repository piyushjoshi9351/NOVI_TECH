import type { Metadata } from "next";
import NavBar from "@/components/ui/NavBar";
import ParentsHero from "@/components/parents/ParentsHero";
import ParentsValueGrid from "@/components/parents/ParentsValueGrid";
import ParentsMonthlyFocus from "@/components/parents/ParentsMonthlyFocus";
import ParentsPillars from "@/components/parents/ParentsPillars";
import ParentsQADemo from "@/components/parents/ParentsQADemo";
import ParentsJourneyMap from "@/components/parents/ParentsJourneyMap";
import ParentsBalanceModel from "@/components/parents/ParentsBalanceModel";
import ParentsSocialProof from "@/components/parents/ParentsSocialProof";
import ParentsCTAFooter from "@/components/parents/ParentsCTAFooter";

export const metadata: Metadata = {
  title: "Career Planning for Your Child | Novi",
  description:
    "Stay informed about your child's journey without micromanaging. Novi gives parents clarity and students independence.",
};

export default function ForParentsPage() {
  return (
    <div className="relative min-h-screen overflow-hidden bg-background text-foreground">
      <NavBar />
      <main className="relative z-10 flex flex-col">
        <ParentsHero />
        <ParentsValueGrid />
        <ParentsMonthlyFocus />
        <ParentsPillars />
        <ParentsQADemo />
        <ParentsJourneyMap />
        <ParentsBalanceModel />
        <ParentsSocialProof />
        <ParentsCTAFooter />
      </main>
    </div>
  );
}
