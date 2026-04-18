use aether_evolve_core::{
    AetherMetrics, GateStatus, PhiComponents, SubsystemStatus,
};
use anyhow::{Context, Result};
use reqwest::Client;
use serde_json::Value;
use std::collections::HashMap;
use std::time::Duration;
use tracing::{debug, info, warn};

pub struct AetherClient {
    client: Client,
    base_url: String,
    max_retries: u32,
}

impl AetherClient {
    pub fn new(base_url: &str, timeout_secs: u64, max_retries: u32) -> Result<Self> {
        let client = Client::builder()
            .timeout(Duration::from_secs(timeout_secs))
            .build()
            .context("Failed to build HTTP client")?;

        Ok(Self {
            client,
            base_url: base_url.trim_end_matches('/').to_string(),
            max_retries,
        })
    }

    pub async fn snapshot(&self) -> Result<AetherMetrics> {
        let v = self.get_json("/aether/info").await?;
        let now = chrono::Utc::now();

        // Parse the nested structure
        let kg = &v["knowledge_graph"];
        let phi_section = &v["phi"];
        let phi_detail = &v.get("phi_detail").unwrap_or(&Value::Null);
        let gates_section = &v["phi_gate_attention"];
        let prediction = &v["prediction_summary"];
        // API returns keys like "debate_protocol", "curiosity", not "debate_engine"
        let debate = &v["debate_protocol"];
        let self_imp = &v["self_improvement"];
        let curiosity = &v["curiosity"];
        let concept_formation = &v["concept_formation"];
        let causal = &v["causal_engine"];
        let metacognition = &v["metacognition"];

        // Extract phi components — also check /aether/phi for detailed data
        let phi_full = self.get_json("/aether/phi").await.unwrap_or_default();
        let hms_phi = phi_section["current_value"].as_f64().unwrap_or(0.0);
        let phi_micro = phi_full["phi_micro"]
            .as_f64()
            .or_else(|| phi_detail["phi_micro"].as_f64())
            .unwrap_or(0.0);
        let phi_meso = phi_full["phi_meso"]
            .as_f64()
            .or_else(|| phi_detail["phi_meso"].as_f64())
            .unwrap_or(0.0);
        let phi_macro = phi_full["phi_macro"]
            .as_f64()
            .or_else(|| phi_detail["phi_macro"].as_f64())
            .unwrap_or(0.0);
        let phi_formula = phi_full["phi_formula"]
            .as_str()
            .unwrap_or("unknown")
            .to_string();

        // Extract gates — prefer /aether/phi (accurate) over /aether/info gate_attention (stale)
        let mut gates = Vec::new();
        if let Some(phi_gates) = phi_full["gates"].as_array() {
            for g in phi_gates {
                gates.push(GateStatus {
                    gate_number: g["id"].as_u64().unwrap_or(0) as u32,
                    name: g["name"].as_str().unwrap_or("").to_string(),
                    passed: g["passed"].as_bool().unwrap_or(false),
                    details: g["requirement"].as_str().unwrap_or("").to_string(),
                });
            }
        } else if let Some(gs) = gates_section["gate_states"].as_object() {
            for (i, (name, passed)) in gs.iter().enumerate() {
                gates.push(GateStatus {
                    gate_number: (i + 1) as u32,
                    name: name.clone(),
                    passed: passed.as_bool().unwrap_or(false),
                    details: String::new(),
                });
            }
        }
        let gates_passed = phi_full["gates_passed"]
            .as_u64()
            .or_else(|| gates_section["gates_currently_passed"].as_u64())
            .or_else(|| phi_section["gates_passed"].as_u64())
            .unwrap_or(0) as u32;

        // Extract domains
        let mut domains = HashMap::new();
        if let Some(d) = kg["domains"].as_object() {
            for (k, v) in d {
                domains.insert(k.clone(), v.as_u64().unwrap_or(0));
            }
        }

        // Build subsystem statuses from various sections
        let mut subsystems = Vec::new();
        let subsystem_checks = [
            ("debate_engine", &debate["total_debates"]),
            ("concept_formation", &concept_formation["total_runs"]),
            ("causal_engine", &causal["total_runs"]),
            ("self_improvement", &self_imp["cycles_completed"]),
            ("metacognition", &metacognition["total_evaluations"]),
            ("curiosity_engine", &curiosity["goals_generated"]),
        ];
        for (name, runs_val) in &subsystem_checks {
            let runs = runs_val.as_u64().unwrap_or(0);
            subsystems.push(SubsystemStatus {
                name: name.to_string(),
                runs,
                last_run: None,
                active: runs > 0,
            });
        }

        let total_nodes = kg["total_nodes"].as_u64().unwrap_or(0);
        let total_edges = kg["total_edges"].as_u64().unwrap_or(0);

        let metrics = AetherMetrics {
            timestamp: now,
            block_height: v["blocks_processed"].as_u64().unwrap_or(0),
            total_nodes,
            total_edges,
            phi: PhiComponents {
                phi_micro,
                phi_meso,
                phi_macro,
                hms_phi,
                formula: phi_formula,
            },
            gates,
            gates_passed,
            gates_total: gates_section["total_gates"].as_u64().unwrap_or(10) as u32,
            debate_count: debate["total_debates"].as_u64().unwrap_or(0),
            contradiction_count: v["contradictions_resolved"].as_u64().unwrap_or(0),
            prediction_accuracy: prediction["accuracy"].as_f64().unwrap_or(0.0),
            mip_score: phi_detail["mip_score"].as_f64().unwrap_or(0.0),
            ece: metacognition["calibration_error"].as_f64().unwrap_or(1.0),
            novel_concepts: concept_formation["total_concepts_created"].as_u64().unwrap_or(0),
            auto_goals: curiosity["goals_generated"].as_u64().unwrap_or(0),
            curiosity_discoveries: curiosity["goals_completed"].as_u64().unwrap_or(0),
            self_improvement_cycles: self_imp["cycles_completed"].as_u64().unwrap_or(0),
            subsystems,
            domains,
            cross_domain_edges: kg["cross_domain_edges"].as_u64().unwrap_or(0),
            cross_domain_inferences: v["cross_domain_inferences"].as_u64().unwrap_or(0),
        };

        info!(
            nodes = metrics.total_nodes,
            edges = metrics.total_edges,
            phi = metrics.phi.hms_phi,
            gates = metrics.gates_passed,
            "Snapshot captured"
        );

        Ok(metrics)
    }

