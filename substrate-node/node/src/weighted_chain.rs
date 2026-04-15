//! Weighted fork choice rule for Qubitcoin.
//!
//! Selects the canonical chain by cumulative weight, matching the Python node's
//! fork choice rule exactly:
//!
//!   weight_per_block = 1.0 / difficulty
//!   chain_weight     = sum(1.0 / difficulty_i for each block i)
//!   tiebreak:          lexicographically smaller block hash wins
//!
//! In QBC's PoSA consensus, HIGHER difficulty = EASIER mining (the energy
//! threshold is more generous). So blocks mined at lower difficulty required
//! more work and receive higher weight via the `1/difficulty` formula.
//!
//! ## Cumulative Weight Storage
//!
//! To avoid re-walking the entire chain on every `best_chain()` call, we
//! store cumulative weights in the node's auxiliary (aux) database.  On each
//! block import the cumulative weight is computed as:
//!
//!   cum_weight(block) = cum_weight(parent) + DIFFICULTY_SCALE / difficulty
//!
//! The aux key format is `b"qbc_weight:" ++ block_hash` with a u128 LE value.
//!
//! If a block's cumulative weight is missing (e.g., the node was upgraded from
//! `LongestChain` without migration), the code falls back to computing it
//! on-the-fly by walking back to genesis.

use sc_client_api::{backend, AuxStore, StorageProvider};
use sp_blockchain::{Backend as BlockchainBackend, HeaderBackend};
use sp_consensus::{Error as ConsensusError, SelectChain};
use sp_runtime::traits::{Block as BlockT, Header, NumberFor, Zero};
use std::{marker::PhantomData, sync::Arc};

use qbc_runtime::opaque::Block;

/// Precision scale for integer weight arithmetic.
///
/// `weight_per_block = DIFFICULTY_SCALE / difficulty`
///
/// With difficulty scaled by 10^6 and DIFFICULTY_SCALE at 10^12, a block at
/// difficulty 1.0 (= 1_000_000) contributes weight 1_000_000 — giving us
/// 6 digits of sub-block precision for fractional difficulties.
const DIFFICULTY_SCALE: u128 = 1_000_000_000_000; // 10^12

/// Aux-DB key prefix for cumulative weights.
const AUX_KEY_PREFIX: &[u8] = b"qbc_weight:";

/// Weighted chain selection matching the Python node's fork choice rule.
///
/// Implements `SelectChain` by choosing the leaf with the highest cumulative
/// weight.  Tiebreaker: lexicographically smaller block hash.
pub struct WeightedChain<B, C> {
    backend: Arc<B>,
    client: Arc<C>,
    _phantom: PhantomData<Block>,
}

impl<B, C> Clone for WeightedChain<B, C> {
    fn clone(&self) -> Self {
        WeightedChain {
            backend: self.backend.clone(),
            client: self.client.clone(),
            _phantom: PhantomData,
        }
    }
}

