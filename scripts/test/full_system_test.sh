#!/usr/bin/env bash
# ============================================================================
# Qubitcoin Full System Test — Substrate Hybrid Mode
# Tests all endpoints, contract deployment, QUSD, Aether, mining, etc.
# ============================================================================
set -uo pipefail

RPC="${RPC:-http://127.0.0.1:5000}"
SUBSTRATE="${SUBSTRATE:-http://localhost:9944}"
TIMEOUT=15
TIMEOUT_SLOW=60
PASS=0
FAIL=0
SKIP=0
TOTAL=0

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

ok()   { ((PASS++)); ((TOTAL++)); echo -e "${GREEN}[PASS]${NC} $1"; }
fail() { ((FAIL++)); ((TOTAL++)); echo -e "${RED}[FAIL]${NC} $1: $2"; }
skip() { ((SKIP++)); ((TOTAL++)); echo -e "${YELLOW}[SKIP]${NC} $1: $2"; }
section() { echo -e "\n${CYAN}═══ $1 ═══${NC}"; }

# Helper: GET request, check for 200
test_get() {
    local name="$1" url="$2" expected="${3:-}" timeout="${4:-$TIMEOUT}"
    local resp
    resp=$(curl -sf --max-time "$timeout" "$RPC$url" 2>&1)
    local code=$?
    if [ $code -ne 0 ]; then
        fail "$name" "HTTP error (curl code $code)"
        return
    fi
    if [ -n "$expected" ]; then
        if echo "$resp" | grep -q "$expected"; then
            ok "$name"
        else
            fail "$name" "Missing: $expected"
        fi
    else
        ok "$name"
    fi
}

# Helper: POST request
test_post() {
    local name="$1" url="$2" data="$3" expected="${4:-}" timeout="${5:-$TIMEOUT}"
    local resp
    resp=$(curl -sf --max-time "$timeout" -X POST -H "Content-Type: application/json" -d "$data" "$RPC$url" 2>&1)
    local code=$?
    if [ $code -ne 0 ]; then
        fail "$name" "HTTP error (curl code $code)"
        return
    fi
    if [ -n "$expected" ]; then
        if echo "$resp" | grep -q "$expected"; then
            ok "$name"
        else
            fail "$name" "Missing: $expected"
        fi
    else
        ok "$name"
    fi
}

echo "============================================"
echo "  Qubitcoin Full System Test"
echo "  $(date)"
echo "  RPC: $RPC"
echo "  Substrate: $SUBSTRATE"
echo "============================================"

# ── 1. CORE HEALTH ──────────────────────────────────────────────────────
section "1. CORE HEALTH & NODE INFO"

test_get "Root endpoint" "/" "Qubitcoin"
test_get "Health check" "/health" "healthy"
test_get "Health — substrate_mode" "/health" "substrate_mode"
test_get "Health — substrate_connected" "/health" "substrate_connected"
test_get "Node info" "/info" "version"
test_get "Health subsystems" "/health/subsystems" "subsystems"

# ── 2. SUBSTRATE NODE ────────────────────────────────────────────────────
section "2. SUBSTRATE NODE"

SUB_HEALTH=$(curl -sf --max-time 5 -H 'Content-Type: application/json' \
    -d '{"id":1,"jsonrpc":"2.0","method":"system_health","params":[]}' \
    "$SUBSTRATE" 2>&1)
if echo "$SUB_HEALTH" | grep -q "isSyncing"; then
    ok "Substrate system_health"
else
    fail "Substrate system_health" "No response"
fi

SUB_CHAIN=$(curl -sf --max-time 5 -H 'Content-Type: application/json' \
    -d '{"id":1,"jsonrpc":"2.0","method":"system_chain","params":[]}' \
    "$SUBSTRATE" 2>&1)
if echo "$SUB_CHAIN" | grep -q "Qubitcoin"; then
    ok "Substrate chain = Qubitcoin"
else
    fail "Substrate chain" "Expected 'Qubitcoin'"
fi

SUB_BLOCK=$(curl -sf --max-time 5 -H 'Content-Type: application/json' \
    -d '{"id":1,"jsonrpc":"2.0","method":"chain_getFinalizedHead","params":[]}' \
    "$SUBSTRATE" 2>&1)
