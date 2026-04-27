pub mod keystore;

use anyhow::Result;
use serde::{Deserialize, Serialize};
use std::path::PathBuf;

pub use keystore::Keystore;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WalletInfo {
    pub address: String,
    pub public_key: String,
    pub label: String,
    pub created_at: String,
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
}
