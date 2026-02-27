import type { Meta, StoryObj } from "@storybook/react";
import { Card } from "./card";

const meta: Meta<typeof Card> = {
  title: "UI/Card",
  component: Card,
  tags: ["autodocs"],
  argTypes: {
    glow: {
      control: "select",
      options: ["none", "green", "violet"],
      description: "Glow effect applied to the card border/shadow",
    },
    variant: {
      control: "select",
      options: ["default", "panel"],
      description: "Card visual variant",
    },
    className: {
      control: "text",
      description: "Additional CSS classes",
    },
  },
};

export default meta;
type Story = StoryObj<typeof Card>;

/** Default panel card with no glow effect. */
export const Default: Story = {
  args: {
    glow: "none",
    variant: "panel",
    children: (
      <div>
        <h3 className="mb-2 text-lg font-semibold">Quantum State</h3>
        <p className="text-sm text-text-secondary">
          4-qubit VQE ansatz with 12 variational parameters.
          Ground state energy: -1.2847 Ha.
        </p>
      </div>
    ),
  },
};

/** Card with quantum green glow (consciousness theme). */
export const GreenGlow: Story = {
  args: {
    glow: "green",
    variant: "panel",
    children: (
      <div>
        <h3 className="mb-2 text-lg font-semibold glow-cyan">
          Consciousness Active
        </h3>
        <p className="text-sm text-text-secondary">
          Phi value: 3.142 — above consciousness threshold.
          Knowledge graph: 1,247 nodes, 3,891 edges.
        </p>
      </div>
    ),
  },
};

/** Card with quantum violet glow (entanglement theme). */
export const VioletGlow: Story = {
  args: {
    glow: "violet",
    variant: "panel",
    children: (
      <div>
        <h3 className="mb-2 text-lg font-semibold text-quantum-violet">
          Entanglement Bridge
        </h3>
        <p className="text-sm text-text-secondary">
          Cross-chain quantum entanglement active. Bridge to ETH
          verified with QBRIDGE_VERIFY opcode.
        </p>
      </div>
    ),
  },
};

/** Default variant card (non-panel). */
export const DefaultVariant: Story = {
  args: {
    glow: "none",
    variant: "default",
    children: (
      <div>
        <h3 className="mb-2 text-lg font-semibold">Block #42,891</h3>
        <p className="text-sm text-text-secondary">
          Mined 3.3s ago. 12 transactions. Reward: 15.27 QBC.
        </p>
      </div>
    ),
  },
};

/** Card with complex content layout. */
export const WithStats: Story = {
  args: {
    glow: "green",
    variant: "panel",
    className: "max-w-md",
    children: (
      <div>
        <h3 className="mb-4 text-sm font-semibold text-text-secondary">
          Network Stats
        </h3>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <p className="text-xs text-text-secondary">Block Height</p>
            <p className="text-xl font-bold glow-cyan">42,891</p>
          </div>
          <div>
            <p className="text-xs text-text-secondary">Active Peers</p>
            <p className="text-xl font-bold glow-cyan">24</p>
          </div>
          <div>
            <p className="text-xs text-text-secondary">Total Supply</p>
            <p className="text-xl font-bold glow-gold">33.65M QBC</p>
          </div>
          <div>
            <p className="text-xs text-text-secondary">Difficulty</p>
            <p className="text-xl font-bold glow-cyan">1.0472</p>
          </div>
        </div>
      </div>
    ),
  },
};
