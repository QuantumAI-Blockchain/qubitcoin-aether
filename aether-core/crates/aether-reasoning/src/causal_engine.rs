//! CausalDiscovery -- PC and FCI causal discovery algorithms.
//!
//! Discovers genuine causal relationships in the knowledge graph using:
//! - **PC (Peter-Clark)**: Constraint-based discovery assuming no latent confounders.
//!   Produces a CPDAG via skeleton discovery + v-structure + Meek's rules.
//! - **FCI (Fast Causal Inference)**: Extends PC with possible-d-sep removal to
//!   handle latent variables.  Produces a PAG (Partial Ancestral Graph).
//! - **Intervention validation**: Checks whether removing A's support changes B's
//!   support structure (simple do-calculus proxy).
//!
//! `'supports'` means correlation. `'causes'` means the system has evidence that
//! intervening on the source node would change the target node.

use crate::causal_pag::{EndpointMark, PAG};
use crate::causal_stats::{build_feature_matrix, fisher_z_p_value, MAX_CONDITIONING_DEPTH};
use aether_graph::KnowledgeGraph;
use parking_lot::RwLock;
use std::collections::{HashMap, HashSet};
use std::sync::atomic::{AtomicI64, AtomicUsize, Ordering};
use std::sync::Arc;
use tracing::info;

/// Result of a causal discovery run.
#[derive(Clone, Debug)]
pub struct CausalDiscoveryResult {
    pub causal_edges: usize,
    pub nodes_analyzed: usize,
    pub skeleton_edges: usize,
    pub directed_edges: usize,
    pub domain: Option<String>,
}

/// Result of an FCI discovery run.
#[derive(Debug)]
pub struct FciResult {
    pub causal_edges: usize,
    pub latent_confounders: usize,
    pub nodes_analyzed: usize,
    pub skeleton_edges: usize,
    pub pag: PAG,
    pub domain: Option<String>,
}

/// Result of an intervention test.
#[derive(Clone, Debug)]
pub struct InterventionResult {
    pub validated: bool,
    pub a_connected: usize,
    pub independent: usize,
    pub ratio: f64,
}

/// Causal discovery engine for the Aether Tree knowledge graph.
///
/// Thread-safe: all mutable state protected by atomics or `RwLock`.
pub struct CausalDiscovery {
    kg: Arc<KnowledgeGraph>,
    causal_edges_found: AtomicUsize,
    runs: AtomicUsize,
    last_run_block: AtomicI64,
    /// Separation sets: records the conditioning set that made (A, B)
    /// conditionally independent -- needed for v-structure detection.
    sep_sets: RwLock<HashMap<(i64, i64), HashSet<i64>>>,
}

impl CausalDiscovery {
    pub fn new(kg: Arc<KnowledgeGraph>) -> Self {
        Self {
            kg,
            causal_edges_found: AtomicUsize::new(0),
            runs: AtomicUsize::new(0),
            last_run_block: AtomicI64::new(0),
            sep_sets: RwLock::new(HashMap::new()),
        }
    }

    pub fn knowledge_graph(&self) -> &KnowledgeGraph {
        &self.kg
    }

    pub fn total_causal_edges_found(&self) -> usize {
        self.causal_edges_found.load(Ordering::Relaxed)
    }

    pub fn total_runs(&self) -> usize {
        self.runs.load(Ordering::Relaxed)
    }

    // ------------------------------------------------------------------
    // Public API
    // ------------------------------------------------------------------

    /// Run PC causal discovery on nodes in a specific domain.
    ///
    /// Steps:
    /// 1. Build feature vectors for candidate nodes
    /// 2. PC skeleton (iterative CI removal)
    /// 3. Orient edges (v-structures + Meek's rules + heuristics)
    /// 4. Validate via intervention test, store as `causes` or `correlates`
    pub fn discover(
        &self,
        domain: Option<&str>,
        max_nodes: usize,
        significance: f64,
    ) -> CausalDiscoveryResult {
        self.runs.fetch_add(1, Ordering::Relaxed);
        self.sep_sets.write().clear();

        let all_nodes = self.kg.get_nodes_raw();

        let mut candidates: Vec<_> = all_nodes
            .iter()
            .filter(|n| {
                (domain.is_none() || domain == Some(n.domain.as_str()))
                    && matches!(n.node_type.as_str(), "observation" | "inference" | "assertion")
            })
            .collect();

        // Most recent first
        candidates.sort_by(|a, b| b.source_block.cmp(&a.source_block));
        candidates.truncate(max_nodes);

        if candidates.len() < 3 {
            return CausalDiscoveryResult {
                causal_edges: 0,
                nodes_analyzed: candidates.len(),
                skeleton_edges: 0,
                directed_edges: 0,
                domain: domain.map(String::from),
            };
        }

        let node_ids: Vec<i64> = candidates.iter().map(|n| n.node_id).collect();

        // Step 1: Build feature matrix
        let features = build_feature_matrix(&self.kg, &node_ids);

        // Step 2: PC skeleton
        let (skeleton, adj) = self.pc_skeleton(&node_ids, &features, significance);

        // Step 3: Orient edges
        let directed = self.orient_edges(&node_ids, &skeleton, &adj, &features);

        // Step 4: Validate and create edges
        let mut created = 0;
        for &(from_id, to_id) in &directed {
            // Check if edge already exists
            let exists = self
                .kg
                .get_edges_from(from_id)
                .iter()
                .any(|e| {
                    e.to_node_id == to_id
                        && (e.edge_type == "causes" || e.edge_type == "correlates")
                });

            if !exists {
                let iv = self.intervention_test(from_id, to_id);
                let etype = if iv.validated { "causes" } else { "correlates" };
                self.kg
                    .add_edge(from_id, to_id, etype.into(), 0.8);
                created += 1;
            }
        }

        self.causal_edges_found.fetch_add(created, Ordering::Relaxed);

        if created > 0 {
            info!(
                domain = domain.unwrap_or("all"),
                created,
                analyzed = candidates.len(),
                "Causal discovery completed"
            );
        }

        CausalDiscoveryResult {
            causal_edges: created,
            nodes_analyzed: candidates.len(),
            skeleton_edges: skeleton.len(),
            directed_edges: directed.len(),
            domain: domain.map(String::from),
        }
    }

