//! API Key Vault — Encrypted storage for LLM provider API keys.
//!
//! Keys are encrypted at rest with AES-256-GCM. The master key is derived from
//! a hex-encoded secret (`AIKGS_VAULT_MASTER_KEY` env var). If not set, a random
//! 32-byte key is generated at startup (keys will be unrecoverable after restart
//! unless the master key is persisted externally).
//!
//! Ciphertext layout: `[12-byte nonce][ciphertext...]`

use aes_gcm::aead::{Aead, KeyInit, OsRng};
use aes_gcm::{Aes256Gcm, Key, Nonce};
use rand::RngCore;
use serde::Serialize;
use uuid::Uuid;

use crate::db::{ApiKeyRow, Db};

// ════════════════════════════════════════════════════════════════════════════
// Constants
// ════════════════════════════════════════════════════════════════════════════

/// AES-256-GCM nonce size in bytes.
const NONCE_SIZE: usize = 12;

/// AES-256 key size in bytes.
const KEY_SIZE: usize = 32;

// ════════════════════════════════════════════════════════════════════════════
// Error type
// ════════════════════════════════════════════════════════════════════════════

#[derive(Debug, thiserror::Error)]
pub enum VaultError {
    #[error("database error: {0}")]
    Db(#[from] sqlx::Error),
    #[error("invalid master key hex: {0}")]
    InvalidMasterKey(String),
    #[error("master key must be exactly 32 bytes (64 hex chars), got {0} bytes")]
    WrongKeyLength(usize),
    #[error("encryption failed")]
    EncryptionFailed,
    #[error("decryption failed — wrong master key or corrupted ciphertext")]
    DecryptionFailed,
    #[error("ciphertext too short (need at least {NONCE_SIZE} bytes for nonce)")]
    CiphertextTooShort,
    #[error("API key {0} not found")]
    KeyNotFound(String),
}

// ════════════════════════════════════════════════════════════════════════════
// Public types
// ════════════════════════════════════════════════════════════════════════════

/// Metadata about a stored API key (no decrypted material).
#[derive(Debug, Clone, Serialize)]
pub struct KeyInfo {
    pub key_id: String,
    pub provider: String,
    pub model: String,
    pub owner_address: String,
    pub is_shared: bool,
    pub shared_reward_bps: i32,
    pub label: String,
    pub use_count: i32,
    pub is_active: bool,
}

/// A decrypted API key — handle with care, do not log or serialize carelessly.
#[derive(Debug, Clone)]
pub struct DecryptedKey {
    pub key_id: String,
    pub provider: String,
    pub model: String,
    pub owner_address: String,
    pub api_key: String,
    pub is_shared: bool,
    pub shared_reward_bps: i32,
    pub label: String,
}

// ════════════════════════════════════════════════════════════════════════════
// VaultManager
// ════════════════════════════════════════════════════════════════════════════

/// Manages encrypted API key storage and retrieval.
pub struct VaultManager {
    cipher: Aes256Gcm,
}

impl VaultManager {
    /// Create a new vault manager. If `master_key_hex` is empty, a random
    /// 32-byte key is generated (ephemeral — keys will be lost on restart).
    pub fn new(master_key_hex: &str) -> Result<Self, VaultError> {
        let key_bytes = if master_key_hex.is_empty() {
            log::warn!(
                "No AIKGS_VAULT_MASTER_KEY set — generating ephemeral key. \
                 Stored API keys will be unrecoverable after restart!"
            );
            let mut key = [0u8; KEY_SIZE];
            OsRng.fill_bytes(&mut key);
            key.to_vec()
        } else {
            let decoded = hex::decode(master_key_hex)
                .map_err(|e| VaultError::InvalidMasterKey(e.to_string()))?;
            if decoded.len() != KEY_SIZE {
                return Err(VaultError::WrongKeyLength(decoded.len()));
            }
            decoded
        };

        let key = Key::<Aes256Gcm>::from_slice(&key_bytes);
        let cipher = Aes256Gcm::new(key);

        Ok(Self { cipher })
    }

    // ── Store an API key ────────────────────────────────────────────────