if echo "$SUB_BLOCK" | grep -q "0x"; then
    ok "Substrate finalized head"
else
    fail "Substrate finalized head" "No hash returned"
fi

# ── 3. CHAIN INFO ────────────────────────────────────────────────────────
section "3. CHAIN INFO & BLOCKS"

test_get "Chain info" "/chain/info" "height"
test_get "Chain tip" "/chain/tip" "height"
test_get "Block 0 (genesis)" "/block/0" "height"
test_get "Block 1" "/block/1" "height"

# Get current height
HEIGHT=$(curl -sf --max-time 5 "$RPC/chain/info" 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin).get('height',0))" 2>/dev/null || echo "0")
echo "  Current height: $HEIGHT"

# ── 4. BALANCE & UTXO ───────────────────────────────────────────────────
section "4. BALANCE & UTXO"

NODE_ADDR=$(curl -sf --max-time 5 "$RPC/" 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin).get('address',''))" 2>/dev/null || echo "")
if [ -n "$NODE_ADDR" ]; then
    test_get "Balance ($NODE_ADDR)" "/balance/$NODE_ADDR" ""
    test_get "UTXOs ($NODE_ADDR)" "/utxos/$NODE_ADDR" ""
else
    skip "Balance" "No address"
    skip "UTXOs" "No address"
fi

# ── 5. MINING ────────────────────────────────────────────────────────────
section "5. MINING"

test_get "Mining stats" "/mining/stats" "is_mining"

# ── 6. MEMPOOL ───────────────────────────────────────────────────────────
section "6. MEMPOOL"

test_get "Mempool" "/mempool" ""

# ── 7. AETHER TREE ──────────────────────────────────────────────────────
section "7. AETHER TREE (AGI)"

# Aether endpoints are compute-heavy — use longer timeout
test_get "Aether info" "/aether/info" "knowledge_graph" "$TIMEOUT_SLOW"
test_get "Aether Phi" "/aether/phi" "phi_value" "$TIMEOUT_SLOW"
test_get "Aether Phi history" "/aether/phi/history" "history" "$TIMEOUT_SLOW"
test_get "Aether knowledge" "/aether/knowledge" "" "$TIMEOUT_SLOW"
test_get "Aether reasoning stats" "/aether/reasoning/stats" ""
test_get "Aether consciousness" "/aether/consciousness" "phi" "$TIMEOUT_SLOW"
test_get "Aether sephirot" "/aether/sephirot" ""

# Chat test — create session first, then send message
SESSION_RESP=$(curl -sf --max-time 10 -X POST -H "Content-Type: application/json" \
    -d '{"user_address":"test_user_001"}' "$RPC/aether/chat/session" 2>&1)
CHAT_SESSION=$(echo "$SESSION_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('session_id',''))" 2>/dev/null || echo "")
if [ -n "$CHAT_SESSION" ]; then
    ok "Aether create session"
    test_post "Aether chat" "/aether/chat/message" "{\"message\":\"What is Qubitcoin?\",\"session_id\":\"$CHAT_SESSION\"}" "response"
else
    fail "Aether create session" "No session_id returned"
    skip "Aether chat" "No session"
fi

# ── 8. QVM ───────────────────────────────────────────────────────────────
section "8. QVM (Quantum Virtual Machine)"

test_get "QVM info" "/qvm/info" ""

# ── 9. ECONOMICS ─────────────────────────────────────────────────────────
section "9. ECONOMICS"

test_get "Emission schedule" "/economics/emission" "current_reward"
test_get "Emission simulate" "/economics/simulate" ""

# ── 10. STABLECOIN (QUSD) ───────────────────────────────────────────────
section "10. QUSD STABLECOIN"

test_get "QUSD health" "/qusd/health" ""
test_get "QUSD vaults at risk" "/qusd/vaults/at-risk" ""

# ── 11. CONTRACT DEPLOYMENT ─────────────────────────────────────────────
section "11. SMART CONTRACT DEPLOYMENT"

# Deploy a test QBC-20 token (contract_type, contract_code dict, deployer)
DEPLOY_RESP=$(curl -sf --max-time 30 -X POST -H "Content-Type: application/json" \
    -d '{"contract_type":"token","contract_code":{"name":"Test Token","symbol":"TST","total_supply":"1000000"},"deployer":"00b5a241577d63bae49073e924f53678f86b4111"}' \
    "$RPC/contracts/deploy" 2>&1)
