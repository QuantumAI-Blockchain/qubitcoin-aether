"use client";

import dynamic from "next/dynamic";

const QBCExchange = dynamic(
  () => import("@/components/exchange/QBCExchange"),
  { ssr: false },
);

export function ExchangeClient() {
  return <QBCExchange />;
}
