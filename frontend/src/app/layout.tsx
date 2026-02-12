import type { Metadata } from "next";
import "@/styles/globals.css";
import { Navbar } from "@/components/ui/navbar";
import { Providers } from "./providers";

/* Fonts are declared in globals.css via @theme.
   When deployed to Vercel with network access, add Google Fonts CDN link
   in <head> or switch to next/font/google imports. */

export const metadata: Metadata = {
  title: "Qubitcoin — Quantum-Secured Blockchain with On-Chain AGI",
  description:
    "QBC is a quantum-secured Layer 1 blockchain combining Proof-of-SUSY-Alignment mining, post-quantum cryptography, and the Aether Tree on-chain AGI engine.",
  keywords: ["qubitcoin", "qbc", "quantum", "blockchain", "AGI", "aether tree"],
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <head>
        <link
          rel="preconnect"
          href="https://fonts.googleapis.com"
          crossOrigin="anonymous"
        />
        <link
          href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;700&family=Space+Grotesk:wght@500;600;700&display=swap"
          rel="stylesheet"
        />
      </head>
      <body className="min-h-screen bg-void text-text-primary antialiased">
        <Providers>
          <Navbar />
          <main>{children}</main>
        </Providers>
      </body>
    </html>
  );
}
