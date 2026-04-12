//! Knowledge Extractor -- Block-to-Knowledge Pipeline for Aether Tree
//!
//! Extracts structured knowledge from every block mined/received and feeds
//! it into the KnowledgeGraph as KeterNodes. This is the sensory input
//! pipeline of the AGI -- how the Aether Tree perceives the blockchain.
//!
//! Extraction categories:
//!   - Block metadata (height, difficulty, timing)
//!   - Transaction patterns (volume, fee trends, contract activity)
//!   - Mining statistics (energy, VQE convergence)
//!   - Temporal patterns (block time drift, difficulty trends)
//!   - Cross-domain interpretations (physics, economics, complexity science)

use serde::{Deserialize, Serialize};
use std::collections::HashMap;

/// Represents a block for extraction purposes.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BlockData {
    pub height: u64,
    pub difficulty: f64,
    pub timestamp: f64,
    pub hash: String,
    pub transactions: Vec<TransactionData>,
    pub proof_data: Option<ProofData>,
}

/// Transaction data for extraction.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TransactionData {
    pub tx_hash: String,
    pub fee: f64,
    pub tx_type: String,
    pub sender: String,
    pub recipient: String,
    pub amount: f64,
}

/// VQE proof data.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProofData {
    pub energy: f64,
    pub n_qubits: u32,
    pub iterations: u32,
}

/// An extracted knowledge item ready to be added to the graph.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ExtractedKnowledge {
    pub node_type: String,
    pub content: HashMap<String, serde_json::Value>,
    pub confidence: f64,
    pub source_block: u64,
    pub domain: String,
    pub grounding_source: String,
}

/// Knowledge Extractor: extracts knowledge nodes from blockchain data.
///
/// Maintains sliding windows for pattern detection (144-block window matching
/// the difficulty adjustment period).
pub struct KnowledgeExtractor {
    block_times: Vec<f64>,
    difficulties: Vec<f64>,
    tx_counts: Vec<usize>,
    energies: Vec<f64>,
    window_size: usize,
    blocks_processed: u64,
}

impl KnowledgeExtractor {
    pub fn new() -> Self {
        Self {
            block_times: Vec::new(),
            difficulties: Vec::new(),
            tx_counts: Vec::new(),
            energies: Vec::new(),
            window_size: 144,
            blocks_processed: 0,
        }
    }

    /// Extract all knowledge from a block. Returns extracted knowledge items.
    pub fn extract_from_block(&mut self, block: &BlockData) -> Vec<ExtractedKnowledge> {
        let mut results = Vec::new();

        // 1. Core block observation
        results.push(self.extract_block_metadata(block));

        // 2. Transaction patterns
        results.extend(self.extract_transaction_patterns(block));

        // 3. Mining / quantum observations
        results.extend(self.extract_mining_data(block));

        // 4. Temporal pattern detection (every 10 blocks)
        if block.height > 0 && block.height % 10 == 0 {
            results.extend(self.detect_temporal_patterns(block.height));
        }

        // 5. Difficulty trend analysis (every 144 blocks)
        if block.height > 0 && block.height % 144 == 0 {
            results.extend(self.analyze_difficulty_trends(block.height));
        }

        // 6. Cross-domain interpretations (every 50 blocks)
        if block.height > 0 && block.height % 50 == 0 {
            results.extend(self.extract_cross_domain(block));
        }

        self.blocks_processed += 1;
        results
    }

    /// Extract knowledge from a single transaction.
    pub fn extract_from_transaction(&self, tx: &TransactionData, block_height: u64) -> Vec<ExtractedKnowledge> {
        let mut results = Vec::new();
        let mut content = HashMap::new();
        content.insert("type".into(), serde_json::Value::String("transaction_observation".into()));
        content.insert("tx_hash".into(), serde_json::Value::String(tx.tx_hash.clone()));
        content.insert("tx_type".into(), serde_json::Value::String(tx.tx_type.clone()));
        content.insert("amount".into(), serde_json::json!(tx.amount));
        content.insert("fee".into(), serde_json::json!(tx.fee));
        content.insert("block_height".into(), serde_json::json!(block_height));

        results.push(ExtractedKnowledge {
            node_type: "observation".into(),
            content,
            confidence: 0.9,
            source_block: block_height,
            domain: "blockchain".into(),
            grounding_source: "block_oracle".into(),
        });
        results
    }

