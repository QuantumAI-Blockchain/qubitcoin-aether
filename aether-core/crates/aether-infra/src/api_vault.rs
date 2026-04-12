//! API key vault: secure storage, tier enforcement, and rate limiting.
//!
//! Provides in-memory API key management with encryption key derivation,
//! per-key metadata tracking, shared key pool, tier-based rate limiting,
//! and usage statistics. Actual AES-256-GCM encryption is handled by the
//! Python layer (cryptography package) or future Rust crypto; this module
//! manages the vault logic, key lifecycle, and rate-limit bookkeeping.
//!
//! Ported from: `src/qubitcoin/aether/api_key_vault.py`

use std::collections::HashMap;

use chrono::Utc;
use pyo3::prelude::*;
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};

// ─── API Tiers ──────────────────────────────────────────────────────────────

/// API access tier with associated rate limits.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[pyclass(eq, eq_int)]
pub enum ApiTier {
    /// Free tier: 5 chat/day, 10 KG lookups/day.
    Free,
    /// Developer tier: ~1 QBC/day.
    Developer,
    /// Professional tier: ~10 QBC/day.
    Professional,
    /// Institutional tier: ~100 QBC/day.
    Institutional,
    /// Enterprise tier: custom limits.
    Enterprise,
}

#[pymethods]
impl ApiTier {
    /// Wire-format string for the tier.
    pub fn as_str(&self) -> &'static str {
        match self {
            Self::Free => "free",
            Self::Developer => "developer",
            Self::Professional => "professional",
            Self::Institutional => "institutional",
            Self::Enterprise => "enterprise",
        }
    }

    /// Parse from string.
    #[staticmethod]
    pub fn from_str(s: &str) -> Option<ApiTier> {
        match s.to_lowercase().as_str() {
            "free" => Some(Self::Free),
            "developer" | "dev" => Some(Self::Developer),
            "professional" | "pro" => Some(Self::Professional),
            "institutional" => Some(Self::Institutional),
            "enterprise" => Some(Self::Enterprise),
            _ => None,
        }
    }

    /// Maximum chat requests per day for this tier.
    pub fn daily_chat_limit(&self) -> u64 {
        match self {
            Self::Free => 5,
            Self::Developer => 1_000,
            Self::Professional => 10_000,
            Self::Institutional => 100_000,
            Self::Enterprise => u64::MAX,
        }
    }

    /// Maximum knowledge graph lookups per day.
    pub fn daily_kg_limit(&self) -> u64 {
        match self {
            Self::Free => 10,
            Self::Developer => 10_000,
            Self::Professional => 100_000,
            Self::Institutional => u64::MAX,
            Self::Enterprise => u64::MAX,
        }
    }

    /// Maximum inference requests per day.
    pub fn daily_inference_limit(&self) -> u64 {
        match self {
            Self::Free => 0,
            Self::Developer => 100,
            Self::Professional => 1_000,
            Self::Institutional => 10_000,
            Self::Enterprise => u64::MAX,
        }
    }

    /// Approximate daily cost in QBC.
    pub fn daily_cost_qbc(&self) -> f64 {
        match self {
            Self::Free => 0.0,
            Self::Developer => 1.0,
            Self::Professional => 10.0,
            Self::Institutional => 100.0,
            Self::Enterprise => 0.0, // custom pricing
        }
    }
}

// ─── Stored Key ─────────────────────────────────────────────────────────────

/// Metadata for a stored API key. Never contains the plaintext key material.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[pyclass(get_all, set_all)]
pub struct StoredKey {
    pub key_id: String,
    /// LLM provider: openai, claude, grok, gemini, mistral, custom.
    pub provider: String,
    /// Preferred model for this key.
    pub model: String,
    /// QBC address of the key owner.
    pub owner_address: String,
    /// Unix timestamp when created.
    pub created_at: f64,
    /// Unix timestamp of last use.
    pub last_used_at: f64,
    /// Total number of times this key has been used.
    pub use_count: u64,
    /// Whether this key is in the shared pool.
    pub is_shared: bool,
    /// Basis points (15% = 1500) reward for shared key usage.
    pub shared_reward_bps: u32,
    /// Whether this key is active (false = revoked).
    pub is_active: bool,
    /// User-friendly label.
    pub label: String,
}

