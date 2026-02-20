package database

import (
	"math/big"
	"time"
)

// ─── Core Blockchain Models ──────────────────────────────────────────

// Block represents a Qubitcoin block.
type Block struct {
	BlockHash          []byte     `db:"block_hash" json:"block_hash"`
	BlockHeight        uint64     `db:"block_height" json:"block_height"`
	Version            int        `db:"version" json:"version"`
	PreviousHash       []byte     `db:"previous_hash" json:"previous_hash"`
	MerkleRoot         []byte     `db:"merkle_root" json:"merkle_root"`
	Timestamp          time.Time  `db:"timestamp" json:"timestamp"`
	VQECircuitHash     []byte     `db:"vqe_circuit_hash" json:"vqe_circuit_hash,omitempty"`
	HamiltonianID      string     `db:"hamiltonian_id" json:"hamiltonian_id,omitempty"`
	TargetEigenvalue   float64    `db:"target_eigenvalue" json:"target_eigenvalue"`
	AchievedEigenvalue float64    `db:"achieved_eigenvalue" json:"achieved_eigenvalue"`
	AlignmentScore     float64    `db:"alignment_score" json:"alignment_score"`
	Difficulty         float64    `db:"difficulty" json:"difficulty"`
	Nonce              uint64     `db:"nonce" json:"nonce"`
	MinerAddress       []byte     `db:"miner_address" json:"miner_address"`
	Era                int        `db:"era" json:"era"`
	BaseReward         float64    `db:"base_reward" json:"base_reward"`
	ActualReward       float64    `db:"actual_reward" json:"actual_reward"`
	TotalFees          float64    `db:"total_fees" json:"total_fees"`
	TransactionCount   int        `db:"transaction_count" json:"transaction_count"`
	BlockSize          int64      `db:"block_size" json:"block_size"`
	GasUsed            uint64     `db:"gas_used" json:"gas_used"`
	GasLimit           uint64     `db:"gas_limit" json:"gas_limit"`
	IsValid            bool       `db:"is_valid" json:"is_valid"`
	PoTHash            string     `db:"proof_of_thought_hash" json:"proof_of_thought_hash,omitempty"`
}

// Transaction represents a Qubitcoin transaction.
type Transaction struct {
	TxHash          []byte    `db:"tx_hash" json:"tx_hash"`
	BlockHash       []byte    `db:"block_hash" json:"block_hash,omitempty"`
	BlockHeight     uint64    `db:"block_height" json:"block_height"`
	TxIndex         int       `db:"tx_index" json:"tx_index"`
	Version         int       `db:"version" json:"version"`
	Timestamp       time.Time `db:"timestamp" json:"timestamp"`
	TxType          string    `db:"tx_type" json:"tx_type"`
	InputCount      int       `db:"input_count" json:"input_count"`
	OutputCount     int       `db:"output_count" json:"output_count"`
	TotalInput      float64   `db:"total_input" json:"total_input"`
	TotalOutput     float64   `db:"total_output" json:"total_output"`
	Fee             float64   `db:"fee" json:"fee"`
	SignaturePubkey []byte    `db:"signature_pubkey" json:"signature_pubkey,omitempty"`
	SignatureData   []byte    `db:"signature_data" json:"signature_data,omitempty"`
	IsConfidential  bool      `db:"is_confidential" json:"is_confidential"`
	ContractAddress []byte    `db:"contract_address" json:"contract_address,omitempty"`
	ContractData    []byte    `db:"contract_data" json:"contract_data,omitempty"`
	GasLimit        uint64    `db:"gas_limit" json:"gas_limit"`
	GasUsed         uint64    `db:"gas_used" json:"gas_used"`
	GasPrice        float64   `db:"gas_price" json:"gas_price"`
	TxSize          int64     `db:"tx_size" json:"tx_size"`
	IsValid         bool      `db:"is_valid" json:"is_valid"`
}

