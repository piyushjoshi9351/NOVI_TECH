import type { Metadata } from "next";
import ThemeProvider from "@/components/ui/ThemeProvider";
import "@/site/site.css";

export const metadata: Metadata = {
  title: "Novi – Career Guidance and Future Planning for Students",
  description:
    "Discover what you're good at, explore careers you didn't know existed, and build a roadmap for the future that's right for you.",
  openGraph: {
    title: "Novi – Career Guidance and Future Planning for Students",
    description:
      "Discover who you are. Explore what's possible. Build your path. Become who you want to be.",
    type: "website",
    siteName: "Novi",
  },
};

export default function PublicLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <ThemeProvider>
      <div className="font-sans">{children}</div>
    </ThemeProvider>
  );
}
