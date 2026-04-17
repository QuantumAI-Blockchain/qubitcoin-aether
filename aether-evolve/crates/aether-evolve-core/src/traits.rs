use crate::types::*;
use anyhow::Result;

/// Trait for evolution agents (diagnose, research, execute, analyze).
#[allow(async_fn_in_trait)]
pub trait EvolutionAgent: Send + Sync {
    fn name(&self) -> &str;
}

/// Trait for experiment sampling strategies.
pub trait Sampler: Send + Sync {
    /// Select parent experiments to build on.
    fn sample(&self, experiments: &[ExperimentNode], n: usize) -> Vec<u64>;
}

/// Trait for metric snapshot providers.
#[allow(async_fn_in_trait)]
pub trait MetricsProvider: Send + Sync {
    async fn snapshot(&self) -> Result<AetherMetrics>;
}

/// Trait for knowledge seeding.
#[allow(async_fn_in_trait)]
pub trait KnowledgeSeeder: Send + Sync {
    async fn seed_batch(&self, payloads: &[KnowledgePayload]) -> Result<u64>;
    async fn trigger_debate(&self, topic: &str) -> Result<()>;
    async fn trigger_causal_discovery(&self) -> Result<()>;
}
