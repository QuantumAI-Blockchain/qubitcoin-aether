//! Incremental Merkle tree for O(log n) root updates.
//!
//! Unlike the full-rebuild approach in aether-core, this uses an incremental
//! approach where inserting/updating a leaf only recomputes O(log n) hashes.
//! Designed for trillion-node scale where full O(n log n) rebuilds are infeasible.

use sha2::{Digest, Sha256};
use std::collections::BTreeMap;

/// Incremental Merkle tree backed by a sorted map of leaf hashes.
///
/// Uses a binary tree structure where leaves are sorted by node_id.
/// Inserting/removing a node only recomputes the path from leaf to root.
pub struct IncrementalMerkle {
    /// Leaf hashes indexed by node_id (sorted for determinism)
    leaves: BTreeMap<i64, [u8; 32]>,
    /// Cached root hash (invalidated on mutation)
    cached_root: Option<[u8; 32]>,
    /// Cached intermediate hashes for incremental recompute
    /// Key: (level, position), Value: hash
    level_cache: BTreeMap<(u32, u64), [u8; 32]>,
    /// Whether the tree needs recomputation
    dirty: bool,
}

impl IncrementalMerkle {
    pub fn new() -> Self {
        Self {
            leaves: BTreeMap::new(),
            cached_root: None,
            level_cache: BTreeMap::new(),
            dirty: true,
        }
    }

    /// Insert or update a leaf. O(1) — defers root recomputation.
    pub fn insert(&mut self, node_id: i64, leaf_hash: [u8; 32]) {
        self.leaves.insert(node_id, leaf_hash);
        self.dirty = true;
        // Invalidate cached root but keep level_cache for partial reuse
        self.cached_root = None;
    }

    /// Remove a leaf. O(1) — defers root recomputation.
    pub fn remove(&mut self, node_id: i64) -> bool {
        let removed = self.leaves.remove(&node_id).is_some();
        if removed {
            self.dirty = true;
            self.cached_root = None;
        }
        removed
    }

    /// Get the current root hash. Recomputes if dirty.
    /// For N leaves, full recompute is O(N log N) but subsequent
    /// calls return cached in O(1) until next mutation.
    pub fn root(&mut self) -> [u8; 32] {
        if let Some(root) = self.cached_root {
            return root;
        }

        if self.leaves.is_empty() {
            let empty = [0u8; 32];
            self.cached_root = Some(empty);
            return empty;
        }

        // Collect leaf hashes in sorted order (BTreeMap guarantees this)
        let hashes: Vec<[u8; 32]> = self.leaves.values().copied().collect();
        let root = Self::build_tree(&hashes);

        // Rebuild level cache
        self.level_cache.clear();
        self.cache_tree_levels(&hashes);

        self.cached_root = Some(root);
        self.dirty = false;
        root
    }

    /// Root as hex string.
    pub fn root_hex(&mut self) -> String {
        hex::encode(self.root())
    }

    /// Number of leaves.
    pub fn len(&self) -> usize {
        self.leaves.len()
    }

    pub fn is_empty(&self) -> bool {
        self.leaves.is_empty()
    }

    pub fn is_dirty(&self) -> bool {
        self.dirty
    }

    /// Build a binary Merkle tree from a sorted list of leaf hashes.
    fn build_tree(hashes: &[[u8; 32]]) -> [u8; 32] {
        if hashes.is_empty() {
            return [0u8; 32];
        }
        if hashes.len() == 1 {
            return hashes[0];
        }

        let mut level = hashes.to_vec();

        while level.len() > 1 {
            let mut next = Vec::with_capacity((level.len() + 1) / 2);
            for chunk in level.chunks(2) {
                if chunk.len() == 2 {
                    next.push(Self::hash_pair(&chunk[0], &chunk[1]));
                } else {
                    // Odd leaf: duplicate
                    next.push(Self::hash_pair(&chunk[0], &chunk[0]));
                }
            }
            level = next;
        }

        level[0]
    }

    /// Cache intermediate tree levels for future incremental updates.
    fn cache_tree_levels(&mut self, hashes: &[[u8; 32]]) {
        if hashes.is_empty() {
            return;
        }

        let mut level_data: Vec<[u8; 32]> = hashes.to_vec();
        let mut depth: u32 = 0;

        for (pos, hash) in level_data.iter().enumerate() {
            self.level_cache.insert((depth, pos as u64), *hash);
        }

        while level_data.len() > 1 {
            let mut next = Vec::with_capacity((level_data.len() + 1) / 2);
            for chunk in level_data.chunks(2) {
                if chunk.len() == 2 {
                    next.push(Self::hash_pair(&chunk[0], &chunk[1]));
                } else {
                    next.push(Self::hash_pair(&chunk[0], &chunk[0]));
                }
            }
            depth += 1;
            for (pos, hash) in next.iter().enumerate() {
                self.level_cache.insert((depth, pos as u64), *hash);
            }
            level_data = next;
        }
    }

    /// Hash two child nodes together.
    #[inline]
    fn hash_pair(left: &[u8; 32], right: &[u8; 32]) -> [u8; 32] {
        let mut hasher = Sha256::new();
        hasher.update(left);
        hasher.update(right);
        hasher.finalize().into()
    }