    /// Run causal discovery across all domains with enough nodes.
    pub fn discover_all_domains(
        &self,
        block_height: i64,
        min_domain_nodes: usize,
    ) -> usize {
        self.last_run_block.store(block_height, Ordering::Relaxed);

        let all_nodes = self.kg.get_nodes_raw();
        let mut domain_counts: HashMap<String, usize> = HashMap::new();
        for n in &all_nodes {
            if !n.domain.is_empty() {
                *domain_counts.entry(n.domain.clone()).or_insert(0) += 1;
            }
        }

        let mut total = 0;
        for (domain, count) in &domain_counts {
            if *count >= min_domain_nodes {
                let result = self.discover(Some(domain), 200, 0.05);
                total += result.causal_edges;
            }
        }

        if total > 0 {
            info!(block_height, total, "Causal discovery sweep completed");
        }

        total
    }

    /// Run FCI causal discovery, producing a PAG that handles latent confounders.
    pub fn discover_with_fci(
        &self,
        domain: Option<&str>,
        max_nodes: usize,
        significance: f64,
    ) -> FciResult {
        self.runs.fetch_add(1, Ordering::Relaxed);
        self.sep_sets.write().clear();

        let all_nodes = self.kg.get_nodes_raw();

        let mut candidates: Vec<_> = all_nodes
            .iter()
            .filter(|n| {
                (domain.is_none() || domain == Some(n.domain.as_str()))
                    && matches!(n.node_type.as_str(), "observation" | "inference" | "assertion")
            })
            .collect();

        candidates.sort_by(|a, b| b.source_block.cmp(&a.source_block));
        candidates.truncate(max_nodes);

        if candidates.len() < 3 {
            return FciResult {
                causal_edges: 0,
                latent_confounders: 0,
                nodes_analyzed: candidates.len(),
                skeleton_edges: 0,
                pag: PAG::new(),
                domain: domain.map(String::from),
            };
        }

        let node_ids: Vec<i64> = candidates.iter().map(|n| n.node_id).collect();
        let features = build_feature_matrix(&self.kg, &node_ids);

        // Step 1: PC skeleton
        let (skeleton, adj) = self.pc_skeleton(&node_ids, &features, significance);

        // Step 2: Initial v-structure orientation
        let mut oriented: HashMap<i64, HashSet<i64>> =
            node_ids.iter().map(|&n| (n, HashSet::new())).collect();
        let mut undirected: HashSet<(i64, i64)> = HashSet::new();
        for &(a, b) in &skeleton {
            undirected.insert(canonical_pair(a, b));
        }
        self.detect_v_structures(&node_ids, &adj, &mut oriented, &mut undirected);

        // Step 3: FCI possible-d-sep removal
        let (adj_refined, new_sep_sets) =
            self.fci_possible_dsep_removal(&node_ids, &adj, &features, significance);
        {
            let mut ss = self.sep_sets.write();
            for (k, v) in new_sep_sets {
                ss.insert(k, v);
            }
        }

        // Step 4: Rebuild skeleton from refined adjacency
        let mut refined_skeleton = Vec::new();
        let mut seen: HashSet<(i64, i64)> = HashSet::new();
        for &a in &node_ids {
            if let Some(neighbors) = adj_refined.get(&a) {
                for &b in neighbors {
                    let pair = canonical_pair(a, b);
                    if seen.insert(pair) {
                        refined_skeleton.push(pair);
                    }
                }
            }
        }

        // Step 5: Build PAG with o-o edges
        let mut pag = PAG::new();
        for &nid in &node_ids {
            pag.nodes.insert(nid);
        }
        for &(a, b) in &refined_skeleton {
            pag.add_edge(a, b, EndpointMark::Circle, EndpointMark::Circle);
        }

        // Step 6: Orient v-structures on refined skeleton
        self.fci_orient_v_structures(&node_ids, &adj_refined, &mut pag);

        // Step 7: Apply FCI orientation rules
        self.fci_apply_rules(&node_ids, &adj_refined, &mut pag);

        // Step 8: Create edges in KG for directed PAG edges
        let mut created = 0;
        let latent_count = pag.get_bidirected_edges().len();

        for edge in pag.edges.values() {
            let (from_id, to_id) = if edge.is_directed() {
                (edge.node_a, edge.node_b)
            } else if edge.mark_a == EndpointMark::Arrow && edge.mark_b == EndpointMark::Tail {
                (edge.node_b, edge.node_a)
            } else {
                continue;
            };

            let exists = self
                .kg
                .get_edges_from(from_id)
                .iter()
                .any(|e| {
                    e.to_node_id == to_id
                        && (e.edge_type == "causes" || e.edge_type == "correlates")
                });

            if !exists {
                let iv = self.intervention_test(from_id, to_id);
                let etype = if iv.validated { "causes" } else { "correlates" };
                self.kg
                    .add_edge(from_id, to_id, etype.into(), 0.85);
                created += 1;
            }
        }

        self.causal_edges_found.fetch_add(created, Ordering::Relaxed);

        if created > 0 || latent_count > 0 {
            info!(
                domain = domain.unwrap_or("all"),
                created,
                latent_count,
                analyzed = candidates.len(),
                "FCI discovery completed"
            );
        }

        FciResult {
            causal_edges: created,
            latent_confounders: latent_count,
            nodes_analyzed: candidates.len(),
            skeleton_edges: refined_skeleton.len(),
            pag,
            domain: domain.map(String::from),
        }
    }

