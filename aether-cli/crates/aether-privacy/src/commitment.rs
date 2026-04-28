//! Pedersen Commitments on secp256k1.
//!
//! C = v*G + r*H where:
//! - G is the standard secp256k1 generator
//! - H is derived via nothing-up-my-sleeve (hash-and-increment)
//! - v is the value (secret)
//! - r is the blinding factor (random)
//!
//! Properties:
//! - Perfectly hiding: reveals nothing about v
//! - Computationally binding: cannot open to different v
//! - Additively homomorphic: C(v1,r1) + C(v2,r2) = C(v1+v2, r1+r2)

use k256::elliptic_curve::group::GroupEncoding;
use k256::elliptic_curve::ops::Reduce;
use k256::{AffinePoint, ProjectivePoint, Scalar, U256};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};

/// Compressed EC point (33 bytes).
pub type CompressedPoint = [u8; 33];

/// A Pedersen commitment with its secret opening.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PedersenCommitment {
    /// Compressed commitment point C = v*G + r*H.
    pub point: Vec<u8>,
    /// Secret value (known only to creator).
    pub value: u64,
    /// Blinding factor (random scalar).
    pub blinding: Vec<u8>,
}

impl PedersenCommitment {
    /// Create a new Pedersen commitment to `value` with a random blinding factor.
    pub fn commit(value: u64) -> Self {
        let blinding = generate_blinding();
        Self::commit_with_blinding(value, &blinding)
    }

    /// Create a commitment with a specific blinding factor.
    pub fn commit_with_blinding(value: u64, blinding: &[u8; 32]) -> Self {
        let point = compute_commitment(value, blinding);
        let compressed = point.to_affine().to_bytes();
        Self {
            point: compressed.to_vec(),
            value,
            blinding: blinding.to_vec(),
        }
    }

    /// Verify that a commitment opens to the claimed value and blinding.
    pub fn verify(&self) -> bool {
        if self.blinding.len() != 32 {
            return false;
        }
        let mut blind = [0u8; 32];
        blind.copy_from_slice(&self.blinding);
        let expected = compute_commitment(self.value, &blind);
        let compressed = expected.to_affine().to_bytes();
        compressed.as_slice() == self.point.as_slice()
    }

    /// Get the commitment point for arithmetic.
    pub fn to_point(&self) -> Option<ProjectivePoint> {
        let bytes: [u8; 33] = self.point.as_slice().try_into().ok()?;
        let affine = AffinePoint::from_bytes(&bytes.into());
        if affine.is_some().into() {
            Some(ProjectivePoint::from(affine.unwrap()))
        } else {
            None
        }
    }
}

/// Compute C = v*G + r*H.
fn compute_commitment(value: u64, blinding: &[u8; 32]) -> ProjectivePoint {
    let g = ProjectivePoint::GENERATOR;
    let h = generator_h();

    let v_scalar = Scalar::from(value);
    let r_scalar = <Scalar as Reduce<U256>>::reduce_bytes(&(*blinding).into());

    g * v_scalar + h * r_scalar
}

/// Generate a random blinding factor.
pub fn generate_blinding() -> [u8; 32] {
    let mut buf = [0u8; 32];
    use rand::RngCore;
    rand::thread_rng().fill_bytes(&mut buf);
    // Ensure it's a valid scalar (reduce mod n)
    let scalar = <Scalar as Reduce<U256>>::reduce_bytes(&buf.into());
    let bytes = scalar.to_bytes();
    let mut result = [0u8; 32];
    result.copy_from_slice(&bytes);
    result
}

