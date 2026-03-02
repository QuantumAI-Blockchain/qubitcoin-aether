import type { NextConfig } from "next";
import bundleAnalyzer from "@next/bundle-analyzer";
import createNextIntlPlugin from "next-intl/plugin";

const withNextIntl = createNextIntlPlugin("./src/i18n/request.ts");

const withBundleAnalyzer = bundleAnalyzer({
  enabled: process.env.ANALYZE === "true",
});

const nextConfig: NextConfig = {
  reactStrictMode: true,
  images: {
    formats: ["image/avif", "image/webp"],
    remotePatterns: [
      { protocol: "https", hostname: "qbc.network" },
      { protocol: "https", hostname: "*.qbc.network" },
      { protocol: "https", hostname: "api.qbc.network" },
      { protocol: "https", hostname: "avatars.githubusercontent.com" },
    ],
  },
  turbopack: {
    root: __dirname,
  },
  experimental: {
    optimizePackageImports: ["framer-motion", "three", "@react-three/fiber", "@react-three/drei", "ethers"],
  },
  poweredByHeader: false,
  async headers() {
    return [
      // TWA routes — allow Telegram to embed in iframe/WebView + load SDK script
      {
        source: "/twa/:path*",
        headers: [
          // No X-Frame-Options — Telegram needs to embed TWA pages
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          {
            key: "Content-Security-Policy",
            value: "default-src 'self'; script-src 'self' 'unsafe-eval' 'unsafe-inline' https://telegram.org; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; connect-src 'self' ws://localhost:* wss://localhost:* wss://*.qbc.network http://localhost:* https://qbc.network https://*.qbc.network https://api.qbc.network; font-src 'self' data:; frame-ancestors https://web.telegram.org https://desktop.telegram.org https://*.telegram.org",
          },
          {
            key: "Permissions-Policy",
            value: "camera=(), microphone=(), geolocation=()",
          },
          {
            key: "Strict-Transport-Security",
            value: "max-age=63072000; includeSubDomains; preload",
          },
        ],
      },
      // All other routes — strict security
      {
        source: "/((?!twa).*)",
        headers: [
          { key: "X-Frame-Options", value: "DENY" },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          {
            key: "Content-Security-Policy",
            value: "default-src 'self'; script-src 'self' 'unsafe-eval' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; connect-src 'self' ws://localhost:* wss://localhost:* wss://*.qbc.network http://localhost:* https://qbc.network https://*.qbc.network https://api.qbc.network; font-src 'self' data:",
          },
          {
            key: "Permissions-Policy",
            value: "camera=(), microphone=(), geolocation=()",
          },
          {
            key: "Strict-Transport-Security",
            value: "max-age=63072000; includeSubDomains; preload",
          },
        ],
      },
    ];
  },
};

export default withBundleAnalyzer(withNextIntl(nextConfig));
