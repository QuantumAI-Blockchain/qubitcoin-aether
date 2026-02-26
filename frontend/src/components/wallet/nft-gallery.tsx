"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { get } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { useWalletStore } from "@/stores/wallet-store";

/* --- Types --- */

interface NFTItem {
  token_id: string;
  contract_address: string;
  name: string;
  description: string;
  image_url: string;
  collection_name: string;
  owner: string;
  metadata_uri: string;
}

interface NFTResponse {
  nfts: NFTItem[];
  total: number;
}

/* --- Helpers --- */

function truncateAddr(addr: string, len = 6): string {
  if (addr.length <= len * 2 + 2) return addr;
  return `${addr.slice(0, len + 2)}...${addr.slice(-len)}`;
}

/* --- NFT Card --- */

function NFTCard({
  nft,
  onSelect,
}: {
  nft: NFTItem;
  onSelect: (nft: NFTItem) => void;
}) {
  const [imgError, setImgError] = useState(false);

  return (
    <button
      onClick={() => onSelect(nft)}
      className="group w-full overflow-hidden rounded-xl border border-border-subtle bg-bg-panel transition hover:border-quantum-violet/50 hover:shadow-lg hover:shadow-quantum-violet/10 text-left"
    >
      {/* Image */}
      <div className="relative aspect-square w-full overflow-hidden bg-bg-deep">
        {nft.image_url && !imgError ? (
          <img
            src={nft.image_url}
            alt={nft.name}
            className="h-full w-full object-cover transition group-hover:scale-105"
            onError={() => setImgError(true)}
            loading="lazy"
          />
        ) : (
          <div className="flex h-full items-center justify-center">
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              className="h-12 w-12 text-surface-light"
            >
              <rect
                x="3"
                y="3"
                width="18"
                height="18"
                rx="2"
                strokeWidth={1.5}
              />
              <path
                d="M3 16l5-5 4 4 3-3 6 6"
                strokeWidth={1.5}
                strokeLinecap="round"
                strokeLinejoin="round"
              />
              <circle cx="8.5" cy="8.5" r="1.5" strokeWidth={1.5} />
            </svg>
          </div>
        )}
      </div>

      {/* Info */}
      <div className="p-3">
        <p className="text-sm font-semibold text-text-primary truncate">
          {nft.name || `#${nft.token_id}`}
        </p>
        <p className="text-xs text-text-secondary truncate">
          {nft.collection_name}
        </p>
      </div>
    </button>
  );
}

/* --- Detail Modal --- */

function NFTDetail({
  nft,
  onClose,
}: {
  nft: NFTItem;
  onClose: () => void;
}) {
  const [imgError, setImgError] = useState(false);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-bg-deep/80 backdrop-blur-sm p-4">
      <div className="w-full max-w-lg rounded-2xl border border-border-subtle bg-bg-panel p-6">
        <div className="flex items-start justify-between mb-4">
          <div>
            <h3 className="font-[family-name:var(--font-display)] text-xl font-bold">
              {nft.name || `Token #${nft.token_id}`}
            </h3>
            <p className="text-sm text-text-secondary">
              {nft.collection_name}
            </p>
          </div>
          <button
            onClick={onClose}
            className="rounded-lg p-1.5 text-text-secondary hover:bg-border-subtle hover:text-text-primary"
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" className="h-5 w-5">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Image */}
        <div className="mb-4 aspect-square w-full overflow-hidden rounded-xl bg-bg-deep">
          {nft.image_url && !imgError ? (
            <img
              src={nft.image_url}
              alt={nft.name}
              className="h-full w-full object-cover"
              onError={() => setImgError(true)}
            />
          ) : (
            <div className="flex h-full items-center justify-center">
              <svg
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                className="h-16 w-16 text-surface-light"
              >
                <rect x="3" y="3" width="18" height="18" rx="2" strokeWidth={1.5} />
                <path d="M3 16l5-5 4 4 3-3 6 6" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </div>
          )}
        </div>

        {/* Details */}
        <div className="space-y-2">
          {nft.description && (
            <p className="text-sm text-text-secondary">{nft.description}</p>
          )}
          <div className="space-y-1 rounded-lg bg-bg-deep p-3">
            <div className="flex justify-between">
              <span className="text-xs text-text-secondary">Token ID</span>
              <span className="font-[family-name:var(--font-code)] text-xs text-quantum-green">
                #{nft.token_id}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-xs text-text-secondary">Contract</span>
              <span className="font-[family-name:var(--font-code)] text-xs text-quantum-violet">
                {truncateAddr(nft.contract_address)}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-xs text-text-secondary">Owner</span>
              <span className="font-[family-name:var(--font-code)] text-xs">
                {truncateAddr(nft.owner)}
              </span>
            </div>
            {nft.metadata_uri && (
              <div className="flex justify-between">
                <span className="text-xs text-text-secondary">Metadata</span>
                <span className="font-[family-name:var(--font-code)] text-xs text-text-secondary truncate max-w-[200px]">
                  {nft.metadata_uri}
                </span>
              </div>
            )}
          </div>
        </div>

        <button
          onClick={onClose}
          className="mt-4 w-full rounded-lg bg-border-subtle py-2.5 text-sm font-medium text-text-primary transition hover:bg-border-subtle/80"
        >
          Close
        </button>
      </div>
    </div>
  );
}

/* --- Main gallery --- */

export function NFTGallery() {
  const { address } = useWalletStore();
  const [selectedNFT, setSelectedNFT] = useState<NFTItem | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["nfts", address],
    queryFn: () =>
      get<NFTResponse>(`/qvm/nfts/${address}`),
    enabled: !!address,
    refetchInterval: 30_000,
    retry: false,
  });

  const nfts = data?.nfts ?? [];

  return (
    <Card>
      <h3 className="mb-4 font-[family-name:var(--font-display)] text-lg font-semibold">
        QBC-721 NFT Gallery
      </h3>

      {!address && (
        <p className="text-sm text-text-secondary">
          Connect your wallet to view NFTs.
        </p>
      )}

      {address && isLoading && (
        <p className="text-sm text-text-secondary">Loading NFTs...</p>
      )}

      {address && !isLoading && nfts.length === 0 && (
        <p className="text-sm text-text-secondary">
          No QBC-721 NFTs found in this wallet.
        </p>
      )}

      {nfts.length > 0 && (
        <>
          <p className="mb-3 text-xs text-text-secondary">
            {data?.total} NFT{data?.total !== 1 ? "s" : ""} owned
          </p>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
            {nfts.map((nft) => (
              <NFTCard
                key={`${nft.contract_address}-${nft.token_id}`}
                nft={nft}
                onSelect={setSelectedNFT}
              />
            ))}
          </div>
        </>
      )}

      {selectedNFT && (
        <NFTDetail nft={selectedNFT} onClose={() => setSelectedNFT(null)} />
      )}
    </Card>
  );
}
