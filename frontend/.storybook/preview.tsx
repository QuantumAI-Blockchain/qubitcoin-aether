import type { Preview } from "@storybook/react";
import React from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { NextIntlClientProvider } from "next-intl";
import "../src/styles/globals.css";

// Import English messages for Storybook previews
import enMessages from "../src/i18n/messages/en.json";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: false,
      refetchOnWindowFocus: false,
    },
  },
});

const preview: Preview = {
  parameters: {
    backgrounds: {
      default: "quantum-dark",
      values: [
        { name: "quantum-dark", value: "#020408" },
        { name: "quantum-panel", value: "#040c14" },
        { name: "light", value: "#f8fafc" },
      ],
    },
    controls: {
      matchers: {
        color: /(background|color)$/i,
        date: /Date$/i,
      },
    },
    layout: "centered",
  },
  decorators: [
    (Story) => (
      <QueryClientProvider client={queryClient}>
        <NextIntlClientProvider locale="en" messages={enMessages}>
          <div
            className="min-h-[200px] p-8"
            style={{
              backgroundColor: "var(--color-bg-deep, #020408)",
              color: "var(--color-text-primary, #e2e8f0)",
              fontFamily: "Inter, system-ui, sans-serif",
            }}
          >
            <Story />
          </div>
        </NextIntlClientProvider>
      </QueryClientProvider>
    ),
  ],
};

export default preview;
