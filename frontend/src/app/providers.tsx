"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState, useEffect, type ReactNode } from "react";
import { ToastProvider } from "@/components/ui/toast";
import { ChainSocketProvider } from "@/components/chain-socket-provider";
import { useKeyboardShortcuts } from "@/hooks/use-keyboard-shortcuts";
import { installGlobalErrorHandlers } from "@/lib/error-reporter";
import { ServiceWorkerRegister } from "@/components/service-worker-register";

function KeyboardShortcuts() {
  useKeyboardShortcuts();
  return null;
}

function ErrorHandlerInit() {
  useEffect(() => {
    installGlobalErrorHandlers();
  }, []);
  return null;
}

export function Providers({ children }: { children: ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: { staleTime: 3_300, refetchInterval: 10_000, retry: 2 },
        },
      }),
  );

  return (
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <KeyboardShortcuts />
        <ErrorHandlerInit />
        <ServiceWorkerRegister />
        <ChainSocketProvider>{children}</ChainSocketProvider>
      </ToastProvider>
    </QueryClientProvider>
  );
}