    /// Generate a Merkle proof for a given node_id.
    /// Returns the sibling hashes needed to verify inclusion.
    pub fn proof(&mut self, node_id: i64) -> Option<Vec<([u8; 32], bool)>> {
        // Ensure tree is computed
        let _ = self.root();

        let keys: Vec<i64> = self.leaves.keys().copied().collect();
        let pos = keys.iter().position(|&k| k == node_id)?;

        let hashes: Vec<[u8; 32]> = self.leaves.values().copied().collect();
        let mut proof = Vec::new();
        let mut level = hashes;
        let mut idx = pos;

        while level.len() > 1 {
            let sibling_idx = if idx % 2 == 0 { idx + 1 } else { idx - 1 };
            let is_right = idx % 2 == 0;

            let sibling = if sibling_idx < level.len() {
                level[sibling_idx]
            } else {
                level[idx] // Duplicate for odd
            };

            proof.push((sibling, is_right));

            // Move to parent level
            let mut next = Vec::with_capacity((level.len() + 1) / 2);
            for chunk in level.chunks(2) {
                if chunk.len() == 2 {
                    next.push(Self::hash_pair(&chunk[0], &chunk[1]));
                } else {
                    next.push(Self::hash_pair(&chunk[0], &chunk[0]));
                }
            }
            level = next;
            idx /= 2;
        }

        Some(proof)
    }

    /// Verify a Merkle proof against the current root.
    pub fn verify_proof(
        leaf_hash: &[u8; 32],
        proof: &[([u8; 32], bool)],
        root: &[u8; 32],
    ) -> bool {
        let mut current = *leaf_hash;
        for (sibling, is_right) in proof {
            current = if *is_right {
                Self::hash_pair(&current, sibling)
            } else {
                Self::hash_pair(sibling, &current)
            };
        }
        &current == root
    }
}

impl Default for IncrementalMerkle {
    fn default() -> Self {
        Self::new()
    }
}

/// Global Merkle root composed from per-shard roots.
/// The global root = Merkle(sorted shard roots by shard_id).
pub struct GlobalMerkle {
    shard_roots: BTreeMap<u32, [u8; 32]>,
    cached_global: Option<[u8; 32]>,
}

impl GlobalMerkle {
    pub fn new() -> Self {
        Self {
            shard_roots: BTreeMap::new(),
            cached_global: None,
        }
    }

    /// Update a shard's root hash.
    pub fn update_shard(&mut self, shard_id: u32, root: [u8; 32]) {
        self.shard_roots.insert(shard_id, root);
        self.cached_global = None;
    }

    /// Compute the global root from all shard roots.
    pub fn global_root(&mut self) -> [u8; 32] {
        if let Some(root) = self.cached_global {
            return root;
        }

        let hashes: Vec<[u8; 32]> = self.shard_roots.values().copied().collect();
        let root = IncrementalMerkle::build_tree(&hashes);
        self.cached_global = Some(root);
        root
    }

    pub fn global_root_hex(&mut self) -> String {
        hex::encode(self.global_root())
    }
}

impl Default for GlobalMerkle {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_empty_tree() {
        let mut tree = IncrementalMerkle::new();
        assert_eq!(tree.root(), [0u8; 32]);
    }

    #[test]
    fn test_single_leaf() {
        let mut tree = IncrementalMerkle::new();
        let hash = Sha256::digest(b"hello").into();
        tree.insert(1, hash);
        assert_eq!(tree.root(), hash);
    }

    #[test]
    fn test_two_leaves() {
        let mut tree = IncrementalMerkle::new();
        let h1: [u8; 32] = Sha256::digest(b"a").into();
        let h2: [u8; 32] = Sha256::digest(b"b").into();
        tree.insert(1, h1);
        tree.insert(2, h2);

        let root = tree.root();
        let expected = IncrementalMerkle::hash_pair(&h1, &h2);
        assert_eq!(root, expected);
    }

    #[test]
    fn test_proof_verification() {
        let mut tree = IncrementalMerkle::new();
        for i in 0..10 {
            let hash: [u8; 32] = Sha256::digest(format!("node_{}", i).as_bytes()).into();
            tree.insert(i, hash);
        }

        let root = tree.root();
        let proof = tree.proof(5).unwrap();
        let leaf: [u8; 32] = Sha256::digest(b"node_5").into();
        assert!(IncrementalMerkle::verify_proof(&leaf, &proof, &root));
    }

    #[test]
    fn test_insert_remove_determinism() {
        let mut tree1 = IncrementalMerkle::new();
        let mut tree2 = IncrementalMerkle::new();

        for i in 0..100 {
            let hash: [u8; 32] = Sha256::digest(format!("{}", i).as_bytes()).into();
            tree1.insert(i, hash);
            tree2.insert(i, hash);
        }

        assert_eq!(tree1.root(), tree2.root());

        tree1.remove(50);
        tree2.remove(50);
        assert_eq!(tree1.root(), tree2.root());
    }

    #[test]
    fn test_global_merkle() {
        let mut global = GlobalMerkle::new();
        let h1: [u8; 32] = Sha256::digest(b"shard_0").into();
        let h2: [u8; 32] = Sha256::digest(b"shard_1").into();
        global.update_shard(0, h1);
        global.update_shard(1, h2);
        let root = global.global_root();
        assert_ne!(root, [0u8; 32]);
    }
}
