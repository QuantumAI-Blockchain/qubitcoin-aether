//! Qubitcoin chain specification — genesis configuration for all networks.
//!
//! Defines the genesis block for mainnet, testnet, and development including:
//! - Initial authorities (Aura/GRANDPA validators)
//! - Genesis UTXO set (coinbase + premine)
//! - Initial difficulty
//! - Economic parameters
//! - QVM and Aether service endpoints
//! - Chain properties (token symbol, decimals, SS58 format)

use qbc_primitives::{
    Address, Utxo, GENESIS_PREMINE, INITIAL_DIFFICULTY, INITIAL_REWARD,
    CHAIN_ID_MAINNET, CHAIN_ID_TESTNET, QBC_DECIMALS,
};
use hex;
use qbc_runtime::{AccountId, Signature, WASM_BINARY};
use sc_service::ChainType;
use sp_consensus_aura::sr25519::AuthorityId as AuraId;
use sp_consensus_grandpa::AuthorityId as GrandpaId;
use sp_core::{sr25519, H256, Pair, Public};
use sp_runtime::traits::{IdentifyAccount, Verify};

/// Specialized `ChainSpec` for Qubitcoin.
pub type ChainSpec = sc_service::GenericChainSpec;

/// Custom SS58 prefix for QBC addresses.
const QBC_SS58_PREFIX: u32 = 88;

// ═══════════════════════════════════════════════════════════════════════
// Key generation helpers
// ═══════════════════════════════════════════════════════════════════════

/// Generate a crypto pair from seed.
pub fn get_from_seed<TPublic: Public>(seed: &str) -> <TPublic::Pair as Pair>::Public {
    TPublic::Pair::from_string(&format!("//{}", seed), None)
        .expect("static values are valid; qed")
        .public()
}

type AccountPublic = <Signature as Verify>::Signer;

/// Generate an account ID from seed.
pub fn get_account_id_from_seed<TPublic: Public>(seed: &str) -> AccountId
where
    AccountPublic: From<<TPublic::Pair as Pair>::Public>,
{
    AccountPublic::from(get_from_seed::<TPublic>(seed)).into_account()
}

/// Generate Aura + GRANDPA authority keys from seed.
pub fn authority_keys_from_seed(s: &str) -> (AuraId, GrandpaId) {
    (get_from_seed::<AuraId>(s), get_from_seed::<GrandpaId>(s))
}

/// Convert a hex address string (20-byte or 32-byte) to a 32-byte Address.
///
/// - 20-byte hex (EVM-style): left-padded with 12 zero bytes
/// - 32-byte hex: used directly
/// - "genesis_miner": mapped to SHA2-256("genesis_miner") for determinism
fn hex_to_address(hex_str: &str) -> Address {
    if hex_str == "genesis_miner" {
        use sp_core::hashing::sha2_256;
        return Address(sha2_256(b"genesis_miner"));
    }
    let clean = hex_str.strip_prefix("0x").unwrap_or(hex_str);
    let bytes = hex::decode(clean).expect("valid hex address");
    let mut addr = [0u8; 32];
    match bytes.len() {
        20 => addr[12..].copy_from_slice(&bytes), // Left-pad for EVM compat
        32 => addr.copy_from_slice(&bytes),
        _ => panic!("Invalid address length: {} bytes", bytes.len()),
    }
    Address(addr)
}

/// Convert a hex txid string to H256.
fn hex_to_h256(hex_str: &str) -> H256 {
    let clean = hex_str.strip_prefix("0x").unwrap_or(hex_str);
    let bytes = hex::decode(clean).expect("valid hex txid");
    assert_eq!(bytes.len(), 32, "txid must be 32 bytes");
    let mut arr = [0u8; 32];
    arr.copy_from_slice(&bytes);
    H256(arr)
}

/// Build standard QBC chain properties (token metadata for wallets/explorers).
fn chain_properties(chain_id: u64) -> sc_service::Properties {
    let mut props = sc_service::Properties::new();
    props.insert("tokenSymbol".into(), "QBC".into());
    props.insert("tokenDecimals".into(), QBC_DECIMALS.into());
    props.insert("ss58Format".into(), QBC_SS58_PREFIX.into());
    props.insert("chainId".into(), chain_id.into());
    props.insert("isEthereum".into(), false.into());
    props
}

