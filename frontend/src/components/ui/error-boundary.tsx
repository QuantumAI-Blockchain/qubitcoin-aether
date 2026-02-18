"use client";

import { Component, type ErrorInfo, type ReactNode } from "react";

interface ErrorBoundaryProps {
  children: ReactNode;
  fallback?: ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("[ErrorBoundary]", error, info.componentStack);
  }

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      return (
        <div className="flex flex-col items-center justify-center rounded-xl border border-quantum-red/30 bg-surface p-8 text-center">
          <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-quantum-red/10">
            <svg
              viewBox="0 0 20 20"
              fill="currentColor"
              className="h-6 w-6 text-quantum-red"
            >
              <path
                fillRule="evenodd"
                d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-8-5a.75.75 0 01.75.75v4.5a.75.75 0 01-1.5 0v-4.5A.75.75 0 0110 5zm0 10a1 1 0 100-2 1 1 0 000 2z"
                clipRule="evenodd"
              />
            </svg>
          </div>
          <h3 className="font-[family-name:var(--font-heading)] text-lg font-semibold text-text-primary">
            Something went wrong
          </h3>
          <p className="mt-1 max-w-md text-sm text-text-secondary">
            {this.state.error?.message || "An unexpected error occurred."}
          </p>
          <button
            onClick={() => this.setState({ hasError: false, error: null })}
            className="mt-4 rounded-lg bg-quantum-violet/20 px-4 py-2 text-sm font-medium text-quantum-violet transition hover:bg-quantum-violet/30"
          >
            Try Again
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}
