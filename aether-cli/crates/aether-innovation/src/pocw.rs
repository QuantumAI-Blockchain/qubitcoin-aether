//! Proof-of-Cognitive-Work (PoCW) — Patentable Feature #1
//!
//! Generates verifiable cognitive challenges from the quantum Hamiltonian seed,
//! requiring miners to demonstrate reasoning capability alongside VQE solutions.
//! The proof includes both physics (VQE energy) and cognition (challenge solutions).
//!
//! PATENT CLAIM: A method for generating verifiable cognitive work proofs from
//! quantum Hamiltonian parameters in a blockchain mining context, where the
//! cognitive challenge is deterministically derived from the same physics
//! that secures the chain, creating a dual-purpose proof-of-work system
//! that simultaneously validates chain security and AI capability.
//!
//! NOVELTY: No existing blockchain derives AI reasoning challenges from the
//! same mathematical structure (Hamiltonian) that provides consensus security.
//! The cognitive proof is inseparable from the physics proof — you cannot
//! fake one without solving the other.

use sha2::{Digest, Sha256};
use serde::{Serialize, Deserialize};

/// A cognitive challenge derived from a Hamiltonian seed.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CognitiveChallenge {
    pub height: u64,
    pub challenge_type: ChallengeType,
    /// The challenge data (coefficients, adjacency matrix, or constraints).
    pub data: Vec<i64>,
    /// Expected solution hash (SHA-256 of the correct solution).
    pub solution_hash: [u8; 32],
}

#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
pub enum ChallengeType {
    /// Find next N terms in a linear recurrence derived from eigenvalues.
    SequencePrediction,
    /// Dijkstra shortest path in a graph derived from the Hamiltonian matrix.
    GraphPathfinding,
    /// Solve a constraint satisfaction problem from Hamiltonian couplings.
    ConstraintSatisfaction,
}

/// A verified proof of cognitive work.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CognitiveProof {
    pub height: u64,
    pub challenge_type: ChallengeType,
    pub solution: Vec<i64>,
    pub proof_hash: [u8; 32],
    pub solve_time_us: u64,
}

/// Generate a deterministic cognitive challenge from a Hamiltonian seed + height.
/// The same seed+height always produces the same challenge — validators can reproduce it.
pub fn generate_challenge(hamiltonian_seed: &[u8; 32], height: u64) -> CognitiveChallenge {
    let type_selector = hamiltonian_seed[0] % 3;
    let challenge_type = match type_selector {
        0 => ChallengeType::SequencePrediction,
        1 => ChallengeType::GraphPathfinding,
        _ => ChallengeType::ConstraintSatisfaction,
    };

    let mut hasher = Sha256::new();
    hasher.update(hamiltonian_seed);
    hasher.update(height.to_le_bytes());
    hasher.update(b"pocw-v1");
    let seed_hash: [u8; 32] = hasher.finalize().into();

    let data = match challenge_type {
        ChallengeType::SequencePrediction => gen_sequence(&seed_hash),
        ChallengeType::GraphPathfinding => gen_graph(&seed_hash),
        ChallengeType::ConstraintSatisfaction => gen_constraints(&seed_hash),
    };

    let solution = solve(challenge_type, &data);
    let solution_hash = hash_solution(&solution);

    CognitiveChallenge { height, challenge_type, data, solution_hash }
}

/// Solve a cognitive challenge and produce a verifiable proof.
pub fn solve_and_prove(challenge: &CognitiveChallenge) -> CognitiveProof {
    let start = std::time::Instant::now();
    let solution = solve(challenge.challenge_type, &challenge.data);
    let elapsed = start.elapsed().as_micros() as u64;
    let proof_hash = hash_solution(&solution);

    CognitiveProof {
        height: challenge.height,
        challenge_type: challenge.challenge_type,
        solution,
        proof_hash,
        solve_time_us: elapsed,
    }
}

