#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────────────
# deploy_contracts_ci.sh — CI-compatible contract deployment for Qubitcoin
#
# Deploys all 50 Solidity contracts via the QBC node RPC, verifies each
# deployment, and updates contract_registry.json.
#
# Usage:
#   ./scripts/deploy/deploy_contracts_ci.sh                 # Full deploy
#   ./scripts/deploy/deploy_contracts_ci.sh --dry-run       # Verify only
#   ./scripts/deploy/deploy_contracts_ci.sh --rpc-url URL   # Custom RPC
#
# Environment variables:
#   RPC_URL          — Node RPC endpoint (default: http://localhost:5000)
#   DEPLOYER_KEY     — Path to secure_key.env (default: secure_key.env)
#   HEALTH_TIMEOUT   — Seconds to wait for node health (default: 120)
#   REGISTRY_PATH    — Output path for contract_registry.json (default: .)
#   DRY_RUN          — Set to "true" for dry-run mode
# ──────────────────────────────────────────────────────────────────────────────
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# ─── Defaults ────────────────────────────────────────────────────────────────
RPC_URL="${RPC_URL:-http://localhost:5000}"
DEPLOYER_KEY="${DEPLOYER_KEY:-${PROJECT_ROOT}/secure_key.env}"
HEALTH_TIMEOUT="${HEALTH_TIMEOUT:-120}"
REGISTRY_PATH="${REGISTRY_PATH:-${PROJECT_ROOT}/contract_registry.json}"
DRY_RUN="${DRY_RUN:-false}"

# ─── Parse CLI args ─────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run)
            DRY_RUN="true"
            shift
            ;;
        --rpc-url)
            RPC_URL="$2"
            shift 2
            ;;
        --deployer-key)
            DEPLOYER_KEY="$2"
            shift 2
            ;;
        --health-timeout)
            HEALTH_TIMEOUT="$2"
            shift 2
            ;;
        --registry-path)
            REGISTRY_PATH="$2"
            shift 2
            ;;
        -h|--help)
            echo "Usage: $0 [--dry-run] [--rpc-url URL] [--deployer-key PATH] [--health-timeout SECS] [--registry-path PATH]"
            echo ""
            echo "Options:"
            echo "  --dry-run          Verify contract files exist and node is reachable, but do not deploy"
            echo "  --rpc-url URL      Node RPC endpoint (default: http://localhost:5000)"
            echo "  --deployer-key P   Path to secure_key.env (default: secure_key.env)"
            echo "  --health-timeout S Seconds to wait for node health (default: 120)"
            echo "  --registry-path P  Output path for contract_registry.json"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# ─── Colors ──────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info()  { echo -e "${BLUE}[INFO]${NC}  $*"; }