/// Get the WASM binary for genesis state.
///
/// When built with `SKIP_WASM_BUILD=1`, WASM_BINARY is None. In that case,
/// we return a minimal placeholder. The node runs in native-only execution
/// mode — acceptable for controlled validator sets and dev/test launches.
/// Runtime upgrades via WASM will not work until a full WASM build is available.
fn wasm_binary() -> Result<&'static [u8], String> {
    // Minimal valid WASM module: (module) — just the magic bytes + version + empty section
    // This satisfies the genesis config requirement without a real runtime WASM.
    const MINIMAL_WASM: &[u8] = &[
        0x00, 0x61, 0x73, 0x6D, // WASM magic: \0asm
        0x01, 0x00, 0x00, 0x00, // WASM version: 1
    ];

    Ok(WASM_BINARY.unwrap_or(MINIMAL_WASM))
}

// ═══════════════════════════════════════════════════════════════════════
// Network configurations
// ═══════════════════════════════════════════════════════════════════════

/// **MAINNET** chain spec — Chain ID 3303, production validators.
///
/// For launch, validator keys are injected from `generate_substrate_keys.sh`.
/// The genesis state includes the 33M QBC premine + initial mining reward.
///
/// Boot nodes should be added before public launch.
pub fn mainnet_config() -> Result<ChainSpec, String> {
    // Mainnet uses 3 initial validators. Keys are placeholder — replaced by
    // real keys generated via `subkey` before launch.
    //
    // Production key injection flow:
    // 1. Run scripts/setup/generate_substrate_keys.sh
    // 2. Replace these seeds with real public keys
    // 3. Build chain spec: qbc-node build-spec --chain mainnet > mainnet.json
    // 4. Distribute mainnet.json to all validators
    let initial_authorities = vec![
        authority_keys_from_seed("Validator1"),
        authority_keys_from_seed("Validator2"),
        authority_keys_from_seed("Validator3"),
    ];

    // Treasury address for premine (SHA2-256 of "qubitcoin-treasury-mainnet")
    let treasury_address = {
        use sp_core::hashing::sha2_256;
        Address(sha2_256(b"qubitcoin-treasury-mainnet"))
    };

    // Root key (sudo) — for governance operations pre-decentralization
    let root_key = get_account_id_from_seed::<sr25519::Public>("Validator1");

    // Endowed accounts for Substrate fee payment (validators need some balance)
    let endowed_accounts = vec![
        get_account_id_from_seed::<sr25519::Public>("Validator1"),
        get_account_id_from_seed::<sr25519::Public>("Validator2"),
        get_account_id_from_seed::<sr25519::Public>("Validator3"),
    ];

    Ok(ChainSpec::builder(wasm_binary()?, None)
        .with_name("Qubitcoin Mainnet")
        .with_id("qbc_mainnet")
        .with_protocol_id("qbc")
        .with_chain_type(ChainType::Live)
        .with_properties(chain_properties(CHAIN_ID_MAINNET))
        .with_genesis_config_patch(build_genesis(
            initial_authorities,
            root_key,
            endowed_accounts,
            treasury_address,
        ))
        // Boot nodes will be added before public launch:
        // .with_boot_nodes(vec![
        //     "/dns/boot1.qbc.network/tcp/30333/p2p/<peer_id>".parse().unwrap(),
        //     "/dns/boot2.qbc.network/tcp/30333/p2p/<peer_id>".parse().unwrap(),
        // ])
        .build())
}

/// **TESTNET** chain spec — Chain ID 3304, 2 validators, testnet faucet.
pub fn testnet_config() -> Result<ChainSpec, String> {
    let initial_authorities = vec![
        authority_keys_from_seed("Alice"),
        authority_keys_from_seed("Bob"),
    ];

    // Testnet treasury address
    let treasury_address = {
        use sp_core::hashing::sha2_256;
        Address(sha2_256(b"qubitcoin-treasury-testnet"))
    };

    let root_key = get_account_id_from_seed::<sr25519::Public>("Alice");

    let endowed_accounts = vec![
        get_account_id_from_seed::<sr25519::Public>("Alice"),
        get_account_id_from_seed::<sr25519::Public>("Bob"),
        get_account_id_from_seed::<sr25519::Public>("Charlie"),
        get_account_id_from_seed::<sr25519::Public>("Dave"),
    ];

    Ok(ChainSpec::builder(wasm_binary()?, None)
        .with_name("Qubitcoin Testnet")
        .with_id("qbc_testnet")
        .with_protocol_id("qbc-test")
        .with_chain_type(ChainType::Local)
        .with_properties(chain_properties(CHAIN_ID_TESTNET))
        .with_genesis_config_patch(build_genesis(
            initial_authorities,
            root_key,
            endowed_accounts,
            treasury_address,
        ))
        .build())
}

