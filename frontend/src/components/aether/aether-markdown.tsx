"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeHighlight from "rehype-highlight";
import "highlight.js/styles/github-dark.min.css";

interface AetherMarkdownProps {
  children: string;
  className?: string;
}

/**
 * Renders Aether chat responses as rich markdown with
 * syntax-highlighted code blocks, GFM tables, and quantum-themed styling.
 */
export function AetherMarkdown({ children, className = "" }: AetherMarkdownProps) {
  if (!children) return null;

  return (
    <div className={`aether-markdown ${className}`}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeHighlight]}
      >
        {children}
      </ReactMarkdown>
    </div>
  );
}
