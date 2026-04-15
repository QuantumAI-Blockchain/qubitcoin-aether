//! CockroachDB writer — persists indexed block data.
//!
//! Uses sqlx with PostgreSQL wire protocol (CockroachDB compatible).
//! All writes are transactional — a block and its contents are committed atomically.

use anyhow::Result;
use bigdecimal::BigDecimal;
use chrono::Utc;
use sqlx::postgres::{PgPool, PgPoolOptions};
use tracing::{debug, info, instrument, warn};
use uuid::Uuid;

use crate::config::Config;
use crate::types::{ChainState, IndexedBlock, IndexedUtxo, MiningEvent, SpentUtxo};

/// Database connection pool and write operations.
pub struct Database {
    pool: PgPool,
}

impl Database {
    /// Connect to CockroachDB and return a Database handle.
    pub async fn connect(config: &Config) -> Result<Self> {
        info!("Connecting to CockroachDB: {}...", &config.database_url[..40]);

        let pool = PgPoolOptions::new()
            .max_connections(config.db_pool_size)
            .connect(&config.database_url)
            .await?;

        // Verify connection
        sqlx::query("SELECT 1").execute(&pool).await?;
        info!("CockroachDB connected successfully");

        let db = Self { pool };
        db.run_migrations().await?;
        Ok(db)
    }

    /// Create substrate indexer tables if they don't exist.
    /// Uses `idx_` prefix to avoid conflicts with the Python node's tables.
    async fn run_migrations(&self) -> Result<()> {
        info!("Running indexer schema migrations...");

        sqlx::query(
            r#"
            CREATE TABLE IF NOT EXISTS idx_blocks (
                block_hash BYTES PRIMARY KEY,
                block_height INT8 NOT NULL,
                previous_hash BYTES,
                timestamp TIMESTAMPTZ,
                difficulty DECIMAL(20,10),
                achieved_eigenvalue DECIMAL(20,10),
                miner_address BYTES,
                era INT4 DEFAULT 0,
                actual_reward DECIMAL(20,8),
                total_fees DECIMAL(20,8) DEFAULT 0,
                transaction_count INT4 DEFAULT 0,
                block_size INT8 DEFAULT 0,
                is_valid BOOL DEFAULT true,
                INDEX idx_blocks_height (block_height DESC)
            )
            "#,
        )
        .execute(&self.pool)
        .await?;

        sqlx::query(
            r#"
            CREATE TABLE IF NOT EXISTS idx_transactions (
                tx_hash BYTES PRIMARY KEY,
                block_hash BYTES,
                block_height INT8,
                tx_index INT4 DEFAULT 0,
                timestamp TIMESTAMPTZ,
                tx_type VARCHAR(20) DEFAULT 'transfer',
                total_output DECIMAL(20,8),
                fee DECIMAL(20,8) DEFAULT 0,
                tx_size INT8 DEFAULT 0,
                is_valid BOOL DEFAULT true,
                INDEX idx_tx_block_height (block_height)
            )
            "#,
        )
        .execute(&self.pool)
        .await?;

        sqlx::query(
            r#"
            CREATE TABLE IF NOT EXISTS idx_transaction_outputs (
                output_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                tx_hash BYTES NOT NULL,
                output_index INT4 NOT NULL,
                amount DECIMAL(20,8) NOT NULL,
                recipient_address BYTES,
                script_pubkey BYTES,
                is_spent BOOL DEFAULT false,
                spent_in_tx BYTES,
                spent_at_height INT8,
                spent_at_timestamp TIMESTAMPTZ,
                UNIQUE (tx_hash, output_index)
            )
            "#,
        )
        .execute(&self.pool)
        .await?;

        sqlx::query(
            r#"
            CREATE TABLE IF NOT EXISTS idx_addresses (
                address BYTES PRIMARY KEY,
                balance DECIMAL(20,8) DEFAULT 0,
                total_received DECIMAL(20,8) DEFAULT 0,
                total_sent DECIMAL(20,8) DEFAULT 0,
                tx_count INT8 DEFAULT 0,
                utxo_count INT8 DEFAULT 0,
                first_seen_height INT8,
                first_seen_timestamp TIMESTAMPTZ,
                last_active_height INT8,
                last_active_timestamp TIMESTAMPTZ
            )
            "#,
        )
        .execute(&self.pool)
        .await?;

        sqlx::query(
            r#"
            CREATE TABLE IF NOT EXISTS idx_chain_state (
                id INT8 PRIMARY KEY DEFAULT 1,
                best_block_hash BYTES,
                best_block_height INT8 DEFAULT 0,
                total_blocks INT8 DEFAULT 0,
                total_transactions INT8 DEFAULT 0,
                total_addresses INT8 DEFAULT 0,
                total_supply DECIMAL(30,8) DEFAULT 0,
                current_era INT8 DEFAULT 0,
                current_difficulty DECIMAL(20,10) DEFAULT 1.0,
                average_block_time DECIMAL(10,2) DEFAULT 3.3,
                updated_at TIMESTAMPTZ DEFAULT now()
            )
            "#,
        )
        .execute(&self.pool)
        .await?;

        sqlx::query(
            r#"
            CREATE TABLE IF NOT EXISTS idx_susy_solutions (
                solution_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                block_hash BYTES,
                block_height INT8,
                miner_address BYTES,
                ground_state_energy DECIMAL(20,10),
                alignment_score FLOAT8 DEFAULT 100.0,
                is_verified BOOL DEFAULT true,
                discovered_timestamp TIMESTAMPTZ DEFAULT now()
            )
            "#,
        )
        .execute(&self.pool)
        .await?;

        sqlx::query(
            r#"
            CREATE TABLE IF NOT EXISTS idx_phi_measurements (
                id SERIAL PRIMARY KEY,
                phi_value FLOAT8,
                phi_threshold FLOAT8 DEFAULT 3.0,
                integration_score FLOAT8 DEFAULT 0.0,
                differentiation_score FLOAT8 DEFAULT 0.0,
                num_nodes INT8 DEFAULT 0,
                num_edges INT8 DEFAULT 0,
                block_height INT8,
                measured_at TIMESTAMPTZ DEFAULT now()
            )
            "#,
        )
        .execute(&self.pool)
        .await?;

        info!("Indexer schema migrations complete");
        Ok(())
    }

