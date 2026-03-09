"use client";

import Link from "next/link";
import { ArrowLeft } from "lucide-react";

const C = {
  bg: "#0a0a0f",
  surface: "#12121a",
  primary: "#00ff88",
  secondary: "#7c3aed",
  accent: "#f59e0b",
  text: "#e2e8f0",
  textMuted: "#94a3b8",
  border: "#1e293b",
};

const tradingPairs = [
  { pair: "QBC/QUSD", base: "QBC", quote: "QUSD", desc: "Native Qubitcoin against QUSD stablecoin" },
  { pair: "wETH/QUSD", base: "wETH", quote: "QUSD", desc: "Wrapped Ethereum against QUSD" },
  { pair: "wBNB/QUSD", base: "wBNB", quote: "QUSD", desc: "Wrapped BNB against QUSD" },
  { pair: "wSOL/QUSD", base: "wSOL", quote: "QUSD", desc: "Wrapped Solana against QUSD" },
  { pair: "wQBC/QUSD", base: "wQBC", quote: "QUSD", desc: "Wrapped QBC against QUSD" },
];

const apiEndpoints = [
  { method: "GET", path: "/exchange/markets", desc: "All market summaries — price, 24h volume, 24h change" },
  { method: "GET", path: "/exchange/orderbook/{pair}", desc: "Order book depth (default 20 levels, max 200)" },
  { method: "GET", path: "/exchange/book/{pair}", desc: "Full order book snapshot" },
  { method: "GET", path: "/exchange/trades/{pair}", desc: "Recent trades (default 50, max 500)" },
  { method: "GET", path: "/exchange/ohlc/{pair}", desc: "OHLC candles (1m, 5m, 15m, 1h, 4h, 1d intervals)" },
  { method: "GET", path: "/exchange/candles/{pair}", desc: "Legacy candle format (backward compatible)" },
  { method: "POST", path: "/exchange/order", desc: "Place order (pair, side, type, price, size, address)" },
  { method: "DELETE", path: "/exchange/order/{order_id}", desc: "Cancel an open order" },
  { method: "GET", path: "/exchange/orders/{address}", desc: "All open orders for an address" },
  { method: "POST", path: "/exchange/deposit", desc: "Deposit funds to exchange balance" },
  { method: "POST", path: "/exchange/withdraw", desc: "Withdraw funds from exchange" },
  { method: "GET", path: "/exchange/balance/{address}", desc: "Exchange balances for an address" },
  { method: "GET", path: "/health", desc: "Service health check" },
];

const techStack = [
  { name: "Tokio", purpose: "Async runtime for high-concurrency networking" },
  { name: "Axum", purpose: "HTTP framework for REST API and WebSocket handling" },
  { name: "rust_decimal", purpose: "Precise decimal arithmetic — no floating point rounding" },
  { name: "tower-http", purpose: "CORS middleware and request tracing" },
  { name: "sqlx", purpose: "Async CockroachDB driver for balance persistence" },
  { name: "serde", purpose: "JSON serialization and deserialization" },
  { name: "tracing", purpose: "Structured logging with span context" },
  { name: "thiserror", purpose: "Typed error handling across the engine" },
];