    /// Extract knowledge from reasoning output.
    pub fn extract_from_reasoning(
        &self,
        reasoning_type: &str,
        conclusion: &str,
        confidence: f64,
        block_height: u64,
    ) -> ExtractedKnowledge {
        let mut content = HashMap::new();
        content.insert("type".into(), serde_json::Value::String("reasoning_output".into()));
        content.insert("reasoning_type".into(), serde_json::Value::String(reasoning_type.into()));
        content.insert("conclusion".into(), serde_json::Value::String(conclusion.into()));
        content.insert("block_height".into(), serde_json::json!(block_height));

        ExtractedKnowledge {
            node_type: "inference".into(),
            content,
            confidence,
            source_block: block_height,
            domain: "ai_ml".into(),
            grounding_source: "reasoning_engine".into(),
        }
    }

    fn extract_block_metadata(&mut self, block: &BlockData) -> ExtractedKnowledge {
        let mut content = HashMap::new();
        content.insert("type".into(), serde_json::Value::String("block_observation".into()));
        content.insert("height".into(), serde_json::json!(block.height));
        content.insert("difficulty".into(), serde_json::json!(block.difficulty));
        content.insert("tx_count".into(), serde_json::json!(block.transactions.len()));
        content.insert("timestamp".into(), serde_json::json!(block.timestamp));

        // Update sliding windows
        self.difficulties.push(block.difficulty);
        self.tx_counts.push(block.transactions.len());
        if self.difficulties.len() > self.window_size {
            self.difficulties.drain(..self.difficulties.len() - self.window_size);
        }
        if self.tx_counts.len() > self.window_size {
            self.tx_counts.drain(..self.tx_counts.len() - self.window_size);
        }

        // Track block times
        if let Some(&last_ts) = self.block_times.last() {
            let block_time = block.timestamp - last_ts;
            content.insert("block_time".into(), serde_json::json!(block_time));
        }
        self.block_times.push(block.timestamp);
        if self.block_times.len() > self.window_size {
            self.block_times.drain(..self.block_times.len() - self.window_size);
        }

        ExtractedKnowledge {
            node_type: "observation".into(),
            content,
            confidence: 0.95,
            source_block: block.height,
            domain: "blockchain".into(),
            grounding_source: "block_oracle".into(),
        }
    }

    fn extract_transaction_patterns(&self, block: &BlockData) -> Vec<ExtractedKnowledge> {
        let mut results = Vec::new();
        if block.transactions.is_empty() {
            return results;
        }

        let mut total_fees = 0.0;
        let mut contract_txs = 0u32;
        let mut regular_txs = 0u32;

        for tx in &block.transactions {
            total_fees += tx.fee;
            if tx.tx_type == "contract_deploy" || tx.tx_type == "contract_call" {
                contract_txs += 1;
            } else {
                regular_txs += 1;
            }
        }

        let tx_count = block.transactions.len() as f64;
        let mut content = HashMap::new();
        content.insert("type".into(), serde_json::Value::String("transaction_pattern".into()));
        content.insert("block_height".into(), serde_json::json!(block.height));
        content.insert("tx_count".into(), serde_json::json!(block.transactions.len()));
        content.insert("regular_txs".into(), serde_json::json!(regular_txs));
        content.insert("contract_txs".into(), serde_json::json!(contract_txs));
        content.insert("total_fees".into(), serde_json::json!(total_fees));
        content.insert("avg_fee".into(), serde_json::json!(total_fees / tx_count));

        results.push(ExtractedKnowledge {
            node_type: "observation".into(),
            content,
            confidence: 0.9,
            source_block: block.height,
            domain: "blockchain".into(),
            grounding_source: "block_oracle".into(),
        });

        // High contract activity inference
        if contract_txs > 3 {
            let mut inf_content = HashMap::new();
            inf_content.insert("type".into(), serde_json::Value::String("activity_inference".into()));
            inf_content.insert("pattern".into(), serde_json::Value::String("high_contract_activity".into()));
            inf_content.insert("block_height".into(), serde_json::json!(block.height));
            inf_content.insert("contract_tx_count".into(), serde_json::json!(contract_txs));

            results.push(ExtractedKnowledge {
                node_type: "inference".into(),
                content: inf_content,
                confidence: 0.7,
                source_block: block.height,
                domain: "blockchain".into(),
                grounding_source: "block_oracle".into(),
            });
        }

        results
    }

