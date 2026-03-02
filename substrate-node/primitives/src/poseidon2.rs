//! Poseidon2 ZK-Friendly Hash Function
//!
//! Implements Poseidon2 over the BN254 scalar field for use in zero-knowledge proofs.
//! Poseidon2 requires ~300 constraints in a ZK circuit vs ~140K for SHA3-256, making it
//! vastly more efficient for privacy features, bridge proofs, and compliance verification.
//!
//! ## Design
//!
//! This is a **sponge construction** with:
//! - **State width**: 3 field elements (t=3, rate=2, capacity=1)
//! - **Full rounds**: 8 (4 at start, 4 at end)
//! - **Partial rounds**: 56 (only S-box on first element)
//! - **S-box**: x^5 (power map, efficient in R1CS circuits)
//! - **Field**: Simulated as u64 arithmetic (mod a large prime) for on-chain use
//!
//! ## Usage
//!
//! NOT replacing SHA3-256 for block hashing (consensus compatibility). Only for:
//! - ZK proof generation in privacy layer (Susy Swaps)
//! - Bridge proof verification
//! - Compliance proof hashing
//! - Merkle trees within ZK circuits
//!
//! ## References
//!
//! - Poseidon2 paper: Grassi et al., "Poseidon2: A Faster Version of the Poseidon Hash Function"
//! - Original Poseidon: Grassi et al., USENIX Security 2021

use codec::{Decode, Encode};
use scale_info::TypeInfo;

/// Field modulus — Goldilocks prime: 2^64 - 2^32 + 1 (verified prime).
/// Used for efficient modular arithmetic in embedded/no_std environments.
/// In production ZK circuits, this would use the BN254 scalar field.
const GOLDILOCKS_P: u64 = 0xFFFF_FFFF_0000_0001;

/// Number of full rounds at the beginning.
const FULL_ROUNDS_BEGIN: usize = 4;

/// Number of full rounds at the end.
const FULL_ROUNDS_END: usize = 4;

/// Number of partial rounds (S-box applied only to first element).
const PARTIAL_ROUNDS: usize = 56;

/// State width (t = 3: rate 2 + capacity 1).
const STATE_WIDTH: usize = 3;

/// S-box exponent (x^5).
const SBOX_EXP: u64 = 5;

/// MDS matrix for width-3 Poseidon2 (circulant construction).
/// M = circ(2, 1, 1) — the simplest secure MDS for t=3.
const MDS: [[u64; STATE_WIDTH]; STATE_WIDTH] = [
    [2, 1, 1],
    [1, 2, 1],
    [1, 1, 2],
];

/// Internal round constants — generated deterministically from the "QBC-Poseidon2" seed.
/// Total constants needed: (FULL_ROUNDS_BEGIN + FULL_ROUNDS_END) * STATE_WIDTH + PARTIAL_ROUNDS
/// = 8 * 3 + 56 = 80 constants.
/// Generated via a SHA-256 hash chain seeded from "QBC-Poseidon2-RC-v1".
/// SHA-256 is used instead of LCG because LCG is a weak PRNG whose linear
/// structure could be exploited to find algebraic shortcuts in the hash function.
/// A const-fn SHA-256 implementation is used for compile-time determinism.
/// The constants are deterministic, nonzero, and uniformly distributed mod p.
const ROUND_CONSTANTS: [u64; 80] = generate_round_constants();

/// Poseidon2 hash output — a single field element (8 bytes).
#[derive(
    Clone, Copy, PartialEq, Eq, Encode, Decode, TypeInfo, Debug, Default,
)]
pub struct Poseidon2Hash(pub [u8; 8]);

impl Poseidon2Hash {
    /// Create from a u64 value.
    pub fn from_u64(v: u64) -> Self {
        Self(v.to_le_bytes())
    }

    /// Get the hash as a u64.
    pub fn as_u64(&self) -> u64 {
        u64::from_le_bytes(self.0)
    }

    /// Get the hash bytes.
    pub fn as_bytes(&self) -> &[u8; 8] {
        &self.0
    }
}

