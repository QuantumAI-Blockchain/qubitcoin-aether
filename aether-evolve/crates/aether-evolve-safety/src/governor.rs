use aether_evolve_core::{AetherMetrics, CodeDiff, EvolveConfig};
use anyhow::{bail, Result};
use std::sync::atomic::{AtomicU32, Ordering};
use std::sync::Arc;
use std::time::Instant;
use tokio::sync::Mutex;
use tracing::{info, warn};

pub struct SafetyGovernor {
    config: EvolveConfig,
    api_calls_this_minute: Arc<AtomicU32>,
    code_changes_this_hour: Arc<AtomicU32>,
    minute_start: Arc<Mutex<Instant>>,
    hour_start: Arc<Mutex<Instant>>,
}

impl SafetyGovernor {
    pub fn new(config: EvolveConfig) -> Self {
        Self {
            config,
            api_calls_this_minute: Arc::new(AtomicU32::new(0)),
            code_changes_this_hour: Arc::new(AtomicU32::new(0)),
            minute_start: Arc::new(Mutex::new(Instant::now())),
            hour_start: Arc::new(Mutex::new(Instant::now())),
        }
    }

    /// Check if a code change is allowed.
    pub async fn check_code_change(&self, diffs: &[CodeDiff]) -> Result<()> {
        // Check forbidden files
        for diff in diffs {
            for forbidden in &self.config.safety.forbidden_files {
                if diff.file_path.contains(forbidden) {
                    bail!(
                        "Safety: Cannot modify forbidden file '{}' (contains '{}')",
                        diff.file_path,
                        forbidden
                    );
                }
            }
        }

        // Check rate limit
        self.reset_if_expired().await;
        let changes = self.code_changes_this_hour.load(Ordering::Relaxed);
        if changes >= self.config.safety.max_code_changes_per_hour {
            bail!(
                "Safety: Code change rate limit exceeded ({}/{})",
                changes,
                self.config.safety.max_code_changes_per_hour
            );
        }

        // Check diff count
        if diffs.len() > 3 {
            warn!(
                count = diffs.len(),
                "More than 3 diffs in a single step — proceed with caution"
            );
        }

        Ok(())
    }

    /// Record that a code change was made.
    pub fn record_code_change(&self) {
        self.code_changes_this_hour.fetch_add(1, Ordering::Relaxed);
    }

    /// Check if an API call is allowed (rate limiting).
    pub async fn check_api_call(&self) -> Result<()> {
        self.reset_if_expired().await;
        let calls = self.api_calls_this_minute.load(Ordering::Relaxed);
        if calls >= self.config.safety.max_api_calls_per_minute {
            bail!(
                "Safety: API rate limit exceeded ({}/{})",
                calls,
                self.config.safety.max_api_calls_per_minute
            );
        }
        Ok(())
    }

    /// Record an API call.
    pub fn record_api_call(&self) {
        self.api_calls_this_minute.fetch_add(1, Ordering::Relaxed);
    }

    /// Check if a regression occurred and rollback is needed.
    pub fn should_rollback(&self, pre: &AetherMetrics, post: &AetherMetrics) -> bool {
        let delta_phi = post.phi.hms_phi - pre.phi.hms_phi;
        let threshold = self.config.safety.auto_rollback_threshold;

        if delta_phi < threshold {
            warn!(
                delta_phi,
                threshold, "Regression detected — recommending rollback"
            );
            return true;
        }

        // Also rollback if gates decreased
        if post.gates_passed < pre.gates_passed {
            warn!(
                pre_gates = pre.gates_passed,
                post_gates = post.gates_passed,
                "Gate regression — recommending rollback"
            );
            return true;
        }

        false
    }

    /// Check seed count limit.
    pub fn check_seed_count(&self, count: u32) -> Result<()> {
        if count > self.config.safety.max_seeds_per_step {
            bail!(
                "Safety: Seed count {} exceeds limit {}",
                count,
                self.config.safety.max_seeds_per_step
            );
        }
        Ok(())
    }

