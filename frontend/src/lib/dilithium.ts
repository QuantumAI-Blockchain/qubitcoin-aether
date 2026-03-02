// ============================================================================
// SECURITY: PLACEHOLDER — NOT REAL SIGNING
// ============================================================================
//
// This module uses HMAC-SHA256 with the PUBLIC KEY as the HMAC secret.
// This is NOT cryptographic signing — anyone who knows the public key can
// forge signatures.  It exists solely as a development placeholder until a
// real Dilithium2 WASM signing module is integrated.
//
// BEFORE PRODUCTION you MUST replace the internals of
// `placeholderSignTransaction()` with real Dilithium2 WASM signing
// (e.g. compiled from liboqs via wasm-pack).  The function signature stays
// the same — only the internal signing primitive changes.
//
// Reference WASM builds:
//   - https://github.com/nicoburniske/pqc-wasm
//   - https://github.com/nicoburniske/dilithium-wasm
//
// DO NOT ship this placeholder to production.
// ============================================================================

/**
 * PLACEHOLDER: Sign transaction data using HMAC-SHA256 (NOT real signing).
 *
 * @deprecated This is a mock implementation. Replace with Dilithium2 WASM
 *   signing before production. Anyone with the public key can forge these
 *   signatures.
 *
 * @param publicKeyHex - The user's Dilithium public key in hex.
 * @param txData - Transaction data to sign.
 * @returns Hex-encoded HMAC-SHA256 output (32 bytes). NOT a real signature.
 */
export async function placeholderSignTransaction(
  publicKeyHex: string,
  txData: Record<string, string | number>,
): Promise<string> {
  // SECURITY: PLACEHOLDER — NOT REAL SIGNING
  // This uses HMAC-SHA256 with the PUBLIC KEY as the HMAC secret.
  // Anyone who knows the public key can reproduce this output.
  // Replace with real Dilithium2 WASM signing before production.
  if (typeof console !== "undefined") {
    console.warn(
      "[QBC SECURITY] placeholderSignTransaction() is NOT real signing. " +
        "It uses HMAC-SHA256 with the public key — anyone can forge these " +
        "signatures. Replace with Dilithium2 WASM before production.",
    );
  }

  // 1. Deterministically serialize the transaction (sorted keys)
  const sortedKeys = Object.keys(txData).sort();
  const sorted: Record<string, string | number> = {};
  for (const k of sortedKeys) {
    sorted[k] = txData[k];
  }
  const message = JSON.stringify(sorted);
  const msgBytes = new TextEncoder().encode(message);

  // 2. Hash the serialised transaction data (SHA-256)
  const hashBuffer = await crypto.subtle.digest("SHA-256", msgBytes);
  const msgHash = new Uint8Array(hashBuffer);

  // 3. PLACEHOLDER: HMAC-SHA256 using PUBLIC KEY as key.
  //    This will be replaced by Dilithium2 WASM signing once available.
  const keyBytes = hexToBytes(publicKeyHex);

  const cryptoKey = await crypto.subtle.importKey(
    "raw",
    keyBytes.buffer as ArrayBuffer,
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );

  const signatureBuffer = await crypto.subtle.sign("HMAC", cryptoKey, msgHash);
  const signature = bufToHex(new Uint8Array(signatureBuffer));

  return signature;
}

/**
 * @deprecated Use `placeholderSignTransaction` — this alias exists only for
 *   backward compatibility and will be removed.
 */
export const signTransaction = placeholderSignTransaction;

function bufToHex(buf: Uint8Array): string {
  return Array.from(buf)
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

function hexToBytes(hex: string): Uint8Array {
  const cleanHex = hex.startsWith("0x") ? hex.slice(2) : hex;
  const bytes = new Uint8Array(cleanHex.length / 2);
  for (let i = 0; i < cleanHex.length; i += 2) {
    bytes[i / 2] = parseInt(cleanHex.substring(i, i + 2), 16);
  }
  return bytes;
}
