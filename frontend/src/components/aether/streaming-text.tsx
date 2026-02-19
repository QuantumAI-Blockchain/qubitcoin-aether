"use client";

import { useState, useEffect, useRef } from "react";

interface StreamingTextProps {
  text: string;
  speed?: number;
  onComplete?: () => void;
  className?: string;
}

/**
 * Typewriter streaming effect for Aether chat responses.
 * Reveals text character-by-character, then shows the full text once complete.
 */
export function StreamingText({
  text,
  speed = 18,
  onComplete,
  className = "",
}: StreamingTextProps) {
  const [displayed, setDisplayed] = useState("");
  const [done, setDone] = useState(false);
  const indexRef = useRef(0);
  const textRef = useRef(text);

  // Reset when text changes
  useEffect(() => {
    if (text !== textRef.current) {
      textRef.current = text;
      indexRef.current = 0;
      setDisplayed("");
      setDone(false);
    }
  }, [text]);

  useEffect(() => {
    if (done) return;

    const interval = setInterval(() => {
      const idx = indexRef.current;
      if (idx >= text.length) {
        setDone(true);
        clearInterval(interval);
        onComplete?.();
        return;
      }

      // Advance by 1-3 chars per tick for natural feel
      const chunk = text[idx] === " " ? 2 : 1;
      const end = Math.min(idx + chunk, text.length);
      indexRef.current = end;
      setDisplayed(text.slice(0, end));
    }, speed);

    return () => clearInterval(interval);
  }, [text, speed, done, onComplete]);

  return (
    <span className={className}>
      {done ? text : displayed}
      {!done && (
        <span className="ml-0.5 inline-block h-4 w-0.5 animate-pulse bg-quantum-green" />
      )}
    </span>
  );
}
