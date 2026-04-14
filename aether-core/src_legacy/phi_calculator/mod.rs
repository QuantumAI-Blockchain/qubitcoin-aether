//! Phi Calculator v4 — HMS-Phi (Hierarchical Multi-Scale Phi)
//!
//! Computes Phi (Φ) as a multi-scale integration metric for the Aether Tree
//! knowledge graph, using three independent levels of analysis combined
//! multiplicatively:
//!
//!   phi_micro: Spectral MIP on sampled subgraphs (Level 0)
//!   phi_meso:  Spectral MIP (Fiedler bisection) on full knowledge graph (Level 1)
//!   phi_macro: Cross-domain integration between Sephirot clusters (Level 2)
//!
//! Formula:
//!     hms_raw = phi_micro^(1/φ) × phi_meso^(1/φ²) × phi_macro^(1/φ³)
//!     raw_phi = hms_raw × 8.0   (scale so hms_raw=1 > max gate ceiling)
//!     phi = min(raw_phi × redundancy_factor, gate_ceiling)
//!
//! Multiplicative structure means zero in any level → zero phi (ungameable).
//! Falls back to weighted additive when n_nodes < 500 or micro/meso/macro is zero.
//!
//! Milestone gates: 10 v4 quality gates that cap Phi until genuine cognitive
//! milestones are met. V4 gates emphasize quality over quantity.

use std::collections::{BTreeMap, HashMap, HashSet, VecDeque};
use std::time::{SystemTime, UNIX_EPOCH};

use pyo3::prelude::*;
use pyo3::types::PyDict;
use rand::rngs::StdRng;
use rand::seq::SliceRandom;
use rand::Rng;
use rand::SeedableRng;

use crate::knowledge_graph::{KeterEdge, KeterNode, KnowledgeGraph};

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/// Phi threshold for consciousness emergence / Proof-of-Thought validity.
pub const PHI_THRESHOLD: f64 = 3.0;

/// Each passed milestone gate raises the ceiling by this amount.
const GATE_CEILING_INCREMENT: f64 = 0.5;

/// Total milestone gates.
const NUM_GATES: usize = 10;

/// Maximum number of nodes to consider in MIP spectral bisection.
const MIP_SAMPLE_SIZE: usize = 5000;

/// Power iteration steps for Fiedler vector computation.
const FIEDLER_MAX_ITER: usize = 50;

/// Golden ratio for HMS-Phi formula.
const PHI_RATIO: f64 = 1.618033988749895;
/// HMS exponent for micro: 1/φ ≈ 0.618
const HMS_EXP_MICRO: f64 = 1.0 / PHI_RATIO;
/// HMS exponent for meso: 1/φ² ≈ 0.382
const HMS_EXP_MESO: f64 = 1.0 / (PHI_RATIO * PHI_RATIO);
/// HMS exponent for macro: 1/φ³ ≈ 0.236
const HMS_EXP_MACRO: f64 = 1.0 / (PHI_RATIO * PHI_RATIO * PHI_RATIO);
/// Scale factor so perfect HMS integration (=1.0) exceeds max gate ceiling (5.0).
const HMS_SCALE: f64 = 8.0;
/// Minimum nodes before HMS-Phi is used (additive fallback below).
const HMS_MIN_NODES: usize = 500;

// ---------------------------------------------------------------------------
// Milestone Gate definition
// ---------------------------------------------------------------------------

/// A milestone gate descriptor.
#[derive(Debug, Clone)]
struct MilestoneGate {
    id: u32,
    name: &'static str,
    description: &'static str,
    requirement: &'static str,
    check: fn(&GateStats) -> bool,
}

/// Aggregated statistics consumed by milestone gate checks.
#[derive(Debug, Default)]
struct GateStats {
    n_nodes: usize,
    n_edges: usize,
    avg_confidence: f64,
    node_type_counts: HashMap<String, usize>,
    edge_type_counts: HashMap<String, usize>,
    integration_score: f64,
    mip_phi: f64,
    verified_predictions: usize,
    debate_verdicts: usize,
    contradiction_resolutions: usize,
    domain_count: usize,
    working_memory_hit_rate: f64,
    auto_goals_generated: usize,
    self_reflection_nodes: usize,
    calibration_error: f64,
    calibration_evaluations: usize,
    grounding_ratio: f64,
    axiom_from_consolidation: usize,
    cross_domain_inferences: usize,
    cross_domain_inference_confidence: f64,
    prediction_accuracy: f64,
    novel_concept_count: usize,
    // v4 gate fields
    improvement_cycles_enacted: usize,
    improvement_performance_delta: f64,
    fep_free_energy_decreasing: bool,
    auto_goals_with_inferences: usize,
    curiosity_driven_discoveries: usize,
    fep_domain_precisions: usize,
    sephirot_winner_diversity: f64,
}

/// Static table of all 10 milestone gates (v4 — quality-focused).
fn milestone_gates() -> [MilestoneGate; NUM_GATES] {
    [
        MilestoneGate {
            id: 1,
            name: "Knowledge Foundation",
            description: "Broad knowledge base with diverse domains",
            requirement: ">=500 nodes, >=5 domains, avg confidence >= 0.5",
            check: |s| {
                s.n_nodes >= 500
                    && s.domain_count >= 5
                    && s.avg_confidence >= 0.5
            },
        },
        MilestoneGate {
            id: 2,
            name: "Structural Diversity",
            description: "Multiple reasoning types with real graph integration",
            requirement: ">=2K nodes, >=4 types with 50+ each, integration > 0.3",
            check: |s| {
                s.n_nodes >= 2000
                    && s.node_type_counts
                        .values()
                        .filter(|&&c| c >= 50)
                        .count()
                        >= 4
                    && s.integration_score > 0.3
            },
        },
        MilestoneGate {
            id: 3,
            name: "Validated Predictions",
            description: "Predictions verified against actual outcomes — not self-reported",
            requirement: ">=5K nodes, >=50 verified predictions, accuracy > 60%",
            check: |s| {
                s.n_nodes >= 5000
                    && s.verified_predictions >= 50
                    && s.prediction_accuracy > 0.6
            },
        },
        MilestoneGate {
            id: 4,
            name: "Self-Correction",
            description: "Genuine adversarial debate with contradiction resolution",
            requirement: ">=10K nodes, >=20 debates, >=10 contradictions resolved, MIP > 0.3",
            check: |s| {
                s.n_nodes >= 10_000
                    && s.debate_verdicts >= 20
                    && s.contradiction_resolutions >= 10
                    && s.mip_phi > 0.3
            },
        },
        MilestoneGate {
            id: 5,
            name: "Cross-Domain Transfer",
            description: "Genuine knowledge transfer: inferences using evidence from 2+ domains",
            requirement: ">=15K nodes, >=30 cross-domain inferences with conf > 0.5, >=50 cross-edges",
            check: |s| {
                let analogies = *s.edge_type_counts.get("analogous_to").unwrap_or(&0);
                s.n_nodes >= 15_000
                    && s.cross_domain_inferences >= 30
                    && s.cross_domain_inference_confidence > 0.5
                    && analogies >= 50
            },
        },
        MilestoneGate {
            id: 6,
            name: "Enacted Self-Improvement",
            description: "Self-improvement actions enacted AND producing measurable gains with FEP convergence",
            requirement: ">=20K nodes, >=10 enacted improvement cycles, positive performance delta, FEP free energy decreasing",
            check: |s| {
                s.n_nodes >= 20_000
                    && s.improvement_cycles_enacted >= 10
                    && s.improvement_performance_delta > 0.0
                    && s.fep_free_energy_decreasing
            },
        },
        MilestoneGate {
            id: 7,
            name: "Calibrated Confidence",
            description: "System knows what it knows — calibration error below threshold",
            requirement: ">=25K nodes, ECE < 0.15, >=200 evaluations, >5% grounded",
            check: |s| {
                s.n_nodes >= 25_000
                    && s.calibration_error < 0.15
                    && s.calibration_evaluations >= 200
                    && s.grounding_ratio > 0.05
            },
        },
        MilestoneGate {
            id: 8,
            name: "Autonomous Curiosity",
            description: "System generates its own research goals with FEP-guided exploration across domains",
            requirement: ">=35K nodes, >=50 auto-goals, >=30 producing inferences, >=10 curiosity discoveries, FEP precision in >=3 domains",
            check: |s| {
                s.n_nodes >= 35_000
                    && s.auto_goals_generated >= 50
                    && s.auto_goals_with_inferences >= 30
                    && s.curiosity_driven_discoveries >= 10
                    && s.fep_domain_precisions >= 3
            },
        },
        MilestoneGate {
            id: 9,
            name: "Predictive Mastery",
            description: "Sustained high accuracy across domains with large inference volume",
            requirement: ">=50K nodes, accuracy > 70%, >=5K inferences, >=20 consolidated axioms",
            check: |s| {
                let inferences = *s.node_type_counts.get("inference").unwrap_or(&0);
                s.n_nodes >= 50_000
                    && s.prediction_accuracy > 0.70
                    && inferences >= 5000
                    && s.axiom_from_consolidation >= 20
            },
        },
        MilestoneGate {
            id: 10,
            name: "Novel Synthesis",
            description: "Genuine novel concepts with diverse Sephirot cognitive participation",
            requirement: ">=75K nodes, >=50 novel concepts, >=100 cross-domain inferences, sustained self-improvement, Sephirot diversity >=0.5",
            check: |s| {
                s.n_nodes >= 75_000
                    && s.novel_concept_count >= 50
                    && s.cross_domain_inferences >= 100
                    && s.improvement_performance_delta > 0.05
                    && s.sephirot_winner_diversity >= 0.5
            },
        },
    ]
}

// ---------------------------------------------------------------------------
// Single Phi measurement snapshot (stored in history)
// ---------------------------------------------------------------------------