impl<B, C> WeightedChain<B, C>
where
    B: backend::Backend<Block>,
    C: HeaderBackend<Block> + AuxStore + StorageProvider<Block, B>,
{
    /// Create a new `WeightedChain`.
    pub fn new(backend: Arc<B>, client: Arc<C>) -> Self {
        WeightedChain {
            backend,
            client,
            _phantom: PhantomData,
        }
    }

    // ── Aux-DB helpers ──────────────────────────────────────────────

    /// Build the aux-DB key for a given block hash.
    fn aux_key(hash: &<Block as BlockT>::Hash) -> Vec<u8> {
        let mut key = Vec::with_capacity(AUX_KEY_PREFIX.len() + 32);
        key.extend_from_slice(AUX_KEY_PREFIX);
        key.extend_from_slice(hash.as_ref());
        key
    }

    /// Read the cumulative weight for `hash` from aux-DB.
    fn read_weight(&self, hash: &<Block as BlockT>::Hash) -> Option<u128> {
        let key = Self::aux_key(hash);
        self.client
            .get_aux(&key)
            .ok()
            .flatten()
            .and_then(|bytes| {
                if bytes.len() == 16 {
                    Some(u128::from_le_bytes(bytes.try_into().unwrap()))
                } else {
                    None
                }
            })
    }

    /// Write the cumulative weight for `hash` to aux-DB.
    fn write_weight(
        &self,
        hash: &<Block as BlockT>::Hash,
        weight: u128,
    ) -> sp_blockchain::Result<()> {
        let key = Self::aux_key(hash);
        let val = weight.to_le_bytes();
        self.client
            .insert_aux(&[(&key[..], &val[..])], &[])
    }

    // ── Difficulty reading ──────────────────────────────────────────

    /// Read the `CurrentDifficulty` storage value at a given block hash.
    ///
    /// Uses direct storage access (same approach as `SubstrateChainReader`).
    fn difficulty_at(&self, at: &<Block as BlockT>::Hash) -> u64 {
        let key = current_difficulty_storage_key();
        self.client
            .storage(*at, &sc_client_api::StorageKey(key))
            .ok()
            .flatten()
            .and_then(|data| codec::Decode::decode(&mut &data.0[..]).ok())
            .unwrap_or(qbc_primitives::INITIAL_DIFFICULTY)
    }

    // ── Weight computation ──────────────────────────────────────────

    /// Get the cumulative weight for a block, computing and caching it if
    /// it is not already stored.
    fn cumulative_weight(
        &self,
        hash: &<Block as BlockT>::Hash,
    ) -> sp_blockchain::Result<u128> {
        // Fast path: already cached.
        if let Some(w) = self.read_weight(hash) {
            return Ok(w);
        }

        // Slow path: walk back to find a cached ancestor (or genesis),
        // then compute forward.
        let blockchain = self.backend.blockchain();
        let mut chain: Vec<(<Block as BlockT>::Hash, u64)> = Vec::new();

        let mut cur_hash = *hash;
        let base_weight = loop {
            // Genesis block has weight 0 (the coinbase block itself is
            // accounted for by the first element pushed into `chain`).
            let header = blockchain
                .header(cur_hash)?
                .ok_or_else(|| {
                    sp_blockchain::Error::UnknownBlock(format!("{:?}", cur_hash))
                })?;

            let difficulty = self.difficulty_at(&cur_hash);
            chain.push((cur_hash, difficulty));

            if header.number().is_zero() {
                // Genesis — base weight is 0.
                break 0u128;
            }

            let parent = *header.parent_hash();
            if let Some(w) = self.read_weight(&parent) {
                break w;
            }
            cur_hash = parent;
        };

        // `chain` is in reverse order (tip → oldest uncached).
        // Walk forward to compute cumulative weights.
        let mut weight = base_weight;
        for (block_hash, difficulty) in chain.into_iter().rev() {
            let diff = if difficulty == 0 { 1u128 } else { difficulty as u128 };
            weight = weight.saturating_add(DIFFICULTY_SCALE / diff);
            // Cache for future lookups.
            let _ = self.write_weight(&block_hash, weight);
        }

        Ok(weight)
    }

    /// Determine the best chain tip among all leaves.
    fn best_header_weighted(
        &self,
    ) -> sp_blockchain::Result<<Block as BlockT>::Header> {
        let blockchain = self.backend.blockchain();
        let leaves = blockchain.leaves()?;

        if leaves.is_empty() {
            // Fallback: return the info best hash.
            let info = blockchain.info();
            return blockchain
                .header(info.best_hash)?
                .ok_or_else(|| {
                    sp_blockchain::Error::UnknownBlock(format!(
                        "{:?}",
                        info.best_hash
                    ))
                });
        }

        let mut best_hash = leaves[0];
        let mut best_weight = self.cumulative_weight(&best_hash)?;

        for &leaf in &leaves[1..] {
            let w = self.cumulative_weight(&leaf)?;
            if w > best_weight || (w == best_weight && leaf < best_hash) {
                best_weight = w;
                best_hash = leaf;
            }
        }

        blockchain.header(best_hash)?.ok_or_else(|| {
            sp_blockchain::Error::UnknownBlock(format!("{:?}", best_hash))
        })
    }

    /// `finality_target` — mirrors `LongestChain` logic but uses weighted
    /// best chain as the anchor.
    fn finality_target_weighted(
        &self,
        base_hash: <Block as BlockT>::Hash,
        maybe_max_number: Option<NumberFor<Block>>,
    ) -> sp_blockchain::Result<<Block as BlockT>::Hash> {
        use sp_blockchain::Error::{Application, MissingHeader};
        let blockchain = self.backend.blockchain();

        let mut current_head = self.best_header_weighted()?;
        let mut best_hash = current_head.hash();

        let base_header = blockchain
            .header(base_hash)?
            .ok_or_else(|| MissingHeader(base_hash.to_string()))?;
        let base_number = *base_header.number();

        if let Some(max_number) = maybe_max_number {
            if max_number < base_number {
                let msg = format!(
                    "Requested finality target with max {} below base {}",
                    max_number, base_number
                );
                return Err(Application(msg.into()));
            }
            while current_head.number() > &max_number {
                best_hash = *current_head.parent_hash();
                current_head = blockchain
                    .header(best_hash)?
                    .ok_or_else(|| MissingHeader(format!("{best_hash:?}")))?;
            }
        }

        while current_head.hash() != base_hash {
            if *current_head.number() < base_number {
                let msg = format!(
                    "Finality target base {:?} not in best chain {:?}",
                    base_hash, best_hash,
                );
                return Err(Application(msg.into()));
            }
            let current_hash = *current_head.parent_hash();
            current_head = blockchain
                .header(current_hash)?
                .ok_or_else(|| MissingHeader(format!("{best_hash:?}")))?;
        }

        Ok(best_hash)
    }
}

