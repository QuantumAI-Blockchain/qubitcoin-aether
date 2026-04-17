use aether_evolve_core::ExperimentNode;
use anyhow::{Context, Result};
use std::path::PathBuf;
use tracing::info;

/// File-backed experiment database using JSONL for persistence.
/// Each experiment is appended as a JSON line. On load, all lines are read.
pub struct ExperimentDb {
    path: PathBuf,
    experiments: Vec<ExperimentNode>,
    next_id: u64,
}

impl ExperimentDb {
    pub fn open(data_dir: &std::path::Path) -> Result<Self> {
        let path = data_dir.join("experiments.jsonl");
        std::fs::create_dir_all(data_dir).context("Failed to create data dir")?;

        let mut experiments = Vec::new();
        let mut next_id = 1u64;

        if path.exists() {
            let content = std::fs::read_to_string(&path).context("Failed to read experiments")?;
            for line in content.lines() {
                if line.trim().is_empty() {
                    continue;
                }
                match serde_json::from_str::<ExperimentNode>(line) {
                    Ok(exp) => {
                        if exp.id >= next_id {
                            next_id = exp.id + 1;
                        }
                        experiments.push(exp);
                    }
                    Err(e) => {
                        tracing::warn!("Skipping malformed experiment line: {e}");
                    }
                }
            }
            info!(count = experiments.len(), "Loaded experiments from disk");
        }

        Ok(Self {
            path,
            experiments,
            next_id,
        })
    }

    pub fn insert(&mut self, mut experiment: ExperimentNode) -> Result<u64> {
        experiment.id = self.next_id;
        self.next_id += 1;

        let line =
            serde_json::to_string(&experiment).context("Failed to serialize experiment")?;

        use std::io::Write;
        let mut file = std::fs::OpenOptions::new()
            .create(true)
            .append(true)
            .open(&self.path)
            .context("Failed to open experiments file")?;
        writeln!(file, "{line}").context("Failed to write experiment")?;

        let id = experiment.id;
        self.experiments.push(experiment);
        Ok(id)
    }

    pub fn get(&self, id: u64) -> Option<&ExperimentNode> {
        self.experiments.iter().find(|e| e.id == id)
    }

    pub fn all(&self) -> &[ExperimentNode] {
        &self.experiments
    }

    pub fn count(&self) -> usize {
        self.experiments.len()
    }

    /// Get the top N experiments by score.
    pub fn top_by_score(&self, n: usize) -> Vec<&ExperimentNode> {
        let mut sorted: Vec<&ExperimentNode> = self.experiments.iter().collect();
        sorted.sort_by(|a, b| b.score.partial_cmp(&a.score).unwrap_or(std::cmp::Ordering::Equal));
        sorted.truncate(n);
        sorted
    }

    /// Get experiments by intervention type.
    pub fn by_type(
        &self,
        intervention_type: &aether_evolve_core::InterventionType,
    ) -> Vec<&ExperimentNode> {
        self.experiments
            .iter()
            .filter(|e| &e.intervention_type == intervention_type)
            .collect()
    }

    /// Get recent N experiments.
    pub fn recent(&self, n: usize) -> Vec<&ExperimentNode> {
        let start = self.experiments.len().saturating_sub(n);
        self.experiments[start..].iter().collect()
    }
}
