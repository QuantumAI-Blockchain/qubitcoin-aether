package database

import (
	"context"
	"database/sql"
	"fmt"
	"sort"
	"time"

	"go.uber.org/zap"
)

// SchemaVersion tracks applied migrations.
type SchemaVersion struct {
	Version   string
	Component string
	Desc      string
	AppliedAt time.Time
}

// Migration represents a single database migration.
type Migration struct {
	Version   string
	Component string
	Desc      string
	Up        string // DDL to apply
	Down      string // DDL to rollback (best-effort)
}

// Migrator manages schema migrations against CockroachDB.
type Migrator struct {
	db     *sql.DB
	logger *zap.Logger
}

// NewMigrator creates a new migration manager.
func NewMigrator(db *sql.DB, logger *zap.Logger) *Migrator {
	return &Migrator{db: db, logger: logger}
}

// Initialize creates the schema_version table if it doesn't exist.
func (m *Migrator) Initialize(ctx context.Context) error {
	_, err := m.db.ExecContext(ctx, schemaVersionDDL)
	if err != nil {
		return fmt.Errorf("create schema_version table: %w", err)
	}
	m.logger.Info("schema_version table ready")
	return nil
}

// AppliedVersions returns all applied migration versions for a component.
func (m *Migrator) AppliedVersions(ctx context.Context, component string) (map[string]bool, error) {
	rows, err := m.db.QueryContext(ctx,
		`SELECT version FROM schema_version WHERE component = $1`, component)
	if err != nil {
		return nil, fmt.Errorf("query applied versions: %w", err)
	}
	defer rows.Close()

	applied := make(map[string]bool)
	for rows.Next() {
		var v string
		if err := rows.Scan(&v); err != nil {
			return nil, err
		}
		applied[v] = true
	}
	return applied, rows.Err()
}

// Apply runs all pending migrations for the given component in order.
func (m *Migrator) Apply(ctx context.Context, migrations []Migration) error {
	if len(migrations) == 0 {
		return nil
	}

	component := migrations[0].Component
	applied, err := m.AppliedVersions(ctx, component)
	if err != nil {
		return err
	}

	// Sort by version string.
	sorted := make([]Migration, len(migrations))
	copy(sorted, migrations)
	sort.Slice(sorted, func(i, j int) bool {
		return sorted[i].Version < sorted[j].Version
	})

	for _, mig := range sorted {
		if applied[mig.Version] {
			m.logger.Debug("migration already applied", zap.String("version", mig.Version))
			continue
		}

		m.logger.Info("applying migration",
			zap.String("version", mig.Version),
			zap.String("component", mig.Component),
			zap.String("desc", mig.Desc),
		)

		tx, err := m.db.BeginTx(ctx, nil)
		if err != nil {
			return fmt.Errorf("begin tx for migration %s: %w", mig.Version, err)
		}

		if _, err := tx.ExecContext(ctx, mig.Up); err != nil {
			tx.Rollback()
			return fmt.Errorf("apply migration %s: %w", mig.Version, err)
		}

		if _, err := tx.ExecContext(ctx,
			`INSERT INTO schema_version (version, component, description, applied_at) VALUES ($1, $2, $3, NOW())`,
			mig.Version, mig.Component, mig.Desc,
		); err != nil {
			tx.Rollback()
			return fmt.Errorf("record migration %s: %w", mig.Version, err)
		}

		if err := tx.Commit(); err != nil {
			return fmt.Errorf("commit migration %s: %w", mig.Version, err)
		}

		m.logger.Info("migration applied", zap.String("version", mig.Version))
	}

	return nil
}

// ApplyAll applies all component migrations in dependency order.
func (m *Migrator) ApplyAll(ctx context.Context) error {
	if err := m.Initialize(ctx); err != nil {
		return err
	}

	componentOrder := []struct {
		name       string
		migrations []Migration
	}{
		{"shared", SharedMigrations},
		{"qbc", QBCMigrations},
		{"agi", AGIMigrations},
		{"qvm", QVMMigrations},
		{"research", ResearchMigrations},
		{"privacy", PrivacyMigrations},
		{"bridge", BridgeMigrations},
		{"compliance", ComplianceMigrations},
	}

	for _, c := range componentOrder {
		m.logger.Info("processing component migrations", zap.String("component", c.name))
		if err := m.Apply(ctx, c.migrations); err != nil {
			return fmt.Errorf("component %s: %w", c.name, err)
		}
	}

	m.logger.Info("all migrations applied successfully")
	return nil
}

// ─── Schema Version DDL ──────────────────────────────────────────────

const schemaVersionDDL = `
CREATE TABLE IF NOT EXISTS schema_version (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    version     VARCHAR(64) NOT NULL,
    component   VARCHAR(64) NOT NULL,
    description TEXT,
    applied_at  TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE (version, component)
);
`

// ─── Shared Migrations ───────────────────────────────────────────────