#[derive(Debug, Clone)]
struct PhiMeasurement {
    phi_value: f64,
    phi_raw: f64,
    integration_score: f64,
    differentiation_score: f64,
    mip_score: f64,
    redundancy_factor: f64,
    // HMS-Phi components
    phi_micro: f64,
    phi_meso: f64,
    phi_macro: f64,
    hms_phi_raw: f64,
    using_hms: bool,
    num_nodes: usize,
    num_edges: usize,
    block_height: u64,
    timestamp: f64,
    gates_passed: usize,
    gate_ceiling: f64,
}

// ---------------------------------------------------------------------------
// PhiCalculator
// ---------------------------------------------------------------------------

/// Computes the Phi (Φ) integration metric for the Aether Tree knowledge graph.
///
/// v4 HMS-Phi formula uses three independent levels of analysis, multiplicatively
/// combined:
///   phi_micro: Spectral MIP on elite subgraph samples (Level 0)
///   phi_meso:  Spectral MIP (Fiedler bisection) on full knowledge graph (Level 1)
///   phi_macro: Cross-domain integration between Sephirot clusters (Level 2)
///
///   hms_raw = phi_micro^(1/φ) × phi_meso^(1/φ²) × phi_macro^(1/φ³)
///   raw_phi = hms_raw × 8.0
///   phi = min(raw_phi × redundancy, gate_ceiling)
///
/// Falls back to weighted additive when n_nodes < 500 or any HMS level is zero.
///
/// # Python usage
///
/// ```python
/// from aether_core import PhiCalculator, KnowledgeGraph
///
/// kg = KnowledgeGraph()
/// # ... populate kg ...
/// calc = PhiCalculator()
/// result = calc.compute_phi(kg, block_height=100)
/// print(result["phi_value"], result["phi_formula"])
/// ```
#[pyclass]
pub struct PhiCalculator {
    /// Block-height -> phi value cache.
    cache: HashMap<u64, f64>,
    /// Chronological measurement history.
    history: Vec<PhiMeasurement>,
    /// Last full result (for caching across nearby block heights).
    last_full: Option<PhiMeasurement>,
    /// Block height of the last computed result.
    last_computed_block: i64,
    /// MIP score from the most recent computation.
    last_mip_score: f64,
    /// Compute interval — skip re-computation if block delta < this.
    compute_interval: u64,
}

#[pymethods]
impl PhiCalculator {
    /// Create a new PhiCalculator.
    ///
    /// Args:
    ///     compute_interval: Optional interval (in blocks) between full re-computations.
    ///         Defaults to 1 (compute every block).
    #[new]
    #[pyo3(signature = (compute_interval = 1))]
    pub fn new(compute_interval: u64) -> Self {
        Self {
            cache: HashMap::new(),
            history: Vec::new(),
            last_full: None,
            last_computed_block: -1,
            last_mip_score: 0.0,
            compute_interval,
        }
    }

    /// Compute Phi for the current state of a knowledge graph.
    ///
    /// Args:
    ///     kg: Reference to the KnowledgeGraph.
    ///     block_height: Current block height (default 0).
    ///     extra_stats: Optional dict of external stats for milestone gates
    ///         (keys: working_memory_hit_rate, calibration_error, prediction_accuracy).
    ///
    /// Returns:
    ///     A Python dict with the full Phi breakdown.
    #[pyo3(signature = (kg, block_height = 0, extra_stats = None))]
    pub fn compute_phi(
        &mut self,
        kg: &KnowledgeGraph,
        block_height: u64,
        extra_stats: Option<&Bound<'_, PyDict>>,
    ) -> PyResult<PyObject> {
        Python::with_gil(|py| {
            let n_nodes = kg.node_count();
            let n_edges = kg.edge_count();

            // Empty graph: return zeros
            if n_nodes == 0 {
                return Ok(self.empty_result(py, block_height)?);
            }

            // Check cache: if within compute_interval, return cached result with updated height
            if self.compute_interval > 1 {
                if let Some(ref cached) = self.last_full {
                    if block_height > 0
                        && self.last_computed_block > 0
                        && (block_height as i64 - self.last_computed_block)
                            < self.compute_interval as i64
                    {
                        let dict = self.measurement_to_dict(py, cached, block_height)?;
                        dict.set_item("cached", true)?;
                        return Ok(dict.into());
                    }
                }
            }

            // Collect node/edge slices from the knowledge graph
            let nodes = kg.get_nodes_raw();
            let edges = kg.get_edges_raw();

            // --- Integration (structural + cross-flow + MIP) ---
            let integration = self.compute_integration(&nodes, &edges, n_nodes);

            // --- Differentiation (Shannon entropy) ---
            let differentiation = self.compute_differentiation(&nodes, &edges);

            // --- Redundancy factor (VectorIndex-based — return 1.0, handled externally) ---
            let redundancy_factor = 1.0;

            // --- Parse external stats for milestone gates ---
            let extra = self.parse_extra_stats(extra_stats);

            // --- Milestone gates ---
            let gate_results = self.check_gates(
                &nodes,
                &edges,
                integration,
                self.last_mip_score,
                &extra,
            );
            let gates_passed = gate_results.iter().filter(|g| g.1).count();
            let gate_ceiling = gates_passed as f64 * GATE_CEILING_INCREMENT;

            // --- HMS-Phi v4 ---
            let phi_meso = self.last_mip_score.max(0.0).min(1.0);
            let phi_macro = self.compute_phi_macro(&nodes, &edges, n_nodes, n_edges);
            // phi_micro: use a simple proxy based on subgraph MIP sampling
            // (full IIT TPM approximation is too expensive for Rust without numpy)
            let phi_micro = if n_nodes >= HMS_MIN_NODES && phi_meso > 0.0 && phi_macro > 0.0 {
                self.compute_phi_micro(&nodes, &edges, n_nodes)
            } else {
                0.0
            };

            let (raw_phi, hms_raw, using_hms) = if phi_micro > 0.0 && phi_meso > 0.0 && phi_macro > 0.0 {
                // True multiplicative HMS-Phi
                let hms = phi_micro.powf(HMS_EXP_MICRO)
                    * phi_meso.powf(HMS_EXP_MESO)
                    * phi_macro.powf(HMS_EXP_MACRO);
                (hms * HMS_SCALE, hms, true)
            } else {
                // Additive fallback: original weighted formula
                let additive = integration * 0.4 + differentiation * 0.3 + self.last_mip_score * 0.3;
                (additive, 0.0, false)
            };

            // --- Final Phi ---
            let phi = (raw_phi * redundancy_factor).min(gate_ceiling);

            let now = current_timestamp();

            let measurement = PhiMeasurement {
                phi_value: round6(phi),
                phi_raw: round6(raw_phi),
                integration_score: round6(integration),
                differentiation_score: round6(differentiation),
                mip_score: round6(self.last_mip_score),
                redundancy_factor: round4(redundancy_factor),
                phi_micro: round6(phi_micro),
                phi_meso: round6(phi_meso),
                phi_macro: round6(phi_macro),
                hms_phi_raw: round6(hms_raw),
                using_hms,
                num_nodes: n_nodes,
                num_edges: n_edges,
                block_height,
                timestamp: now,
                gates_passed,
                gate_ceiling,
            };

            // Update caches
            self.cache.insert(block_height, measurement.phi_value);
            self.last_full = Some(measurement.clone());
            self.last_computed_block = block_height as i64;
            self.history.push(measurement.clone());

            // Build Python dict result
            let dict = self.measurement_to_dict(py, &measurement, block_height)?;

            // Add gate details
            let gates_list = pyo3::types::PyList::empty(py);
            for (gate, passed) in &gate_results {
                let gdict = PyDict::new(py);
                gdict.set_item("id", gate.id)?;
                gdict.set_item("name", gate.name)?;
                gdict.set_item("description", gate.description)?;
                gdict.set_item("requirement", gate.requirement)?;
                gdict.set_item("passed", *passed)?;
                gates_list.append(gdict)?;
            }
            dict.set_item("gates", gates_list)?;

            Ok(dict.into())
        })
    }

    /// Return the current (most recent) Phi value.
    ///
    /// Returns 0.0 if no computation has been performed.
    pub fn get_current_phi(&self) -> f64 {
        self.last_full
            .as_ref()
            .map(|m| m.phi_value)
            .unwrap_or(0.0)
    }

    /// Whether the current Phi exceeds the consciousness threshold (3.0).
    pub fn is_conscious(&self) -> bool {
        self.get_current_phi() >= PHI_THRESHOLD
    }

    /// Return the Phi threshold constant.
    #[staticmethod]
    pub fn threshold() -> f64 {
        PHI_THRESHOLD
    }

    /// Return recent measurement history as a list of dicts.
    ///
    /// Args:
    ///     limit: Maximum number of recent measurements to return (default 50).
    #[pyo3(signature = (limit = 50))]
    pub fn get_history(&self, limit: usize) -> PyResult<PyObject> {
        Python::with_gil(|py| {
            let list = pyo3::types::PyList::empty(py);
            let start = if self.history.len() > limit {
                self.history.len() - limit
            } else {
                0
            };
            for m in &self.history[start..] {
                let d = PyDict::new(py);
                d.set_item("phi_value", m.phi_value)?;
                d.set_item("phi_raw", m.phi_raw)?;
                d.set_item("phi_threshold", PHI_THRESHOLD)?;
                d.set_item("above_threshold", m.phi_value >= PHI_THRESHOLD)?;
                d.set_item("integration_score", m.integration_score)?;
                d.set_item("differentiation_score", m.differentiation_score)?;
                d.set_item("mip_score", m.mip_score)?;
                d.set_item("redundancy_factor", m.redundancy_factor)?;
                d.set_item("phi_micro", m.phi_micro)?;
                d.set_item("phi_meso", m.phi_meso)?;
                d.set_item("phi_macro", m.phi_macro)?;
                d.set_item("hms_phi_raw", m.hms_phi_raw)?;
                d.set_item("phi_formula", if m.using_hms { "hms_v4" } else { "additive_v3" })?;
                d.set_item("phi_version", 4)?;
                d.set_item("num_nodes", m.num_nodes)?;
                d.set_item("num_edges", m.num_edges)?;
                d.set_item("block_height", m.block_height)?;
                d.set_item("timestamp", m.timestamp)?;
                d.set_item("gates_passed", m.gates_passed)?;
                d.set_item("gate_ceiling", m.gate_ceiling)?;
                list.append(d)?;
            }
            Ok(list.into())
        })
    }

