//! Bloom filter for privacy-preserving set membership queries.
//!
//! Uses SHA-256 double-hashing: h(i) = h1 + i * h2 for k hash functions.

use pyo3::prelude::*;
use sha2::{Digest, Sha256};

/// A probabilistic data structure for fast set membership testing.
#[pyclass]
#[derive(Clone)]
pub struct BloomFilter {
    bits: Vec<u8>,
    size: usize,
    hash_count: usize,
    count: usize,
}

impl BloomFilter {
    fn hash_indices(&self, item: &[u8]) -> Vec<usize> {
        let mut hasher1 = Sha256::new();
        hasher1.update(item);
        let h1_bytes = hasher1.finalize();

        let mut hasher2 = Sha256::new();
        hasher2.update(&h1_bytes);
        hasher2.update(b"bloom2");
        let h2_bytes = hasher2.finalize();

        let h1 = u64::from_le_bytes(h1_bytes[0..8].try_into().unwrap()) as usize;
        let h2 = u64::from_le_bytes(h2_bytes[0..8].try_into().unwrap()) as usize;

        let bit_size = self.size * 8;
        (0..self.hash_count)
            .map(|i| (h1.wrapping_add(i.wrapping_mul(h2))) % bit_size)
            .collect()
    }
}

#[pymethods]
impl BloomFilter {
    /// Create a new Bloom filter.
    ///
    /// Args:
    ///     size: Number of bytes in the bit array.
    ///     hash_count: Number of hash functions.
    #[new]
    pub fn new(size: usize, hash_count: usize) -> Self {
        Self {
            bits: vec![0u8; size],
            size,
            hash_count,
            count: 0,
        }
    }

    /// Insert an item into the filter.
    pub fn insert(&mut self, item: &str) {
        let indices = self.hash_indices(item.as_bytes());
        for idx in indices {
            let byte_idx = idx / 8;
            let bit_idx = idx % 8;
            self.bits[byte_idx] |= 1 << bit_idx;
        }
        self.count += 1;
    }

    /// Check if an item might be in the filter.
    ///
    /// Returns True if the item might be present (possible false positive),
    /// False if definitely not present.
    pub fn check(&self, item: &str) -> bool {
        let indices = self.hash_indices(item.as_bytes());
        for idx in indices {
            let byte_idx = idx / 8;
            let bit_idx = idx % 8;
            if self.bits[byte_idx] & (1 << bit_idx) == 0 {
                return false;
            }
        }
        true
    }

    /// Serialize the filter to bytes.
    pub fn to_bytes(&self) -> Vec<u8> {
        self.bits.clone()
    }

    /// Deserialize a filter from bytes.
    #[staticmethod]
    pub fn from_bytes(data: Vec<u8>, hash_count: usize) -> Self {
        let size = data.len();
        Self {
            bits: data,
            size,
            hash_count,
            count: 0, // Unknown after deserialization
        }
    }

    /// Merge another filter into this one (union).
    pub fn union(&mut self, other: &BloomFilter) {
        let min_len = self.bits.len().min(other.bits.len());
        for i in 0..min_len {
            self.bits[i] |= other.bits[i];
        }
    }

    /// Get the number of items inserted.
    pub fn item_count(&self) -> usize {
        self.count
    }

    /// Get the size of the filter in bytes.
    pub fn byte_size(&self) -> usize {
        self.size
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_insert_and_check() {
        let mut bf = BloomFilter::new(1024, 5);
        bf.insert("hello");
        bf.insert("world");
        assert!(bf.check("hello"));
        assert!(bf.check("world"));
        assert!(!bf.check("nonexistent"));
    }

    #[test]
    fn test_empty_filter() {
        let bf = BloomFilter::new(1024, 5);
        assert!(!bf.check("anything"));
    }

    #[test]
    fn test_serialization() {
        let mut bf = BloomFilter::new(256, 3);
        bf.insert("test1");
        bf.insert("test2");
        let bytes = bf.to_bytes();
        let bf2 = BloomFilter::from_bytes(bytes, 3);
        assert!(bf2.check("test1"));
        assert!(bf2.check("test2"));
        assert!(!bf2.check("test3"));
    }

    #[test]
    fn test_union() {
        let mut bf1 = BloomFilter::new(256, 3);
        bf1.insert("a");
        let mut bf2 = BloomFilter::new(256, 3);
        bf2.insert("b");
        bf1.union(&bf2);
        assert!(bf1.check("a"));
        assert!(bf1.check("b"));
    }

    #[test]
    fn test_item_count() {
        let mut bf = BloomFilter::new(1024, 5);
        assert_eq!(bf.item_count(), 0);
        bf.insert("x");
        assert_eq!(bf.item_count(), 1);
    }

    #[test]
    fn test_no_false_negatives() {
        let mut bf = BloomFilter::new(4096, 7);
        let items: Vec<String> = (0..100).map(|i| format!("item_{}", i)).collect();
        for item in &items {
            bf.insert(item);
        }
        for item in &items {
            assert!(bf.check(item), "False negative for {}", item);
        }
    }
}
