use aes_gcm::aead::{Aead, KeyInit};
use aes_gcm::{Aes256Gcm, Nonce};
use anyhow::{Context, Result};
use argon2::Argon2;
use pqcrypto_dilithium::dilithium5;
use pqcrypto_traits::sign::{DetachedSignature, PublicKey, SecretKey};
use rand::RngCore;
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::fs;
use std::path::PathBuf;

use crate::WalletInfo;

const NONCE_LEN: usize = 12;
const SALT_LEN: usize = 16;
const ARGON2_MEM_COST: u32 = 65536; // 64 MiB
const ARGON2_TIME_COST: u32 = 3;
const ARGON2_PARALLELISM: u32 = 1;

/// Dilithium5 key sizes (NIST Level 5, pqcrypto-dilithium 0.5).
pub const DILITHIUM5_PK_SIZE: usize = 2592;
pub const DILITHIUM5_SK_SIZE: usize = 4896;
pub const DILITHIUM5_SIG_SIZE: usize = 4627;

/// QBC address size — full SHA-256 of Dilithium5 public key (matches Substrate pallet).
pub const ADDRESS_SIZE: usize = 32;
pub const ADDRESS_HEX_LEN: usize = ADDRESS_SIZE * 2; // 64 hex chars

/// On-disk format for an encrypted wallet file (v3 = Dilithium5).
#[derive(Serialize, Deserialize)]
struct EncryptedWallet {
    /// Schema version: 3 = Dilithium5 quantum-secure.
    version: u8,
    /// Human-readable label (optional).
    label: String,
    /// Hex-encoded 32-byte QBC address (SHA-256 of Dilithium5 public key).
    address: String,
    /// Hex-encoded 2592-byte Dilithium5 public key.
    public_key_hex: String,
    /// Hex-encoded salt for Argon2id key derivation.
    salt_hex: String,
    /// Hex-encoded (nonce ++ ciphertext) — AES-256-GCM encrypted Dilithium5 secret key (4896 bytes).
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

