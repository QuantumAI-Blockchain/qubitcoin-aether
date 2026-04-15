//! IIT-inspired phi computation from ACTUAL system state transitions.
//!
//! Instead of constructing a synthetic TPM from edge weights, this module
//! records actual state transitions of the cognitive system and computes
//! phi from the observed transition probability matrix.
//!
//! The key insight: genuine integrated information requires measuring how
//! much information is lost when you partition a system. This must be done
//! on the system's *actual dynamics* (observed state transitions), not on
//! a graph-theoretic proxy derived from edge weights.
//!
//! Architecture:
//!   1. `SystemState` — compact bit-vector representation of cognitive element states
//!   2. `TransitionRecorder` — ring buffer of observed (before, after) state pairs
//!   3. `EmpiricalTPM` — transition probability matrix built from observations
//!   4. `PhiFromDynamics` — MIP-based phi computation on the empirical TPM
//!   5. `cognitive_state_to_binary` — maps Aether cognitive state to binary vector

use std::collections::{HashMap, VecDeque};

use serde::{Deserialize, Serialize};

// ---------------------------------------------------------------------------
// SystemState — compact bit-vector for cognitive element states
// ---------------------------------------------------------------------------

/// A binary state vector for a set of cognitive elements.
/// Each element is either active (1) or inactive (0).
///
/// Stored as a packed bit vector using u64 words for memory efficiency
/// and fast Hamming distance via XOR + popcount.
#[derive(Clone, Debug, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub struct SystemState {
    /// Packed bit storage: element i is active if bits[i/64] & (1 << (i%64)) != 0
    bits: Vec<u64>,
    /// Number of cognitive elements this state represents.
    n_elements: usize,
}

impl SystemState {
    /// Create a new zero state (all elements inactive) for n elements.
    pub fn new(n_elements: usize) -> Self {
        let n_words = (n_elements + 63) / 64;
        Self {
            bits: vec![0u64; n_words],
            n_elements,
        }
    }

    /// Create a SystemState from a slice of booleans.
    pub fn from_bools(states: &[bool]) -> Self {
        let n_elements = states.len();
        let n_words = (n_elements + 63) / 64;
        let mut bits = vec![0u64; n_words];
        for (i, &active) in states.iter().enumerate() {
            if active {
                bits[i / 64] |= 1u64 << (i % 64);
            }
        }
        Self { bits, n_elements }
    }

    /// Check whether element at index `idx` is active.
    ///
    /// # Panics
    /// Panics if `idx >= n_elements`.
    pub fn get(&self, idx: usize) -> bool {
        assert!(idx < self.n_elements, "index {idx} out of bounds for {}", self.n_elements);
        (self.bits[idx / 64] >> (idx % 64)) & 1 == 1
    }

    /// Set element at index `idx` to active or inactive.
    ///
    /// # Panics
    /// Panics if `idx >= n_elements`.
    pub fn set(&mut self, idx: usize, active: bool) {
        assert!(idx < self.n_elements, "index {idx} out of bounds for {}", self.n_elements);
        if active {
            self.bits[idx / 64] |= 1u64 << (idx % 64);
        } else {
            self.bits[idx / 64] &= !(1u64 << (idx % 64));
        }
    }

    /// Number of cognitive elements this state represents.
    pub fn n_elements(&self) -> usize {
        self.n_elements
    }

    /// Hamming distance: number of differing bits between two states.
    /// Both states must have the same n_elements.
    pub fn hamming_distance(&self, other: &Self) -> usize {
        assert_eq!(
            self.n_elements, other.n_elements,
            "cannot compare states with different element counts"
        );
        self.bits
            .iter()
            .zip(other.bits.iter())
            .map(|(a, b)| (a ^ b).count_ones() as usize)
            .sum()
    }

    /// Convert the state to a usize index (for states with n_elements <= 64).
    /// Used for TPM indexing on small systems.
    fn to_index(&self) -> usize {
        assert!(
            self.n_elements <= 64,
            "to_index only valid for n_elements <= 64"
        );
        self.bits[0] as usize
    }

    /// Number of active elements.
    pub fn count_active(&self) -> usize {
        self.bits.iter().map(|w| w.count_ones() as usize).sum()
    }

    /// Extract a sub-state containing only the specified element indices.
    pub fn subset(&self, indices: &[usize]) -> SystemState {
        let mut sub = SystemState::new(indices.len());
        for (new_idx, &orig_idx) in indices.iter().enumerate() {
            sub.set(new_idx, self.get(orig_idx));
        }
        sub
    }
}

// ---------------------------------------------------------------------------
// TransitionRecorder — ring buffer of observed state transitions
// ---------------------------------------------------------------------------

/// Records actual state transitions and builds an empirical TPM.
///
/// Each transition is a (before, after) pair representing the system's state
/// at consecutive time steps. From these observations we estimate the
/// transition probability matrix P(state_t+1 | state_t).
pub struct TransitionRecorder {
    /// Ring buffer of observed state transitions: (before, after).
    transitions: VecDeque<(SystemState, SystemState)>,
    /// Maximum number of transitions to retain.
    max_history: usize,
    /// Number of cognitive elements in each state.
    n_elements: usize,
}

