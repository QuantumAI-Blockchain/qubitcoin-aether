"use client";

import { motion, AnimatePresence } from "framer-motion";

interface ConfirmModalProps {
  open: boolean;
  title: string;
  description: string;
  confirmLabel?: string;
  cancelLabel?: string;
  variant?: "default" | "danger";
  loading?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

export function ConfirmModal({
  open,
  title,
  description,
  confirmLabel = "Confirm",
  cancelLabel = "Cancel",
  variant = "default",
  loading = false,
  onConfirm,
  onCancel,
}: ConfirmModalProps) {
  const confirmColor =
    variant === "danger"
      ? "bg-glow-crimson/20 text-glow-crimson hover:bg-glow-crimson/30"
      : "bg-glow-cyan/20 text-glow-cyan hover:bg-glow-cyan/30";

  return (
    <AnimatePresence>
      {open && (
        <>
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 bg-bg-deep/60 backdrop-blur-sm"
            onClick={onCancel}
          />

          {/* Modal */}
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: 10 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 10 }}
            transition={{ duration: 0.15 }}
            className="fixed inset-0 z-50 flex items-center justify-center p-4"
          >
            <div
              className="panel-inset w-full max-w-md p-6 shadow-2xl"
              onClick={(e) => e.stopPropagation()}
            >
              <h2 className="font-[family-name:var(--font-display)] text-lg font-semibold">
                {title}
              </h2>
              <p className="mt-2 font-[family-name:var(--font-reading)] text-sm leading-relaxed text-text-secondary">{description}</p>

              <div className="mt-6 flex justify-end gap-3">
                <button
                  onClick={onCancel}
                  disabled={loading}
                  className="rounded-lg px-4 py-2 text-sm font-medium text-text-secondary transition hover:bg-border-subtle hover:text-text-primary disabled:opacity-40"
                >
                  {cancelLabel}
                </button>
                <button
                  onClick={onConfirm}
                  disabled={loading}
                  className={`rounded-lg px-4 py-2 text-sm font-medium transition disabled:opacity-40 ${confirmColor}`}
                  style={variant === "default" ? { boxShadow: "0 0 12px rgba(0,212,255,0.2)" } : { boxShadow: "0 0 12px rgba(220,38,38,0.2)" }}
                >
                  {loading ? "Processing..." : confirmLabel}
                </button>
              </div>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
