#!/bin/bash
set -e

CERT_DIR="/home/ash/qubitcoin/certs/client"
HOST="cockroach-1:26257"
DB="qubitcoin"

echo "🚀 Deploying Qubitcoin Production Schema"
echo "========================================"

# Function to run SQL file
run_sql() {
    local file=$1
    echo "📝 Executing: $file"
    docker exec -i qbc-cockroachdb-1 ./cockroach sql \
        --certs-dir=/certs \
        --host=$HOST \
        --database=$DB < "$file"
}

# Deploy in order
echo ""
echo "Step 1: Core QBC Blockchain"
run_sql "qbc/00_init_database.sql"
run_sql "qbc/01_blocks_transactions.sql"
run_sql "qbc/02_utxo_model.sql"
run_sql "qbc/03_addresses_balances.sql"
run_sql "qbc/04_chain_state.sql"
run_sql "qbc/05_mempool.sql"

echo ""
echo "Step 2: Quantum Research"
run_sql "research/00_hamiltonians.sql"
run_sql "research/01_vqe_circuits.sql"
run_sql "research/02_susy_solutions.sql"

echo ""
echo "Step 3: QVM Smart Contracts"
run_sql "qvm/00_contracts_core.sql"
run_sql "qvm/01_execution_engine.sql"
run_sql "qvm/02_state_storage.sql"
run_sql "qvm/03_gas_metering.sql"

echo ""
echo "Step 4: AetherTree AGI"
run_sql "agi/00_knowledge_graph.sql"
run_sql "agi/01_reasoning_engine.sql"
run_sql "agi/02_training_data.sql"
run_sql "agi/03_phi_metrics.sql"

echo ""
echo "Step 5: Multi-Chain Bridge"
run_sql "bridge/00_supported_chains.sql"
run_sql "bridge/01_bridge_transfers.sql"

echo ""
echo "Step 6: QUSD Stablecoin"
run_sql "stablecoin/00_qusd_config.sql"
run_sql "stablecoin/01_qusd_reserves.sql"

echo ""
echo "Step 7: Shared Components"
run_sql "shared/00_ipfs_storage.sql"
run_sql "shared/01_system_config.sql"

echo ""
echo "Step 8: Genesis Block"
run_sql "qbc/99_genesis_block.sql"

echo ""
echo "✅ Schema deployment complete!"
docker exec -it qbc-cockroachdb-1 ./cockroach sql \
    --certs-dir=/certs \
    --host=$HOST \
    --database=$DB \
    -e "SELECT version, component, applied_at FROM schema_version ORDER BY applied_at;"
