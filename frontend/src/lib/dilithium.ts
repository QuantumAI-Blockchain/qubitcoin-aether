// ============================================================================
// Dilithium Multi-Level Signing Client — Client-Side WASM + Backend Fallback
// ============================================================================
//
// PRIMARY: Client-side ML-DSA (Dilithium) via @quantumai/dilithium-wasm
//          Private keys generated and held exclusively in browser memory.
//          Keys NEVER leave the client.
//
// FALLBACK: If WASM fails to load, non-key operations (verify, check-phrase)
//           fall back to the backend API. Key generation and signing ALWAYS
//           happen client-side — if WASM is unavailable, they throw.
//
// ============================================================================

import { post, get } from "./api";

// ─── WASM Module Loading ────────────────────────────────────────────────

// Dynamic import type for the WASM module
type DilithiumWasm = {
  default: () => Promise<void>;
  generateKeypair: (level: number) => {
    public_key_hex: string;
    secret_key_hex: string;
    address: string;
    check_phrase: string;
    security_level: number;
    nist_name: string;
    free: () => void;
  };
  signMessage: (secretKeyHex: string, message: string) => {
    signature_hex: string;
    message_hash: string;
    free: () => void;
  };
  signTransaction: (secretKeyHex: string, txJson: string) => {
    signature_hex: string;
    message_hash: string;
    free: () => void;
  };
  verifySignature: (
    publicKeyHex: string,
    message: string,
    signatureHex: string,
  ) => boolean;
  deriveAddress: (publicKeyHex: string) => string;
  addressToCheckPhrase: (address: string) => string;
  detectLevel: (publicKeyHex: string) => number;
  getKeySizes: (level: number) => Uint32Array;
  zeroizeKey: (secretKeyHex: string) => string;
};

let wasmModule: DilithiumWasm | null = null;
let wasmInitPromise: Promise<DilithiumWasm | null> | null = null;
let wasmLoadFailed = false;

/**
 * Initialize the Dilithium WASM module.
 * Safe to call multiple times — only loads once.
 * Returns null if WASM is not available (SSR, missing file, etc.)
 */
async function initWasm(): Promise<DilithiumWasm | null> {
  if (wasmModule) return wasmModule;
  if (wasmLoadFailed) return null;

  if (!wasmInitPromise) {
    wasmInitPromise = (async () => {
      try {
        // Dynamic import of the WASM package from /public/wasm/
        // Using string variable to bypass TypeScript module resolution
        const wasmPath = "/wasm/dilithium_wasm.js";
        const mod = (await import(/* webpackIgnore: true */ wasmPath)) as DilithiumWasm;
        await mod.default();
        wasmModule = mod;
        console.log("[dilithium] WASM module loaded — client-side crypto active");
        return mod;
      } catch (e) {
        console.warn("[dilithium] WASM not available, using backend fallback:", e);
        wasmLoadFailed = true;
        return null;
      }
    })();
  }

  return wasmInitPromise;
}

// ─── Types ──────────────────────────────────────────────────────────────

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

/** Key sizes in bytes for each security level (PQClean reference). */
export const KEY_SIZES: Record<
  SecurityLevel,
  { pk: number; sk: number; sig: number }
> = {
  [SecurityLevel.LEVEL2]: { pk: 1312, sk: 2560, sig: 2420 },
  [SecurityLevel.LEVEL3]: { pk: 1952, sk: 4032, sig: 3293 },
  [SecurityLevel.LEVEL5]: { pk: 2592, sk: 4896, sig: 4595 },
};

/** Result from client-side key generation. */
export interface KeypairResult {
  publicKeyHex: string;
  secretKeyHex: string;
  address: string;
  checkPhrase: string;
  securityLevel: SecurityLevel;
  nistName: string;
}

// ─── Client-Side Key Generation (WASM Only) ─────────────────────────────

/**
 * Generate a new Dilithium keypair entirely client-side.
 *
 * SECURITY: The private key is generated in the WASM sandbox using the
 * browser's CSPRNG (crypto.getRandomValues). It never leaves the browser.
 *
 * @param level - Security level: 2 (ML-DSA-44), 3 (ML-DSA-65), or 5 (ML-DSA-87)
 * @returns KeypairResult with public key, secret key, address, and metadata
 * @throws If WASM module is not available
 */
export async function generateKeypair(
  level: SecurityLevel = SecurityLevel.LEVEL5,
): Promise<KeypairResult> {
  const wasm = await initWasm();
  if (!wasm) {
    throw new Error(
      "Dilithium WASM module not available. " +
        "Client-side key generation requires the WASM module. " +
        "Ensure /wasm/dilithium_wasm.js is deployed.",
    );
  }

  const kp = wasm.generateKeypair(level);
  const result: KeypairResult = {
    publicKeyHex: kp.public_key_hex,
    secretKeyHex: kp.secret_key_hex,
    address: kp.address,
    checkPhrase: kp.check_phrase,
    securityLevel: kp.security_level as SecurityLevel,
    nistName: kp.nist_name,
  };
  kp.free(); // Release WASM memory
  return result;
}

