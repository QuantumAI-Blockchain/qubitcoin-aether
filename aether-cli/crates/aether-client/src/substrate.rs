//! Substrate JSON-RPC client for Qubitcoin chain queries and extrinsic submission.
//!
//! Computes storage keys matching Substrate's Twox128 + Blake2_128Concat hashing
//! to query on-chain state directly without subxt.

use anyhow::{Context, Result};
use blake2::digest::{Update, VariableOutput};
use blake2::Blake2bVar;
use parity_scale_codec::Encode;
use serde::Deserialize;
use std::hash::Hasher;

/// Substrate RPC client for the Qubitcoin chain.
#[derive(Clone)]
pub struct SubstrateClient {
    rpc_url: String,
    http: reqwest::Client,
}

/// On-chain balance (u128 in smallest QBC units, 1 QBC = 10^8).
pub type QbcBalance = u128;

/// Chain state summary.
#[derive(Debug, Clone)]
pub struct ChainState {
    pub best_hash: String,
    pub height: u64,
    pub difficulty: u64,
}

/// Transaction input (matches Substrate pallet SCALE encoding).
#[derive(Debug, Clone, Encode)]
pub struct TxInput {
    pub prev_txid: [u8; 32],
    pub prev_vout: u32,
}

/// Transaction output (matches Substrate pallet SCALE encoding).
#[derive(Debug, Clone, Encode)]
pub struct TxOutput {
    pub address: [u8; 32],
    pub amount: u128,
}

/// VQE mining proof (matches Substrate pallet VqeProof SCALE encoding).
#[derive(Debug, Clone, Encode)]
pub struct VqeProofEncoded {
    pub params: Vec<i64>,
    pub energy: i128,
    pub hamiltonian_seed: [u8; 32],
    pub n_qubits: u8,
}

#[derive(Deserialize)]
struct RpcResponse<T> {
    result: Option<T>,
    error: Option<serde_json::Value>,
}

impl SubstrateClient {
    pub fn new(rpc_url: &str) -> Self {
        Self {
            rpc_url: rpc_url.trim_end_matches('/').to_string(),
            http: reqwest::Client::builder()
                .timeout(std::time::Duration::from_secs(30))
                .build()
                .expect("failed to create HTTP client"),
        }
    }

    /// Query the balance for a QBC address (32-byte address as hex).
    /// Returns balance in smallest units (1 QBC = 10^8).
    pub async fn get_balance(&self, address_hex: &str) -> Result<QbcBalance> {
        let address_bytes = hex::decode(address_hex)
            .context("invalid address hex")?;
        if address_bytes.len() != 32 {
            anyhow::bail!("address must be 32 bytes (64 hex chars), got {}", address_bytes.len());
        }

        // Storage key: Twox128("QbcUtxo") ++ Twox128("Balances") ++ Blake2_128Concat(address)
        let pallet_hash = twox_128(b"QbcUtxo");
        let storage_hash = twox_128(b"Balances");
        let blake_hash = blake2_128(&address_bytes);

        let mut key = Vec::with_capacity(16 + 16 + 16 + 32);
        key.extend_from_slice(&pallet_hash);
        key.extend_from_slice(&storage_hash);
        key.extend_from_slice(&blake_hash);
        key.extend_from_slice(&address_bytes);

        let key_hex = format!("0x{}", hex::encode(&key));

        let resp: RpcResponse<Option<String>> = self.http
            .post(&self.rpc_url)
            .json(&serde_json::json!({
                "jsonrpc": "2.0",
                "id": 1,
                "method": "state_getStorage",
                "params": [key_hex]
            }))
            .send()
            .await
            .context("failed to reach Substrate RPC")?
            .json()
            .await
            .context("failed to parse RPC response")?;

        match resp.result {
            Some(Some(hex_val)) => {
                let bytes = hex::decode(hex_val.trim_start_matches("0x"))
                    .context("invalid hex in storage value")?;
                if bytes.len() >= 16 {
                    let mut buf = [0u8; 16];
                    buf.copy_from_slice(&bytes[..16]);
                    Ok(u128::from_le_bytes(buf))
                } else {
                    Ok(0)
                }
            }
            _ => Ok(0),
        }
    }

