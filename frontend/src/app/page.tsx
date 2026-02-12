import { HeroSection } from "@/components/ui/hero-section";
import { StatsBar } from "@/components/ui/stats-bar";
import { FeatureSections } from "@/components/ui/feature-sections";
import { ChatWidget } from "@/components/aether/chat-widget";

export default function HomePage() {
  return (
    <>
      <HeroSection />
      <section className="relative z-10 -mt-16 px-4 pb-12">
        <StatsBar />
      </section>
      <FeatureSections />
      <ChatWidget />
    </>
  );
}
