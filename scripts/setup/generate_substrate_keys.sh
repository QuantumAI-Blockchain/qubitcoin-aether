#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════
# Qubitcoin Substrate Validator Key Generation
# ═══════════════════════════════════════════════════════════════════════
#
# Generates sr25519 (Aura block authoring) + ed25519 (GRANDPA finality)
# keypairs for N validators using the `subkey` CLI tool.
#
# Usage:
#   ./generate_substrate_keys.sh [NUM_VALIDATORS]
#
# Default: 3 validators (mainnet default)
#
# Requirements:
#   - subkey CLI (install: cargo install subkey --locked)
#   - Or use Docker: docker run --rm parity/subkey:latest generate
#
# Output:
#   - keys/validator_N_aura.json     (sr25519 for Aura)
#   - keys/validator_N_grandpa.json  (ed25519 for GRANDPA)
#   - keys/chain_spec_authorities.json (ready for chain_spec injection)
#
# Security:
#   - Generated keys are written to keys/ directory
#   - keys/ is .gitignored — NEVER commit validator keys
#   - Back up keys securely before launch
# ═══════════════════════════════════════════════════════════════════════

set -euo pipefail

NUM_VALIDATORS=${1:-3}
KEYS_DIR="$(dirname "$0")/../../substrate-node/keys"
mkdir -p "$KEYS_DIR"

echo "═══════════════════════════════════════════════════════════════"
echo "  Qubitcoin Substrate Validator Key Generation"
echo "  Generating keys for $NUM_VALIDATORS validators"
echo "═══════════════════════════════════════════════════════════════"
echo ""

# Check for subkey
if ! command -v subkey &> /dev/null; then
    echo "ERROR: 'subkey' CLI not found."
    echo ""
    echo "Install via cargo:"
    echo "  cargo install subkey --locked"
    echo ""
    echo "Or use the Substrate node binary:"
    echo "  qbc-node key generate --scheme sr25519"
    exit 1
fi

AUTHORITIES_JSON="["

for i in $(seq 1 "$NUM_VALIDATORS"); do
    echo "─── Validator $i ───"

    # Generate Aura key (sr25519 for block authoring)
    AURA_OUTPUT=$(subkey generate --scheme sr25519 --output-type json 2>/dev/null)
    AURA_SECRET=$(echo "$AURA_OUTPUT" | jq -r '.secretPhrase')
    AURA_SEED=$(echo "$AURA_OUTPUT" | jq -r '.secretSeed')
    AURA_PUBLIC=$(echo "$AURA_OUTPUT" | jq -r '.publicKey')
    AURA_SS58=$(echo "$AURA_OUTPUT" | jq -r '.ss58Address')
    AURA_ACCOUNT=$(echo "$AURA_OUTPUT" | jq -r '.accountId')

    echo "$AURA_OUTPUT" > "$KEYS_DIR/validator_${i}_aura.json"
    echo "  Aura (sr25519):   $AURA_SS58"
    echo "  Public key:       $AURA_PUBLIC"

    # Generate GRANDPA key (ed25519 for finality)
    GRANDPA_OUTPUT=$(subkey generate --scheme ed25519 --output-type json 2>/dev/null)
    GRANDPA_SECRET=$(echo "$GRANDPA_OUTPUT" | jq -r '.secretPhrase')
    GRANDPA_PUBLIC=$(echo "$GRANDPA_OUTPUT" | jq -r '.publicKey')
    GRANDPA_SS58=$(echo "$GRANDPA_OUTPUT" | jq -r '.ss58Address')

    echo "$GRANDPA_OUTPUT" > "$KEYS_DIR/validator_${i}_grandpa.json"
    echo "  GRANDPA (ed25519): $GRANDPA_SS58"
    echo "  Public key:        $GRANDPA_PUBLIC"
    echo ""

    # Build JSON for chain_spec injection
    if [ "$i" -gt 1 ]; then
        AUTHORITIES_JSON+=","
    fi
    AUTHORITIES_JSON+=$(cat <<EOF
    {
        "validator": $i,
        "aura": {
            "scheme": "sr25519",
            "public_key": "$AURA_PUBLIC",
            "ss58_address": "$AURA_SS58",
            "account_id": "$AURA_ACCOUNT"
        },
        "grandpa": {
            "scheme": "ed25519",
            "public_key": "$GRANDPA_PUBLIC",
            "ss58_address": "$GRANDPA_SS58"
        }
    }
EOF
)
done

AUTHORITIES_JSON+="]"

# Write chain_spec-ready JSON
echo "$AUTHORITIES_JSON" | jq '.' > "$KEYS_DIR/chain_spec_authorities.json"

echo "═══════════════════════════════════════════════════════════════"
echo "  Keys generated successfully!"
echo ""
echo "  Output directory: $KEYS_DIR"
echo "  Files:"
for i in $(seq 1 "$NUM_VALIDATORS"); do
    echo "    - validator_${i}_aura.json    (sr25519)"
    echo "    - validator_${i}_grandpa.json  (ed25519)"
done
echo "    - chain_spec_authorities.json (for chain_spec injection)"
echo ""
echo "  SECURITY REMINDER:"
echo "    - Back up these keys securely (encrypted USB, hardware wallet)"
echo "    - NEVER commit keys/ to git"
echo "    - Each validator needs its own key pair"
echo ""
echo "  Next steps:"
echo "    1. Insert keys into each validator node:"
echo "       qbc-node key insert --chain mainnet \\"
echo "         --scheme sr25519 --key-type aura \\"
echo "         --suri '<aura_secret_phrase>'"
echo "       qbc-node key insert --chain mainnet \\"
echo "         --scheme ed25519 --key-type gran \\"
echo "         --suri '<grandpa_secret_phrase>'"
echo "    2. Build chain spec: qbc-node build-spec --chain mainnet > mainnet.json"
echo "    3. Start validators: qbc-node --chain mainnet.json --validator"
echo "═══════════════════════════════════════════════════════════════"