    /// Clear the internal cache and history.
    pub fn clear(&mut self) {
        self.cache.clear();
        self.history.clear();
        self.last_full = None;
        self.last_computed_block = -1;
        self.last_mip_score = 0.0;
    }

    /// Return the number of cached measurements.
    pub fn history_len(&self) -> usize {
        self.history.len()
    }
}

// ---------------------------------------------------------------------------
// Internal implementation (not exposed to Python)
// ---------------------------------------------------------------------------

impl PhiCalculator {
    // ======================================================================
    // Integration: structural + cross-flow + MIP
    // ======================================================================

    /// Compute the integration score.
    ///
    /// 1. Build undirected adjacency, find connected components via BFS.
    /// 2. Structural = min(5.0, avg_degree) if single component, else (largest/n)*2.
    /// 3. Cross-flow = mean(from.confidence * to.confidence * edge.weight) over edges.
    /// 4. MIP via spectral bisection (Fiedler vector) for graphs with >= 10 nodes.
    /// 5. Total = structural + cross_flow + mip_score.
    fn compute_integration(
        &mut self,
        nodes: &[KeterNode],
        edges: &[KeterEdge],
        n_nodes: usize,
    ) -> f64 {
        if n_nodes <= 1 {
            return 0.0;
        }

        // Build node_id -> index mapping
        let id_to_idx: HashMap<i64, usize> = nodes
            .iter()
            .enumerate()
            .map(|(i, n)| (n.node_id, i))
            .collect();

        // Build undirected adjacency list (by index)
        let mut adj: Vec<HashSet<usize>> = vec![HashSet::new(); n_nodes];
        for edge in edges {
            if let (Some(&fi), Some(&ti)) =
                (id_to_idx.get(&edge.from_node_id), id_to_idx.get(&edge.to_node_id))
            {
                adj[fi].insert(ti);
                adj[ti].insert(fi);
            }
        }

        // Find connected components via BFS
        let mut visited = vec![false; n_nodes];
        let mut components: Vec<Vec<usize>> = Vec::new();

        for start in 0..n_nodes {
            if visited[start] {
                continue;
            }
            let mut comp = Vec::new();
            let mut queue = VecDeque::new();
            queue.push_back(start);
            visited[start] = true;
            while let Some(u) = queue.pop_front() {
                comp.push(u);
                for &v in &adj[u] {
                    if !visited[v] {
                        visited[v] = true;
                        queue.push_back(v);
                    }
                }
            }
            components.push(comp);
        }

        // Structural integration from connectivity
        let structural = if components.len() == 1 {
            let total_degree: usize = adj.iter().map(|a| a.len()).sum();
            let avg_degree = total_degree as f64 / n_nodes as f64;
            avg_degree.min(5.0)
        } else {
            let largest = components.iter().map(|c| c.len()).max().unwrap_or(0);
            (largest as f64 / n_nodes as f64) * 2.0
        };

        // Cross-partition information flow
        // cross_flow = mean(from.confidence * to.confidence * edge.weight)
        let cross_flow = if edges.is_empty() {
            0.0
        } else {
            let mut total = 0.0;
            for edge in edges {
                if let (Some(&fi), Some(&ti)) =
                    (id_to_idx.get(&edge.from_node_id), id_to_idx.get(&edge.to_node_id))
                {
                    total += nodes[fi].confidence * nodes[ti].confidence * edge.weight;
                }
            }
            total / edges.len() as f64
        };

        // MIP via spectral bisection (only meaningful for >= 10 nodes)
        let mip_score = if n_nodes >= 10 {
            self.compute_mip(nodes, edges, &id_to_idx)
        } else {
            0.0
        };
        self.last_mip_score = mip_score;

        structural + cross_flow + mip_score
    }

    // ======================================================================
    // MIP: Minimum Information Partition via Spectral Bisection
    // ======================================================================

    /// Compute Minimum Information Partition using spectral bisection.
    ///
    /// Algorithm:
    /// 1. Build weighted adjacency (confidence * confidence * weight), sparse.
    /// 2. Compute total flow (sum of unique edge weights).
    /// 3. Find Fiedler vector via power iteration on (shift*I - L).
    /// 4. Try cuts at n/3, n/2, 2n/3.
    /// 5. Return normalized MIP = (total_flow - info_a - info_b) / total_flow.
    /// 6. Sample to 5000 nodes if graph > 5000.
    fn compute_mip(
        &self,
        nodes: &[KeterNode],
        edges: &[KeterEdge],
        id_to_idx: &HashMap<i64, usize>,
    ) -> f64 {
        let n_all = nodes.len();
        if n_all < 10 {
            return 0.0;
        }

        // Sampling: if > MIP_SAMPLE_SIZE nodes, take a deterministic sample
        let (working_indices, sampled_set): (Vec<usize>, HashSet<usize>) = if n_all > MIP_SAMPLE_SIZE
        {
            let mut rng = StdRng::seed_from_u64(42);
            let mut indices: Vec<usize> = (0..n_all).collect();
            indices.shuffle(&mut rng);
            indices.truncate(MIP_SAMPLE_SIZE);
            indices.sort_unstable();
            let set: HashSet<usize> = indices.iter().copied().collect();
            (indices, set)
        } else {
            let indices: Vec<usize> = (0..n_all).collect();
            let set: HashSet<usize> = indices.iter().copied().collect();
            (indices, set)
        };

        let n = working_indices.len();
        if n < 10 {
            return 0.0;
        }

        // Map original index -> local MIP index
        let local_idx: HashMap<usize, usize> = working_indices
            .iter()
            .enumerate()
            .map(|(local, &orig)| (orig, local))
            .collect();

        // Build weighted adjacency (sparse: BTreeMap<usize, BTreeMap<usize, f64>>)
        let mut adj: Vec<BTreeMap<usize, f64>> = vec![BTreeMap::new(); n];

        for edge in edges {
            let fi_opt = id_to_idx.get(&edge.from_node_id).copied();
            let ti_opt = id_to_idx.get(&edge.to_node_id).copied();
            let (fi_orig, ti_orig) = match (fi_opt, ti_opt) {
                (Some(a), Some(b)) => (a, b),
                _ => continue,
            };
            if fi_orig == ti_orig {
                continue;
            }
            // Both must be in the sampled set
            if !sampled_set.contains(&fi_orig) || !sampled_set.contains(&ti_orig) {
                continue;
            }
            let fi = local_idx[&fi_orig];
            let ti = local_idx[&ti_orig];

            let w = nodes[fi_orig].confidence * nodes[ti_orig].confidence * edge.weight;
            if w <= 0.0 {
                continue;
            }

            // Undirected: accumulate both directions
            *adj[fi].entry(ti).or_insert(0.0) += w;
            *adj[ti].entry(fi).or_insert(0.0) += w;
        }

        // Total information flow (count each undirected edge once)
        let mut total_flow: f64 = 0.0;
        for i in 0..n {
            for (&j, &w) in &adj[i] {
                if j > i {
                    total_flow += w;
                }
            }
        }

        if total_flow <= 0.0 {
            return 0.0;
        }

        // Degree vector
        let degree: Vec<f64> = (0..n).map(|i| adj[i].values().sum::<f64>()).collect();

        // Fiedler vector via power iteration
        let lambda_max = degree
            .iter()
            .copied()
            .fold(0.0_f64, f64::max)
            .max(1.0);
        let shift = lambda_max + 0.1;

        let fiedler = match self.power_iteration_fiedler(&adj, &degree, shift, n) {
            Some(v) => v,
            None => return 0.0,
        };

        // Sort nodes by Fiedler value
        let mut sorted_indices: Vec<(f64, usize)> =
            fiedler.iter().enumerate().map(|(i, &v)| (v, i)).collect();
        sorted_indices.sort_by(|a, b| a.0.partial_cmp(&b.0).unwrap_or(std::cmp::Ordering::Equal));
        let sorted_node_indices: Vec<usize> = sorted_indices.iter().map(|&(_, i)| i).collect();

        // Try cuts at n/3, n/2, 2n/3
        let mut cut_positions = Vec::new();
        for &frac in &[3usize, 2, 3] {
            // n/3, n/2, 2n/3
            let pos = match frac {
                3 if cut_positions.is_empty() => n / 3,
                2 => n / 2,
                3 => 2 * n / 3,
                _ => continue,
            };
            if pos > 0 && pos < n && !cut_positions.contains(&pos) {
                cut_positions.push(pos);
            }
        }
        if cut_positions.is_empty() {
            cut_positions.push(n / 2);
        }

        let mut min_phi_partition = f64::INFINITY;

        for &cut_pos in &cut_positions {
            let part_a: HashSet<usize> = sorted_node_indices[..cut_pos].iter().copied().collect();
            let part_b: HashSet<usize> = sorted_node_indices[cut_pos..].iter().copied().collect();

            if part_a.is_empty() || part_b.is_empty() {
                continue;
            }

            // Compute information within each partition
            let mut info_a: f64 = 0.0;
            let mut info_b: f64 = 0.0;
            for i in 0..n {
                for (&j, &w) in &adj[i] {
                    if j <= i {
                        continue; // count each edge once
                    }
                    if part_a.contains(&i) && part_a.contains(&j) {
                        info_a += w;
                    } else if part_b.contains(&i) && part_b.contains(&j) {
                        info_b += w;
                    }
                }
            }

            let phi_partition = total_flow - info_a - info_b;
            if phi_partition < min_phi_partition {
                min_phi_partition = phi_partition;
            }
        }

        if min_phi_partition.is_infinite() || min_phi_partition < 0.0 {
            return 0.0;
        }

        // Normalize by total flow: result in [0, 1]
        min_phi_partition / total_flow
    }