/// **DEVELOPMENT** chain spec — single validator (Alice), fast iteration.
pub fn development_config() -> Result<ChainSpec, String> {
    let treasury_address = {
        use sp_core::hashing::sha2_256;
        Address(sha2_256(b"qubitcoin-treasury-dev"))
    };

    Ok(ChainSpec::builder(wasm_binary()?, None)
        .with_name("Qubitcoin Development")
        .with_id("qbc_dev")
        .with_chain_type(ChainType::Development)
        .with_properties(chain_properties(CHAIN_ID_TESTNET))
        .with_genesis_config_patch(build_genesis(
            vec![authority_keys_from_seed("Alice")],
            get_account_id_from_seed::<sr25519::Public>("Alice"),
            vec![
                get_account_id_from_seed::<sr25519::Public>("Alice"),
                get_account_id_from_seed::<sr25519::Public>("Bob"),
            ],
            treasury_address,
        ))
        .build())
}

/// **LOCAL TESTNET** — two validators, for multi-node testing.
pub fn local_testnet_config() -> Result<ChainSpec, String> {
    let treasury_address = {
        use sp_core::hashing::sha2_256;
        Address(sha2_256(b"qubitcoin-treasury-local"))
    };

    Ok(ChainSpec::builder(wasm_binary()?, None)
        .with_name("Qubitcoin Local Testnet")
        .with_id("qbc_local_testnet")
        .with_chain_type(ChainType::Local)
        .with_properties(chain_properties(CHAIN_ID_TESTNET))
        .with_genesis_config_patch(build_genesis(
            vec![
                authority_keys_from_seed("Alice"),
                authority_keys_from_seed("Bob"),
            ],
            get_account_id_from_seed::<sr25519::Public>("Alice"),
            vec![
                get_account_id_from_seed::<sr25519::Public>("Alice"),
                get_account_id_from_seed::<sr25519::Public>("Bob"),
                get_account_id_from_seed::<sr25519::Public>("Charlie"),
            ],
            treasury_address,
        ))
        .build())
}

/// **MAINNET FORK** — State-preserving fork from the Python chain.
///
/// This genesis embeds ALL unspent UTXOs from the Python chain at the fork
/// height, preserving every coin in circulation. The Substrate chain starts
/// fresh from block 0 but with the exact same UTXO distribution.
///
/// Fork state is loaded from `fork_state.json` (baked in at compile time).
pub fn mainnet_fork_config() -> Result<ChainSpec, String> {
    let fork_state: serde_json::Value = serde_json::from_str(
        include_str!("../../fork_state.json")
    ).map_err(|e| format!("Failed to parse fork_state.json: {}", e))?;

    let fork_height = fork_state["fork_height"].as_u64().unwrap_or(0);
    log::info!("Building fork genesis from Python chain at block {}", fork_height);

    // Two validators — Alice (primary) and Bob (public node)
    // Both run VQE mining; Aura alternates block slots between them.
    let initial_authorities = vec![
        authority_keys_from_seed("Alice"),
        authority_keys_from_seed("Bob"),
    ];

    let root_key = get_account_id_from_seed::<sr25519::Public>("Alice");
    let endowed_accounts = vec![
        root_key.clone(),
        get_account_id_from_seed::<sr25519::Public>("Bob"),
    ];

    // Parse fork UTXOs from JSON
    let utxo_array = fork_state["genesis_utxos"].as_array()
        .ok_or("fork_state.json missing genesis_utxos array")?;

    let mut genesis_utxos = Vec::with_capacity(utxo_array.len());
    for entry in utxo_array {
        let txid = hex_to_h256(entry["txid"].as_str().unwrap());
        let address = hex_to_address(entry["address_hex"].as_str().unwrap());
        let amount = entry["amount"].as_u64().unwrap() as u128;
        if amount == 0 {
            continue;
        }
        genesis_utxos.push(Utxo {
            txid,
            vout: entry["vout"].as_u64().unwrap_or(0) as u32,
            address,
            amount,
            block_height: fork_height,
            is_coinbase: true, // All fork genesis UTXOs marked coinbase
        });
    }

    let difficulty_scaled = fork_state["difficulty_scaled"].as_u64()
        .unwrap_or(INITIAL_DIFFICULTY);
    let total_emitted = fork_state["total_supply_units"].as_u64()
        .unwrap_or(0) as u128;

    Ok(ChainSpec::builder(wasm_binary()?, None)
        .with_name("Qubitcoin Mainnet (Fork)")
        .with_id("qbc_mainnet_fork")
        .with_protocol_id("qbc")
        .with_chain_type(ChainType::Live)
        .with_properties(chain_properties(CHAIN_ID_MAINNET))
        .with_genesis_config_patch(build_fork_genesis(
            initial_authorities,
            root_key,
            endowed_accounts,
            genesis_utxos,
            difficulty_scaled,
            total_emitted,
        ))
        .build())
}