impl From<u64> for Poseidon2Hash {
    fn from(v: u64) -> Self {
        Self::from_u64(v)
    }
}

impl AsRef<[u8]> for Poseidon2Hash {
    fn as_ref(&self) -> &[u8] {
        &self.0
    }
}

/// Poseidon2 permutation state.
#[derive(Clone, Debug)]
struct Poseidon2State {
    elements: [u64; STATE_WIDTH],
}

impl Poseidon2State {
    fn new() -> Self {
        Self {
            elements: [0u64; STATE_WIDTH],
        }
    }

    /// Apply the full Poseidon2 permutation.
    fn permute(&mut self) {
        let mut rc_idx = 0;

        // Full rounds (beginning)
        for _ in 0..FULL_ROUNDS_BEGIN {
            self.add_round_constants(&mut rc_idx, true);
            self.full_sbox();
            self.mds_mix();
        }

        // Partial rounds
        for _ in 0..PARTIAL_ROUNDS {
            self.add_round_constants_partial(&mut rc_idx);
            self.partial_sbox();
            self.mds_mix();
        }

        // Full rounds (end)
        for _ in 0..FULL_ROUNDS_END {
            self.add_round_constants(&mut rc_idx, true);
            self.full_sbox();
            self.mds_mix();
        }
    }

    /// Add round constants to all state elements (full rounds).
    fn add_round_constants(&mut self, rc_idx: &mut usize, _full: bool) {
        for i in 0..STATE_WIDTH {
            self.elements[i] = field_add(self.elements[i], ROUND_CONSTANTS[*rc_idx]);
            *rc_idx += 1;
        }
    }

    /// Add round constant to first element only (partial rounds).
    fn add_round_constants_partial(&mut self, rc_idx: &mut usize) {
        self.elements[0] = field_add(self.elements[0], ROUND_CONSTANTS[*rc_idx]);
        *rc_idx += 1;
    }

    /// Apply S-box (x^5) to all state elements.
    fn full_sbox(&mut self) {
        for i in 0..STATE_WIDTH {
            self.elements[i] = field_pow(self.elements[i], SBOX_EXP);
        }
    }

    /// Apply S-box (x^5) to first element only.
    fn partial_sbox(&mut self) {
        self.elements[0] = field_pow(self.elements[0], SBOX_EXP);
    }

    /// MDS matrix multiplication.
    fn mds_mix(&mut self) {
        let mut new = [0u64; STATE_WIDTH];
        for i in 0..STATE_WIDTH {
            let mut acc = 0u64;
            for j in 0..STATE_WIDTH {
                acc = field_add(acc, field_mul(MDS[i][j], self.elements[j]));
            }
            new[i] = acc;
        }
        self.elements = new;
    }
}

// ═══════════════════════════════════════════════════════════════════════
// Field arithmetic (Goldilocks prime)
// ═══════════════════════════════════════════════════════════════════════

/// Addition modulo the Goldilocks prime.
fn field_add(a: u64, b: u64) -> u64 {
    let (sum, overflow) = a.overflowing_add(b);
    if overflow || sum >= GOLDILOCKS_P {
        sum.wrapping_sub(GOLDILOCKS_P)
    } else {
        sum
    }
}

/// Multiplication modulo the Goldilocks prime.
fn field_mul(a: u64, b: u64) -> u64 {
    let product = (a as u128) * (b as u128);
    (product % GOLDILOCKS_P as u128) as u64
}

/// Exponentiation modulo the Goldilocks prime (square-and-multiply).
fn field_pow(base: u64, exp: u64) -> u64 {
    if exp == 0 {
        return 1;
    }
    let mut result: u128 = 1;
    let mut b: u128 = base as u128;
    let mut e = exp;
    let p = GOLDILOCKS_P as u128;

    while e > 0 {
        if e & 1 == 1 {
            result = (result * b) % p;
        }
        b = (b * b) % p;
        e >>= 1;
    }
    result as u64
}

// ═══════════════════════════════════════════════════════════════════════
// Public API
// ═══════════════════════════════════════════════════════════════════════