    fn extract_mining_data(&mut self, block: &BlockData) -> Vec<ExtractedKnowledge> {
        let mut results = Vec::new();
        if let Some(ref proof) = block.proof_data {
            if proof.energy != 0.0 {
                let mut content = HashMap::new();
                content.insert("type".into(), serde_json::Value::String("quantum_observation".into()));
                content.insert("energy".into(), serde_json::json!(proof.energy));
                content.insert("difficulty".into(), serde_json::json!(block.difficulty));
                content.insert("block_height".into(), serde_json::json!(block.height));
                content.insert("n_qubits".into(), serde_json::json!(proof.n_qubits));
                content.insert("optimizer_iterations".into(), serde_json::json!(proof.iterations));

                results.push(ExtractedKnowledge {
                    node_type: "observation".into(),
                    content,
                    confidence: 0.9,
                    source_block: block.height,
                    domain: "quantum_physics".into(),
                    grounding_source: "block_oracle".into(),
                });

                self.energies.push(proof.energy);
                if self.energies.len() > self.window_size {
                    self.energies.drain(..self.energies.len() - self.window_size);
                }
            }
        }
        results
    }

    fn detect_temporal_patterns(&self, block_height: u64) -> Vec<ExtractedKnowledge> {
        let mut results = Vec::new();
        if self.block_times.len() < 10 {
            return results;
        }

        let recent = &self.block_times[self.block_times.len() - 10..];
        let intervals: Vec<f64> = recent.windows(2).map(|w| w[1] - w[0]).collect();
        if intervals.is_empty() {
            return results;
        }

        let avg_interval: f64 = intervals.iter().sum::<f64>() / intervals.len() as f64;
        let target = 3.3;
        let drift = (avg_interval - target).abs() / target;

        if drift > 0.20 {
            let direction = if avg_interval < target { "fast" } else { "slow" };
            let mut content = HashMap::new();
            content.insert("type".into(), serde_json::Value::String("temporal_pattern".into()));
            content.insert("pattern".into(), serde_json::Value::String(format!("block_time_{}", direction)));
            content.insert("avg_block_time".into(), serde_json::json!(avg_interval));
            content.insert("target_block_time".into(), serde_json::json!(target));
            content.insert("drift_percent".into(), serde_json::json!(drift * 100.0));
            content.insert("block_height".into(), serde_json::json!(block_height));

            results.push(ExtractedKnowledge {
                node_type: "inference".into(),
                content,
                confidence: 0.75,
                source_block: block_height,
                domain: "blockchain".into(),
                grounding_source: "block_oracle".into(),
            });
        }
        results
    }