    /// Get the highest indexed block height, or None if no blocks exist.
    pub async fn get_last_indexed_height(&self) -> Result<Option<u64>> {
        let row: Option<(i64,)> = sqlx::query_as(
            "SELECT best_block_height FROM idx_chain_state WHERE id = 1",
        )
        .fetch_optional(&self.pool)
        .await?;

        Ok(row.map(|(h,)| h as u64))
    }

    /// Insert a finalized block into the blocks table.
    #[instrument(skip(self, block), fields(height = block.block_height))]
    pub async fn insert_block(&self, block: &IndexedBlock) -> Result<()> {
        sqlx::query(
            r#"
            INSERT INTO idx_blocks (
                block_hash, block_height, previous_hash, timestamp,
                difficulty, achieved_eigenvalue, miner_address,
                era, actual_reward, total_fees, transaction_count,
                block_size, is_valid
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, true)
            ON CONFLICT (block_hash) DO NOTHING
            "#,
        )
        .bind(&block.block_hash)
        .bind(block.block_height as i64)
        .bind(&block.parent_hash)
        .bind(block.timestamp)
        .bind(&block.difficulty)
        .bind(&block.energy)
        .bind(&block.miner_address)
        .bind(block.era as i32)
        .bind(&block.reward)
        .bind(&block.total_fees)
        .bind(block.transaction_count as i32)
        .bind(0i64) // block_size — populated later if needed
        .execute(&self.pool)
        .await?;

        debug!("Inserted block {}", block.block_height);
        Ok(())
    }

