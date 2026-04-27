use aes_gcm::aead::{Aead, KeyInit};
use aes_gcm::{Aes256Gcm, Nonce};
use anyhow::{Context, Result};
use argon2::Argon2;
use rand::RngCore;
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::fs;
use std::path::{Path, PathBuf};

use crate::WalletInfo;

const NONCE_LEN: usize = 12;
const SALT_LEN: usize = 16;
const ARGON2_MEM_COST: u32 = 65536; // 64 MiB
const ARGON2_TIME_COST: u32 = 3;
const ARGON2_PARALLELISM: u32 = 1;

/// On-disk format for an encrypted wallet file.
#[derive(Serialize, Deserialize)]
struct EncryptedWallet {
    /// Schema version for forward compatibility.
    version: u8,
    /// Human-readable label (optional).
    label: String,
    /// Hex-encoded 20-byte address (derived from public key).
    address: String,
    /// Hex-encoded 32-byte public key (SHA-256 of secret).
    public_key_hex: String,
    /// Hex-encoded salt for Argon2id key derivation.
    salt_hex: String,
    /// Hex-encoded (nonce ++ ciphertext) — AES-256-GCM encrypted 32-byte secret.
    encrypted_secret_hex: String,
    /// ISO-ish timestamp.
    created_at: String,
}

pub struct Keystore {
    dir: PathBuf,
}

impl Keystore {
    pub fn new(dir: PathBuf) -> Self {
        Self { dir }
    }

    /// Filename for a wallet: `<address>.json`
    fn wallet_path(&self, address: &str) -> PathBuf {
        self.dir.join(format!("{}.json", address))
    }

    /// Legacy single-wallet path for backward compat migration.
    fn legacy_path(&self) -> PathBuf {
        self.dir.join("wallet.json")
    }

    /// Return true if at least one wallet exists.
    pub fn has_any(&self) -> bool {
        self.list_addresses().map_or(false, |v| !v.is_empty())
    }

    /// List all wallet addresses in the keystore directory.
    pub fn list_addresses(&self) -> Result<Vec<String>> {
        self.maybe_migrate_legacy()?;

        if !self.dir.exists() {
            return Ok(vec![]);
        }
        let mut addrs = Vec::new();
        for entry in fs::read_dir(&self.dir)? {
            let entry = entry?;
            let name = entry.file_name();
            let name = name.to_string_lossy();
            if name.ends_with(".json") && name.len() == 45 {
                // 40 hex chars + ".json"
                addrs.push(name[..40].to_string());
            }
        }
        addrs.sort();
        Ok(addrs)
    }

    /// List full wallet info (without decrypting secrets).
    pub fn list_wallets(&self) -> Result<Vec<WalletInfo>> {
        self.maybe_migrate_legacy()?;

        let mut wallets = Vec::new();
        for addr in self.list_addresses()? {
            let path = self.wallet_path(&addr);
            if let Ok(data) = fs::read_to_string(&path) {
                if let Ok(stored) = serde_json::from_str::<EncryptedWallet>(&data) {
                    wallets.push(WalletInfo {
                        address: stored.address,
                        public_key: stored.public_key_hex,
                        label: stored.label,
                        created_at: stored.created_at,
                    });
                }
            }
        }
        Ok(wallets)
    }

    /// Read just the address of the first (default) wallet without decrypting.
    pub fn default_address(&self) -> Result<Option<String>> {
        let addrs = self.list_addresses()?;
        Ok(addrs.into_iter().next())
    }

    /// Generate a new wallet keypair and store it encrypted with Argon2id + AES-256-GCM.
    pub fn generate(&self, password: &str, label: &str) -> Result<WalletInfo> {
        fs::create_dir_all(&self.dir)?;

        // Generate random 32-byte secret
        let mut secret = [0u8; 32];
        rand::thread_rng().fill_bytes(&mut secret);

        let info = self.store_secret(&secret, password, label)?;

        // Zeroize secret from stack
        zeroize::Zeroize::zeroize(&mut secret);

        Ok(info)
    }

    /// Import a wallet from a hex-encoded 32-byte private key.
    pub fn import_hex(&self, secret_hex: &str, password: &str, label: &str) -> Result<WalletInfo> {
        fs::create_dir_all(&self.dir)?;

        let bytes = hex::decode(secret_hex.trim())
            .context("invalid hex for private key")?;
        if bytes.len() != 32 {
            anyhow::bail!("private key must be exactly 32 bytes (64 hex chars), got {}", bytes.len());
        }

        let mut secret = [0u8; 32];
        secret.copy_from_slice(&bytes);

        let info = self.store_secret(&secret, password, label)?;
        zeroize::Zeroize::zeroize(&mut secret);
        Ok(info)
    }

