pub mod keystore;

use anyhow::Result;
use serde::{Deserialize, Serialize};
use std::path::PathBuf;

pub use keystore::Keystore;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WalletInfo {
    pub address: String,
    pub public_key: String,
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
        self.keystore.has_key()
    }

    pub fn create(&self, password: &str) -> Result<WalletInfo> {
        self.keystore.generate(password)
    }

    pub fn load(&self, password: &str) -> Result<WalletInfo> {
        self.keystore.load(password)
    }

    pub fn address(&self) -> Result<Option<String>> {
        self.keystore.address()
    }
}