var SharedMigrations = []Migration{
	{
		Version: "001", Component: "shared", Desc: "system config and IPFS",
		Up: `
CREATE TABLE IF NOT EXISTS system_config (
    config_key   VARCHAR(256) PRIMARY KEY,
    config_value TEXT,
    config_type  VARCHAR(32) DEFAULT 'string',
    category     VARCHAR(64),
    description  TEXT,
    is_mutable   BOOL DEFAULT true,
    requires_consensus BOOL DEFAULT false,
    updated_at   TIMESTAMP DEFAULT NOW(),
    updated_by   BYTES
);

CREATE TABLE IF NOT EXISTS network_peers (
    peer_id          VARCHAR(256) PRIMARY KEY,
    ip_address       VARCHAR(64),
    port             INT,
    node_type        VARCHAR(32) DEFAULT 'full',
    is_connected     BOOL DEFAULT false,
    connection_quality VARCHAR(16) DEFAULT 'unknown',
    blocks_shared    BIGINT DEFAULT 0,
    transactions_shared BIGINT DEFAULT 0,
    average_latency_ms BIGINT DEFAULT 0,
    client_version   VARCHAR(128),
    protocol_version VARCHAR(16),
    first_seen       TIMESTAMP DEFAULT NOW(),
    last_seen        TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS blockchain_snapshots (
    snapshot_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    block_height    BIGINT NOT NULL,
    block_hash      BYTES,
    snapshot_type   VARCHAR(32) NOT NULL,
    ipfs_hash       VARCHAR(128) UNIQUE,
    ipfs_size_bytes BIGINT DEFAULT 0,
    compression     VARCHAR(16) DEFAULT 'zstd',
    merkle_root     BYTES,
    is_pinned       BOOL DEFAULT false,
    pin_count       INT DEFAULT 0,
    is_public       BOOL DEFAULT true,
    download_count  BIGINT DEFAULT 0,
    created_timestamp TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS ipfs_content_registry (
    content_id   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ipfs_hash    VARCHAR(128) UNIQUE NOT NULL,
    content_type VARCHAR(64) NOT NULL,
    content_category VARCHAR(64),
    file_name    VARCHAR(256),
    mime_type    VARCHAR(128),
    size_bytes   BIGINT DEFAULT 0,
    is_public    BOOL DEFAULT true,
    owner_address BYTES,
    access_cost  DECIMAL(30,18) DEFAULT 0,
    download_count BIGINT DEFAULT 0,
    last_accessed TIMESTAMP,
    created_timestamp TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS ipfs_pins (
    pin_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ipfs_hash    VARCHAR(128) NOT NULL,
    content_type VARCHAR(64),
    pin_service  VARCHAR(64) DEFAULT 'local',
    service_pin_id VARCHAR(128),
    pin_status   VARCHAR(32) DEFAULT 'queued',
    priority     INT DEFAULT 5,
    pin_requested_at TIMESTAMP DEFAULT NOW(),
    pinned_at    TIMESTAMP,
    expires_at   TIMESTAMP
);

CREATE TABLE IF NOT EXISTS ipfs_gateways (
    gateway_id   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    gateway_name VARCHAR(128) NOT NULL,
    gateway_url  TEXT NOT NULL,
    gateway_type VARCHAR(32) DEFAULT 'public',
    provider     VARCHAR(64),
    is_active    BOOL DEFAULT true,
    is_default   BOOL DEFAULT false,
    health_status VARCHAR(16) DEFAULT 'unknown',
    average_response_ms BIGINT DEFAULT 0,
    uptime_percent DECIMAL(5,2) DEFAULT 0,
    last_health_check TIMESTAMP
);
`,
		Down: `
DROP TABLE IF EXISTS ipfs_gateways;
DROP TABLE IF EXISTS ipfs_pins;
DROP TABLE IF EXISTS ipfs_content_registry;
DROP TABLE IF EXISTS blockchain_snapshots;
DROP TABLE IF EXISTS network_peers;
DROP TABLE IF EXISTS system_config;
`,
	},
}

// ─── QBC (Core Blockchain) Migrations ────────────────────────────────

