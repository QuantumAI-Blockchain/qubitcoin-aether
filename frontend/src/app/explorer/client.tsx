"use client";

import dynamic from "next/dynamic";

const QBCExplorer = dynamic(() => import("@/components/explorer/QBCExplorer"), {
  ssr: false,
  loading: () => (
    <div className="flex min-h-screen items-center justify-center bg-[#020408]">
      <div className="text-center">
        <div className="mx-auto h-12 w-12 animate-spin rounded-full border-2 border-[#0d2a44] border-t-[#00d4ff]" />
        <p
          className="mt-4 text-sm tracking-widest text-[#5a8fa8]"
          style={{ fontFamily: "'Orbitron', sans-serif" }}
        >
          INITIALIZING EXPLORER
        </p>
      </div>
    </div>
  ),
});

export function ExplorerClient() {
  return <QBCExplorer />;
}