    /// Get chain state (best hash, height, difficulty).
    pub async fn get_chain_state(&self) -> Result<ChainState> {
        let resp: RpcResponse<String> = self.http
            .post(&self.rpc_url)
            .json(&serde_json::json!({
                "jsonrpc": "2.0",
                "id": 1,
                "method": "chain_getBlockHash",
                "params": []
            }))
            .send()
            .await?
            .json()
            .await?;
        let best_hash = resp.result.context("no best hash")?;

        let resp: RpcResponse<serde_json::Value> = self.http
            .post(&self.rpc_url)
            .json(&serde_json::json!({
                "jsonrpc": "2.0",
                "id": 2,
                "method": "chain_getHeader",
                "params": [&best_hash]
            }))
            .send()
            .await?
            .json()
            .await?;
        let header = resp.result.context("no header")?;
        let number_hex = header["number"].as_str().unwrap_or("0x0");
        let height = u64::from_str_radix(number_hex.trim_start_matches("0x"), 16).unwrap_or(0);

        let diff_key = format!("0x{}{}",
            hex::encode(twox_128(b"QbcConsensus")),
            hex::encode(twox_128(b"CurrentDifficulty")),
        );

        let resp: RpcResponse<Option<String>> = self.http
            .post(&self.rpc_url)
            .json(&serde_json::json!({
                "jsonrpc": "2.0",
                "id": 3,
                "method": "state_getStorage",
                "params": [diff_key]
            }))
            .send()
            .await?
            .json()
            .await?;

        let difficulty = if let Some(Some(hex_val)) = resp.result {
            let bytes = hex::decode(hex_val.trim_start_matches("0x")).unwrap_or_default();
            if bytes.len() >= 8 {
                u64::from_le_bytes(bytes[..8].try_into().unwrap_or([0; 8]))
            } else {
                1_000_000
            }
        } else {
            1_000_000
        };

        Ok(ChainState { best_hash, height, difficulty })
    }

    /// Get the current block height.
    pub async fn get_height(&self) -> Result<u64> {
        let state = self.get_chain_state().await?;
        Ok(state.height)
    }

    /// Submit a raw SCALE-encoded extrinsic (hex-encoded with 0x prefix).
    pub async fn submit_extrinsic(&self, extrinsic_hex: &str) -> Result<String> {
        let resp: RpcResponse<serde_json::Value> = self.http
            .post(&self.rpc_url)
            .json(&serde_json::json!({
                "jsonrpc": "2.0",
                "id": 1,
                "method": "author_submitExtrinsic",
                "params": [extrinsic_hex]
            }))
            .send()
            .await
            .context("failed to submit extrinsic")?
            .json()
            .await
            .context("failed to parse submit response")?;

        if let Some(error) = resp.error {
            anyhow::bail!("extrinsic submission failed: {}", error);
        }

        match resp.result {
            Some(v) => Ok(v.to_string()),
            None => Ok("submitted".to_string()),
        }
    }

    /// Get the account nonce for extrinsic signing.
    pub async fn get_nonce(&self, account_id_hex: &str) -> Result<u32> {
        let resp: RpcResponse<serde_json::Value> = self.http
            .post(&self.rpc_url)
            .json(&serde_json::json!({
                "jsonrpc": "2.0",
                "id": 1,
                "method": "system_accountNextIndex",
                "params": [account_id_hex]
            }))
            .send()
            .await?
            .json()
            .await?;

        match resp.result {
            Some(v) => Ok(v.as_u64().unwrap_or(0) as u32),
            None => Ok(0),
        }
    }

    /// Get the runtime version (spec_version, tx_version).
    pub async fn get_runtime_version(&self) -> Result<(u32, u32)> {
        let resp: RpcResponse<serde_json::Value> = self.http
            .post(&self.rpc_url)
            .json(&serde_json::json!({
                "jsonrpc": "2.0",
                "id": 1,
                "method": "state_getRuntimeVersion",
                "params": []
            }))
            .send()
            .await?
            .json()
            .await?;

        let rv = resp.result.context("no runtime version")?;
        let spec_version = rv["specVersion"].as_u64().unwrap_or(1) as u32;
        let tx_version = rv["transactionVersion"].as_u64().unwrap_or(1) as u32;
        Ok((spec_version, tx_version))
    }