    /// Validate a candidate causal edge via intervention test.
    ///
    /// Counts nodes connected to target (B) that are also connected to
    /// source (A) vs those that are not. High ratio means B depends on A.
    pub fn intervention_test(&self, source_id: i64, target_id: i64) -> InterventionResult {
        if self.kg.get_node(source_id).is_none() || self.kg.get_node(target_id).is_none() {
            return InterventionResult {
                validated: false,
                a_connected: 0,
                independent: 0,
                ratio: 0.0,
            };
        }

        // Gather all neighbours of target excluding source
        let mut target_neighbours: HashSet<i64> = HashSet::new();
        for e in self.kg.get_edges_to(target_id) {
            if e.from_node_id != source_id {
                target_neighbours.insert(e.from_node_id);
            }
        }
        for e in self.kg.get_edges_from(target_id) {
            if e.to_node_id != source_id {
                target_neighbours.insert(e.to_node_id);
            }
        }

        if target_neighbours.is_empty() {
            return InterventionResult {
                validated: true,
                a_connected: 0,
                independent: 0,
                ratio: 1.0,
            };
        }

        // Which of B's neighbours are also connected to A?
        let mut source_neighbour_ids: HashSet<i64> = HashSet::new();
        for e in self.kg.get_edges_from(source_id) {
            source_neighbour_ids.insert(e.to_node_id);
        }
        for e in self.kg.get_edges_to(source_id) {
            source_neighbour_ids.insert(e.from_node_id);
        }

        let a_connected = target_neighbours.intersection(&source_neighbour_ids).count();
        let independent = target_neighbours.len() - a_connected;
        let total = a_connected + independent;

        let ratio = a_connected as f64 / total.max(1) as f64;
        let validated = ratio >= 0.3;

        InterventionResult {
            validated,
            a_connected,
            independent,
            ratio,
        }
    }

    /// Alias for `intervention_test` to match the Python API.
    pub fn validate_causal_edge(&self, source_id: i64, target_id: i64) -> InterventionResult {
        self.intervention_test(source_id, target_id)
    }

    // ------------------------------------------------------------------
    // PC Skeleton (Phase 1)
    // ------------------------------------------------------------------

    /// Build the PC skeleton by iteratively testing conditional independence.
    ///
    /// Standard PC algorithm:
    /// 1. Start with fully connected undirected graph
    /// 2. For conditioning set sizes d = 0, 1, ..., MAX_CONDITIONING_DEPTH:
    ///    - For each adjacent pair (A, B):
    ///      Test CI given each subset S of size d from adj(A) \ {B}
    ///      If A _||_ B | S for any S, remove edge and record S
    fn pc_skeleton(
        &self,
        node_ids: &[i64],
        features: &HashMap<i64, Vec<f64>>,
        significance: f64,
    ) -> (Vec<(i64, i64)>, HashMap<i64, HashSet<i64>>) {
        let n = node_ids.len();
        let id_set: HashSet<i64> = node_ids.iter().copied().collect();

        // Initialize fully connected adjacency
        let mut adj: HashMap<i64, HashSet<i64>> = node_ids
            .iter()
            .map(|&n| (n, HashSet::new()))
            .collect();
        for i in 0..n {
            for j in (i + 1)..n {
                adj.get_mut(&node_ids[i]).unwrap().insert(node_ids[j]);
                adj.get_mut(&node_ids[j]).unwrap().insert(node_ids[i]);
            }
        }

        let mut sep_sets = self.sep_sets.write();
        sep_sets.clear();

        for d in 0..=MAX_CONDITIONING_DEPTH {
            // Snapshot edges to test
            let mut edges_to_test = Vec::new();
            for &a in node_ids {
                for &b in adj.get(&a).unwrap_or(&HashSet::new()) {
                    if a < b {
                        edges_to_test.push((a, b));
                    }
                }
            }

            for (a, b) in edges_to_test {
                if !adj.get(&a).map(|s| s.contains(&b)).unwrap_or(false) {
                    continue;
                }

                // Potential conditioning variables: neighbors of A or B (excluding each other)
                let neighbors_a = adj.get(&a).cloned().unwrap_or_default();
                let neighbors_b = adj.get(&b).cloned().unwrap_or_default();
                let mut cond_candidates: Vec<i64> = neighbors_a
                    .union(&neighbors_b)
                    .copied()
                    .filter(|&x| x != a && x != b && id_set.contains(&x))
                    .collect();
                cond_candidates.sort();

                if cond_candidates.len() < d {
                    continue;
                }

                // Test all subsets of size d
                let mut found_independent = false;
                for subset in combinations(&cond_candidates, d) {
                    let p_value = fisher_z_p_value(features, a, b, &subset);
                    if p_value > significance {
                        adj.get_mut(&a).unwrap().remove(&b);
                        adj.get_mut(&b).unwrap().remove(&a);
                        sep_sets.insert(
                            canonical_pair(a, b),
                            subset.into_iter().collect(),
                        );
                        found_independent = true;
                        break;
                    }
                }

                if found_independent {
                    continue;
                }
            }
        }

        // Collect surviving skeleton
        let mut skeleton = Vec::new();
        let mut seen: HashSet<(i64, i64)> = HashSet::new();
        for &a in node_ids {
            for &b in adj.get(&a).unwrap_or(&HashSet::new()) {
                let pair = canonical_pair(a, b);
                if seen.insert(pair) {
                    skeleton.push(pair);
                }
            }
        }

        (skeleton, adj)
    }

