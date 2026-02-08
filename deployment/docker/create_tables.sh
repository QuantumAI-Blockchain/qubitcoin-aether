#!/bin/bash
set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$PROJECT_ROOT"

echo "════════════════════════════════════════════════════════════"
echo "  STEP 2: CREATE DATABASE TABLES"
echo "  Creating 33 tables from 9 SQL schema files"
echo "════════════════════════════════════════════════════════════"
echo ""

# Create all schemas
for sql_file in sql/*.sql; do
    if [ -f "$sql_file" ]; then
        filename=$(basename "$sql_file")
        echo "[$filename]"
        
        docker run --rm --network docker_qbc-network \
          -v "$PROJECT_ROOT/certs/client:/certs:ro" \
          -v "$PROJECT_ROOT/sql:/sql:ro" \
          cockroachdb/cockroach:v24.2.0 sql \
          --certs-dir=/certs \
          --host=cockroach-1:26257 \
          --database=qubitcoin \
          --file="/sql/$filename"
        
        echo "  ✓ Complete"
        echo ""
    fi
done

# Count tables
echo "Counting tables..."
TABLE_COUNT=$(docker run --rm --network docker_qbc-network \
  -v "$PROJECT_ROOT/certs/client:/certs:ro" \
  cockroachdb/cockroach:v24.2.0 sql \
  --certs-dir=/certs \
  --host=cockroach-1:26257 \
  --database=qubitcoin \
  --execute="SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public';" \
  --format=tsv | tail -1)

echo ""
echo "════════════════════════════════════════════════════════════"
echo "  ✅ DATABASE COMPLETE"
echo "════════════════════════════════════════════════════════════"
echo ""
echo "Tables Created: $TABLE_COUNT"
echo ""
echo "Schema Breakdown:"
echo "  • 00_init_database.sql        - Database + schema_version"
echo "  • 01_core_blockchain.sql      - UTXO model (7 tables)"
echo "  • 02_privacy_susy_swaps.sql   - Confidential transactions"
echo "  • 03_smart_contracts_qvm.sql  - Smart contract engine"
echo "  • 04_multi_chain_bridge.sql   - 8 blockchain bridges"
echo "  • 05_qusd_stablecoin.sql      - QUSD stablecoin"
echo "  • 06_quantum_research.sql     - Hamiltonians, VQE, SUSY"
echo "  • 07_ipfs_storage.sql         - IPFS integration"
echo "  • 08_system_configuration.sql - Economics, network params"
echo "  • 09_genesis_block.sql        - Genesis block initialization"
echo ""
echo "Login to Web UI to explore: https://localhost:8080"
echo "Username: root"
echo "Password: qubitcoin2026"
echo ""