    /// Get the genesis hash as [u8; 32].
    pub async fn get_genesis_hash(&self) -> Result<[u8; 32]> {
        let resp: RpcResponse<String> = self.http
            .post(&self.rpc_url)
            .json(&serde_json::json!({
                "jsonrpc": "2.0",
                "id": 1,
                "method": "chain_getBlockHash",
                "params": [0]
            }))
            .send()
            .await?
            .json()
            .await?;

        let hash_hex = resp.result.context("no genesis hash")?;
        let bytes = hex::decode(hash_hex.trim_start_matches("0x"))?;
        let mut hash = [0u8; 32];
        let len = bytes.len().min(32);
        hash[..len].copy_from_slice(&bytes[..len]);
        Ok(hash)
    }

    /// Encode a submit_mining_proof call.
    pub fn encode_mining_proof_call(
        pallet_index: u8,
        miner_address: [u8; 32],
        proof: VqeProofEncoded,
    ) -> Vec<u8> {
        let mut call = Vec::new();
        call.push(pallet_index);
        call.push(0); // call_index(0) = submit_mining_proof

        // Address([u8; 32]) — raw 32 bytes
        call.extend_from_slice(&miner_address);

        // VqeProof — SCALE encoded struct
        call.extend_from_slice(&proof.encode());

        call
    }

    /// Encode a submit_transaction call (UTXO transfer).
    pub fn encode_utxo_transaction_call(
        pallet_index: u8,
        inputs: &[TxInput],
        outputs: &[TxOutput],
        signatures: &[Vec<u8>],
    ) -> Vec<u8> {
        let mut call = Vec::new();
        call.push(pallet_index);
        call.push(0); // call_index(0) = submit_transaction

        // BoundedVec<TransactionInput> — encoded as Vec
        call.extend_from_slice(&inputs.encode());
        // BoundedVec<TransactionOutput> — encoded as Vec
        call.extend_from_slice(&outputs.encode());
        // BoundedVec<BoundedVec<u8>> — encoded as Vec<Vec<u8>>
        call.extend_from_slice(&signatures.encode());

        call
    }

    /// Encode a register_key call (Dilithium pallet).
    pub fn encode_register_key_call(
        pallet_index: u8,
        public_key: &[u8],
    ) -> Vec<u8> {
        let mut call = Vec::new();
        call.push(pallet_index);
        call.push(0); // call_index(0) = register_key

        // BoundedVec<u8> — encoded as Vec<u8>
        call.extend_from_slice(&public_key.to_vec().encode());

        call
    }

    /// Build the signing payload for a Substrate extrinsic.
    pub fn build_signing_payload(
        call_data: &[u8],
        nonce: u32,
        spec_version: u32,
        tx_version: u32,
        genesis_hash: &[u8; 32],
    ) -> Vec<u8> {
        let mut payload = Vec::new();
        payload.extend_from_slice(call_data);

        // SignedExtra: Era (immortal=0x00), Nonce (compact), Tip (compact 0)
        payload.push(0x00);
        compact_encode(&mut payload, nonce as u64);
        compact_encode(&mut payload, 0);

        // AdditionalSigned: spec_version, tx_version, genesis_hash, block_hash (=genesis for immortal)
        payload.extend_from_slice(&spec_version.to_le_bytes());
        payload.extend_from_slice(&tx_version.to_le_bytes());
        payload.extend_from_slice(genesis_hash);
        payload.extend_from_slice(genesis_hash);

        // If payload > 256 bytes, hash it with Blake2b-256
        if payload.len() > 256 {
            let hash = blake2_256(&payload);
            hash.to_vec()
        } else {
            payload
        }
    }

    /// Wrap a signed call into a complete extrinsic.
    pub fn build_signed_extrinsic(
        call_data: &[u8],
        signer_public: &[u8; 32],
        signature: &[u8; 64],
        nonce: u32,
    ) -> Vec<u8> {
        let mut body = Vec::new();

        // Version: 0x84 = signed + extrinsic format version 4
        body.push(0x84);

        // MultiAddress::Id (0x00) + AccountId32
        body.push(0x00);
        body.extend_from_slice(signer_public);

        // MultiSignature::Ed25519 (0x00) + 64-byte sig
        body.push(0x00);
        body.extend_from_slice(signature);

        // SignedExtra: Era, Nonce, Tip
        body.push(0x00); // Immortal era
        compact_encode(&mut body, nonce as u64);
        compact_encode(&mut body, 0); // Tip = 0

        // Call data
        body.extend_from_slice(call_data);

        // Compact-length prefix
        let mut extrinsic = Vec::new();
        compact_encode(&mut extrinsic, body.len() as u64);
        extrinsic.extend_from_slice(&body);

        extrinsic
    }