    /// Encrypt and store an API key in the database. Returns metadata about
    /// the newly stored key.
    pub async fn store_key(
        &self,
        db: &Db,
        provider: &str,
        api_key: &str,
        owner_address: &str,
        model: &str,
        is_shared: bool,
        shared_reward_bps: i32,
        label: &str,
    ) -> Result<KeyInfo, VaultError> {
        let key_id = Uuid::new_v4().to_string();

        // Encrypt: random 12-byte nonce prepended to ciphertext
        let encrypted = self.encrypt(api_key.as_bytes())?;

        db.insert_api_key(
            &key_id,
            provider,
            model,
            owner_address,
            &encrypted,
            is_shared,
            shared_reward_bps,
            label,
        )
        .await?;

        log::info!(
            "Stored API key: id={} provider={} owner={} shared={}",
            key_id,
            provider,
            owner_address,
            is_shared
        );

        Ok(KeyInfo {
            key_id,
            provider: provider.to_string(),
            model: model.to_string(),
            owner_address: owner_address.to_string(),
            is_shared,
            shared_reward_bps,
            label: label.to_string(),
            use_count: 0,
            is_active: true,
        })
    }

    // ── Retrieve and decrypt an API key ─────────────────────────────────

    /// Fetch an API key by ID, decrypt it, and return the plaintext key
    /// material along with metadata.
    pub async fn get_key(
        &self,
        db: &Db,
        key_id: &str,
    ) -> Result<DecryptedKey, VaultError> {
        let row = db
            .get_api_key(key_id)
            .await?
            .ok_or_else(|| VaultError::KeyNotFound(key_id.to_string()))?;

        let plaintext = self.decrypt(&row.encrypted_key)?;
        let api_key = String::from_utf8(plaintext)
            .map_err(|_| VaultError::DecryptionFailed)?;

        // Increment usage counter
        let _ = db.increment_key_usage(key_id).await;

        Ok(DecryptedKey {
            key_id: row.key_id,
            provider: row.provider,
            model: row.model,
            owner_address: row.owner_address,
            api_key,
            is_shared: row.is_shared,
            shared_reward_bps: row.shared_reward_bps,
            label: row.label,
        })
    }

    // ── List keys (metadata only, no decryption) ────────────────────────

    /// List all active API keys owned by the given address. No decrypted
    /// key material is returned.
    pub async fn list_keys(
        &self,
        db: &Db,
        owner_address: &str,
    ) -> Result<Vec<KeyInfo>, VaultError> {
        let rows = db.list_api_keys(owner_address).await?;
        Ok(rows.iter().map(api_key_row_to_info).collect())
    }

    // ── Revoke a key ────────────────────────────────────────────────────

    /// Soft-delete (deactivate) an API key. Only the owner can revoke.
    /// Returns `true` if the key was found and revoked, `false` if not found
    /// or already revoked.
    pub async fn revoke_key(
        &self,
        db: &Db,
        key_id: &str,
        owner_address: &str,
    ) -> Result<bool, VaultError> {
        let revoked = db.revoke_api_key(key_id, owner_address).await?;
        if revoked {
            log::info!("Revoked API key: id={} owner={}", key_id, owner_address);
        }
        Ok(revoked)
    }

    // ── Shared key pool ─────────────────────────────────────────────────

    /// Get all shared API keys for a given provider (metadata only).
    pub async fn get_shared_pool(
        &self,
        db: &Db,
        provider: &str,
    ) -> Result<Vec<KeyInfo>, VaultError> {
        let rows = db.get_shared_keys(provider).await?;
        Ok(rows.iter().map(api_key_row_to_info).collect())
    }

    // ── Encryption internals ────────────────────────────────────────────

