//! Core indexing logic — processes finalized blocks and writes to CockroachDB.
//!
//! Flow:
//! 1. Subscribe to finalized block headers (or backfill from a start height)
//! 2. For each finalized block:
//!    a. Fetch full block (header + extrinsics)
//!    b. Fetch events for that block
//!    c. Decode QbcConsensus events: BlockMined, DifficultyAdjusted, SusySolutionStored
//!    d. Decode QbcUtxo events: UtxoCreated, UtxoSpent (if present)
//!    e. Write block, transactions, UTXOs, addresses to CockroachDB
//!    f. Update chain_state singleton
//! 3. Repeat

use anyhow::{Context, Result};
use bigdecimal::BigDecimal;
use chrono::{DateTime, Utc};
use std::str::FromStr;
use subxt::events::EventDetails;
use subxt::{OnlineClient, SubstrateConfig};
use tracing::{debug, error, info, warn};

use crate::config::Config;
use crate::db::Database;
use crate::substrate::SubstrateClient;
use crate::types::*;

/// The block indexer — orchestrates the subscription → decode → persist pipeline.
pub struct Indexer {
    substrate: SubstrateClient,
    db: Database,
    config: Config,
    blocks_indexed: u64,
}

/// Constants matching the on-chain scaling factors.
const ENERGY_SCALE: i128 = 1_000_000_000_000; // 10^12
const DIFFICULTY_SCALE: u64 = 1_000_000;      // 10^6
const QBC_UNIT: u128 = 100_000_000;           // 10^8

impl Indexer {
    /// Create a new indexer from config.
    pub async fn new(config: Config) -> Result<Self> {
        let substrate = SubstrateClient::connect(&config).await?;
        let db = Database::connect(&config).await?;

        Ok(Self {
            substrate,
            db,
            config,
            blocks_indexed: 0,
        })
    }

    /// Run the indexer: backfill if needed, then subscribe to new finalized blocks.
    pub async fn run(&mut self) -> Result<()> {
        // Determine start height
        let db_height = self.db.get_last_indexed_height().await?;
        let start = match db_height {
            Some(h) if h > 0 => {
                info!("Resuming from last indexed height: {}", h);
                h + 1
            }
            _ => {
                info!("Starting from height: {}", self.config.start_height);
                self.config.start_height
            }
        };

        // Backfill historical blocks if requested or if behind
        let finalized = self.substrate.get_finalized_height().await?;
        if start < finalized {
            info!(
                "Backfilling blocks {} to {} ({} blocks)",
                start,
                finalized,
                finalized - start
            );
            self.backfill(start, finalized).await?;
        }

        // Subscribe to new finalized blocks
        info!("Subscribing to new finalized blocks...");
        self.subscribe_loop().await
    }

    /// Backfill historical blocks from `start` to `end` (inclusive).
    async fn backfill(&mut self, start: u64, end: u64) -> Result<()> {
        for height in start..=end {
            if let Err(e) = self.index_block_at_height(height).await {
                error!("Failed to index block {}: {:?}", height, e);
                // Continue to next block — don't halt on individual failures
                // (the block may have no mining events, which is fine)
            }

            if height % 100 == 0 {
                info!(
                    "Backfill progress: {}/{} ({:.1}%)",
                    height - start,
                    end - start,
                    (height - start) as f64 / (end - start) as f64 * 100.0
                );
            }
        }

        info!("Backfill complete: {} blocks indexed", end - start + 1);
        Ok(())
    }

    /// Subscribe to finalized block headers and index each one.
    async fn subscribe_loop(&mut self) -> Result<()> {
        let mut block_sub = self
            .substrate
            .api
            .blocks()
            .subscribe_finalized()
            .await
            .context("Failed to subscribe to finalized blocks")?;

        while let Some(block_result) = block_sub.next().await {
            match block_result {
                Ok(block) => {
                    let height = block.number() as u64;
                    let hash = block.hash();

                    debug!("Finalized block {}: 0x{}", height, hex::encode(hash.0));

                    if let Err(e) = self.process_finalized_block(block).await {
                        error!("Error processing block {}: {:?}", height, e);
                    }
                }
                Err(e) => {
                    error!("Block subscription error: {:?}", e);
                    // subxt will auto-reconnect on transient errors
                }
            }
        }

        warn!("Block subscription ended unexpectedly");
        Ok(())
    }

    /// Index a single block by height (used in backfill mode).
    async fn index_block_at_height(&mut self, height: u64) -> Result<()> {
        let hash = self
            .substrate
            .get_block_hash(height)
            .await?
            .context(format!("Block hash not found for height {}", height))?;

        let block = self
            .substrate
            .api
            .blocks()
            .at(hash)
            .await
            .context(format!("Failed to fetch block at height {}", height))?;

        self.process_finalized_block(block).await
    }

