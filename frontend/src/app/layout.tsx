import type { Metadata } from "next";
import { Inter, Space_Grotesk, JetBrains_Mono, Orbitron, Share_Tech_Mono, Exo_2 } from "next/font/google";
import { NextIntlClientProvider } from "next-intl";
import { getLocale, getMessages } from "next-intl/server";
import "@/styles/globals.css";
import { Navbar } from "@/components/ui/navbar";
import { Footer } from "@/components/ui/footer";
import { Providers } from "./providers";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-body",
  display: "swap",
});

const spaceGrotesk = Space_Grotesk({
  subsets: ["latin"],
  variable: "--font-heading",
  display: "swap",
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-mono",
  display: "swap",
});

const orbitron = Orbitron({
  subsets: ["latin"],
  variable: "--font-display",
  display: "swap",
});

const shareTechMono = Share_Tech_Mono({
  weight: "400",
  subsets: ["latin"],
  variable: "--font-code",
  display: "swap",
});

const exo2 = Exo_2({
  subsets: ["latin"],
  variable: "--font-reading",
  display: "swap",
});

export const metadata: Metadata = {
  title: {
    default: "QBC | Physics-Secured Digital Assets with On-Chain AGI",
    template: "%s | Qubitcoin",
  },
  description:
    "Qubitcoin (QBC) is a physics-secured Layer 1 blockchain combining Proof-of-SUSY-Alignment mining, post-quantum cryptography, and the Aether Tree on-chain AGI engine.",
  keywords: ["qubitcoin", "qbc", "quantum", "blockchain", "AGI", "aether tree", "proof of thought", "SUSY"],
  metadataBase: new URL("https://qbc.network"),
  manifest: "/manifest.json",
  openGraph: {
    type: "website",
    siteName: "Qubitcoin",
    title: "Qubitcoin — Physics-Secured Digital Assets with On-Chain AGI",
    description: "Layer 1 blockchain with quantum computing, post-quantum cryptography, and the Aether Tree AGI engine.",
    url: "https://qbc.network",
    locale: "en_US",
  },
  twitter: {
    card: "summary_large_image",
    title: "Qubitcoin (QBC)",
    description: "Physics-secured blockchain with on-chain AGI.",
  },
  robots: {
    index: true,
    follow: true,
  },
};

export default async function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const locale = await getLocale();
  const messages = await getMessages();

  return (
    <html lang={locale} className={`${inter.variable} ${spaceGrotesk.variable} ${jetbrainsMono.variable} ${orbitron.variable} ${shareTechMono.variable} ${exo2.variable}`}>
      <body className="min-h-screen bg-bg-deep text-text-primary antialiased">
        <NextIntlClientProvider messages={messages}>
          <Providers>
            <Navbar />
            <main>{children}</main>
            <Footer />
          </Providers>
        </NextIntlClientProvider>
      </body>
    </html>
  );
}