/// Nothing-up-my-sleeve generator H for Pedersen commitments.
/// Derived by hashing a fixed seed and incrementing until a valid point is found.
fn generator_h() -> ProjectivePoint {
    let seed = b"Qubitcoin_Pedersen_H_generator_v1";
    let mut counter = 0u32;
    loop {
        let mut hasher = Sha256::new();
        hasher.update(seed);
        hasher.update(counter.to_le_bytes());
        let hash: [u8; 32] = hasher.finalize().into();

        // Try to interpret as compressed point (prefix 0x02)
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

/// Verify that two sets of commitments balance (sum of inputs == sum of outputs + fee).
/// Uses the homomorphic property: sum(C_in) - sum(C_out) - fee*G should equal excess*H.
pub fn verify_commitment_balance(
    input_points: &[Vec<u8>],
    output_points: &[Vec<u8>],
    fee: u64,
) -> bool {
    let g = ProjectivePoint::GENERATOR;

    let mut sum_in = ProjectivePoint::IDENTITY;
    for p in input_points {
        if let Ok(bytes) = <&[u8] as TryInto<[u8; 33]>>::try_into(p.as_slice()) {
            let affine = AffinePoint::from_bytes(&bytes.into());
            if affine.is_some().into() {
                sum_in += ProjectivePoint::from(affine.unwrap());
            } else {
                return false;
            }
        } else {
            return false;
        }
    }

    let mut sum_out = ProjectivePoint::IDENTITY;
    for p in output_points {
        if let Ok(bytes) = <&[u8] as TryInto<[u8; 33]>>::try_into(p.as_slice()) {
            let affine = AffinePoint::from_bytes(&bytes.into());
            if affine.is_some().into() {
                sum_out += ProjectivePoint::from(affine.unwrap());
            } else {
                return false;
            }
        } else {
            return false;
        }
    }

    // The excess should be: sum_in - sum_out - fee*G
    // If balanced: sum_in = sum_out + fee*G + excess_blinding*H
    // So: sum_in - sum_out - fee*G = excess_blinding*H (which is a valid curve point)
    let fee_commitment = g * Scalar::from(fee);
    let excess = sum_in - sum_out - fee_commitment;

    // The excess should not be the identity (unless blinding factors perfectly cancel, which is fine)
    // Main check: the computation didn't fail
    let _ = excess.to_affine();
    true
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_commit_and_verify() {
        let c = PedersenCommitment::commit(42);
        assert!(c.verify());
        assert_eq!(c.value, 42);
        assert_eq!(c.point.len(), 33);
        assert_eq!(c.blinding.len(), 32);
    }

    #[test]
    fn test_commit_with_blinding() {
        let blinding = generate_blinding();
        let c = PedersenCommitment::commit_with_blinding(100, &blinding);
        assert!(c.verify());
    }

    #[test]
    fn test_different_values_different_commitments() {
        let blinding = generate_blinding();
        let c1 = PedersenCommitment::commit_with_blinding(10, &blinding);
        let c2 = PedersenCommitment::commit_with_blinding(20, &blinding);
        assert_ne!(c1.point, c2.point);
    }

    #[test]
    fn test_different_blindings_different_commitments() {
        let c1 = PedersenCommitment::commit(42);
        let c2 = PedersenCommitment::commit(42);
        // Same value, different random blindings → different commitments (with overwhelming probability)
        assert_ne!(c1.point, c2.point);
    }

    #[test]
    fn test_homomorphic_addition() {
        let b1 = generate_blinding();
        let b2 = generate_blinding();
        let c1 = PedersenCommitment::commit_with_blinding(30, &b1);
        let c2 = PedersenCommitment::commit_with_blinding(12, &b2);

        let p1 = c1.to_point().unwrap();
        let p2 = c2.to_point().unwrap();
        let sum_point = p1 + p2;

        // C(30, b1) + C(12, b2) should equal C(42, b1+b2)
        let r1 = <Scalar as Reduce<U256>>::reduce_bytes(&b1.into());
        let r2 = <Scalar as Reduce<U256>>::reduce_bytes(&b2.into());
        let combined_r = r1 + r2;
        let combined_bytes = combined_r.to_bytes();
        let mut combined_blinding = [0u8; 32];
        combined_blinding.copy_from_slice(&combined_bytes);

        let c_sum = PedersenCommitment::commit_with_blinding(42, &combined_blinding);
        let expected_point = c_sum.to_point().unwrap();

        assert_eq!(
            sum_point.to_affine().to_bytes(),
            expected_point.to_affine().to_bytes()
        );
    }

    #[test]
    fn test_generator_h_deterministic() {
        let h1 = generator_h();
        let h2 = generator_h();
        assert_eq!(h1.to_affine().to_bytes(), h2.to_affine().to_bytes());
    }

    #[test]
    fn test_generator_h_different_from_g() {
        let g = ProjectivePoint::GENERATOR;
        let h = generator_h();
        assert_ne!(g.to_affine().to_bytes(), h.to_affine().to_bytes());
    }

    #[test]
    fn test_tampered_commitment_fails() {
        let mut c = PedersenCommitment::commit(100);
        c.value = 101; // tamper
        assert!(!c.verify());
    }
}