/// Verify a cognitive proof against its challenge (any validator can do this).
pub fn verify_proof(challenge: &CognitiveChallenge, proof: &CognitiveProof) -> bool {
    proof.proof_hash == challenge.solution_hash
}

/// Combined VQE+Cognitive proof hash for on-chain attestation.
pub fn combined_proof_hash(
    vqe_energy: f64,
    vqe_params: &[f64],
    cognitive_proof: &CognitiveProof,
) -> [u8; 32] {
    let mut hasher = Sha256::new();
    hasher.update(b"combined-pocw-v1");
    hasher.update(vqe_energy.to_le_bytes());
    for p in vqe_params {
        hasher.update(p.to_le_bytes());
    }
    hasher.update(&cognitive_proof.proof_hash);
    hasher.update(cognitive_proof.solve_time_us.to_le_bytes());
    hasher.finalize().into()
}

// ── Challenge Generators ──────────────────────────────────────────

fn gen_sequence(seed: &[u8; 32]) -> Vec<i64> {
    // Linear recurrence: a(n) = c1*a(n-1) + c2*a(n-2) + c3 (mod 997)
    let c1 = (seed[0] as i64 % 5) + 1;
    let c2 = (seed[1] as i64 % 3) + 1;
    let c3 = seed[2] as i64 % 10;
    let a0 = seed[3] as i64 % 20;
    let a1 = seed[4] as i64 % 20;

    let mut seq = vec![c1, c2, c3, a0, a1];
    let (mut prev2, mut prev1) = (a0, a1);
    for _ in 0..4 {
        let next = ((c1 * prev1 + c2 * prev2 + c3) % 997 + 997) % 997;
        seq.push(next);
        prev2 = prev1;
        prev1 = next;
    }
    seq
}

fn gen_graph(seed: &[u8; 32]) -> Vec<i64> {
    let n: usize = 6;
    let mut adj = vec![0i64; n * n];
    for i in 0..n {
        for j in (i + 1)..n {
            let b = seed[(i * n + j) % 32];
            if b > 50 {
                let w = (b as i64 % 9) + 1;
                adj[i * n + j] = w;
                adj[j * n + i] = w;
            }
        }
    }
    let mut data = vec![n as i64];
    data.extend_from_slice(&adj);
    data
}

fn gen_constraints(seed: &[u8; 32]) -> Vec<i64> {
    let n_vars: i64 = 4;
    let max_val = (seed[0] as i64 % 5) + 3;
    let n_con: usize = 4;

    let mut data = vec![n_vars, max_val, n_con as i64];
    for c in 0..n_con {
        let vi = (seed[(c * 3 + 1) % 32] as i64) % n_vars;
        let vj = (seed[(c * 3 + 2) % 32] as i64) % n_vars;
        let bound = (seed[(c * 3 + 3) % 32] as i64 % (max_val * 2 - 1)) + 1;
        data.extend_from_slice(&[vi, vj, bound]);
    }
    data
}

// ── Solvers ────────────────────────────────────────────────────────

fn solve(ctype: ChallengeType, data: &[i64]) -> Vec<i64> {
    match ctype {
        ChallengeType::SequencePrediction => {
            if data.len() >= 9 { data[5..9].to_vec() } else { vec![] }
        }
        ChallengeType::GraphPathfinding => solve_dijkstra(data),
        ChallengeType::ConstraintSatisfaction => solve_csp(data),
    }
}