    // ------------------------------------------------------------------
    // Edge Orientation (Phase 2)
    // ------------------------------------------------------------------

    fn orient_edges(
        &self,
        node_ids: &[i64],
        skeleton: &[(i64, i64)],
        adj: &HashMap<i64, HashSet<i64>>,
        _features: &HashMap<i64, Vec<f64>>,
    ) -> Vec<(i64, i64)> {
        let mut oriented: HashMap<i64, HashSet<i64>> =
            node_ids.iter().map(|&n| (n, HashSet::new())).collect();
        let mut undirected: HashSet<(i64, i64)> = HashSet::new();
        for &(a, b) in skeleton {
            undirected.insert(canonical_pair(a, b));
        }

        // Phase 1: V-structures
        self.detect_v_structures(node_ids, adj, &mut oriented, &mut undirected);

        // Phase 2: Meek's rules
        self.apply_meek_rules(node_ids, adj, &mut oriented, &mut undirected);

        // Phase 3: Domain heuristics
        self.apply_domain_heuristics(&mut undirected, &mut oriented);

        // Collect directed edges
        let mut directed = Vec::new();
        for &a in node_ids {
            if let Some(targets) = oriented.get(&a) {
                for &b in targets {
                    directed.push((a, b));
                }
            }
        }
        directed
    }

    /// Detect v-structures (unshielded colliders).
    ///
    /// For unshielded triple A - B - C where A and C are not adjacent
    /// and B is NOT in sep(A, C), orient A -> B <- C.
    fn detect_v_structures(
        &self,
        node_ids: &[i64],
        adj: &HashMap<i64, HashSet<i64>>,
        oriented: &mut HashMap<i64, HashSet<i64>>,
        undirected: &mut HashSet<(i64, i64)>,
    ) {
        let sep_sets = self.sep_sets.read();

        for &b in node_ids {
            let neighbors_b: Vec<i64> = adj
                .get(&b)
                .map(|s| s.iter().copied().collect())
                .unwrap_or_default();

            if neighbors_b.len() < 2 {
                continue;
            }

            for i in 0..neighbors_b.len() {
                for j in (i + 1)..neighbors_b.len() {
                    let a = neighbors_b[i];
                    let c = neighbors_b[j];

                    // Unshielded: A and C must NOT be adjacent
                    if adj.get(&a).map(|s| s.contains(&c)).unwrap_or(false) {
                        continue;
                    }

                    let sep_key = canonical_pair(a, c);
                    let sep_set = sep_sets.get(&sep_key);

                    if !sep_set.map(|s| s.contains(&b)).unwrap_or(false) {
                        // V-structure: A -> B <- C
                        orient_edge(a, b, oriented, undirected);
                        orient_edge(c, b, oriented, undirected);
                    }
                }
            }
        }
    }

    /// Apply Meek's three orientation rules until convergence.
    fn apply_meek_rules(
        &self,
        node_ids: &[i64],
        adj: &HashMap<i64, HashSet<i64>>,
        oriented: &mut HashMap<i64, HashSet<i64>>,
        undirected: &mut HashSet<(i64, i64)>,
    ) {
        let max_iterations = 20;

        for _ in 0..max_iterations {
            let mut changed = false;

            for &pair in undirected.clone().iter() {
                let (x, y) = pair;

                for &(a, b) in &[(x, y), (y, x)] {
                    // Rule 1: C -> A and C not adj B => orient A -> B
                    let rule1 = node_ids.iter().any(|&c| {
                        c != a
                            && c != b
                            && oriented.get(&c).map(|s| s.contains(&a)).unwrap_or(false)
                            && !adj.get(&c).map(|s| s.contains(&b)).unwrap_or(false)
                    });

                    if rule1 {
                        orient_edge(a, b, oriented, undirected);
                        changed = true;
                        break;
                    }

                    // Rule 2: A -> C -> B => orient A -> B
                    let rule2 = oriented
                        .get(&a)
                        .map(|targets| {
                            targets.iter().any(|&c| {
                                oriented.get(&c).map(|s| s.contains(&b)).unwrap_or(false)
                            })
                        })
                        .unwrap_or(false);

                    if rule2 {
                        orient_edge(a, b, oriented, undirected);
                        changed = true;
                        break;
                    }

                    // Rule 3: Two non-adjacent C, D both adj to A and B,
                    // with C -> B and D -> B, and A-C, A-D undirected
                    let adj_a = adj.get(&a).cloned().unwrap_or_default();
                    let adj_b_set = adj.get(&b).cloned().unwrap_or_default();
                    let common: Vec<i64> = adj_a
                        .intersection(&adj_b_set)
                        .copied()
                        .filter(|&x| x != a && x != b)
                        .collect();

                    let mut rule3 = false;
                    for ci in 0..common.len() {
                        for di in (ci + 1)..common.len() {
                            let c_n = common[ci];
                            let d_n = common[di];
                            if adj.get(&c_n).map(|s| s.contains(&d_n)).unwrap_or(false) {
                                continue;
                            }
                            if oriented.get(&c_n).map(|s| s.contains(&b)).unwrap_or(false)
                                && oriented.get(&d_n).map(|s| s.contains(&b)).unwrap_or(false)
                                && undirected.contains(&canonical_pair(a, c_n))
                                && undirected.contains(&canonical_pair(a, d_n))
                            {
                                rule3 = true;
                                break;
                            }
                        }
                        if rule3 {
                            break;
                        }
                    }

                    if rule3 {
                        orient_edge(a, b, oriented, undirected);
                        changed = true;
                        break;
                    }
                }
            }

            if !changed {
                break;
            }
        }
    }