#[pymethods]
impl StoredKey {
    #[new]
    #[pyo3(signature = (key_id, provider, owner_address, model="".to_string(), label="".to_string(), is_shared=false, shared_reward_bps=1500))]
    pub fn new(
        key_id: String,
        provider: String,
        owner_address: String,
        model: String,
        label: String,
        is_shared: bool,
        shared_reward_bps: u32,
    ) -> Self {
        let now = Utc::now().timestamp() as f64;
        Self {
            key_id,
            provider,
            model,
            owner_address,
            created_at: now,
            last_used_at: 0.0,
            use_count: 0,
            is_shared,
            shared_reward_bps,
            is_active: true,
            label,
        }
    }

    /// Record that this key was used.
    pub fn record_use(&mut self) {
        self.last_used_at = Utc::now().timestamp() as f64;
        self.use_count += 1;
    }

    /// Deactivate (revoke) this key.
    pub fn revoke(&mut self) {
        self.is_active = false;
    }
}

// ─── Rate Limit Entry ───────────────────────────────────────────────────────

/// Per-key or per-address rate limit tracking entry.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[pyclass(get_all)]
pub struct RateLimitEntry {
    /// Identifier (key_id or address).
    pub identifier: String,
    /// API tier for this entry.
    pub tier: String,
    /// Chat requests used in current window.
    pub chat_used: u64,
    /// KG lookups used in current window.
    pub kg_used: u64,
    /// Inference requests used in current window.
    pub inference_used: u64,
    /// Start of current rate limit window (Unix timestamp, day boundary).
    pub window_start: f64,
}

#[pymethods]
impl RateLimitEntry {
    #[new]
    #[pyo3(signature = (identifier, tier="free".to_string()))]
    pub fn new(identifier: String, tier: String) -> Self {
        let now = Utc::now().timestamp() as f64;
        // Round down to day boundary
        let day_secs = 86400.0;
        let window_start = (now / day_secs).floor() * day_secs;
        Self {
            identifier,
            tier,
            chat_used: 0,
            kg_used: 0,
            inference_used: 0,
            window_start,
        }
    }

    /// Reset counters if the window has expired (new day).
    pub fn maybe_reset(&mut self) {
        let now = Utc::now().timestamp() as f64;
        let day_secs = 86400.0;
        let current_window = (now / day_secs).floor() * day_secs;
        if current_window > self.window_start {
            self.chat_used = 0;
            self.kg_used = 0;
            self.inference_used = 0;
            self.window_start = current_window;
        }
    }

    /// Check if a chat request is allowed under the rate limit.
    pub fn can_chat(&mut self) -> bool {
        self.maybe_reset();
        let tier = ApiTier::from_str(&self.tier).unwrap_or(ApiTier::Free);
        self.chat_used < tier.daily_chat_limit()
    }

    /// Check if a KG lookup is allowed under the rate limit.
    pub fn can_kg_lookup(&mut self) -> bool {
        self.maybe_reset();
        let tier = ApiTier::from_str(&self.tier).unwrap_or(ApiTier::Free);
        self.kg_used < tier.daily_kg_limit()
    }

    /// Check if an inference request is allowed under the rate limit.
    pub fn can_inference(&mut self) -> bool {
        self.maybe_reset();
        let tier = ApiTier::from_str(&self.tier).unwrap_or(ApiTier::Free);
        self.inference_used < tier.daily_inference_limit()
    }

    /// Record a chat request. Returns false if rate limited.
    pub fn record_chat(&mut self) -> bool {
        if !self.can_chat() {
            return false;
        }
        self.chat_used += 1;
        true
    }

    /// Record a KG lookup. Returns false if rate limited.
    pub fn record_kg_lookup(&mut self) -> bool {
        if !self.can_kg_lookup() {
            return false;
        }
        self.kg_used += 1;
        true
    }

    /// Record an inference request. Returns false if rate limited.
    pub fn record_inference(&mut self) -> bool {
        if !self.can_inference() {
            return false;
        }
        self.inference_used += 1;
        true
    }
}

// ─── Vault Statistics ───────────────────────────────────────────────────────

/// Statistics about the API key vault (never includes key material).
#[derive(Debug, Clone, Serialize, Deserialize)]
#[pyclass(get_all)]
pub struct VaultStats {
    pub total_keys: usize,
    pub active_keys: usize,
    pub shared_pool_size: usize,
    pub shared_pool_providers: Vec<String>,
    pub total_owners: usize,
    pub by_provider: HashMap<String, usize>,
}

// ─── API Key Vault ──────────────────────────────────────────────────────────