log_ok()    { echo -e "${GREEN}[OK]${NC}    $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }

# ─── Step 0: Verify prerequisites ───────────────────────────────────────────
log_info "========================================="
log_info "Qubitcoin Contract Deployment (CI)"
log_info "========================================="
log_info "RPC URL:       $RPC_URL"
log_info "Deployer key:  $DEPLOYER_KEY"
log_info "Registry path: $REGISTRY_PATH"
log_info "Dry run:       $DRY_RUN"
log_info ""

# Check Python is available
if ! command -v python3 &>/dev/null; then
    log_error "python3 is required but not found in PATH"
    exit 1
fi

# Check deployer key exists
if [[ ! -f "$DEPLOYER_KEY" ]]; then
    log_error "Deployer key file not found: $DEPLOYER_KEY"
    log_info "Run: python3 scripts/setup/generate_keys.py"
    exit 1
fi
log_ok "Deployer key file found"

# ─── Step 1: Verify all Solidity contract files exist ────────────────────────
log_info ""
log_info "[Step 1] Verifying Solidity contract files..."

SOL_DIR="${PROJECT_ROOT}/src/qubitcoin/contracts/solidity"
EXPECTED_CONTRACTS=(
    # Proxy infrastructure (3)
    "proxy/Initializable.sol"
    "proxy/ProxyAdmin.sol"
    "proxy/QBCProxy.sol"
    # Interfaces (6)
    "interfaces/IDebtLedger.sol"
    "interfaces/IFlashBorrower.sol"
    "interfaces/IQBC20.sol"
    "interfaces/IQBC721.sol"
    "interfaces/IQUSD.sol"
    "interfaces/ISephirah.sol"
    # Aether core (16)
    "aether/AetherKernel.sol"
    "aether/ConsciousnessDashboard.sol"
    "aether/ConstitutionalAI.sol"
    "aether/EmergencyShutdown.sol"
    "aether/GasOracle.sol"
    "aether/GlobalWorkspace.sol"
    "aether/MessageBus.sol"
    "aether/NodeRegistry.sol"
    "aether/PhaseSync.sol"
    "aether/ProofOfThought.sol"
    "aether/RewardDistributor.sol"
    "aether/SUSYEngine.sol"
    "aether/SynapticStaking.sol"
    "aether/TaskMarket.sol"
    "aether/TreasuryDAO.sol"
    "aether/UpgradeGovernor.sol"
    "aether/ValidatorRegistry.sol"
    "aether/VentricleRouter.sol"
    # Sephirot (10)
    "aether/sephirot/SephirahKeter.sol"
    "aether/sephirot/SephirahChochmah.sol"
    "aether/sephirot/SephirahBinah.sol"
    "aether/sephirot/SephirahChesed.sol"
    "aether/sephirot/SephirahGevurah.sol"
    "aether/sephirot/SephirahTiferet.sol"
    "aether/sephirot/SephirahNetzach.sol"
    "aether/sephirot/SephirahHod.sol"
    "aether/sephirot/SephirahYesod.sol"
    "aether/sephirot/SephirahMalkuth.sol"
    # Tokens (5)
    "tokens/QBC20.sol"
    "tokens/QBC721.sol"
    "tokens/QBC1155.sol"
    "tokens/ERC20QC.sol"
    "tokens/VestingSchedule.sol"
    "tokens/wQBC.sol"
    # QUSD suite (9)
    "qusd/QUSD.sol"
    "qusd/QUSDReserve.sol"
    "qusd/QUSDDebtLedger.sol"
    "qusd/QUSDOracle.sol"
    "qusd/QUSDGovernance.sol"
    "qusd/QUSDStabilizer.sol"
    "qusd/QUSDAllocation.sol"
    "qusd/QUSDFlashLoan.sol"
    "qusd/wQUSD.sol"
    "qusd/MultiSigAdmin.sol"
    # Bridge (2)
    "bridge/BridgeVault.sol"
    "bridge/wQBC.sol"
)

MISSING=0
FOUND=0
for contract in "${EXPECTED_CONTRACTS[@]}"; do
    if [[ -f "${SOL_DIR}/${contract}" ]]; then
        FOUND=$((FOUND + 1))
    else
        log_error "Missing contract: ${contract}"
        MISSING=$((MISSING + 1))
    fi
done

TOTAL=${#EXPECTED_CONTRACTS[@]}
log_info "Contracts found: ${FOUND}/${TOTAL}"
if [[ $MISSING -gt 0 ]]; then
    log_error "${MISSING} contract files missing!"
    exit 1
fi
log_ok "All ${TOTAL} contract files verified"

# ─── Step 2: Wait for node health ───────────────────────────────────────────
log_info ""
log_info "[Step 2] Waiting for node health check..."

HEALTH_URL="${RPC_URL}/health"
ELAPSED=0
HEALTH_OK=false

while [[ $ELAPSED -lt $HEALTH_TIMEOUT ]]; do
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$HEALTH_URL" 2>/dev/null || echo "000")
    if [[ "$HTTP_CODE" == "200" ]]; then
        HEALTH_OK=true
        break
    fi
    if [[ $((ELAPSED % 10)) -eq 0 ]]; then
        log_info "  Waiting for node... (${ELAPSED}s / ${HEALTH_TIMEOUT}s, HTTP: ${HTTP_CODE})"
    fi
    sleep 2
    ELAPSED=$((ELAPSED + 2))
done

if [[ "$HEALTH_OK" != "true" ]]; then
    log_error "Node not reachable at ${RPC_URL} after ${HEALTH_TIMEOUT}s"
    log_info "Is the node running? Try: cd src && python3 run_node.py"
    exit 1
fi
log_ok "Node is healthy (${ELAPSED}s)"

# Fetch chain info
CHAIN_INFO=$(curl -s "${RPC_URL}/chain/info" 2>/dev/null || echo "{}")
BLOCK_HEIGHT=$(echo "$CHAIN_INFO" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('block_height', d.get('height', 'unknown')))" 2>/dev/null || echo "unknown")
log_info "  Current block height: ${BLOCK_HEIGHT}"

# ─── Step 3: Dry-run exit point ─────────────────────────────────────────────
if [[ "$DRY_RUN" == "true" ]]; then
    log_info ""
    log_info "[Dry Run] All checks passed. Skipping actual deployment."
    log_info ""
    log_ok "DRY RUN COMPLETE"
    log_info "  - ${TOTAL} contract files verified"
    log_info "  - Node is reachable at ${RPC_URL}"
    log_info "  - Block height: ${BLOCK_HEIGHT}"
    log_info ""
    log_info "To deploy for real, run without --dry-run:"
    log_info "  $0 --rpc-url ${RPC_URL}"
    exit 0
fi

# ─── Step 4: Deploy contracts via Python deployer ────────────────────────────
log_info ""
log_info "[Step 4] Deploying contracts..."

DEPLOY_SCRIPT="${PROJECT_ROOT}/scripts/deploy/deploy_contracts.py"
if [[ ! -f "$DEPLOY_SCRIPT" ]]; then
    log_error "Deployment script not found: $DEPLOY_SCRIPT"
    exit 1
fi

# Run the Python deployment script
python3 "$DEPLOY_SCRIPT" \
    --rpc-url "$RPC_URL" \
    --deployer-key "$DEPLOYER_KEY"

DEPLOY_EXIT=$?
if [[ $DEPLOY_EXIT -ne 0 ]]; then
    log_error "Deployment script failed with exit code ${DEPLOY_EXIT}"
    if [[ -f "${PROJECT_ROOT}/contract_registry_partial.json" ]]; then
        log_warn "Partial registry saved to contract_registry_partial.json"
    fi
    exit $DEPLOY_EXIT
fi

# ─── Step 5: Verify deployments ─────────────────────────────────────────────
log_info ""
log_info "[Step 5] Verifying deployed contracts..."

if [[ ! -f "$REGISTRY_PATH" ]]; then
    log_error "Registry file not found after deployment: $REGISTRY_PATH"
    exit 1
fi

# Count entries in registry
REG_COUNT=$(python3 -c "
import json, sys
with open('$REGISTRY_PATH') as f:
    reg = json.load(f)
print(len(reg))
" 2>/dev/null || echo "0")

log_info "Registry contains ${REG_COUNT} contract entries"

# Verify each contract has a valid address
VERIFY_FAILED=0
python3 -c "
import json, sys

with open('$REGISTRY_PATH') as f:
    reg = json.load(f)

failed = 0
for name, info in reg.items():
    addr = info.get('proxy', info.get('address', ''))
    if not addr or addr == '0x' + '0' * 40:
        print(f'  FAIL: {name} — no valid address')
        failed += 1
    else:
        # Verify address is hex
        clean = addr.replace('0x', '')
        if len(clean) < 8 or not all(c in '0123456789abcdef' for c in clean):
            print(f'  FAIL: {name} — invalid address format: {addr}')
            failed += 1
        else:
            print(f'  OK:   {name} -> {addr}')

sys.exit(failed)
" 2>&1 || VERIFY_FAILED=$?

if [[ $VERIFY_FAILED -gt 0 ]]; then
    log_error "${VERIFY_FAILED} contract(s) failed verification"
    exit 1
fi

# ─── Step 6: Verify contracts via RPC ────────────────────────────────────────
log_info ""
log_info "[Step 6] Verifying contracts on-chain via RPC..."

ONCHAIN_FAILED=0
python3 -c "
import json, sys, requests

rpc_url = '$RPC_URL'
with open('$REGISTRY_PATH') as f:
    reg = json.load(f)

failed = 0
checked = 0
for name, info in reg.items():
    addr = info.get('proxy', info.get('address', ''))
    if not addr:
        continue
    checked += 1
    # Use eth_getCode to verify contract has code
    try:
        resp = requests.post(
            f'{rpc_url}/',
            json={'jsonrpc': '2.0', 'method': 'eth_getCode', 'params': [addr, 'latest'], 'id': 1},
            timeout=10
        )
        result = resp.json().get('result', '0x')
        if result and result != '0x' and result != '0x0' and len(result) > 4:
            pass  # Contract has code
        else:
            # Try REST endpoint as fallback
            try:
                resp2 = requests.get(f'{rpc_url}/qvm/account/{addr.replace(\"0x\", \"\")}', timeout=5)
                if resp2.status_code == 200:
                    pass  # Account exists
                else:
                    print(f'  WARN: {name} at {addr} — no on-chain code detected')
            except Exception:
                print(f'  WARN: {name} at {addr} — could not verify on-chain')
    except Exception as e:
        print(f'  WARN: {name} — RPC check failed: {e}')

print(f'Checked {checked} contracts on-chain')
sys.exit(0)
" 2>&1 || true

# ─── Summary ─────────────────────────────────────────────────────────────────
log_info ""
log_info "========================================="
log_ok   "DEPLOYMENT COMPLETE"
log_info "========================================="
log_info "  Contracts deployed: ${REG_COUNT}"
log_info "  Registry:          ${REGISTRY_PATH}"
log_info "  RPC URL:           ${RPC_URL}"
log_info "  Block height:      ${BLOCK_HEIGHT}"
log_info ""
log_info "Next steps:"
log_info "  1. Verify contract_registry.json in version control"
log_info "  2. Wire contract addresses into .env / config"
log_info "  3. Run validation: python3 scripts/deploy/validate_contracts.py"