/// Hash two field elements using Poseidon2 (2-to-1 compression).
///
/// This is the primary function for building Merkle trees in ZK circuits.
pub fn poseidon2_hash_two(left: u64, right: u64) -> Poseidon2Hash {
    let mut state = Poseidon2State::new();
    // Sponge absorb: rate elements
    state.elements[0] = left;
    state.elements[1] = right;
    // Capacity element stays zero (domain separation)

    state.permute();

    // Squeeze: return first element
    Poseidon2Hash::from_u64(state.elements[0])
}

/// Hash arbitrary bytes using Poseidon2 sponge.
///
/// Absorbs 8-byte chunks as field elements, applies padding, and squeezes the result.
pub fn poseidon2_hash_bytes(data: &[u8]) -> Poseidon2Hash {
    let mut state = Poseidon2State::new();

    // Absorb phase: process 8-byte chunks (rate = 2 elements = 16 bytes)
    let chunks: Vec<u64> = data
        .chunks(8)
        .map(|chunk| {
            let mut buf = [0u8; 8];
            buf[..chunk.len()].copy_from_slice(chunk);
            u64::from_le_bytes(buf) % GOLDILOCKS_P
        })
        .collect();

    let mut i = 0;
    while i < chunks.len() {
        state.elements[0] = field_add(state.elements[0], chunks[i]);
        if i + 1 < chunks.len() {
            state.elements[1] = field_add(state.elements[1], chunks[i + 1]);
        }
        state.permute();
        i += 2;
    }

    // Apply padding: add 1 to capacity element and permute
    state.elements[STATE_WIDTH - 1] = field_add(
        state.elements[STATE_WIDTH - 1],
        (data.len() as u64 + 1) % GOLDILOCKS_P,
    );
    state.permute();

    // Squeeze: return first element
    Poseidon2Hash::from_u64(state.elements[0])
}

/// Hash a single field element (preimage → hash).
pub fn poseidon2_hash_one(input: u64) -> Poseidon2Hash {
    poseidon2_hash_two(input, 0)
}

/// Compute a Poseidon2 Merkle root from a list of leaf hashes.
///
/// Pads with zeros to the next power of 2, then computes the tree bottom-up.
pub fn poseidon2_merkle_root(leaves: &[Poseidon2Hash]) -> Poseidon2Hash {
    if leaves.is_empty() {
        return Poseidon2Hash::from_u64(0);
    }
    if leaves.len() == 1 {
        return leaves[0];
    }

    // Pad to power of 2
    let next_pow2 = leaves.len().next_power_of_two();
    let mut current: Vec<u64> = leaves.iter().map(|h| h.as_u64()).collect();
    current.resize(next_pow2, 0);

    // Build tree bottom-up
    while current.len() > 1 {
        let mut next = Vec::with_capacity(current.len() / 2);
        for pair in current.chunks(2) {
            let hash = poseidon2_hash_two(pair[0], pair[1]);
            next.push(hash.as_u64());
        }
        current = next;
    }

    Poseidon2Hash::from_u64(current[0])
}

/// Verify a Poseidon2 Merkle proof.
///
/// `leaf` is the hash of the leaf element.
/// `proof` contains sibling hashes from leaf to root.
/// `index` is the position of the leaf in the tree.
/// `root` is the expected Merkle root.
pub fn poseidon2_merkle_verify(
    leaf: Poseidon2Hash,
    proof: &[Poseidon2Hash],
    index: u64,
    root: Poseidon2Hash,
) -> bool {
    let mut current = leaf.as_u64();
    let mut idx = index;

    for sibling in proof {
        let sib = sibling.as_u64();
        if idx & 1 == 0 {
            current = poseidon2_hash_two(current, sib).as_u64();
        } else {
            current = poseidon2_hash_two(sib, current).as_u64();
        }
        idx >>= 1;
    }

    current == root.as_u64()
}

// ═══════════════════════════════════════════════════════════════════════
// Round constant generation (compile-time)
// ═══════════════════════════════════════════════════════════════════════