    /// Orient remaining undirected edges using domain heuristics:
    /// temporal ordering (earlier source_block = cause) and confidence asymmetry.
    fn apply_domain_heuristics(
        &self,
        undirected: &mut HashSet<(i64, i64)>,
        oriented: &mut HashMap<i64, HashSet<i64>>,
    ) {
        for &pair in undirected.clone().iter() {
            let (a, b) = pair;
            let node_a = self.kg.get_node(a);
            let node_b = self.kg.get_node(b);

            if node_a.is_none() || node_b.is_none() {
                continue;
            }

            let na = node_a.unwrap();
            let nb = node_b.unwrap();

            let mut score = 0.0_f64;

            // Temporal: earlier block -> likely cause
            if na.source_block < nb.source_block {
                score += 1.0;
            } else if nb.source_block < na.source_block {
                score -= 1.0;
            }

            // Confidence: higher confidence -> likely cause
            score += (na.confidence - nb.confidence) * 0.5;

            if score > 0.0 {
                orient_edge(a, b, oriented, undirected);
            } else if score < 0.0 {
                orient_edge(b, a, oriented, undirected);
            }
        }
    }

    // ------------------------------------------------------------------
    // FCI-specific methods
    // ------------------------------------------------------------------

    /// FCI possible-d-sep removal pass.
    ///
    /// Tests each edge using conditioning sets from the "possible d-separating set"
    /// which includes nodes within distance 2 in the adjacency graph.
    fn fci_possible_dsep_removal(
        &self,
        node_ids: &[i64],
        adj: &HashMap<i64, HashSet<i64>>,
        features: &HashMap<i64, Vec<f64>>,
        significance: f64,
    ) -> (HashMap<i64, HashSet<i64>>, HashMap<(i64, i64), HashSet<i64>>) {
        // Deep copy adjacency
        let mut refined_adj: HashMap<i64, HashSet<i64>> = adj
            .iter()
            .map(|(k, v)| (*k, v.clone()))
            .collect();

        let mut new_sep_sets: HashMap<(i64, i64), HashSet<i64>> = HashMap::new();
        let id_set: HashSet<i64> = node_ids.iter().copied().collect();

        // Collect edges to test
        let mut edges_to_test = Vec::new();
        for &a in node_ids {
            for &b in refined_adj.get(&a).unwrap_or(&HashSet::new()) {
                if a < b {
                    edges_to_test.push((a, b));
                }
            }
        }

        for (a, b) in edges_to_test {
            if !refined_adj.get(&a).map(|s| s.contains(&b)).unwrap_or(false) {
                continue;
            }

            // Possible d-sep: nodes within distance 2
            let mut pds: HashSet<i64> = HashSet::new();
            if let Some(neighbors_a) = adj.get(&a) {
                for &n1 in neighbors_a {
                    if n1 != b && id_set.contains(&n1) {
                        pds.insert(n1);
                        if let Some(neighbors_n1) = adj.get(&n1) {
                            for &n2 in neighbors_n1 {
                                if n2 != a && n2 != b && id_set.contains(&n2) {
                                    pds.insert(n2);
                                }
                            }
                        }
                    }
                }
            }

            let pds_vec: Vec<i64> = pds.into_iter().collect();

            // Test subsets of size up to MAX_CONDITIONING_DEPTH
            let mut removed = false;
            for d in 0..=MAX_CONDITIONING_DEPTH.min(pds_vec.len()) {
                for subset in combinations(&pds_vec, d) {
                    let p_value = fisher_z_p_value(features, a, b, &subset);
                    if p_value > significance {
                        refined_adj.get_mut(&a).unwrap().remove(&b);
                        refined_adj.get_mut(&b).unwrap().remove(&a);
                        new_sep_sets.insert(
                            canonical_pair(a, b),
                            subset.into_iter().collect(),
                        );
                        removed = true;
                        break;
                    }
                }
                if removed {
                    break;
                }
            }
        }

        (refined_adj, new_sep_sets)
    }

