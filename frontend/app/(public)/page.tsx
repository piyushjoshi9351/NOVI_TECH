import NavBar from "@/components/ui/NavBar";
import BackgroundParticles from "@/components/ui/BackgroundParticles";
import Hero from "@/components/home/Hero";
import HowItWorks from "@/components/home/HowItWorks";
import ForStudents from "@/components/home/ForStudents";
import ForParents from "@/components/home/ForParents";
import Universities from "@/components/home/Universities";
import AboutUs from "@/components/home/AboutUs";
import { TheProblem, NoviJourney, EverythingStartsWithYou, CareerPassport, NoviDifference } from "@/components/home/WebsiteSections";

export default function Home() {
  return (
    <div className="relative min-h-screen overflow-hidden bg-background">
      <BackgroundParticles />
      <NavBar />
      <main className="relative z-10">
        <Hero />
        <TheProblem />
        <NoviJourney />
        <EverythingStartsWithYou />
        <HowItWorks />
        <ForStudents />
        <ForParents />
        <CareerPassport />
        <Universities />
        <NoviDifference />
        <AboutUs />
      </main>
    </div>
  );
}