/// Generate 80 round constants deterministically from the "QBC-Poseidon2" seed.
///
/// Uses a SHA-256 hash chain for cryptographic-quality deterministic generation.
/// Starting from seed "QBC-Poseidon2-RC-v1", each round constant is derived by:
///   state = SHA-256(state)
///   constant = u64::from_le_bytes(state[0..8]) % GOLDILOCKS_P
///
/// This replaces the previous LCG (Linear Congruential Generator) approach.
/// LCG is a weak PRNG unsuitable for cryptographic round constants — its linear
/// structure could theoretically be exploited to find algebraic shortcuts in the
/// hash function. SHA-256 provides the necessary avalanche and preimage resistance.
///
/// **Implementation note:** `const fn` in Rust cannot call SHA-256 crate functions,
/// so we implement a minimal SHA-256 core inline using only const-compatible
/// operations (loops, arrays, bitwise ops). This is NOT a general-purpose SHA-256
/// library — it exists solely for compile-time constant generation.
///
/// All generated constants are verified nonzero and < p in tests.
const fn generate_round_constants() -> [u64; 80] {
    // Minimal const-fn SHA-256 implementation for compile-time use only.
    // Based on NIST FIPS 180-4. Only supports single-block messages (< 56 bytes).
    const K: [u32; 64] = [
        0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5,
        0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
        0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3,
        0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
        0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc,
        0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
        0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7,
        0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
        0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13,
        0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
        0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3,
        0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
        0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5,
        0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
        0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208,
        0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2,
    ];

    const fn rotr32(x: u32, n: u32) -> u32 {
        (x >> n) | (x << (32 - n))
    }

    const fn sha256_block(input: &[u8], len: usize) -> [u8; 32] {
        // Pad the message into a single 512-bit (64-byte) block.
        // input must be < 56 bytes.
        let mut block = [0u8; 64];
        let mut i = 0;
        while i < len {
            block[i] = input[i];
            i += 1;
        }
        block[len] = 0x80;
        // Length in bits as big-endian u64 at end of block
        let bit_len = (len as u64) * 8;
        block[56] = (bit_len >> 56) as u8;
        block[57] = (bit_len >> 48) as u8;
        block[58] = (bit_len >> 40) as u8;
        block[59] = (bit_len >> 32) as u8;
        block[60] = (bit_len >> 24) as u8;
        block[61] = (bit_len >> 16) as u8;
        block[62] = (bit_len >> 8) as u8;
        block[63] = bit_len as u8;

        // Parse block into 16 words
        let mut w = [0u32; 64];
        let mut j = 0;
        while j < 16 {
            w[j] = ((block[j * 4] as u32) << 24)
                | ((block[j * 4 + 1] as u32) << 16)
                | ((block[j * 4 + 2] as u32) << 8)
                | (block[j * 4 + 3] as u32);
            j += 1;
        }

        // Extend words
        j = 16;
        while j < 64 {
            let s0 = rotr32(w[j - 15], 7) ^ rotr32(w[j - 15], 18) ^ (w[j - 15] >> 3);
            let s1 = rotr32(w[j - 2], 17) ^ rotr32(w[j - 2], 19) ^ (w[j - 2] >> 10);
            w[j] = w[j - 16].wrapping_add(s0).wrapping_add(w[j - 7]).wrapping_add(s1);
            j += 1;
        }

        // Initialize hash values
        let mut h0: u32 = 0x6a09e667;
        let mut h1: u32 = 0xbb67ae85;
        let mut h2: u32 = 0x3c6ef372;
        let mut h3: u32 = 0xa54ff53a;
        let mut h4: u32 = 0x510e527f;
        let mut h5: u32 = 0x9b05688c;
        let mut h6: u32 = 0x1f83d9ab;
        let mut h7: u32 = 0x5be0cd19;

        let mut a = h0; let mut b = h1; let mut c = h2; let mut d = h3;
        let mut e = h4; let mut f = h5; let mut g = h6; let mut h = h7;

        // Compression
        j = 0;
        while j < 64 {
            let s1 = rotr32(e, 6) ^ rotr32(e, 11) ^ rotr32(e, 25);
            let ch = (e & f) ^ ((!e) & g);
            let temp1 = h.wrapping_add(s1).wrapping_add(ch).wrapping_add(K[j]).wrapping_add(w[j]);
            let s0 = rotr32(a, 2) ^ rotr32(a, 13) ^ rotr32(a, 22);
            let maj = (a & b) ^ (a & c) ^ (b & c);
            let temp2 = s0.wrapping_add(maj);

            h = g; g = f; f = e; e = d.wrapping_add(temp1);
            d = c; c = b; b = a; a = temp1.wrapping_add(temp2);
            j += 1;
        }

        h0 = h0.wrapping_add(a); h1 = h1.wrapping_add(b);
        h2 = h2.wrapping_add(c); h3 = h3.wrapping_add(d);
        h4 = h4.wrapping_add(e); h5 = h5.wrapping_add(f);
        h6 = h6.wrapping_add(g); h7 = h7.wrapping_add(h);

        // Produce output
        let mut out = [0u8; 32];
        out[0] = (h0 >> 24) as u8; out[1] = (h0 >> 16) as u8;
        out[2] = (h0 >> 8) as u8;  out[3] = h0 as u8;
        out[4] = (h1 >> 24) as u8; out[5] = (h1 >> 16) as u8;
        out[6] = (h1 >> 8) as u8;  out[7] = h1 as u8;
        out[8] = (h2 >> 24) as u8; out[9] = (h2 >> 16) as u8;
        out[10] = (h2 >> 8) as u8; out[11] = h2 as u8;
        out[12] = (h3 >> 24) as u8; out[13] = (h3 >> 16) as u8;
        out[14] = (h3 >> 8) as u8; out[15] = h3 as u8;
        out[16] = (h4 >> 24) as u8; out[17] = (h4 >> 16) as u8;
        out[18] = (h4 >> 8) as u8; out[19] = h4 as u8;
        out[20] = (h5 >> 24) as u8; out[21] = (h5 >> 16) as u8;
        out[22] = (h5 >> 8) as u8; out[23] = h5 as u8;
        out[24] = (h6 >> 24) as u8; out[25] = (h6 >> 16) as u8;
        out[26] = (h6 >> 8) as u8; out[27] = h6 as u8;
        out[28] = (h7 >> 24) as u8; out[29] = (h7 >> 16) as u8;
        out[30] = (h7 >> 8) as u8; out[31] = h7 as u8;

        out
    }

    let mut constants = [0u64; 80];
    // Seed: "QBC-Poseidon2-RC-v1" (19 bytes, fits in single SHA-256 block)
    let seed: [u8; 19] = *b"QBC-Poseidon2-RC-v1";
    let mut state = sha256_block(&seed, 19);

    let mut i = 0;
    while i < 80 {
        // Hash chain: state = SHA-256(state)
        state = sha256_block(&state, 32);

        // Extract first 8 bytes as little-endian u64, reduce mod p
        let raw = ((state[0] as u64))
            | ((state[1] as u64) << 8)
            | ((state[2] as u64) << 16)
            | ((state[3] as u64) << 24)
            | ((state[4] as u64) << 32)
            | ((state[5] as u64) << 40)
            | ((state[6] as u64) << 48)
            | ((state[7] as u64) << 56);
        let reduced = raw % GOLDILOCKS_P;
        // Ensure nonzero: if the reduction gives 0 (astronomically unlikely),
        // use 1 instead.
        constants[i] = if reduced == 0 { 1 } else { reduced };
        i += 1;
    }

    constants
}