// ═══════════════════════════════════════════════════════════════════════
// Genesis state builder
// ═══════════════════════════════════════════════════════════════════════

/// Build the genesis state JSON patch for any network configuration.
///
/// This produces a deterministic genesis block with:
/// - Coinbase UTXO (vout=0): INITIAL_REWARD (15.27 QBC) to genesis miner
/// - Premine UTXO (vout=1): GENESIS_PREMINE (33M QBC) to treasury
/// - Initial difficulty: 1.0 (INITIAL_DIFFICULTY)
/// - Initial emitted supply: GENESIS_PREMINE + INITIAL_REWARD = 33,000,015.27 QBC
/// - Aura/GRANDPA authorities configured
/// - QVM and Aether anchor service endpoints
///
/// # Genesis Alignment with Python Node
///
/// The genesis block MUST produce identical state to the Python node's genesis.
/// Key alignment points:
/// - **Coinbase txid**: Bitcoin genesis tribute hash (hardcoded, NOT computed)
/// - **Premine txid**: SHA2-256("genesis_premine") — matches Python's `substrate_codec.py`
/// - **Timestamp**: 1707350400 (2024-02-08T00:00:00Z) — set via Aura slot inherent
/// - **Total emitted**: GENESIS_PREMINE + INITIAL_REWARD = 33,000,015.27 QBC
/// - **Genesis hash**: All zeros (0x0000...0000) — Python uses this as prev_hash for block 1
///
/// # Fork Prevention
///
/// Both node types MUST agree on genesis state or they will fork immediately.
/// Any change to genesis constants, txids, or UTXO structure requires coordinated
/// updates across:
/// 1. This file (Substrate chain_spec.rs)
/// 2. Python node's config.py (CANONICAL_GENESIS_* constants)
/// 3. Python node's substrate_codec.py (genesis txid derivation)
/// 4. P2P bridge daemon (genesis block translation)
fn build_genesis(
    initial_authorities: Vec<(AuraId, GrandpaId)>,
    root_key: AccountId,
    endowed_accounts: Vec<AccountId>,
    treasury_address: Address,
) -> serde_json::Value {
    // Genesis miner address: used for coinbase output.
    // For mainnet, this is the treasury. For dev, a deterministic address.
    let genesis_miner = treasury_address;

    // Genesis coinbase UTXO txid: Bitcoin genesis tribute hash.
    // This is the same hash Satoshi used in Bitcoin's genesis coinbase.
    // It is HARDCODED, not computed — it MUST match the Python node's
    // Config.CANONICAL_GENESIS_COINBASE_TXID exactly.
    //
    // Python: config.py line 135:
    //   CANONICAL_GENESIS_COINBASE_TXID = '4a5e1e4baab89f3a32518a88c31bc87f618f76673e2cc77ab2127b7afdeda33b'
    //
    // WARNING: Do NOT change this value. It is a consensus-critical constant.
    // Changing it will cause an immediate fork with the Python node network.
    let genesis_coinbase_txid = H256::from([
        0x4a, 0x5e, 0x1e, 0x4b, 0xaa, 0xb8, 0x9f, 0x3a,
        0x32, 0x51, 0x8a, 0x88, 0xc3, 0x1b, 0xc8, 0x7f,
        0x61, 0x8f, 0x76, 0x67, 0x3e, 0x2c, 0xc7, 0x7a,
        0xb2, 0x12, 0x7b, 0x7a, 0xfd, 0xed, 0xa3, 0x3b,
    ]);

    // Genesis premine UTXO txid: SHA2-256("genesis_premine")
    // This MUST match Python's substrate_codec.py: hashlib.sha256(b"genesis_premine").hexdigest()
    //
    // WARNING: Do NOT change this derivation. It is a consensus-critical constant.
    let genesis_premine_txid = {
        use sp_core::hashing::sha2_256;
        H256::from(sha2_256(b"genesis_premine"))
    };

    serde_json::json!({
        // Standard Substrate pallet genesis
        "balances": {
            "balances": endowed_accounts.iter().cloned()
                .map(|k| (k, 1u128 << 60))
                .collect::<Vec<_>>(),
        },
        "aura": {
            "authorities": initial_authorities.iter()
                .map(|x| x.0.clone())
                .collect::<Vec<_>>(),
        },
        "grandpa": {
            "authorities": initial_authorities.iter()
                .map(|x| (x.1.clone(), 1u64))
                .collect::<Vec<_>>(),
        },
        "sudo": {
            "key": Some(root_key),
        },

        // QBC UTXO genesis — two outputs at block 0
        //
        // Genesis timestamp: 1707350400 (2024-02-08T00:00:00Z)
        // This is set via the Aura slot inherent data provider at node startup.
        // The Python node uses Config.CANONICAL_GENESIS_TIMESTAMP = 1707350400.0
        // Both nodes MUST agree on this timestamp for genesis block hash alignment.
        //
        // Genesis block hash: all zeros (0x0000...0000)
        // Python's block 1 references this as prev_hash. Substrate's genesis
        // hash is computed from the genesis state and will differ from all-zeros,
        // but the P2P bridge maps between the two representations.
        "qbcUtxo": {
            "genesisUtxos": vec![
                // vout=0: Mining reward (15.27 QBC)
                Utxo {
                    txid: genesis_coinbase_txid,
                    vout: 0,
                    address: genesis_miner.clone(),
                    amount: INITIAL_REWARD,
                    block_height: 0,
                    is_coinbase: true,
                },
                // vout=1: Genesis premine (33,000,000 QBC)
                Utxo {
                    txid: genesis_premine_txid,
                    vout: 1,
                    address: genesis_miner,
                    amount: GENESIS_PREMINE,
                    block_height: 0,
                    is_coinbase: true,
                },
            ],
        },

        // QBC Consensus — initial difficulty 1.0 (scaled by 10^6)
        "qbcConsensus": {
            "initialDifficulty": INITIAL_DIFFICULTY,
        },

        // QBC Economics — initial total emitted = premine + first block reward
        // = 33,000,000 QBC + 15.27 QBC = 33,000,015.27 QBC
        // In smallest units: 3_300_000_000_000_000 + 1_527_000_000 = 3_300_001_527_000_000
        //
        // This MUST match the Python node's genesis supply calculation.
        // Python config.py: GENESIS_PREMINE (33M) + INITIAL_REWARD (15.27)
        "qbcEconomics": {
            "initialEmitted": GENESIS_PREMINE + INITIAL_REWARD,
        },

        // QVM Anchor — Python execution service handles QVM
        "qbcQvmAnchor": {
            "serviceEndpoint": b"http://127.0.0.1:5000".to_vec(),
        },

        // Aether Anchor — Python execution service handles Aether Tree
        // Phi starts at 0, empty knowledge root, AI tracked from genesis
        "qbcAetherAnchor": {
            "serviceEndpoint": b"http://127.0.0.1:5000".to_vec(),
        },
    })
}