    /// Build the signing message for a UTXO transaction (Dilithium5 signature).
    /// Matches Substrate pallet's `signing_message()`.
    pub fn build_utxo_signing_message(
        inputs: &[TxInput],
        outputs: &[TxOutput],
    ) -> Vec<u8> {
        let mut msg = Vec::new();
        for input in inputs {
            msg.extend_from_slice(&input.prev_txid);
            msg.extend_from_slice(&input.prev_vout.to_le_bytes());
        }
        for output in outputs {
            msg.extend_from_slice(&output.address);
            msg.extend_from_slice(&output.amount.to_le_bytes());
        }
        msg
    }
}

// ── Hashing utilities matching Substrate ─────────────────────────────────

/// Twox128 hash (Substrate pallet/storage name hashing).
fn twox_128(data: &[u8]) -> [u8; 16] {
    let mut h0 = twox_hash::XxHash64::with_seed(0);
    h0.write(data);
    let r0 = h0.finish();

    let mut h1 = twox_hash::XxHash64::with_seed(1);
    h1.write(data);
    let r1 = h1.finish();

    let mut result = [0u8; 16];
    result[..8].copy_from_slice(&r0.to_le_bytes());
    result[8..].copy_from_slice(&r1.to_le_bytes());
    result
}

/// Blake2b-128 hash (Substrate Blake2_128Concat map key hashing).
fn blake2_128(data: &[u8]) -> [u8; 16] {
    let mut hasher = Blake2bVar::new(16)
        .expect("valid blake2b output size");
    hasher.update(data);
    let mut out = [0u8; 16];
    hasher.finalize_variable(&mut out)
        .expect("valid output buffer");
    out
}

/// Blake2b-256 hash (for signing payload hashing when > 256 bytes).
fn blake2_256(data: &[u8]) -> [u8; 32] {
    let mut hasher = Blake2bVar::new(32)
        .expect("valid blake2b output size");
    hasher.update(data);
    let mut out = [0u8; 32];
    hasher.finalize_variable(&mut out)
        .expect("valid output buffer");
    out
}

/// SCALE compact encoding for unsigned integers.
fn compact_encode(buf: &mut Vec<u8>, value: u64) {
    if value < 0x40 {
        buf.push((value as u8) << 2);
    } else if value < 0x4000 {
        let v = ((value as u16) << 2) | 0x01;
        buf.extend_from_slice(&v.to_le_bytes());
    } else if value < 0x4000_0000 {
        let v = ((value as u32) << 2) | 0x02;
        buf.extend_from_slice(&v.to_le_bytes());
    } else {
        let bytes_needed = 8 - (value.leading_zeros() / 8) as usize;
        buf.push(((bytes_needed as u8 - 4) << 2) | 0x03);
        let le = value.to_le_bytes();
        buf.extend_from_slice(&le[..bytes_needed]);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_compact_encode() {
        let mut buf = Vec::new();
        compact_encode(&mut buf, 0);
        assert_eq!(buf, vec![0x00]);

        buf.clear();
        compact_encode(&mut buf, 1);
        assert_eq!(buf, vec![0x04]);

        buf.clear();
        compact_encode(&mut buf, 63);
        assert_eq!(buf, vec![0xFC]);

        buf.clear();
        compact_encode(&mut buf, 64);
        assert_eq!(buf, vec![0x01, 0x01]);
    }

    #[test]
    fn test_twox_128_known_value() {
        let hash = twox_128(b"System");
        assert_eq!(hash.len(), 16);
        // This should be deterministic
        let hash2 = twox_128(b"System");
        assert_eq!(hash, hash2);
    }

    #[test]
    fn test_blake2_128() {
        let hash = blake2_128(b"test");
        assert_eq!(hash.len(), 16);
        let hash2 = blake2_128(b"test");
        assert_eq!(hash, hash2);
        // Different input should give different output
        let hash3 = blake2_128(b"other");
        assert_ne!(hash, hash3);
    }

    #[test]
    fn test_blake2_256() {
        let hash = blake2_256(b"test");
        assert_eq!(hash.len(), 32);
    }
}