/// Secure vault for LLM API keys with ownership tracking, shared pool, and rate limiting.
///
/// Key encryption/decryption is handled externally (Python cryptography or
/// Rust ring/aes-gcm). This vault manages metadata, ownership, shared pool
/// membership, and rate limiting logic.
#[pyclass]
pub struct APIKeyVault {
    /// key_id -> StoredKey metadata
    keys: HashMap<String, StoredKey>,
    /// owner_address -> [key_ids]
    owner_keys: HashMap<String, Vec<String>>,
    /// provider -> [key_ids] (shared pool only)
    shared_pool: HashMap<String, Vec<String>>,
    /// identifier -> RateLimitEntry
    rate_limits: HashMap<String, RateLimitEntry>,
}

#[pymethods]
impl APIKeyVault {
    #[new]
    pub fn new() -> Self {
        Self {
            keys: HashMap::new(),
            owner_keys: HashMap::new(),
            shared_pool: HashMap::new(),
            rate_limits: HashMap::new(),
        }
    }

    /// Generate a key_id from owner, provider, and timestamp.
    #[staticmethod]
    pub fn generate_key_id(owner_address: &str, provider: &str, nonce: &str) -> String {
        let input = format!(
            "{}:{}:{}:{}",
            owner_address,
            provider,
            Utc::now().timestamp(),
            nonce,
        );
        let hash = Sha256::digest(input.as_bytes());
        hex::encode(&hash[..8]) // 16 hex chars
    }

    /// Store a key's metadata. Returns the StoredKey.
    /// The caller is responsible for encrypting and storing the actual key bytes.
    #[pyo3(signature = (key_id, owner_address, provider, model="".to_string(), label="".to_string(), is_shared=false, shared_reward_bps=1500))]
    pub fn store(
        &mut self,
        key_id: String,
        owner_address: String,
        provider: String,
        model: String,
        label: String,
        is_shared: bool,
        shared_reward_bps: u32,
    ) -> StoredKey {
        let stored = StoredKey::new(
            key_id.clone(),
            provider.clone(),
            owner_address.clone(),
            model,
            label,
            is_shared,
            shared_reward_bps,
        );

        self.keys.insert(key_id.clone(), stored.clone());

        // Index by owner
        self.owner_keys
            .entry(owner_address)
            .or_default()
            .push(key_id.clone());

        // Shared pool
        if is_shared {
            self.shared_pool
                .entry(provider)
                .or_default()
                .push(key_id);
        }

        stored
    }

    /// Get key metadata by key_id. Returns None if not found or inactive.
    pub fn get_metadata(&self, key_id: &str) -> Option<StoredKey> {
        self.keys.get(key_id).and_then(|k| {
            if k.is_active { Some(k.clone()) } else { None }
        })
    }

    /// Record that a key was used (updates usage stats).
    pub fn record_key_use(&mut self, key_id: &str) -> bool {
        if let Some(key) = self.keys.get_mut(key_id) {
            if key.is_active {
                key.record_use();
                return true;
            }
        }
        false
    }

    /// Get all key metadata for an owner (never includes key material).
    pub fn get_owner_keys(&self, owner_address: &str) -> Vec<StoredKey> {
        self.owner_keys
            .get(owner_address)
            .map(|ids| {
                ids.iter()
                    .filter_map(|id| self.keys.get(id))
                    .cloned()
                    .collect()
            })
            .unwrap_or_default()
    }

    /// Get an active shared key_id for a provider.
    pub fn get_shared_key_id(&self, provider: &str) -> Option<String> {
        self.shared_pool.get(provider).and_then(|ids| {
            ids.iter()
                .find(|id| {
                    self.keys.get(*id).map(|k| k.is_active).unwrap_or(false)
                })
                .cloned()
        })
    }

    /// Get all shared key_ids for a provider (or all providers if empty).
    pub fn get_shared_pool(&self, provider: &str) -> Vec<StoredKey> {
        if provider.is_empty() {
            self.shared_pool
                .values()
                .flatten()
                .filter_map(|id| {
                    self.keys.get(id).and_then(|k| {
                        if k.is_active { Some(k.clone()) } else { None }
                    })
                })
                .collect()
        } else {
            self.shared_pool
                .get(provider)
                .map(|ids| {
                    ids.iter()
                        .filter_map(|id| {
                            self.keys.get(id).and_then(|k| {
                                if k.is_active { Some(k.clone()) } else { None }
                            })
                        })
                        .collect()
                })
                .unwrap_or_default()
        }
    }