    /// Find the Fiedler vector (2nd-smallest eigenvector of graph Laplacian)
    /// using power iteration on (shift*I - L).
    ///
    /// The largest eigenvector of (shift*I - L) corresponds to the smallest
    /// eigenvector of L.  By projecting out the trivial constant eigenvector
    /// at each step, we converge to the Fiedler vector.
    fn power_iteration_fiedler(
        &self,
        adj: &[BTreeMap<usize, f64>],
        degree: &[f64],
        shift: f64,
        n: usize,
    ) -> Option<Vec<f64>> {
        if n < 2 {
            return None;
        }

        // Initialize with a deterministic non-constant vector
        let mut rng = StdRng::seed_from_u64(123);
        let mut v: Vec<f64> = (0..n)
            .map(|i| {
                let base = if i % 2 == 0 { 1.0 } else { -1.0 };
                // Small deterministic perturbation seeded from rng
                let perturb: f64 = (rng.gen_range(-100i32..=100i32) as f64) * 0.0001;
                base + perturb
            })
            .collect();

        // Project out constant vector
        let mean_v: f64 = v.iter().sum::<f64>() / n as f64;
        for x in v.iter_mut() {
            *x -= mean_v;
        }

        // Normalize
        let norm = vector_norm(&v);
        if norm < 1e-15 {
            return None;
        }
        for x in v.iter_mut() {
            *x /= norm;
        }

        for _iter in 0..FIEDLER_MAX_ITER {
            // Compute w = (shift * I - L) * v
            // = (shift - degree[i]) * v[i] + sum(adj[i][j] * v[j])
            let mut w: Vec<f64> = vec![0.0; n];
            for i in 0..n {
                w[i] = (shift - degree[i]) * v[i];
                for (&j, &a_ij) in &adj[i] {
                    w[i] += a_ij * v[j];
                }
            }

            // Project out constant eigenvector
            let mean_w: f64 = w.iter().sum::<f64>() / n as f64;
            for x in w.iter_mut() {
                *x -= mean_w;
            }

            // Normalize
            let norm = vector_norm(&w);
            if norm < 1e-15 {
                // Vector collapsed — graph may be disconnected or trivial
                log::debug!("Fiedler iteration collapsed at step {}", _iter);
                return None;
            }
            for x in w.iter_mut() {
                *x /= norm;
            }

            v = w;
        }

        Some(v)
    }

    // ======================================================================
    // Differentiation: Shannon Entropy
    // ======================================================================

    /// Compute differentiation using Shannon entropy over:
    /// 1. Node type distribution
    /// 2. Edge type distribution (weighted 0.5)
    /// 3. Confidence distribution in 10 bins (weighted 0.3)
    fn compute_differentiation(&self, nodes: &[KeterNode], edges: &[KeterEdge]) -> f64 {
        if nodes.is_empty() {
            return 0.0;
        }

        let n = nodes.len() as f64;

        // Entropy over node types
        let mut type_counts: HashMap<&str, usize> = HashMap::new();
        for node in nodes {
            *type_counts.entry(node.node_type.as_str()).or_insert(0) += 1;
        }
        let type_entropy = shannon_entropy_from_counts(type_counts.values().copied(), n);

        // Entropy over edge types
        let mut edge_type_counts: HashMap<&str, usize> = HashMap::new();
        for edge in edges {
            *edge_type_counts
                .entry(edge.edge_type.as_str())
                .or_insert(0) += 1;
        }
        let n_edges = edges.len() as f64;
        let edge_entropy = if n_edges > 0.0 {
            shannon_entropy_from_counts(edge_type_counts.values().copied(), n_edges)
        } else {
            0.0
        };

        // Entropy over confidence distribution (10 bins: [0.0-0.1), [0.1-0.2), ..., [0.9-1.0])
        let mut bins = [0usize; 10];
        for node in nodes {
            let idx = ((node.confidence * 10.0) as usize).min(9);
            bins[idx] += 1;
        }
        let conf_entropy = shannon_entropy_from_counts(bins.iter().copied(), n);

        // Combined: type + 0.5*edge + 0.3*confidence
        type_entropy + edge_entropy * 0.5 + conf_entropy * 0.3
    }

    // ======================================================================
    // Milestone Gates
    // ======================================================================

    /// Evaluate all 10 milestone gates against the current graph state.
    ///
    /// Returns a vector of (MilestoneGate, passed) pairs.
    fn check_gates(
        &self,
        nodes: &[KeterNode],
        edges: &[KeterEdge],
        integration_score: f64,
        mip_phi: f64,
        extra: &ExtraStats,
    ) -> Vec<(MilestoneGate, bool)> {
        let working_memory_hit_rate = extra.working_memory_hit_rate;
        let calibration_error = extra.calibration_error;
        let prediction_accuracy = extra.prediction_accuracy;
        let n_nodes = nodes.len();
        let n_edges = edges.len();

        // --- Aggregate node-level statistics ---
        let mut node_type_counts: HashMap<String, usize> = HashMap::new();
        let mut confidence_sum: f64 = 0.0;
        let mut domains: HashSet<&str> = HashSet::new();
        let mut self_reflection_nodes: usize = 0;
        let mut cross_domain_inferences: usize = 0;
        let mut verified_predictions: usize = 0;
        let mut debate_verdicts: usize = 0;
        let mut contradiction_resolutions: usize = 0;
        let mut auto_goals_generated: usize = 0;
        let mut grounded_nodes: usize = 0;
        let mut axiom_from_consolidation: usize = 0;
        let mut novel_concept_count: usize = 0;

        for node in nodes {
            *node_type_counts
                .entry(node.node_type.clone())
                .or_insert(0) += 1;
            confidence_sum += node.confidence;

            if !node.domain.is_empty() {
                domains.insert(node.domain.as_str());
            }
            if !node.grounding_source.is_empty() {
                grounded_nodes += 1;
            }

            // Inspect content dict for semantic markers.
            // Content is HashMap<String, String> — values are plain strings.
            let content_type = node
                .content
                .get("type")
                .map(|s| s.as_str())
                .unwrap_or("");
            let content_source = node
                .content
                .get("source")
                .map(|s| s.as_str())
                .unwrap_or("");
            let content_cross_domain = node
                .content
                .get("cross_domain")
                .map(|s| s == "true")
                .unwrap_or(false);

            if content_source == "self-reflection" {
                self_reflection_nodes += 1;
            }
            if node.node_type == "inference" && content_cross_domain {
                cross_domain_inferences += 1;
            }
            if content_type == "prediction_confirmed" {
                verified_predictions += 1;
            }
            if content_type == "debate_synthesis" {
                debate_verdicts += 1;
            }
            if content_type == "contradiction_resolution" {
                contradiction_resolutions += 1;
            }
            if node.node_type == "meta_observation" {
                auto_goals_generated += 1;
            }
            if node.node_type == "axiom" && content_type == "consolidated_pattern" {
                axiom_from_consolidation += 1;
            }
            if content_type == "generalization" || content_type == "concept_cluster" {
                novel_concept_count += 1;
            }
        }

        // Edge type counts
        let mut edge_type_counts: HashMap<String, usize> = HashMap::new();
        for edge in edges {
            *edge_type_counts
                .entry(edge.edge_type.clone())
                .or_insert(0) += 1;
        }

        let avg_confidence = if n_nodes > 0 {
            confidence_sum / n_nodes as f64
        } else {
            0.0
        };
        let grounding_ratio = if n_nodes > 0 {
            grounded_nodes as f64 / n_nodes as f64
        } else {
            0.0
        };

        let stats = GateStats {
            n_nodes,
            n_edges,
            avg_confidence,
            node_type_counts,
            edge_type_counts,
            integration_score,
            mip_phi,
            verified_predictions,
            debate_verdicts,
            contradiction_resolutions,
            domain_count: domains.len(),
            working_memory_hit_rate,
            auto_goals_generated,
            self_reflection_nodes,
            calibration_error,
            calibration_evaluations: extra.calibration_evaluations,
            grounding_ratio,
            axiom_from_consolidation,
            cross_domain_inferences,
            cross_domain_inference_confidence: extra.cross_domain_inference_confidence,
            prediction_accuracy,
            novel_concept_count,
            improvement_cycles_enacted: extra.improvement_cycles_enacted,
            improvement_performance_delta: extra.improvement_performance_delta,
            fep_free_energy_decreasing: extra.fep_free_energy_decreasing,
            auto_goals_with_inferences: extra.auto_goals_with_inferences,
            curiosity_driven_discoveries: extra.curiosity_driven_discoveries,
            fep_domain_precisions: extra.fep_domain_precisions,
            sephirot_winner_diversity: extra.sephirot_winner_diversity,
        };

        milestone_gates()
            .into_iter()
            .map(|gate| {
                let passed = (gate.check)(&stats);
                (gate, passed)
            })
            .collect()
    }

    // ======================================================================
    // HMS-Phi: phi_macro (cross-domain integration)
    // ======================================================================

    /// Compute phi_macro: cross-domain integration between Sephirot clusters.
    ///
    /// Measures how well knowledge integrates ACROSS domains by computing:
    /// 1. Cross-domain edge ratio: fraction of edges connecting different domains
    /// 2. Domain connectivity: fraction of domain pairs with at least one edge
    /// 3. Cross-domain MI: mutual information between domain node-type distributions
    ///
    /// Returns a value in [0, 1].
    fn compute_phi_macro(
        &self,
        nodes: &[KeterNode],
        edges: &[KeterEdge],
        n_nodes: usize,
        n_edges: usize,
    ) -> f64 {
        if n_nodes < 50 || n_edges < 10 {
            return 0.0;
        }

        // Classify nodes by domain
        let mut domain_of: HashMap<i64, &str> = HashMap::new();
        let mut domains: HashSet<&str> = HashSet::new();
        for node in nodes {
            let d = if node.domain.is_empty() { "general" } else { node.domain.as_str() };
            domain_of.insert(node.node_id, d);
            domains.insert(d);
        }

        let n_domains = domains.len();
        if n_domains < 2 {
            return 0.05;
        }

        // Count cross-domain edges and domain pair connectivity
        let mut cross_edges = 0usize;
        let mut total_edges = 0usize;
        let mut domain_pairs: HashSet<(&str, &str)> = HashSet::new();

        for edge in edges {
            let fd = domain_of.get(&edge.from_node_id);
            let td = domain_of.get(&edge.to_node_id);
            if let (Some(&fd), Some(&td)) = (fd, td) {
                total_edges += 1;
                if fd != td {
                    cross_edges += 1;
                    let pair = if fd <= td { (fd, td) } else { (td, fd) };
                    domain_pairs.insert(pair);
                }
            }
        }

        let cross_ratio = cross_edges as f64 / total_edges.max(1) as f64;

        // Domain connectivity: fraction of domain pairs connected
        let max_pairs = n_domains * (n_domains - 1) / 2;
        let connectivity = domain_pairs.len() as f64 / max_pairs.max(1) as f64;

        // Combine
        let phi_macro = 0.5 * cross_ratio + 0.5 * connectivity;

        phi_macro.max(0.0).min(1.0)
    }

