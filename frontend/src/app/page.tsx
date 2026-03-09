import Link from "next/link";
import { HeroSection } from "@/components/ui/hero-section";
import { StatsBar } from "@/components/ui/stats-bar";
import { FeatureSections } from "@/components/ui/feature-sections";
import { ChatWidget } from "@/components/aether/chat-widget";
import { ErrorBoundary } from "@/components/ui/error-boundary";
import { NetworkInfo } from "@/components/ui/network-info";
import { PrivacyBanner } from "@/components/ui/privacy-banner";

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
      <PrivacyBanner />
      <NetworkInfo />
      <ErrorBoundary>
        <ChatWidget />
      </ErrorBoundary>
    </>
  );
}