    /// Decrypt and return wallet info (verifies password).
    pub fn load(&self, address: &str, password: &str) -> Result<WalletInfo> {
        let path = self.wallet_path(address);
        let data = fs::read_to_string(&path)
            .with_context(|| format!("wallet {} not found", address))?;
        let stored: EncryptedWallet = serde_json::from_str(&data)?;

        // Verify password by decrypting
        let salt = hex::decode(&stored.salt_hex)?;
        let encrypted = hex::decode(&stored.encrypted_secret_hex)?;
        let _secret = decrypt_secret(&encrypted, password, &salt)?;

        Ok(WalletInfo {
            address: stored.address,
            public_key: stored.public_key_hex,
            label: stored.label,
            created_at: stored.created_at,
        })
    }

    /// Export the raw secret key (hex) — requires password.
    pub fn export_secret(&self, address: &str, password: &str) -> Result<String> {
        let path = self.wallet_path(address);
        let data = fs::read_to_string(&path)
            .with_context(|| format!("wallet {} not found", address))?;
        let stored: EncryptedWallet = serde_json::from_str(&data)?;

        let salt = hex::decode(&stored.salt_hex)?;
        let encrypted = hex::decode(&stored.encrypted_secret_hex)?;
        let secret = decrypt_secret(&encrypted, password, &salt)?;
        let hex_out = hex::encode(secret);
        Ok(hex_out)
    }

    /// Delete a wallet file. Requires address confirmation.
    pub fn delete(&self, address: &str) -> Result<()> {
        let path = self.wallet_path(address);
        if !path.exists() {
            anyhow::bail!("wallet {} not found", address);
        }
        fs::remove_file(&path).context("failed to delete wallet file")?;
        Ok(())
    }

    // --- internal helpers ---

    /// Derive address and public key from secret, encrypt, and write to disk.
    fn store_secret(&self, secret: &[u8; 32], password: &str, label: &str) -> Result<WalletInfo> {
        // Public key = SHA-256(secret)
        let public_key = Sha256::digest(secret);
        let public_key_hex = hex::encode(public_key);

        // Address = last 20 bytes of SHA-256(public_key) as hex
        let addr_hash = Sha256::digest(public_key);
        let address = hex::encode(&addr_hash[12..32]);

        // Check for collision
        if self.wallet_path(&address).exists() {
            anyhow::bail!("wallet with address {} already exists", address);
        }

        // Encrypt with Argon2id-derived key + AES-256-GCM
        let mut salt = [0u8; SALT_LEN];
        rand::thread_rng().fill_bytes(&mut salt);

        let encrypted = encrypt_secret(secret, password, &salt)?;
        let now = utc_timestamp();

        let stored = EncryptedWallet {
            version: 2,
            label: label.to_string(),
            address: address.clone(),
            public_key_hex: public_key_hex.clone(),
            salt_hex: hex::encode(salt),
            encrypted_secret_hex: hex::encode(encrypted),
            created_at: now.clone(),
        };

        let json = serde_json::to_string_pretty(&stored)?;
        fs::write(self.wallet_path(&address), json)?;

        Ok(WalletInfo {
            address,
            public_key: public_key_hex,
            label: label.to_string(),
            created_at: now,
        })
    }

    /// Migrate legacy single `wallet.json` to new `<address>.json` format.
    fn maybe_migrate_legacy(&self) -> Result<()> {
        let legacy = self.legacy_path();
        if !legacy.exists() {
            return Ok(());
        }

        let data = fs::read_to_string(&legacy)?;

        // Try parsing as old format (no salt, no version field)
        #[derive(Deserialize)]
        struct LegacyKey {
            address: String,
            public_key_hex: String,
            encrypted_secret: String,
            created_at: String,
        }

        if let Ok(old) = serde_json::from_str::<LegacyKey>(&data) {
            // Convert to new format — keep the encrypted blob as-is but mark as v1
            let new = EncryptedWallet {
                version: 1, // v1 = legacy key derivation (no argon2)
                label: "default".to_string(),
                address: old.address.clone(),
                public_key_hex: old.public_key_hex,
                salt_hex: String::new(), // v1 has no salt
                encrypted_secret_hex: old.encrypted_secret,
                created_at: old.created_at,
            };
            let new_path = self.wallet_path(&old.address);
            if !new_path.exists() {
                let json = serde_json::to_string_pretty(&new)?;
                fs::write(&new_path, json)?;
            }
            fs::remove_file(&legacy)?;
        }

        Ok(())
    }
}

