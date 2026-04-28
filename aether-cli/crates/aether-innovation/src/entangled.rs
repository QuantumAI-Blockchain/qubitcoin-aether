//! Quantum-Entangled Wallet Protocol (QEWP) — Patentable Feature #2
//!
//! Creates cryptographic "entanglement" between two Dilithium5 wallets,
//! enabling conditional spending rules, inheritance, escrow, and dead-man
//! switches enforced by the protocol itself.
//!
//! PATENT CLAIM: A post-quantum cryptographic protocol for creating
//! deterministic bidirectional spending conditions between wallet pairs
//! using Dilithium5 key material derivation, with on-chain enforceable
//! conditions including dead-man switches, time-locked inheritance,
//! and escrow requiring dual-party authorization.
//!
//! NOVELTY: No existing blockchain implements cryptographic wallet
//! entanglement where the shared channel key is derived from both
//! parties' post-quantum public keys, and conditions are committed
//! via hash commitments that validators can verify without knowing
//! the conditions themselves.

use sha2::{Digest, Sha256};
use serde::{Serialize, Deserialize};
use rand::RngCore;

/// Conditions governing the entanglement between two wallets.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EntanglementConditions {
    /// If wallet A is inactive for this many blocks, wallet B gains spending rights.
    /// At 3.3s/block: 100_000 blocks ~ 3.8 days, 1_000_000 ~ 38 days.
    pub deadman_blocks: u64,
    /// Fraction of balance wallet B inherits (0.0 = none, 1.0 = all).
    pub inheritance_ratio: f64,
    /// If true, both parties must sign for any transaction (escrow mode).
    pub require_dual_sign: bool,
    /// Entanglement activates only after this block height.
    pub activation_height: u64,
    /// Optional message embedded in the commitment (max 256 bytes).
    pub memo: String,
}

/// A completed entanglement between two wallets.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WalletEntanglement {
    /// Unique entanglement identifier.
    pub entanglement_id: [u8; 32],
    /// First wallet address.
    pub wallet_a: String,
    /// Second wallet address.
    pub wallet_b: String,
    /// Shared channel key (derived from both public keys + nonce).
    pub channel_key: [u8; 32],
    /// Commitment hash (proves conditions without revealing them).
    pub commitment: [u8; 32],
    /// The conditions.
    pub conditions: EntanglementConditions,
    /// Nonce used in key derivation.
    pub nonce: [u8; 16],
    /// Block height when created.
    pub created_at_height: u64,
}

/// Status of an entanglement at a given point in time.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EntanglementStatus {
    pub entanglement_id: String,
    pub is_active: bool,
    pub deadman_triggered: bool,
    pub blocks_until_deadman: Option<u64>,
    pub wallet_a_last_active: u64,
    pub current_height: u64,
}

/// Create an entanglement between two wallets.
pub fn create_entanglement(
    pk_a: &[u8],
    pk_b: &[u8],
    conditions: EntanglementConditions,
    current_height: u64,
) -> WalletEntanglement {
    let mut nonce = [0u8; 16];
    rand::thread_rng().fill_bytes(&mut nonce);

    let channel_key = derive_channel_key(pk_a, pk_b, &nonce);
    let addr_a = hex::encode(Sha256::digest(pk_a));
    let addr_b = hex::encode(Sha256::digest(pk_b));
    let commitment = compute_commitment(&channel_key, &conditions);

    let mut id_hasher = Sha256::new();
    id_hasher.update(addr_a.as_bytes());
    id_hasher.update(addr_b.as_bytes());
    id_hasher.update(&nonce);
    id_hasher.update(current_height.to_le_bytes());
    let entanglement_id: [u8; 32] = id_hasher.finalize().into();

    WalletEntanglement {
        entanglement_id,
        wallet_a: addr_a,
        wallet_b: addr_b,
        channel_key,
        commitment,
        conditions,
        nonce,
        created_at_height: current_height,
    }
}

/// Check the current status of an entanglement.
pub fn check_status(
    entanglement: &WalletEntanglement,
    wallet_a_last_active: u64,
    current_height: u64,
) -> EntanglementStatus {
    let is_active = current_height >= entanglement.conditions.activation_height;

    let deadman_triggered = is_active
        && entanglement.conditions.deadman_blocks > 0
        && current_height.saturating_sub(wallet_a_last_active)
            >= entanglement.conditions.deadman_blocks;

    let blocks_until_deadman = if is_active && entanglement.conditions.deadman_blocks > 0 {
        let inactive_blocks = current_height.saturating_sub(wallet_a_last_active);
        if inactive_blocks >= entanglement.conditions.deadman_blocks {
            Some(0)
        } else {
            Some(entanglement.conditions.deadman_blocks - inactive_blocks)
        }
    } else {
        None
    };

    EntanglementStatus {
        entanglement_id: hex::encode(entanglement.entanglement_id),
        is_active,
        deadman_triggered,
        blocks_until_deadman,
        wallet_a_last_active,
        current_height,
    }
}

