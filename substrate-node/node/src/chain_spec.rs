//! Qubitcoin chain specification — genesis configuration.
//!
//! Defines the genesis block for mainnet and testnet including:
//! - Initial authorities (Aura/GRANDPA validators)
//! - Genesis UTXO set (coinbase + premine)
//! - Initial difficulty
//! - Economic parameters
//! - QVM and Aether service endpoints

use qbc_primitives::{
    Address, Utxo, GENESIS_PREMINE, INITIAL_DIFFICULTY, INITIAL_REWARD,
};
use qbc_runtime::{AccountId, Signature, WASM_BINARY};
use sc_service::ChainType;
use sp_consensus_aura::sr25519::AuthorityId as AuraId;
use sp_consensus_grandpa::AuthorityId as GrandpaId;
use sp_core::{sr25519, H256, Pair, Public};
use sp_runtime::traits::{IdentifyAccount, Verify};

/// Specialized `ChainSpec` for Qubitcoin.
pub type ChainSpec = sc_service::GenericChainSpec;

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

/// Generate an Aura authority key.
pub fn authority_keys_from_seed(s: &str) -> (AuraId, GrandpaId) {
    (get_from_seed::<AuraId>(s), get_from_seed::<GrandpaId>(s))
}

/// Development chain spec with single validator.
pub fn development_config() -> Result<ChainSpec, String> {
    Ok(ChainSpec::builder(
        WASM_BINARY.ok_or_else(|| "Development wasm not available".to_string())?,
        None,
    )
    .with_name("Qubitcoin Development")
    .with_id("qbc_dev")
    .with_chain_type(ChainType::Development)
    .with_genesis_config_patch(testnet_genesis(
        vec![authority_keys_from_seed("Alice")],
        get_account_id_from_seed::<sr25519::Public>("Alice"),
        vec![
            get_account_id_from_seed::<sr25519::Public>("Alice"),
            get_account_id_from_seed::<sr25519::Public>("Bob"),
        ],
        true,
    ))
    .build())
}

/// Local testnet chain spec with two validators.
pub fn local_testnet_config() -> Result<ChainSpec, String> {
    Ok(ChainSpec::builder(
        WASM_BINARY.ok_or_else(|| "Local testnet wasm not available".to_string())?,
        None,
    )
    .with_name("Qubitcoin Local Testnet")
    .with_id("qbc_local_testnet")
    .with_chain_type(ChainType::Local)
    .with_genesis_config_patch(testnet_genesis(
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
        true,
    ))
    .build())
}

/// Configure initial storage state for testing.
fn testnet_genesis(
    initial_authorities: Vec<(AuraId, GrandpaId)>,
    root_key: AccountId,
    endowed_accounts: Vec<AccountId>,
    _enable_println: bool,
) -> serde_json::Value {
    // Genesis miner address (deterministic for dev/testnet)
    let genesis_miner = Address([0x01; 32]);

    // Genesis coinbase UTXO: mining reward (vout=0)
    let genesis_coinbase_txid = {
        use sp_core::hashing::sha2_256;
        let mut data = b"coinbase:".to_vec();
        data.extend_from_slice(&0u64.to_le_bytes());
        H256::from(sha2_256(&data))
    };

    // Genesis premine UTXO (vout=1) — 33M QBC
    let genesis_premine_txid = {
        use sp_core::hashing::sha2_256;
        let data = b"genesis_premine";
        H256::from(sha2_256(data))
    };

    serde_json::json!({
        "balances": {
            "balances": endowed_accounts.iter().cloned()
                .map(|k| (k, 1u128 << 60))
                .collect::<Vec<_>>(),
        },
        "aura": {
            "authorities": initial_authorities.iter().map(|x| x.0.clone()).collect::<Vec<_>>(),
        },
        "grandpa": {
            "authorities": initial_authorities.iter().map(|x| (x.1.clone(), 1)).collect::<Vec<_>>(),
        },
        "sudo": {
            "key": Some(root_key),
        },
        "qbcUtxo": {
            "genesisUtxos": vec![
                // Coinbase reward UTXO (vout=0)
                Utxo {
                    txid: genesis_coinbase_txid,
                    vout: 0,
                    address: genesis_miner.clone(),
                    amount: INITIAL_REWARD,
                    block_height: 0,
                    is_coinbase: true,
                },
                // Genesis premine UTXO (vout=1) — 33M QBC
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
        "qbcConsensus": {
            "initialDifficulty": INITIAL_DIFFICULTY,
        },
        "qbcEconomics": {
            "initialEmitted": GENESIS_PREMINE + INITIAL_REWARD,
        },
        "qbcQvmAnchor": {
            "serviceEndpoint": b"http://127.0.0.1:9944".to_vec(),
        },
        "qbcAetherAnchor": {
            "serviceEndpoint": b"http://127.0.0.1:5000".to_vec(),
        },
    })
}