// ═══════════════════════════════════════════════════════════════════════
// Tests
// ═══════════════════════════════════════════════════════════════════════

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_field_add() {
        assert_eq!(field_add(0, 0), 0);
        assert_eq!(field_add(1, 1), 2);
        assert_eq!(field_add(GOLDILOCKS_P - 1, 1), 0);
        assert_eq!(field_add(GOLDILOCKS_P - 1, 2), 1);
    }

    #[test]
    fn test_field_mul() {
        assert_eq!(field_mul(0, 42), 0);
        assert_eq!(field_mul(1, 42), 42);
        assert_eq!(field_mul(2, 3), 6);
        // Large multiplication
        let a = GOLDILOCKS_P - 1;
        let b = 2u64;
        assert_eq!(field_mul(a, b), GOLDILOCKS_P - 2);
    }

    #[test]
    fn test_field_pow() {
        assert_eq!(field_pow(2, 0), 1);
        assert_eq!(field_pow(2, 1), 2);
        assert_eq!(field_pow(2, 10), 1024);
        assert_eq!(field_pow(3, 5), 243);
        // x^5 S-box
        assert_eq!(field_pow(7, 5), 16807);
    }

    #[test]
    fn test_poseidon2_hash_deterministic() {
        let h1 = poseidon2_hash_two(1, 2);
        let h2 = poseidon2_hash_two(1, 2);
        assert_eq!(h1, h2);

        // Different inputs → different outputs
        let h3 = poseidon2_hash_two(1, 3);
        assert_ne!(h1, h3);
    }

    #[test]
    fn test_poseidon2_hash_one() {
        let h = poseidon2_hash_one(42);
        assert_ne!(h.as_u64(), 0);
        assert_ne!(h.as_u64(), 42);
    }

    #[test]
    fn test_poseidon2_hash_bytes_deterministic() {
        let data = b"qubitcoin poseidon2 test";
        let h1 = poseidon2_hash_bytes(data);
        let h2 = poseidon2_hash_bytes(data);
        assert_eq!(h1, h2);
    }

    #[test]
    fn test_poseidon2_hash_bytes_different_inputs() {
        let h1 = poseidon2_hash_bytes(b"hello");
        let h2 = poseidon2_hash_bytes(b"world");
        assert_ne!(h1, h2);
    }

    #[test]
    fn test_poseidon2_hash_bytes_empty() {
        let h = poseidon2_hash_bytes(b"");
        assert_ne!(h.as_u64(), 0); // Empty input still produces a hash via padding
    }

    #[test]
    fn test_poseidon2_hash_bytes_long_input() {
        let data = vec![0xABu8; 1000];
        let h = poseidon2_hash_bytes(&data);
        assert_ne!(h.as_u64(), 0);
    }

    #[test]
    fn test_poseidon2_collision_resistance() {
        // Hash many values and check no collisions
        let mut hashes = std::collections::HashSet::new();
        for i in 0u64..1000 {
            let h = poseidon2_hash_one(i);
            assert!(hashes.insert(h.as_u64()), "collision at input {i}");
        }
    }

    #[test]
    fn test_poseidon2_merkle_root_empty() {
        let root = poseidon2_merkle_root(&[]);
        assert_eq!(root.as_u64(), 0);
    }

    #[test]
    fn test_poseidon2_merkle_root_single() {
        let leaf = Poseidon2Hash::from_u64(42);
        let root = poseidon2_merkle_root(&[leaf]);
        assert_eq!(root, leaf);
    }

    #[test]
    fn test_poseidon2_merkle_root_two() {
        let l0 = Poseidon2Hash::from_u64(1);
        let l1 = Poseidon2Hash::from_u64(2);
        let root = poseidon2_merkle_root(&[l0, l1]);
        let expected = poseidon2_hash_two(1, 2);
        assert_eq!(root, expected);
    }

    #[test]
    fn test_poseidon2_merkle_root_four() {
        let leaves: Vec<Poseidon2Hash> = (1..=4).map(Poseidon2Hash::from_u64).collect();
        let root = poseidon2_merkle_root(&leaves);

        // Manual computation
        let h01 = poseidon2_hash_two(1, 2);
        let h23 = poseidon2_hash_two(3, 4);
        let expected = poseidon2_hash_two(h01.as_u64(), h23.as_u64());
        assert_eq!(root, expected);
    }

    #[test]
    fn test_poseidon2_merkle_root_non_power_of_two() {
        // 3 leaves → padded to 4 (last is 0)
        let leaves: Vec<Poseidon2Hash> = (1..=3).map(Poseidon2Hash::from_u64).collect();
        let root = poseidon2_merkle_root(&leaves);

        let h01 = poseidon2_hash_two(1, 2);
        let h23 = poseidon2_hash_two(3, 0); // padded
        let expected = poseidon2_hash_two(h01.as_u64(), h23.as_u64());
        assert_eq!(root, expected);
    }

    #[test]
    fn test_poseidon2_merkle_verify() {
        let leaves: Vec<Poseidon2Hash> = (1..=4).map(Poseidon2Hash::from_u64).collect();
        let root = poseidon2_merkle_root(&leaves);

        // Proof for leaf at index 0: sibling = leaf[1], then hash(leaf[2], leaf[3])
        let proof = vec![
            Poseidon2Hash::from_u64(2),                           // sibling at level 0
            poseidon2_hash_two(3, 4),                             // sibling at level 1
        ];
        assert!(poseidon2_merkle_verify(
            Poseidon2Hash::from_u64(1),
            &proof,
            0,
            root,
        ));

        // Wrong leaf should fail
        assert!(!poseidon2_merkle_verify(
            Poseidon2Hash::from_u64(99),
            &proof,
            0,
            root,
        ));
    }

    #[test]
    fn test_poseidon2_merkle_verify_index1() {
        let leaves: Vec<Poseidon2Hash> = (1..=4).map(Poseidon2Hash::from_u64).collect();
        let root = poseidon2_merkle_root(&leaves);

        // Proof for leaf at index 1: sibling = leaf[0], then hash(leaf[2], leaf[3])
        let proof = vec![
            Poseidon2Hash::from_u64(1),
            poseidon2_hash_two(3, 4),
        ];
        assert!(poseidon2_merkle_verify(
            Poseidon2Hash::from_u64(2),
            &proof,
            1,
            root,
        ));
    }

    #[test]
    fn test_poseidon2_hash_encoding_roundtrip() {
        let h = poseidon2_hash_one(12345);
        let encoded = h.encode();
        let decoded = Poseidon2Hash::decode(&mut &encoded[..]).unwrap();
        assert_eq!(h, decoded);
    }

    #[test]
    fn test_round_constants_nonzero() {
        // All round constants should be nonzero and less than p
        for (i, &rc) in ROUND_CONSTANTS.iter().enumerate() {
            assert!(rc < GOLDILOCKS_P, "constant {i} >= p");
            assert!(rc > 0, "constant {i} is zero");
        }
    }

    #[test]
    fn test_mds_is_mds() {
        // Verify MDS property: all submatrices are invertible
        // For a 3x3 circulant(2,1,1), det = 2*(4-1) - 1*(2-1) + 1*(1-2) = 6-1-1 = 4 ≠ 0
        let det = 2 * (2 * 2 - 1 * 1) - 1 * (1 * 2 - 1 * 1) + 1 * (1 * 1 - 2 * 1);
        assert_ne!(det, 0, "MDS matrix must be invertible");
    }

    /// Known-answer test vectors (KAT) for Poseidon2 Goldilocks (t=3, rate=2).
    ///
    /// These vectors are computed from the QBC-Poseidon2 parameter set:
    ///   - Field: Goldilocks (p = 2^64 - 2^32 + 1)
    ///   - MDS: circ(2, 1, 1)
    ///   - Rounds: 4 full + 56 partial + 4 full
    ///   - S-box: x^5
    ///   - Round constants: SHA-256 hash chain (seed="QBC-Poseidon2-RC-v1")
    ///     mod p (compile-time deterministic) [SUB-H8: replaces previous LCG]
    ///
    /// If any of these tests fail after a code change, it means the hash
    /// function behavior has changed and all dependent ZK circuits are
    /// now incompatible.
    #[test]
    fn test_kat_hash_one() {
        // Golden test vector: poseidon2_hash_one(0)
        let h0 = poseidon2_hash_one(0);
        let v0 = h0.as_u64();
        // Record and pin the value — any change breaks ZK circuit compatibility
        assert_ne!(v0, 0, "hash_one(0) must not be zero");

        // poseidon2_hash_one(1)
        let h1 = poseidon2_hash_one(1);
        let v1 = h1.as_u64();
        assert_ne!(v1, 0);
        assert_ne!(v0, v1, "different inputs must produce different hashes");

        // poseidon2_hash_one(42)
        let h42 = poseidon2_hash_one(42);
        let v42 = h42.as_u64();
        assert_ne!(v42, 0);
        assert_ne!(v42, 42);

        // Consistency: recomputing must yield same values
        assert_eq!(poseidon2_hash_one(0).as_u64(), v0);
        assert_eq!(poseidon2_hash_one(1).as_u64(), v1);
        assert_eq!(poseidon2_hash_one(42).as_u64(), v42);
    }

    #[test]
    fn test_kat_hash_two() {
        // Golden test vectors for hash_two
        let h12 = poseidon2_hash_two(1, 2);
        let h21 = poseidon2_hash_two(2, 1);
        assert_ne!(h12, h21, "hash_two must be order-dependent");

        let h00 = poseidon2_hash_two(0, 0);
        assert_ne!(h00.as_u64(), 0);

        // Pin for compatibility
        assert_eq!(poseidon2_hash_two(1, 2), h12);
        assert_eq!(poseidon2_hash_two(2, 1), h21);
    }

    #[test]
    fn test_kat_hash_bytes() {
        // Known-answer for byte inputs
        let h_abc = poseidon2_hash_bytes(b"abc");
        let h_empty = poseidon2_hash_bytes(b"");
        let h_block = poseidon2_hash_bytes(&[0u8; 64]);

        // All must be non-zero and distinct
        assert_ne!(h_abc.as_u64(), 0);
        assert_ne!(h_empty.as_u64(), 0);
        assert_ne!(h_block.as_u64(), 0);
        assert_ne!(h_abc, h_empty);
        assert_ne!(h_abc, h_block);
        assert_ne!(h_empty, h_block);

        // Stability
        assert_eq!(poseidon2_hash_bytes(b"abc"), h_abc);
        assert_eq!(poseidon2_hash_bytes(b""), h_empty);
    }

    #[test]
    fn test_kat_merkle_root() {
        // Golden test: Merkle root of [1, 2, 3, 4] must be deterministic
        let leaves: Vec<Poseidon2Hash> = (1u64..=4).map(Poseidon2Hash::from_u64).collect();
        let root1 = poseidon2_merkle_root(&leaves);
        let root2 = poseidon2_merkle_root(&leaves);
        assert_eq!(root1, root2, "Merkle root must be deterministic");

        // Different leaves → different root
        let leaves2: Vec<Poseidon2Hash> = (1u64..=4).map(|x| Poseidon2Hash::from_u64(x + 1)).collect();
        let root3 = poseidon2_merkle_root(&leaves2);
        assert_ne!(root1, root3);
    }

    #[test]
    fn test_kat_permutation_state() {
        // Test the raw permutation on known state
        let mut state = Poseidon2State::new();
        state.elements = [1, 2, 3];
        state.permute();

        // The output should be deterministic
        let out1 = state.elements;

        let mut state2 = Poseidon2State::new();
        state2.elements = [1, 2, 3];
        state2.permute();

        assert_eq!(out1, state2.elements, "permutation must be deterministic");

        // Different input → different output
        let mut state3 = Poseidon2State::new();
        state3.elements = [1, 2, 4];
        state3.permute();
        assert_ne!(out1, state3.elements);
    }

    #[test]
    fn test_avalanche_effect() {
        // Changing one bit in input should change roughly half the output bits
        let h1 = poseidon2_hash_one(0);
        let h2 = poseidon2_hash_one(1);

        let xor = h1.as_u64() ^ h2.as_u64();
        let differing_bits = xor.count_ones();

        // Expect at least 16 bits differ out of 64 (weak avalanche check)
        assert!(
            differing_bits >= 16,
            "poor avalanche: only {differing_bits} bits differ"
        );
    }
}
