//! Susy Swap — Confidential Transaction Builder.
//!
//! Constructs privacy-preserving transactions that hide amounts and addresses:
//! - Each output has a Pedersen commitment (hides amount)
//! - Each output has a range proof (proves amount >= 0)
//! - Optional stealth addresses (hides recipient)
//! - Key images prevent double-spending
//! - Homomorphic balance verification (sum inputs == sum outputs + fee)
//!
//! Fee is always public (not hidden).

use crate::commitment::{generate_blinding, PedersenCommitment};
use crate::range_proof::RangeProof;
use crate::stealth::{StealthAddressManager, StealthOutput};
use k256::elliptic_curve::ops::Reduce;
use k256::{Scalar, U256};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};

/// A confidential transaction (Susy Swap).
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ConfidentialTransaction {
    pub txid: [u8; 32],
    pub inputs: Vec<ConfidentialInput>,
    pub outputs: Vec<ConfidentialOutput>,
    pub fee: u64,
    pub key_images: Vec<Vec<u8>>,
    pub excess_commitment: Vec<u8>,
    pub signature: Vec<u8>,
    pub timestamp: u64,
}

/// An input to a confidential transaction.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ConfidentialInput {
    pub prev_txid: [u8; 32],
    pub prev_vout: u32,
    pub value: u64,
    pub blinding: [u8; 32],
    pub key_image: Vec<u8>,
    pub commitment: Vec<u8>,
}

/// An output of a confidential transaction.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ConfidentialOutput {
    pub commitment: Vec<u8>,
    pub range_proof: RangeProof,
    pub stealth: Option<StealthOutput>,
    pub value: u64,
    pub blinding: [u8; 32],
}

/// Builder for constructing Susy Swap transactions.
pub struct SusySwapBuilder {
    inputs: Vec<BuilderInput>,
    outputs: Vec<BuilderOutput>,
    fee: u64,
}

struct BuilderInput {
    prev_txid: [u8; 32],
    prev_vout: u32,
    value: u64,
    blinding: [u8; 32],
    spending_key: Vec<u8>,
}

struct BuilderOutput {
    value: u64,
    recipient_spend_pub: Option<Vec<u8>>,
    recipient_view_pub: Option<Vec<u8>>,
}

impl SusySwapBuilder {
    pub fn new() -> Self {
        Self {
            inputs: Vec::new(),
            outputs: Vec::new(),
            fee: 0,
        }
    }

    /// Add an input UTXO.
    pub fn add_input(
        &mut self,
        prev_txid: [u8; 32],
        prev_vout: u32,
        value: u64,
        blinding: [u8; 32],
        spending_key: Vec<u8>,
    ) -> &mut Self {
        self.inputs.push(BuilderInput {
            prev_txid,
            prev_vout,
            value,
            blinding,
            spending_key,
        });
        self
    }

    /// Add an output with optional stealth address.
    pub fn add_output(
        &mut self,
        value: u64,
        recipient_spend_pub: Option<Vec<u8>>,
        recipient_view_pub: Option<Vec<u8>>,
    ) -> &mut Self {
        self.outputs.push(BuilderOutput {
            value,
            recipient_spend_pub,
            recipient_view_pub,
        });
        self
    }

    /// Set the transaction fee (in smallest units).
    pub fn set_fee(&mut self, fee: u64) -> &mut Self {
        self.fee = fee;
        self
    }