impl TransitionRecorder {
    /// Create a new recorder for a system with `n_elements` cognitive elements.
    /// Retains at most `max_history` transitions in a ring buffer.
    pub fn new(n_elements: usize, max_history: usize) -> Self {
        Self {
            transitions: VecDeque::with_capacity(max_history.min(4096)),
            max_history,
            n_elements,
        }
    }

    /// Record an observed state transition.
    ///
    /// # Panics
    /// Panics if before/after have different element counts or don't match the recorder.
    pub fn record(&mut self, before: SystemState, after: SystemState) {
        assert_eq!(before.n_elements(), self.n_elements);
        assert_eq!(after.n_elements(), self.n_elements);
        if self.transitions.len() >= self.max_history {
            self.transitions.pop_front();
        }
        self.transitions.push_back((before, after));
    }

    /// Build an empirical TPM from observed transitions.
    ///
    /// For small systems (n_elements <= 16): builds a full element-wise conditional
    /// probability table: P(element_j = 1 at t+1 | system state at t).
    ///
    /// For large systems (n_elements > 16): uses Markov blanket approximation,
    /// conditioning each element only on its local neighborhood.
    ///
    /// Returns `None` if insufficient observations. For the full TPM we need
    /// enough transitions to get reasonable coverage. The threshold is
    /// `4 * n_elements` transitions minimum.
    pub fn build_tpm(&self) -> Option<EmpiricalTPM> {
        let min_transitions = 4 * self.n_elements;
        if self.transitions.len() < min_transitions {
            return None;
        }

        if self.n_elements <= 16 {
            self.build_full_tpm()
        } else {
            self.build_local_tpm()
        }
    }

    /// Number of recorded transitions.
    pub fn transition_count(&self) -> usize {
        self.transitions.len()
    }

    /// Number of elements in the system.
    pub fn n_elements(&self) -> usize {
        self.n_elements
    }

    /// Build full element-wise conditional TPM for small systems.
    /// tpm[j][s] = P(element j active at t+1 | system in state s)
    fn build_full_tpm(&self) -> Option<EmpiricalTPM> {
        let n = self.n_elements;
        let n_states = 1usize << n;

        // Count transitions from each source state, and element activations
        // tpm_counts[j][s] = count of times element j was active in the next state
        //                    when current state was s
        // state_counts[s] = total transitions observed from state s
        let mut tpm_counts: Vec<Vec<u64>> = vec![vec![0u64; n_states]; n];
        let mut state_counts: Vec<u64> = vec![0u64; n_states];

        for (before, after) in &self.transitions {
            let s = before.to_index();
            state_counts[s] += 1;
            for j in 0..n {
                if after.get(j) {
                    tpm_counts[j][s] += 1;
                }
            }
        }

        // Convert counts to probabilities
        let mut tpm: Vec<Vec<f64>> = vec![vec![0.5; n_states]; n];
        for j in 0..n {
            for s in 0..n_states {
                if state_counts[s] > 0 {
                    tpm[j][s] = tpm_counts[j][s] as f64 / state_counts[s] as f64;
                }
                // If no observations for this state, use 0.5 (maximum entropy prior)
            }
        }

        Some(EmpiricalTPM {
            n_elements: n,
            full_tpm: Some(tpm),
            local_tpm: None,
        })
    }

    /// Build local (Markov blanket) TPM for large systems.
    /// For each element j, we identify its neighbors (elements that frequently
    /// co-change with it) and condition only on those neighbors' states.
    fn build_local_tpm(&self) -> Option<EmpiricalTPM> {
        let n = self.n_elements;
        // Neighborhood size: condition on at most 8 nearest neighbors
        let max_neighbors = 8usize.min(n - 1);

        // Step 1: Compute co-change frequency between all pairs of elements.
        // co_change[i][j] = fraction of transitions where both i and j changed.
        let total = self.transitions.len() as f64;
        let mut co_change: Vec<Vec<f64>> = vec![vec![0.0; n]; n];

        for (before, after) in &self.transitions {
            let changed: Vec<usize> = (0..n)
                .filter(|&i| before.get(i) != after.get(i))
                .collect();
            for &i in &changed {
                for &j in &changed {
                    if i != j {
                        co_change[i][j] += 1.0;
                    }
                }
            }
        }
        for i in 0..n {
            for j in 0..n {
                co_change[i][j] /= total;
            }
        }

        // Step 2: For each element, find its top-K neighbors by co-change.
        let mut local_tpm: Vec<LocalElementTPM> = Vec::with_capacity(n);

        for j in 0..n {
            let mut neighbors: Vec<(usize, f64)> = (0..n)
                .filter(|&i| i != j)
                .map(|i| (i, co_change[j][i]))
                .collect();
            neighbors.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap_or(std::cmp::Ordering::Equal));
            let neighbor_indices: Vec<usize> =
                neighbors.iter().take(max_neighbors).map(|&(i, _)| i).collect();

            // Condition on neighbor states
            let n_neighbor_states = 1usize << neighbor_indices.len();
            let mut counts: Vec<(u64, u64)> = vec![(0, 0); n_neighbor_states]; // (active_count, total_count)

            for (before, after) in &self.transitions {
                let neighbor_state = neighbor_state_index(before, &neighbor_indices);
                counts[neighbor_state].1 += 1;
                if after.get(j) {
                    counts[neighbor_state].0 += 1;
                }
            }

            let mut probs: HashMap<usize, f64> = HashMap::new();
            for (ns, &(active, total)) in counts.iter().enumerate() {
                if total > 0 {
                    probs.insert(ns, active as f64 / total as f64);
                }
            }

            local_tpm.push(LocalElementTPM {
                neighbor_indices,
                probs,
            });
        }