// TxInput represents a transaction input (UTXO reference).
type TxInput struct {
	InputID            string `db:"input_id" json:"input_id"`
	TxHash             []byte `db:"tx_hash" json:"tx_hash"`
	InputIndex         int    `db:"input_index" json:"input_index"`
	PreviousTxHash     []byte `db:"previous_tx_hash" json:"previous_tx_hash"`
	PreviousOutputIndex int   `db:"previous_output_index" json:"previous_output_index"`
	ScriptSig          []byte `db:"script_sig" json:"script_sig,omitempty"`
	Sequence           uint64 `db:"sequence" json:"sequence"`
}

// TxOutput represents a transaction output (UTXO).
type TxOutput struct {
	OutputID         string    `db:"output_id" json:"output_id"`
	TxHash           []byte    `db:"tx_hash" json:"tx_hash"`
	OutputIndex      int       `db:"output_index" json:"output_index"`
	Amount           float64   `db:"amount" json:"amount"`
	RecipientAddress []byte    `db:"recipient_address" json:"recipient_address"`
	ScriptPubkey     []byte    `db:"script_pubkey" json:"script_pubkey,omitempty"`
	IsSpent          bool      `db:"is_spent" json:"is_spent"`
	SpentInTx        []byte    `db:"spent_in_tx" json:"spent_in_tx,omitempty"`
	SpentAtHeight    uint64    `db:"spent_at_height" json:"spent_at_height,omitempty"`
	SpentAtTimestamp *time.Time `db:"spent_at_timestamp" json:"spent_at_timestamp,omitempty"`
}

// Address represents a tracked address.
type Address struct {
	Address            []byte    `db:"address" json:"address"`
	Balance            float64   `db:"balance" json:"balance"`
	TotalReceived      float64   `db:"total_received" json:"total_received"`
	TotalSent          float64   `db:"total_sent" json:"total_sent"`
	TxCount            uint64    `db:"tx_count" json:"tx_count"`
	UTXOCount          uint64    `db:"utxo_count" json:"utxo_count"`
	IsContract         bool      `db:"is_contract" json:"is_contract"`
	FirstSeenHeight    uint64    `db:"first_seen_height" json:"first_seen_height"`
	FirstSeenTimestamp time.Time `db:"first_seen_timestamp" json:"first_seen_timestamp"`
	LastActiveHeight   uint64    `db:"last_active_height" json:"last_active_height"`
	LastActiveTimestamp time.Time `db:"last_active_timestamp" json:"last_active_timestamp"`
}

// ChainState represents the singleton chain state row.
type ChainState struct {
	BestBlockHash      []byte  `db:"best_block_hash" json:"best_block_hash"`
	BestBlockHeight    uint64  `db:"best_block_height" json:"best_block_height"`
	TotalBlocks        uint64  `db:"total_blocks" json:"total_blocks"`
	TotalTransactions  uint64  `db:"total_transactions" json:"total_transactions"`
	TotalAddresses     uint64  `db:"total_addresses" json:"total_addresses"`
	TotalSupply        float64 `db:"total_supply" json:"total_supply"`
	CirculatingSupply  float64 `db:"circulating_supply" json:"circulating_supply"`
	CurrentEra         int     `db:"current_era" json:"current_era"`
	NextHalvingHeight  uint64  `db:"next_halving_height" json:"next_halving_height"`
	CurrentDifficulty  float64 `db:"current_difficulty" json:"current_difficulty"`
	AverageBlockTime   float64 `db:"average_block_time" json:"average_block_time"`
	TotalContracts     uint64  `db:"total_contracts" json:"total_contracts"`
	CurrentPhiScore    float64 `db:"current_phi_score" json:"current_phi_score"`
}

// MempoolEntry represents a pending transaction.
type MempoolEntry struct {
	TxHash            []byte    `db:"tx_hash" json:"tx_hash"`
	RawTx             []byte    `db:"raw_tx" json:"raw_tx"`
	TxSize            int64     `db:"tx_size" json:"tx_size"`
	Fee               float64   `db:"fee" json:"fee"`
	FeePerByte        float64   `db:"fee_per_byte" json:"fee_per_byte"`
	GasPrice          float64   `db:"gas_price" json:"gas_price"`
	PriorityScore     float64   `db:"priority_score" json:"priority_score"`
	ReceivedTimestamp time.Time `db:"received_timestamp" json:"received_timestamp"`
	PropagationCount  int       `db:"propagation_count" json:"propagation_count"`
	IsValid           bool      `db:"is_valid" json:"is_valid"`
}

