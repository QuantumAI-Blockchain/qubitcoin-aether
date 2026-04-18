use crate::config::*;
use crate::types::*;
use chrono::Utc;

    // ── Config tests ──────────────────────────────────────────────────────

    #[test]
    fn test_default_config_values() {
        let config = EvolveConfig::default();
        assert_eq!(config.general.name, "aether-evolve");
        assert_eq!(config.general.log_level, "info");
        assert_eq!(config.aether.base_url, "http://localhost:5000");
        assert_eq!(config.aether.timeout_secs, 30);
        assert_eq!(config.aether.max_retries, 3);
        assert_eq!(config.claude.enabled, false);
        assert_eq!(config.safety.max_api_calls_per_minute, 60);
        assert_eq!(config.safety.max_code_changes_per_hour, 5);
        assert_eq!(config.safety.max_seeds_per_step, 1000);
        assert!(config.safety.forbidden_files.contains(&".env".to_string()));
        assert!(config.safety.forbidden_files.contains(&"secure_key.env".to_string()));
    }

    #[test]
    fn test_config_from_toml() {
        let toml_content = r#"
[general]
name = "test-evolve"
log_level = "debug"
data_dir = "/tmp/test"
aether_source = "/tmp/aether"

[aether]
base_url = "http://example.com:5000"
timeout_secs = 60
max_retries = 5
admin_key = "test-key-123"

[claude]
enabled = true

[ollama]
base_url = "http://localhost:11434"
primary_model = "qwen2.5:7b"
fast_model = "qwen2.5:3b"
bulk_model = "qwen2.5:0.5b"
timeout_secs = 120
max_concurrent = 4

[pipeline]
max_steps = 100
step_interval_secs = 30
parallel_workers = 8
save_interval = 5

[sampling]
algorithm = "ucb1"
sample_n = 5
exploration_weight = 2.0

[safety]
max_api_calls_per_minute = 30
max_code_changes_per_hour = 10
max_seeds_per_step = 500
min_test_pass_rate = 0.90
max_memory_mb = 4096
auto_rollback_threshold = -0.10
forbidden_files = [".env", "genesis.py"]
"#;
        let config: EvolveConfig = toml::from_str(toml_content).unwrap();
        assert_eq!(config.general.name, "test-evolve");
        assert_eq!(config.aether.timeout_secs, 60);
        assert_eq!(config.aether.admin_key, "test-key-123");
        assert!(config.claude.enabled);
        assert_eq!(config.pipeline.max_steps, 100);
        assert_eq!(config.safety.max_api_calls_per_minute, 30);
        assert_eq!(config.safety.forbidden_files.len(), 2);
    }

    #[test]
    fn test_claude_config_defaults_to_disabled() {
        let toml_content = r#"
[general]
name = "test"
log_level = "info"
data_dir = "/tmp"
aether_source = "/tmp"

[aether]
base_url = "http://localhost:5000"
timeout_secs = 30
max_retries = 3

[ollama]
base_url = "http://localhost:11434"
primary_model = "qwen2.5:7b"
fast_model = "qwen2.5:3b"
bulk_model = "qwen2.5:0.5b"
timeout_secs = 120
max_concurrent = 2

[pipeline]
max_steps = 0
step_interval_secs = 60
parallel_workers = 4
save_interval = 10

[sampling]
algorithm = "ucb1"
sample_n = 3
exploration_weight = 1.414

[safety]
max_api_calls_per_minute = 60
max_code_changes_per_hour = 5
max_seeds_per_step = 1000
min_test_pass_rate = 0.95
max_memory_mb = 2048
auto_rollback_threshold = -0.05
forbidden_files = [".env"]
"#;
        let config: EvolveConfig = toml::from_str(toml_content).unwrap();
        assert!(!config.claude.enabled);
    }

    // ── MetricsDelta tests ────────────────────────────────────────────────

    fn make_metrics(
        phi: f64,
        nodes: u64,
        edges: u64,
        gates_passed: u32,
        debates: u64,
        novel: u64,
        subsystems: Vec<SubsystemStatus>,
    ) -> AetherMetrics {
        AetherMetrics {
            timestamp: Utc::now(),
            block_height: 1000,
            total_nodes: nodes,
            total_edges: edges,
            phi: PhiComponents {
                phi_micro: phi * 0.5,
                phi_meso: phi * 0.3,
                phi_macro: phi * 0.2,
                hms_phi: phi,
                formula: "test".into(),
            },
            gates: vec![],
            gates_passed,
            gates_total: 10,
            debate_count: debates,
            contradiction_count: 0,
            prediction_accuracy: 0.9,
            mip_score: 0.5,
            ece: 0.1,
            novel_concepts: novel,
            auto_goals: 10,
            curiosity_discoveries: 5,
            self_improvement_cycles: 3,
            subsystems,
            domains: Default::default(),
            cross_domain_edges: 100,
            cross_domain_inferences: 50,
        }
    }

    #[test]
    fn test_metrics_delta_compute_basic() {
        let pre = make_metrics(3.0, 1000, 500, 7, 10, 5, vec![]);
        let post = make_metrics(3.5, 1200, 600, 8, 15, 8, vec![]);

        let delta = MetricsDelta::compute(&pre, &post);
        assert!((delta.delta_phi - 0.5).abs() < 1e-10);
        assert_eq!(delta.delta_nodes, 200);
        assert_eq!(delta.delta_edges, 100);
        assert_eq!(delta.delta_gates, 1);
        assert_eq!(delta.delta_debates, 5);
        assert_eq!(delta.delta_novel_concepts, 3);
        assert!(delta.subsystems_activated.is_empty());
    }

    #[test]
    fn test_metrics_delta_negative_phi() {
        let pre = make_metrics(3.5, 1000, 500, 8, 10, 5, vec![]);
        let post = make_metrics(3.0, 1000, 500, 8, 10, 5, vec![]);

        let delta = MetricsDelta::compute(&pre, &post);
        assert!(delta.delta_phi < 0.0);
    }

    #[test]
    fn test_metrics_delta_subsystem_activation() {
        let pre_sub = vec![SubsystemStatus {
            name: "debate".into(),
            runs: 0,
            last_run: None,
            active: false,
        }];
        let post_sub = vec![SubsystemStatus {
            name: "debate".into(),
            runs: 5,
            last_run: None,
            active: true,
        }];

        let pre = make_metrics(3.0, 1000, 500, 7, 10, 5, pre_sub);
        let post = make_metrics(3.0, 1000, 500, 7, 10, 5, post_sub);

        let delta = MetricsDelta::compute(&pre, &post);
        assert_eq!(delta.subsystems_activated, vec!["debate".to_string()]);
    }

    #[test]
    fn test_metrics_delta_score_positive() {
        let pre = make_metrics(3.0, 1000, 500, 7, 10, 5, vec![]);
        let post = make_metrics(3.5, 1200, 600, 8, 15, 8, vec![]);

        let delta = MetricsDelta::compute(&pre, &post);
        let score = delta.score();
        assert!(score > 0.0, "Score should be positive for improvements");
        assert!(score <= 100.0, "Score should not exceed 100");
    }

    #[test]
    fn test_metrics_delta_score_stability_bonus() {
        // Positive phi delta should get stability bonus
        let pre = make_metrics(3.0, 1000, 500, 7, 0, 0, vec![]);
        let post = make_metrics(3.1, 1000, 500, 7, 0, 0, vec![]);
        let delta = MetricsDelta::compute(&pre, &post);
        let score_positive = delta.score();

        // Negative phi delta should lose stability bonus
        let post_neg = make_metrics(2.9, 1000, 500, 7, 0, 0, vec![]);
        let delta_neg = MetricsDelta::compute(&pre, &post_neg);
        let score_negative = delta_neg.score();

        assert!(
            score_positive > score_negative,
            "Positive phi should score higher than negative"
        );
    }

    #[test]
    fn test_metrics_delta_score_clamping() {
        // Extreme values should be clamped
        let pre = make_metrics(0.0, 0, 0, 0, 0, 0, vec![]);
        let post = make_metrics(100.0, 1_000_000, 500_000, 10, 1000, 1000, vec![]);

        let delta = MetricsDelta::compute(&pre, &post);
        let score = delta.score();
        assert!(score <= 100.0, "Score must be clamped to 100 max");
    }

    // ── Type serialization tests ──────────────────────────────────────────

    #[test]
    fn test_intervention_type_serialization() {
        let types = vec![
            InterventionType::CodeChange,
            InterventionType::KnowledgeSeed,
            InterventionType::SwarmSeed,
            InterventionType::ApiCall,
            InterventionType::CacheBust,
        ];
        for t in &types {
            let json = serde_json::to_string(t).unwrap();
            let parsed: InterventionType = serde_json::from_str(&json).unwrap();
            assert_eq!(&parsed, t);
        }
    }

    #[test]
    fn test_intervention_type_snake_case() {
        let json = serde_json::to_string(&InterventionType::CodeChange).unwrap();
        assert_eq!(json, "\"code_change\"");

        let json = serde_json::to_string(&InterventionType::KnowledgeSeed).unwrap();
        assert_eq!(json, "\"knowledge_seed\"");
    }

    #[test]
    fn test_diagnosis_priority_ordering() {
        assert!(DiagnosisPriority::P0PhiZero < DiagnosisPriority::P1GateBlocker);
        assert!(DiagnosisPriority::P1GateBlocker < DiagnosisPriority::P5NovelSynthesis);
    }

    #[test]
    fn test_evolve_plan_serialization_roundtrip() {
        let plan = EvolvePlan {
            intervention_type: InterventionType::KnowledgeSeed,
            hypothesis: "Seeding cross-domain knowledge improves phi".into(),
            diffs: vec![],
            seeds: vec![KnowledgePayload {
                content: "Quantum entanglement enables secure communication".into(),
                domain: "quantum_physics".into(),
                node_type: "assertion".into(),
                confidence: 0.85,
                connections: vec!["cryptography".into()],
            }],
        };

        let json = serde_json::to_string_pretty(&plan).unwrap();
        let parsed: EvolvePlan = serde_json::from_str(&json).unwrap();

        assert_eq!(parsed.hypothesis, plan.hypothesis);
        assert_eq!(parsed.seeds.len(), 1);
        assert_eq!(parsed.seeds[0].domain, "quantum_physics");
        assert_eq!(parsed.seeds[0].confidence, 0.85);
    }

    #[test]
    fn test_pipeline_state_default() {
        let state = PipelineState::default();
        assert_eq!(state.current_step, 0);
        assert_eq!(state.current_phase, PipelinePhase::FixZeros);
        assert_eq!(state.total_experiments, 0);
        assert_eq!(state.best_score, 0.0);
        assert!(state.best_experiment_id.is_none());
    }

    #[test]
    fn test_pipeline_phase_serialization() {
        let phase = PipelinePhase::CognitiveIntegration;
        let json = serde_json::to_string(&phase).unwrap();
        assert_eq!(json, "\"cognitive_integration\"");

        let parsed: PipelinePhase = serde_json::from_str(&json).unwrap();
        assert_eq!(parsed, PipelinePhase::CognitiveIntegration);
    }

    #[test]
    fn test_aether_metrics_default() {
        let m = AetherMetrics::default();
        assert_eq!(m.total_nodes, 0);
        assert_eq!(m.total_edges, 0);
        assert_eq!(m.phi.hms_phi, 0.0);
        assert_eq!(m.gates_passed, 0);
        assert!(m.subsystems.is_empty());
        assert!(m.domains.is_empty());
    }

    #[test]
    fn test_code_diff_serialization() {
        let diff = CodeDiff {
            file_path: "src/qubitcoin/aether/reasoning.py".into(),
            search: "old_code()".into(),
            replace: "new_code()".into(),
        };
        let json = serde_json::to_string(&diff).unwrap();
        let parsed: CodeDiff = serde_json::from_str(&json).unwrap();
        assert_eq!(parsed.file_path, diff.file_path);
        assert_eq!(parsed.search, diff.search);
        assert_eq!(parsed.replace, diff.replace);
    }
