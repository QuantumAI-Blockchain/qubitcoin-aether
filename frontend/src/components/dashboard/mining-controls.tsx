"use client";

import { useState } from "react";
import { Card } from "@/components/ui/card";
import { useToast } from "@/components/ui/toast";
import { ConfirmModal } from "@/components/ui/confirm-modal";
import { post } from "@/lib/api";

interface MiningControlsProps {
  isActive: boolean;
}

export function MiningControls({ isActive }: MiningControlsProps) {
  const [pending, setPending] = useState(false);
  const [confirm, setConfirm] = useState<"start" | "stop" | null>(null);
  const { toast } = useToast();

  async function handleAction(action: "start" | "stop") {
    setPending(true);
    try {
      await post(`/mining/${action}`, {});
      toast(`Mining ${action === "start" ? "started" : "stopped"}`, "success");
    } catch {
      toast(`Failed to ${action} mining`, "error");
    } finally {
      setPending(false);
      setConfirm(null);
    }
  }

  return (
    <>
      <Card>
        <h3 className="mb-3 text-sm font-semibold text-text-secondary">Mining Controls</h3>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <span
              className={`inline-block h-2.5 w-2.5 rounded-full ${
                isActive ? "bg-quantum-green consciousness-pulse" : "bg-text-secondary/40"
              }`}
            />
            <span className="text-sm font-medium">
              {isActive ? "Mining Active" : "Mining Stopped"}
            </span>
          </div>
          <div className="ml-auto flex gap-2">
            <button
              onClick={() => setConfirm("start")}
              disabled={pending || isActive}
              className="rounded-lg bg-quantum-green/20 px-4 py-2 text-sm font-medium text-quantum-green transition hover:bg-quantum-green/30 disabled:opacity-40"
            >
              Start
            </button>
            <button
              onClick={() => setConfirm("stop")}
              disabled={pending || !isActive}
              className="rounded-lg bg-quantum-red/20 px-4 py-2 text-sm font-medium text-quantum-red transition hover:bg-quantum-red/30 disabled:opacity-40"
            >
              Stop
            </button>
          </div>
        </div>
      </Card>

      <ConfirmModal
        open={confirm !== null}
        title={confirm === "start" ? "Start Mining" : "Stop Mining"}
        description={
          confirm === "start"
            ? "This will begin VQE mining on this node. The node will start solving SUSY Hamiltonians and creating blocks."
            : "This will stop the mining process on this node. No new blocks will be created until mining is restarted."
        }
        confirmLabel={confirm === "start" ? "Start Mining" : "Stop Mining"}
        variant={confirm === "stop" ? "danger" : "default"}
        loading={pending}
        onConfirm={() => confirm && handleAction(confirm)}
        onCancel={() => setConfirm(null)}
      />
    </>
  );
}