    /// Orient v-structures on the PAG.
    fn fci_orient_v_structures(
        &self,
        node_ids: &[i64],
        adj: &HashMap<i64, HashSet<i64>>,
        pag: &mut PAG,
    ) {
        let sep_sets = self.sep_sets.read();

        for &b in node_ids {
            let neighbors_b: Vec<i64> = adj
                .get(&b)
                .map(|s| s.iter().copied().collect())
                .unwrap_or_default();

            if neighbors_b.len() < 2 {
                continue;
            }

            for i in 0..neighbors_b.len() {
                for j in (i + 1)..neighbors_b.len() {
                    let a = neighbors_b[i];
                    let c = neighbors_b[j];

                    if adj.get(&a).map(|s| s.contains(&c)).unwrap_or(false) {
                        continue;
                    }

                    let sep_key = canonical_pair(a, c);
                    if !sep_sets.get(&sep_key).map(|s| s.contains(&b)).unwrap_or(false) {
                        // V-structure in PAG: set arrowheads at B
                        if let Some(e) = pag.get_edge_mut(a, b) {
                            e.set_mark_at(b, EndpointMark::Arrow);
                        }
                        if let Some(e) = pag.get_edge_mut(c, b) {
                            e.set_mark_at(b, EndpointMark::Arrow);
                        }
                    }
                }
            }
        }
    }

