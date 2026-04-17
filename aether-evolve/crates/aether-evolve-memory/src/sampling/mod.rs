pub mod ucb1;

pub use ucb1::Ucb1Sampler;

use aether_evolve_core::{traits::Sampler, ExperimentNode};

/// Create a sampler by name.
pub fn create_sampler(algorithm: &str, exploration_weight: f64) -> Box<dyn Sampler> {
    match algorithm {
        "ucb1" => Box::new(Ucb1Sampler::new(exploration_weight)),
        "greedy" => Box::new(GreedySampler),
        _ => Box::new(Ucb1Sampler::new(exploration_weight)),
    }
}

/// Simple greedy sampler — always picks highest-scoring experiments.
struct GreedySampler;

impl Sampler for GreedySampler {
    fn sample(&self, experiments: &[ExperimentNode], n: usize) -> Vec<u64> {
        let mut sorted: Vec<&ExperimentNode> = experiments.iter().collect();
        sorted.sort_by(|a, b| {
            b.score
                .partial_cmp(&a.score)
                .unwrap_or(std::cmp::Ordering::Equal)
        });
        sorted.iter().take(n).map(|e| e.id).collect()
    }
}
