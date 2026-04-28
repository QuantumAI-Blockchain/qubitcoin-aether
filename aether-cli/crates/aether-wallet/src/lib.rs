pub mod keystore;

use anyhow::Result;
use serde::{Deserialize, Serialize};
use std::path::PathBuf;

pub use keystore::{
    derive_address, verify_dilithium5, Keystore,
    DILITHIUM5_PK_SIZE, DILITHIUM5_SIG_SIZE, DILITHIUM5_SK_SIZE,
    ADDRESS_HEX_LEN, ADDRESS_SIZE,
};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WalletInfo {
    pub address: String,
    pub public_key: String,
    pub label: String,
    pub created_at: String,
    /// Keystore version: 1=legacy(no argon2), 2=argon2+SHA256, 3=Dilithium5
    pub version: u8,
}

impl WalletInfo {
    /// Whether this wallet uses quantum-secure Dilithium5 keys.
    pub fn is_quantum_secure(&self) -> bool {
        self.version >= 3
    }
}

/// Get the default keystore directory.
pub fn default_keystore_dir() -> PathBuf {
    dirs::data_dir()
        .unwrap_or_else(|| PathBuf::from("."))
        .join("aether-cli")
        .join("keystore")
}

/// Wallet manager wrapping the encrypted keystore.
pub struct Wallet {
    keystore: Keystore,
}

impl Wallet {
    pub fn open(keystore_dir: PathBuf) -> Result<Self> {
        Ok(Self {
            keystore: Keystore::new(keystore_dir),
        })
    }

    pub fn exists(&self) -> bool {
        self.keystore.has_any()
    }

    pub fn create(&self, password: &str, label: &str) -> Result<WalletInfo> {
        self.keystore.generate(password, label)
    }

    pub fn import_hex(&self, secret_hex: &str, password: &str, label: &str) -> Result<WalletInfo> {
        self.keystore.import_hex(secret_hex, password, label)
    }

    pub fn load(&self, address: &str, password: &str) -> Result<WalletInfo> {
        self.keystore.load(address, password)
    }

    pub fn list(&self) -> Result<Vec<WalletInfo>> {
        self.keystore.list_wallets()
    }

    pub fn delete(&self, address: &str) -> Result<()> {
        self.keystore.delete(address)
    }

    pub fn export_secret(&self, address: &str, password: &str) -> Result<String> {
        self.keystore.export_secret(address, password)
    }

    /// Get the default (first) wallet address without decrypting.
    pub fn address(&self) -> Result<Option<String>> {
        self.keystore.default_address()
    }

    /// Sign a message with the wallet's Dilithium5 key.
    /// Returns the 4627-byte detached signature.
    pub fn sign(&self, address: &str, password: &str, message: &[u8]) -> Result<Vec<u8>> {
        self.keystore.sign(address, password, message)
    }

    /// Get the raw Dilithium5 public key bytes for a wallet.
    pub fn public_key_bytes(&self, address: &str) -> Result<Vec<u8>> {
        self.keystore.public_key_bytes(address)
    }

    /// Get the wallet version (1=legacy, 2=argon2, 3=Dilithium5).
    pub fn wallet_version(&self, address: &str) -> Result<u8> {
        self.keystore.wallet_version(address)
    }
}
