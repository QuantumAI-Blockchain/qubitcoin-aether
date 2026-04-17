use aether_evolve_core::KnowledgePayload;
use anyhow::{Context, Result};
use tracing::info;

use crate::client::AetherClient;

pub struct KnowledgeSeederImpl {
    client: AetherClient,
}

impl KnowledgeSeederImpl {
    pub fn new(client: AetherClient) -> Self {
        Self { client }
    }

    /// Seed a batch of knowledge payloads, converting to API format.
    pub async fn seed_batch(&self, payloads: &[KnowledgePayload]) -> Result<u64> {
        if payloads.is_empty() {
            return Ok(0);
        }

        let nodes: Vec<serde_json::Value> = payloads
            .iter()
            .map(|p| {
                serde_json::json!({
                    "content": p.content,
                    "domain": p.domain,
                    "node_type": p.node_type,
                    "confidence": p.confidence,
                    "connections": p.connections,
                })
            })
            .collect();

        // Batch in chunks of 100 to avoid overloading the API
        let mut total = 0u64;
        for chunk in nodes.chunks(100) {
            let ingested = self
                .client
                .ingest_batch(chunk)
                .await
                .context("Batch seed failed")?;
            total += ingested;
        }

        info!(total, payloads = payloads.len(), "Knowledge batch seeded");
        Ok(total)
    }

    /// Trigger a debate by chatting with a controversial / contradictory topic.
    pub async fn trigger_debate(&self, topic: &str) -> Result<()> {
        let prompt = format!(
            "I want to challenge a belief: {}. Present the strongest counterargument \
             and let's debate this.",
            topic
        );
        let _response = self.client.chat(&prompt).await?;
        info!(topic, "Debate triggered");
        Ok(())
    }

    /// Trigger causal discovery by submitting causal observations.
    pub async fn trigger_causal_discovery(&self) -> Result<()> {
        let causal_prompt =
            "Analyze the causal relationships between the most recent knowledge nodes. \
             What causes what? Identify any confounders or spurious correlations.";
        let _response = self.client.chat(causal_prompt).await?;
        info!("Causal discovery triggered");
        Ok(())
    }

    /// Health check passthrough.
    pub async fn health(&self) -> Result<bool> {
        self.client.health().await
    }
}