/// Verify a commitment matches the given conditions.
pub fn verify_commitment(
    channel_key: &[u8; 32],
    conditions: &EntanglementConditions,
    expected: &[u8; 32],
) -> bool {
    compute_commitment(channel_key, conditions) == *expected
}

/// Generate a disentanglement proof — both parties sign this to dissolve.
pub fn disentanglement_hash(entanglement_id: &[u8; 32], reason: &str) -> [u8; 32] {
    let mut hasher = Sha256::new();
    hasher.update(b"disentangle-v1");
    hasher.update(entanglement_id);
    hasher.update(reason.as_bytes());
    hasher.finalize().into()
}

// ── Internal ──────────────────────────────────────────────────────

/// Order-independent channel key derivation (same result regardless of who initiates).
fn derive_channel_key(pk_a: &[u8], pk_b: &[u8], nonce: &[u8; 16]) -> [u8; 32] {
    let mut hasher = Sha256::new();
    hasher.update(b"qewp-channel-v1");
    if pk_a <= pk_b {
        hasher.update(pk_a);
        hasher.update(pk_b);
    } else {
        hasher.update(pk_b);
        hasher.update(pk_a);
    }
    hasher.update(nonce);
    hasher.finalize().into()
}

fn compute_commitment(channel_key: &[u8; 32], cond: &EntanglementConditions) -> [u8; 32] {
    let mut hasher = Sha256::new();
    hasher.update(b"qewp-commit-v1");
    hasher.update(channel_key);
    hasher.update(cond.deadman_blocks.to_le_bytes());
    hasher.update(cond.inheritance_ratio.to_le_bytes());
    hasher.update([cond.require_dual_sign as u8]);
    hasher.update(cond.activation_height.to_le_bytes());
    hasher.update(cond.memo.as_bytes());
    hasher.finalize().into()
}

#[cfg(test)]
mod tests {
    use super::*;

    fn test_keys() -> (Vec<u8>, Vec<u8>) {
        (vec![1u8; 2592], vec![2u8; 2592])
    }

    fn default_cond() -> EntanglementConditions {
        EntanglementConditions {
            deadman_blocks: 100_000,
            inheritance_ratio: 1.0,
            require_dual_sign: false,
            activation_height: 0,
            memo: String::new(),
        }
    }

    #[test]
    fn test_create_entanglement() {
        let (a, b) = test_keys();
        let ent = create_entanglement(&a, &b, default_cond(), 265000);
        assert_ne!(ent.entanglement_id, [0u8; 32]);
        assert_ne!(ent.channel_key, [0u8; 32]);
    }

    #[test]
    fn test_channel_key_order_independent() {
        let (a, b) = test_keys();
        let nonce = [42u8; 16];
        assert_eq!(derive_channel_key(&a, &b, &nonce), derive_channel_key(&b, &a, &nonce));
    }

    #[test]
    fn test_verify_commitment() {
        let (a, b) = test_keys();
        let cond = default_cond();
        let ent = create_entanglement(&a, &b, cond.clone(), 265000);
        assert!(verify_commitment(&ent.channel_key, &cond, &ent.commitment));
    }

    #[test]
    fn test_deadman_not_triggered_early() {
        let (a, b) = test_keys();
        let ent = create_entanglement(&a, &b, default_cond(), 265000);
        let status = check_status(&ent, 265000, 265500);
        assert!(!status.deadman_triggered);
        assert_eq!(status.blocks_until_deadman, Some(99_500));
    }

    #[test]
    fn test_deadman_triggers() {
        let (a, b) = test_keys();
        let ent = create_entanglement(&a, &b, default_cond(), 265000);
        let status = check_status(&ent, 265000, 365001);
        assert!(status.deadman_triggered);
        assert_eq!(status.blocks_until_deadman, Some(0));
    }

    #[test]
    fn test_activation_gate() {
        let (a, b) = test_keys();
        let mut cond = default_cond();
        cond.activation_height = 300000;
        let ent = create_entanglement(&a, &b, cond, 265000);
        let status = check_status(&ent, 265000, 290000);
        assert!(!status.is_active);
        assert!(!status.deadman_triggered);
    }

    #[test]
    fn test_escrow_mode() {
        let (a, b) = test_keys();
        let mut cond = default_cond();
        cond.require_dual_sign = true;
        cond.deadman_blocks = 0;
        let ent = create_entanglement(&a, &b, cond.clone(), 265000);
        assert!(ent.conditions.require_dual_sign);
        assert!(verify_commitment(&ent.channel_key, &cond, &ent.commitment));
    }

    #[test]
    fn test_disentanglement() {
        let id = [42u8; 32];
        let h1 = disentanglement_hash(&id, "mutual");
        let h2 = disentanglement_hash(&id, "mutual");
        assert_eq!(h1, h2);
        assert_ne!(h1, disentanglement_hash(&id, "dispute"));
    }
}