    /// Process a single finalized block: decode events, write to DB.
    async fn process_finalized_block(
        &mut self,
        block: subxt::blocks::Block<SubstrateConfig, OnlineClient<SubstrateConfig>>,
    ) -> Result<()> {
        let height = block.number() as u64;
        let hash = block.hash();
        let header = block.header();

        // Decode events for this block
        let events = block.events().await?;

        // Look for mining events from QbcConsensus pallet
        let mut mining_event: Option<MiningEvent> = None;
        let mut difficulty_event: Option<DifficultyEvent> = None;
        let mut susy_event: Option<SusySolutionEvent> = None;
        let mut phi_event: Option<PhiEvent> = None;

        for event in events.iter() {
            let event = match event {
                Ok(e) => e,
                Err(e) => {
                    debug!("Could not decode event: {:?}", e);
                    continue;
                }
            };

            let pallet = event.pallet_name();
            let variant = event.variant_name();

            match (pallet, variant) {
                ("QbcConsensus", "BlockMined") => {
                    mining_event = decode_mining_event(&event);
                }
                ("QbcConsensus", "DifficultyAdjusted") => {
                    difficulty_event = decode_difficulty_event(&event);
                }
                ("QbcConsensus", "SusySolutionStored") => {
                    susy_event = decode_susy_event(&event);
                }
                ("QbcAetherAnchor", "PhiMeasured") => {
                    phi_event = decode_phi_event(&event);
                }
                _ => {
                    debug!("Event: {}::{}", pallet, variant);
                }
            }
        }

        // Build the indexed block
        let timestamp = Utc::now(); // Use current time; real timestamp from pallet_timestamp
        let difficulty = mining_event
            .as_ref()
            .map(|m| BigDecimal::from(m.difficulty))
            .unwrap_or_else(|| BigDecimal::from(DIFFICULTY_SCALE));

        let energy = mining_event
            .as_ref()
            .map(|m| {
                // Convert from scaled i128 to decimal
                let e = m.energy as f64 / ENERGY_SCALE as f64;
                BigDecimal::from_str(&format!("{:.10}", e)).unwrap_or_default()
            });

        let reward = mining_event
            .as_ref()
            .map(|m| {
                // Convert from smallest units to QBC
                let r = m.reward as f64 / QBC_UNIT as f64;
                BigDecimal::from_str(&format!("{:.8}", r)).unwrap_or_default()
            });

        let miner_address = mining_event.as_ref().map(|m| m.miner.clone());

        // Calculate era from height
        let era = (height / 15_474_020) as u32;

        let indexed_block = IndexedBlock {
            block_hash: hash.0.to_vec(),
            block_height: height,
            parent_hash: header.parent_hash.0.to_vec(),
            state_root: header.state_root.0.to_vec(),
            extrinsics_root: header.extrinsics_root.0.to_vec(),
            timestamp,
            miner_address: miner_address.clone(),
            difficulty: difficulty.clone(),
            energy,
            reward: reward.clone(),
            era,
            transaction_count: 0, // Updated below
            total_fees: BigDecimal::from(0),
            extrinsic_count: 0,
        };

        // Write block to DB
        self.db.insert_block(&indexed_block).await?;

        // If a block was mined, create the coinbase UTXO
        if let Some(ref me) = mining_event {
            let reward_decimal = BigDecimal::from_str(&format!(
                "{:.8}",
                me.reward as f64 / QBC_UNIT as f64
            ))
            .unwrap_or_default();

            // Coinbase txid: SHA2-256("coinbase:" + height_le_bytes)
            let coinbase_txid = compute_coinbase_txid(height);

            let utxo = IndexedUtxo {
                txid: coinbase_txid.clone(),
                vout: 0,
                address: me.miner.clone(),
                amount: reward_decimal.clone(),
                block_height: height,
                is_coinbase: true,
            };

            self.db.insert_utxo(&utxo, &hash.0).await?;

            // Update miner's address balance
            self.db
                .upsert_address(&me.miner, &reward_decimal, true, height)
                .await?;
        }

        // Store SUSY solution if present
        if let Some(ref se) = susy_event {
            if let Some(ref miner) = miner_address {
                let energy_decimal = BigDecimal::from_str(&format!(
                    "{:.10}",
                    se.energy as f64 / ENERGY_SCALE as f64
                ))
                .unwrap_or_default();

                self.db
                    .insert_susy_solution(
                        height,
                        &hash.0,
                        miner,
                        &energy_decimal,
                        se.n_qubits,
                    )
                    .await
                    .ok(); // Non-critical — don't fail block indexing
            }
        }

        // Store Phi measurement if present (from QbcAetherAnchor pallet)
        if let Some(ref pe) = phi_event {
            self.db
                .insert_phi_measurement(
                    pe.block_height,
                    pe.phi_scaled as f64 / 1000.0,
                    pe.knowledge_nodes,
                    pe.knowledge_edges,
                )
                .await
                .ok(); // Non-critical
        }

        // Update chain state
        let total_tx = self.db.count_transactions().await.unwrap_or(0);
        let total_addrs = self.db.count_addresses().await.unwrap_or(0);

        let new_difficulty = difficulty_event
            .as_ref()
            .map(|d| BigDecimal::from(d.new_difficulty))
            .unwrap_or(difficulty);

        // Approximate total supply from era + height
        let total_supply = approximate_total_supply(height);

        let chain_state = ChainState {
            best_block_hash: hash.0.to_vec(),
            best_block_height: height,
            total_blocks: height + 1,
            total_transactions: total_tx,
            total_addresses: total_addrs,
            total_supply,
            current_era: era,
            current_difficulty: new_difficulty,
            average_block_time: BigDecimal::from_str("3.3").unwrap(),
        };

        self.db.update_chain_state(&chain_state).await?;

        self.blocks_indexed += 1;

        if self.blocks_indexed % 10 == 0 || mining_event.is_some() {
            info!(
                "Indexed block {} | mined={} | total_indexed={}",
                height,
                mining_event.is_some(),
                self.blocks_indexed
            );
        }

        Ok(())
    }

