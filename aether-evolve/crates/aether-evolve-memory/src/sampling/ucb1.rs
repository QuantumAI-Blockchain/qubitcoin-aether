use aether_evolve_core::{traits::Sampler, ExperimentNode};

/// UCB1 sampler for exploration-exploitation balance.
pub struct Ucb1Sampler {
    exploration_weight: f64,
}

impl Ucb1Sampler {
    pub fn new(exploration_weight: f64) -> Self {
        Self { exploration_weight }
    }
}

impl Sampler for Ucb1Sampler {
    fn sample(&self, experiments: &[ExperimentNode], n: usize) -> Vec<u64> {
        if experiments.is_empty() {
            return Vec::new();
        }

        let total = experiments.len() as f64;

        // Group experiments by their intervention type + diagnosis category
        // and compute UCB1 score per experiment
        let mut scored: Vec<(u64, f64)> = experiments
            .iter()
            .map(|exp| {
                // Count how many experiments share the same tags
                let tag_key = exp.tags.first().cloned().unwrap_or_default();
                let same_tag_count = experiments
                    .iter()
                    .filter(|e| e.tags.first().cloned().unwrap_or_default() == tag_key)
                    .count() as f64;

                // UCB1: mean_score + C * sqrt(ln(N) / n_i)
                let mean_score = exp.score / 100.0; // normalize to 0-1
                let exploration = if same_tag_count > 0.0 {
                    self.exploration_weight * (total.ln() / same_tag_count).sqrt()
                } else {
                    f64::MAX
                };

                (exp.id, mean_score + exploration)
            })
            .collect();

        scored.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap_or(std::cmp::Ordering::Equal));
        scored.iter().take(n).map(|(id, _)| *id).collect()
    }
}
