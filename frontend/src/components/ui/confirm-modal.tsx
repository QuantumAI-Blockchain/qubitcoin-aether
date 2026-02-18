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
      ? "bg-quantum-red/20 text-quantum-red hover:bg-quantum-red/30"
      : "bg-quantum-green/20 text-quantum-green hover:bg-quantum-green/30";

  return (
    <AnimatePresence>
      {open && (
        <>
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 bg-void/60 backdrop-blur-sm"
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
              className="w-full max-w-md rounded-xl border border-surface-light bg-surface p-6 shadow-2xl"
              onClick={(e) => e.stopPropagation()}
            >
              <h2 className="font-[family-name:var(--font-heading)] text-lg font-semibold">
                {title}
              </h2>
              <p className="mt-2 text-sm leading-relaxed text-text-secondary">{description}</p>

              <div className="mt-6 flex justify-end gap-3">
                <button
                  onClick={onCancel}
                  disabled={loading}
                  className="rounded-lg px-4 py-2 text-sm font-medium text-text-secondary transition hover:bg-surface-light hover:text-text-primary disabled:opacity-40"
                >
                  {cancelLabel}
                </button>
                <button
                  onClick={onConfirm}
                  disabled={loading}
                  className={`rounded-lg px-4 py-2 text-sm font-medium transition disabled:opacity-40 ${confirmColor}`}
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
