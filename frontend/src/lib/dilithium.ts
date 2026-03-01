/**
 * Client-side Dilithium2 transaction signing.
 *
 * SECURITY: Private keys NEVER leave the browser. Signing is performed
 * entirely client-side.
 *
 * Current implementation uses HMAC-SHA256 as a placeholder signature
 * scheme. Once a Dilithium2 WASM module is available (e.g. compiled from
 * liboqs via wasm-pack), replace the HMAC call with real Dilithium2
 * sign(privateKey, message) and update the signature format accordingly.
 *
 * TODO: Replace HMAC-SHA256 placeholder with real Dilithium2 WASM signing.
 *       See: https://github.com/nicoburniske/pqc-wasm for a reference
 *       Dilithium WASM build. The function signature stays the same —
 *       only the internal signing primitive changes.
 */

/**
 * Sign transaction data using client-side cryptography.
 *
 * The private key is used locally and is NEVER sent to any backend
 * endpoint. The resulting signature (currently HMAC-SHA256, will be
 * upgraded to Dilithium2 via WASM) is returned as a hex string.
 */
export async function signTransaction(
  privateKeyHex: string,
  txData: Record<string, string | number>,
): Promise<string> {
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

  // 3. Client-side signing — HMAC-SHA256 placeholder.
  //    This will be replaced by Dilithium2 WASM signing once available.
  //    The private key stays in-browser; nothing is sent over the network.
  const keyBytes = hexToBytes(privateKeyHex);

  const cryptoKey = await crypto.subtle.importKey(
    "raw",
    keyBytes,
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );

  const signatureBuffer = await crypto.subtle.sign("HMAC", cryptoKey, msgHash);
  const signature = bufToHex(new Uint8Array(signatureBuffer));

  return signature;
}

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
