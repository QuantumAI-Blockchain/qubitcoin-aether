package database

import (
	"context"
	"database/sql"
	"fmt"
	"time"

	"go.uber.org/zap"
)

// Repository provides data access methods for all QVM database tables.
type Repository struct {
	db     *sql.DB
	logger *zap.Logger
}

// NewRepository creates a new data access repository.
func NewRepository(db *sql.DB, logger *zap.Logger) *Repository {
	return &Repository{db: db, logger: logger}
}

// DB returns the underlying database connection.
func (r *Repository) DB() *sql.DB {
	return r.db
}

// ─── Block Operations ────────────────────────────────────────────────

// InsertBlock stores a new block.
func (r *Repository) InsertBlock(ctx context.Context, b *Block) error {
	_, err := r.db.ExecContext(ctx, `
		INSERT INTO blocks (block_hash, block_height, version, previous_hash, merkle_root,
			timestamp, difficulty, nonce, miner_address, era, base_reward, actual_reward,
			total_fees, transaction_count, block_size, gas_used, gas_limit, is_valid,
			proof_of_thought_hash)
		VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19)`,
		b.BlockHash, b.BlockHeight, b.Version, b.PreviousHash, b.MerkleRoot,
		b.Timestamp, b.Difficulty, b.Nonce, b.MinerAddress, b.Era, b.BaseReward,
		b.ActualReward, b.TotalFees, b.TransactionCount, b.BlockSize,
		b.GasUsed, b.GasLimit, b.IsValid, b.PoTHash,
	)
	return err
}

// GetBlockByHeight retrieves a block by height.
func (r *Repository) GetBlockByHeight(ctx context.Context, height uint64) (*Block, error) {
	b := &Block{}
	err := r.db.QueryRowContext(ctx, `
		SELECT block_hash, block_height, version, previous_hash, merkle_root, timestamp,
			difficulty, nonce, miner_address, era, base_reward, actual_reward, total_fees,
			transaction_count, block_size, gas_used, gas_limit, is_valid, proof_of_thought_hash
		FROM blocks WHERE block_height = $1`, height,
	).Scan(
		&b.BlockHash, &b.BlockHeight, &b.Version, &b.PreviousHash, &b.MerkleRoot,
		&b.Timestamp, &b.Difficulty, &b.Nonce, &b.MinerAddress, &b.Era, &b.BaseReward,
		&b.ActualReward, &b.TotalFees, &b.TransactionCount, &b.BlockSize,
		&b.GasUsed, &b.GasLimit, &b.IsValid, &b.PoTHash,
	)
	if err == sql.ErrNoRows {
		return nil, nil
	}
	return b, err
}

// GetBlockByHash retrieves a block by hash.
func (r *Repository) GetBlockByHash(ctx context.Context, hash []byte) (*Block, error) {
	b := &Block{}
	err := r.db.QueryRowContext(ctx, `
		SELECT block_hash, block_height, version, previous_hash, merkle_root, timestamp,
			difficulty, nonce, miner_address, era, base_reward, actual_reward, total_fees,
			transaction_count, block_size, gas_used, gas_limit, is_valid
		FROM blocks WHERE block_hash = $1`, hash,
	).Scan(
		&b.BlockHash, &b.BlockHeight, &b.Version, &b.PreviousHash, &b.MerkleRoot,
		&b.Timestamp, &b.Difficulty, &b.Nonce, &b.MinerAddress, &b.Era, &b.BaseReward,
		&b.ActualReward, &b.TotalFees, &b.TransactionCount, &b.BlockSize,
		&b.GasUsed, &b.GasLimit, &b.IsValid,
	)
	if err == sql.ErrNoRows {
		return nil, nil
	}
	return b, err
}

// GetLatestBlockHeight returns the current chain tip height.
func (r *Repository) GetLatestBlockHeight(ctx context.Context) (uint64, error) {
	var height uint64
	err := r.db.QueryRowContext(ctx,
		`SELECT COALESCE(MAX(block_height), 0) FROM blocks`).Scan(&height)
	return height, err
}