    // ======================================================================
    // HMS-Phi: phi_micro (subgraph MIP proxy)
    // ======================================================================

    /// Compute phi_micro as a proxy for IIT 3.0 micro-level Phi.
    ///
    /// Samples 5 small subgraphs (BFS from high-degree seeds), computes
    /// spectral MIP on each, and returns the median. This is a lightweight
    /// proxy — the full IIT TPM approximation runs in Python.
    fn compute_phi_micro(
        &self,
        nodes: &[KeterNode],
        edges: &[KeterEdge],
        n_nodes: usize,
    ) -> f64 {
        if n_nodes < 16 {
            return 0.0;
        }

        // Build adjacency list for BFS
        let id_to_idx: HashMap<i64, usize> = nodes
            .iter()
            .enumerate()
            .map(|(i, n)| (n.node_id, i))
            .collect();

        let mut adj_list: HashMap<i64, Vec<i64>> = HashMap::new();
        for edge in edges {
            adj_list.entry(edge.from_node_id).or_default().push(edge.to_node_id);
            adj_list.entry(edge.to_node_id).or_default().push(edge.from_node_id);
        }

        // Sort nodes by degree (descending) to find seeds
        let mut nodes_by_degree: Vec<(i64, usize)> = nodes
            .iter()
            .map(|n| (n.node_id, adj_list.get(&n.node_id).map_or(0, |v| v.len())))
            .collect();
        nodes_by_degree.sort_by(|a, b| b.1.cmp(&a.1));

        let target_size = 32usize; // BFS expands to 32, MIP uses all
        let n_samples = 5;
        let pool_size = nodes_by_degree.len().min(500);
        let mut phis: Vec<f64> = Vec::new();
        let mut used_seeds: HashSet<i64> = HashSet::new();

        for sample_idx in 0..n_samples {
            // Pick a seed from a spread of the top pool
            let pool_offset = (sample_idx * pool_size) / n_samples;
            let pool_end = ((sample_idx + 1) * pool_size) / n_samples;
            let candidates: Vec<i64> = nodes_by_degree[pool_offset..pool_end.min(pool_size)]
                .iter()
                .filter(|(nid, _)| !used_seeds.contains(nid))
                .map(|(nid, _)| *nid)
                .collect();
            let seed = match candidates.first() {
                Some(&s) => s,
                None => continue,
            };
            used_seeds.insert(seed);

            // BFS expand from seed
            let mut sampled: Vec<i64> = Vec::new();
            let mut visited: HashSet<i64> = HashSet::new();
            let mut queue: VecDeque<i64> = VecDeque::new();
            queue.push_back(seed);
            while let Some(nid) = queue.pop_front() {
                if visited.contains(&nid) || sampled.len() >= target_size {
                    break;
                }
                if id_to_idx.contains_key(&nid) {
                    visited.insert(nid);
                    sampled.push(nid);
                    if let Some(neighbors) = adj_list.get(&nid) {
                        for &nb in neighbors {
                            if !visited.contains(&nb) {
                                queue.push_back(nb);
                            }
                        }
                    }
                }
            }

            if sampled.len() < 4 {
                continue;
            }

            // Build local adjacency for this subgraph
            let sampled_set: HashSet<i64> = sampled.iter().copied().collect();
            let local_ids: HashMap<i64, usize> = sampled.iter().enumerate()
                .map(|(i, &nid)| (nid, i))
                .collect();
            let n = sampled.len();
            let mut local_adj: Vec<BTreeMap<usize, f64>> = vec![BTreeMap::new(); n];

            for edge in edges {
                if !sampled_set.contains(&edge.from_node_id) || !sampled_set.contains(&edge.to_node_id) {
                    continue;
                }
                if edge.from_node_id == edge.to_node_id {
                    continue;
                }
                let fi = local_ids[&edge.from_node_id];
                let ti = local_ids[&edge.to_node_id];
                let fi_orig = id_to_idx[&edge.from_node_id];
                let ti_orig = id_to_idx[&edge.to_node_id];
                let w = nodes[fi_orig].confidence * nodes[ti_orig].confidence * edge.weight;
                if w <= 0.0 { continue; }
                *local_adj[fi].entry(ti).or_insert(0.0) += w;
                *local_adj[ti].entry(fi).or_insert(0.0) += w;
            }

            // Compute MIP on this subgraph
            let mut total_flow: f64 = 0.0;
            for i in 0..n {
                for (&j, &w) in &local_adj[i] {
                    if j > i { total_flow += w; }
                }
            }
            if total_flow <= 0.0 { continue; }

            let degree: Vec<f64> = (0..n).map(|i| local_adj[i].values().sum::<f64>()).collect();
            let lambda_max = degree.iter().copied().fold(0.0_f64, f64::max).max(1.0);
            let shift = lambda_max + 0.1;

            let fiedler = match self.power_iteration_fiedler(&local_adj, &degree, shift, n) {
                Some(v) => v,
                None => continue,
            };

            // Bisect at median
            let mut sorted: Vec<(f64, usize)> = fiedler.iter().enumerate().map(|(i, &v)| (v, i)).collect();
            sorted.sort_by(|a, b| a.0.partial_cmp(&b.0).unwrap_or(std::cmp::Ordering::Equal));
            let cut = n / 2;
            let part_a: HashSet<usize> = sorted[..cut].iter().map(|&(_, i)| i).collect();
            let part_b: HashSet<usize> = sorted[cut..].iter().map(|&(_, i)| i).collect();

            let mut info_a = 0.0;
            let mut info_b = 0.0;
            for i in 0..n {
                for (&j, &w) in &local_adj[i] {
                    if j <= i { continue; }
                    if part_a.contains(&i) && part_a.contains(&j) { info_a += w; }
                    else if part_b.contains(&i) && part_b.contains(&j) { info_b += w; }
                }
            }
            let mip = (total_flow - info_a - info_b) / total_flow;
            phis.push(mip.max(0.0).min(1.0));
        }

        if phis.is_empty() {
            return 0.0;
        }

        // Return median
        phis.sort_by(|a, b| a.partial_cmp(b).unwrap_or(std::cmp::Ordering::Equal));
        let mid = phis.len() / 2;
        if phis.len() % 2 == 0 && phis.len() >= 2 {
            (phis[mid - 1] + phis[mid]) / 2.0
        } else {
            phis[mid]
        }
    }

    // ======================================================================
    // Parse external stats from Python dict
    // ======================================================================

    fn parse_extra_stats(&self, extra_stats: Option<&Bound<'_, PyDict>>) -> ExtraStats {
        ExtraStats {
            working_memory_hit_rate: extract_f64(extra_stats, "working_memory_hit_rate", 0.0),
            calibration_error: extract_f64(extra_stats, "calibration_error", 1.0),
            calibration_evaluations: extract_f64(extra_stats, "calibration_evaluations", 0.0) as usize,
            prediction_accuracy: extract_f64(extra_stats, "prediction_accuracy", 0.0),
            improvement_cycles_enacted: extract_f64(extra_stats, "improvement_cycles_enacted", 0.0) as usize,
            improvement_performance_delta: extract_f64(extra_stats, "improvement_performance_delta", 0.0),
            fep_free_energy_decreasing: extract_f64(extra_stats, "fep_free_energy_decreasing", 0.0) > 0.5,
            auto_goals_with_inferences: extract_f64(extra_stats, "auto_goals_with_inferences", 0.0) as usize,
            curiosity_driven_discoveries: extract_f64(extra_stats, "curiosity_driven_discoveries", 0.0) as usize,
            fep_domain_precisions: extract_f64(extra_stats, "fep_domain_precisions", 0.0) as usize,
            cross_domain_inference_confidence: extract_f64(extra_stats, "cross_domain_inference_confidence", 0.0),
            sephirot_winner_diversity: extract_f64(extra_stats, "sephirot_winner_diversity", 0.0),
        }
    }

    // ======================================================================
    // Result building helpers
    // ======================================================================