    async fn reset_if_expired(&self) {
        let now = Instant::now();

        let mut minute = self.minute_start.lock().await;
        if now.duration_since(*minute).as_secs() >= 60 {
            *minute = now;
            self.api_calls_this_minute.store(0, Ordering::Relaxed);
        }

        let mut hour = self.hour_start.lock().await;
        if now.duration_since(*hour).as_secs() >= 3600 {
            *hour = now;
            self.code_changes_this_hour.store(0, Ordering::Relaxed);
            info!("Safety counters reset");
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use aether_evolve_core::{EvolveConfig, PhiComponents};
    use chrono::Utc;

    fn test_config() -> EvolveConfig {
        let mut config = EvolveConfig::default();
        config.safety.max_api_calls_per_minute = 5;
        config.safety.max_code_changes_per_hour = 3;
        config.safety.max_seeds_per_step = 100;
        config.safety.auto_rollback_threshold = -0.05;
        config.safety.forbidden_files = vec![".env".into(), "secure_key.env".into()];
        config
    }

    fn make_metrics(phi: f64, gates: u32) -> AetherMetrics {
        AetherMetrics {
            timestamp: Utc::now(),
            block_height: 1000,
            total_nodes: 10000,
            total_edges: 5000,
            phi: PhiComponents {
                hms_phi: phi,
                ..Default::default()
            },
            gates_passed: gates,
            gates_total: 10,
            ..Default::default()
        }
    }

    #[tokio::test]
    async fn test_forbidden_file_blocked() {
        let gov = SafetyGovernor::new(test_config());
        let diffs = vec![CodeDiff {
            file_path: "src/.env".into(),
            search: "old".into(),
            replace: "new".into(),
        }];
        let result = gov.check_code_change(&diffs).await;
        assert!(result.is_err());
        assert!(result.unwrap_err().to_string().contains("forbidden"));
    }

    #[tokio::test]
    async fn test_allowed_file_passes() {
        let gov = SafetyGovernor::new(test_config());
        let diffs = vec![CodeDiff {
            file_path: "src/qubitcoin/aether/reasoning.py".into(),
            search: "old".into(),
            replace: "new".into(),
        }];
        assert!(gov.check_code_change(&diffs).await.is_ok());
    }

    #[tokio::test]
    async fn test_code_change_rate_limit() {
        let gov = SafetyGovernor::new(test_config());
        let diffs = vec![CodeDiff {
            file_path: "test.py".into(),
            search: "a".into(),
            replace: "b".into(),
        }];

        // 3 changes allowed
        for _ in 0..3 {
            assert!(gov.check_code_change(&diffs).await.is_ok());
            gov.record_code_change();
        }

        // 4th should fail
        let result = gov.check_code_change(&diffs).await;
        assert!(result.is_err());
        assert!(result.unwrap_err().to_string().contains("rate limit"));
    }

    #[tokio::test]
    async fn test_api_call_rate_limit() {
        let gov = SafetyGovernor::new(test_config());

        // 5 calls allowed
        for _ in 0..5 {
            assert!(gov.check_api_call().await.is_ok());
            gov.record_api_call();
        }

        // 6th should fail
        assert!(gov.check_api_call().await.is_err());
    }

    #[test]
    fn test_should_rollback_phi_regression() {
        let gov = SafetyGovernor::new(test_config());
        let pre = make_metrics(3.5, 8);
        let post = make_metrics(3.4, 8); // -0.1 phi (below -0.05 threshold)
        assert!(gov.should_rollback(&pre, &post));
    }

    #[test]
    fn test_should_not_rollback_small_phi_drop() {
        let gov = SafetyGovernor::new(test_config());
        let pre = make_metrics(3.5, 8);
        let post = make_metrics(3.48, 8); // -0.02 phi (above -0.05 threshold)
        assert!(!gov.should_rollback(&pre, &post));
    }

    #[test]
    fn test_should_rollback_gate_regression() {
        let gov = SafetyGovernor::new(test_config());
        let pre = make_metrics(3.5, 8);
        let post = make_metrics(3.5, 7); // Lost a gate
        assert!(gov.should_rollback(&pre, &post));
    }

    #[test]
    fn test_should_not_rollback_improvement() {
        let gov = SafetyGovernor::new(test_config());
        let pre = make_metrics(3.5, 8);
        let post = make_metrics(3.8, 9);
        assert!(!gov.should_rollback(&pre, &post));
    }

    #[test]
    fn test_seed_count_within_limit() {
        let gov = SafetyGovernor::new(test_config());
        assert!(gov.check_seed_count(50).is_ok());
        assert!(gov.check_seed_count(100).is_ok());
    }

    #[test]
    fn test_seed_count_exceeds_limit() {
        let gov = SafetyGovernor::new(test_config());
        let result = gov.check_seed_count(101);
        assert!(result.is_err());
        assert!(result.unwrap_err().to_string().contains("Seed count"));
    }
}
