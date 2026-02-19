"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { get } from "@/lib/api";
import { Card } from "@/components/ui/card";

interface ContractEvent {
  log_index: number;
  transaction_hash: string;
  block_number: number;
  address: string;
  topic0: string;
  topic1?: string;
  topic2?: string;
  data: string;
  timestamp: number;
}

interface EventLogResponse {
  events: ContractEvent[];
  total: number;
}

/** Well-known event topic hashes for display. */
const KNOWN_TOPICS: Record<string, string> = {
  "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef": "Transfer",
  "0x8c5be1e5ebec7d5bd14f71427d1e84f3dd0314c0f7b2291e5b200ac8c7c3b925": "Approval",
  "0x17307eab39ab6107e8899845ad3d59bd9653f200f220920489ca2b5937696c31": "ApprovalForAll",
  "0xe1fffcc4923d04b559f4d29a8bfc6cda04eb5b0d3c460751c2402c5c5cc9109c": "Deposit",
  "0x7fcf532c15f0a6db0bd6d0e038bea71d30d808c7d98cb3bf7268a95bf5081b65": "Withdrawal",
};

function truncateHash(hash: string, len = 10): string {
  if (hash.length <= len * 2 + 2) return hash;
  return `${hash.slice(0, len + 2)}...${hash.slice(-len)}`;
}

function formatTimestamp(ts: number): string {
  return new Date(ts * 1000).toLocaleString();
}

export function EventLog() {
  const [contractAddress, setContractAddress] = useState("");
  const [topicFilter, setTopicFilter] = useState("");
  const [searchAddress, setSearchAddress] = useState("");

  const { data, isLoading, isError } = useQuery({
    queryKey: ["contractEvents", searchAddress, topicFilter],
    queryFn: () => {
      const params = new URLSearchParams();
      if (topicFilter) params.set("topic0", topicFilter);
      const qs = params.toString();
      return get<EventLogResponse>(
        `/qvm/events/${searchAddress}${qs ? `?${qs}` : ""}`,
      );
    },
    enabled: !!searchAddress,
    retry: false,
  });

  function handleSearch() {
    const addr = contractAddress.trim();
    if (addr) setSearchAddress(addr);
  }

  return (
    <Card>
      <h3 className="mb-4 font-[family-name:var(--font-heading)] text-lg font-semibold">
        Event Log
      </h3>

      {/* Search */}
      <div className="space-y-3">
        <div className="flex gap-3">
          <input
            value={contractAddress}
            onChange={(e) => setContractAddress(e.target.value)}
            placeholder="Contract address (0x...)"
            className="flex-1 rounded-lg bg-void px-4 py-2.5 font-[family-name:var(--font-mono)] text-xs text-text-primary placeholder:text-text-secondary focus:outline-none focus:ring-2 focus:ring-quantum-violet/50"
          />
          <button
            onClick={handleSearch}
            disabled={!contractAddress.trim()}
            className="rounded-lg bg-quantum-green/20 px-5 py-2.5 text-sm font-medium text-quantum-green transition hover:bg-quantum-green/30 disabled:opacity-40"
          >
            Fetch
          </button>
        </div>

        {/* Topic filter */}
        <div>
          <label className="mb-1 block text-xs text-text-secondary">
            Filter by topic (optional)
          </label>
          <select
            value={topicFilter}
            onChange={(e) => setTopicFilter(e.target.value)}
            className="w-full rounded-lg bg-void px-4 py-2.5 text-sm text-text-primary focus:outline-none focus:ring-2 focus:ring-quantum-violet/50"
          >
            <option value="">All events</option>
            {Object.entries(KNOWN_TOPICS).map(([hash, name]) => (
              <option key={hash} value={hash}>
                {name}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Results */}
      {isLoading && searchAddress && (
        <p className="mt-4 text-sm text-text-secondary">Loading events...</p>
      )}
      {isError && searchAddress && (
        <p className="mt-4 text-sm text-red-400">
          Failed to load events for this contract.
        </p>
      )}

      {data && data.events.length === 0 && (
        <p className="mt-4 text-sm text-text-secondary">
          No events found for this contract.
        </p>
      )}

      {data && data.events.length > 0 && (
        <div className="mt-4 max-h-96 overflow-y-auto rounded-lg border border-surface-light bg-void">
          <table className="w-full text-xs">
            <thead className="sticky top-0 bg-void">
              <tr className="border-b border-surface-light text-left text-text-secondary">
                <th className="px-3 py-2">Block</th>
                <th className="px-3 py-2">Event</th>
                <th className="px-3 py-2">Tx Hash</th>
                <th className="px-3 py-2">Data</th>
                <th className="px-3 py-2">Time</th>
              </tr>
            </thead>
            <tbody className="font-[family-name:var(--font-mono)]">
              {data.events.map((ev) => {
                const eventName =
                  KNOWN_TOPICS[ev.topic0] ?? truncateHash(ev.topic0, 6);
                return (
                  <tr
                    key={`${ev.transaction_hash}-${ev.log_index}`}
                    className="border-b border-surface-light/30"
                  >
                    <td className="px-3 py-2 text-text-secondary">
                      {ev.block_number.toLocaleString()}
                    </td>
                    <td className="px-3 py-2 font-medium text-quantum-green">
                      {eventName}
                    </td>
                    <td className="px-3 py-2 text-quantum-violet">
                      {truncateHash(ev.transaction_hash, 8)}
                    </td>
                    <td className="max-w-[160px] truncate px-3 py-2 text-text-secondary">
                      {ev.data === "0x" ? "—" : truncateHash(ev.data, 8)}
                    </td>
                    <td className="whitespace-nowrap px-3 py-2 text-text-secondary">
                      {formatTimestamp(ev.timestamp)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          <p className="border-t border-surface-light px-3 py-2 text-xs text-text-secondary">
            {data.total} event{data.total !== 1 ? "s" : ""} total
          </p>
        </div>
      )}
    </Card>
  );
}