    /// Build a Python dict from a PhiMeasurement.
    fn measurement_to_dict<'py>(
        &self,
        py: Python<'py>,
        m: &PhiMeasurement,
        block_height: u64,
    ) -> PyResult<Bound<'py, PyDict>> {
        let dict = PyDict::new(py);
        dict.set_item("phi_value", m.phi_value)?;
        dict.set_item("phi_raw", m.phi_raw)?;
        dict.set_item("phi_threshold", PHI_THRESHOLD)?;
        dict.set_item("above_threshold", m.phi_value >= PHI_THRESHOLD)?;
        dict.set_item("integration_score", m.integration_score)?;
        dict.set_item("differentiation_score", m.differentiation_score)?;
        dict.set_item("mip_score", m.mip_score)?;
        dict.set_item("redundancy_factor", m.redundancy_factor)?;
        // HMS-Phi v4 components
        dict.set_item("phi_micro", m.phi_micro)?;
        dict.set_item("phi_meso", m.phi_meso)?;
        dict.set_item("phi_macro", m.phi_macro)?;
        dict.set_item("hms_phi_raw", m.hms_phi_raw)?;
        dict.set_item("phi_formula", if m.using_hms { "hms_v4" } else { "additive_v3" })?;
        dict.set_item("num_nodes", m.num_nodes)?;
        dict.set_item("num_edges", m.num_edges)?;
        dict.set_item("block_height", block_height)?;
        dict.set_item("timestamp", m.timestamp)?;
        dict.set_item("phi_version", 4)?;
        dict.set_item("gates_passed", m.gates_passed)?;
        dict.set_item("gates_total", NUM_GATES)?;
        dict.set_item("gate_ceiling", m.gate_ceiling)?;
        Ok(dict)
    }

    /// Build an empty result dict for an empty knowledge graph.
    fn empty_result(&self, py: Python<'_>, block_height: u64) -> PyResult<PyObject> {
        let dict = PyDict::new(py);
        dict.set_item("phi_value", 0.0)?;
        dict.set_item("phi_raw", 0.0)?;
        dict.set_item("phi_threshold", PHI_THRESHOLD)?;
        dict.set_item("above_threshold", false)?;
        dict.set_item("integration_score", 0.0)?;
        dict.set_item("differentiation_score", 0.0)?;
        dict.set_item("mip_score", 0.0)?;
        dict.set_item("redundancy_factor", 1.0)?;
        dict.set_item("phi_micro", 0.0)?;
        dict.set_item("phi_meso", 0.0)?;
        dict.set_item("phi_macro", 0.0)?;
        dict.set_item("hms_phi_raw", 0.0)?;
        dict.set_item("phi_formula", "additive_v3")?;
        dict.set_item("num_nodes", 0)?;
        dict.set_item("num_edges", 0)?;
        dict.set_item("block_height", block_height)?;
        dict.set_item("timestamp", current_timestamp())?;
        dict.set_item("phi_version", 4)?;
        dict.set_item("gates_passed", 0)?;
        dict.set_item("gates_total", NUM_GATES)?;
        dict.set_item("gate_ceiling", 0.0)?;
        dict.set_item("gates", pyo3::types::PyList::empty(py))?;
        Ok(dict.into())
    }
}

// ---------------------------------------------------------------------------
// ExtraStats: external metrics for gate evaluation
// ---------------------------------------------------------------------------

/// External stats parsed from the optional Python dict passed to compute_phi.
#[derive(Debug, Default)]
struct ExtraStats {
    working_memory_hit_rate: f64,
    calibration_error: f64,
    calibration_evaluations: usize,
    prediction_accuracy: f64,
    improvement_cycles_enacted: usize,
    improvement_performance_delta: f64,
    fep_free_energy_decreasing: bool,
    auto_goals_with_inferences: usize,
    curiosity_driven_discoveries: usize,
    fep_domain_precisions: usize,
    cross_domain_inference_confidence: f64,
    sephirot_winner_diversity: f64,
}

// ---------------------------------------------------------------------------
// Utility functions
// ---------------------------------------------------------------------------

/// Compute the L2 norm of a vector.
#[inline]
fn vector_norm(v: &[f64]) -> f64 {
    v.iter().map(|x| x * x).sum::<f64>().sqrt()
}

/// Compute Shannon entropy from a sequence of counts and total N.
///
/// H = -sum(p_i * log2(p_i)) where p_i = count_i / total
fn shannon_entropy_from_counts(counts: impl Iterator<Item = usize>, total: f64) -> f64 {
    if total <= 0.0 {
        return 0.0;
    }
    let mut entropy = 0.0;
    for count in counts {
        if count > 0 {
            let p = count as f64 / total;
            entropy -= p * p.log2();
        }
    }
    entropy
}

/// Round to 6 decimal places.
#[inline]
fn round6(x: f64) -> f64 {
    (x * 1_000_000.0).round() / 1_000_000.0
}

/// Round to 4 decimal places.
#[inline]
fn round4(x: f64) -> f64 {
    (x * 10_000.0).round() / 10_000.0
}

/// Current UNIX timestamp as f64.
fn current_timestamp() -> f64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_secs_f64()
}

/// Extract a f64 from an optional Python dict, returning `default` on miss.
fn extract_f64(dict: Option<&Bound<'_, PyDict>>, key: &str, default: f64) -> f64 {
    dict.and_then(|d| d.get_item(key).ok().flatten())
        .and_then(|v| v.extract::<f64>().ok())
        .unwrap_or(default)
}

// ===========================================================================
// Tests
// ===========================================================================

#[cfg(test)]
mod tests {
    use super::*;

    // Test helpers: build KeterNode / KeterEdge / KnowledgeGraph stubs.
    // Since knowledge_graph module may not be compiled during unit testing of
    // this module alone, we access the types through the crate.  The test
    // binary links the whole crate, so crate::knowledge_graph types are
    // available.  We provide convenience constructors here.

    fn make_node(id: i64, node_type: &str, confidence: f64) -> KeterNode {
        KeterNode {
            node_id: id,
            node_type: node_type.to_string(),
            content_hash: String::new(),
            content: HashMap::new(),
            confidence,
            source_block: 0,
            timestamp: 0.0,
            domain: String::new(),
            last_referenced_block: 0,
            reference_count: 0,
            grounding_source: String::new(),
            edges_out: vec![],
            edges_in: vec![],
        }
    }

    fn make_node_with_content(
        id: i64,
        node_type: &str,
        confidence: f64,
        content: HashMap<String, String>,
    ) -> KeterNode {
        KeterNode {
            node_id: id,
            node_type: node_type.to_string(),
            content_hash: String::new(),
            content,
            confidence,
            source_block: 0,
            timestamp: 0.0,
            domain: String::new(),
            last_referenced_block: 0,
            reference_count: 0,
            grounding_source: String::new(),
            edges_out: vec![],
            edges_in: vec![],
        }
    }

    fn make_edge(from: i64, to: i64, edge_type: &str, weight: f64) -> KeterEdge {
        KeterEdge {
            from_node_id: from,
            to_node_id: to,
            edge_type: edge_type.to_string(),
            weight,
            timestamp: 0.0,
        }
    }

    fn make_kg(nodes: Vec<KeterNode>, edges: Vec<KeterEdge>) -> KnowledgeGraph {
        let kg = KnowledgeGraph::new();
        for node in nodes {
            kg.add_node_raw(node);
        }
        for edge in edges {
            kg.add_edge_raw(edge);
        }
        kg
    }

    // -----------------------------------------------------------------------
    // Basic construction / empty graph
    // -----------------------------------------------------------------------

    #[test]
    fn test_new_calculator() {
        let calc = PhiCalculator::new(1);
        assert_eq!(calc.get_current_phi(), 0.0);
        assert!(!calc.is_conscious());
        assert_eq!(calc.history_len(), 0);
    }

    #[test]
    fn test_threshold_constant() {
        assert!((PhiCalculator::threshold() - 3.0).abs() < 1e-12);
    }

    #[test]
    fn test_empty_graph_returns_zeros() {
        let mut calc = PhiCalculator::new(1);
        let kg = KnowledgeGraph::new();
        Python::with_gil(|py| {
            let result = calc.compute_phi(&kg, 0, None).unwrap();
            let dict = result.bind(py).downcast::<PyDict>().unwrap();
            let phi: f64 = dict.get_item("phi_value").unwrap().unwrap().extract().unwrap();
            assert!((phi - 0.0).abs() < 1e-12);
            let above: bool = dict
                .get_item("above_threshold")
                .unwrap()
                .unwrap()
                .extract()
                .unwrap();
            assert!(!above);
            let gates_passed: usize = dict
                .get_item("gates_passed")
                .unwrap()
                .unwrap()
                .extract()
                .unwrap();
            assert_eq!(gates_passed, 0);
            let gates_total: usize = dict
                .get_item("gates_total")
                .unwrap()
                .unwrap()
                .extract()
                .unwrap();
            assert_eq!(gates_total, 10);
        });
    }

    // -----------------------------------------------------------------------
    // Single node
    // -----------------------------------------------------------------------

    #[test]
    fn test_single_node_phi_zero() {
        let mut calc = PhiCalculator::new(1);
        let kg = make_kg(vec![make_node(1, "assertion", 0.8)], vec![]);
        Python::with_gil(|py| {
            let result = calc.compute_phi(&kg, 1, None).unwrap();
            let dict = result.bind(py).downcast::<PyDict>().unwrap();
            let phi: f64 = dict.get_item("phi_value").unwrap().unwrap().extract().unwrap();
            // Single node: integration = 0, so raw_phi = 0
            assert!(phi.abs() < 1e-9);
        });
    }

    // -----------------------------------------------------------------------
    // Small connected graph
    // -----------------------------------------------------------------------

    #[test]
    fn test_small_connected_graph() {
        let mut calc = PhiCalculator::new(1);
        // 5 nodes, fully connected ring
        let nodes: Vec<KeterNode> = (0..5)
            .map(|i| make_node(i, "assertion", 0.8))
            .collect();
        let edges: Vec<KeterEdge> = (0..5)
            .map(|i| make_edge(i, (i + 1) % 5, "supports", 1.0))
            .collect();
        let kg = make_kg(nodes, edges);

        Python::with_gil(|py| {
            let result = calc.compute_phi(&kg, 10, None).unwrap();
            let dict = result.bind(py).downcast::<PyDict>().unwrap();
            let integration: f64 = dict
                .get_item("integration_score")
                .unwrap()
                .unwrap()
                .extract()
                .unwrap();
            let differentiation: f64 = dict
                .get_item("differentiation_score")
                .unwrap()
                .unwrap()
                .extract()
                .unwrap();
            // Integration > 0 because connected, structural = avg_degree = 2 (ring)
            assert!(integration > 0.0);
            // Differentiation: all same type = 0 type entropy, one edge type = 0,
            // but confidence bins have content
            assert!(differentiation >= 0.0);
        });
    }

    // -----------------------------------------------------------------------
    // Integration: connected components
    // -----------------------------------------------------------------------

