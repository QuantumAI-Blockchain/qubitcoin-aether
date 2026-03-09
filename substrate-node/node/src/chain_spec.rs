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

// ═══════════════════════════════════════════════════════════════════════
// Genesis state builder
// ═══════════════════════════════════════════════════════════════════════

/// Build the genesis state JSON patch for any network configuration.
///
/// This produces a deterministic genesis block with:
/// - Coinbase UTXO (vout=0): INITIAL_REWARD (15.27 QBC) to genesis miner
/// - Premine UTXO (vout=1): GENESIS_PREMINE (33M QBC) to treasury
/// - Initial difficulty: 1.0 (INITIAL_DIFFICULTY)
/// - Initial emitted supply: GENESIS_PREMINE + INITIAL_REWARD
/// - Aura/GRANDPA authorities configured
/// - QVM and Aether anchor service endpoints
fn build_genesis(
    initial_authorities: Vec<(AuraId, GrandpaId)>,
    root_key: AccountId,
    endowed_accounts: Vec<AccountId>,
    treasury_address: Address,
) -> serde_json::Value {
    // Genesis miner address: used for coinbase output.
    // For mainnet, this is the treasury. For dev, a deterministic address.
    let genesis_miner = treasury_address;

    // Genesis coinbase UTXO txid: SHA2-256("coinbase:" || block_height_le_bytes)
    // This MUST match the Python node's genesis txid derivation exactly.
    let genesis_coinbase_txid = {
        use sp_core::hashing::sha2_256;
        let mut data = b"coinbase:".to_vec();
        data.extend_from_slice(&0u64.to_le_bytes());
        H256::from(sha2_256(&data))
    };

    // Genesis premine UTXO txid: SHA2-256("genesis_premine")
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

        // QBC Economics — initial total emitted = premine + first reward
        "qbcEconomics": {
            "initialEmitted": GENESIS_PREMINE + INITIAL_REWARD,
        },

        // QVM Anchor — Python execution service handles QVM
        "qbcQvmAnchor": {
            "serviceEndpoint": b"http://127.0.0.1:5000".to_vec(),
        },

        // Aether Anchor — Python execution service handles Aether Tree
        // Phi starts at 0, empty knowledge root, AGI tracked from genesis
        "qbcAetherAnchor": {
            "serviceEndpoint": b"http://127.0.0.1:5000".to_vec(),
        },
    })
}