    fn analyze_difficulty_trends(&self, block_height: u64) -> Vec<ExtractedKnowledge> {
        let mut results = Vec::new();
        if self.difficulties.len() < 20 {
            return results;
        }

        let n = self.difficulties.len().min(144);
        let recent = &self.difficulties[self.difficulties.len() - n..];
        let n_f = n as f64;
        let x_mean = (n_f - 1.0) / 2.0;
        let y_mean: f64 = recent.iter().sum::<f64>() / n_f;

        let numerator: f64 = recent.iter().enumerate()
            .map(|(i, &y)| (i as f64 - x_mean) * (y - y_mean))
            .sum();
        let denominator: f64 = (0..n).map(|i| (i as f64 - x_mean).powi(2)).sum();

        if denominator == 0.0 {
            return results;
        }

        let slope = numerator / denominator;
        let normalized_slope = if y_mean > 0.0 { slope / y_mean } else { 0.0 };

        let trend = if normalized_slope > 0.01 {
            "rising"
        } else if normalized_slope < -0.01 {
            "falling"
        } else {
            "stable"
        };

        let mut content = HashMap::new();
        content.insert("type".into(), serde_json::Value::String("difficulty_trend".into()));
        content.insert("trend".into(), serde_json::Value::String(trend.into()));
        content.insert("normalized_slope".into(), serde_json::json!(normalized_slope));
        content.insert("mean_difficulty".into(), serde_json::json!(y_mean));
        content.insert("window_size".into(), serde_json::json!(n));
        content.insert("block_height".into(), serde_json::json!(block_height));

        results.push(ExtractedKnowledge {
            node_type: "inference".into(),
            content,
            confidence: 0.8,
            source_block: block_height,
            domain: "blockchain".into(),
            grounding_source: "block_oracle".into(),
        });

        results
    }

    fn extract_cross_domain(&self, block: &BlockData) -> Vec<ExtractedKnowledge> {
        let mut results = Vec::new();

        // Physics: VQE as ground-state energy optimization
        if let Some(ref proof) = block.proof_data {
            if proof.energy != 0.0 && block.difficulty != 0.0 {
                let mut content = HashMap::new();
                content.insert("type".into(), serde_json::Value::String("cross_domain_observation".into()));
                content.insert("domain".into(), serde_json::Value::String("physics".into()));
                content.insert("description".into(), serde_json::Value::String(format!(
                    "VQE found ground state energy {:.6} for a {}-qubit SUSY Hamiltonian. \
                     Demonstrates variational principle in quantum mechanics.",
                    proof.energy, proof.n_qubits
                )));
                content.insert("energy".into(), serde_json::json!(proof.energy));
                content.insert("block_height".into(), serde_json::json!(block.height));

                results.push(ExtractedKnowledge {
                    node_type: "observation".into(),
                    content,
                    confidence: 0.85,
                    source_block: block.height,
                    domain: "physics".into(),
                    grounding_source: "block_oracle".into(),
                });
            }
        }

        // Economics: Transaction volume as supply-demand signal
        if self.tx_counts.len() >= 10 {
            let recent: Vec<f64> = self.tx_counts[self.tx_counts.len() - 10..]
                .iter().map(|&x| x as f64).collect();
            let avg_tx: f64 = recent.iter().sum::<f64>() / recent.len() as f64;
            if avg_tx > 0.0 {
                let variance: f64 = recent.iter().map(|&x| (x - avg_tx).powi(2)).sum::<f64>() / recent.len() as f64;
                let volatility = variance.sqrt() / avg_tx;

                let mut content = HashMap::new();
                content.insert("type".into(), serde_json::Value::String("cross_domain_observation".into()));
                content.insert("domain".into(), serde_json::Value::String("economics".into()));
                content.insert("description".into(), serde_json::Value::String(format!(
                    "Network tx volume averaging {:.1} tx/block with CV {:.3}. \
                     Fee market reflects supply-demand for block space.",
                    avg_tx, volatility
                )));
                content.insert("avg_tx_volume".into(), serde_json::json!(avg_tx));
                content.insert("volatility".into(), serde_json::json!(volatility));
                content.insert("block_height".into(), serde_json::json!(block.height));

                results.push(ExtractedKnowledge {
                    node_type: "observation".into(),
                    content,
                    confidence: 0.8,
                    source_block: block.height,
                    domain: "economics".into(),
                    grounding_source: "block_oracle".into(),
                });
            }
        }

        results
    }

