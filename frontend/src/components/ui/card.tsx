import type { ReactNode } from "react";

interface CardProps {
  children: ReactNode;
  className?: string;
  glow?: "green" | "violet" | "none";
  variant?: "default" | "panel";
}

export function Card({ children, className = "", glow = "none", variant = "panel" }: CardProps) {
  const glowClass =
    glow === "green"
      ? "quantum-glow"
      : glow === "violet"
        ? "quantum-glow-violet"
        : "";

  const variantClass =
    variant === "panel"
      ? "panel-inset"
      : "rounded-xl border border-border-subtle bg-bg-panel";

  return (
    <div
      className={`rounded-xl p-6 ${variantClass} ${glowClass} ${className}`}
    >
      {children}
    </div>
  );
}