var QBCMigrations = []Migration{
	{
		Version: "001", Component: "qbc", Desc: "blocks and transactions",
		Up: `
CREATE TABLE IF NOT EXISTS blocks (
    block_hash       BYTES PRIMARY KEY,
    block_height     BIGINT UNIQUE NOT NULL,
    version          INT DEFAULT 1,
    previous_hash    BYTES,
    merkle_root      BYTES,
    timestamp        TIMESTAMP NOT NULL,
    vqe_circuit_hash BYTES,
    hamiltonian_id   UUID,
    target_eigenvalue  DECIMAL(30,18),
    achieved_eigenvalue DECIMAL(30,18),
    alignment_score  DECIMAL(10,8),
    difficulty       DECIMAL(30,18),
    nonce            BIGINT DEFAULT 0,
    miner_address    BYTES,
    era              INT DEFAULT 0,
    base_reward      DECIMAL(30,18),
    actual_reward    DECIMAL(30,18),
    total_fees       DECIMAL(30,18) DEFAULT 0,
    transaction_count INT DEFAULT 0,
    block_size       BIGINT DEFAULT 0,
    gas_used         BIGINT DEFAULT 0,
    gas_limit        BIGINT DEFAULT 30000000,
    is_valid         BOOL DEFAULT true,
    proof_of_thought_hash STRING,
    INDEX idx_blocks_height (block_height),
    INDEX idx_blocks_miner (miner_address),
    INDEX idx_blocks_timestamp (timestamp)
);

CREATE TABLE IF NOT EXISTS transactions (
    tx_hash          BYTES PRIMARY KEY,
    block_hash       BYTES REFERENCES blocks(block_hash),
    block_height     BIGINT,
    tx_index         INT DEFAULT 0,
    version          INT DEFAULT 1,
    timestamp        TIMESTAMP NOT NULL,
    tx_type          VARCHAR(32) DEFAULT 'transfer',
    input_count      INT DEFAULT 0,
    output_count     INT DEFAULT 0,
    total_input      DECIMAL(30,18) DEFAULT 0,
    total_output     DECIMAL(30,18) DEFAULT 0,
    fee              DECIMAL(30,18) DEFAULT 0,
    signature_pubkey BYTES,
    signature_data   BYTES,
    is_confidential  BOOL DEFAULT false,
    contract_address BYTES,
    contract_data    BYTES,
    gas_limit        BIGINT DEFAULT 0,
    gas_used         BIGINT DEFAULT 0,
    gas_price        DECIMAL(30,18) DEFAULT 0,
    tx_size          BIGINT DEFAULT 0,
    is_valid         BOOL DEFAULT true,
    INDEX idx_tx_block (block_hash),
    INDEX idx_tx_height (block_height),
    INDEX idx_tx_type (tx_type)
);

CREATE TABLE IF NOT EXISTS transaction_inputs (
    input_id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tx_hash              BYTES REFERENCES transactions(tx_hash),
    input_index          INT NOT NULL,
    previous_tx_hash     BYTES,
    previous_output_index INT,
    script_sig           BYTES,
    sequence             BIGINT DEFAULT 4294967295
);

CREATE TABLE IF NOT EXISTS transaction_outputs (
    output_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tx_hash        BYTES REFERENCES transactions(tx_hash),
    output_index   INT NOT NULL,
    amount         DECIMAL(30,18) NOT NULL,
    recipient_address BYTES NOT NULL,
    script_pubkey  BYTES,
    is_spent       BOOL DEFAULT false,
    spent_in_tx    BYTES,
    spent_at_height BIGINT,
    spent_at_timestamp TIMESTAMP,
    INDEX idx_utxo_address (recipient_address),
    INDEX idx_utxo_unspent (is_spent) WHERE is_spent = false
);
`,
		Down: `
DROP TABLE IF EXISTS transaction_outputs;
DROP TABLE IF EXISTS transaction_inputs;
DROP TABLE IF EXISTS transactions;
DROP TABLE IF EXISTS blocks;
`,
	},
	{
		Version: "002", Component: "qbc", Desc: "addresses, chain state, mempool",
		Up: `
CREATE TABLE IF NOT EXISTS addresses (
    address          BYTES PRIMARY KEY,
    balance          DECIMAL(30,18) DEFAULT 0,
    total_received   DECIMAL(30,18) DEFAULT 0,
    total_sent       DECIMAL(30,18) DEFAULT 0,
    tx_count         BIGINT DEFAULT 0,
    utxo_count       BIGINT DEFAULT 0,
    is_contract      BOOL DEFAULT false,
    contract_bytecode_hash BYTES,
    first_seen_height BIGINT,
    first_seen_timestamp TIMESTAMP,
    last_active_height BIGINT,
    last_active_timestamp TIMESTAMP
);

CREATE TABLE IF NOT EXISTS chain_state (
    id               INT PRIMARY KEY DEFAULT 1,
    best_block_hash  BYTES,
    best_block_height BIGINT DEFAULT 0,
    total_blocks     BIGINT DEFAULT 0,
    total_transactions BIGINT DEFAULT 0,
    total_addresses  BIGINT DEFAULT 0,
    total_supply     DECIMAL(30,18) DEFAULT 0,
    circulating_supply DECIMAL(30,18) DEFAULT 0,
    current_era      INT DEFAULT 0,
    next_halving_height BIGINT,
    current_difficulty DECIMAL(30,18) DEFAULT 1.0,
    network_hashrate DECIMAL(30,18) DEFAULT 0,
    average_block_time DECIMAL(10,4) DEFAULT 3.3,
    total_contracts  BIGINT DEFAULT 0,
    total_contract_calls BIGINT DEFAULT 0,
    total_knowledge_nodes BIGINT DEFAULT 0,
    total_reasoning_operations BIGINT DEFAULT 0,
    current_phi_score DECIMAL(10,6) DEFAULT 0,
    updated_at       TIMESTAMP DEFAULT NOW(),
    CHECK (id = 1)
);

CREATE TABLE IF NOT EXISTS mempool (
    tx_hash          BYTES PRIMARY KEY,
    raw_tx           BYTES NOT NULL,
    tx_size          BIGINT DEFAULT 0,
    fee              DECIMAL(30,18) DEFAULT 0,
    fee_per_byte     DECIMAL(30,18) DEFAULT 0,
    gas_price        DECIMAL(30,18) DEFAULT 0,
    priority_score   DECIMAL(20,8) DEFAULT 0,
    received_timestamp TIMESTAMP DEFAULT NOW(),
    first_seen_peer  VARCHAR(256),
    propagation_count INT DEFAULT 1,
    is_valid         BOOL DEFAULT true,
    validation_errors TEXT,
    INDEX idx_mempool_priority (priority_score DESC),
    INDEX idx_mempool_fee (fee_per_byte DESC)
);
`,
		Down: `
DROP TABLE IF EXISTS mempool;
DROP TABLE IF EXISTS chain_state;
DROP TABLE IF EXISTS addresses;
`,
	},
}

// ─── AGI (Aether Tree) Migrations ────────────────────────────────────

