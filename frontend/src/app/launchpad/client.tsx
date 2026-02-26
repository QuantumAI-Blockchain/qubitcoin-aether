"use client";

import dynamic from "next/dynamic";

const QBCLaunchpad = dynamic(
  () => import("@/components/launchpad/QBCLaunchpad"),
  { ssr: false },
);

export function LaunchpadClient() {
  return <QBCLaunchpad />;
}