// ─── Transaction Operations ──────────────────────────────────────────

// InsertTransaction stores a new transaction.
func (r *Repository) InsertTransaction(ctx context.Context, tx *Transaction) error {
	_, err := r.db.ExecContext(ctx, `
		INSERT INTO transactions (tx_hash, block_hash, block_height, tx_index, version,
			timestamp, tx_type, input_count, output_count, total_input, total_output,
			fee, is_confidential, gas_limit, gas_used, gas_price, tx_size, is_valid)
		VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18)`,
		tx.TxHash, tx.BlockHash, tx.BlockHeight, tx.TxIndex, tx.Version,
		tx.Timestamp, tx.TxType, tx.InputCount, tx.OutputCount, tx.TotalInput,
		tx.TotalOutput, tx.Fee, tx.IsConfidential, tx.GasLimit, tx.GasUsed,
		tx.GasPrice, tx.TxSize, tx.IsValid,
	)
	return err
}

// GetTransactionByHash retrieves a transaction by hash.
func (r *Repository) GetTransactionByHash(ctx context.Context, hash []byte) (*Transaction, error) {
	tx := &Transaction{}
	err := r.db.QueryRowContext(ctx, `
		SELECT tx_hash, block_hash, block_height, tx_index, version, timestamp, tx_type,
			input_count, output_count, total_input, total_output, fee, is_confidential,
			gas_limit, gas_used, gas_price, tx_size, is_valid
		FROM transactions WHERE tx_hash = $1`, hash,
	).Scan(
		&tx.TxHash, &tx.BlockHash, &tx.BlockHeight, &tx.TxIndex, &tx.Version,
		&tx.Timestamp, &tx.TxType, &tx.InputCount, &tx.OutputCount, &tx.TotalInput,
		&tx.TotalOutput, &tx.Fee, &tx.IsConfidential, &tx.GasLimit, &tx.GasUsed,
		&tx.GasPrice, &tx.TxSize, &tx.IsValid,
	)
	if err == sql.ErrNoRows {
		return nil, nil
	}
	return tx, err
}

// ─── UTXO Operations ─────────────────────────────────────────────────

// InsertOutput stores a transaction output (UTXO).
func (r *Repository) InsertOutput(ctx context.Context, out *TxOutput) error {
	_, err := r.db.ExecContext(ctx, `
		INSERT INTO transaction_outputs (tx_hash, output_index, amount, recipient_address,
			script_pubkey, is_spent)
		VALUES ($1,$2,$3,$4,$5,$6)`,
		out.TxHash, out.OutputIndex, out.Amount, out.RecipientAddress,
		out.ScriptPubkey, out.IsSpent,
	)
	return err
}

// GetUnspentOutputs returns all UTXOs for an address.
func (r *Repository) GetUnspentOutputs(ctx context.Context, address []byte) ([]TxOutput, error) {
	rows, err := r.db.QueryContext(ctx, `
		SELECT output_id, tx_hash, output_index, amount, recipient_address, is_spent
		FROM transaction_outputs
		WHERE recipient_address = $1 AND is_spent = false
		ORDER BY amount DESC`, address,
	)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var utxos []TxOutput
	for rows.Next() {
		var u TxOutput
		if err := rows.Scan(&u.OutputID, &u.TxHash, &u.OutputIndex, &u.Amount,
			&u.RecipientAddress, &u.IsSpent); err != nil {
			return nil, err
		}
		utxos = append(utxos, u)
	}
	return utxos, rows.Err()
}

// SpendOutput marks a UTXO as spent.
func (r *Repository) SpendOutput(ctx context.Context, txHash []byte, outputIndex int, spentInTx []byte, height uint64) error {
	res, err := r.db.ExecContext(ctx, `
		UPDATE transaction_outputs
		SET is_spent = true, spent_in_tx = $3, spent_at_height = $4, spent_at_timestamp = NOW()
		WHERE tx_hash = $1 AND output_index = $2 AND is_spent = false`,
		txHash, outputIndex, spentInTx, height,
	)
	if err != nil {
		return err
	}
	n, _ := res.RowsAffected()
	if n == 0 {
		return fmt.Errorf("UTXO %x:%d already spent or not found", txHash, outputIndex)
	}
	return nil
}