/// Derive a 32-byte encryption key from password + salt using Argon2id.
fn derive_key(password: &str, salt: &[u8]) -> Result<[u8; 32]> {
    let argon2 = Argon2::new(
        argon2::Algorithm::Argon2id,
        argon2::Version::V0x13,
        argon2::Params::new(ARGON2_MEM_COST, ARGON2_TIME_COST, ARGON2_PARALLELISM, Some(32))
            .map_err(|e| anyhow::anyhow!("argon2 params: {e}"))?,
    );

    let mut key = [0u8; 32];
    argon2
        .hash_password_into(password.as_bytes(), salt, &mut key)
        .map_err(|e| anyhow::anyhow!("argon2 hash: {e}"))?;
    Ok(key)
}

fn encrypt_secret(secret: &[u8; 32], password: &str, salt: &[u8]) -> Result<Vec<u8>> {
    let key = derive_key(password, salt)?;
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

fn decrypt_secret(data: &[u8], password: &str, salt: &[u8]) -> Result<[u8; 32]> {
    if data.len() < NONCE_LEN + 32 {
        anyhow::bail!("encrypted data too short");
    }

    let key = derive_key(password, salt)?;
    let cipher = Aes256Gcm::new_from_slice(&key)?;
    let nonce = Nonce::from_slice(&data[..NONCE_LEN]);
    let ciphertext = &data[NONCE_LEN..];

    let plaintext = cipher
        .decrypt(nonce, ciphertext)
        .map_err(|_| anyhow::anyhow!("wrong password or corrupted keystore"))?;

    if plaintext.len() != 32 {
        anyhow::bail!("decrypted key has wrong length");
    }
    let mut secret = [0u8; 32];
    secret.copy_from_slice(&plaintext);
    Ok(secret)
}

fn utc_timestamp() -> String {
    use std::time::{SystemTime, UNIX_EPOCH};
    let secs = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_secs();
    // days/years approximation for display
    let days_total = secs / 86400;
    let year = 1970 + (days_total as f64 / 365.25) as u64;
    let day_of_year = days_total - ((year - 1970) as f64 * 365.25) as u64;
    let month = (day_of_year / 30).min(11) + 1;
    let day = (day_of_year % 30) + 1;
    format!("{year}-{month:02}-{day:02}T{:02}:{:02}:{:02}Z",
        (secs % 86400) / 3600,
        (secs % 3600) / 60,
        secs % 60)
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
        let info = ks.generate("test-password", "my-wallet").unwrap();
        assert!(!info.address.is_empty());
        assert_eq!(info.label, "my-wallet");

        let loaded = ks.load(&info.address, "test-password").unwrap();
        assert_eq!(loaded.address, info.address);
    }

    #[test]
    fn test_wrong_password() {
        let (_dir, ks) = temp_keystore();
        let info = ks.generate("correct", "test").unwrap();
        assert!(ks.load(&info.address, "wrong").is_err());
    }

    #[test]
    fn test_list_wallets() {
        let (_dir, ks) = temp_keystore();
        assert_eq!(ks.list_addresses().unwrap().len(), 0);

        ks.generate("pw1", "wallet-1").unwrap();
        ks.generate("pw2", "wallet-2").unwrap();

        let addrs = ks.list_addresses().unwrap();
        assert_eq!(addrs.len(), 2);

        let wallets = ks.list_wallets().unwrap();
        assert_eq!(wallets.len(), 2);
    }

    #[test]
    fn test_delete_wallet() {
        let (_dir, ks) = temp_keystore();
        let info = ks.generate("pw", "deleteme").unwrap();
        assert!(ks.has_any());

        ks.delete(&info.address).unwrap();
        assert!(!ks.has_any());
    }

    #[test]
    fn test_import_hex() {
        let (_dir, ks) = temp_keystore();
        let secret_hex = "aa".repeat(32); // 64 hex chars = 32 bytes
        let info = ks.import_hex(&secret_hex, "pw", "imported").unwrap();
        assert!(!info.address.is_empty());
        assert_eq!(info.label, "imported");

        // Verify we can load it back
        let loaded = ks.load(&info.address, "pw").unwrap();
        assert_eq!(loaded.address, info.address);
    }

    #[test]
    fn test_export_secret() {
        let (_dir, ks) = temp_keystore();
        let secret_hex = "bb".repeat(32);
        let info = ks.import_hex(&secret_hex, "pw", "test").unwrap();

        let exported = ks.export_secret(&info.address, "pw").unwrap();
        assert_eq!(exported, secret_hex);
    }
}