// ═══════════════════════════════════════════════════════════════════════
// SelectChain implementation
// ═══════════════════════════════════════════════════════════════════════

#[async_trait::async_trait]
impl<B, C> SelectChain<Block> for WeightedChain<B, C>
where
    B: backend::Backend<Block>,
    C: HeaderBackend<Block> + AuxStore + StorageProvider<Block, B> + Send + Sync,
{
    async fn leaves(
        &self,
    ) -> Result<Vec<<Block as BlockT>::Hash>, ConsensusError> {
        self.backend
            .blockchain()
            .leaves()
            .map_err(|e| ConsensusError::ChainLookup(e.to_string()))
    }

    async fn best_chain(
        &self,
    ) -> Result<<Block as BlockT>::Header, ConsensusError> {
        self.best_header_weighted()
            .map_err(|e| ConsensusError::ChainLookup(e.to_string()))
    }

    async fn finality_target(
        &self,
        base_hash: <Block as BlockT>::Hash,
        maybe_max_number: Option<NumberFor<Block>>,
    ) -> Result<<Block as BlockT>::Hash, ConsensusError> {
        self.finality_target_weighted(base_hash, maybe_max_number)
            .map_err(|e| ConsensusError::ChainLookup(e.to_string()))
    }
}

/// Notify the weighted chain selector about a newly imported block so its
/// cumulative weight is eagerly cached.
#[allow(dead_code)]
///
/// Call this from the block import pipeline (e.g., after each block import
/// in `service.rs`).  If the weight is already cached this is a no-op.
pub fn on_block_imported<B, C>(
    chain: &WeightedChain<B, C>,
    hash: &<Block as BlockT>::Hash,
) where
    B: backend::Backend<Block>,
    C: HeaderBackend<Block> + AuxStore + StorageProvider<Block, B>,
{
    if let Err(e) = chain.cumulative_weight(hash) {
        log::warn!(
            target: "weighted-chain",
            "Failed to cache cumulative weight for {:?}: {:?}",
            hash, e
        );
    }
}

// ═══════════════════════════════════════════════════════════════════════
// Storage key helper (duplicated from service.rs for encapsulation)
// ═══════════════════════════════════════════════════════════════════════

/// Compute the storage key for `QbcConsensus::CurrentDifficulty`.
fn current_difficulty_storage_key() -> Vec<u8> {
    let mut key = Vec::new();
    key.extend_from_slice(&sp_core::twox_128(b"QbcConsensus"));
    key.extend_from_slice(&sp_core::twox_128(b"CurrentDifficulty"));
    key
}