    /// Revoke a key. Only the owner can revoke. Returns true on success.
    pub fn revoke(&mut self, key_id: &str, owner_address: &str) -> bool {
        if let Some(key) = self.keys.get_mut(key_id) {
            if key.owner_address != owner_address {
                return false;
            }
            key.revoke();

            // Remove from shared pool
            if key.is_shared {
                if let Some(pool) = self.shared_pool.get_mut(&key.provider) {
                    pool.retain(|id| id != key_id);
                }
            }
            true
        } else {
            false
        }
    }

    /// Permanently delete a key. Only the owner can delete.
    pub fn delete(&mut self, key_id: &str, owner_address: &str) -> bool {
        let key = match self.keys.get(key_id) {
            Some(k) if k.owner_address == owner_address => k.clone(),
            _ => return false,
        };

        self.keys.remove(key_id);

        // Remove from owner index
        if let Some(ids) = self.owner_keys.get_mut(owner_address) {
            ids.retain(|id| id != key_id);
        }

        // Remove from shared pool
        if key.is_shared {
            if let Some(pool) = self.shared_pool.get_mut(&key.provider) {
                pool.retain(|id| id != key_id);
            }
        }

        true
    }

    /// Toggle shared pool membership for a key.
    pub fn toggle_shared(
        &mut self,
        key_id: &str,
        owner_address: &str,
        shared: bool,
    ) -> bool {
        let key = match self.keys.get_mut(key_id) {
            Some(k) if k.owner_address == owner_address => k,
            _ => return false,
        };

        if key.is_shared == shared {
            return true; // no change
        }

        let provider = key.provider.clone();
        key.is_shared = shared;

        if shared {
            self.shared_pool
                .entry(provider)
                .or_default()
                .push(key_id.to_string());
        } else {
            if let Some(pool) = self.shared_pool.get_mut(&provider) {
                pool.retain(|id| id != key_id);
            }
        }
        true
    }

    /// Get or create a rate limit entry for an identifier.
    pub fn get_rate_limit(&mut self, identifier: &str, tier: &str) -> RateLimitEntry {
        let entry = self
            .rate_limits
            .entry(identifier.to_string())
            .or_insert_with(|| RateLimitEntry::new(identifier.to_string(), tier.to_string()));
        entry.maybe_reset();
        entry.clone()
    }

    /// Record a chat request for rate limiting. Returns true if allowed.
    pub fn rate_limit_chat(&mut self, identifier: &str, tier: &str) -> bool {
        let entry = self
            .rate_limits
            .entry(identifier.to_string())
            .or_insert_with(|| RateLimitEntry::new(identifier.to_string(), tier.to_string()));
        entry.record_chat()
    }

    /// Record a KG lookup for rate limiting. Returns true if allowed.
    pub fn rate_limit_kg(&mut self, identifier: &str, tier: &str) -> bool {
        let entry = self
            .rate_limits
            .entry(identifier.to_string())
            .or_insert_with(|| RateLimitEntry::new(identifier.to_string(), tier.to_string()));
        entry.record_kg_lookup()
    }

    /// Record an inference request for rate limiting. Returns true if allowed.
    pub fn rate_limit_inference(&mut self, identifier: &str, tier: &str) -> bool {
        let entry = self
            .rate_limits
            .entry(identifier.to_string())
            .or_insert_with(|| RateLimitEntry::new(identifier.to_string(), tier.to_string()));
        entry.record_inference()
    }

    /// Get vault statistics (never includes key material).
    pub fn get_stats(&self) -> VaultStats {
        let mut by_provider: HashMap<String, usize> = HashMap::new();
        for key in self.keys.values() {
            if key.is_active {
                *by_provider.entry(key.provider.clone()).or_default() += 1;
            }
        }

        VaultStats {
            total_keys: self.keys.len(),
            active_keys: self.keys.values().filter(|k| k.is_active).count(),
            shared_pool_size: self
                .shared_pool
                .values()
                .map(|v| v.len())
                .sum(),
            shared_pool_providers: self.shared_pool.keys().cloned().collect(),
            total_owners: self.owner_keys.len(),
            by_provider,
        }
    }

    /// Get per-provider shared pool key counts.
    pub fn get_shared_pool_counts(&self) -> HashMap<String, usize> {
        self.shared_pool
            .iter()
            .map(|(k, v)| (k.clone(), v.len()))
            .collect()
    }
}

// Hex encoding helper (no external dep needed)
mod hex {
    pub fn encode(bytes: &[u8]) -> String {
        bytes.iter().map(|b| format!("{:02x}", b)).collect()
    }
}