// GetBalance computes balance from unspent outputs.
func (r *Repository) GetBalance(ctx context.Context, address []byte) (float64, error) {
	var balance float64
	err := r.db.QueryRowContext(ctx, `
		SELECT COALESCE(SUM(amount), 0)
		FROM transaction_outputs
		WHERE recipient_address = $1 AND is_spent = false`, address,
	).Scan(&balance)
	return balance, err
}

// ─── Contract Operations ─────────────────────────────────────────────

// InsertContract stores a deployed smart contract.
func (r *Repository) InsertContract(ctx context.Context, c *SmartContract) error {
	_, err := r.db.ExecContext(ctx, `
		INSERT INTO smart_contracts (contract_address, creator_address, deployer_tx_hash,
			deployed_at_height, bytecode, bytecode_hash, bytecode_size, contract_name,
			contract_type, is_active)
		VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)`,
		c.ContractAddress, c.CreatorAddress, c.DeployerTxHash,
		c.DeployedAtHeight, c.Bytecode, c.BytecodeHash, c.BytecodeSize,
		c.ContractName, c.ContractType, c.IsActive,
	)
	return err
}

// GetContract retrieves a smart contract by address.
func (r *Repository) GetContract(ctx context.Context, address []byte) (*SmartContract, error) {
	c := &SmartContract{}
	err := r.db.QueryRowContext(ctx, `
		SELECT contract_address, creator_address, deployed_at_height, bytecode,
			bytecode_hash, bytecode_size, contract_name, contract_type,
			balance, total_gas_used, execution_count, is_active, is_paused
		FROM smart_contracts WHERE contract_address = $1`, address,
	).Scan(
		&c.ContractAddress, &c.CreatorAddress, &c.DeployedAtHeight, &c.Bytecode,
		&c.BytecodeHash, &c.BytecodeSize, &c.ContractName, &c.ContractType,
		&c.Balance, &c.TotalGasUsed, &c.ExecutionCount, &c.IsActive, &c.IsPaused,
	)
	if err == sql.ErrNoRows {
		return nil, nil
	}
	return c, err
}

// InsertContractExecution logs a contract execution.
func (r *Repository) InsertContractExecution(ctx context.Context, e *ContractExecution) error {
	_, err := r.db.ExecContext(ctx, `
		INSERT INTO contract_executions (tx_hash, block_height, contract_address,
			caller_address, function_name, gas_limit, gas_used, success,
			return_data, error_message, revert_reason, execution_time_ms,
			opcodes_executed, storage_writes, storage_reads, logs_count)
		VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16)`,
		e.TxHash, e.BlockHeight, e.ContractAddress, e.CallerAddress,
		e.FunctionName, e.GasLimit, e.GasUsed, e.Success,
		e.ReturnData, e.ErrorMessage, e.RevertReason, e.ExecutionTimeMs,
		e.OpcodesExecuted, e.StorageWrites, e.StorageReads, e.LogsCount,
	)
	return err
}

// ─── Storage Operations ──────────────────────────────────────────────

// SetStorage upserts a contract storage slot.
func (r *Repository) SetStorage(ctx context.Context, contractAddr, key, value []byte, height uint64) error {
	_, err := r.db.ExecContext(ctx, `
		UPSERT INTO contract_storage (contract_address, storage_key, storage_value,
			last_modified_height, last_modified_timestamp)
		VALUES ($1,$2,$3,$4,NOW())`,
		contractAddr, key, value, height,
	)
	return err
}