        Some(EmpiricalTPM {
            n_elements: n,
            full_tpm: None,
            local_tpm: Some(local_tpm),
        })
    }
}

/// Compute an index from the neighbor elements' states in a given SystemState.
fn neighbor_state_index(state: &SystemState, neighbors: &[usize]) -> usize {
    let mut idx = 0usize;
    for (bit, &elem) in neighbors.iter().enumerate() {
        if state.get(elem) {
            idx |= 1 << bit;
        }
    }
    idx
}

// ---------------------------------------------------------------------------
// EmpiricalTPM — transition probability matrix from observations
// ---------------------------------------------------------------------------

/// Per-element local TPM: P(element_j = 1 | neighbor states).
#[derive(Clone, Debug)]
struct LocalElementTPM {
    /// Indices of the neighbor elements this element is conditioned on.
    neighbor_indices: Vec<usize>,
    /// neighbor_state_index -> P(element active at t+1).
    probs: HashMap<usize, f64>,
}

/// Empirical Transition Probability Matrix built from observed state transitions.
///
/// For n elements, the full TPM is conceptually 2^n x 2^n. We store it in
/// element-wise conditional form: tpm[j][s] = P(element j = 1 at t+1 | state s at t).
///
/// Two representations:
/// - `full_tpm`: for small systems (n <= 16), exact conditional probabilities
/// - `local_tpm`: for large systems, Markov blanket approximation
#[derive(Clone, Debug)]
pub struct EmpiricalTPM {
    /// Number of cognitive elements.
    n_elements: usize,
    /// Full element-wise conditional TPM: tpm[j][s] = P(element j active | state s).
    /// Present when n_elements <= 16.
    full_tpm: Option<Vec<Vec<f64>>>,
    /// Local (Markov blanket) TPM for large systems.
    local_tpm: Option<Vec<LocalElementTPM>>,
}

impl EmpiricalTPM {
    /// Number of elements in the system.
    pub fn n_elements(&self) -> usize {
        self.n_elements
    }

    /// Get P(element j = 1 at t+1 | system in state `state` at t).
    pub fn transition_prob(&self, j: usize, state: &SystemState) -> f64 {
        assert!(j < self.n_elements);
        if let Some(ref full) = self.full_tpm {
            let s = state.to_index();
            full[j][s]
        } else if let Some(ref local) = self.local_tpm {
            let elem_tpm = &local[j];
            let ns = neighbor_state_index(state, &elem_tpm.neighbor_indices);
            *elem_tpm.probs.get(&ns).unwrap_or(&0.5)
        } else {
            0.5 // maximum entropy fallback
        }
    }

    /// Compute the effect repertoire: P(future state of `elements` | current `state`).
    /// Assumes conditional independence across elements given the current state
    /// (which is exact for the element-wise TPM representation).
    ///
    /// Returns a probability distribution over 2^|elements| states.
    pub fn effect_repertoire(&self, state: &SystemState, elements: &[usize]) -> Vec<f64> {
        let k = elements.len();
        let n_sub_states = 1usize << k;
        let mut dist = vec![0.0f64; n_sub_states];

        // P(future_sub_state | current_state) = product of element-wise probs
        for sub_s in 0..n_sub_states {
            let mut prob = 1.0;
            for (bit, &elem) in elements.iter().enumerate() {
                let p_active = self.transition_prob(elem, state);
                if (sub_s >> bit) & 1 == 1 {
                    prob *= p_active;
                } else {
                    prob *= 1.0 - p_active;
                }
            }
            dist[sub_s] = prob;
        }
        dist
    }

    /// Compute the cause repertoire: P(past state of `elements` | current `state`).
    /// Uses Bayes' theorem: P(past | current) proportional to P(current | past) * P(past).
    /// Assumes uniform prior over past states (maximum entropy assumption).
    ///
    /// Returns a probability distribution over 2^|elements| states.
    pub fn cause_repertoire(&self, state: &SystemState, elements: &[usize]) -> Vec<f64> {
        let k = elements.len();
        if k > 20 {
            // Too large for exhaustive enumeration; return uniform
            let n_sub = 1usize << k;
            return vec![1.0 / n_sub as f64; n_sub];
        }
        let n_sub_states = 1usize << k;
        let mut unnormalized = vec![0.0f64; n_sub_states];

        // For each possible past sub-state, compute P(current elements | past sub-state)
        // We need a hypothetical state where the `elements` are in a specific configuration
        // and other elements are marginalized out (set to their most likely values).
        for past_s in 0..n_sub_states {
            // Build a hypothetical past state with elements set to past_s
            let mut hyp_past = state.clone();
            for (bit, &elem) in elements.iter().enumerate() {
                hyp_past.set(elem, (past_s >> bit) & 1 == 1);
            }

            // P(current elements state | past hyp) = product over elements
            let mut likelihood = 1.0;
            for &elem in elements {
                let p_active = self.transition_prob(elem, &hyp_past);
                if state.get(elem) {
                    likelihood *= p_active;
                } else {
                    likelihood *= 1.0 - p_active;
                }
            }
            unnormalized[past_s] = likelihood; // uniform prior = 1/n_sub_states cancels in normalization
        }

        // Normalize
        let sum: f64 = unnormalized.iter().sum();
        if sum > 1e-15 {
            unnormalized.iter_mut().for_each(|p| *p /= sum);
        } else {
            let uniform = 1.0 / n_sub_states as f64;
            unnormalized.iter_mut().for_each(|p| *p = uniform);
        }
        unnormalized
    }
}

