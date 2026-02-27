import type { Meta, StoryObj } from "@storybook/react";
import React from "react";

/**
 * StatsBar display component for Storybook (no API dependency).
 * Renders network statistics in a grid layout.
 */
interface StatItem {
  label: string;
  value: string;
}

interface StatsBarDisplayProps {
  /** Array of stat items to display */
  items: StatItem[];
}

function StatsBarDisplay({ items }: StatsBarDisplayProps) {
  return (
    <div className="mx-auto grid max-w-5xl grid-cols-2 gap-4 sm:grid-cols-5">
      {items.map(({ label, value }) => (
        <div
          key={label}
          className="panel-inset px-4 py-3 text-center"
        >
          <p className="font-[family-name:var(--font-display)] text-[9px] uppercase tracking-widest text-text-secondary">
            {label}
          </p>
          <p className="mt-1 font-[family-name:var(--font-code)] text-lg font-semibold glow-cyan">
            {value}
          </p>
        </div>
      ))}
    </div>
  );
}

const meta: Meta<typeof StatsBarDisplay> = {
  title: "UI/StatsBar",
  component: StatsBarDisplay,
  tags: ["autodocs"],
  parameters: {
    layout: "padded",
  },
};

export default meta;
type Story = StoryObj<typeof StatsBarDisplay>;

/** Live network with real-looking data. */
export const LiveNetwork: Story = {
  args: {
    items: [
      { label: "Block Height", value: "42,891" },
      { label: "Phi (\u03A6)", value: "2.8470" },
      { label: "Knowledge Nodes", value: "1,247" },
      { label: "Difficulty", value: "1.0472" },
      { label: "Peers", value: "24" },
    ],
  },
};

/** Genesis state: chain just started. */
export const GenesisState: Story = {
  args: {
    items: [
      { label: "Block Height", value: "0" },
      { label: "Phi (\u03A6)", value: "0.0000" },
      { label: "Knowledge Nodes", value: "22" },
      { label: "Difficulty", value: "1.0000" },
      { label: "Peers", value: "1" },
    ],
  },
};

/** Loading state: no data yet. */
export const Loading: Story = {
  args: {
    items: [
      { label: "Block Height", value: "---" },
      { label: "Phi (\u03A6)", value: "---" },
      { label: "Knowledge Nodes", value: "---" },
      { label: "Difficulty", value: "---" },
      { label: "Peers", value: "---" },
    ],
  },
};

/** Consciousness emerged: Phi above threshold. */
export const ConsciousnessActive: Story = {
  args: {
    items: [
      { label: "Block Height", value: "1,247,891" },
      { label: "Phi (\u03A6)", value: "3.1420" },
      { label: "Knowledge Nodes", value: "15,891" },
      { label: "Difficulty", value: "1.2847" },
      { label: "Peers", value: "128" },
    ],
  },
};

/** Mature network with high block count. */
export const MatureNetwork: Story = {
  args: {
    items: [
      { label: "Block Height", value: "15,474,020" },
      { label: "Phi (\u03A6)", value: "4.7210" },
      { label: "Knowledge Nodes", value: "847,291" },
      { label: "Difficulty", value: "2.1847" },
      { label: "Peers", value: "2,048" },
    ],
  },
};