DEPLOY_CODE=$?
if [ $DEPLOY_CODE -eq 0 ] && echo "$DEPLOY_RESP" | grep -q "success\|contract_id"; then
    ok "Deploy QBC-20 token"
    CONTRACT_ID=$(echo "$DEPLOY_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('contract_id',''))" 2>/dev/null || echo "")
    echo "  Contract: $CONTRACT_ID"
else
    fail "Deploy QBC-20 token" "Response: $(echo $DEPLOY_RESP | head -c 200)"
fi

# Deploy NFT
DEPLOY_NFT=$(curl -sf --max-time 30 -X POST -H "Content-Type: application/json" \
    -d '{"contract_type":"nft","contract_code":{"name":"Test NFT","symbol":"TNFT"},"deployer":"00b5a241577d63bae49073e924f53678f86b4111"}' \
    "$RPC/contracts/deploy" 2>&1)
if [ $? -eq 0 ] && echo "$DEPLOY_NFT" | grep -q "success\|contract_id"; then
    ok "Deploy QBC-721 NFT"
else
    fail "Deploy QBC-721 NFT" "$(echo $DEPLOY_NFT | head -c 200)"
fi

# List contracts
test_get "List contracts" "/contracts" ""

# ── 12. HIGGS COGNITIVE FIELD ────────────────────────────────────────────
section "12. HIGGS COGNITIVE FIELD"

test_get "Higgs status" "/higgs/status" ""
test_get "Higgs masses" "/higgs/masses" ""
test_get "Higgs excitations" "/higgs/excitations" ""
test_get "Higgs potential" "/higgs/potential" ""

# ── 13. SUSY DATABASE ───────────────────────────────────────────────────
section "13. SUSY SOLUTION DATABASE"

test_get "SUSY database" "/susy-database" ""

# ── 14. COMPLIANCE ──────────────────────────────────────────────────────
section "14. COMPLIANCE"

test_get "Compliance policies" "/qvm/compliance/policies" ""
test_get "Circuit breaker" "/qvm/compliance/circuit-breaker" ""

# ── 15. DATABASE ─────────────────────────────────────────────────────────
section "15. DATABASE"

test_get "DB pool health" "/db/pool/health" ""
test_get "DB pool stats" "/db/pool/stats" ""

# ── 16. PROMETHEUS METRICS ──────────────────────────────────────────────
section "16. METRICS"

if curl -sf --max-time 10 "$RPC/metrics" 2>/dev/null | grep -qE "qbc_blocks_mined_total|qbc_blockchain_height"; then
    ok "Prometheus metrics"
else
    fail "Prometheus metrics" "No metrics found"
fi

# ── 17. JSON-RPC (ETH COMPAT) ──────────────────────────────────────────
section "17. JSON-RPC (MetaMask Compatible)"

test_post "eth_chainId" "/jsonrpc" '{"jsonrpc":"2.0","id":1,"method":"eth_chainId","params":[]}' "0xce5"
test_post "eth_blockNumber" "/jsonrpc" '{"jsonrpc":"2.0","id":1,"method":"eth_blockNumber","params":[]}' "result"
test_post "net_version" "/jsonrpc" '{"jsonrpc":"2.0","id":1,"method":"net_version","params":[]}' "3301"
test_post "web3_clientVersion" "/jsonrpc" '{"jsonrpc":"2.0","id":1,"method":"web3_clientVersion","params":[]}' "Qubitcoin"

# ── SUMMARY ──────────────────────────────────────────────────────────────
echo ""
echo "============================================"
echo "  SYSTEM TEST RESULTS"
echo "============================================"
echo -e "  ${GREEN}PASS: $PASS${NC}"
echo -e "  ${RED}FAIL: $FAIL${NC}"
echo -e "  ${YELLOW}SKIP: $SKIP${NC}"
echo "  TOTAL: $TOTAL"
echo ""
RATE=$(python3 -c "print(f'{$PASS/$TOTAL*100:.1f}%')" 2>/dev/null || echo "N/A")
echo "  Pass Rate: $RATE"
echo "============================================"

exit $FAIL