// GetStorage retrieves a contract storage value.
func (r *Repository) GetStorage(ctx context.Context, contractAddr, key []byte) ([]byte, error) {
	var value []byte
	err := r.db.QueryRowContext(ctx, `
		SELECT storage_value FROM contract_storage
		WHERE contract_address = $1 AND storage_key = $2`,
		contractAddr, key,
	).Scan(&value)
	if err == sql.ErrNoRows {
		return nil, nil
	}
	return value, err
}

// ─── Chain State Operations ──────────────────────────────────────────

// GetChainState retrieves the singleton chain state.
func (r *Repository) GetChainState(ctx context.Context) (*ChainState, error) {
	cs := &ChainState{}
	err := r.db.QueryRowContext(ctx, `
		SELECT best_block_hash, best_block_height, total_blocks, total_transactions,
			total_addresses, total_supply, circulating_supply, current_era,
			current_difficulty, average_block_time, total_contracts, current_phi_score
		FROM chain_state WHERE id = 1`,
	).Scan(
		&cs.BestBlockHash, &cs.BestBlockHeight, &cs.TotalBlocks, &cs.TotalTransactions,
		&cs.TotalAddresses, &cs.TotalSupply, &cs.CirculatingSupply, &cs.CurrentEra,
		&cs.CurrentDifficulty, &cs.AverageBlockTime, &cs.TotalContracts, &cs.CurrentPhiScore,
	)
	if err == sql.ErrNoRows {
		return nil, nil
	}
	return cs, err
}

// UpdateChainState updates the singleton chain state row.
func (r *Repository) UpdateChainState(ctx context.Context, cs *ChainState) error {
	_, err := r.db.ExecContext(ctx, `
		UPSERT INTO chain_state (id, best_block_hash, best_block_height, total_blocks,
			total_transactions, total_supply, circulating_supply, current_era,
			current_difficulty, average_block_time, total_contracts, current_phi_score,
			updated_at)
		VALUES (1,$1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,NOW())`,
		cs.BestBlockHash, cs.BestBlockHeight, cs.TotalBlocks, cs.TotalTransactions,
		cs.TotalSupply, cs.CirculatingSupply, cs.CurrentEra, cs.CurrentDifficulty,
		cs.AverageBlockTime, cs.TotalContracts, cs.CurrentPhiScore,
	)
	return err
}

// ─── Mempool Operations ──────────────────────────────────────────────

// InsertMempoolEntry adds a transaction to the mempool.
func (r *Repository) InsertMempoolEntry(ctx context.Context, entry *MempoolEntry) error {
	_, err := r.db.ExecContext(ctx, `
		INSERT INTO mempool (tx_hash, raw_tx, tx_size, fee, fee_per_byte, gas_price,
			priority_score, is_valid)
		VALUES ($1,$2,$3,$4,$5,$6,$7,$8)`,
		entry.TxHash, entry.RawTx, entry.TxSize, entry.Fee, entry.FeePerByte,
		entry.GasPrice, entry.PriorityScore, entry.IsValid,
	)
	return err
}

// GetMempoolByPriority returns top-N mempool entries ordered by priority.
func (r *Repository) GetMempoolByPriority(ctx context.Context, limit int) ([]MempoolEntry, error) {
	rows, err := r.db.QueryContext(ctx, `
		SELECT tx_hash, raw_tx, tx_size, fee, fee_per_byte, gas_price, priority_score,
			received_timestamp, propagation_count, is_valid
		FROM mempool
		WHERE is_valid = true
		ORDER BY priority_score DESC
		LIMIT $1`, limit,
	)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var entries []MempoolEntry
	for rows.Next() {
		var e MempoolEntry
		if err := rows.Scan(&e.TxHash, &e.RawTx, &e.TxSize, &e.Fee, &e.FeePerByte,
			&e.GasPrice, &e.PriorityScore, &e.ReceivedTimestamp,
			&e.PropagationCount, &e.IsValid); err != nil {
			return nil, err
		}
		entries = append(entries, e)
	}
	return entries, rows.Err()
}