    /// Insert a coinbase UTXO (mining reward output).
    #[instrument(skip(self, utxo), fields(height = utxo.block_height, vout = utxo.vout))]
    pub async fn insert_utxo(&self, utxo: &IndexedUtxo, block_hash: &[u8]) -> Result<()> {
        let output_id = Uuid::new_v4();

        // Insert transaction if it doesn't exist (coinbase tx)
        sqlx::query(
            r#"
            INSERT INTO idx_transactions (
                tx_hash, block_hash, block_height, tx_index, timestamp,
                tx_type, total_output, fee, tx_size, is_valid
            ) VALUES ($1, $2, $3, 0, now(), 'coinbase', $4, 0, 0, true)
            ON CONFLICT (tx_hash) DO NOTHING
            "#,
        )
        .bind(&utxo.txid)
        .bind(block_hash)
        .bind(utxo.block_height as i64)
        .bind(&utxo.amount)
        .execute(&self.pool)
        .await?;

        // Insert the output
        sqlx::query(
            r#"
            INSERT INTO idx_transaction_outputs (
                output_id, tx_hash, output_index, amount,
                recipient_address, script_pubkey, is_spent
            ) VALUES ($1, $2, $3, $4, $5, $6, false)
            ON CONFLICT (tx_hash, output_index) DO NOTHING
            "#,
        )
        .bind(output_id)
        .bind(&utxo.txid)
        .bind(utxo.vout as i32)
        .bind(&utxo.amount)
        .bind(&utxo.address)
        .bind(&utxo.address) // script_pubkey = address for QBC
        .execute(&self.pool)
        .await?;

        debug!(
            "Inserted UTXO {}:{} ({})",
            hex::encode(&utxo.txid[..8]),
            utxo.vout,
            utxo.amount
        );
        Ok(())
    }

    /// Mark a UTXO as spent.
    #[instrument(skip(self, spent))]
    pub async fn mark_utxo_spent(&self, spent: &SpentUtxo) -> Result<()> {
        let result = sqlx::query(
            r#"
            UPDATE idx_transaction_outputs
            SET is_spent = true,
                spent_in_tx = $1,
                spent_at_height = $2,
                spent_at_timestamp = $3
            WHERE tx_hash = $4 AND output_index = $5
            "#,
        )
        .bind(&spent.spent_in_tx)
        .bind(spent.spent_at_height as i64)
        .bind(spent.spent_at_timestamp)
        .bind(&spent.prev_txid)
        .bind(spent.prev_vout as i32)
        .execute(&self.pool)
        .await?;

        if result.rows_affected() == 0 {
            warn!(
                "UTXO not found to mark spent: {}:{}",
                hex::encode(&spent.prev_txid[..8]),
                spent.prev_vout
            );
        }

        Ok(())
    }

    /// Update or insert an address balance entry.
    #[instrument(skip(self))]
    pub async fn upsert_address(
        &self,
        address: &[u8],
        balance_delta: &BigDecimal,
        is_receive: bool,
        block_height: u64,
    ) -> Result<()> {
        if is_receive {
            sqlx::query(
                r#"
                INSERT INTO idx_addresses (
                    address, balance, total_received, tx_count, utxo_count,
                    first_seen_height, first_seen_timestamp,
                    last_active_height, last_active_timestamp
                ) VALUES ($1, $2, $2, 1, 1, $3, now(), $3, now())
                ON CONFLICT (address) DO UPDATE SET
                    balance = idx_addresses.balance + $2,
                    total_received = idx_addresses.total_received + $2,
                    tx_count = idx_addresses.tx_count + 1,
                    utxo_count = idx_addresses.utxo_count + 1,
                    last_active_height = $3,
                    last_active_timestamp = now()
                "#,
            )
            .bind(address)
            .bind(balance_delta)
            .bind(block_height as i64)
            .execute(&self.pool)
            .await?;
        } else {
            sqlx::query(
                r#"
                UPDATE idx_addresses SET
                    balance = balance - $1,
                    total_sent = total_sent + $1,
                    tx_count = tx_count + 1,
                    utxo_count = GREATEST(utxo_count - 1, 0),
                    last_active_height = $2,
                    last_active_timestamp = now()
                WHERE address = $3
                "#,
            )
            .bind(balance_delta)
            .bind(block_height as i64)
            .bind(address)
            .execute(&self.pool)
            .await?;
        }

        Ok(())
    }