    /// Build the confidential transaction.
    pub fn build(&mut self) -> Result<ConfidentialTransaction, String> {
        if self.inputs.is_empty() {
            return Err("no inputs".to_string());
        }
        if self.outputs.is_empty() {
            return Err("no outputs".to_string());
        }

        // Verify balance: sum(inputs) == sum(outputs) + fee
        let total_in: u64 = self.inputs.iter().map(|i| i.value).sum();
        let total_out: u64 = self.outputs.iter().map(|o| o.value).sum();
        if total_in != total_out + self.fee {
            return Err(format!(
                "unbalanced: inputs={} outputs={} fee={} (diff={})",
                total_in,
                total_out,
                self.fee,
                total_in as i128 - total_out as i128 - self.fee as i128,
            ));
        }

        // Build input commitments and key images
        let mut conf_inputs = Vec::with_capacity(self.inputs.len());
        let mut key_images = Vec::with_capacity(self.inputs.len());
        let mut total_input_blinding = Scalar::ZERO;

        for input in &self.inputs {
            let commitment = PedersenCommitment::commit_with_blinding(input.value, &input.blinding);
            let ki = StealthAddressManager::compute_key_image(&input.spending_key)
                .map_err(|e| format!("key image: {e}"))?;

            let blind_scalar =
                <Scalar as Reduce<U256>>::reduce_bytes(&input.blinding.into());
            total_input_blinding = total_input_blinding + blind_scalar;

            key_images.push(ki.image.clone());
            conf_inputs.push(ConfidentialInput {
                prev_txid: input.prev_txid,
                prev_vout: input.prev_vout,
                value: input.value,
                blinding: input.blinding,
                key_image: ki.image,
                commitment: commitment.point,
            });
        }

        // Build output commitments and range proofs
        let mut conf_outputs = Vec::with_capacity(self.outputs.len());
        let mut total_output_blinding = Scalar::ZERO;

        for (i, output) in self.outputs.iter().enumerate() {
            let blinding = if i == self.outputs.len() - 1 {
                // Last output: adjust blinding to ensure balance
                // excess_blinding = total_input_blinding - sum(previous_output_blindings)
                let excess = total_input_blinding - total_output_blinding;
                let bytes = excess.to_bytes();
                let mut b = [0u8; 32];
                b.copy_from_slice(&bytes);
                b
            } else {
                generate_blinding()
            };

            let blind_scalar =
                <Scalar as Reduce<U256>>::reduce_bytes(&blinding.into());
            total_output_blinding = total_output_blinding + blind_scalar;

            let commitment = PedersenCommitment::commit_with_blinding(output.value, &blinding);
            let range_proof = RangeProof::generate(output.value, &blinding);

            let stealth = match (&output.recipient_spend_pub, &output.recipient_view_pub) {
                (Some(spend), Some(view)) => {
                    Some(StealthAddressManager::create_output(spend, view)
                        .map_err(|e| format!("stealth: {e}"))?)
                }
                _ => None,
            };

            conf_outputs.push(ConfidentialOutput {
                commitment: commitment.point,
                range_proof,
                stealth,
                value: output.value,
                blinding,
            });
        }

        // Excess commitment (should be fee*G if balanced correctly)
        let excess_blinding = total_input_blinding - total_output_blinding;
        let excess_commit = k256::ProjectivePoint::GENERATOR * Scalar::from(self.fee)
            + crate::commitment::PedersenCommitment::commit_with_blinding(0, &{
                let bytes = excess_blinding.to_bytes();
                let mut b = [0u8; 32];
                b.copy_from_slice(&bytes);
                b
            })
            .to_point()
            .unwrap_or(k256::ProjectivePoint::IDENTITY);

        use k256::elliptic_curve::group::GroupEncoding;
        let excess_bytes = excess_commit.to_affine().to_bytes().to_vec();

        // Compute txid
        let mut txid_hasher = Sha256::new();
        txid_hasher.update(b"susy_swap_txid_v1");
        for ci in &conf_inputs {
            txid_hasher.update(&ci.prev_txid);
            txid_hasher.update(ci.prev_vout.to_le_bytes());
            txid_hasher.update(&ci.commitment);
        }
        for co in &conf_outputs {
            txid_hasher.update(&co.commitment);
        }
        txid_hasher.update(self.fee.to_le_bytes());
        let txid: [u8; 32] = txid_hasher.finalize().into();

        // Sign: HMAC-like construction over txid + excess + key_images
        let mut sig_hasher = Sha256::new();
        sig_hasher.update(b"susy_swap_sig_v1");
        sig_hasher.update(&txid);
        sig_hasher.update(&excess_bytes);
        for ki in &key_images {
            sig_hasher.update(ki);
        }
        // Aggregate signing keys
        let mut agg_key = Scalar::ZERO;
        for input in &self.inputs {
            let sk = <Scalar as Reduce<U256>>::reduce_bytes(
                &{
                    let mut arr = [0u8; 32];
                    let len = input.spending_key.len().min(32);
                    arr[..len].copy_from_slice(&input.spending_key[..len]);
                    arr
                }
                .into(),
            );
            agg_key = agg_key + sk;
        }
        sig_hasher.update(&agg_key.to_bytes());
        let signature: [u8; 32] = sig_hasher.finalize().into();

        let timestamp = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap_or_default()
            .as_secs();

        // Clear builder state
        self.inputs.clear();
        self.outputs.clear();
        self.fee = 0;

        Ok(ConfidentialTransaction {
            txid,
            inputs: conf_inputs,
            outputs: conf_outputs,
            fee: self.fee,
            key_images,
            excess_commitment: excess_bytes,
            signature: signature.to_vec(),
            timestamp,
        })
    }
}

/// Verify a confidential transaction.
pub fn verify_transaction(tx: &ConfidentialTransaction) -> Result<bool, String> {
    // Verify all range proofs
    for (i, output) in tx.outputs.iter().enumerate() {
        if !output.range_proof.verify() {
            return Err(format!("range proof #{i} invalid"));
        }
    }

    // Verify key image uniqueness
    let mut seen = std::collections::HashSet::new();
    for ki in &tx.key_images {
        if !seen.insert(ki.clone()) {
            return Err("duplicate key image (double-spend attempt)".to_string());
        }
    }

    // Verify commitment balance via homomorphic property
    let input_points: Vec<Vec<u8>> = tx.inputs.iter().map(|i| i.commitment.clone()).collect();
    let output_points: Vec<Vec<u8>> = tx.outputs.iter().map(|o| o.commitment.clone()).collect();

    if !crate::commitment::verify_commitment_balance(&input_points, &output_points, tx.fee) {
        return Err("commitment balance check failed".to_string());
    }

    Ok(true)
}

