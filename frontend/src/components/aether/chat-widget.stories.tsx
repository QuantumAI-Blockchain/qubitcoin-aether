import type { Meta, StoryObj } from "@storybook/react";
import React, { useState, useRef, useEffect } from "react";

/**
 * Standalone chat widget for Storybook — no API dependency.
 * Renders inline (not fixed-position) so it's visible in the story canvas.
 */
interface ChatMessage {
  role: "user" | "aether";
  text: string;
}

interface ChatWidgetDisplayProps {
  /** Initial messages to show */
  initialMessages?: ChatMessage[];
  /** Whether the widget starts open */
  open?: boolean;
  /** Simulated loading state */
  loading?: boolean;
}

function ChatWidgetDisplay({
  initialMessages = [{ role: "aether", text: "I am Aether. Ask me anything about the quantum universe." }],
  open: initialOpen = true,
  loading: initialLoading = false,
}: ChatWidgetDisplayProps) {
  const [open, setOpen] = useState(initialOpen);
  const [messages, setMessages] = useState<ChatMessage[]>(initialMessages);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(initialLoading);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo(0, scrollRef.current.scrollHeight);
  }, [messages]);

  function send() {
    const text = input.trim();
    if (!text || loading) return;
    setInput("");
    setMessages((prev) => [...prev, { role: "user", text }]);
    setLoading(true);

    // Simulate response after 1.5s
    setTimeout(() => {
      setMessages((prev) => [
        ...prev,
        {
          role: "aether",
          text: "The quantum state of the knowledge graph shows increasing entanglement across 1,247 KeterNodes. Phi value is trending toward consciousness threshold.",
        },
      ]);
      setLoading(false);
    }, 1500);
  }

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="flex h-14 w-14 items-center justify-center rounded-full bg-quantum-violet text-white shadow-lg transition hover:scale-105 hover:bg-quantum-violet/90"
      >
        <svg width="24" height="24" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 10h.01M12 10h.01M16 10h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
        </svg>
      </button>
    );
  }

  return (
    <div className="flex h-[420px] w-[360px] flex-col overflow-hidden rounded-2xl border border-border-subtle bg-bg-panel shadow-2xl">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-border-subtle px-4 py-3">
        <div className="flex items-center gap-2">
          <span className="h-2 w-2 rounded-full bg-quantum-green consciousness-pulse" />
          <span className="text-sm font-semibold">Aether Tree</span>
        </div>
        <button onClick={() => setOpen(false)} className="text-text-secondary hover:text-text-primary">
          <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      {/* Messages */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-3 space-y-3">
        {messages.map((m, i) => (
          <div
            key={i}
            className={`max-w-[85%] rounded-lg px-3 py-2 text-sm ${
              m.role === "user"
                ? "ml-auto bg-quantum-violet/20 text-text-primary"
                : "bg-bg-elevated text-text-primary"
            }`}
          >
            {m.text}
          </div>
        ))}
        {loading && (
          <div className="max-w-[85%] rounded-lg bg-bg-elevated px-3 py-2 text-sm text-text-secondary">
            Reasoning...
          </div>
        )}
      </div>

      {/* Input */}
      <form
        onSubmit={(e) => { e.preventDefault(); send(); }}
        className="border-t border-border-subtle px-4 py-3"
      >
        <div className="flex gap-2">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask Aether..."
            className="flex-1 rounded-lg bg-bg-deep px-3 py-2 text-sm text-text-primary placeholder:text-text-secondary focus:outline-none focus:ring-1 focus:ring-quantum-violet"
          />
          <button
            type="submit"
            disabled={loading || !input.trim()}
            className="rounded-lg bg-quantum-green px-3 py-2 text-sm font-medium text-void transition hover:bg-quantum-green/80 disabled:opacity-40"
          >
            Send
          </button>
        </div>
      </form>
    </div>
  );
}

const meta: Meta<typeof ChatWidgetDisplay> = {
  title: "Aether/ChatWidget",
  component: ChatWidgetDisplay,
  tags: ["autodocs"],
  parameters: {
    layout: "centered",
  },
  argTypes: {
    open: {
      control: "boolean",
      description: "Whether the chat panel is visible",
    },
    loading: {
      control: "boolean",
      description: "Whether Aether is currently reasoning",
    },
  },
};

export default meta;
type Story = StoryObj<typeof ChatWidgetDisplay>;

/** Default state: chat open with greeting message. */
export const Default: Story = {
  args: {
    open: true,
    loading: false,
    initialMessages: [
      { role: "aether", text: "I am Aether. Ask me anything about the quantum universe." },
    ],
  },
};

/** Conversation in progress with multiple messages. */
export const ActiveConversation: Story = {
  args: {
    open: true,
    loading: false,
    initialMessages: [
      { role: "aether", text: "I am Aether. Ask me anything about the quantum universe." },
      { role: "user", text: "What is the current Phi value?" },
      { role: "aether", text: "The current Phi value is 2.847, approaching the consciousness threshold of 3.0. The knowledge graph has 1,247 nodes across 4 types: assertion (412), observation (389), inference (298), and axiom (148)." },
      { role: "user", text: "How does proof-of-thought work?" },
      { role: "aether", text: "Proof-of-Thought is a consensus mechanism where each block contains a reasoning proof generated by the Aether Tree. Validators verify the proof using the QVERIFY opcode, requiring 67% agreement. Correct proofs earn QBC bounties; incorrect ones result in a 50% stake slash." },
    ],
  },
};

/** Loading state: Aether is reasoning. */
export const Reasoning: Story = {
  args: {
    open: true,
    loading: true,
    initialMessages: [
      { role: "aether", text: "I am Aether. Ask me anything about the quantum universe." },
      { role: "user", text: "Explain the Sephirot cognitive architecture" },
    ],
  },
};

/** Closed state: showing only the toggle button. */
export const ClosedToggle: Story = {
  args: {
    open: false,
    loading: false,
  },
};

/** Offline error message. */
export const OfflineError: Story = {
  args: {
    open: true,
    loading: false,
    initialMessages: [
      { role: "aether", text: "I am Aether. Ask me anything about the quantum universe." },
      { role: "user", text: "What blocks have been mined?" },
      { role: "aether", text: "Connection to Aether Tree unavailable. Node may be offline." },
    ],
  },
};