    /// Filename for a wallet: `<address>.json` (64 hex chars + .json = 69 chars)
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
            if name.ends_with(".json") && name != "wallet.json" {
                let addr_part = &name[..name.len() - 5];
                // Accept both legacy 40-char (v2) and new 64-char (v3) addresses
                if addr_part.len() == ADDRESS_HEX_LEN || addr_part.len() == 40 {
                    addrs.push(addr_part.to_string());
                }
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
                        version: stored.version,
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

    /// Generate a new Dilithium5 wallet keypair and store it encrypted.
    pub fn generate(&self, password: &str, label: &str) -> Result<WalletInfo> {
        fs::create_dir_all(&self.dir)?;

        // Generate real CRYSTALS-Dilithium5 keypair (NIST Level 5)
        let (pk, sk) = dilithium5::keypair();
        let pk_bytes = pk.as_bytes();
        let sk_bytes = sk.as_bytes();

        assert_eq!(pk_bytes.len(), DILITHIUM5_PK_SIZE, "Dilithium5 PK size mismatch");
        assert_eq!(sk_bytes.len(), DILITHIUM5_SK_SIZE, "Dilithium5 SK size mismatch");

        let info = self.store_dilithium_keypair(pk_bytes, sk_bytes, password, label)?;
        Ok(info)
    }

    /// Import a wallet from a hex-encoded Dilithium5 secret key.
    pub fn import_hex(&self, secret_hex: &str, password: &str, label: &str) -> Result<WalletInfo> {
        fs::create_dir_all(&self.dir)?;

        let sk_bytes = hex::decode(secret_hex.trim())
            .context("invalid hex for Dilithium5 secret key")?;

        let combined_size = DILITHIUM5_PK_SIZE + DILITHIUM5_SK_SIZE;
        if sk_bytes.len() == combined_size {
            // PK||SK combined export format (7488 bytes)
            let pk_bytes = &sk_bytes[..DILITHIUM5_PK_SIZE];
            let sk_only = &sk_bytes[DILITHIUM5_PK_SIZE..];

            let info = self.store_dilithium_keypair(pk_bytes, sk_only, password, label)?;
            Ok(info)
        } else if sk_bytes.len() == DILITHIUM5_SK_SIZE {
            // Raw SK only — we can't recover PK reliably, so sign a test message
            // and verify against the stored PK to confirm correctness
            anyhow::bail!(
                "raw {}-byte Dilithium5 SK import not supported. \
                 Use the PK||SK combined format ({} bytes) from `wallet export`.",
                DILITHIUM5_SK_SIZE, combined_size
            );
        } else if sk_bytes.len() == 32 {
            // Legacy 32-byte secret — store as v2 format for backward compat
            let mut secret = [0u8; 32];
            secret.copy_from_slice(&sk_bytes);
            let info = self.store_legacy_secret(&secret, password, label)?;
            zeroize::Zeroize::zeroize(&mut secret);
            Ok(info)
        } else {
            anyhow::bail!(
                "invalid key size: expected {} bytes (PK||SK export) or 32 bytes (legacy), got {}",
                combined_size, sk_bytes.len()
            );
        }
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
        let _secret = decrypt_bytes(&encrypted, password, &salt)?;

        Ok(WalletInfo {
            address: stored.address,
            public_key: stored.public_key_hex,
            label: stored.label,
            created_at: stored.created_at,
            version: stored.version,
        })
    }

    /// Export the raw keypair (hex) — requires password.
    /// For v3 wallets, exports PK||SK concatenated (2592 + 4896 = 7488 bytes).
    pub fn export_secret(&self, address: &str, password: &str) -> Result<String> {
        let path = self.wallet_path(address);
        let data = fs::read_to_string(&path)
            .with_context(|| format!("wallet {} not found", address))?;
        let stored: EncryptedWallet = serde_json::from_str(&data)?;

        let salt = hex::decode(&stored.salt_hex)?;
        let encrypted = hex::decode(&stored.encrypted_secret_hex)?;
        let secret = decrypt_bytes(&encrypted, password, &salt)?;

        if stored.version >= 3 {
            // Export PK||SK so re-import can recover both
            let pk_bytes = hex::decode(&stored.public_key_hex)?;
            let mut combined = Vec::with_capacity(pk_bytes.len() + secret.len());
            combined.extend_from_slice(&pk_bytes);
            combined.extend_from_slice(&secret);
            Ok(hex::encode(combined))
        } else {
            Ok(hex::encode(secret))
        }
    }

    /// Sign a message with the wallet's Dilithium5 secret key.
    /// Returns the detached signature (4627 bytes).
    pub fn sign(&self, address: &str, password: &str, message: &[u8]) -> Result<Vec<u8>> {
        let path = self.wallet_path(address);
        let data = fs::read_to_string(&path)
            .with_context(|| format!("wallet {} not found", address))?;
        let stored: EncryptedWallet = serde_json::from_str(&data)?;

        if stored.version < 3 {
            anyhow::bail!(
                "wallet {} is v{} (legacy). Only Dilithium5 (v3) wallets can sign. \
                 Create a new wallet with `aether wallet create`.",
                address, stored.version
            );
        }

        let salt = hex::decode(&stored.salt_hex)?;
        let encrypted = hex::decode(&stored.encrypted_secret_hex)?;
        let sk_bytes = decrypt_bytes(&encrypted, password, &salt)?;

        if sk_bytes.len() != DILITHIUM5_SK_SIZE {
            anyhow::bail!("decrypted key has wrong length for Dilithium5: {}", sk_bytes.len());
        }

        let sk = dilithium5::SecretKey::from_bytes(&sk_bytes)
            .map_err(|_| anyhow::anyhow!("invalid Dilithium5 secret key"))?;

        let sig = dilithium5::detached_sign(message, &sk);
        Ok(sig.as_bytes().to_vec())
    }

    /// Get the Dilithium5 public key bytes for a wallet.
    pub fn public_key_bytes(&self, address: &str) -> Result<Vec<u8>> {
        let path = self.wallet_path(address);
        let data = fs::read_to_string(&path)
            .with_context(|| format!("wallet {} not found", address))?;
        let stored: EncryptedWallet = serde_json::from_str(&data)?;
        hex::decode(&stored.public_key_hex).context("invalid public key hex in wallet file")
    }

    /// Get the wallet version.
    pub fn wallet_version(&self, address: &str) -> Result<u8> {
        let path = self.wallet_path(address);
        let data = fs::read_to_string(&path)
            .with_context(|| format!("wallet {} not found", address))?;
        let stored: EncryptedWallet = serde_json::from_str(&data)?;
        Ok(stored.version)
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

    /// Store a Dilithium5 keypair as v3 wallet.
    fn store_dilithium_keypair(
        &self,
        pk_bytes: &[u8],
        sk_bytes: &[u8],
        password: &str,
        label: &str,
    ) -> Result<WalletInfo> {
        let public_key_hex = hex::encode(pk_bytes);

        // QBC address = SHA-256(Dilithium5 public key) — matches Substrate pallet
        let address_hash = Sha256::digest(pk_bytes);
        let address = hex::encode(address_hash);

        // Check for collision
        if self.wallet_path(&address).exists() {
            anyhow::bail!("wallet with address {} already exists", address);
        }

        // Encrypt the full Dilithium5 secret key
        let mut salt = [0u8; SALT_LEN];
        rand::thread_rng().fill_bytes(&mut salt);
        let encrypted = encrypt_bytes(sk_bytes, password, &salt)?;
        let now = utc_timestamp();

        let stored = EncryptedWallet {
            version: 3,
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
            version: 3,
        })
    }

    /// Store a legacy 32-byte secret as v2 wallet (backward compat for imports).
    fn store_legacy_secret(
        &self,
        secret: &[u8; 32],
        password: &str,
        label: &str,
    ) -> Result<WalletInfo> {
        // Legacy derivation: public_key = SHA-256(secret), address = SHA-256(public_key)[12..32]
        let public_key = Sha256::digest(secret);
        let public_key_hex = hex::encode(public_key);
        let addr_hash = Sha256::digest(public_key);
        let address = hex::encode(&addr_hash[12..32]);

        if self.wallet_path(&address).exists() {
            anyhow::bail!("wallet with address {} already exists", address);
        }

        let mut salt = [0u8; SALT_LEN];
        rand::thread_rng().fill_bytes(&mut salt);
        let encrypted = encrypt_bytes(secret, password, &salt)?;
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
            version: 2,
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

/// Verify a Dilithium5 detached signature.
pub fn verify_dilithium5(public_key: &[u8], message: &[u8], signature: &[u8]) -> Result<bool> {
    if public_key.len() != DILITHIUM5_PK_SIZE {
        anyhow::bail!("invalid Dilithium5 public key size: {}", public_key.len());
    }
    if signature.len() != DILITHIUM5_SIG_SIZE {
        anyhow::bail!("invalid Dilithium5 signature size: {}", signature.len());
    }

    let pk = dilithium5::PublicKey::from_bytes(public_key)
        .map_err(|_| anyhow::anyhow!("invalid Dilithium5 public key"))?;
    let sig = dilithium5::DetachedSignature::from_bytes(signature)
        .map_err(|_| anyhow::anyhow!("invalid Dilithium5 signature"))?;

    Ok(dilithium5::verify_detached_signature(&sig, message, &pk).is_ok())
}

/// Derive QBC address from Dilithium5 public key (matches Substrate pallet).
pub fn derive_address(public_key: &[u8]) -> [u8; 32] {
    let hash = Sha256::digest(public_key);
    let mut addr = [0u8; 32];
    addr.copy_from_slice(&hash);
    addr
}

// ── Encryption Helpers ──────────────────────────────────────────────────

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

/// Encrypt arbitrary bytes with Argon2id + AES-256-GCM.
fn encrypt_bytes(plaintext: &[u8], password: &str, salt: &[u8]) -> Result<Vec<u8>> {
    let key = derive_key(password, salt)?;
    let cipher = Aes256Gcm::new_from_slice(&key)?;

    let mut nonce_bytes = [0u8; NONCE_LEN];
    rand::thread_rng().fill_bytes(&mut nonce_bytes);
    let nonce = Nonce::from_slice(&nonce_bytes);

    let ciphertext = cipher
        .encrypt(nonce, plaintext)
        .map_err(|e| anyhow::anyhow!("encryption failed: {e}"))?;

    let mut result = Vec::with_capacity(NONCE_LEN + ciphertext.len());
    result.extend_from_slice(&nonce_bytes);
    result.extend(ciphertext);
    Ok(result)
}

/// Decrypt arbitrary bytes with Argon2id + AES-256-GCM.
fn decrypt_bytes(data: &[u8], password: &str, salt: &[u8]) -> Result<Vec<u8>> {
    if data.len() < NONCE_LEN + 1 {
        anyhow::bail!("encrypted data too short");
    }

    let key = derive_key(password, salt)?;
    let cipher = Aes256Gcm::new_from_slice(&key)?;
    let nonce = Nonce::from_slice(&data[..NONCE_LEN]);
    let ciphertext = &data[NONCE_LEN..];

    let plaintext = cipher
        .decrypt(nonce, ciphertext)
        .map_err(|_| anyhow::anyhow!("wrong password or corrupted keystore"))?;

    Ok(plaintext)
}

fn utc_timestamp() -> String {
    use std::time::{SystemTime, UNIX_EPOCH};
    let secs = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_secs();
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
    fn test_generate_dilithium5_wallet() {
        let (_dir, ks) = temp_keystore();
        let info = ks.generate("test-password", "my-wallet").unwrap();

        // v3 = Dilithium5
        assert_eq!(info.version, 3);
        // Address is 64 hex chars (32 bytes SHA-256)
        assert_eq!(info.address.len(), ADDRESS_HEX_LEN);
        // Public key is 5184 hex chars (2592 bytes Dilithium5)
        assert_eq!(info.public_key.len(), DILITHIUM5_PK_SIZE * 2);
        assert_eq!(info.label, "my-wallet");

        // Load it back
        let loaded = ks.load(&info.address, "test-password").unwrap();
        assert_eq!(loaded.address, info.address);
        assert_eq!(loaded.version, 3);
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
        assert!(wallets.iter().all(|w| w.version == 3));
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
    fn test_sign_and_verify() {
        let (_dir, ks) = temp_keystore();
        let info = ks.generate("pw", "signer").unwrap();

        let message = b"Hello, quantum world!";
        let sig = ks.sign(&info.address, "pw", message).unwrap();

        // Signature is exactly 4627 bytes
        assert_eq!(sig.len(), DILITHIUM5_SIG_SIZE);

        // Verify the signature
        let pk_bytes = ks.public_key_bytes(&info.address).unwrap();
        let valid = verify_dilithium5(&pk_bytes, message, &sig).unwrap();
        assert!(valid, "Dilithium5 signature should be valid");

        // Wrong message should fail
        let wrong_valid = verify_dilithium5(&pk_bytes, b"wrong message", &sig).unwrap();
        assert!(!wrong_valid, "Dilithium5 signature should NOT verify with wrong message");
    }

    #[test]
    fn test_export_and_import_dilithium5() {
        let (_dir, ks) = temp_keystore();
        let info = ks.generate("pw", "original").unwrap();

        // Export the keypair (PK||SK combined)
        let exported_hex = ks.export_secret(&info.address, "pw").unwrap();
        let combined_size = DILITHIUM5_PK_SIZE + DILITHIUM5_SK_SIZE;
        assert_eq!(exported_hex.len(), combined_size * 2);

        // Delete the original
        ks.delete(&info.address).unwrap();

        // Import it back
        let reimported = ks.import_hex(&exported_hex, "pw2", "reimported").unwrap();
        assert_eq!(reimported.address, info.address);
        assert_eq!(reimported.public_key, info.public_key);
        assert_eq!(reimported.version, 3);

        // Signing should still work after reimport
        let sig = ks.sign(&reimported.address, "pw2", b"test").unwrap();
        let pk_bytes = ks.public_key_bytes(&reimported.address).unwrap();
        assert!(verify_dilithium5(&pk_bytes, b"test", &sig).unwrap());
    }

    #[test]
    fn test_address_matches_substrate_derivation() {
        // Verify our address derivation matches the Substrate pallet:
        // Address = SHA-256(public_key) — full 32 bytes
        let (_dir, ks) = temp_keystore();
        let info = ks.generate("pw", "test").unwrap();

        let pk_bytes = hex::decode(&info.public_key).unwrap();
        let expected_addr = hex::encode(Sha256::digest(&pk_bytes));
        assert_eq!(info.address, expected_addr);
    }

    #[test]
    fn test_import_legacy_32byte_key() {
        let (_dir, ks) = temp_keystore();
        let secret_hex = "aa".repeat(32); // 64 hex chars = 32 bytes
        let info = ks.import_hex(&secret_hex, "pw", "legacy").unwrap();
        assert_eq!(info.version, 2);
        assert_eq!(info.address.len(), 40); // Legacy 20-byte address

        let loaded = ks.load(&info.address, "pw").unwrap();
        assert_eq!(loaded.address, info.address);
    }

    #[test]
    fn test_derive_address_deterministic() {
        let pk = vec![42u8; DILITHIUM5_PK_SIZE];
        let addr1 = derive_address(&pk);
        let addr2 = derive_address(&pk);
        assert_eq!(addr1, addr2);
    }
}
