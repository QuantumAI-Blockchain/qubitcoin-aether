#!/usr/bin/env bash
# ============================================================================
# Qubitcoin Substrate Genesis Initialization
#
# Run AFTER docker compose -f docker-compose.substrate.yml up -d
# Verifies all services are healthy and performs post-genesis setup.
#
# Usage:
#   bash scripts/setup/substrate_genesis_init.sh
# ============================================================================

set -euo pipefail

SUBSTRATE_RPC="${SUBSTRATE_RPC:-http://localhost:9944}"
PYTHON_RPC="${PYTHON_RPC:-http://localhost:5000}"
MAX_WAIT=120  # seconds

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

ok()   { echo -e "${GREEN}[OK]${NC} $1"; }
fail() { echo -e "${RED}[FAIL]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
info() { echo -e "     $1"; }

echo "============================================"
echo "  Qubitcoin Substrate Genesis Initialization"
echo "============================================"
echo ""

# ── 1. Wait for Substrate node ────────────────────────────────────────
echo "Step 1: Waiting for Substrate node..."
elapsed=0
while [ $elapsed -lt $MAX_WAIT ]; do
    if curl -sf -H 'Content-Type: application/json' \
        -d '{"id":1,"jsonrpc":"2.0","method":"system_health","params":[]}' \
        "$SUBSTRATE_RPC" > /dev/null 2>&1; then
        ok "Substrate node is healthy at $SUBSTRATE_RPC"
        break
    fi
    sleep 2
    elapsed=$((elapsed + 2))
done
if [ $elapsed -ge $MAX_WAIT ]; then
    fail "Substrate node not reachable after ${MAX_WAIT}s"
    exit 1
fi

# Get chain info
CHAIN_NAME=$(curl -sf -H 'Content-Type: application/json' \
    -d '{"id":1,"jsonrpc":"2.0","method":"system_chain","params":[]}' \
    "$SUBSTRATE_RPC" | python3 -c "import sys,json; print(json.load(sys.stdin)['result'])" 2>/dev/null || echo "unknown")
VERSION=$(curl -sf -H 'Content-Type: application/json' \
    -d '{"id":1,"jsonrpc":"2.0","method":"system_version","params":[]}' \
    "$SUBSTRATE_RPC" | python3 -c "import sys,json; print(json.load(sys.stdin)['result'])" 2>/dev/null || echo "unknown")
info "Chain: $CHAIN_NAME, Version: $VERSION"

# ── 2. Wait for Python execution service ──────────────────────────────
echo ""
echo "Step 2: Waiting for Python execution service..."
elapsed=0
while [ $elapsed -lt $MAX_WAIT ]; do
    if curl -sf "$PYTHON_RPC/health" > /dev/null 2>&1; then
        ok "Python execution service is healthy at $PYTHON_RPC"
        break
    fi
    sleep 3
    elapsed=$((elapsed + 3))
done
if [ $elapsed -ge $MAX_WAIT ]; then
    fail "Python execution service not reachable after ${MAX_WAIT}s"
    exit 1
fi

# ── 3. Verify Substrate is producing blocks ───────────────────────────
echo ""
echo "Step 3: Verifying block production..."
BEST_HASH=$(curl -sf -H 'Content-Type: application/json' \
    -d '{"id":1,"jsonrpc":"2.0","method":"chain_getFinalizedHead","params":[]}' \
    "$SUBSTRATE_RPC" | python3 -c "import sys,json; print(json.load(sys.stdin)['result'])" 2>/dev/null || echo "0x")
BEST_HEADER=$(curl -sf -H 'Content-Type: application/json' \
    -d "{\"id\":1,\"jsonrpc\":\"2.0\",\"method\":\"chain_getHeader\",\"params\":[\"$BEST_HASH\"]}" \
    "$SUBSTRATE_RPC" 2>/dev/null || echo '{}')
BLOCK_NUM=$(echo "$BEST_HEADER" | python3 -c "import sys,json; print(int(json.load(sys.stdin).get('result',{}).get('number','0x0'),16))" 2>/dev/null || echo "0")
if [ "$BLOCK_NUM" -gt 0 ]; then
    ok "Substrate producing blocks (finalized: #$BLOCK_NUM)"
else
    warn "Substrate at block 0 — blocks may not be producing yet"
    info "Waiting 10s for first blocks..."
    sleep 10
    BEST_HASH=$(curl -sf -H 'Content-Type: application/json' \
        -d '{"id":1,"jsonrpc":"2.0","method":"chain_getFinalizedHead","params":[]}' \
        "$SUBSTRATE_RPC" | python3 -c "import sys,json; print(json.load(sys.stdin)['result'])" 2>/dev/null || echo "0x")
    BEST_HEADER=$(curl -sf -H 'Content-Type: application/json' \
        -d "{\"id\":1,\"jsonrpc\":\"2.0\",\"method\":\"chain_getHeader\",\"params\":[\"$BEST_HASH\"]}" \
        "$SUBSTRATE_RPC" 2>/dev/null || echo '{}')
    BLOCK_NUM=$(echo "$BEST_HEADER" | python3 -c "import sys,json; print(int(json.load(sys.stdin).get('result',{}).get('number','0x0'),16))" 2>/dev/null || echo "0")
    if [ "$BLOCK_NUM" -gt 0 ]; then
        ok "Substrate producing blocks (finalized: #$BLOCK_NUM)"
    else
        warn "Still at block 0 — check Substrate logs"
    fi
fi

# ── 4. Verify Python is processing blocks ─────────────────────────────
echo ""
echo "Step 4: Checking Python block processing..."
CHAIN_INFO=$(curl -sf "$PYTHON_RPC/chain/info" 2>/dev/null || echo '{}')
PY_HEIGHT=$(echo "$CHAIN_INFO" | python3 -c "import sys,json; print(json.load(sys.stdin).get('height', -1))" 2>/dev/null || echo "-1")
SUB_MODE=$(echo "$CHAIN_INFO" | python3 -c "import sys,json; print(json.load(sys.stdin).get('substrate_mode', False))" 2>/dev/null || echo "False")
if [ "$SUB_MODE" = "True" ]; then
    ok "Python running in SUBSTRATE_MODE"
else
    warn "Python NOT in SUBSTRATE_MODE (substrate_mode=$SUB_MODE)"
fi
info "Python chain height: $PY_HEIGHT"

# ── 5. Verify Aether Tree ─────────────────────────────────────────────
echo ""
echo "Step 5: Checking Aether Tree..."
AETHER_INFO=$(curl -sf "$PYTHON_RPC/aether/info" 2>/dev/null || echo '{}')
PHI=$(echo "$AETHER_INFO" | python3 -c "import sys,json; print(json.load(sys.stdin).get('phi', 'N/A'))" 2>/dev/null || echo "N/A")
KG_NODES=$(echo "$AETHER_INFO" | python3 -c "import sys,json; print(json.load(sys.stdin).get('knowledge_nodes', 0))" 2>/dev/null || echo "0")
if [ "$KG_NODES" -gt 0 ] 2>/dev/null; then
    ok "Aether Tree active: Phi=$PHI, KnowledgeNodes=$KG_NODES"
else
    warn "Aether Tree: Phi=$PHI, KnowledgeNodes=$KG_NODES (may need blocks to seed)"
fi

# ── 6. Check CockroachDB ──────────────────────────────────────────────
echo ""
echo "Step 6: Checking CockroachDB..."
if curl -sf "http://localhost:8080/health?ready=1" > /dev/null 2>&1; then
    ok "CockroachDB healthy"
else
    warn "CockroachDB health check failed (may be internal-only in Docker)"
fi

# ── 7. Health summary ─────────────────────────────────────────────────
echo ""
echo "Step 7: Full health check..."
HEALTH=$(curl -sf "$PYTHON_RPC/health" 2>/dev/null || echo '{}')
echo "$HEALTH" | python3 -c "
import sys, json
h = json.load(sys.stdin)
for k, v in sorted(h.items()):
    status = '${GREEN}OK${NC}' if v else '${RED}--${NC}'
    print(f'  {status}  {k}: {v}')
" 2>/dev/null || echo "  (Could not parse health response)"

# ── Summary ───────────────────────────────────────────────────────────
echo ""
echo "============================================"
echo "  Genesis Initialization Complete"
echo "============================================"
echo ""
echo "  Substrate Node:    $SUBSTRATE_RPC"
echo "  Python RPC:        $PYTHON_RPC"
echo "  CockroachDB:       http://localhost:8080"
echo "  Frontend:          cd frontend && pnpm dev"
echo ""
echo "  Next steps:"
echo "    1. Start frontend: cd frontend && pnpm dev"
echo "    2. Open http://localhost:3000"
echo "    3. Monitor: docker compose -f docker-compose.substrate.yml logs -f"
echo ""
