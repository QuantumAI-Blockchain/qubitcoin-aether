import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Dashboard",
  description:
    "Monitor your Qubitcoin node: mining stats, Phi integration meter, network health, and contract management.",
  openGraph: {
    title: "Qubitcoin Dashboard",
    description: "Real-time node monitoring, mining controls, and AGI integration metrics.",
  },
};

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
