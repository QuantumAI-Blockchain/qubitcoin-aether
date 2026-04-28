//! Stealth Address Protocol for Qubitcoin.
//!
//! Uses Diffie-Hellman on secp256k1 to generate one-time addresses:
//!
//! Recipient publishes: (spend_pub, view_pub)
//! Sender:
//!   1. Generates ephemeral keypair (r, R = r*G)
//!   2. Computes shared_secret = SHA256(r * view_pub)
//!   3. Derives one_time_address = spend_pub + shared_secret * G
//!   4. Publishes R in transaction
//! Recipient:
//!   1. Computes shared_secret = SHA256(view_priv * R)
//!   2. Checks if spend_pub + shared_secret * G == output address
//!   3. If match, spending_key = spend_priv + shared_secret
//!
//! Key images prevent double-spending: I = spend_key * H(spend_key * G)

use k256::elliptic_curve::group::GroupEncoding;
use k256::elliptic_curve::ops::Reduce;
use k256::elliptic_curve::sec1::ToEncodedPoint;
use k256::{AffinePoint, ProjectivePoint, Scalar, U256};
use rand::RngCore;
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};

/// Stealth address keypair (spend + view).
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct StealthKeypair {
    pub spend_privkey: Vec<u8>,
    pub spend_pubkey: Vec<u8>,
    pub view_privkey: Vec<u8>,
    pub view_pubkey: Vec<u8>,
}

impl StealthKeypair {
    /// The stealth public address: spend_pubkey || view_pubkey (66 bytes compressed).
    pub fn public_address(&self) -> Vec<u8> {
        let mut addr = Vec::with_capacity(66);
        addr.extend_from_slice(&self.spend_pubkey);
        addr.extend_from_slice(&self.view_pubkey);
        addr
    }

    /// Hex-encoded public address (132 chars).
    pub fn public_address_hex(&self) -> String {
        hex::encode(self.public_address())
    }
}

/// A stealth output created by a sender.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct StealthOutput {
    /// One-time address (compressed point, 33 bytes).
    pub one_time_address: Vec<u8>,
    /// Sender's ephemeral public key R (compressed, 33 bytes).
    pub ephemeral_pubkey: Vec<u8>,
}

/// Key image for double-spend prevention.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct KeyImage {
    pub image: Vec<u8>,
}

pub struct StealthAddressManager;

impl StealthAddressManager {
    /// Generate a new stealth keypair (spend + view).
    pub fn generate_keypair() -> StealthKeypair {
        let (spend_priv, spend_pub) = generate_keypair();
        let (view_priv, view_pub) = generate_keypair();

        StealthKeypair {
            spend_privkey: spend_priv.to_bytes().to_vec(),
            spend_pubkey: spend_pub.to_affine().to_bytes().to_vec(),
            view_privkey: view_priv.to_bytes().to_vec(),
            view_pubkey: view_pub.to_affine().to_bytes().to_vec(),
        }
    }

    /// Create a stealth output for a recipient.
    /// Takes the recipient's spend_pub and view_pub (33 bytes each, compressed).
    pub fn create_output(
        recipient_spend_pub: &[u8],
        recipient_view_pub: &[u8],
    ) -> Result<StealthOutput, String> {
        let spend_pub = decode_point(recipient_spend_pub)?;
        let view_pub = decode_point(recipient_view_pub)?;

        // Generate ephemeral keypair
        let (eph_priv, eph_pub) = generate_keypair();

        // shared_secret = SHA256(r * view_pub)
        let shared_point = view_pub * eph_priv;
        let shared_secret = hash_shared_point(&shared_point);

        // one_time_address = spend_pub + shared_secret * G
        let ss_scalar = <Scalar as Reduce<U256>>::reduce_bytes(&shared_secret.into());
        let one_time = spend_pub + ProjectivePoint::GENERATOR * ss_scalar;

        Ok(StealthOutput {
            one_time_address: one_time.to_affine().to_bytes().to_vec(),
            ephemeral_pubkey: eph_pub.to_affine().to_bytes().to_vec(),
        })
    }

    /// Scan a stealth output to check if it belongs to us.
    /// Returns the spending key scalar if it matches.
    pub fn scan_output(
        keypair: &StealthKeypair,
        ephemeral_pubkey: &[u8],
        output_address: &[u8],
    ) -> Result<Option<Vec<u8>>, String> {
        let eph_pub = decode_point(ephemeral_pubkey)?;
        let view_priv = decode_scalar(&keypair.view_privkey)?;
        let spend_priv = decode_scalar(&keypair.spend_privkey)?;
        let spend_pub = decode_point(&keypair.spend_pubkey)?;

        // shared_secret = SHA256(view_priv * R)
        let shared_point = eph_pub * view_priv;
        let shared_secret = hash_shared_point(&shared_point);
        let ss_scalar = <Scalar as Reduce<U256>>::reduce_bytes(&shared_secret.into());

        // Expected one_time_address = spend_pub + shared_secret * G
        let expected = spend_pub + ProjectivePoint::GENERATOR * ss_scalar;
        let expected_bytes = expected.to_affine().to_bytes();

        if expected_bytes.as_slice() == output_address {
            // Derive spending key: spend_priv + shared_secret
            let spending_key = spend_priv + ss_scalar;
            Ok(Some(spending_key.to_bytes().to_vec()))
        } else {
            Ok(None)
        }
    }

    /// Compute key image for double-spend prevention.
    /// I = spending_key * H(spending_key * G)
    pub fn compute_key_image(spending_key: &[u8]) -> Result<KeyImage, String> {
        let sk = decode_scalar(spending_key)?;
        let pk = ProjectivePoint::GENERATOR * sk;

        // H(pk) - hash the public key to get a curve point
        let pk_bytes = pk.to_affine().to_bytes();
        let hp = hash_to_point(&pk_bytes);

        // I = sk * H(pk)
        let image = hp * sk;

        Ok(KeyImage {
            image: image.to_affine().to_bytes().to_vec(),
        })
    }
}