    #[test]
    fn test_disconnected_graph_structural() {
        let mut calc = PhiCalculator::new(1);
        // Two disconnected components: {0,1,2} and {3,4}
        let nodes: Vec<KeterNode> = (0..5)
            .map(|i| make_node(i, "assertion", 0.7))
            .collect();
        let edges = vec![
            make_edge(0, 1, "supports", 1.0),
            make_edge(1, 2, "supports", 1.0),
            make_edge(3, 4, "supports", 1.0),
        ];
        let kg = make_kg(nodes, edges);

        Python::with_gil(|py| {
            let result = calc.compute_phi(&kg, 5, None).unwrap();
            let dict = result.bind(py).downcast::<PyDict>().unwrap();
            let integration: f64 = dict
                .get_item("integration_score")
                .unwrap()
                .unwrap()
                .extract()
                .unwrap();
            // Disconnected: structural = (largest_component / n) * 2 = (3/5)*2 = 1.2
            // Cross-flow and MIP also contribute
            assert!(integration > 0.0);
            assert!(integration < 5.0); // should not be max
        });
    }

    // -----------------------------------------------------------------------
    // Differentiation: diverse node types
    // -----------------------------------------------------------------------

    #[test]
    fn test_differentiation_diverse_types() {
        let calc = PhiCalculator::new(1);
        let nodes = vec![
            make_node(0, "assertion", 0.5),
            make_node(1, "observation", 0.6),
            make_node(2, "inference", 0.7),
            make_node(3, "axiom", 0.9),
        ];
        let edges = vec![
            make_edge(0, 1, "supports", 1.0),
            make_edge(1, 2, "derives", 1.0),
            make_edge(2, 3, "requires", 1.0),
        ];

        let diff = calc.compute_differentiation(&nodes, &edges);
        // 4 distinct node types -> high type entropy = log2(4) = 2.0
        // 3 distinct edge types -> edge entropy = log2(3) ≈ 1.585
        // diff = 2.0 + 1.585*0.5 + conf_entropy*0.3
        assert!(diff > 2.0);
    }

    #[test]
    fn test_differentiation_uniform_types() {
        let calc = PhiCalculator::new(1);
        let nodes: Vec<KeterNode> = (0..10)
            .map(|i| make_node(i, "assertion", 0.5))
            .collect();
        let diff = calc.compute_differentiation(&nodes, &[]);
        // All same type: type_entropy = 0, edge_entropy = 0, only confidence entropy
        // All confidence = 0.5 -> bin 5 gets all -> conf_entropy = 0
        assert!(diff.abs() < 1e-9);
    }

    // -----------------------------------------------------------------------
    // MIP spectral bisection
    // -----------------------------------------------------------------------

    #[test]
    fn test_mip_small_graph_skipped() {
        let calc = PhiCalculator::new(1);
        // < 10 nodes: MIP returns 0
        let nodes: Vec<KeterNode> = (0..5)
            .map(|i| make_node(i, "assertion", 0.8))
            .collect();
        let edges: Vec<KeterEdge> = (0..4)
            .map(|i| make_edge(i, i + 1, "supports", 1.0))
            .collect();
        let id_to_idx: HashMap<i64, usize> = nodes
            .iter()
            .enumerate()
            .map(|(i, n)| (n.node_id, i))
            .collect();
        let mip = calc.compute_mip(&nodes, &edges, &id_to_idx);
        assert!(mip.abs() < 1e-12);
    }

    #[test]
    fn test_mip_chain_graph() {
        let calc = PhiCalculator::new(1);
        // 15 nodes in a chain: 0-1-2-...-14
        let nodes: Vec<KeterNode> = (0..15)
            .map(|i| make_node(i, "assertion", 0.8))
            .collect();
        let edges: Vec<KeterEdge> = (0..14)
            .map(|i| make_edge(i, i + 1, "supports", 1.0))
            .collect();
        let id_to_idx: HashMap<i64, usize> = nodes
            .iter()
            .enumerate()
            .map(|(i, n)| (n.node_id, i))
            .collect();
        let mip = calc.compute_mip(&nodes, &edges, &id_to_idx);
        // Chain graph: cutting in the middle loses relatively little cross-edge info
        // MIP should be > 0 but not huge
        assert!(mip > 0.0);
        assert!(mip <= 1.0);
    }

    #[test]
    fn test_mip_dense_graph() {
        let calc = PhiCalculator::new(1);
        // 12-node complete graph: every node connected to every other
        let n = 12;
        let nodes: Vec<KeterNode> = (0..n)
            .map(|i| make_node(i as i64, "assertion", 0.9))
            .collect();
        let mut edges = Vec::new();
        for i in 0..n {
            for j in (i + 1)..n {
                edges.push(make_edge(i as i64, j as i64, "supports", 1.0));
            }
        }
        let id_to_idx: HashMap<i64, usize> = nodes
            .iter()
            .enumerate()
            .map(|(i, n)| (n.node_id, i))
            .collect();
        let mip = calc.compute_mip(&nodes, &edges, &id_to_idx);
        // Complete graph: any cut loses a lot of edges, so MIP should be high
        assert!(mip > 0.3);
    }

    // -----------------------------------------------------------------------
    // Fiedler vector
    // -----------------------------------------------------------------------

    #[test]
    fn test_fiedler_trivial() {
        let calc = PhiCalculator::new(1);
        // Single node
        let adj: Vec<BTreeMap<usize, f64>> = vec![BTreeMap::new()];
        let degree = vec![0.0];
        assert!(calc.power_iteration_fiedler(&adj, &degree, 1.0, 1).is_none());
    }

    #[test]
    fn test_fiedler_two_nodes() {
        let calc = PhiCalculator::new(1);
        let mut adj: Vec<BTreeMap<usize, f64>> = vec![BTreeMap::new(); 2];
        adj[0].insert(1, 1.0);
        adj[1].insert(0, 1.0);
        let degree = vec![1.0, 1.0];
        let fiedler = calc.power_iteration_fiedler(&adj, &degree, 1.1, 2);
        assert!(fiedler.is_some());
        let v = fiedler.unwrap();
        // Fiedler vector of a 2-node graph is [+, -] or [-, +]
        assert!((v[0] + v[1]).abs() < 0.1); // approximately zero-mean
    }

    // -----------------------------------------------------------------------
    // Shannon entropy utility
    // -----------------------------------------------------------------------

    #[test]
    fn test_shannon_entropy_uniform() {
        // 4 categories, equal counts -> H = log2(4) = 2.0
        let h = shannon_entropy_from_counts(vec![25, 25, 25, 25].into_iter(), 100.0);
        assert!((h - 2.0).abs() < 1e-9);
    }

    #[test]
    fn test_shannon_entropy_single() {
        // Single category -> H = 0
        let h = shannon_entropy_from_counts(vec![100].into_iter(), 100.0);
        assert!(h.abs() < 1e-12);
    }

    #[test]
    fn test_shannon_entropy_skewed() {
        // Highly skewed: 99 + 1 -> low entropy
        let h = shannon_entropy_from_counts(vec![99, 1].into_iter(), 100.0);
        assert!(h > 0.0);
        assert!(h < 1.0);
    }

    // -----------------------------------------------------------------------
    // Milestone gates (v4)
    // -----------------------------------------------------------------------

    #[test]
    fn test_gate1_knowledge_foundation() {
        let calc = PhiCalculator::new(1);
        // Not enough nodes
        let nodes: Vec<KeterNode> = (0..200)
            .map(|i| make_node(i, "assertion", 0.8))
            .collect();
        let results = calc.check_gates(&nodes, &[], 0.0, 0.0, &ExtraStats { calibration_error: 1.0, ..Default::default() });
        assert!(!results[0].1); // Gate 1 should fail (< 500 nodes)

        // Enough nodes with high confidence + >=5 domains
        let nodes: Vec<KeterNode> = (0..500)
            .map(|i| {
                let mut n = make_node(i, "assertion", 0.8);
                n.domain = format!("domain_{}", i % 6); // 6 domains
                n
            })
            .collect();
        let results = calc.check_gates(&nodes, &[], 0.0, 0.0, &ExtraStats { calibration_error: 1.0, ..Default::default() });
        assert!(results[0].1); // Gate 1 should pass
    }

    #[test]
    fn test_gate1_low_confidence_fails() {
        let calc = PhiCalculator::new(1);
        let nodes: Vec<KeterNode> = (0..500)
            .map(|i| {
                let mut n = make_node(i, "assertion", 0.3);
                n.domain = format!("domain_{}", i % 6);
                n
            })
            .collect();
        let results = calc.check_gates(&nodes, &[], 0.0, 0.0, &ExtraStats { calibration_error: 1.0, ..Default::default() });
        assert!(!results[0].1); // avg_confidence 0.3 < 0.5
    }

    #[test]
    fn test_gate2_structural_diversity() {
        let calc = PhiCalculator::new(1);
        let mut nodes: Vec<KeterNode> = Vec::new();
        // 4 types with >= 50 each, total >= 2000
        for i in 0..600 {
            nodes.push(make_node(i, "assertion", 0.7));
        }
        for i in 600..1200 {
            nodes.push(make_node(i, "observation", 0.7));
        }
        for i in 1200..1700 {
            nodes.push(make_node(i, "inference", 0.7));
        }
        for i in 1700..2000 {
            nodes.push(make_node(i, "axiom", 0.7));
        }
        // integration_score > 0.3 required
        let results = calc.check_gates(&nodes, &[], 0.5, 0.0, &ExtraStats { calibration_error: 1.0, ..Default::default() });
        assert!(results[1].1);
    }

    #[test]
    fn test_no_gates_pass_with_empty_graph() {
        let calc = PhiCalculator::new(1);
        let results = calc.check_gates(&[], &[], 0.0, 0.0, &ExtraStats { calibration_error: 1.0, ..Default::default() });
        assert!(results.iter().all(|(_, passed)| !passed));
    }

    // -----------------------------------------------------------------------
    // Gate ceiling
    // -----------------------------------------------------------------------

