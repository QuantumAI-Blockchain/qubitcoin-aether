import type { ReactNode } from "react";

interface CardProps {
  children: ReactNode;
  className?: string;
  glow?: "green" | "violet" | "none";
}

export function Card({ children, className = "", glow = "none" }: CardProps) {
  const glowClass =
    glow === "green"
      ? "quantum-glow"
      : glow === "violet"
        ? "quantum-glow-violet"
        : "";

  return (
    <div
      className={`rounded-xl border border-surface-light bg-surface p-6 ${glowClass} ${className}`}
    >
      {children}
    </div>
  );
}