// ── Helpers ──────────────────────────────────────────────────────

fn generate_keypair() -> (Scalar, ProjectivePoint) {
    let mut bytes = [0u8; 32];
    rand::thread_rng().fill_bytes(&mut bytes);
    let scalar = <Scalar as Reduce<U256>>::reduce_bytes(&bytes.into());
    let point = ProjectivePoint::GENERATOR * scalar;
    (scalar, point)
}

fn decode_point(bytes: &[u8]) -> Result<ProjectivePoint, String> {
    let arr: [u8; 33] = bytes
        .try_into()
        .map_err(|_| format!("point must be 33 bytes compressed, got {}", bytes.len()))?;
    let affine = AffinePoint::from_bytes(&arr.into());
    if affine.is_some().into() {
        Ok(ProjectivePoint::from(affine.unwrap()))
    } else {
        Err("invalid curve point".to_string())
    }
}

fn decode_scalar(bytes: &[u8]) -> Result<Scalar, String> {
    if bytes.len() != 32 {
        return Err(format!("scalar must be 32 bytes, got {}", bytes.len()));
    }
    let mut arr = [0u8; 32];
    arr.copy_from_slice(bytes);
    Ok(<Scalar as Reduce<U256>>::reduce_bytes(&arr.into()))
}

fn hash_shared_point(point: &ProjectivePoint) -> [u8; 32] {
    let encoded = point.to_affine().to_encoded_point(false);
    let mut hasher = Sha256::new();
    hasher.update(b"QBC_stealth_shared_secret_v1");
    hasher.update(encoded.as_bytes());
    hasher.finalize().into()
}

/// Hash arbitrary data to a curve point (try-and-increment).
fn hash_to_point(data: &[u8]) -> ProjectivePoint {
    let mut counter = 0u32;
    loop {
        let mut hasher = Sha256::new();
        hasher.update(b"QBC_hash_to_point_v1");
        hasher.update(data);
        hasher.update(counter.to_le_bytes());
        let hash: [u8; 32] = hasher.finalize().into();

        let mut compressed = [0u8; 33];
        compressed[0] = 0x02;
        compressed[1..].copy_from_slice(&hash);

        let point = AffinePoint::from_bytes(&compressed.into());
        if point.is_some().into() {
            return ProjectivePoint::from(point.unwrap());
        }
        counter += 1;
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_generate_keypair() {
        let kp = StealthAddressManager::generate_keypair();
        assert_eq!(kp.spend_privkey.len(), 32);
        assert_eq!(kp.spend_pubkey.len(), 33);
        assert_eq!(kp.view_privkey.len(), 32);
        assert_eq!(kp.view_pubkey.len(), 33);
        assert_eq!(kp.public_address().len(), 66);
    }

    #[test]
    fn test_create_and_scan_output() {
        let recipient = StealthAddressManager::generate_keypair();
        let output = StealthAddressManager::create_output(
            &recipient.spend_pubkey,
            &recipient.view_pubkey,
        )
        .unwrap();

        assert_eq!(output.one_time_address.len(), 33);
        assert_eq!(output.ephemeral_pubkey.len(), 33);

        // Recipient scans and finds it
        let spending_key = StealthAddressManager::scan_output(
            &recipient,
            &output.ephemeral_pubkey,
            &output.one_time_address,
        )
        .unwrap();

        assert!(spending_key.is_some());
        assert_eq!(spending_key.unwrap().len(), 32);
    }

    #[test]
    fn test_scan_wrong_recipient_returns_none() {
        let recipient = StealthAddressManager::generate_keypair();
        let other = StealthAddressManager::generate_keypair();

        let output = StealthAddressManager::create_output(
            &recipient.spend_pubkey,
            &recipient.view_pubkey,
        )
        .unwrap();

        // Other person scans — should NOT match
        let result = StealthAddressManager::scan_output(
            &other,
            &output.ephemeral_pubkey,
            &output.one_time_address,
        )
        .unwrap();

        assert!(result.is_none());
    }

    #[test]
    fn test_key_image_deterministic() {
        let kp = StealthAddressManager::generate_keypair();
        let output = StealthAddressManager::create_output(
            &kp.spend_pubkey,
            &kp.view_pubkey,
        )
        .unwrap();

        let sk = StealthAddressManager::scan_output(
            &kp,
            &output.ephemeral_pubkey,
            &output.one_time_address,
        )
        .unwrap()
        .unwrap();

        let ki1 = StealthAddressManager::compute_key_image(&sk).unwrap();
        let ki2 = StealthAddressManager::compute_key_image(&sk).unwrap();
        assert_eq!(ki1.image, ki2.image);
    }

    #[test]
    fn test_different_outputs_different_addresses() {
        let kp = StealthAddressManager::generate_keypair();
        let o1 = StealthAddressManager::create_output(&kp.spend_pubkey, &kp.view_pubkey).unwrap();
        let o2 = StealthAddressManager::create_output(&kp.spend_pubkey, &kp.view_pubkey).unwrap();
        // Different ephemeral keys → different one-time addresses
        assert_ne!(o1.one_time_address, o2.one_time_address);
        assert_ne!(o1.ephemeral_pubkey, o2.ephemeral_pubkey);
    }

    #[test]
    fn test_public_address_hex() {
        let kp = StealthAddressManager::generate_keypair();
        let hex_addr = kp.public_address_hex();
        assert_eq!(hex_addr.len(), 132); // 66 bytes * 2
    }
}
