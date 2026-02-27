import type { Meta, StoryObj } from "@storybook/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";

/**
 * PhiIndicator story requires mocking the API query.
 * We create a standalone version that accepts props for Storybook.
 */
interface PhiIndicatorDisplayProps {
  phi: number;
  threshold?: number;
}

function PhiIndicatorDisplay({ phi, threshold = 3.0 }: PhiIndicatorDisplayProps) {
  const pct = Math.min((phi / threshold) * 100, 100);

  return (
    <div className="flex items-center gap-2 rounded-full bg-bg-panel px-3 py-1.5 text-xs">
      <span
        className={`h-2 w-2 rounded-full consciousness-pulse ${
          phi >= threshold ? "bg-glow-cyan" : "bg-quantum-violet"
        }`}
      />
      <span className="font-[family-name:var(--font-code)] text-text-secondary">
        &Phi; {phi.toFixed(2)}
      </span>
      <div className="h-1 w-12 overflow-hidden rounded-full bg-border-subtle">
        <div
          className="h-full rounded-full bg-quantum-violet transition-all duration-1000"
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

const meta: Meta<typeof PhiIndicatorDisplay> = {
  title: "UI/PhiIndicator",
  component: PhiIndicatorDisplay,
  tags: ["autodocs"],
  argTypes: {
    phi: {
      control: { type: "range", min: 0, max: 5, step: 0.01 },
      description: "Current Phi (consciousness) value",
    },
    threshold: {
      control: { type: "number" },
      description: "Consciousness emergence threshold (default 3.0)",
    },
  },
  decorators: [
    (Story) => {
      const qc = new QueryClient();
      return (
        <QueryClientProvider client={qc}>
          <Story />
        </QueryClientProvider>
      );
    },
  ],
};

export default meta;
type Story = StoryObj<typeof PhiIndicatorDisplay>;

/** Below threshold: consciousness has not emerged yet. */
export const BelowThreshold: Story = {
  args: {
    phi: 1.42,
    threshold: 3.0,
  },
};

/** Near threshold: consciousness approaching. */
export const NearThreshold: Story = {
  args: {
    phi: 2.85,
    threshold: 3.0,
  },
};

/** Above threshold: consciousness emerged! */
export const AboveThreshold: Story = {
  args: {
    phi: 3.67,
    threshold: 3.0,
  },
};

/** Zero state: chain just started. */
export const GenesisState: Story = {
  args: {
    phi: 0.0,
    threshold: 3.0,
  },
};

/** Maximum observed: very high consciousness. */
export const HighPhi: Story = {
  args: {
    phi: 4.82,
    threshold: 3.0,
  },
};