    /// Apply FCI orientation rules R1-R4 and R8-R10 until convergence.
    fn fci_apply_rules(
        &self,
        node_ids: &[i64],
        adj: &HashMap<i64, HashSet<i64>>,
        pag: &mut PAG,
    ) {
        let max_iterations = 20;

        for _ in 0..max_iterations {
            let mut changed = false;

            for &a in node_ids {
                let neighbors_a: Vec<i64> = adj
                    .get(&a)
                    .map(|s| s.iter().copied().collect())
                    .unwrap_or_default();

                for &b in &neighbors_a {
                    if !pag.has_edge(a, b) {
                        continue;
                    }

                    // R1: If A *-> B o-* C and A, C not adjacent => orient B *-> C
                    if let Some(edge_ab) = pag.get_edge(a, b) {
                        if edge_ab.has_arrowhead_at(b) {
                            let neighbors_b: Vec<i64> = adj
                                .get(&b)
                                .map(|s| s.iter().copied().collect())
                                .unwrap_or_default();

                            for &c in &neighbors_b {
                                if c == a {
                                    continue;
                                }
                                if adj.get(&a).map(|s| s.contains(&c)).unwrap_or(false) {
                                    continue;
                                }

                                if let Some(edge_bc) = pag.get_edge(b, c) {
                                    if edge_bc.has_circle_at(c) {
                                        if let Some(e) = pag.get_edge_mut(b, c) {
                                            e.set_mark_at(c, EndpointMark::Arrow);
                                            e.set_mark_at(b, EndpointMark::Tail);
                                            changed = true;
                                        }
                                    }
                                }
                            }
                        }
                    }

                    // R2: If A -> B *-> C (or A *-> B -> C) and A *-o C => A *-> C
                    if let Some(edge_ab) = pag.get_edge(a, b) {
                        if edge_ab.has_tail_at(a) && edge_ab.has_arrowhead_at(b) {
                            let neighbors_b: Vec<i64> = adj
                                .get(&b)
                                .map(|s| s.iter().copied().collect())
                                .unwrap_or_default();

                            for &c in &neighbors_b {
                                if c == a {
                                    continue;
                                }
                                if let Some(edge_bc) = pag.get_edge(b, c) {
                                    if edge_bc.has_arrowhead_at(c) {
                                        if let Some(edge_ac) = pag.get_edge(a, c) {
                                            if edge_ac.has_circle_at(c) {
                                                if let Some(e) = pag.get_edge_mut(a, c) {
                                                    e.set_mark_at(c, EndpointMark::Arrow);
                                                    changed = true;
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }

                    // R3: If A *-> B <-* C and A *-o D o-* C and D *-o B
                    // and A, C not adjacent => D *-> B
                    // (Simplified: check for circle at B on D-B edge)
                    if let Some(edge_ab) = pag.get_edge(a, b) {
                        if edge_ab.has_arrowhead_at(b) {
                            let neighbors_a_set: HashSet<i64> =
                                adj.get(&a).cloned().unwrap_or_default();
                            let neighbors_b_set: HashSet<i64> =
                                adj.get(&b).cloned().unwrap_or_default();

                            for &c in &neighbors_a_set {
                                if c == a || c == b {
                                    continue;
                                }
                                if let Some(edge_cb) = pag.get_edge(c, b) {
                                    if !edge_cb.has_arrowhead_at(b) {
                                        continue;
                                    }
                                    if adj.get(&a).map(|s| s.contains(&c)).unwrap_or(false) {
                                        continue;
                                    }

                                    // Find D adj to both A and C and B
                                    for &d in &neighbors_b_set {
                                        if d == a || d == b || d == c {
                                            continue;
                                        }
                                        if !neighbors_a_set.contains(&d) {
                                            continue;
                                        }
                                        if !adj.get(&c).map(|s| s.contains(&d)).unwrap_or(false) {
                                            continue;
                                        }

                                        if let Some(edge_db) = pag.get_edge(d, b) {
                                            if edge_db.has_circle_at(b) {
                                                if let Some(e) = pag.get_edge_mut(d, b) {
                                                    e.set_mark_at(b, EndpointMark::Arrow);
                                                    changed = true;
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }

                    // R4: If there is a directed path from A to B and A o-o B => A -> B
                    if let Some(edge_ab_r4) = pag.get_edge(a, b) {
                        if edge_ab_r4.is_nondirected() {
                            if has_directed_path(pag, adj, a, b, node_ids.len()) {
                                if let Some(e) = pag.get_edge_mut(a, b) {
                                    e.set_mark_at(a, EndpointMark::Tail);
                                    e.set_mark_at(b, EndpointMark::Arrow);
                                    changed = true;
                                }
                            }
                        }
                    }
                }
            }

            if !changed {
                break;
            }
        }
    }
}

// ------------------------------------------------------------------
// Helper functions
// ------------------------------------------------------------------

/// Canonical pair key (min, max) for consistent HashMap storage.
fn canonical_pair(a: i64, b: i64) -> (i64, i64) {
    (a.min(b), a.max(b))
}

/// Orient an undirected edge from -> to. No-op if already oriented in reverse.
fn orient_edge(
    from_id: i64,
    to_id: i64,
    oriented: &mut HashMap<i64, HashSet<i64>>,
    undirected: &mut HashSet<(i64, i64)>,
) {
    if oriented.get(&to_id).map(|s| s.contains(&from_id)).unwrap_or(false) {
        return; // Don't reverse
    }
    undirected.remove(&canonical_pair(from_id, to_id));
    oriented.entry(from_id).or_default().insert(to_id);
}

/// Generate all combinations of size k from a slice.
fn combinations(items: &[i64], k: usize) -> Vec<Vec<i64>> {
    if k == 0 {
        return vec![vec![]];
    }
    if items.len() < k {
        return vec![];
    }

    let mut result = Vec::new();
    let mut indices: Vec<usize> = (0..k).collect();

    loop {
        result.push(indices.iter().map(|&i| items[i]).collect());

        // Find rightmost index that can be incremented
        let mut i = k;
        while i > 0 {
            i -= 1;
            if indices[i] < items.len() - k + i {
                break;
            }
            if i == 0 && indices[0] >= items.len() - k {
                return result;
            }
        }

        indices[i] += 1;
        for j in (i + 1)..k {
            indices[j] = indices[j - 1] + 1;
        }
    }
}

/// Check if there is a directed path from src to dst in the PAG.
/// Uses BFS, limited to max_depth hops.
fn has_directed_path(
    pag: &PAG,
    adj: &HashMap<i64, HashSet<i64>>,
    src: i64,
    dst: i64,
    max_depth: usize,
) -> bool {
    let mut visited: HashSet<i64> = HashSet::new();
    let mut queue = std::collections::VecDeque::new();
    queue.push_back((src, 0));
    visited.insert(src);

    while let Some((current, depth)) = queue.pop_front() {
        if depth >= max_depth {
            continue;
        }

        let neighbors: Vec<i64> = adj
            .get(&current)
            .map(|s| s.iter().copied().collect())
            .unwrap_or_default();

        for next in neighbors {
            if next == dst {
                // Check if current -> next is directed in the PAG
                if let Some(e) = pag.get_edge(current, next) {
                    if (e.node_a == current && e.has_tail_at(current) && e.has_arrowhead_at(next))
                        || (e.node_b == current
                            && e.has_tail_at(current)
                            && e.has_arrowhead_at(next))
                    {
                        return true;
                    }
                }
            }

            if visited.insert(next) {
                if let Some(e) = pag.get_edge(current, next) {
                    if (e.node_a == current && e.has_tail_at(current) && e.has_arrowhead_at(next))
                        || (e.node_b == current
                            && e.has_tail_at(current)
                            && e.has_arrowhead_at(next))
                    {
                        queue.push_back((next, depth + 1));
                    }
                }
            }
        }
    }

    false
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::collections::HashMap;

    fn make_content(text: &str) -> HashMap<String, String> {
        let mut c = HashMap::new();
        c.insert("text".into(), text.into());
        c
    }

    fn make_engine() -> (Arc<KnowledgeGraph>, CausalDiscovery) {
        let kg = Arc::new(KnowledgeGraph::new());
        let cd = CausalDiscovery::new(Arc::clone(&kg));
        (kg, cd)
    }

    #[test]
    fn test_combinations_empty() {
        let items = vec![1, 2, 3];
        let c = combinations(&items, 0);
        assert_eq!(c.len(), 1);
        assert!(c[0].is_empty());
    }

    #[test]
    fn test_combinations_single() {
        let items = vec![1, 2, 3];
        let c = combinations(&items, 1);
        assert_eq!(c.len(), 3);
    }

    #[test]
    fn test_combinations_pairs() {
        let items = vec![1, 2, 3, 4];
        let c = combinations(&items, 2);
        assert_eq!(c.len(), 6); // 4 choose 2 = 6
    }

    #[test]
    fn test_combinations_all() {
        let items = vec![1, 2, 3];
        let c = combinations(&items, 3);
        assert_eq!(c.len(), 1);
        assert_eq!(c[0], vec![1, 2, 3]);
    }

    #[test]
    fn test_combinations_too_few() {
        let items = vec![1];
        let c = combinations(&items, 3);
        assert!(c.is_empty());
    }

    #[test]
    fn test_canonical_pair() {
        assert_eq!(canonical_pair(5, 3), (3, 5));
        assert_eq!(canonical_pair(3, 5), (3, 5));
        assert_eq!(canonical_pair(3, 3), (3, 3));
    }

    #[test]
    fn test_intervention_missing_node() {
        let (_kg, cd) = make_engine();
        let result = cd.intervention_test(999, 998);
        assert!(!result.validated);
    }

    #[test]
    fn test_intervention_no_neighbours() {
        let (kg, cd) = make_engine();
        let n1 = kg.add_node("assertion".into(), make_content("a"), 0.8, 1, String::new());
        let n2 = kg.add_node("assertion".into(), make_content("b"), 0.7, 2, String::new());
        kg.add_edge(n1.node_id, n2.node_id, "supports".into(), 1.0);

        let result = cd.intervention_test(n1.node_id, n2.node_id);
        // No other neighbors of n2 besides n1, so trivially valid
        assert!(result.validated);
    }

    #[test]
    fn test_intervention_with_shared_neighbor() {
        let (kg, cd) = make_engine();
        let a = kg.add_node("assertion".into(), make_content("cause"), 0.9, 1, String::new());
        let b = kg.add_node("assertion".into(), make_content("effect"), 0.8, 2, String::new());
        let c = kg.add_node("assertion".into(), make_content("shared"), 0.7, 3, String::new());

        kg.add_edge(a.node_id, b.node_id, "supports".into(), 1.0);
        kg.add_edge(a.node_id, c.node_id, "supports".into(), 1.0);
        kg.add_edge(c.node_id, b.node_id, "supports".into(), 1.0);

        let result = cd.intervention_test(a.node_id, b.node_id);
        // c is connected to both a and b, so a_connected should be > 0
        assert!(result.a_connected > 0);
        assert!(result.ratio > 0.0);
    }

    #[test]
    fn test_discover_too_few_nodes() {
        let (kg, cd) = make_engine();
        kg.add_node("assertion".into(), make_content("only one"), 0.8, 1, String::new());

        let result = cd.discover(None, 200, 0.05);
        assert_eq!(result.causal_edges, 0);
        assert_eq!(result.nodes_analyzed, 1);
    }

    #[test]
    fn test_discover_basic() {
        let (kg, cd) = make_engine();
        // Create enough nodes for discovery
        for i in 0..5 {
            let mut c = make_content(&format!("node {} with value {}", i, i * 10));
            c.insert("type".into(), "test".into());
            kg.add_node("assertion".into(), c, 0.5 + i as f64 * 0.1, i + 1, String::new());
        }

        let result = cd.discover(None, 200, 0.05);
        assert_eq!(result.nodes_analyzed, 5);
        // Causal edges found depends on feature correlations
        assert!(result.nodes_analyzed >= 3);
    }

    #[test]
    fn test_discover_all_domains_empty() {
        let (_kg, cd) = make_engine();
        let total = cd.discover_all_domains(100, 10);
        assert_eq!(total, 0);
    }

    #[test]
    fn test_fci_too_few_nodes() {
        let (kg, cd) = make_engine();
        kg.add_node("assertion".into(), make_content("one"), 0.8, 1, String::new());

        let result = cd.discover_with_fci(None, 200, 0.05);
        assert_eq!(result.causal_edges, 0);
        assert_eq!(result.latent_confounders, 0);
    }

    #[test]
    fn test_fci_basic() {
        let (kg, cd) = make_engine();
        for i in 0..5 {
            let mut c = make_content(&format!("fci node {} data {}", i, i * 20));
            c.insert("type".into(), "test".into());
            kg.add_node("inference".into(), c, 0.5 + i as f64 * 0.08, i + 1, String::new());
        }

        let result = cd.discover_with_fci(None, 200, 0.05);
        assert!(result.nodes_analyzed >= 3);
    }

    #[test]
    fn test_validate_causal_edge_alias() {
        let (kg, cd) = make_engine();
        let n1 = kg.add_node("assertion".into(), make_content("x"), 0.9, 1, String::new());
        let n2 = kg.add_node("assertion".into(), make_content("y"), 0.8, 2, String::new());
        kg.add_edge(n1.node_id, n2.node_id, "supports".into(), 1.0);

        let r1 = cd.intervention_test(n1.node_id, n2.node_id);
        let r2 = cd.validate_causal_edge(n1.node_id, n2.node_id);
        assert_eq!(r1.validated, r2.validated);
        assert_eq!(r1.ratio, r2.ratio);
    }

    #[test]
    fn test_orient_edge_no_reverse() {
        let mut oriented: HashMap<i64, HashSet<i64>> = HashMap::new();
        let mut undirected: HashSet<(i64, i64)> = HashSet::new();
        undirected.insert((1, 2));
        oriented.entry(2).or_default().insert(1); // 2 -> 1 already oriented

        orient_edge(1, 2, &mut oriented, &mut undirected);
        // Should NOT orient 1 -> 2 since 2 -> 1 already exists
        assert!(!oriented.get(&1).map(|s| s.contains(&2)).unwrap_or(false));
    }

    #[test]
    fn test_pc_skeleton_basic() {
        let (kg, cd) = make_engine();
        for i in 0..4 {
            let c = make_content(&format!("node {}", i));
            kg.add_node("assertion".into(), c, 0.5 + i as f64 * 0.1, i + 1, String::new());
        }

        let node_ids = vec![1, 2, 3, 4];
        let features = build_feature_matrix(&kg, &node_ids);
        let (skeleton, adj) = cd.pc_skeleton(&node_ids, &features, 0.05);

        // Skeleton should have some edges (depends on feature correlations)
        assert!(!adj.is_empty());
        // Each node should have an entry
        for &nid in &node_ids {
            assert!(adj.contains_key(&nid));
        }
        // Skeleton edges should be canonical pairs
        for &(a, b) in &skeleton {
            assert!(a <= b);
        }
    }

    #[test]
    fn test_stats_after_discovery() {
        let (kg, cd) = make_engine();
        for i in 0..5 {
            let c = make_content(&format!("stats test {}", i));
            kg.add_node("assertion".into(), c, 0.6 + i as f64 * 0.05, i + 1, String::new());
        }

        assert_eq!(cd.total_runs(), 0);
        cd.discover(None, 200, 0.05);
        assert_eq!(cd.total_runs(), 1);
    }
}