// ---------------------------------------------------------------------------
// PhiFromDynamics — MIP-based phi computation
// ---------------------------------------------------------------------------

/// Computes phi from an empirical TPM using partition-based information loss.
///
/// The algorithm (simplified IIT 3.0):
/// 1. For a given system state, compute cause and effect repertoires for the whole system.
/// 2. For each bipartition (A, B) of elements:
///    a. Compute cause/effect repertoires of partitioned system (treating A and B independently).
///    b. Measure information loss (EMD/L1 distance between whole and partitioned repertoires).
///    c. Partition information = min(cause_loss, effect_loss).
/// 3. Phi = minimum partition information across all bipartitions (the MIP).
///
/// For n > 12 elements, uses greedy spectral bisection instead of exhaustive search
/// over all 2^(n-1) - 1 bipartitions.
pub struct PhiFromDynamics {
    tpm: EmpiricalTPM,
}

impl PhiFromDynamics {
    /// Create a new phi computer from an empirical TPM.
    pub fn new(tpm: EmpiricalTPM) -> Self {
        Self { tpm }
    }

    /// Compute phi for the full system in a given state.
    ///
    /// This is the core IIT measure: the minimum information lost when
    /// the system is partitioned into independent parts.
    pub fn compute_phi(&self, current_state: &SystemState) -> f64 {
        let n = self.tpm.n_elements();
        if n < 2 {
            return 0.0;
        }

        let elements: Vec<usize> = (0..n).collect();
        let (_, _, phi) = if n <= 12 {
            self.exhaustive_mip(&elements, current_state)
        } else {
            self.greedy_mip(&elements, current_state)
        };
        phi
    }

    /// Compute phi averaged over multiple observed states.
    /// This gives a more robust estimate than a single-state phi.
    pub fn compute_phi_average(&self, states: &[SystemState]) -> f64 {
        if states.is_empty() {
            return 0.0;
        }
        let sum: f64 = states.iter().map(|s| self.compute_phi(s)).sum();
        sum / states.len() as f64
    }

    /// Find the MIP via exhaustive bipartition search (n <= 12).
    /// Returns (partition_a, partition_b, phi).
    fn exhaustive_mip(
        &self,
        elements: &[usize],
        current_state: &SystemState,
    ) -> (Vec<usize>, Vec<usize>, f64) {
        let n = elements.len();
        if n < 2 {
            return (elements.to_vec(), vec![], 0.0);
        }

        let mut best_phi = f64::MAX;
        let mut best_a = vec![];
        let mut best_b = vec![];

        // Enumerate all bipartitions: element 0 always in partition A (symmetry breaking).
        // For each subset S of {1..n-1}, partition A = {0} union S, B = rest.
        let n_subsets = 1usize << (n - 1);
        for mask in 0..n_subsets {
            let mut part_a = vec![elements[0]];
            let mut part_b = vec![];
            for bit in 0..(n - 1) {
                if (mask >> bit) & 1 == 1 {
                    part_a.push(elements[bit + 1]);
                } else {
                    part_b.push(elements[bit + 1]);
                }
            }
            if part_b.is_empty() {
                continue; // Skip trivial partition
            }

            let loss = self.partition_information_loss(&part_a, &part_b, current_state);
            if loss < best_phi {
                best_phi = loss;
                best_a = part_a;
                best_b = part_b;
            }
        }

        (best_a, best_b, best_phi)
    }

