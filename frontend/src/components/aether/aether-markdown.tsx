"use client";

import React from "react";
import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeHighlight from "rehype-highlight";
import "highlight.js/styles/github-dark.min.css";

// SECURITY: Do NOT add rehype-raw — it would bypass ReactMarkdown's
// default HTML sanitization and enable XSS via user-injected markdown.

interface AetherMarkdownProps {
  children: string;
  className?: string;
}

/** Custom components: external links open in new tab with noopener. */
const components: Components = {
  a: ({ href, children, ...props }) => {
    const isExternal = href?.startsWith("http");
    return (
      <a
        href={href}
        {...(isExternal ? { target: "_blank", rel: "noopener noreferrer" } : {})}
        {...props}
      >
        {children}
      </a>
    );
  },
};

/**
 * Renders Aether chat responses as rich markdown with
 * syntax-highlighted code blocks, GFM tables, and quantum-themed styling.
 */
export const AetherMarkdown = React.memo(function AetherMarkdown({
  children,
  className = "",
}: AetherMarkdownProps) {
  if (!children) return null;

  return (
    <div className={`aether-markdown ${className}`}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeHighlight]}
        components={components}
      >
        {children}
      </ReactMarkdown>
    </div>
  );
});