export default function ExchangePage() {
  return (
    <main
      className="min-h-screen p-6 md:p-12"
      style={{ background: C.bg, color: C.text, fontFamily: "Inter, system-ui, sans-serif" }}
    >
      <div className="mx-auto max-w-3xl">
        <Link
          href="/docs"
          className="mb-8 inline-flex items-center gap-2 text-sm transition-opacity hover:opacity-80"
          style={{ color: C.textMuted }}
        >
          <ArrowLeft size={14} />
          Back to Docs
        </Link>

        <h1 className="mb-2 text-3xl font-bold" style={{ fontFamily: "Space Grotesk, sans-serif" }}>
          Exchange
        </h1>
        <p className="mb-8 text-sm" style={{ color: C.textMuted }}>
          Production matching engine built in Rust — microsecond latency, price-time priority,
          and real-time market data via WebSocket
        </p>

        {/* Overview */}
        <section className="mb-8">
          <h2 className="mb-3 text-xl font-semibold" style={{ color: C.primary, fontFamily: "Space Grotesk, sans-serif" }}>
            Overview
          </h2>
          <p className="text-sm leading-relaxed" style={{ color: C.textMuted }}>
            The QBC Exchange is a high-performance order matching engine written entirely in Rust.
            It runs as a standalone binary separate from the Python node, connecting to CockroachDB
            for balance persistence and trade history. The engine uses price-time priority (FIFO at
            each price level) for fair order matching, rust_decimal for precise arithmetic with no
            floating point errors, and a thread-safe Mutex-based single-writer design for
            deterministic execution. All market data is streamed in real-time via WebSocket, and
            the REST API is fully compatible with the QBC frontend.
          </p>
        </section>

        {/* Key Stats Grid */}
        <section className="mb-8">
          <h2 className="mb-3 text-xl font-semibold" style={{ color: C.primary, fontFamily: "Space Grotesk, sans-serif" }}>
            Key Stats
          </h2>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-3">
            {[
              { label: "Language", value: "Rust" },
              { label: "Source Files", value: "11 files" },
              { label: "Lines of Code", value: "~2,185 LOC" },
              { label: "Order Matching", value: "Microsecond" },
              { label: "API Endpoints", value: "13 routes" },
              { label: "Trading Pairs", value: "5 default" },
            ].map((c) => (
              <div key={c.label} className="rounded border p-3" style={{ borderColor: C.border, background: C.surface }}>
                <p className="text-sm font-bold" style={{ color: C.accent }}>{c.value}</p>
                <p className="text-xs" style={{ color: C.textMuted }}>{c.label}</p>
              </div>
            ))}
          </div>
        </section>

        {/* Core Features */}
        <section className="mb-8">
          <h2 className="mb-3 text-xl font-semibold" style={{ color: C.primary, fontFamily: "Space Grotesk, sans-serif" }}>
            Core Features
          </h2>
          <div className="space-y-2">
            {[
              "Price-time priority matching — orders at the same price are filled in FIFO order, ensuring fairness.",
              "Self-trade prevention in cancel-oldest mode — prevents wash trading by canceling the resting order when both sides belong to the same address.",
              "Balance management with lock/unlock — open orders lock funds to guarantee settlement, released on cancel or fill.",
              "OHLC candlestick generation with synthetic backfill — produces candles at 1m, 5m, 15m, 1h, 4h, and 1d intervals, filling gaps with previous close.",
              "WebSocket real-time streaming — live order book updates, trades, and ticker data pushed to connected clients.",
              "Decimal precision via rust_decimal — all price and quantity calculations use exact decimal arithmetic, never floating point.",
              "CockroachDB persistence — balances and trade history are persisted with snapshots saved every 30 seconds.",
              "Graceful shutdown — final balance snapshot is saved on SIGTERM/SIGINT before the process exits.",
            ].map((item, i) => (
              <div key={i} className="flex items-start gap-3 rounded border p-3" style={{ borderColor: C.border, background: C.surface }}>
                <span className="mt-0.5 text-xs font-mono font-bold" style={{ color: C.secondary }}>{i + 1}</span>
                <span className="text-sm" style={{ color: C.textMuted }}>{item}</span>
              </div>
            ))}
          </div>
        </section>

        {/* Trading Pairs */}
        <section className="mb-8">
          <h2 className="mb-3 text-xl font-semibold" style={{ color: C.primary, fontFamily: "Space Grotesk, sans-serif" }}>
            Trading Pairs
          </h2>
          <p className="mb-4 text-sm" style={{ color: C.textMuted }}>
            Default markets available at launch. All pairs are quoted in QUSD. Additional pairs
            can be configured at runtime.
          </p>
          <div className="overflow-x-auto">
            <table className="w-full text-sm" style={{ borderColor: C.border }}>
              <thead>
                <tr style={{ borderBottom: `1px solid ${C.border}` }}>
                  <th className="px-3 py-2 text-left" style={{ color: C.text }}>Pair</th>
                  <th className="px-3 py-2 text-left" style={{ color: C.text }}>Base</th>
                  <th className="px-3 py-2 text-left" style={{ color: C.text }}>Quote</th>
                  <th className="px-3 py-2 text-left" style={{ color: C.text }}>Description</th>
                </tr>
              </thead>
              <tbody>
                {tradingPairs.map((p) => (
                  <tr key={p.pair} style={{ borderBottom: `1px solid ${C.border}22` }}>
                    <td className="px-3 py-2 font-mono text-xs font-bold" style={{ color: C.primary }}>{p.pair}</td>
                    <td className="px-3 py-2 font-mono text-xs" style={{ color: C.accent }}>{p.base}</td>
                    <td className="px-3 py-2 font-mono text-xs" style={{ color: C.accent }}>{p.quote}</td>
                    <td className="px-3 py-2 text-xs" style={{ color: C.textMuted }}>{p.desc}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        {/* Order Types */}
        <section className="mb-8">
          <h2 className="mb-3 text-xl font-semibold" style={{ color: C.primary, fontFamily: "Space Grotesk, sans-serif" }}>
            Order Types
          </h2>
          <div className="grid grid-cols-2 gap-3">
            <div className="rounded border p-4" style={{ borderColor: C.border, background: C.surface }}>
              <p className="mb-1 text-sm font-bold" style={{ color: C.accent }}>Limit Order</p>
              <p className="text-xs" style={{ color: C.textMuted }}>
                Specify exact price and size. Rests on the book until filled, canceled, or matched.
                Eligible for maker fee rates.
              </p>
            </div>
            <div className="rounded border p-4" style={{ borderColor: C.border, background: C.surface }}>
              <p className="mb-1 text-sm font-bold" style={{ color: C.accent }}>Market Order</p>
              <p className="text-xs" style={{ color: C.textMuted }}>
                Executes immediately at the best available price. Walks the book until the order
                is fully filled. Taker fee rates apply.
              </p>
            </div>
          </div>
        </section>

        {/* Architecture */}
        <section className="mb-8">
          <h2 className="mb-3 text-xl font-semibold" style={{ color: C.primary, fontFamily: "Space Grotesk, sans-serif" }}>
            Architecture
          </h2>
          <p className="mb-4 text-sm leading-relaxed" style={{ color: C.textMuted }}>
            The exchange runs as a standalone Rust binary, fully decoupled from the Python blockchain
            node. This separation ensures that order matching performance is not affected by block
            processing, P2P networking, or other node operations. The engine connects to CockroachDB
            for durable balance and trade storage, with balance snapshots persisted every 30 seconds.
            CORS is enabled for frontend access, and Prometheus metrics are exported for monitoring.
          </p>
          <div className="rounded border p-4 font-mono text-xs leading-relaxed" style={{ borderColor: C.border, background: C.surface, color: C.textMuted }}>
            <pre>{`┌─────────────────┐     ┌──────────────────┐
│   QBC Frontend  │────▶│  REST API (Axum) │
│   (Next.js)     │     │  13 endpoints    │
└─────────────────┘     └────────┬─────────┘
                                 │
┌─────────────────┐     ┌────────▼─────────┐
│   WebSocket     │◀────│  Matching Engine  │
│   Clients       │     │  (price-time     │
└─────────────────┘     │   priority)      │
                        └────────┬─────────┘
                                 │
                        ┌────────▼─────────┐
                        │   CockroachDB    │
                        │   (balances +    │
                        │    trade history)│
                        └──────────────────┘`}</pre>
          </div>
        </section>

        {/* REST API */}
        <section className="mb-8">
          <h2 className="mb-3 text-xl font-semibold" style={{ color: C.primary, fontFamily: "Space Grotesk, sans-serif" }}>
            REST API
          </h2>
          <p className="mb-4 text-sm" style={{ color: C.textMuted }}>
            13 endpoints for market data, order management, and balance operations. All responses
            are JSON. WebSocket streaming is available on a separate port for real-time updates.
          </p>
          <div className="overflow-x-auto">
            <table className="w-full text-sm" style={{ borderColor: C.border }}>
              <thead>
                <tr style={{ borderBottom: `1px solid ${C.border}` }}>
                  <th className="px-3 py-2 text-left" style={{ color: C.text }}>Method</th>
                  <th className="px-3 py-2 text-left" style={{ color: C.text }}>Endpoint</th>
                  <th className="px-3 py-2 text-left" style={{ color: C.text }}>Description</th>
                </tr>
              </thead>
              <tbody>
                {apiEndpoints.map((e) => (
                  <tr key={e.path + e.method} style={{ borderBottom: `1px solid ${C.border}22` }}>
                    <td className="px-3 py-2">
                      <span
                        className="rounded-full px-2 py-0.5 text-xs font-mono font-bold"
                        style={{
                          background: e.method === "GET" ? `${C.primary}20` : e.method === "POST" ? `${C.secondary}20` : `${C.accent}20`,
                          color: e.method === "GET" ? C.primary : e.method === "POST" ? C.secondary : C.accent,
                        }}
                      >
                        {e.method}
                      </span>
                    </td>
                    <td className="px-3 py-2 font-mono text-xs" style={{ color: C.primary }}>{e.path}</td>
                    <td className="px-3 py-2 text-xs" style={{ color: C.textMuted }}>{e.desc}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        {/* Fee Structure */}
        <section className="mb-8">
          <h2 className="mb-3 text-xl font-semibold" style={{ color: C.primary, fontFamily: "Space Grotesk, sans-serif" }}>
            Fee Structure
          </h2>
          <p className="mb-4 text-sm leading-relaxed" style={{ color: C.textMuted }}>
            The exchange supports configurable maker and taker fee rates. Maker fees apply to
            limit orders that add liquidity to the book. Taker fees apply to orders that remove
            liquidity (market orders or limit orders that cross the spread). All collected fees
            are directed to a configurable treasury address.
          </p>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            {[
              { label: "Maker Fee", value: "Configurable" },
              { label: "Taker Fee", value: "Configurable" },
              { label: "Fee Collection", value: "Treasury address" },
              { label: "Self-Trade", value: "Cancel-oldest" },
            ].map((s) => (
              <div key={s.label} className="rounded border p-3" style={{ borderColor: C.border, background: C.surface }}>
                <p className="text-sm font-bold" style={{ color: C.secondary }}>{s.value}</p>
                <p className="text-xs" style={{ color: C.textMuted }}>{s.label}</p>
              </div>
            ))}
          </div>
        </section>

        {/* Technology Stack */}
        <section className="mb-8">
          <h2 className="mb-3 text-xl font-semibold" style={{ color: C.primary, fontFamily: "Space Grotesk, sans-serif" }}>
            Technology Stack
          </h2>
          <p className="mb-4 text-sm" style={{ color: C.textMuted }}>
            Built with Rust for maximum performance and memory safety. All dependencies are
            production-grade crates from the Rust ecosystem.
          </p>
          <div className="overflow-x-auto">
            <table className="w-full text-sm" style={{ borderColor: C.border }}>
              <thead>
                <tr style={{ borderBottom: `1px solid ${C.border}` }}>
                  <th className="px-3 py-2 text-left" style={{ color: C.text }}>Crate</th>
                  <th className="px-3 py-2 text-left" style={{ color: C.text }}>Purpose</th>
                </tr>
              </thead>
              <tbody>
                {techStack.map((t) => (
                  <tr key={t.name} style={{ borderBottom: `1px solid ${C.border}22` }}>
                    <td className="px-3 py-2 font-mono text-xs" style={{ color: C.primary }}>{t.name}</td>
                    <td className="px-3 py-2 text-xs" style={{ color: C.textMuted }}>{t.purpose}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        {/* OHLC Candles */}
        <section className="mb-8">
          <h2 className="mb-3 text-xl font-semibold" style={{ color: C.primary, fontFamily: "Space Grotesk, sans-serif" }}>
            OHLC Candlestick Data
          </h2>
          <p className="mb-4 text-sm leading-relaxed" style={{ color: C.textMuted }}>
            The engine generates OHLC (Open, High, Low, Close) candlestick data in real-time as
            trades execute. Six intervals are supported. When no trades occur during an interval,
            synthetic candles are generated using the previous close price, ensuring continuous
            charting data without gaps.
          </p>
          <div className="grid grid-cols-3 gap-3 md:grid-cols-6">
            {["1m", "5m", "15m", "1h", "4h", "1d"].map((interval) => (
              <div key={interval} className="rounded border p-3 text-center" style={{ borderColor: C.border, background: C.surface }}>
                <p className="font-mono text-sm font-bold" style={{ color: C.accent }}>{interval}</p>
              </div>
            ))}
          </div>
        </section>

        {/* Monitoring */}
        <section>
          <h2 className="mb-3 text-xl font-semibold" style={{ color: C.primary, fontFamily: "Space Grotesk, sans-serif" }}>
            Monitoring and Reliability
          </h2>
          <p className="mb-4 text-sm leading-relaxed" style={{ color: C.textMuted }}>
            The exchange exports Prometheus metrics for integration with the Qubitcoin monitoring
            stack (Grafana dashboards). Balance snapshots are persisted to CockroachDB every 30
            seconds, and a final snapshot is saved on graceful shutdown. The Mutex-based
            single-writer design ensures deterministic order matching with no race conditions,
            while Tokio provides high-concurrency async I/O for API and WebSocket connections.
          </p>
          <div className="grid grid-cols-2 gap-3">
            {[
              { label: "Balance Snapshots", value: "Every 30 seconds" },
              { label: "Shutdown", value: "Graceful with final save" },
              { label: "Concurrency Model", value: "Single-writer Mutex" },
              { label: "Metrics", value: "Prometheus" },
            ].map((s) => (
              <div key={s.label} className="rounded border p-3" style={{ borderColor: C.border, background: C.surface }}>
                <p className="text-sm font-bold" style={{ color: C.accent }}>{s.value}</p>
                <p className="text-xs" style={{ color: C.textMuted }}>{s.label}</p>
              </div>
            ))}
          </div>
        </section>
      </div>
    </main>
  );
}