    /// Find the MIP via greedy spectral bisection for large systems (n > 12).
    /// Uses the Fiedler vector of the element interaction matrix to find a good cut.
    fn greedy_mip(
        &self,
        elements: &[usize],
        current_state: &SystemState,
    ) -> (Vec<usize>, Vec<usize>, f64) {
        let n = elements.len();
        if n < 2 {
            return (elements.to_vec(), vec![], 0.0);
        }

        // Build an interaction matrix: how much does element i's transition prob
        // depend on element j's state?
        let mut interaction = vec![vec![0.0f64; n]; n];

        for i in 0..n {
            for j in 0..n {
                if i == j {
                    continue;
                }
                // Measure how much flipping element j changes P(element i = 1)
                let mut state_0 = current_state.clone();
                state_0.set(elements[j], false);
                let p0 = self.tpm.transition_prob(elements[i], &state_0);

                let mut state_1 = current_state.clone();
                state_1.set(elements[j], true);
                let p1 = self.tpm.transition_prob(elements[i], &state_1);

                interaction[i][j] = (p1 - p0).abs();
            }
        }

        // Build Laplacian
        let mut laplacian = vec![vec![0.0f64; n]; n];
        for i in 0..n {
            let degree: f64 = interaction[i].iter().sum();
            laplacian[i][i] = degree;
            for j in 0..n {
                if i != j {
                    laplacian[i][j] = -interaction[i][j];
                }
            }
        }

        // Approximate Fiedler vector via power iteration on (D_max * I - L)
        let d_max = laplacian
            .iter()
            .map(|row| row.iter().cloned().fold(0.0f64, f64::max))
            .fold(0.0f64, f64::max)
            + 1.0;

        // Shifted matrix M = d_max * I - L  (so largest eigvec of M = smallest non-trivial of L)
        let mut vec_v: Vec<f64> = (0..n).map(|i| (i as f64 + 1.0).sin()).collect();
        let norm: f64 = vec_v.iter().map(|x| x * x).sum::<f64>().sqrt();
        vec_v.iter_mut().for_each(|x| *x /= norm);

        // Remove projection onto constant vector (Fiedler is orthogonal to it)
        let ones_norm = (n as f64).sqrt();
        for _ in 0..100 {
            // M * v
            let mut new_v = vec![0.0f64; n];
            for i in 0..n {
                for j in 0..n {
                    let m_ij = if i == j {
                        d_max - laplacian[i][j]
                    } else {
                        -laplacian[i][j]
                    };
                    new_v[i] += m_ij * vec_v[j];
                }
            }
            // Subtract projection onto constant vector
            let proj: f64 = new_v.iter().sum::<f64>() / n as f64;
            new_v.iter_mut().for_each(|x| *x -= proj);
            // Normalize
            let n2: f64 = new_v.iter().map(|x| x * x).sum::<f64>().sqrt();
            if n2 < 1e-15 {
                break;
            }
            new_v.iter_mut().for_each(|x| *x /= n2);
            vec_v = new_v;
        }

        // Partition by sign of Fiedler vector
        let mut part_a = vec![];
        let mut part_b = vec![];
        for (i, &v) in vec_v.iter().enumerate() {
            if v >= 0.0 {
                part_a.push(elements[i]);
            } else {
                part_b.push(elements[i]);
            }
        }

        // Ensure non-trivial partition
        if part_a.is_empty() {
            part_a.push(part_b.pop().unwrap());
        } else if part_b.is_empty() {
            part_b.push(part_a.pop().unwrap());
        }

        let phi = self.partition_information_loss(&part_a, &part_b, current_state);
        (part_a, part_b, phi)
    }

    /// Compute information loss when partitioning the system into (A, B).
    ///
    /// Loss = min(cause_loss, effect_loss) where each loss is the L1 distance
    /// between whole-system and partitioned repertoires.
    fn partition_information_loss(
        &self,
        part_a: &[usize],
        part_b: &[usize],
        current_state: &SystemState,
    ) -> f64 {
        let all_elements: Vec<usize> = part_a.iter().chain(part_b.iter()).copied().collect();

        // Limit repertoire computation to manageable sizes
        if all_elements.len() > 20 {
            // For very large partitions, use marginal-based approximation
            return self.marginal_partition_loss(part_a, part_b, current_state);
        }

        // Effect repertoires
        let whole_effect = self.tpm.effect_repertoire(current_state, &all_elements);
        let effect_a = self.tpm.effect_repertoire(current_state, part_a);
        let effect_b = self.tpm.effect_repertoire(current_state, part_b);
        let partitioned_effect = tensor_product(&effect_a, &effect_b, part_a, part_b, &all_elements);
        let effect_loss = l1_distance(&whole_effect, &partitioned_effect);

        // Cause repertoires
        let whole_cause = self.tpm.cause_repertoire(current_state, &all_elements);
        let cause_a = self.tpm.cause_repertoire(current_state, part_a);
        let cause_b = self.tpm.cause_repertoire(current_state, part_b);
        let partitioned_cause = tensor_product(&cause_a, &cause_b, part_a, part_b, &all_elements);
        let cause_loss = l1_distance(&whole_cause, &partitioned_cause);

        // IIT uses minimum of cause and effect loss
        cause_loss.min(effect_loss)
    }

    /// Marginal-based partition loss for very large systems.
    /// Instead of computing the full 2^n distribution, compares element-wise
    /// marginal probabilities between whole and partitioned system.
    fn marginal_partition_loss(
        &self,
        part_a: &[usize],
        part_b: &[usize],
        current_state: &SystemState,
    ) -> f64 {
        let mut loss = 0.0;

        // For each element in A, measure how much its transition prob changes
        // when we "disconnect" it from B (and vice versa).
        // When partitioned, element in A only depends on A's state.
        for &elem_a in part_a {
            let p_whole = self.tpm.transition_prob(elem_a, current_state);
            // In the partitioned system, element_a only sees part_a's state.
            // We approximate by zeroing out part_b's contribution.
            let mut masked_state = current_state.clone();
            for &elem_b in part_b {
                masked_state.set(elem_b, false);
            }
            let p_partitioned = self.tpm.transition_prob(elem_a, &masked_state);
            loss += (p_whole - p_partitioned).abs();
        }

        for &elem_b in part_b {
            let p_whole = self.tpm.transition_prob(elem_b, current_state);
            let mut masked_state = current_state.clone();
            for &elem_a in part_a {
                masked_state.set(elem_a, false);
            }
            let p_partitioned = self.tpm.transition_prob(elem_b, &masked_state);
            loss += (p_whole - p_partitioned).abs();
        }

        loss
    }
}

// ---------------------------------------------------------------------------
// Utility functions: tensor product, L1 distance
// ---------------------------------------------------------------------------