// ─── QVM Models ──────────────────────────────────────────────────────

// SmartContract represents a deployed smart contract.
type SmartContract struct {
	ContractAddress    []byte    `db:"contract_address" json:"contract_address"`
	CreatorAddress     []byte    `db:"creator_address" json:"creator_address"`
	DeployerTxHash     []byte    `db:"deployer_tx_hash" json:"deployer_tx_hash,omitempty"`
	DeployedAtHeight   uint64    `db:"deployed_at_height" json:"deployed_at_height"`
	DeployedTimestamp  time.Time `db:"deployed_timestamp" json:"deployed_timestamp"`
	Bytecode           []byte    `db:"bytecode" json:"bytecode"`
	BytecodeHash       []byte    `db:"bytecode_hash" json:"bytecode_hash"`
	BytecodeSize       int64     `db:"bytecode_size" json:"bytecode_size"`
	ContractName       string    `db:"contract_name" json:"contract_name,omitempty"`
	ContractType       string    `db:"contract_type" json:"contract_type"`
	IsVerified         bool      `db:"is_verified" json:"is_verified"`
	SourceCode         string    `db:"source_code" json:"source_code,omitempty"`
	Balance            float64   `db:"balance" json:"balance"`
	TotalGasUsed       uint64    `db:"total_gas_used" json:"total_gas_used"`
	ExecutionCount     uint64    `db:"execution_count" json:"execution_count"`
	IsActive           bool      `db:"is_active" json:"is_active"`
	IsPaused           bool      `db:"is_paused" json:"is_paused"`
	IsUpgradeable      bool      `db:"is_upgradeable" json:"is_upgradeable"`
}

// ContractExecution records a single contract invocation.
type ContractExecution struct {
	ExecutionID     string    `db:"execution_id" json:"execution_id"`
	TxHash          []byte    `db:"tx_hash" json:"tx_hash"`
	BlockHeight     uint64    `db:"block_height" json:"block_height"`
	ContractAddress []byte    `db:"contract_address" json:"contract_address"`
	CallerAddress   []byte    `db:"caller_address" json:"caller_address"`
	FunctionName    string    `db:"function_name" json:"function_name,omitempty"`
	GasLimit        uint64    `db:"gas_limit" json:"gas_limit"`
	GasUsed         uint64    `db:"gas_used" json:"gas_used"`
	Success         bool      `db:"success" json:"success"`
	ReturnData      []byte    `db:"return_data" json:"return_data,omitempty"`
	ErrorMessage    string    `db:"error_message" json:"error_message,omitempty"`
	RevertReason    string    `db:"revert_reason" json:"revert_reason,omitempty"`
	ExecutionTimeMs int64     `db:"execution_time_ms" json:"execution_time_ms"`
	OpcodesExecuted int       `db:"opcodes_executed" json:"opcodes_executed"`
	StorageWrites   int       `db:"storage_writes" json:"storage_writes"`
	StorageReads    int       `db:"storage_reads" json:"storage_reads"`
	LogsCount       int       `db:"logs_count" json:"logs_count"`
	Timestamp       time.Time `db:"timestamp" json:"timestamp"`
}

// ContractLog represents an event emitted by a contract.
type ContractLog struct {
	LogID           string    `db:"log_id" json:"log_id"`
	ExecutionID     string    `db:"execution_id" json:"execution_id"`
	TxHash          []byte    `db:"tx_hash" json:"tx_hash"`
	BlockHeight     uint64    `db:"block_height" json:"block_height"`
	ContractAddress []byte    `db:"contract_address" json:"contract_address"`
	LogIndex        int       `db:"log_index" json:"log_index"`
	Topic0          []byte    `db:"topic0" json:"topic0,omitempty"`
	Topic1          []byte    `db:"topic1" json:"topic1,omitempty"`
	Topic2          []byte    `db:"topic2" json:"topic2,omitempty"`
	Topic3          []byte    `db:"topic3" json:"topic3,omitempty"`
	Data            []byte    `db:"data" json:"data,omitempty"`
	EventName       string    `db:"event_name" json:"event_name,omitempty"`
	Timestamp       time.Time `db:"timestamp" json:"timestamp"`
}