var AGIMigrations = []Migration{
	{
		Version: "001", Component: "agi", Desc: "knowledge graph",
		Up: `
CREATE TABLE IF NOT EXISTS knowledge_nodes (
    node_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    node_type        VARCHAR(32) NOT NULL,
    node_label       VARCHAR(256),
    node_hash        BYTES UNIQUE,
    content_text     TEXT,
    content_embedding FLOAT8[],
    content_metadata JSONB,
    confidence_score DECIMAL(5,4) DEFAULT 0.5,
    validation_count INT DEFAULT 0,
    consensus_weight DECIMAL(10,6) DEFAULT 1.0,
    anchored_to_block BIGINT,
    anchor_tx_hash   BYTES,
    is_immutable     BOOL DEFAULT false,
    parent_nodes     UUID[],
    child_nodes      UUID[],
    related_nodes    UUID[],
    source_type      VARCHAR(32) DEFAULT 'system',
    source_address   BYTES,
    ipfs_hash        VARCHAR(128),
    created_at       TIMESTAMP DEFAULT NOW(),
    updated_at       TIMESTAMP DEFAULT NOW(),
    INDEX idx_kn_type (node_type),
    INDEX idx_kn_block (anchored_to_block),
    INDEX idx_kn_confidence (confidence_score DESC)
);

CREATE TABLE IF NOT EXISTS knowledge_edges (
    edge_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_node      UUID REFERENCES knowledge_nodes(node_id),
    target_node      UUID REFERENCES knowledge_nodes(node_id),
    edge_type        VARCHAR(32) NOT NULL,
    edge_weight      DECIMAL(10,6) DEFAULT 1.0,
    is_bidirectional BOOL DEFAULT false,
    evidence_count   INT DEFAULT 1,
    confidence_score DECIMAL(5,4) DEFAULT 0.5,
    properties       JSONB,
    anchored_to_block BIGINT,
    created_at       TIMESTAMP DEFAULT NOW(),
    INDEX idx_ke_source (source_node),
    INDEX idx_ke_target (target_node),
    INDEX idx_ke_type (edge_type)
);
`,
		Down: `
DROP TABLE IF EXISTS knowledge_edges;
DROP TABLE IF EXISTS knowledge_nodes;
`,
	},
	{
		Version: "002", Component: "agi", Desc: "reasoning, training, Phi metrics",
		Up: `
CREATE TABLE IF NOT EXISTS reasoning_operations (
    operation_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    reasoning_type   VARCHAR(32) NOT NULL,
    operation_name   VARCHAR(128),
    input_nodes      UUID[],
    input_context    JSONB,
    query_text       TEXT,
    output_nodes     UUID[],
    inferred_relations JSONB,
    conclusion       TEXT,
    confidence_score DECIMAL(5,4),
    execution_time_ms BIGINT DEFAULT 0,
    computational_steps INT DEFAULT 0,
    proof_chain      JSONB,
    triggered_by_tx  BYTES,
    anchored_to_block BIGINT,
    is_verified      BOOL DEFAULT false,
    verification_count INT DEFAULT 0,
    consensus_reached BOOL DEFAULT false,
    created_at       TIMESTAMP DEFAULT NOW(),
    INDEX idx_ro_type (reasoning_type),
    INDEX idx_ro_block (anchored_to_block)
);

CREATE TABLE IF NOT EXISTS inference_rules (
    rule_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    rule_name        VARCHAR(128) UNIQUE NOT NULL,
    rule_type        VARCHAR(32) NOT NULL,
    premise_pattern  JSONB,
    conclusion_pattern JSONB,
    condition_expression TEXT,
    rule_confidence  DECIMAL(5,4) DEFAULT 0.8,
    success_rate     DECIMAL(5,4) DEFAULT 0,
    application_count BIGINT DEFAULT 0,
    is_active        BOOL DEFAULT true,
    is_validated     BOOL DEFAULT false,
    created_by_address BYTES,
    requires_consensus BOOL DEFAULT false,
    created_at       TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS causal_chains (
    chain_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cause_node       UUID REFERENCES knowledge_nodes(node_id),
    effect_node      UUID REFERENCES knowledge_nodes(node_id),
    causal_strength  DECIMAL(5,4) DEFAULT 0.5,
    causal_type      VARCHAR(32) DEFAULT 'correlative',
    evidence_count   INT DEFAULT 1,
    supporting_data  JSONB,
    intermediate_nodes UUID[],
    path_length      INT DEFAULT 1,
    is_validated     BOOL DEFAULT false,
    validation_method VARCHAR(32),
    created_at       TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS training_datasets (
    dataset_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    dataset_name     VARCHAR(256) NOT NULL,
    dataset_type     VARCHAR(64) NOT NULL,
    dataset_category VARCHAR(64),
    sample_count     BIGINT DEFAULT 0,
    feature_count    INT DEFAULT 0,
    data_format      VARCHAR(32) DEFAULT 'json',
    ipfs_hash        VARCHAR(128),
    ipfs_size_bytes  BIGINT DEFAULT 0,
    merkle_root      BYTES,
    quality_score    DECIMAL(5,4) DEFAULT 0,
    validation_accuracy DECIMAL(5,4) DEFAULT 0,
    is_verified      BOOL DEFAULT false,
    is_public        BOOL DEFAULT true,
    access_cost      DECIMAL(30,18) DEFAULT 0,
    usage_count      BIGINT DEFAULT 0,
    created_by_address BYTES,
    anchored_to_block BIGINT,
    created_at       TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS model_registry (
    model_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    model_name       VARCHAR(256) NOT NULL,
    model_type       VARCHAR(64) NOT NULL,
    model_architecture VARCHAR(64),
    trained_on_dataset UUID REFERENCES training_datasets(dataset_id),
    training_epochs  INT DEFAULT 0,
    training_duration_seconds BIGINT DEFAULT 0,
    ipfs_model_hash  VARCHAR(128),
    ipfs_weights_hash VARCHAR(128),
    model_size_bytes BIGINT DEFAULT 0,
    accuracy         DECIMAL(5,4) DEFAULT 0,
    precision_score  DECIMAL(5,4) DEFAULT 0,
    recall_score     DECIMAL(5,4) DEFAULT 0,
    f1_score         DECIMAL(5,4) DEFAULT 0,
    inference_time_ms BIGINT DEFAULT 0,
    version          VARCHAR(32),
    parent_model_id  UUID,
    is_active        BOOL DEFAULT true,
    is_verified      BOOL DEFAULT false,
    deployment_count BIGINT DEFAULT 0,
    owner_address    BYTES,
    anchored_to_block BIGINT,
    created_at       TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS model_predictions (
    prediction_id    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    model_id         UUID REFERENCES model_registry(model_id),
    input_data       JSONB,
    input_hash       BYTES,
    prediction_result JSONB,
    confidence_score DECIMAL(5,4),
    inference_time_ms BIGINT DEFAULT 0,
    gas_used         BIGINT DEFAULT 0,
    ground_truth     JSONB,
    is_correct       BOOL,
    triggered_by_tx  BYTES,
    anchored_to_block BIGINT,
    created_at       TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS phi_measurements (
    measurement_id   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    system_snapshot_id UUID,
    measurement_type VARCHAR(32) DEFAULT 'standard',
    phi_value        DECIMAL(10,6) NOT NULL,
    phi_threshold    DECIMAL(10,6) DEFAULT 3.0,
    exceeds_threshold BOOL DEFAULT false,
    node_count       BIGINT DEFAULT 0,
    edge_count       BIGINT DEFAULT 0,
    causal_chain_length INT DEFAULT 0,
    integration_score DECIMAL(10,6) DEFAULT 0,
    differentiation_score DECIMAL(10,6) DEFAULT 0,
    computation_method VARCHAR(32) DEFAULT 'standard',
    computation_time_ms BIGINT DEFAULT 0,
    confidence_interval JSONB,
    measured_at_height BIGINT,
    anchored_to_block BIGINT,
    previous_phi     DECIMAL(10,6),
    phi_delta        DECIMAL(10,6),
    trend            VARCHAR(16) DEFAULT 'stable',
    measured_at      TIMESTAMP DEFAULT NOW(),
    INDEX idx_phi_height (measured_at_height),
    INDEX idx_phi_value (phi_value)
);

CREATE TABLE IF NOT EXISTS consciousness_events (
    event_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_type       VARCHAR(64) NOT NULL,
    event_severity   VARCHAR(16) DEFAULT 'info',
    event_description TEXT,
    phi_measurement_id UUID REFERENCES phi_measurements(measurement_id),
    phi_value_at_event DECIMAL(10,6),
    supporting_data  JSONB,
    proof_of_emergence JSONB,
    anchored_to_block BIGINT,
    anchor_tx_hash   BYTES,
    is_verified      BOOL DEFAULT false,
    verified_by_consensus BOOL DEFAULT false,
    verification_count INT DEFAULT 0,
    detected_at      TIMESTAMP DEFAULT NOW(),
    INDEX idx_ce_type (event_type),
    INDEX idx_ce_block (anchored_to_block)
);

CREATE TABLE IF NOT EXISTS system_snapshots (
    snapshot_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    block_height     BIGINT NOT NULL,
    snapshot_type    VARCHAR(32) DEFAULT 'full',
    total_nodes      BIGINT DEFAULT 0,
    total_edges      BIGINT DEFAULT 0,
    active_operations INT DEFAULT 0,
    graph_diameter   INT DEFAULT 0,
    clustering_coefficient DECIMAL(5,4) DEFAULT 0,
    betweenness_centrality JSONB,
    state_hash       BYTES UNIQUE,
    ipfs_hash        VARCHAR(128),
    snapshot_size_bytes BIGINT DEFAULT 0,
    created_at       TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS agi_governance (
    proposal_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    proposal_type    VARCHAR(32) NOT NULL,
    title            VARCHAR(256) NOT NULL,
    description      TEXT,
    proposer_address BYTES NOT NULL,
    voting_start_height BIGINT,
    voting_end_height BIGINT,
    votes_for        BIGINT DEFAULT 0,
    votes_against    BIGINT DEFAULT 0,
    votes_abstain    BIGINT DEFAULT 0,
    status           VARCHAR(32) DEFAULT 'proposed',
    execution_block  BIGINT,
    execution_data   JSONB,
    execution_result TEXT,
    created_at       TIMESTAMP DEFAULT NOW(),
    executed_at      TIMESTAMP
);
`,
		Down: `
DROP TABLE IF EXISTS agi_governance;
DROP TABLE IF EXISTS system_snapshots;
DROP TABLE IF EXISTS consciousness_events;
DROP TABLE IF EXISTS phi_measurements;
DROP TABLE IF EXISTS model_predictions;
DROP TABLE IF EXISTS model_registry;
DROP TABLE IF EXISTS training_datasets;
DROP TABLE IF EXISTS causal_chains;
DROP TABLE IF EXISTS inference_rules;
DROP TABLE IF EXISTS reasoning_operations;
`,
	},
}