/// Summary of a confidential transaction for display.
pub struct TxSummary {
    pub txid: String,
    pub input_count: usize,
    pub output_count: usize,
    pub fee: u64,
    pub key_images: usize,
    pub has_stealth: bool,
    pub total_proof_size: usize,
    pub timestamp: u64,
}

impl ConfidentialTransaction {
    pub fn summary(&self) -> TxSummary {
        TxSummary {
            txid: hex::encode(self.txid),
            input_count: self.inputs.len(),
            output_count: self.outputs.len(),
            fee: self.fee,
            key_images: self.key_images.len(),
            has_stealth: self.outputs.iter().any(|o| o.stealth.is_some()),
            total_proof_size: self
                .outputs
                .iter()
                .map(|o| o.range_proof.size())
                .sum(),
            timestamp: self.timestamp,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn test_spending_key() -> Vec<u8> {
        let mut key = [0u8; 32];
        key[0] = 0x42;
        key[1] = 0x01;
        key.to_vec()
    }

    #[test]
    fn test_simple_transfer() {
        let spending_key = test_spending_key();
        let input_blinding = generate_blinding();

        let mut builder = SusySwapBuilder::new();
        builder
            .add_input([1u8; 32], 0, 100_000_000, input_blinding, spending_key)
            .add_output(90_000_000, None, None)
            .set_fee(10_000_000);

        let tx = builder.build().unwrap();
        assert_eq!(tx.inputs.len(), 1);
        assert_eq!(tx.outputs.len(), 1);
        assert_eq!(tx.key_images.len(), 1);
        assert!(!tx.txid.iter().all(|&b| b == 0));
    }

    #[test]
    fn test_multi_output() {
        let sk = test_spending_key();
        let blind = generate_blinding();

        let mut builder = SusySwapBuilder::new();
        builder
            .add_input([2u8; 32], 0, 200_000_000, blind, sk)
            .add_output(100_000_000, None, None)
            .add_output(90_000_000, None, None)
            .set_fee(10_000_000);

        let tx = builder.build().unwrap();
        assert_eq!(tx.outputs.len(), 2);

        // All range proofs should verify
        for o in &tx.outputs {
            assert!(o.range_proof.verify());
        }
    }

    #[test]
    fn test_with_stealth() {
        let sk = test_spending_key();
        let blind = generate_blinding();
        let recipient = StealthAddressManager::generate_keypair();

        let mut builder = SusySwapBuilder::new();
        builder
            .add_input([3u8; 32], 0, 50_000_000, blind, sk)
            .add_output(
                40_000_000,
                Some(recipient.spend_pubkey.clone()),
                Some(recipient.view_pubkey.clone()),
            )
            .set_fee(10_000_000);

        let tx = builder.build().unwrap();
        assert!(tx.outputs[0].stealth.is_some());
        let summary = tx.summary();
        assert!(summary.has_stealth);
    }

    #[test]
    fn test_unbalanced_fails() {
        let sk = test_spending_key();
        let blind = generate_blinding();

        let mut builder = SusySwapBuilder::new();
        builder
            .add_input([4u8; 32], 0, 100_000_000, blind, sk)
            .add_output(110_000_000, None, None) // More than input
            .set_fee(0);

        let result = builder.build();
        assert!(result.is_err());
        assert!(result.unwrap_err().contains("unbalanced"));
    }

    #[test]
    fn test_verify_transaction() {
        let sk = test_spending_key();
        let blind = generate_blinding();

        let mut builder = SusySwapBuilder::new();
        builder
            .add_input([5u8; 32], 0, 100_000_000, blind, sk)
            .add_output(95_000_000, None, None)
            .set_fee(5_000_000);

        let tx = builder.build().unwrap();
        let result = verify_transaction(&tx);
        assert!(result.is_ok());
        assert!(result.unwrap());
    }

    #[test]
    fn test_txid_deterministic_per_inputs() {
        let sk = test_spending_key();
        let blind = generate_blinding();

        let mut b1 = SusySwapBuilder::new();
        b1.add_input([6u8; 32], 0, 100_000_000, blind, sk.clone())
            .add_output(90_000_000, None, None)
            .set_fee(10_000_000);

        let mut b2 = SusySwapBuilder::new();
        b2.add_input([7u8; 32], 0, 100_000_000, blind, sk) // different txid
            .add_output(90_000_000, None, None)
            .set_fee(10_000_000);

        let tx1 = b1.build().unwrap();
        let tx2 = b2.build().unwrap();
        assert_ne!(tx1.txid, tx2.txid);
    }

    #[test]
    fn test_summary() {
        let sk = test_spending_key();
        let blind = generate_blinding();

        let mut builder = SusySwapBuilder::new();
        builder
            .add_input([8u8; 32], 0, 100_000_000, blind, sk)
            .add_output(90_000_000, None, None)
            .set_fee(10_000_000);

        let tx = builder.build().unwrap();
        let s = tx.summary();
        assert_eq!(s.input_count, 1);
        assert_eq!(s.output_count, 1);
        assert!(!s.has_stealth);
        assert!(s.total_proof_size > 0);
    }
}
