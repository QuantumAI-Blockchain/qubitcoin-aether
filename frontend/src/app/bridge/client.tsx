"use client";

import dynamic from "next/dynamic";

const QBCBridge = dynamic(() => import("@/components/bridge/QBCBridge"), {
  ssr: false,
  loading: () => (
    <div className="flex min-h-screen items-center justify-center" style={{ background: "#020408" }}>
      <div className="text-center">
        <div className="mx-auto h-12 w-12 animate-spin rounded-full border-2 border-[#0d2a44] border-t-[#00d4ff]" />
        <p
          className="mt-4 text-sm tracking-widest"
          style={{ color: "#5a8fa8", fontFamily: "'Orbitron', sans-serif" }}
        >
          INITIALIZING BRIDGE
        </p>
      </div>
    </div>
  ),
});

export function BridgeClient() {
  return <QBCBridge />;
}
