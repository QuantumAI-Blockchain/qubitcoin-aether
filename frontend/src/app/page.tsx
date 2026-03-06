import { HeroSection } from "@/components/ui/hero-section";
import { StatsBar } from "@/components/ui/stats-bar";
import { FeatureSections } from "@/components/ui/feature-sections";
import { ChatWidget } from "@/components/aether/chat-widget";
import { ErrorBoundary } from "@/components/ui/error-boundary";

export default function HomePage() {
  return (
    <>
      <HeroSection />
      <section className="relative z-10 mt-2 px-4 pb-12 sm:-mt-16">
        <ErrorBoundary>
          <StatsBar />
        </ErrorBoundary>
      </section>
      <FeatureSections />
      <ErrorBoundary>
        <ChatWidget />
      </ErrorBoundary>
    </>
  );
}