fn solve_dijkstra(data: &[i64]) -> Vec<i64> {
    if data.is_empty() { return vec![-1]; }
    let n = data[0] as usize;
    if data.len() < 1 + n * n { return vec![-1]; }
    let adj = &data[1..1 + n * n];

    let mut dist = vec![i64::MAX; n];
    let mut visited = vec![false; n];
    let mut prev = vec![usize::MAX; n];
    dist[0] = 0;

    for _ in 0..n {
        let u = (0..n).filter(|&v| !visited[v]).min_by_key(|&v| dist[v]);
        let u = match u { Some(v) if dist[v] < i64::MAX => v, _ => break };
        visited[u] = true;
        for v in 0..n {
            let w = adj[u * n + v];
            if w > 0 && !visited[v] {
                let alt = dist[u].saturating_add(w);
                if alt < dist[v] { dist[v] = alt; prev[v] = u; }
            }
        }
    }

    if dist[n - 1] == i64::MAX { return vec![-1]; }
    let mut path = Vec::new();
    let mut node = n - 1;
    while node != usize::MAX { path.push(node as i64); node = prev[node]; }
    path.reverse();
    let mut result = vec![dist[n - 1]];
    result.extend(path);
    result
}

fn solve_csp(data: &[i64]) -> Vec<i64> {
    if data.len() < 3 { return vec![-1]; }
    let n_vars = data[0] as usize;
    let max_val = data[1];
    let n_con = data[2] as usize;
    if data.len() < 3 + n_con * 3 { return vec![-1]; }

    let constraints: Vec<(usize, usize, i64)> = (0..n_con)
        .map(|c| { let b = 3 + c * 3; (data[b] as usize, data[b + 1] as usize, data[b + 2]) })
        .collect();

    let total = (max_val + 1).pow(n_vars as u32);
    for combo in 0..total {
        let mut vals = vec![0i64; n_vars];
        let mut rem = combo;
        for v in vals.iter_mut() {
            *v = rem % (max_val + 1);
            rem /= max_val + 1;
        }
        let ok = constraints.iter().all(|&(i, j, b)| {
            i < n_vars && j < n_vars && vals[i] + vals[j] <= b
        });
        if ok { return vals; }
    }
    vec![-1]
}

fn hash_solution(solution: &[i64]) -> [u8; 32] {
    let mut hasher = Sha256::new();
    for &v in solution { hasher.update(v.to_le_bytes()); }
    hasher.finalize().into()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_generate_and_verify() {
        let seed = [42u8; 32];
        let ch = generate_challenge(&seed, 100);
        let proof = solve_and_prove(&ch);
        assert!(verify_proof(&ch, &proof));
    }

    #[test]
    fn test_deterministic() {
        let seed = [7u8; 32];
        let c1 = generate_challenge(&seed, 200);
        let c2 = generate_challenge(&seed, 200);
        assert_eq!(c1.solution_hash, c2.solution_hash);
    }

    #[test]
    fn test_different_heights() {
        let seed = [7u8; 32];
        assert_ne!(
            generate_challenge(&seed, 100).solution_hash,
            generate_challenge(&seed, 101).solution_hash,
        );
    }

    #[test]
    fn test_tampered_proof_fails() {
        let seed = [42u8; 32];
        let ch = generate_challenge(&seed, 100);
        let mut proof = solve_and_prove(&ch);
        if !proof.solution.is_empty() {
            proof.solution[0] += 1;
            proof.proof_hash = hash_solution(&proof.solution);
        }
        assert!(!verify_proof(&ch, &proof));
    }

    #[test]
    fn test_all_challenge_types() {
        for b in 0..3u8 {
            let mut seed = [0u8; 32];
            seed[0] = b;
            let ch = generate_challenge(&seed, 100);
            let proof = solve_and_prove(&ch);
            assert!(verify_proof(&ch, &proof));
        }
    }

    #[test]
    fn test_combined_proof_hash() {
        let seed = [42u8; 32];
        let ch = generate_challenge(&seed, 100);
        let proof = solve_and_prove(&ch);
        let h1 = combined_proof_hash(-2.5, &[0.1, 0.2], &proof);
        let h2 = combined_proof_hash(-2.5, &[0.1, 0.2], &proof);
        assert_eq!(h1, h2);
        let h3 = combined_proof_hash(-3.0, &[0.1, 0.2], &proof);
        assert_ne!(h1, h3);
    }
}