/// Build the fork genesis — preserves all UTXO balances from the Python chain.
///
/// Unlike `build_genesis()`, this function takes pre-built UTXOs (from the
/// fork state export) and custom difficulty/supply values matching the Python
/// chain's state at the fork block.
fn build_fork_genesis(
    initial_authorities: Vec<(AuraId, GrandpaId)>,
    root_key: AccountId,
    endowed_accounts: Vec<AccountId>,
    genesis_utxos: Vec<Utxo>,
    difficulty_scaled: u64,
    total_emitted: u128,
) -> serde_json::Value {
    serde_json::json!({
        "balances": {
            "balances": endowed_accounts.iter().cloned()
                .map(|k| (k, 1u128 << 60))
                .collect::<Vec<_>>(),
        },
        "aura": {
            "authorities": initial_authorities.iter()
                .map(|x| x.0.clone())
                .collect::<Vec<_>>(),
        },
        "grandpa": {
            "authorities": initial_authorities.iter()
                .map(|x| (x.1.clone(), 1u64))
                .collect::<Vec<_>>(),
        },
        "sudo": {
            "key": Some(root_key),
        },

        // Fork genesis: ALL unspent UTXOs from the Python chain at fork height.
        // Every coin in circulation is preserved.
        "qbcUtxo": {
            "genesisUtxos": genesis_utxos,
        },

        // Difficulty at fork height (not 1.0 — matches Python chain's current difficulty)
        "qbcConsensus": {
            "initialDifficulty": difficulty_scaled,
        },

        // Total emitted at fork height (not genesis amount — matches Python chain's supply)
        "qbcEconomics": {
            "initialEmitted": total_emitted,
        },

        "qbcQvmAnchor": {
            "serviceEndpoint": b"http://127.0.0.1:5000".to_vec(),
        },

        "qbcAetherAnchor": {
            "serviceEndpoint": b"http://127.0.0.1:5000".to_vec(),
        },
    })
}
