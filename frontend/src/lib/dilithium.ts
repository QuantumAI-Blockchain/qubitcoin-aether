import { RPC_URL } from "./constants";

/**
 * Sign transaction data using Dilithium2 via the backend.
 *
 * The private key is passed to the backend signing endpoint and is
 * used only for this operation — never stored server-side.
 */
export async function signTransaction(
  privateKeyHex: string,
  txData: Record<string, string | number>,
): Promise<string> {
  // Sort keys and stringify to match backend's json.dumps(data, sort_keys=True)
  const sortedKeys = Object.keys(txData).sort();
  const sorted: Record<string, string | number> = {};
  for (const k of sortedKeys) {
    sorted[k] = txData[k];
  }
  const message = JSON.stringify(sorted);
  const msgBytes = new TextEncoder().encode(message);
  const hashBuffer = await crypto.subtle.digest("SHA-256", msgBytes);
  const msgHash = bufToHex(new Uint8Array(hashBuffer));

  const resp = await fetch(`${RPC_URL}/wallet/sign`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      message_hash: msgHash,
      private_key_hex: privateKeyHex,
    }),
  });

  if (!resp.ok) {
    const err = await resp.text().catch(() => "");
    throw new Error(`Signing failed: ${err}`);
  }

  const data = (await resp.json()) as { signature_hex: string };
  return data.signature_hex;
}

function bufToHex(buf: Uint8Array): string {
  return Array.from(buf)
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}