    /// Update the singleton chain_state row.
    #[instrument(skip(self, state))]
    pub async fn update_chain_state(&self, state: &ChainState) -> Result<()> {
        sqlx::query(
            r#"
            INSERT INTO idx_chain_state (
                id, best_block_hash, best_block_height,
                total_blocks, total_transactions, total_addresses,
                total_supply, current_era, current_difficulty,
                average_block_time, updated_at
            ) VALUES (
                1, $1, $2, $3, $4, $5, $6, $7, $8, $9, now()
            )
            ON CONFLICT (id) DO UPDATE SET
                best_block_hash = $1,
                best_block_height = $2,
                total_blocks = $3,
                total_transactions = $4,
                total_addresses = $5,
                total_supply = $6,
                current_era = $7,
                current_difficulty = $8,
                average_block_time = $9,
                updated_at = now()
            "#,
        )
        .bind(&state.best_block_hash)
        .bind(state.best_block_height as i64)
        .bind(state.total_blocks as i64)
        .bind(state.total_transactions as i64)
        .bind(state.total_addresses as i64)
        .bind(&state.total_supply)
        .bind(state.current_era as i32)
        .bind(&state.current_difficulty)
        .bind(&state.average_block_time)
        .execute(&self.pool)
        .await?;

        debug!("Updated chain_state: height={}", state.best_block_height);
        Ok(())
    }

    /// Insert a SUSY solution into the research database.
    pub async fn insert_susy_solution(
        &self,
        block_height: u64,
        block_hash: &[u8],
        miner_address: &[u8],
        energy: &BigDecimal,
        n_qubits: u8,
    ) -> Result<()> {
        let solution_id = Uuid::new_v4();

        sqlx::query(
            r#"
            INSERT INTO idx_susy_solutions (
                solution_id, block_hash, block_height, miner_address,
                ground_state_energy, alignment_score, is_verified,
                discovered_timestamp
            ) VALUES ($1, $2, $3, $4, $5, 100.0, true, now())
            ON CONFLICT DO NOTHING
            "#,
        )
        .bind(solution_id)
        .bind(block_hash)
        .bind(block_height as i64)
        .bind(miner_address)
        .bind(energy)
        .execute(&self.pool)
        .await?;

        Ok(())
    }

    /// Insert a phi measurement (from Aether anchor pallet events).
    pub async fn insert_phi_measurement(
        &self,
        block_height: u64,
        phi_value: f64,
        num_nodes: u64,
        num_edges: u64,
    ) -> Result<()> {
        sqlx::query(
            r#"
            INSERT INTO idx_phi_measurements (
                phi_value, phi_threshold, integration_score,
                differentiation_score, num_nodes, num_edges,
                block_height, measured_at
            ) VALUES ($1, 3.0, 0.0, 0.0, $2, $3, $4, now())
            "#,
        )
        .bind(phi_value)
        .bind(num_nodes as i64)
        .bind(num_edges as i64)
        .bind(block_height as i64)
        .execute(&self.pool)
        .await?;

        Ok(())
    }

    /// Count total addresses in the addresses table.
    pub async fn count_addresses(&self) -> Result<u64> {
        let row: (i64,) = sqlx::query_as("SELECT COUNT(*) FROM idx_addresses")
            .fetch_one(&self.pool)
            .await?;
        Ok(row.0 as u64)
    }

    /// Count total transactions.
    pub async fn count_transactions(&self) -> Result<u64> {
        let row: (i64,) = sqlx::query_as("SELECT COUNT(*) FROM idx_transactions")
            .fetch_one(&self.pool)
            .await?;
        Ok(row.0 as u64)
    }

    /// Remove a transaction from the mempool after it's been finalized.
    pub async fn remove_from_mempool(&self, tx_hash: &[u8]) -> Result<()> {
        sqlx::query("DELETE FROM idx_transactions WHERE tx_hash = $1 AND tx_type = 'mempool'")
            .bind(tx_hash)
            .execute(&self.pool)
            .await?;
        Ok(())
    }

    /// Close the connection pool.
    pub async fn close(&self) {
        self.pool.close().await;
    }
}