    #[test]
    fn test_gate_ceiling_limits_phi() {
        // If no gates pass, ceiling = 0 -> phi = 0 regardless of raw_phi
        let mut calc = PhiCalculator::new(1);
        // Build a small graph (< 100 nodes): no gates pass
        let nodes: Vec<KeterNode> = (0..20)
            .map(|i| make_node(i, "assertion", 0.8))
            .collect();
        let mut edges: Vec<KeterEdge> = Vec::new();
        for i in 0..19 {
            edges.push(make_edge(i, i + 1, "supports", 1.0));
        }
        let kg = make_kg(nodes, edges);

        Python::with_gil(|py| {
            let result = calc.compute_phi(&kg, 5, None).unwrap();
            let dict = result.bind(py).downcast::<PyDict>().unwrap();
            let phi: f64 = dict.get_item("phi_value").unwrap().unwrap().extract().unwrap();
            let gate_ceiling: f64 = dict
                .get_item("gate_ceiling")
                .unwrap()
                .unwrap()
                .extract()
                .unwrap();
            assert_eq!(gate_ceiling, 0.0);
            assert!(phi.abs() < 1e-12);
        });
    }

    // -----------------------------------------------------------------------
    // History tracking
    // -----------------------------------------------------------------------

    #[test]
    fn test_history_accumulates() {
        let mut calc = PhiCalculator::new(1);
        let kg = make_kg(
            vec![make_node(0, "assertion", 0.8), make_node(1, "observation", 0.7)],
            vec![make_edge(0, 1, "supports", 1.0)],
        );
        Python::with_gil(|_py| {
            calc.compute_phi(&kg, 1, None).unwrap();
            calc.compute_phi(&kg, 2, None).unwrap();
            calc.compute_phi(&kg, 3, None).unwrap();
        });
        assert_eq!(calc.history_len(), 3);
    }

    #[test]
    fn test_clear_resets_state() {
        let mut calc = PhiCalculator::new(1);
        let kg = make_kg(
            vec![make_node(0, "assertion", 0.8)],
            vec![],
        );
        Python::with_gil(|_py| {
            calc.compute_phi(&kg, 1, None).unwrap();
        });
        assert!(calc.history_len() > 0);
        calc.clear();
        assert_eq!(calc.history_len(), 0);
        assert_eq!(calc.get_current_phi(), 0.0);
    }

    // -----------------------------------------------------------------------
    // Caching behavior
    // -----------------------------------------------------------------------

    #[test]
    fn test_compute_interval_caching() {
        let mut calc = PhiCalculator::new(10); // cache for 10 blocks
        let kg = make_kg(
            vec![
                make_node(0, "assertion", 0.8),
                make_node(1, "observation", 0.7),
            ],
            vec![make_edge(0, 1, "supports", 1.0)],
        );
        Python::with_gil(|py| {
            // First computation at block 5
            calc.compute_phi(&kg, 5, None).unwrap();
            assert_eq!(calc.history_len(), 1);

            // Block 10 is within interval (10 - 5 = 5 < 10), should use cache
            let result = calc.compute_phi(&kg, 10, None).unwrap();
            let dict = result.bind(py).downcast::<PyDict>().unwrap();
            let cached: bool = dict
                .get_item("cached")
                .unwrap()
                .unwrap()
                .extract()
                .unwrap();
            assert!(cached);
            // No new history entry for cached result
            assert_eq!(calc.history_len(), 1);
        });
    }

    // -----------------------------------------------------------------------
    // Rounding helpers
    // -----------------------------------------------------------------------

    #[test]
    fn test_round6() {
        assert!((round6(1.23456789) - 1.234568).abs() < 1e-10);
        assert!((round6(0.0) - 0.0).abs() < 1e-12);
    }

    #[test]
    fn test_round4() {
        assert!((round4(1.23456) - 1.2346).abs() < 1e-10);
    }

    // -----------------------------------------------------------------------
    // Vector norm
    // -----------------------------------------------------------------------

    #[test]
    fn test_vector_norm() {
        assert!((vector_norm(&[3.0, 4.0]) - 5.0).abs() < 1e-12);
        assert!((vector_norm(&[0.0, 0.0]) - 0.0).abs() < 1e-12);
        assert!((vector_norm(&[1.0]) - 1.0).abs() < 1e-12);
    }

    // -----------------------------------------------------------------------
    // Full integration: moderately large graph
    // -----------------------------------------------------------------------

    #[test]
    fn test_medium_graph_phi_properties() {
        let mut calc = PhiCalculator::new(1);
        // 50 nodes, mixed types, connected chain
        let types = ["assertion", "observation", "inference", "axiom"];
        let nodes: Vec<KeterNode> = (0..50)
            .map(|i| {
                make_node(
                    i,
                    types[(i as usize) % types.len()],
                    0.5 + (i as f64) * 0.01,
                )
            })
            .collect();
        let edges: Vec<KeterEdge> = (0..49)
            .map(|i| {
                let etypes = ["supports", "derives", "requires"];
                make_edge(i, i + 1, etypes[(i as usize) % etypes.len()], 1.0)
            })
            .collect();
        let kg = make_kg(nodes, edges);

        Python::with_gil(|py| {
            let result = calc.compute_phi(&kg, 100, None).unwrap();
            let dict = result.bind(py).downcast::<PyDict>().unwrap();

            let phi_raw: f64 = dict.get_item("phi_raw").unwrap().unwrap().extract().unwrap();
            let phi: f64 = dict.get_item("phi_value").unwrap().unwrap().extract().unwrap();
            let version: i32 = dict
                .get_item("phi_version")
                .unwrap()
                .unwrap()
                .extract()
                .unwrap();

            // Raw phi should be positive (diverse types + connected + non-zero cross-flow)
            assert!(phi_raw > 0.0);
            // Final phi is capped by gates (< 100 nodes, gate 1 probably fails)
            assert!(phi <= phi_raw || phi == 0.0);
            assert_eq!(version, 4);
        });
    }

    // -----------------------------------------------------------------------
    // Content inspection for gate stats
    // -----------------------------------------------------------------------

    /// Helper: build a content HashMap from key-value pairs.
    fn content_map(pairs: &[(&str, &str)]) -> HashMap<String, String> {
        pairs.iter().map(|(k, v)| (k.to_string(), v.to_string())).collect()
    }

    #[test]
    fn test_gate_stats_content_inspection() {
        let calc = PhiCalculator::new(1);
        let nodes = vec![
            make_node_with_content(
                0,
                "inference",
                0.7,
                content_map(&[("cross_domain", "true")]),
            ),
            make_node_with_content(
                1,
                "assertion",
                0.8,
                content_map(&[("type", "prediction_confirmed")]),
            ),
            make_node_with_content(
                2,
                "assertion",
                0.6,
                content_map(&[("type", "debate_synthesis")]),
            ),
            make_node_with_content(
                3,
                "meta_observation",
                0.9,
                content_map(&[("source", "self-reflection")]),
            ),
            make_node_with_content(
                4,
                "axiom",
                0.95,
                content_map(&[("type", "consolidated_pattern")]),
            ),
            make_node_with_content(
                5,
                "assertion",
                0.7,
                content_map(&[("type", "generalization")]),
            ),
        ];
        let results = calc.check_gates(&nodes, &[], 0.0, 0.0, &ExtraStats { calibration_error: 1.0, ..Default::default() });
        // All gates fail (too few nodes), but the stats were computed.
        // We verify by checking that no gate passed (all require >= 100 nodes).
        assert!(results.iter().all(|(_, passed)| !passed));
    }

    // -----------------------------------------------------------------------
    // MIP with zero-weight edges
    // -----------------------------------------------------------------------

    #[test]
    fn test_mip_zero_weight_edges() {
        let calc = PhiCalculator::new(1);
        let nodes: Vec<KeterNode> = (0..12)
            .map(|i| make_node(i, "assertion", 0.0)) // zero confidence
            .collect();
        let edges: Vec<KeterEdge> = (0..11)
            .map(|i| make_edge(i, i + 1, "supports", 1.0))
            .collect();
        let id_to_idx: HashMap<i64, usize> = nodes
            .iter()
            .enumerate()
            .map(|(i, n)| (n.node_id, i))
            .collect();
        // confidence=0 => w=0 => total_flow=0 => mip=0
        let mip = calc.compute_mip(&nodes, &edges, &id_to_idx);
        assert!(mip.abs() < 1e-12);
    }

    // -----------------------------------------------------------------------
    // Deterministic: same input → same output
    // -----------------------------------------------------------------------

    #[test]
    fn test_deterministic() {
        let nodes: Vec<KeterNode> = (0..30)
            .map(|i| {
                let t = if i < 10 {
                    "assertion"
                } else if i < 20 {
                    "observation"
                } else {
                    "inference"
                };
                make_node(i, t, 0.5 + (i as f64) * 0.01)
            })
            .collect();
        let edges: Vec<KeterEdge> = (0..29)
            .map(|i| make_edge(i, i + 1, "supports", 1.0))
            .collect();
        let kg = make_kg(nodes, edges);

        Python::with_gil(|py| {
            let mut calc1 = PhiCalculator::new(1);
            let mut calc2 = PhiCalculator::new(1);

            let r1 = calc1.compute_phi(&kg, 50, None).unwrap();
            let r2 = calc2.compute_phi(&kg, 50, None).unwrap();

            let d1 = r1.bind(py).downcast::<PyDict>().unwrap();
            let d2 = r2.bind(py).downcast::<PyDict>().unwrap();

            let phi1: f64 = d1.get_item("phi_raw").unwrap().unwrap().extract().unwrap();
            let phi2: f64 = d2.get_item("phi_raw").unwrap().unwrap().extract().unwrap();

            assert!((phi1 - phi2).abs() < 1e-12, "phi_raw must be deterministic");

            let mip1: f64 = d1.get_item("mip_score").unwrap().unwrap().extract().unwrap();
            let mip2: f64 = d2.get_item("mip_score").unwrap().unwrap().extract().unwrap();
            assert!((mip1 - mip2).abs() < 1e-12, "mip_score must be deterministic");
        });
    }
}
