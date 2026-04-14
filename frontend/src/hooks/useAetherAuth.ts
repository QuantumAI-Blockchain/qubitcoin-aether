"use client";

import { useState, useCallback } from "react";
import { useWalletStore } from "@/stores/wallet-store";
import { api } from "@/lib/api";
import { signMessage } from "@/lib/dilithium";

/**
 * Hook for Dilithium5 wallet authentication (challenge → sign → JWT).
 *
 * Works with native QBC wallets that have a secret key available client-side.
 * The secret key is used only in the WASM sandbox and never sent to the server.
 */
export function useAetherAuth() {
  const {
    activeNativeWallet,
    nativeWallets,
    authToken,
    authExpiry,
    authAddress,
    setAuth,
    clearAuth,
  } = useWalletStore();
  const [authenticating, setAuthenticating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isAuthenticated =
    !!authToken && !!authExpiry && Date.now() < authExpiry - 60_000;

  // The active native wallet object (has publicKeyHex)
  const activeWallet = nativeWallets.find(
    (w) => w.address === activeNativeWallet,
  );

  /**
   * Authenticate with the Aether API using a Dilithium5 wallet.
   * Requires the wallet's secret key (stored only in browser, never sent to server).
   *
   * @param secretKeyHex - The Dilithium secret key hex (from client-side WASM generation)
   */
  const authenticate = useCallback(
    async (secretKeyHex: string) => {
      if (!activeWallet) {
        setError("No active native wallet selected");
        return false;
      }

      setAuthenticating(true);
      setError(null);

      try {
        // Step 1: Request challenge
        const challenge = await api.getChallenge(activeWallet.address);

        // Step 2: Sign challenge message client-side (WASM)
        const signatureHex = await signMessage(secretKeyHex, challenge.message);

        // Step 3: Exchange signature for JWT
        const authResult = await api.authenticate({
          public_key_hex: activeWallet.publicKeyHex,
          signature_hex: signatureHex,
          message: challenge.message,
        });

        // Step 4: Store auth token
        setAuth(authResult.token, authResult.expires_at, authResult.address);
        return true;
      } catch (err) {
        const msg =
          err instanceof Error ? err.message : "Authentication failed";
        setError(msg);
        return false;
      } finally {
        setAuthenticating(false);
      }
    },
    [activeWallet, setAuth],
  );

  const logout = useCallback(() => {
    clearAuth();
    setError(null);
  }, [clearAuth]);

  return {
    isAuthenticated,
    authenticating,
    error,
    authAddress,
    activeWallet,
    authenticate,
    logout,
  };
}