    /// Get extractor statistics.
    pub fn get_stats(&self) -> HashMap<String, serde_json::Value> {
        let avg_difficulty = if self.difficulties.is_empty() {
            0.0
        } else {
            self.difficulties.iter().sum::<f64>() / self.difficulties.len() as f64
        };
        let avg_tx = if self.tx_counts.is_empty() {
            0.0
        } else {
            self.tx_counts.iter().sum::<usize>() as f64 / self.tx_counts.len() as f64
        };

        let mut stats = HashMap::new();
        stats.insert("blocks_processed".into(), serde_json::json!(self.blocks_processed));
        stats.insert("window_size".into(), serde_json::json!(self.window_size));
        stats.insert("avg_difficulty".into(), serde_json::json!(avg_difficulty));
        stats.insert("avg_tx_count".into(), serde_json::json!(avg_tx));
        stats.insert("difficulty_samples".into(), serde_json::json!(self.difficulties.len()));
        stats.insert("energy_samples".into(), serde_json::json!(self.energies.len()));
        stats
    }
}

impl Default for KnowledgeExtractor {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn make_block(height: u64, difficulty: f64, tx_count: usize) -> BlockData {
        let txs: Vec<TransactionData> = (0..tx_count).map(|i| TransactionData {
            tx_hash: format!("0x{:064x}", i),
            fee: 0.001,
            tx_type: if i % 5 == 0 { "contract_deploy".into() } else { "transfer".into() },
            sender: "0xaaa".into(),
            recipient: "0xbbb".into(),
            amount: 10.0,
        }).collect();

        BlockData {
            height,
            difficulty,
            timestamp: 1000.0 + height as f64 * 3.3,
            hash: format!("0x{:064x}", height),
            transactions: txs,
            proof_data: Some(ProofData { energy: -1.5, n_qubits: 4, iterations: 100 }),
        }
    }

    #[test]
    fn test_extract_from_block_basic() {
        let mut extractor = KnowledgeExtractor::new();
        let block = make_block(100, 10.5, 3);
        let results = extractor.extract_from_block(&block);
        assert!(!results.is_empty());
        // Should have at least block metadata + tx pattern + mining data
        assert!(results.len() >= 3);
    }

    #[test]
    fn test_temporal_patterns_detected() {
        let mut extractor = KnowledgeExtractor::new();
        // Feed blocks with slow times to trigger drift detection
        for i in 0..20 {
            let mut block = make_block(i, 10.0, 1);
            block.timestamp = 1000.0 + i as f64 * 6.0; // 6s blocks (slow)
            extractor.extract_from_block(&block);
        }
        let block = make_block(20, 10.0, 1);
        let results = extractor.extract_from_block(&BlockData {
            height: 20,
            timestamp: 1000.0 + 20.0 * 6.0,
            ..block
        });
        let temporal = results.iter().find(|r| {
            r.content.get("type").and_then(|v| v.as_str()) == Some("temporal_pattern")
        });
        assert!(temporal.is_some());
    }

    #[test]
    fn test_extract_from_transaction() {
        let extractor = KnowledgeExtractor::new();
        let tx = TransactionData {
            tx_hash: "0xabc".into(),
            fee: 0.01,
            tx_type: "transfer".into(),
            sender: "0x111".into(),
            recipient: "0x222".into(),
            amount: 50.0,
        };
        let results = extractor.extract_from_transaction(&tx, 42);
        assert_eq!(results.len(), 1);
        assert_eq!(results[0].source_block, 42);
    }

    #[test]
    fn test_extract_from_reasoning() {
        let extractor = KnowledgeExtractor::new();
        let result = extractor.extract_from_reasoning("deductive", "A implies B", 0.85, 100);
        assert_eq!(result.node_type, "inference");
        assert_eq!(result.confidence, 0.85);
    }

    #[test]
    fn test_difficulty_trend_analysis() {
        let mut extractor = KnowledgeExtractor::new();
        // Feed 144 blocks with rising difficulty (large increment for clear trend)
        for i in 0..144 {
            let block = make_block(i, 10.0 + i as f64 * 0.5, 1);
            extractor.extract_from_block(&block);
        }
        let block = make_block(144, 10.0 + 144.0 * 0.5, 1);
        let results = extractor.extract_from_block(&block);
        let trend = results.iter().find(|r| {
            r.content.get("type").and_then(|v| v.as_str()) == Some("difficulty_trend")
        });
        assert!(trend.is_some());
        let t = trend.unwrap();
        assert_eq!(t.content.get("trend").and_then(|v| v.as_str()), Some("rising"));
    }
}