// ─── QVM (Smart Contracts) Migrations ────────────────────────────────

var QVMMigrations = []Migration{
	{
		Version: "001", Component: "qvm", Desc: "contracts core and execution",
		Up: `
CREATE TABLE IF NOT EXISTS smart_contracts (
    contract_address BYTES PRIMARY KEY,
    creator_address  BYTES NOT NULL,
    deployer_tx_hash BYTES,
    deployed_at_height BIGINT,
    deployed_timestamp TIMESTAMP DEFAULT NOW(),
    bytecode         BYTES NOT NULL,
    bytecode_hash    BYTES NOT NULL,
    bytecode_size    BIGINT DEFAULT 0,
    contract_name    VARCHAR(256),
    contract_type    VARCHAR(64) DEFAULT 'custom',
    contract_version VARCHAR(32) DEFAULT '1.0',
    is_verified      BOOL DEFAULT false,
    source_code      TEXT,
    compiler_version VARCHAR(64),
    optimization_enabled BOOL DEFAULT false,
    balance          DECIMAL(30,18) DEFAULT 0,
    total_gas_used   BIGINT DEFAULT 0,
    execution_count  BIGINT DEFAULT 0,
    is_active        BOOL DEFAULT true,
    is_paused        BOOL DEFAULT false,
    is_upgradeable   BOOL DEFAULT false,
    proxy_implementation BYTES,
    ipfs_bytecode_hash VARCHAR(128),
    ipfs_source_hash VARCHAR(128),
    INDEX idx_sc_creator (creator_address),
    INDEX idx_sc_type (contract_type)
);

CREATE TABLE IF NOT EXISTS token_contracts (
    contract_address BYTES PRIMARY KEY REFERENCES smart_contracts(contract_address),
    token_standard   VARCHAR(16) NOT NULL,
    token_name       VARCHAR(128),
    token_symbol     VARCHAR(16),
    decimals         INT DEFAULT 18,
    total_supply     DECIMAL(38,18) DEFAULT 0,
    max_supply       DECIMAL(38,18),
    circulating_supply DECIMAL(38,18) DEFAULT 0,
    total_holders    BIGINT DEFAULT 0,
    total_transfers  BIGINT DEFAULT 0,
    is_mintable      BOOL DEFAULT true,
    is_burnable      BOOL DEFAULT true,
    is_pausable      BOOL DEFAULT true
);

CREATE TABLE IF NOT EXISTS contract_executions (
    execution_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tx_hash          BYTES,
    block_hash       BYTES,
    block_height     BIGINT,
    tx_index         INT DEFAULT 0,
    contract_address BYTES REFERENCES smart_contracts(contract_address),
    caller_address   BYTES NOT NULL,
    function_selector BYTES,
    function_name    VARCHAR(128),
    input_data       BYTES,
    gas_limit        BIGINT DEFAULT 0,
    gas_used         BIGINT DEFAULT 0,
    gas_price        DECIMAL(30,18) DEFAULT 0,
    execution_cost   DECIMAL(30,18) DEFAULT 0,
    success          BOOL DEFAULT true,
    return_data      BYTES,
    error_message    TEXT,
    revert_reason    TEXT,
    execution_time_ms BIGINT DEFAULT 0,
    opcodes_executed INT DEFAULT 0,
    storage_writes   INT DEFAULT 0,
    storage_reads    INT DEFAULT 0,
    logs_count       INT DEFAULT 0,
    timestamp        TIMESTAMP DEFAULT NOW(),
    INDEX idx_ce_contract (contract_address),
    INDEX idx_ce_height (block_height),
    INDEX idx_ce_caller (caller_address)
);

CREATE TABLE IF NOT EXISTS contract_logs (
    log_id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    execution_id     UUID REFERENCES contract_executions(execution_id),
    tx_hash          BYTES,
    block_height     BIGINT,
    contract_address BYTES,
    log_index        INT DEFAULT 0,
    topic0           BYTES,
    topic1           BYTES,
    topic2           BYTES,
    topic3           BYTES,
    data             BYTES,
    event_name       VARCHAR(128),
    decoded_data     JSONB,
    timestamp        TIMESTAMP DEFAULT NOW(),
    INDEX idx_cl_contract (contract_address),
    INDEX idx_cl_topic0 (topic0)
);
`,
		Down: `
DROP TABLE IF EXISTS contract_logs;
DROP TABLE IF EXISTS contract_executions;
DROP TABLE IF EXISTS token_contracts;
DROP TABLE IF EXISTS smart_contracts;
`,
	},
	{
		Version: "002", Component: "qvm", Desc: "storage, snapshots, gas oracle, opcodes",
		Up: `
CREATE TABLE IF NOT EXISTS contract_storage (
    storage_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    contract_address BYTES NOT NULL,
    storage_key      BYTES NOT NULL,
    storage_value    BYTES,
    value_type       VARCHAR(32) DEFAULT 'bytes32',
    last_modified_height BIGINT,
    last_modified_tx BYTES,
    last_modified_timestamp TIMESTAMP DEFAULT NOW(),
    UNIQUE (contract_address, storage_key)
);

CREATE TABLE IF NOT EXISTS contract_state_snapshots (
    snapshot_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    contract_address BYTES REFERENCES smart_contracts(contract_address),
    block_height     BIGINT NOT NULL,
    block_hash       BYTES,
    storage_root     BYTES,
    state_data       JSONB,
    storage_size     BIGINT DEFAULT 0,
    ipfs_hash        VARCHAR(128),
    created_timestamp TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS gas_price_oracle (
    oracle_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    block_height     BIGINT NOT NULL,
    base_fee         DECIMAL(30,18) DEFAULT 0,
    priority_fee_percentile_50 DECIMAL(30,18) DEFAULT 0,
    priority_fee_percentile_75 DECIMAL(30,18) DEFAULT 0,
    priority_fee_percentile_90 DECIMAL(30,18) DEFAULT 0,
    gas_used         BIGINT DEFAULT 0,
    gas_limit        BIGINT DEFAULT 30000000,
    utilization_percent DECIMAL(5,2) DEFAULT 0,
    sample_size      INT DEFAULT 0,
    timestamp        TIMESTAMP DEFAULT NOW(),
    INDEX idx_gpo_height (block_height DESC)
);

CREATE TABLE IF NOT EXISTS opcode_costs (
    opcode_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    opcode_name      VARCHAR(32) UNIQUE NOT NULL,
    opcode_value     INT NOT NULL,
    base_gas_cost    BIGINT DEFAULT 0,
    memory_gas_cost  BIGINT DEFAULT 0,
    storage_gas_cost BIGINT DEFAULT 0,
    category         VARCHAR(32),
    description      TEXT,
    is_quantum_enhanced BOOL DEFAULT false
);
`,
		Down: `
DROP TABLE IF EXISTS opcode_costs;
DROP TABLE IF EXISTS gas_price_oracle;
DROP TABLE IF EXISTS contract_state_snapshots;
DROP TABLE IF EXISTS contract_storage;
`,
	},
}