    async fn get_json(&self, path: &str) -> Result<Value> {
        let url = format!("{}{}", self.base_url, path);
        let mut last_err = None;

        for attempt in 0..=self.max_retries {
            if attempt > 0 {
                tokio::time::sleep(Duration::from_secs(2u64.pow(attempt))).await;
                debug!(attempt, path, "Retrying request");
            }

            match self.client.get(&url).send().await {
                Ok(resp) => {
                    if resp.status().is_success() {
                        match resp.json::<Value>().await {
                            Ok(v) => return Ok(v),
                            Err(e) => {
                                warn!("Failed to parse {path} response: {e}");
                                last_err = Some(anyhow::anyhow!("Parse error: {e}"));
                            }
                        }
                    } else {
                        let status = resp.status();
                        let body = resp.text().await.unwrap_or_default();
                        warn!(%status, "Non-success from {path}: {body}");
                        last_err = Some(anyhow::anyhow!("HTTP {status}: {body}"));
                    }
                }
                Err(e) => {
                    warn!("Request to {path} failed: {e}");
                    last_err = Some(anyhow::anyhow!("Request failed: {e}"));
                }
            }
        }

        Err(last_err.unwrap_or_else(|| anyhow::anyhow!("No attempts made")))
    }

    /// Send a chat message to exercise reasoning.
    pub async fn chat(&self, message: &str) -> Result<String> {
        let url = format!("{}/aether/chat", self.base_url);
        let body = serde_json::json!({ "message": message });
        let resp = self
            .client
            .post(&url)
            .json(&body)
            .send()
            .await
            .context("Chat request failed")?;

        let data: Value = resp.json().await.context("Chat parse failed")?;
        Ok(data["response"]
            .as_str()
            .unwrap_or("")
            .to_string())
    }

    /// Trigger batch knowledge ingestion.
    pub async fn ingest_batch(&self, nodes: &[Value], admin_key: &str) -> Result<u64> {
        let url = format!("{}/aether/ingest/batch", self.base_url);
        let body = serde_json::json!({
            "nodes": nodes,
            "_admin_key": admin_key,
        });
        let resp = self
            .client
            .post(&url)
            .json(&body)
            .send()
            .await
            .context("Batch ingest request failed")?;

        if !resp.status().is_success() {
            let status = resp.status();
            let body = resp.text().await.unwrap_or_default();
            warn!(%status, "Batch ingest failed: {body}");
            return Ok(0);
        }

        let data: Value = resp.json().await.context("Batch ingest parse failed")?;
        Ok(data["nodes_created"].as_u64().unwrap_or(0))
    }

    /// Force a fresh Phi recalculation (busts restored/stale caches).
    pub async fn recalculate_phi(&self) -> Result<serde_json::Value> {
        let url = format!("{}/aether/phi/recalculate", self.base_url);
        let resp = self
            .client
            .post(&url)
            .send()
            .await
            .context("Phi recalculate request failed")?;
        let data: serde_json::Value = resp.json().await.context("Phi recalculate parse failed")?;
        info!(
            phi = data["phi_value"].as_f64().unwrap_or(0.0),
            phi_meso = data["phi_meso"].as_f64().unwrap_or(0.0),
            phi_micro = data["phi_micro"].as_f64().unwrap_or(0.0),
            phi_macro = data["phi_macro"].as_f64().unwrap_or(0.0),
            formula = data["phi_formula"].as_str().unwrap_or("?"),
            "Phi recalculated"
        );
        Ok(data)
    }

    /// Health check.
    pub async fn health(&self) -> Result<bool> {
        let url = format!("{}/health", self.base_url);
        match self.client.get(&url).send().await {
            Ok(resp) => Ok(resp.status().is_success()),
            Err(_) => Ok(false),
        }
    }
}