// StorageSlot represents a contract storage key-value pair.
type StorageSlot struct {
	ContractAddress []byte    `db:"contract_address" json:"contract_address"`
	StorageKey      []byte    `db:"storage_key" json:"storage_key"`
	StorageValue    []byte    `db:"storage_value" json:"storage_value"`
	LastModHeight   uint64    `db:"last_modified_height" json:"last_modified_height"`
	LastModTimestamp time.Time `db:"last_modified_timestamp" json:"last_modified_timestamp"`
}

// ─── AGI / Aether Tree Models ────────────────────────────────────────

// KnowledgeNode represents a node in the Aether Tree knowledge graph.
type KnowledgeNode struct {
	NodeID          string    `db:"node_id" json:"node_id"`
	NodeType        string    `db:"node_type" json:"node_type"`
	NodeLabel       string    `db:"node_label" json:"node_label,omitempty"`
	ContentText     string    `db:"content_text" json:"content_text,omitempty"`
	ConfidenceScore float64   `db:"confidence_score" json:"confidence_score"`
	AnchoredToBlock uint64    `db:"anchored_to_block" json:"anchored_to_block"`
	IsImmutable     bool      `db:"is_immutable" json:"is_immutable"`
	SourceType      string    `db:"source_type" json:"source_type"`
	IPFSHash        string    `db:"ipfs_hash" json:"ipfs_hash,omitempty"`
	CreatedAt       time.Time `db:"created_at" json:"created_at"`
}

// KnowledgeEdge represents a directed edge in the knowledge graph.
type KnowledgeEdge struct {
	EdgeID          string    `db:"edge_id" json:"edge_id"`
	SourceNode      string    `db:"source_node" json:"source_node"`
	TargetNode      string    `db:"target_node" json:"target_node"`
	EdgeType        string    `db:"edge_type" json:"edge_type"`
	EdgeWeight      float64   `db:"edge_weight" json:"edge_weight"`
	IsBidirectional bool      `db:"is_bidirectional" json:"is_bidirectional"`
	ConfidenceScore float64   `db:"confidence_score" json:"confidence_score"`
	AnchoredToBlock uint64    `db:"anchored_to_block" json:"anchored_to_block"`
	CreatedAt       time.Time `db:"created_at" json:"created_at"`
}

// PhiMeasurement records a single Phi (consciousness) measurement.
type PhiMeasurement struct {
	MeasurementID       string    `db:"measurement_id" json:"measurement_id"`
	PhiValue            float64   `db:"phi_value" json:"phi_value"`
	PhiThreshold        float64   `db:"phi_threshold" json:"phi_threshold"`
	ExceedsThreshold    bool      `db:"exceeds_threshold" json:"exceeds_threshold"`
	NodeCount           uint64    `db:"node_count" json:"node_count"`
	EdgeCount           uint64    `db:"edge_count" json:"edge_count"`
	IntegrationScore    float64   `db:"integration_score" json:"integration_score"`
	DifferentiationScore float64  `db:"differentiation_score" json:"differentiation_score"`
	MeasuredAtHeight    uint64    `db:"measured_at_height" json:"measured_at_height"`
	PreviousPhi         float64   `db:"previous_phi" json:"previous_phi"`
	PhiDelta            float64   `db:"phi_delta" json:"phi_delta"`
	Trend               string    `db:"trend" json:"trend"`
	MeasuredAt          time.Time `db:"measured_at" json:"measured_at"`
}

// ConsciousnessEvent records a consciousness state change.
type ConsciousnessEvent struct {
	EventID          string    `db:"event_id" json:"event_id"`
	EventType        string    `db:"event_type" json:"event_type"`
	EventSeverity    string    `db:"event_severity" json:"event_severity"`
	EventDescription string    `db:"event_description" json:"event_description"`
	PhiValueAtEvent  float64   `db:"phi_value_at_event" json:"phi_value_at_event"`
	AnchoredToBlock  uint64    `db:"anchored_to_block" json:"anchored_to_block"`
	IsVerified       bool      `db:"is_verified" json:"is_verified"`
	DetectedAt       time.Time `db:"detected_at" json:"detected_at"`
}