// ─── Research (Quantum) Migrations ───────────────────────────────────

var ResearchMigrations = []Migration{
	{
		Version: "001", Component: "research", Desc: "hamiltonians, VQE circuits, SUSY solutions",
		Up: `
CREATE TABLE IF NOT EXISTS hamiltonians (
    hamiltonian_id   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    hamiltonian_hash BYTES UNIQUE NOT NULL,
    system_type      VARCHAR(64) DEFAULT 'susy',
    dimension        INT NOT NULL,
    qubit_count      INT NOT NULL,
    hamiltonian_matrix JSONB,
    expected_ground_energy DECIMAL(30,18),
    difficulty_class VARCHAR(16) DEFAULT 'medium',
    computational_complexity INT DEFAULT 0,
    is_active        BOOL DEFAULT true,
    times_mined      BIGINT DEFAULT 0,
    best_solution_energy DECIMAL(30,18),
    best_solution_miner BYTES,
    ipfs_hash        VARCHAR(128),
    ipfs_metadata_hash VARCHAR(128),
    added_timestamp  TIMESTAMP DEFAULT NOW(),
    last_mined_timestamp TIMESTAMP,
    INDEX idx_h_qubits (qubit_count),
    INDEX idx_h_active (is_active)
);

CREATE TABLE IF NOT EXISTS vqe_circuits (
    circuit_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    circuit_hash     BYTES UNIQUE NOT NULL,
    hamiltonian_id   UUID REFERENCES hamiltonians(hamiltonian_id),
    qubit_count      INT NOT NULL,
    circuit_depth    INT DEFAULT 0,
    gate_count       INT DEFAULT 0,
    ansatz_type      VARCHAR(64) DEFAULT 'ry_rz',
    circuit_definition JSONB,
    optimized_parameters JSONB,
    achieved_energy  DECIMAL(30,18),
    convergence_iterations INT DEFAULT 0,
    execution_time_ms BIGINT DEFAULT 0,
    block_hash       BYTES,
    block_height     BIGINT,
    miner_address    BYTES,
    ipfs_hash        VARCHAR(128),
    created_timestamp TIMESTAMP DEFAULT NOW(),
    INDEX idx_vc_hamiltonian (hamiltonian_id),
    INDEX idx_vc_height (block_height)
);

CREATE TABLE IF NOT EXISTS susy_solutions (
    solution_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    hamiltonian_id   UUID REFERENCES hamiltonians(hamiltonian_id),
    circuit_id       UUID REFERENCES vqe_circuits(circuit_id),
    block_hash       BYTES,
    block_height     BIGINT,
    miner_address    BYTES,
    ground_state_energy DECIMAL(30,18) NOT NULL,
    alignment_score  DECIMAL(10,8),
    energy_gap       DECIMAL(30,18),
    fidelity         DECIMAL(10,8),
    is_verified      BOOL DEFAULT false,
    verification_method VARCHAR(32),
    verified_by_peers INT DEFAULT 0,
    novelty_score    DECIMAL(5,4) DEFAULT 0,
    scientific_value VARCHAR(16) DEFAULT 'low',
    ipfs_hash        VARCHAR(128),
    ipfs_analysis_hash VARCHAR(128),
    discovered_timestamp TIMESTAMP DEFAULT NOW(),
    verified_timestamp TIMESTAMP,
    INDEX idx_ss_height (block_height),
    INDEX idx_ss_energy (ground_state_energy),
    INDEX idx_ss_miner (miner_address)
);
`,
		Down: `
DROP TABLE IF EXISTS susy_solutions;
DROP TABLE IF EXISTS vqe_circuits;
DROP TABLE IF EXISTS hamiltonians;
`,
	},
}