/// Compute tensor product of two partition distributions, reindexed to match
/// the combined element ordering.
///
/// Given P_A over part_a elements and P_B over part_b elements, produces
/// P_A x P_B over all_elements (the union).
fn tensor_product(
    dist_a: &[f64],
    dist_b: &[f64],
    part_a: &[usize],
    part_b: &[usize],
    all_elements: &[usize],
) -> Vec<f64> {
    let k = all_elements.len();
    let n_states = 1usize << k;
    let mut result = vec![0.0f64; n_states];

    // Build index maps: for each element in all_elements, which bit position
    // does it correspond to in part_a's or part_b's distribution?
    let mut a_bit_map: HashMap<usize, usize> = HashMap::new();
    for (bit, &elem) in part_a.iter().enumerate() {
        a_bit_map.insert(elem, bit);
    }
    let mut b_bit_map: HashMap<usize, usize> = HashMap::new();
    for (bit, &elem) in part_b.iter().enumerate() {
        b_bit_map.insert(elem, bit);
    }

    for s in 0..n_states {
        // Extract the sub-indices for A and B from the combined state index
        let mut a_idx = 0usize;
        let mut b_idx = 0usize;
        for (combined_bit, &elem) in all_elements.iter().enumerate() {
            let bit_val = (s >> combined_bit) & 1;
            if let Some(&a_bit) = a_bit_map.get(&elem) {
                a_idx |= bit_val << a_bit;
            }
            if let Some(&b_bit) = b_bit_map.get(&elem) {
                b_idx |= bit_val << b_bit;
            }
        }
        result[s] = dist_a[a_idx] * dist_b[b_idx];
    }

    result
}

/// L1 distance between two probability distributions (sum of absolute differences).
/// This is a tractable approximation to EMD over binary state spaces.
fn l1_distance(p: &[f64], q: &[f64]) -> f64 {
    assert_eq!(p.len(), q.len());
    p.iter().zip(q.iter()).map(|(a, b)| (a - b).abs()).sum()
}

// ---------------------------------------------------------------------------
// Cognitive state mapping
// ---------------------------------------------------------------------------

/// Default energy threshold for considering a Sephirah active.
const SEPHIRAH_ENERGY_THRESHOLD: f64 = 0.3;