    /// Encrypt plaintext with AES-256-GCM. Returns `[nonce (12 bytes)][ciphertext]`.
    fn encrypt(&self, plaintext: &[u8]) -> Result<Vec<u8>, VaultError> {
        let mut nonce_bytes = [0u8; NONCE_SIZE];
        OsRng.fill_bytes(&mut nonce_bytes);
        let nonce = Nonce::from_slice(&nonce_bytes);

        let ciphertext = self
            .cipher
            .encrypt(nonce, plaintext)
            .map_err(|_| VaultError::EncryptionFailed)?;

        // Prepend nonce to ciphertext
        let mut result = Vec::with_capacity(NONCE_SIZE + ciphertext.len());
        result.extend_from_slice(&nonce_bytes);
        result.extend_from_slice(&ciphertext);
        Ok(result)
    }

    /// Decrypt ciphertext produced by `encrypt()`. Expects `[nonce (12)][ciphertext]`.
    fn decrypt(&self, data: &[u8]) -> Result<Vec<u8>, VaultError> {
        if data.len() < NONCE_SIZE {
            return Err(VaultError::CiphertextTooShort);
        }

        let (nonce_bytes, ciphertext) = data.split_at(NONCE_SIZE);
        let nonce = Nonce::from_slice(nonce_bytes);

        self.cipher
            .decrypt(nonce, ciphertext)
            .map_err(|_| VaultError::DecryptionFailed)
    }
}

// ════════════════════════════════════════════════════════════════════════════
// Conversion helpers
// ════════════════════════════════════════════════════════════════════════════

fn api_key_row_to_info(row: &ApiKeyRow) -> KeyInfo {
    KeyInfo {
        key_id: row.key_id.clone(),
        provider: row.provider.clone(),
        model: row.model.clone(),
        owner_address: row.owner_address.clone(),
        is_shared: row.is_shared,
        shared_reward_bps: row.shared_reward_bps,
        label: row.label.clone(),
        use_count: row.use_count,
        is_active: row.is_active,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_encrypt_decrypt_roundtrip() {
        let vault = VaultManager::new("").unwrap();
        let plaintext = b"sk-test-key-1234567890abcdef";
        let encrypted = vault.encrypt(plaintext).unwrap();

        // Encrypted data must be larger than plaintext (nonce + auth tag)
        assert!(encrypted.len() > plaintext.len());

        let decrypted = vault.decrypt(&encrypted).unwrap();
        assert_eq!(decrypted, plaintext);
    }

    #[test]
    fn test_encrypt_different_nonces() {
        let vault = VaultManager::new("").unwrap();
        let plaintext = b"same-key";
        let enc1 = vault.encrypt(plaintext).unwrap();
        let enc2 = vault.encrypt(plaintext).unwrap();

        // Same plaintext should produce different ciphertext (random nonce)
        assert_ne!(enc1, enc2);

        // Both should decrypt to the same value
        assert_eq!(vault.decrypt(&enc1).unwrap(), plaintext);
        assert_eq!(vault.decrypt(&enc2).unwrap(), plaintext);
    }

    #[test]
    fn test_decrypt_wrong_key() {
        let vault1 = VaultManager::new("").unwrap();
        let vault2 = VaultManager::new("").unwrap();
        let encrypted = vault1.encrypt(b"secret").unwrap();

        // Decrypting with a different key should fail
        let result = vault2.decrypt(&encrypted);
        assert!(result.is_err());
    }

    #[test]
    fn test_decrypt_truncated_ciphertext() {
        let vault = VaultManager::new("").unwrap();
        let result = vault.decrypt(&[0u8; 5]);
        assert!(matches!(result, Err(VaultError::CiphertextTooShort)));
    }

    #[test]
    fn test_new_from_hex_key() {
        let hex_key = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef";
        let vault = VaultManager::new(hex_key).unwrap();
        let encrypted = vault.encrypt(b"test").unwrap();
        let decrypted = vault.decrypt(&encrypted).unwrap();
        assert_eq!(decrypted, b"test");
    }

    #[test]
    fn test_new_wrong_key_length() {
        let result = VaultManager::new("0123456789abcdef");
        assert!(matches!(result, Err(VaultError::WrongKeyLength(8))));
    }

    #[test]
    fn test_new_invalid_hex() {
        let result = VaultManager::new("not-hex-at-all!!");
        assert!(matches!(result, Err(VaultError::InvalidMasterKey(_))));
    }
}