// ─── Privacy Migrations ──────────────────────────────────────────────

var PrivacyMigrations = []Migration{
	{
		Version: "001", Component: "privacy", Desc: "confidential transactions and stealth addresses",
		Up: `
CREATE TABLE IF NOT EXISTS confidential_transactions (
    tx_hash          BYTES PRIMARY KEY,
    block_hash       BYTES,
    block_height     BIGINT,
    timestamp        TIMESTAMP DEFAULT NOW(),
    input_commitments BYTES[],
    output_commitments BYTES[],
    range_proofs     BYTES[],
    fee              DECIMAL(30,18) DEFAULT 0,
    signature        BYTES,
    is_valid         BOOL DEFAULT true,
    INDEX idx_ct_height (block_height)
);

CREATE TABLE IF NOT EXISTS stealth_addresses (
    stealth_address  BYTES PRIMARY KEY,
    public_spend_key BYTES NOT NULL,
    public_view_key  BYTES NOT NULL,
    one_time_pubkey  BYTES UNIQUE NOT NULL,
    tx_hash          BYTES,
    output_index     INT DEFAULT 0,
    created_at_height BIGINT,
    is_spent         BOOL DEFAULT false,
    INDEX idx_sa_spend (public_spend_key)
);

CREATE TABLE IF NOT EXISTS key_images (
    key_image        STRING PRIMARY KEY,
    tx_hash          BYTES NOT NULL,
    block_height     BIGINT,
    created_at       TIMESTAMP DEFAULT NOW(),
    INDEX idx_ki_height (block_height)
);

CREATE TABLE IF NOT EXISTS range_proof_cache (
    proof_hash       STRING PRIMARY KEY,
    commitment_hash  STRING NOT NULL,
    verified         BOOL DEFAULT false,
    verified_at      TIMESTAMP,
    block_height     BIGINT
);

CREATE TABLE IF NOT EXISTS susy_swap_pools (
    pool_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    token_a_address  BYTES,
    token_b_address  BYTES,
    token_a_commitment BYTES,
    token_b_commitment BYTES,
    total_swaps      BIGINT DEFAULT 0,
    swap_fee_basis_points INT DEFAULT 30,
    is_active        BOOL DEFAULT true,
    created_timestamp TIMESTAMP DEFAULT NOW()
);
`,
		Down: `
DROP TABLE IF EXISTS susy_swap_pools;
DROP TABLE IF EXISTS range_proof_cache;
DROP TABLE IF EXISTS key_images;
DROP TABLE IF EXISTS stealth_addresses;
DROP TABLE IF EXISTS confidential_transactions;
`,
	},
}

// ─── Bridge Migrations ───────────────────────────────────────────────