/// Maps the Aether cognitive system's state to a binary vector
/// suitable for IIT analysis.
///
/// Each "element" corresponds to a cognitive component:
/// - Elements 0-9: 10 Sephirot (active if energy > threshold)
/// - Elements 10..(10+n_domains): Per-domain knowledge activity
/// - Next 3: Reasoning modes (deduction, induction, abduction active)
/// - Next 1: Memory consolidation state
/// - Next 1: Debate active
///
/// Total: 15 + n_domains elements. With 10 domains this gives 25 elements,
/// well within the Markov blanket approximation threshold.
pub fn cognitive_state_to_binary(
    sephirot_energies: &[f64; 10],
    domain_activity: &[bool],
    reasoning_active: &[bool; 3],
    memory_consolidating: bool,
    debate_active: bool,
) -> SystemState {
    let n_domains = domain_activity.len();
    let n_elements = 10 + n_domains + 3 + 1 + 1; // sephirot + domains + reasoning + memory + debate

    let mut state = SystemState::new(n_elements);
    let mut idx = 0;

    // Sephirot (elements 0-9)
    for &energy in sephirot_energies {
        state.set(idx, energy > SEPHIRAH_ENERGY_THRESHOLD);
        idx += 1;
    }

    // Domain activity
    for &active in domain_activity {
        state.set(idx, active);
        idx += 1;
    }

    // Reasoning modes (deduction, induction, abduction)
    for &active in reasoning_active {
        state.set(idx, active);
        idx += 1;
    }

    // Memory consolidation
    state.set(idx, memory_consolidating);
    idx += 1;

    // Debate
    state.set(idx, debate_active);

    state
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;

    // -- SystemState tests --

    #[test]
    fn test_system_state_new_is_all_zero() {
        let s = SystemState::new(10);
        assert_eq!(s.n_elements(), 10);
        for i in 0..10 {
            assert!(!s.get(i));
        }
    }

    #[test]
    fn test_system_state_set_get() {
        let mut s = SystemState::new(8);
        s.set(0, true);
        s.set(3, true);
        s.set(7, true);
        assert!(s.get(0));
        assert!(!s.get(1));
        assert!(!s.get(2));
        assert!(s.get(3));
        assert!(s.get(7));

        // Unset
        s.set(3, false);
        assert!(!s.get(3));
    }

    #[test]
    fn test_system_state_from_bools() {
        let s = SystemState::from_bools(&[true, false, true, true, false]);
        assert_eq!(s.n_elements(), 5);
        assert!(s.get(0));
        assert!(!s.get(1));
        assert!(s.get(2));
        assert!(s.get(3));
        assert!(!s.get(4));
    }

    #[test]
    fn test_system_state_large() {
        // Test with > 64 elements (multi-word)
        let mut s = SystemState::new(130);
        s.set(0, true);
        s.set(63, true);
        s.set(64, true);
        s.set(127, true);
        s.set(129, true);
        assert!(s.get(0));
        assert!(s.get(63));
        assert!(s.get(64));
        assert!(!s.get(65));
        assert!(s.get(127));
        assert!(!s.get(128));
        assert!(s.get(129));
    }

    #[test]
    fn test_hamming_distance() {
        let a = SystemState::from_bools(&[true, false, true, false]);
        let b = SystemState::from_bools(&[true, true, false, false]);
        // Differ at positions 1 and 2
        assert_eq!(a.hamming_distance(&b), 2);
    }

    #[test]
    fn test_hamming_distance_same() {
        let a = SystemState::from_bools(&[true, true, false]);
        assert_eq!(a.hamming_distance(&a), 0);
    }

    #[test]
    fn test_count_active() {
        let s = SystemState::from_bools(&[true, false, true, true, false, true]);
        assert_eq!(s.count_active(), 4);
    }

    #[test]
    fn test_subset() {
        let s = SystemState::from_bools(&[true, false, true, true, false]);
        let sub = s.subset(&[0, 2, 4]);
        assert_eq!(sub.n_elements(), 3);
        assert!(sub.get(0));  // was index 0 (true)
        assert!(sub.get(1));  // was index 2 (true)
        assert!(!sub.get(2)); // was index 4 (false)
    }

    // -- TransitionRecorder tests --

    #[test]
    fn test_recorder_insufficient_transitions() {
        let mut recorder = TransitionRecorder::new(4, 1000);
        // Need at least 4*4 = 16 transitions
        for _ in 0..15 {
            recorder.record(
                SystemState::from_bools(&[true, false, true, false]),
                SystemState::from_bools(&[false, true, false, true]),
            );
        }
        assert!(recorder.build_tpm().is_none());
    }

    #[test]
    fn test_recorder_builds_tpm() {
        let mut recorder = TransitionRecorder::new(3, 1000);
        // Record enough transitions
        for _ in 0..50 {
            recorder.record(
                SystemState::from_bools(&[true, false, false]),
                SystemState::from_bools(&[true, true, false]),
            );
            recorder.record(
                SystemState::from_bools(&[false, true, false]),
                SystemState::from_bools(&[false, false, true]),
            );
        }
        let tpm = recorder.build_tpm();
        assert!(tpm.is_some());
        let tpm = tpm.unwrap();
        assert_eq!(tpm.n_elements(), 3);
    }

    #[test]
    fn test_recorder_ring_buffer_eviction() {
        let mut recorder = TransitionRecorder::new(2, 5);
        for i in 0..10 {
            recorder.record(SystemState::new(2), SystemState::new(2));
        }
        assert_eq!(recorder.transition_count(), 5);
    }

    // -- PhiFromDynamics tests --

    /// Helper: build a fully connected 4-element system where every element's
    /// next state depends on all others. This should have HIGH phi.
    fn build_connected_system() -> (EmpiricalTPM, Vec<SystemState>) {
        let n = 4;
        let mut recorder = TransitionRecorder::new(n, 10000);
        let mut states = vec![];

        // Simulate a system where each element's next state is XOR of its neighbors.
        // This creates strong inter-element dependencies = high integrated information.
        let n_states = 1usize << n;
        for s in 0..n_states {
            let before = SystemState::from_bools(
                &(0..n).map(|i| (s >> i) & 1 == 1).collect::<Vec<_>>(),
            );

            // Next state: element i = XOR of all other elements
            let mut after_bits = vec![false; n];
            for i in 0..n {
                let mut xor_val = false;
                for j in 0..n {
                    if j != i && before.get(j) {
                        xor_val = !xor_val;
                    }
                }
                after_bits[i] = xor_val;
            }
            let after = SystemState::from_bools(&after_bits);

            // Record multiple times for statistical confidence
            for _ in 0..20 {
                recorder.record(before.clone(), after.clone());
            }
            states.push(before);
        }

        (recorder.build_tpm().unwrap(), states)
    }

    /// Helper: build a disconnected 4-element system where two halves are independent.
    /// Elements {0,1} evolve independently of {2,3}. This should have LOW phi.
    fn build_disconnected_system() -> (EmpiricalTPM, Vec<SystemState>) {
        let n = 4;
        let mut recorder = TransitionRecorder::new(n, 10000);
        let mut states = vec![];

        let n_states = 1usize << n;
        for s in 0..n_states {
            let before = SystemState::from_bools(
                &(0..n).map(|i| (s >> i) & 1 == 1).collect::<Vec<_>>(),
            );

            // Elements 0,1 only depend on each other; 2,3 only depend on each other
            let mut after_bits = vec![false; n];
            after_bits[0] = before.get(1);  // 0 copies from 1
            after_bits[1] = before.get(0);  // 1 copies from 0
            after_bits[2] = before.get(3);  // 2 copies from 3
            after_bits[3] = before.get(2);  // 3 copies from 2
            let after = SystemState::from_bools(&after_bits);

            for _ in 0..20 {
                recorder.record(before.clone(), after.clone());
            }
            states.push(before);
        }

        (recorder.build_tpm().unwrap(), states)
    }

    #[test]
    fn test_phi_connected_system_is_positive() {
        let (tpm, states) = build_connected_system();
        let phi_calc = PhiFromDynamics::new(tpm);

        // Test with a non-trivial state
        let state = SystemState::from_bools(&[true, false, true, false]);
        let phi = phi_calc.compute_phi(&state);
        assert!(
            phi > 0.0,
            "Connected system should have positive phi, got {phi}"
        );
    }

    #[test]
    fn test_phi_disconnected_lower_than_connected() {
        let (tpm_conn, _) = build_connected_system();
        let (tpm_disc, _) = build_disconnected_system();

        let state = SystemState::from_bools(&[true, false, true, false]);

        let phi_conn = PhiFromDynamics::new(tpm_conn).compute_phi(&state);
        let phi_disc = PhiFromDynamics::new(tpm_disc).compute_phi(&state);

        assert!(
            phi_conn > phi_disc,
            "Connected phi ({phi_conn}) should exceed disconnected phi ({phi_disc})"
        );
    }

    #[test]
    fn test_phi_average_over_states() {
        let (tpm, states) = build_connected_system();
        let phi_calc = PhiFromDynamics::new(tpm);

        let avg = phi_calc.compute_phi_average(&states);
        assert!(
            avg > 0.0,
            "Average phi over states should be positive, got {avg}"
        );
    }

    #[test]
    fn test_phi_single_element_is_zero() {
        // A 1-element system has no partition possible, phi = 0
        let mut recorder = TransitionRecorder::new(1, 100);
        for _ in 0..20 {
            recorder.record(
                SystemState::from_bools(&[true]),
                SystemState::from_bools(&[false]),
            );
            recorder.record(
                SystemState::from_bools(&[false]),
                SystemState::from_bools(&[true]),
            );
        }
        // Not enough transitions for 1 element (need 4*1=4)
        let tpm = recorder.build_tpm().unwrap();
        let phi_calc = PhiFromDynamics::new(tpm);
        let phi = phi_calc.compute_phi(&SystemState::from_bools(&[true]));
        assert_eq!(phi, 0.0, "Single element phi should be 0");
    }

    // -- cognitive_state_to_binary tests --

    #[test]
    fn test_cognitive_state_mapping_basic() {
        let sephirot = [0.5, 0.1, 0.8, 0.2, 0.9, 0.0, 0.4, 0.35, 0.6, 0.7];
        let domains = vec![true, false, true, false, true];
        let reasoning = [true, false, true];
        let memory = true;
        let debate = false;

        let state = cognitive_state_to_binary(&sephirot, &domains, &reasoning, memory, debate);

        // n_elements = 10 + 5 + 3 + 1 + 1 = 20
        assert_eq!(state.n_elements(), 20);

        // Sephirot: active if energy > 0.3
        assert!(state.get(0));   // 0.5 > 0.3
        assert!(!state.get(1));  // 0.1 <= 0.3
        assert!(state.get(2));   // 0.8 > 0.3
        assert!(!state.get(3));  // 0.2 <= 0.3
        assert!(state.get(4));   // 0.9 > 0.3
        assert!(!state.get(5));  // 0.0 <= 0.3
        assert!(state.get(6));   // 0.4 > 0.3
        assert!(state.get(7));   // 0.35 > 0.3
        assert!(state.get(8));   // 0.6 > 0.3
        assert!(state.get(9));   // 0.7 > 0.3

        // Domains (indices 10-14)
        assert!(state.get(10));  // true
        assert!(!state.get(11)); // false
        assert!(state.get(12));  // true
        assert!(!state.get(13)); // false
        assert!(state.get(14));  // true

        // Reasoning (15-17)
        assert!(state.get(15));  // deduction active
        assert!(!state.get(16)); // induction inactive
        assert!(state.get(17));  // abduction active

        // Memory consolidation (18)
        assert!(state.get(18));

        // Debate (19)
        assert!(!state.get(19));
    }

    #[test]
    fn test_cognitive_state_all_inactive() {
        let sephirot = [0.0; 10];
        let domains: Vec<bool> = vec![false; 10];
        let reasoning = [false; 3];
        let state = cognitive_state_to_binary(&sephirot, &domains, &reasoning, false, false);

        assert_eq!(state.n_elements(), 25); // 10 + 10 + 3 + 1 + 1
        assert_eq!(state.count_active(), 0);
    }

    #[test]
    fn test_l1_distance_identical() {
        let p = vec![0.25, 0.25, 0.25, 0.25];
        assert!((l1_distance(&p, &p) - 0.0).abs() < 1e-10);
    }

    #[test]
    fn test_l1_distance_different() {
        let p = vec![1.0, 0.0, 0.0, 0.0];
        let q = vec![0.0, 0.0, 0.0, 1.0];
        assert!((l1_distance(&p, &q) - 2.0).abs() < 1e-10);
    }

    #[test]
    fn test_effect_repertoire_deterministic() {
        // Build a 2-element system where:
        //   State (0,0) -> (1,1) always
        //   State (1,1) -> (0,0) always
        let mut recorder = TransitionRecorder::new(2, 1000);
        for _ in 0..50 {
            recorder.record(
                SystemState::from_bools(&[false, false]),
                SystemState::from_bools(&[true, true]),
            );
            recorder.record(
                SystemState::from_bools(&[true, true]),
                SystemState::from_bools(&[false, false]),
            );
        }
        let tpm = recorder.build_tpm().unwrap();

        // Effect of (0,0): should put all probability on (1,1)
        let state_00 = SystemState::from_bools(&[false, false]);
        let effect = tpm.effect_repertoire(&state_00, &[0, 1]);
        // (1,1) = index 3 in 2-bit encoding
        assert!(effect[3] > 0.99, "P(1,1 | 0,0) should be ~1.0, got {}", effect[3]);
    }
}