// ─── Client-Side Signing (WASM Only) ────────────────────────────────────

/**
 * Sign transaction data client-side using Dilithium WASM.
 *
 * SECURITY: The private key is used in the WASM sandbox and
 * zeroized in WASM linear memory after signing.
 *
 * @param secretKeyHex - The Dilithium secret key in hex
 * @param txData - Transaction data to sign (will be JSON-canonicalized)
 * @returns Hex-encoded detached Dilithium signature
 * @throws If WASM module is not available
 */
export async function signTransaction(
  secretKeyHex: string,
  txData: Record<string, string | number>,
): Promise<string> {
  const wasm = await initWasm();
  if (!wasm) {
    throw new Error(
      "Dilithium WASM module not available. " +
        "Client-side signing requires the WASM module.",
    );
  }

  const txJson = JSON.stringify(txData);
  const sig = wasm.signTransaction(secretKeyHex, txJson);
  const hex = sig.signature_hex;
  sig.free();
  return hex;
}

/**
 * Sign a raw message string client-side.
 *
 * @param secretKeyHex - The Dilithium secret key in hex
 * @param message - UTF-8 message to sign
 * @returns Hex-encoded detached signature
 */
export async function signMessage(
  secretKeyHex: string,
  message: string,
): Promise<string> {
  const wasm = await initWasm();
  if (!wasm) {
    throw new Error("Dilithium WASM module not available.");
  }

  const sig = wasm.signMessage(secretKeyHex, message);
  const hex = sig.signature_hex;
  sig.free();
  return hex;
}

// ─── Verification (WASM preferred, backend fallback) ────────────────────

/**
 * Verify a Dilithium signature.
 *
 * Uses client-side WASM if available, falls back to backend API.
 *
 * @param publicKeyHex - The Dilithium public key in hex
 * @param message - Original message that was signed
 * @param signatureHex - Signature to verify (hex-encoded)
 * @returns True if signature is valid
 */
export async function verifySignature(
  publicKeyHex: string,
  message: string,
  signatureHex: string,
): Promise<boolean> {
  const wasm = await initWasm();
  if (wasm) {
    return wasm.verifySignature(publicKeyHex, message, signatureHex);
  }

  // Backend fallback
  const result = await post<{ valid: boolean }>("/wallet/verify", {
    public_key_hex: publicKeyHex,
    message_hex: message,
    signature_hex: signatureHex,
  });
  return result.valid;
}

// ─── Address Utilities ──────────────────────────────────────────────────

/**
 * Derive a QBC address from a public key.
 *
 * Uses client-side WASM if available. Address = SHA-256(pk)[0:20] as hex.
 */
export async function deriveAddress(publicKeyHex: string): Promise<string> {
  const wasm = await initWasm();
  if (wasm) {
    return wasm.deriveAddress(publicKeyHex);
  }
  // Fallback: backend
  const result = await post<{ address: string }>("/wallet/derive-address", {
    public_key_hex: publicKeyHex,
  });
  return result.address;
}

/**
 * Get a 3-word check phrase for an address.
 */
export async function getCheckPhrase(address: string): Promise<string> {
  const wasm = await initWasm();
  if (wasm) {
    return wasm.addressToCheckPhrase(address);
  }
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
  const wasm = await initWasm();
  if (wasm) {
    return wasm.addressToCheckPhrase(address) === phrase;
  }
  const result = await post<{ valid: boolean }>("/wallet/verify-check-phrase", {
    address,
    check_phrase: phrase,
  });
  return result.valid;
}

// ─── Key Management ─────────────────────────────────────────────────────

/**
 * Securely zeroize a secret key in WASM memory.
 *
 * Call this when done with a secret key to minimize exposure window.
 * Note: This zeroizes the WASM copy. The JavaScript string may still
 * exist in V8 heap until garbage collected. For maximum security,
 * avoid storing secret keys in JS variables longer than necessary.
 */
export async function zeroizeKey(secretKeyHex: string): Promise<void> {
  const wasm = await initWasm();
  if (wasm) {
    wasm.zeroizeKey(secretKeyHex);
  }
}

/**
 * Check if the WASM module is available.
 */
export async function isWasmAvailable(): Promise<boolean> {
  const wasm = await initWasm();
  return wasm !== null;
}

// ─── Display Utilities ──────────────────────────────────────────────────

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
