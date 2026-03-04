/**
 * Biometric Authentication for Qubitcoin Wallet
 *
 * Uses the Web Authentication API (WebAuthn) to protect
 * high-value operations with biometric verification:
 * - Transaction signing approval
 * - Wallet key export
 * - Security policy changes
 */

export interface BiometricCredential {
  credentialId: string;
  publicKey: string;
  createdAt: number;
}

const RP_NAME = "Qubitcoin Wallet";
const RP_ID =
  typeof window !== "undefined" ? window.location.hostname : "localhost";

/** Check if WebAuthn / biometric auth is available. */
export function isBiometricAvailable(): boolean {
  return (
    typeof window !== "undefined" &&
    !!window.PublicKeyCredential &&
    typeof window.PublicKeyCredential.isUserVerifyingPlatformAuthenticatorAvailable === "function"
  );
}

/** Check if a platform authenticator (fingerprint/face) is available. */
export async function hasPlatformAuthenticator(): Promise<boolean> {
  if (!isBiometricAvailable()) return false;
  try {
    return await PublicKeyCredential.isUserVerifyingPlatformAuthenticatorAvailable();
  } catch {
    return false;
  }
}

/** Register a new biometric credential for the wallet address. */
export async function registerBiometric(
  walletAddress: string,
): Promise<BiometricCredential | null> {
  if (!isBiometricAvailable()) return null;

  try {
    const challenge = crypto.getRandomValues(new Uint8Array(32));
    const userId = new TextEncoder().encode(walletAddress);

    const credential = (await navigator.credentials.create({
      publicKey: {
        rp: { name: RP_NAME, id: RP_ID },
        user: {
          id: userId,
          name: walletAddress,
          displayName: `QBC Wallet (${walletAddress.slice(0, 8)}...)`,
        },
        challenge,
        pubKeyCredParams: [
          { alg: -7, type: "public-key" }, // ES256
          { alg: -257, type: "public-key" }, // RS256
        ],
        authenticatorSelection: {
          authenticatorAttachment: "platform",
          userVerification: "required",
          residentKey: "preferred",
        },
        timeout: 60000,
        attestation: "none",
      },
    })) as PublicKeyCredential | null;

    if (!credential) return null;

    const response = credential.response as AuthenticatorAttestationResponse;
    const result: BiometricCredential = {
      credentialId: bufferToBase64(credential.rawId),
      publicKey: bufferToBase64(response.getPublicKey()!),
      createdAt: Date.now(),
    };

    // Store credential ID in localStorage for later verification
    localStorage.setItem(
      `qbc-biometric-${walletAddress}`,
      JSON.stringify(result),
    );

    return result;
  } catch {
    return null;
  }
}

/** Verify biometric authentication for a wallet address. */
export async function verifyBiometric(
  walletAddress: string,
): Promise<boolean> {
  if (!isBiometricAvailable()) return false;

  const stored = localStorage.getItem(`qbc-biometric-${walletAddress}`);
  if (!stored) return false;

  try {
    const { credentialId } = JSON.parse(stored) as BiometricCredential;
    const challenge = crypto.getRandomValues(new Uint8Array(32));

    const assertion = await navigator.credentials.get({
      publicKey: {
        challenge,
        allowCredentials: [
          {
            id: base64ToBuffer(credentialId),
            type: "public-key",
            transports: ["internal"],
          },
        ],
        userVerification: "required",
        timeout: 60000,
      },
    });

    return !!assertion;
  } catch {
    return false;
  }
}

/** Check if biometric is registered for a wallet address. */
export function hasBiometricRegistered(walletAddress: string): boolean {
  return !!localStorage.getItem(`qbc-biometric-${walletAddress}`);
}

/** Remove biometric registration for a wallet address. */
export function removeBiometric(walletAddress: string): void {
  localStorage.removeItem(`qbc-biometric-${walletAddress}`);
}

// ── Helpers ──────────────────────────────────────────────────────────

function bufferToBase64(buffer: ArrayBuffer): string {
  return btoa(String.fromCharCode(...new Uint8Array(buffer)));
}

function base64ToBuffer(base64: string): ArrayBuffer {
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) {
    bytes[i] = binary.charCodeAt(i);
  }
  return bytes.buffer;
}