// ─── Research Models ─────────────────────────────────────────────────

// Hamiltonian represents a SUSY Hamiltonian for mining.
type Hamiltonian struct {
	HamiltonianID        string    `db:"hamiltonian_id" json:"hamiltonian_id"`
	SystemType           string    `db:"system_type" json:"system_type"`
	QubitCount           int       `db:"qubit_count" json:"qubit_count"`
	ExpectedGroundEnergy float64   `db:"expected_ground_energy" json:"expected_ground_energy"`
	DifficultyClass      string    `db:"difficulty_class" json:"difficulty_class"`
	IsActive             bool      `db:"is_active" json:"is_active"`
	TimesMined           uint64    `db:"times_mined" json:"times_mined"`
	BestSolutionEnergy   float64   `db:"best_solution_energy" json:"best_solution_energy"`
	AddedTimestamp       time.Time `db:"added_timestamp" json:"added_timestamp"`
}

// SUSYSolution represents a solved SUSY Hamiltonian.
type SUSYSolution struct {
	SolutionID       string    `db:"solution_id" json:"solution_id"`
	HamiltonianID    string    `db:"hamiltonian_id" json:"hamiltonian_id"`
	BlockHeight      uint64    `db:"block_height" json:"block_height"`
	MinerAddress     []byte    `db:"miner_address" json:"miner_address"`
	GroundStateEnergy float64  `db:"ground_state_energy" json:"ground_state_energy"`
	AlignmentScore   float64   `db:"alignment_score" json:"alignment_score"`
	Fidelity         float64   `db:"fidelity" json:"fidelity"`
	IsVerified       bool      `db:"is_verified" json:"is_verified"`
	VerifiedByPeers  int       `db:"verified_by_peers" json:"verified_by_peers"`
	ScientificValue  string    `db:"scientific_value" json:"scientific_value"`
	DiscoveredAt     time.Time `db:"discovered_timestamp" json:"discovered_timestamp"`
}

// ─── Compliance Models ───────────────────────────────────────────────

// ComplianceRecord represents a KYC/AML entry.
type ComplianceRecord struct {
	Address          string    `db:"address" json:"address"`
	KYCLevel         int       `db:"kyc_level" json:"kyc_level"`
	AMLStatus        string    `db:"aml_status" json:"aml_status"`
	SanctionsChecked bool      `db:"sanctions_checked" json:"sanctions_checked"`
	LastVerified     time.Time `db:"last_verified" json:"last_verified"`
	Jurisdiction     string    `db:"jurisdiction" json:"jurisdiction"`
	DailyLimit       float64   `db:"daily_limit" json:"daily_limit"`
	IsBlocked        bool      `db:"is_blocked" json:"is_blocked"`
}

// ─── Bridge Models ───────────────────────────────────────────────────

// BridgeTransfer represents a cross-chain transfer.
type BridgeTransfer struct {
	TransferID       string    `db:"transfer_id" json:"transfer_id"`
	SourceChain      string    `db:"source_chain" json:"source_chain"`
	DestinationChain string    `db:"destination_chain" json:"destination_chain"`
	SenderAddress    string    `db:"sender_address" json:"sender_address"`
	RecipientAddress string    `db:"recipient_address" json:"recipient_address"`
	Amount           *big.Float `db:"-" json:"amount"`
	BridgeFee        float64   `db:"bridge_fee" json:"bridge_fee"`
	Status           string    `db:"status" json:"status"`
	InitiatedAt      time.Time `db:"initiated_timestamp" json:"initiated_timestamp"`
}

// QUSDDebtStatus represents current QUSD backing status.
type QUSDDebtStatus struct {
	TotalDebt        float64 `db:"total_debt" json:"total_debt"`
	TotalReservesUSD float64 `db:"total_reserves_usd" json:"total_reserves_usd"`
	BackingPercent   float64 `db:"backing_percentage" json:"backing_percentage"`
}