    /// Graceful shutdown.
    pub async fn shutdown(&self) {
        info!("Shutting down indexer...");
        self.db.close().await;
        info!(
            "Indexer stopped. Total blocks indexed: {}",
            self.blocks_indexed
        );
    }
}

// ═══════════════════════════════════════════════════════════════════════
// Event Decoders
// ═══════════════════════════════════════════════════════════════════════

// In subxt 0.38 dynamic mode, `event.field_values()` returns
// `scale_value::Composite<u32>`.  The inner field values are
// `scale_value::Value<u32>` structs whose `.value` is a `ValueDef`.
// Use the convenience accessors (`.as_u128()`, `.as_i128()`) on Value.

use scale_value::{Composite, Value, ValueDef, Primitive};

/// Decode a BlockMined event from dynamic event data.
fn decode_mining_event(
    event: &EventDetails<SubstrateConfig>,
) -> Option<MiningEvent> {
    let fields = event.field_values().ok()?;

    let block_height = extract_u64_field(&fields, "block_height")?;
    let miner = extract_bytes_field(&fields, "miner")?;
    let energy = extract_i128_field(&fields, "energy")?;
    let difficulty = extract_u64_field(&fields, "difficulty")?;
    let reward = extract_u128_field(&fields, "reward")?;

    Some(MiningEvent {
        block_height,
        miner,
        energy,
        difficulty,
        reward,
    })
}

/// Decode a DifficultyAdjusted event.
fn decode_difficulty_event(
    event: &EventDetails<SubstrateConfig>,
) -> Option<DifficultyEvent> {
    let fields = event.field_values().ok()?;

    let old_difficulty = extract_u64_field(&fields, "old_difficulty")?;
    let new_difficulty = extract_u64_field(&fields, "new_difficulty")?;
    let block_height = extract_u64_field(&fields, "block_height")?;

    Some(DifficultyEvent {
        old_difficulty,
        new_difficulty,
        block_height,
    })
}

/// Decode a PhiMeasured event from the Aether anchor pallet.
fn decode_phi_event(
    event: &EventDetails<SubstrateConfig>,
) -> Option<PhiEvent> {
    let fields = event.field_values().ok()?;

    let block_height = extract_u64_field(&fields, "block_height")?;
    let phi_scaled = extract_u64_field(&fields, "phi_scaled")?;

    Some(PhiEvent {
        block_height,
        phi_scaled,
        knowledge_nodes: 0, // Not in the event — populated from storage queries
        knowledge_edges: 0,
    })
}

/// Decode a SusySolutionStored event.
fn decode_susy_event(
    event: &EventDetails<SubstrateConfig>,
) -> Option<SusySolutionEvent> {
    let fields = event.field_values().ok()?;

    let block_height = extract_u64_field(&fields, "block_height")?;
    let energy = extract_i128_field(&fields, "energy")?;
    let n_qubits = extract_u64_field(&fields, "n_qubits")? as u8;

    Some(SusySolutionEvent {
        block_height,
        energy,
        n_qubits,
    })
}