var BridgeMigrations = []Migration{
	{
		Version: "001", Component: "bridge", Desc: "chains, validators, transfers, QUSD",
		Up: `
CREATE TABLE IF NOT EXISTS supported_chains (
    chain_id         VARCHAR(16) PRIMARY KEY,
    chain_name       VARCHAR(64) UNIQUE NOT NULL,
    chain_type       VARCHAR(16) DEFAULT 'evm',
    rpc_endpoint     TEXT,
    bridge_contract_address VARCHAR(128),
    block_time_seconds INT DEFAULT 12,
    confirmation_blocks INT DEFAULT 20,
    base_fee         DECIMAL(30,18) DEFAULT 0,
    min_transfer_amount DECIMAL(30,18) DEFAULT 0.01,
    max_transfer_amount DECIMAL(30,18) DEFAULT 100000,
    is_active        BOOL DEFAULT true,
    total_transfers  BIGINT DEFAULT 0
);

CREATE TABLE IF NOT EXISTS bridge_validators (
    validator_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    validator_address BYTES UNIQUE NOT NULL,
    validator_name   VARCHAR(128),
    bonded_amount    DECIMAL(30,18) DEFAULT 0,
    is_active        BOOL DEFAULT true,
    reputation_score DECIMAL(5,4) DEFAULT 1.0,
    registered_timestamp TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS bridge_transfers (
    transfer_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_chain     VARCHAR(16) REFERENCES supported_chains(chain_id),
    destination_chain VARCHAR(16) NOT NULL,
    source_tx_hash   VARCHAR(128),
    sender_address   VARCHAR(128) NOT NULL,
    recipient_address VARCHAR(128) NOT NULL,
    amount           DECIMAL(30,18) NOT NULL,
    bridge_fee       DECIMAL(30,18) DEFAULT 0,
    status           VARCHAR(32) DEFAULT 'initiated',
    initiated_timestamp TIMESTAMP DEFAULT NOW(),
    INDEX idx_bt_status (status),
    INDEX idx_bt_sender (sender_address)
);

CREATE TABLE IF NOT EXISTS qusd_config (
    id               INT PRIMARY KEY DEFAULT 1,
    initial_supply   DECIMAL(38,18) DEFAULT 3300000000,
    current_supply   DECIMAL(38,18) DEFAULT 3300000000,
    target_reserve_ratio DECIMAL(5,4) DEFAULT 1.0,
    current_reserve_ratio DECIMAL(5,4) DEFAULT 0.05,
    is_active        BOOL DEFAULT true,
    last_updated     TIMESTAMP DEFAULT NOW(),
    CHECK (id = 1)
);

CREATE TABLE IF NOT EXISTS qusd_balances (
    address          BYTES PRIMARY KEY,
    balance          DECIMAL(38,18) DEFAULT 0,
    locked_balance   DECIMAL(38,18) DEFAULT 0,
    total_minted     DECIMAL(38,18) DEFAULT 0,
    total_burned     DECIMAL(38,18) DEFAULT 0
);

CREATE TABLE IF NOT EXISTS qusd_reserves (
    reserve_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    asset_type       VARCHAR(32) NOT NULL,
    amount           DECIMAL(38,18) DEFAULT 0,
    usd_value        DECIMAL(38,18) DEFAULT 0,
    storage_type     VARCHAR(32) DEFAULT 'on_chain',
    is_verified      BOOL DEFAULT false,
    last_updated     TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS qusd_debt (
    id               INT PRIMARY KEY DEFAULT 1,
    total_debt       DECIMAL(38,18) DEFAULT 3300000000,
    total_reserves_usd DECIMAL(38,18) DEFAULT 0,
    backing_percentage DECIMAL(10,6) DEFAULT 0,
    last_updated     TIMESTAMP DEFAULT NOW(),
    CHECK (id = 1)
);
`,
		Down: `
DROP TABLE IF EXISTS qusd_debt;
DROP TABLE IF EXISTS qusd_reserves;
DROP TABLE IF EXISTS qusd_balances;
DROP TABLE IF EXISTS qusd_config;
DROP TABLE IF EXISTS bridge_transfers;
DROP TABLE IF EXISTS bridge_validators;
DROP TABLE IF EXISTS supported_chains;
`,
	},
}

// ─── Compliance Migrations ───────────────────────────────────────────

var ComplianceMigrations = []Migration{
	{
		Version: "001", Component: "compliance", Desc: "KYC registry, quantum states, entanglement",
		Up: `
CREATE TABLE IF NOT EXISTS compliance_registry (
    address          STRING PRIMARY KEY,
    kyc_level        INT DEFAULT 0,
    aml_status       VARCHAR(32) DEFAULT 'unchecked',
    sanctions_checked BOOL DEFAULT false,
    last_verified    TIMESTAMP,
    jurisdiction     VARCHAR(8),
    daily_limit      DECIMAL(30,18) DEFAULT 10000,
    is_blocked       BOOL DEFAULT false,
    created_at       TIMESTAMP DEFAULT NOW(),
    updated_at       TIMESTAMP DEFAULT NOW(),
    INDEX idx_cr_kyc (kyc_level),
    INDEX idx_cr_blocked (is_blocked)
);

CREATE TABLE IF NOT EXISTS quantum_states (
    state_id         STRING PRIMARY KEY,
    n_qubits         INT NOT NULL,
    contract_address STRING,
    block_height     BIGINT,
    measured         BOOL DEFAULT false,
    entangled_with   STRING,
    created_at       TIMESTAMP DEFAULT NOW(),
    INDEX idx_qs_contract (contract_address),
    INDEX idx_qs_measured (measured)
);

CREATE TABLE IF NOT EXISTS entanglement_pairs (
    pair_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    state_a          STRING REFERENCES quantum_states(state_id),
    state_b          STRING REFERENCES quantum_states(state_id),
    block_height     BIGINT,
    created_at       TIMESTAMP DEFAULT NOW(),
    is_active        BOOL DEFAULT true
);
`,
		Down: `
DROP TABLE IF EXISTS entanglement_pairs;
DROP TABLE IF EXISTS quantum_states;
DROP TABLE IF EXISTS compliance_registry;
`,
	},
}

// AllMigrations returns every migration across all components.
func AllMigrations() []Migration {
	var all []Migration
	all = append(all, SharedMigrations...)
	all = append(all, QBCMigrations...)
	all = append(all, AGIMigrations...)
	all = append(all, QVMMigrations...)
	all = append(all, ResearchMigrations...)
	all = append(all, PrivacyMigrations...)
	all = append(all, BridgeMigrations...)
	all = append(all, ComplianceMigrations...)
	return all
}

// TableCount returns the total number of tables defined across all migrations.
func TableCount() int {
	// 55 tables across 8 components:
	// shared: 6 (system_config, network_peers, blockchain_snapshots, ipfs_content_registry, ipfs_pins, ipfs_gateways)
	// qbc: 7 (blocks, transactions, transaction_inputs, transaction_outputs, addresses, chain_state, mempool)
	// agi: 11 (knowledge_nodes, knowledge_edges, reasoning_operations, inference_rules, causal_chains,
	//          training_datasets, model_registry, model_predictions, phi_measurements, consciousness_events,
	//          system_snapshots, agi_governance) -> 12
	// qvm: 8 (smart_contracts, token_contracts, contract_executions, contract_logs,
	//         contract_storage, contract_state_snapshots, gas_price_oracle, opcode_costs)
	// research: 3 (hamiltonians, vqe_circuits, susy_solutions)
	// privacy: 5 (confidential_transactions, stealth_addresses, key_images, range_proof_cache, susy_swap_pools)
	// bridge: 7 (supported_chains, bridge_validators, bridge_transfers, qusd_config, qusd_balances, qusd_reserves, qusd_debt)
	// compliance: 3 (compliance_registry, quantum_states, entanglement_pairs)
	return 55
}