// RemoveFromMempool removes a transaction from the mempool (e.g., after inclusion in a block).
func (r *Repository) RemoveFromMempool(ctx context.Context, txHash []byte) error {
	_, err := r.db.ExecContext(ctx, `DELETE FROM mempool WHERE tx_hash = $1`, txHash)
	return err
}

// ─── Knowledge Graph Operations ──────────────────────────────────────

// InsertKnowledgeNode adds a node to the knowledge graph.
func (r *Repository) InsertKnowledgeNode(ctx context.Context, n *KnowledgeNode) error {
	_, err := r.db.ExecContext(ctx, `
		INSERT INTO knowledge_nodes (node_type, node_label, content_text, confidence_score,
			anchored_to_block, is_immutable, source_type, ipfs_hash)
		VALUES ($1,$2,$3,$4,$5,$6,$7,$8)`,
		n.NodeType, n.NodeLabel, n.ContentText, n.ConfidenceScore,
		n.AnchoredToBlock, n.IsImmutable, n.SourceType, n.IPFSHash,
	)
	return err
}

// InsertKnowledgeEdge adds an edge to the knowledge graph.
func (r *Repository) InsertKnowledgeEdge(ctx context.Context, e *KnowledgeEdge) error {
	_, err := r.db.ExecContext(ctx, `
		INSERT INTO knowledge_edges (source_node, target_node, edge_type, edge_weight,
			is_bidirectional, confidence_score, anchored_to_block)
		VALUES ($1,$2,$3,$4,$5,$6,$7)`,
		e.SourceNode, e.TargetNode, e.EdgeType, e.EdgeWeight,
		e.IsBidirectional, e.ConfidenceScore, e.AnchoredToBlock,
	)
	return err
}

// GetKnowledgeNodeCount returns the total number of knowledge nodes.
func (r *Repository) GetKnowledgeNodeCount(ctx context.Context) (uint64, error) {
	var count uint64
	err := r.db.QueryRowContext(ctx, `SELECT COUNT(*) FROM knowledge_nodes`).Scan(&count)
	return count, err
}

// ─── Phi Measurement Operations ──────────────────────────────────────

// InsertPhiMeasurement records a Phi measurement.
func (r *Repository) InsertPhiMeasurement(ctx context.Context, m *PhiMeasurement) error {
	_, err := r.db.ExecContext(ctx, `
		INSERT INTO phi_measurements (phi_value, phi_threshold, exceeds_threshold,
			node_count, edge_count, integration_score, differentiation_score,
			measured_at_height, previous_phi, phi_delta, trend)
		VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)`,
		m.PhiValue, m.PhiThreshold, m.ExceedsThreshold,
		m.NodeCount, m.EdgeCount, m.IntegrationScore, m.DifferentiationScore,
		m.MeasuredAtHeight, m.PreviousPhi, m.PhiDelta, m.Trend,
	)
	return err
}

// GetLatestPhi returns the most recent Phi measurement.
func (r *Repository) GetLatestPhi(ctx context.Context) (*PhiMeasurement, error) {
	m := &PhiMeasurement{}
	err := r.db.QueryRowContext(ctx, `
		SELECT measurement_id, phi_value, phi_threshold, exceeds_threshold,
			node_count, edge_count, integration_score, differentiation_score,
			measured_at_height, previous_phi, phi_delta, trend, measured_at
		FROM phi_measurements
		ORDER BY measured_at DESC
		LIMIT 1`,
	).Scan(
		&m.MeasurementID, &m.PhiValue, &m.PhiThreshold, &m.ExceedsThreshold,
		&m.NodeCount, &m.EdgeCount, &m.IntegrationScore, &m.DifferentiationScore,
		&m.MeasuredAtHeight, &m.PreviousPhi, &m.PhiDelta, &m.Trend, &m.MeasuredAt,
	)
	if err == sql.ErrNoRows {
		return nil, nil
	}
	return m, err
}

// ─── Compliance Operations ───────────────────────────────────────────

