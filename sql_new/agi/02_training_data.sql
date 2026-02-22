SET DATABASE = qubitcoin;

-- ================================================================
-- TRAINING DATA SCHEMAS — REMOVED
-- ================================================================
-- The following tables were removed in v2.0.0 because no Python code
-- references them. They can be re-added when AGI training features
-- are implemented:
--   - training_datasets
--   - model_registry
--   - model_predictions
--
-- If these tables exist from a previous schema version, they are
-- harmless but unused. They can be dropped manually if desired.
-- ================================================================

INSERT INTO schema_version (version, component, description)
VALUES ('2.0.0', 'agi_training', 'Training data tables removed — no runtime usage')
ON CONFLICT DO NOTHING;