// ═══════════════════════════════════════════════════════════════════════
// Field Extraction Helpers (scale-value 0.17 API)
// ═══════════════════════════════════════════════════════════════════════
//
// `Composite<T>` is an enum: `Named(Vec<(String, Value<T>)>)` | `Unnamed(Vec<Value<T>>)`
// `Value<T>` is a struct with `.value: ValueDef<T>` and `.context: T`
// `ValueDef<T>` is an enum: `Composite(...)` | `Variant(...)` | `Primitive(...)` | `BitSequence(...)`
// `Primitive` is an enum: `U128(u128)` | `I128(i128)` | `U256([u8;32])` | ...
// `Value<T>` has accessors: `.as_u128()`, `.as_i128()`, `.as_bool()`, `.as_str()`

/// Find a named field in a Composite and return its Value.
fn find_named_field<'a, T>(
    composite: &'a Composite<T>,
    name: &str,
) -> Option<&'a Value<T>> {
    if let Composite::Named(fields) = composite {
        for (field_name, field_value) in fields {
            if field_name == name {
                return Some(field_value);
            }
        }
    }
    None
}

/// Extract a u64 field from a Composite.
fn extract_u64_field<T>(composite: &Composite<T>, name: &str) -> Option<u64> {
    let val = find_named_field(composite, name)?;
    // as_u128() handles Primitive::U128; also try U256 as fallback
    if let Some(n) = val.as_u128() {
        return Some(n as u64);
    }
    // U256 fallback: read as little-endian bytes
    if let ValueDef::Primitive(Primitive::U256(bytes)) = &val.value {
        // Read first 8 bytes as little-endian u64
        let mut buf = [0u8; 8];
        buf.copy_from_slice(&bytes[..8]);
        return Some(u64::from_le_bytes(buf));
    }
    None
}

/// Extract an i128 field from a Composite.
fn extract_i128_field<T>(composite: &Composite<T>, name: &str) -> Option<i128> {
    let val = find_named_field(composite, name)?;
    if let Some(n) = val.as_i128() {
        return Some(n);
    }
    // U128 → i128 cast as fallback
    if let Some(n) = val.as_u128() {
        return Some(n as i128);
    }
    None
}

/// Extract a u128 field from a Composite.
fn extract_u128_field<T>(composite: &Composite<T>, name: &str) -> Option<u128> {
    let val = find_named_field(composite, name)?;
    val.as_u128()
}

/// Extract a bytes (Address) field from a Composite.
/// Address is a newtype wrapper: Address([u8; 32])
/// In SCALE value it appears as a Composite with unnamed u8 fields.
fn extract_bytes_field<T>(composite: &Composite<T>, name: &str) -> Option<Vec<u8>> {
    let val = find_named_field(composite, name)?;
    value_to_bytes(val)
}

fn value_to_bytes<T>(v: &Value<T>) -> Option<Vec<u8>> {
    match &v.value {
        ValueDef::Composite(Composite::Unnamed(fields)) => {
            // Try: each element is a u8 value
            let bytes: Option<Vec<u8>> = fields
                .iter()
                .map(|f| f.as_u128().map(|n| n as u8))
                .collect();
            if bytes.is_some() {
                return bytes;
            }
            // Try: first element is itself a byte array
            if let Some(first) = fields.first() {
                return value_to_bytes(first);
            }
            None
        }
        ValueDef::Composite(Composite::Named(fields)) => {
            // Named struct with a "0" or "value" field
            for (name, val) in fields {
                if name == "0" || name == "value" {
                    return value_to_bytes(val);
                }
            }
            None
        }
        _ => None,
    }
}

// ═══════════════════════════════════════════════════════════════════════
// Utility Functions
// ═══════════════════════════════════════════════════════════════════════

/// Compute the deterministic coinbase transaction ID.
/// Must match: SHA2-256("coinbase:" + height.to_le_bytes())
fn compute_coinbase_txid(block_height: u64) -> Vec<u8> {
    use sha2::{Digest, Sha256};
    let mut data = b"coinbase:".to_vec();
    data.extend_from_slice(&block_height.to_le_bytes());
    Sha256::digest(&data).to_vec()
}

/// Approximate total supply at a given block height.
/// Uses the phi-halving emission schedule.
fn approximate_total_supply(block_height: u64) -> BigDecimal {
    const PHI: f64 = 1.618033988749895;
    const INITIAL_REWARD: f64 = 15.27;
    const HALVING_INTERVAL: u64 = 15_474_020;
    const GENESIS_PREMINE: f64 = 33_000_000.0;

    let mut total = GENESIS_PREMINE;
    let mut remaining = block_height;
    let mut era = 0u32;

    while remaining > 0 {
        let blocks_in_era = remaining.min(HALVING_INTERVAL);
        let reward = INITIAL_REWARD / PHI.powi(era as i32);
        total += blocks_in_era as f64 * reward;
        remaining -= blocks_in_era;
        era += 1;
    }

    BigDecimal::from_str(&format!("{:.8}", total)).unwrap_or_default()
}