// UpsertComplianceRecord creates or updates a compliance registry entry.
func (r *Repository) UpsertComplianceRecord(ctx context.Context, c *ComplianceRecord) error {
	_, err := r.db.ExecContext(ctx, `
		UPSERT INTO compliance_registry (address, kyc_level, aml_status, sanctions_checked,
			last_verified, jurisdiction, daily_limit, is_blocked, updated_at)
		VALUES ($1,$2,$3,$4,$5,$6,$7,$8,NOW())`,
		c.Address, c.KYCLevel, c.AMLStatus, c.SanctionsChecked,
		c.LastVerified, c.Jurisdiction, c.DailyLimit, c.IsBlocked,
	)
	return err
}

// GetComplianceRecord retrieves a compliance entry by address.
func (r *Repository) GetComplianceRecord(ctx context.Context, address string) (*ComplianceRecord, error) {
	c := &ComplianceRecord{}
	err := r.db.QueryRowContext(ctx, `
		SELECT address, kyc_level, aml_status, sanctions_checked, last_verified,
			jurisdiction, daily_limit, is_blocked
		FROM compliance_registry WHERE address = $1`, address,
	).Scan(
		&c.Address, &c.KYCLevel, &c.AMLStatus, &c.SanctionsChecked,
		&c.LastVerified, &c.Jurisdiction, &c.DailyLimit, &c.IsBlocked,
	)
	if err == sql.ErrNoRows {
		return nil, nil
	}
	return c, err
}

// ─── Health & Stats ──────────────────────────────────────────────────

// Ping verifies the database connection.
func (r *Repository) Ping(ctx context.Context) error {
	return r.db.PingContext(ctx)
}

// Stats returns database connection pool statistics.
func (r *Repository) Stats() sql.DBStats {
	return r.db.Stats()
}

// TableStats returns row counts for key tables.
func (r *Repository) TableStats(ctx context.Context) (map[string]int64, error) {
	tables := []string{
		"blocks", "transactions", "transaction_outputs",
		"smart_contracts", "knowledge_nodes", "phi_measurements",
		"compliance_registry", "mempool",
	}

	stats := make(map[string]int64, len(tables))
	for _, t := range tables {
		var count int64
		// Safe: table names are hardcoded above, not user input.
		err := r.db.QueryRowContext(ctx,
			fmt.Sprintf("SELECT COUNT(*) FROM %s", t)).Scan(&count)
		if err != nil {
			stats[t] = -1 // table may not exist yet
			continue
		}
		stats[t] = count
	}
	return stats, nil
}

// ─── Connection Factory ──────────────────────────────────────────────

// ConnectConfig holds database connection parameters.
type ConnectConfig struct {
	Host     string
	Port     int
	Database string
	User     string
	SSLMode  string
	MaxConns int
	MaxIdle  int
	MaxLife  time.Duration
}

// DefaultConnectConfig returns the default CockroachDB connection config.
func DefaultConnectConfig() ConnectConfig {
	return ConnectConfig{
		Host:     "localhost",
		Port:     26257,
		Database: "qbc",
		User:     "root",
		SSLMode:  "disable",
		MaxConns: 25,
		MaxIdle:  5,
		MaxLife:  5 * time.Minute,
	}
}

// Connect opens a connection pool to CockroachDB.
func Connect(cfg ConnectConfig) (*sql.DB, error) {
	dsn := fmt.Sprintf("postgresql://%s@%s:%d/%s?sslmode=%s",
		cfg.User, cfg.Host, cfg.Port, cfg.Database, cfg.SSLMode)

	db, err := sql.Open("postgres", dsn)
	if err != nil {
		return nil, fmt.Errorf("open database: %w", err)
	}

	db.SetMaxOpenConns(cfg.MaxConns)
	db.SetMaxIdleConns(cfg.MaxIdle)
	db.SetConnMaxLifetime(cfg.MaxLife)

	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	if err := db.PingContext(ctx); err != nil {
		db.Close()
		return nil, fmt.Errorf("ping database: %w", err)
	}

	return db, nil
}
