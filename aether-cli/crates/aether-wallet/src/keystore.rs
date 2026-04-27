use aes_gcm::aead::{Aead, KeyInit};
use aes_gcm::{Aes256Gcm, Nonce};
use anyhow::{Context, Result};
use rand::RngCore;
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::fs;
use std::path::PathBuf;

use crate::WalletInfo;

const KEY_FILE: &str = "wallet.json";
const NONCE_LEN: usize = 12;

#[derive(Serialize, Deserialize)]
struct EncryptedKey {
    address: String,
    public_key_hex: String,
    encrypted_secret: String, // hex(nonce ++ ciphertext)
    created_at: String,
}

pub struct Keystore {
    dir: PathBuf,
}

impl Keystore {
    pub fn new(dir: PathBuf) -> Self {
        Self { dir }
    }

    fn key_path(&self) -> PathBuf {
        self.dir.join(KEY_FILE)
    }

    pub fn has_key(&self) -> bool {
        self.key_path().exists()
    }

    /// Read just the address without decrypting.
    pub fn address(&self) -> Result<Option<String>> {
        let path = self.key_path();
        if !path.exists() {
            return Ok(None);
        }
        let data = fs::read_to_string(&path)?;
        let stored: EncryptedKey = serde_json::from_str(&data)?;
        Ok(Some(stored.address))
    }

    /// Generate a new keypair and store it encrypted.
    ///
    /// Uses a random 32-byte secret as the "private key" material.
    /// The address is derived as the last 20 bytes of SHA256(public_key).
    /// In production this would use Dilithium5 — here we use a simple
    /// scheme so the CLI compiles without heavy PQC dependencies.
    pub fn generate(&self, password: &str) -> Result<WalletInfo> {
        fs::create_dir_all(&self.dir)?;

        // Generate random secret (32 bytes)
        let mut secret = [0u8; 32];
        rand::thread_rng().fill_bytes(&mut secret);

        // Derive "public key" = SHA256(secret)
        let public_key = Sha256::digest(secret);
        let public_key_hex = hex::encode(public_key);

        // Address = last 20 bytes of SHA256(public_key) as hex
        let addr_hash = Sha256::digest(public_key);
        let address = hex::encode(&addr_hash[12..32]);

        // Encrypt secret with password
        let encrypted = encrypt_secret(&secret, password)?;

        let now = chrono_lite_now();
        let stored = EncryptedKey {
            address: address.clone(),
            public_key_hex: public_key_hex.clone(),
            encrypted_secret: hex::encode(encrypted),
            created_at: now.clone(),
        };

        let json = serde_json::to_string_pretty(&stored)?;
        fs::write(self.key_path(), json)?;

        // Zero out secret from memory
        zeroize::Zeroize::zeroize(&mut secret);

        Ok(WalletInfo {
            address,
            public_key: public_key_hex,
            created_at: now,
        })
    }

    pub fn load(&self, password: &str) -> Result<WalletInfo> {
        let data = fs::read_to_string(self.key_path())
            .context("no wallet found — run `aether wallet create` first")?;
        let stored: EncryptedKey = serde_json::from_str(&data)?;

        // Verify password by attempting decryption
        let encrypted_bytes = hex::decode(&stored.encrypted_secret)?;
        let _secret = decrypt_secret(&encrypted_bytes, password)?;

        Ok(WalletInfo {
            address: stored.address,
            public_key: stored.public_key_hex,
            created_at: stored.created_at,
        })
    }
}

fn derive_key(password: &str) -> [u8; 32] {
    // Simple key derivation: SHA256(SHA256(password) ++ "aether-cli-v1")
    // In production, use Argon2id.
    let pass_hash = Sha256::digest(password.as_bytes());
    let mut hasher = Sha256::new();
    hasher.update(pass_hash);
    hasher.update(b"aether-cli-v1");
    let result = hasher.finalize();
    let mut key = [0u8; 32];
    key.copy_from_slice(&result);
    key
}

fn encrypt_secret(secret: &[u8; 32], password: &str) -> Result<Vec<u8>> {
    let key = derive_key(password);
    let cipher = Aes256Gcm::new_from_slice(&key)?;

    let mut nonce_bytes = [0u8; NONCE_LEN];
    rand::thread_rng().fill_bytes(&mut nonce_bytes);
    let nonce = Nonce::from_slice(&nonce_bytes);

    let ciphertext = cipher
        .encrypt(nonce, secret.as_ref())
        .map_err(|e| anyhow::anyhow!("encryption failed: {e}"))?;

    let mut result = Vec::with_capacity(NONCE_LEN + ciphertext.len());
    result.extend_from_slice(&nonce_bytes);
    result.extend(ciphertext);
    Ok(result)
}

fn decrypt_secret(data: &[u8], password: &str) -> Result<[u8; 32]> {
    if data.len() < NONCE_LEN + 32 {
        anyhow::bail!("encrypted data too short");
    }

    let key = derive_key(password);
    let cipher = Aes256Gcm::new_from_slice(&key)?;
    let nonce = Nonce::from_slice(&data[..NONCE_LEN]);
    let ciphertext = &data[NONCE_LEN..];

    let plaintext = cipher
        .decrypt(nonce, ciphertext)
        .map_err(|_| anyhow::anyhow!("wrong password or corrupted keystore"))?;

    let mut secret = [0u8; 32];
    if plaintext.len() != 32 {
        anyhow::bail!("decrypted key has wrong length");
    }
    secret.copy_from_slice(&plaintext);
    Ok(secret)
}

fn chrono_lite_now() -> String {
    // Simple UTC timestamp without chrono dependency
    use std::time::{SystemTime, UNIX_EPOCH};
    let secs = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_secs();
    // Approximate ISO 8601
    let days = secs / 86400;
    let years = 1970 + days / 365;
    format!("{years}-xx-xx (epoch: {secs})")
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::TempDir;

    fn temp_keystore() -> (TempDir, Keystore) {
        let dir = TempDir::new().unwrap();
        let ks = Keystore::new(dir.path().to_path_buf());
        (dir, ks)
    }

    #[test]
    fn test_generate_and_load() {
        let (_dir, ks) = temp_keystore();
        let info = ks.generate("test-password").unwrap();
        assert!(!info.address.is_empty());

        let loaded = ks.load("test-password").unwrap();
        assert_eq!(loaded.address, info.address);
    }

    #[test]
    fn test_wrong_password() {
        let (_dir, ks) = temp_keystore();
        ks.generate("correct").unwrap();
        assert!(ks.load("wrong").is_err());
    }

    #[test]
    fn test_has_key() {
        let (_dir, ks) = temp_keystore();
        assert!(!ks.has_key());
        ks.generate("pw").unwrap();
        assert!(ks.has_key());
    }
}