// ──────────────────────────────────────────────────────────────────────────────
// Tests
// ──────────────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_api_tier_roundtrip() {
        for tier in [
            ApiTier::Free,
            ApiTier::Developer,
            ApiTier::Professional,
            ApiTier::Institutional,
            ApiTier::Enterprise,
        ] {
            let s = tier.as_str();
            let parsed = ApiTier::from_str(s).unwrap();
            assert_eq!(tier, parsed);
        }
    }

    #[test]
    fn test_api_tier_aliases() {
        assert_eq!(ApiTier::from_str("dev"), Some(ApiTier::Developer));
        assert_eq!(ApiTier::from_str("pro"), Some(ApiTier::Professional));
        assert_eq!(ApiTier::from_str("FREE"), Some(ApiTier::Free));
        assert!(ApiTier::from_str("unknown").is_none());
    }

    #[test]
    fn test_api_tier_limits() {
        assert_eq!(ApiTier::Free.daily_chat_limit(), 5);
        assert_eq!(ApiTier::Developer.daily_chat_limit(), 1_000);
        assert_eq!(ApiTier::Free.daily_inference_limit(), 0);
        assert!(ApiTier::Enterprise.daily_chat_limit() > 1_000_000);
    }

    #[test]
    fn test_api_tier_costs() {
        assert_eq!(ApiTier::Free.daily_cost_qbc(), 0.0);
        assert_eq!(ApiTier::Developer.daily_cost_qbc(), 1.0);
        assert_eq!(ApiTier::Professional.daily_cost_qbc(), 10.0);
    }

    #[test]
    fn test_stored_key_creation() {
        let key = StoredKey::new(
            "k1".into(), "openai".into(), "addr1".into(),
            "gpt-4".into(), "My key".into(), false, 1500,
        );
        assert_eq!(key.key_id, "k1");
        assert_eq!(key.provider, "openai");
        assert!(key.is_active);
        assert_eq!(key.use_count, 0);
    }

    #[test]
    fn test_stored_key_record_use() {
        let mut key = StoredKey::new(
            "k1".into(), "openai".into(), "addr1".into(),
            "".into(), "".into(), false, 1500,
        );
        key.record_use();
        assert_eq!(key.use_count, 1);
        assert!(key.last_used_at > 0.0);
    }

    #[test]
    fn test_stored_key_revoke() {
        let mut key = StoredKey::new(
            "k1".into(), "openai".into(), "addr1".into(),
            "".into(), "".into(), false, 1500,
        );
        assert!(key.is_active);
        key.revoke();
        assert!(!key.is_active);
    }

    #[test]
    fn test_generate_key_id() {
        let id = APIKeyVault::generate_key_id("addr1", "openai", "abc");
        assert_eq!(id.len(), 16);
        // Deterministic for same timestamp, but different nonce gives different id
        let id2 = APIKeyVault::generate_key_id("addr1", "openai", "xyz");
        assert_ne!(id, id2);
    }

    #[test]
    fn test_vault_store_and_get() {
        let mut vault = APIKeyVault::new();
        vault.store("k1".into(), "addr1".into(), "openai".into(),
                     "gpt-4".into(), "test".into(), false, 1500);

        let meta = vault.get_metadata("k1").unwrap();
        assert_eq!(meta.provider, "openai");
        assert!(meta.is_active);

        assert!(vault.get_metadata("nonexistent").is_none());
    }

    #[test]
    fn test_vault_owner_keys() {
        let mut vault = APIKeyVault::new();
        vault.store("k1".into(), "addr1".into(), "openai".into(),
                     "".into(), "".into(), false, 1500);
        vault.store("k2".into(), "addr1".into(), "claude".into(),
                     "".into(), "".into(), false, 1500);
        vault.store("k3".into(), "addr2".into(), "openai".into(),
                     "".into(), "".into(), false, 1500);

        let keys = vault.get_owner_keys("addr1");
        assert_eq!(keys.len(), 2);

        let keys = vault.get_owner_keys("addr2");
        assert_eq!(keys.len(), 1);
    }

    #[test]
    fn test_vault_revoke() {
        let mut vault = APIKeyVault::new();
        vault.store("k1".into(), "addr1".into(), "openai".into(),
                     "".into(), "".into(), true, 1500);

        // Wrong owner can't revoke
        assert!(!vault.revoke("k1", "addr2"));

        // Right owner can revoke
        assert!(vault.revoke("k1", "addr1"));
        assert!(vault.get_metadata("k1").is_none()); // inactive
    }

    #[test]
    fn test_vault_delete() {
        let mut vault = APIKeyVault::new();
        vault.store("k1".into(), "addr1".into(), "openai".into(),
                     "".into(), "".into(), true, 1500);

        assert!(!vault.delete("k1", "addr2")); // wrong owner
        assert!(vault.delete("k1", "addr1"));

        let stats = vault.get_stats();
        assert_eq!(stats.total_keys, 0);
    }

    #[test]
    fn test_vault_shared_pool() {
        let mut vault = APIKeyVault::new();
        vault.store("k1".into(), "addr1".into(), "openai".into(),
                     "".into(), "".into(), true, 1500);
        vault.store("k2".into(), "addr2".into(), "openai".into(),
                     "".into(), "".into(), false, 1500);

        let shared = vault.get_shared_pool("openai");
        assert_eq!(shared.len(), 1);
        assert_eq!(shared[0].key_id, "k1");

        let shared_id = vault.get_shared_key_id("openai").unwrap();
        assert_eq!(shared_id, "k1");

        assert!(vault.get_shared_key_id("claude").is_none());
    }

    #[test]
    fn test_vault_toggle_shared() {
        let mut vault = APIKeyVault::new();
        vault.store("k1".into(), "addr1".into(), "openai".into(),
                     "".into(), "".into(), false, 1500);

        assert!(vault.get_shared_pool("openai").is_empty());

        vault.toggle_shared("k1", "addr1", true);
        assert_eq!(vault.get_shared_pool("openai").len(), 1);

        vault.toggle_shared("k1", "addr1", false);
        assert!(vault.get_shared_pool("openai").is_empty());
    }

    #[test]
    fn test_vault_record_use() {
        let mut vault = APIKeyVault::new();
        vault.store("k1".into(), "addr1".into(), "openai".into(),
                     "".into(), "".into(), false, 1500);

        assert!(vault.record_key_use("k1"));
        let meta = vault.get_metadata("k1").unwrap();
        assert_eq!(meta.use_count, 1);

        assert!(!vault.record_key_use("nonexistent"));
    }

    #[test]
    fn test_rate_limit_free_tier() {
        let mut vault = APIKeyVault::new();

        // Free tier: 5 chat/day
        for _ in 0..5 {
            assert!(vault.rate_limit_chat("user1", "free"));
        }
        assert!(!vault.rate_limit_chat("user1", "free"));

        // Free tier: 0 inference/day
        assert!(!vault.rate_limit_inference("user1", "free"));
    }

    #[test]
    fn test_rate_limit_developer_tier() {
        let mut vault = APIKeyVault::new();
        // Developer tier: 1000 chat/day — just test first few work
        for _ in 0..10 {
            assert!(vault.rate_limit_chat("dev1", "developer"));
        }
    }

    #[test]
    fn test_rate_limit_entry_creation() {
        let entry = RateLimitEntry::new("user1".into(), "free".into());
        assert_eq!(entry.chat_used, 0);
        assert_eq!(entry.kg_used, 0);
        assert!(entry.window_start > 0.0);
    }

    #[test]
    fn test_vault_stats() {
        let mut vault = APIKeyVault::new();
        vault.store("k1".into(), "addr1".into(), "openai".into(),
                     "".into(), "".into(), true, 1500);
        vault.store("k2".into(), "addr1".into(), "claude".into(),
                     "".into(), "".into(), false, 1500);

        let stats = vault.get_stats();
        assert_eq!(stats.total_keys, 2);
        assert_eq!(stats.active_keys, 2);
        assert_eq!(stats.shared_pool_size, 1);
        assert_eq!(stats.total_owners, 1);
        assert_eq!(*stats.by_provider.get("openai").unwrap(), 1);
        assert_eq!(*stats.by_provider.get("claude").unwrap(), 1);
    }

    #[test]
    fn test_vault_shared_pool_counts() {
        let mut vault = APIKeyVault::new();
        vault.store("k1".into(), "a".into(), "openai".into(),
                     "".into(), "".into(), true, 1500);
        vault.store("k2".into(), "b".into(), "openai".into(),
                     "".into(), "".into(), true, 1500);
        vault.store("k3".into(), "c".into(), "claude".into(),
                     "".into(), "".into(), true, 1500);

        let counts = vault.get_shared_pool_counts();
        assert_eq!(*counts.get("openai").unwrap(), 2);
        assert_eq!(*counts.get("claude").unwrap(), 1);
    }
}
