// ============================================================================
// Dilithium Multi-Level Signing Client
// ============================================================================
//
// All signing operations are delegated to the backend (POST /wallet/sign).
// No client-side cryptography — the backend handles Dilithium at all levels
// (ML-DSA-44/65/87) via the Python dilithium-py library.
//
// This module provides:
// 1. Type definitions for security levels
// 2. API-backed sign/verify functions
// 3. Check-phrase display utilities
//
// ============================================================================

import { post, get } from "./api";

/** Dilithium security levels matching NIST ML-DSA standards. */
export enum SecurityLevel {
  LEVEL2 = 2, // ML-DSA-44 (128-bit classical, 64-bit quantum)
  LEVEL3 = 3, // ML-DSA-65 (192-bit classical, 96-bit quantum)
  LEVEL5 = 5, // ML-DSA-87 (256-bit classical, 128-bit quantum)
}

/** Human-readable NIST names for each level. */
export const LEVEL_NAMES: Record<SecurityLevel, string> = {
  [SecurityLevel.LEVEL2]: "ML-DSA-44",
  [SecurityLevel.LEVEL3]: "ML-DSA-65",
  [SecurityLevel.LEVEL5]: "ML-DSA-87",
};

/** Key sizes in bytes for each security level. */
export const KEY_SIZES: Record<
  SecurityLevel,
  { pk: number; sk: number; sig: number }
> = {
  [SecurityLevel.LEVEL2]: { pk: 1312, sk: 2528, sig: 2420 },
  [SecurityLevel.LEVEL3]: { pk: 1952, sk: 4000, sig: 3293 },
  [SecurityLevel.LEVEL5]: { pk: 2592, sk: 4864, sig: 4595 },
};

/**
 * Sign transaction data via backend API.
 *
 * @param privateKeyHex - The Dilithium private key in hex
 * @param txData - Transaction data to sign (serialized to JSON)
 * @returns Hex-encoded Dilithium signature
 */
export async function signTransaction(
  privateKeyHex: string,
  txData: Record<string, string | number>,
): Promise<string> {
  const result = await post<{ signature_hex: string }>("/wallet/sign", {
    private_key_hex: privateKeyHex,
    data: txData,
  });
  return result.signature_hex;
}

/**
 * Verify a signature via backend API.
 *
 * Security level is auto-detected from public key size.
 *
 * @param publicKeyHex - The Dilithium public key in hex
 * @param message - Original message bytes (hex-encoded)
 * @param signatureHex - Signature to verify (hex-encoded)
 * @returns True if signature is valid
 */
export async function verifySignature(
  publicKeyHex: string,
  message: string,
  signatureHex: string,
): Promise<boolean> {
  const result = await post<{ valid: boolean }>("/wallet/verify", {
    public_key_hex: publicKeyHex,
    message_hex: message,
    signature_hex: signatureHex,
  });
  return result.valid;
}

/**
 * Get the check-phrase for an address.
 *
 * Check-phrases are 3 BIP-39 words that serve as a human-readable
 * alias for hex addresses, making it easy to verify addresses verbally.
 *
 * @param address - QBC hex address (40 chars)
 * @returns Hyphenated check-phrase (e.g., "tiger-ocean-marble")
 */
export async function getCheckPhrase(address: string): Promise<string> {
  const result = await get<{ check_phrase: string }>(
    `/wallet/check-phrase/${address}`,
  );
  return result.check_phrase;
}

/**
 * Verify a check-phrase matches an address.
 */
export async function verifyCheckPhrase(
  address: string,
  phrase: string,
): Promise<boolean> {
  const result = await post<{ valid: boolean }>("/wallet/verify-check-phrase", {
    address,
    check_phrase: phrase,
  });
  return result.valid;
}

/**
 * Get crypto system info from the backend.
 */
export async function getCryptoInfo(): Promise<{
  algorithm: string;
  nist_name: string;
  security_level: string;
  pk_size: number;
  sk_size: number;
  sig_size: number;
}> {
  return get("/crypto/info");
}

/**
 * Format a security level for display.
 */
export function formatSecurityLevel(level: SecurityLevel): string {
  return `${LEVEL_NAMES[level]} (Level ${level})`;
}

/**
 * Detect security level from public key hex length.
 */
export function detectLevelFromPkHex(pkHex: string): SecurityLevel | null {
  const byteLen = pkHex.length / 2;
  if (byteLen === 1312) return SecurityLevel.LEVEL2;
  if (byteLen === 1952) return SecurityLevel.LEVEL3;
  if (byteLen === 2592) return SecurityLevel.LEVEL5;
  return null;
}
