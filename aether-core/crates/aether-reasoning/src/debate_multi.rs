//! N-party debate with coalition formation.
//!
//! Extends the 2-party DebateProtocol to support arbitrary numbers of debate
//! parties. Parties with similar positions automatically form coalitions based
//! on Jaro-Winkler string similarity. The strongest coalition wins.

use aether_graph::KnowledgeGraph;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::sync::Arc;

/// A group of debate parties with similar positions.
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Coalition {
    pub members: Vec<String>,
    pub position: String,
    pub strength: f64,
}

/// A single party in an N-party debate.
#[derive(Clone, Debug)]
pub struct DebateParty {
    pub name: String,
    pub position: String,
    pub confidence: f64,
    pub evidence_node_ids: Vec<i64>,
}

/// Result of an N-party debate.
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct MultiPartyDebateResult {
    pub topic: String,
    pub rounds: usize,
    pub winner: String,
    pub coalitions: Vec<Coalition>,
    pub rounds_log: Vec<HashMap<String, String>>,
}

/// N-party debate engine with coalition formation.
///
/// In each round:
/// 1. Each party gathers evidence and states a position
/// 2. Parties with similar positions (Jaro-Winkler >= 0.6) form coalitions
/// 3. Coalition strength = sum of member confidences
/// 4. After all rounds, strongest coalition wins
pub struct MultiPartyDebate {
    kg: Arc<KnowledgeGraph>,
}

/// Similarity threshold for coalition formation.
const COALITION_SIMILARITY_THRESHOLD: f64 = 0.6;

impl MultiPartyDebate {
    pub fn new(kg: Arc<KnowledgeGraph>) -> Self {
        Self { kg }
    }

    pub fn knowledge_graph(&self) -> &KnowledgeGraph {
        &self.kg
    }

    /// Run an N-party debate.
    ///
    /// Each party presents a position. Parties with similar positions
    /// automatically merge into coalitions. Strongest coalition wins.
    pub fn debate(
        &self,
        topic: &str,
        parties: &mut [DebateParty],
        max_rounds: usize,
    ) -> MultiPartyDebateResult {
        if parties.is_empty() {
            return MultiPartyDebateResult {
                topic: topic.into(),
                rounds: 0,
                winner: String::new(),
                coalitions: Vec::new(),
                rounds_log: Vec::new(),
            };
        }

        let mut rounds_log = Vec::new();

        for round_num in 0..max_rounds {
            let mut round_entry = HashMap::new();
            round_entry.insert("round".into(), (round_num + 1).to_string());

            // Each party gathers evidence and updates confidence
            for party in parties.iter_mut() {
                let evidence_strength = self.compute_party_strength(party);
                party.confidence =
                    (party.confidence * 0.6 + evidence_strength * 0.4).clamp(0.0, 1.0);

                round_entry.insert(
                    format!("{}_confidence", party.name),
                    format!("{:.4}", party.confidence),
                );
            }

            rounds_log.push(round_entry);
        }

        // Form coalitions based on position similarity
        let coalitions = self.form_coalitions(parties);

        // Winner is the coalition with highest strength
        let winner = coalitions
            .iter()
            .max_by(|a, b| a.strength.partial_cmp(&b.strength).unwrap_or(std::cmp::Ordering::Equal))
            .map(|c| c.members.first().cloned().unwrap_or_default())
            .unwrap_or_default();

        MultiPartyDebateResult {
            topic: topic.into(),
            rounds: max_rounds,
            winner,
            coalitions,
            rounds_log,
        }
    }

    /// Compute the strength of a party's evidence from the knowledge graph.
    fn compute_party_strength(&self, party: &DebateParty) -> f64 {
        if party.evidence_node_ids.is_empty() {
            return party.confidence * 0.5;
        }

        let confidences: Vec<f64> = party
            .evidence_node_ids
            .iter()
            .filter_map(|&nid| self.kg.get_node(nid).map(|n| n.confidence))
            .collect();

        if confidences.is_empty() {
            return party.confidence * 0.5;
        }

        confidences.iter().sum::<f64>() / confidences.len() as f64
    }

    /// Form coalitions from parties with similar positions.
    ///
    /// Uses Jaro-Winkler similarity (via `strsim` crate). Parties
    /// with similarity >= COALITION_SIMILARITY_THRESHOLD merge.
    fn form_coalitions(&self, parties: &[DebateParty]) -> Vec<Coalition> {
        let n = parties.len();
        // Track which parties have been assigned to a coalition
        let mut assigned = vec![false; n];
        let mut coalitions = Vec::new();

        for i in 0..n {
            if assigned[i] {
                continue;
            }

            let mut members = vec![parties[i].name.clone()];
            let mut total_strength = parties[i].confidence;
            assigned[i] = true;

            for j in (i + 1)..n {
                if assigned[j] {
                    continue;
                }

                let similarity =
                    strsim::jaro_winkler(&parties[i].position, &parties[j].position);

                if similarity >= COALITION_SIMILARITY_THRESHOLD {
                    members.push(parties[j].name.clone());
                    total_strength += parties[j].confidence;
                    assigned[j] = true;
                }
            }

            coalitions.push(Coalition {
                position: parties[i].position.clone(),
                members,
                strength: total_strength,
            });
        }

        // Sort by strength descending
        coalitions.sort_by(|a, b| {
            b.strength
                .partial_cmp(&a.strength)
                .unwrap_or(std::cmp::Ordering::Equal)
        });

        coalitions
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn make_kg() -> Arc<KnowledgeGraph> {
        Arc::new(KnowledgeGraph::new())
    }

    #[test]
    fn test_multi_party_empty() {
        let kg = make_kg();
        let mpd = MultiPartyDebate::new(kg);
        let result = mpd.debate("empty topic", &mut [], 3);
        assert_eq!(result.rounds, 0);
        assert!(result.winner.is_empty());
        assert!(result.coalitions.is_empty());
    }

    #[test]
    fn test_multi_party_single() {
        let kg = make_kg();
        let mpd = MultiPartyDebate::new(kg);

        let mut parties = vec![DebateParty {
            name: "solo".into(),
            position: "the only position".into(),
            confidence: 0.8,
            evidence_node_ids: vec![],
        }];

        let result = mpd.debate("single party", &mut parties, 2);
        assert_eq!(result.rounds, 2);
        assert_eq!(result.winner, "solo");
        assert_eq!(result.coalitions.len(), 1);
    }

    #[test]
    fn test_coalition_formation_similar() {
        let kg = make_kg();
        let mpd = MultiPartyDebate::new(kg);

        let parties = vec![
            DebateParty {
                name: "A".into(),
                position: "quantum effects are significant".into(),
                confidence: 0.7,
                evidence_node_ids: vec![],
            },
            DebateParty {
                name: "B".into(),
                position: "quantum effects are significant and measurable".into(),
                confidence: 0.8,
                evidence_node_ids: vec![],
            },
            DebateParty {
                name: "C".into(),
                position: "classical physics is sufficient".into(),
                confidence: 0.6,
                evidence_node_ids: vec![],
            },
        ];

        let coalitions = mpd.form_coalitions(&parties);
        // A and B should form a coalition due to similar positions
        // C should be separate
        assert!(coalitions.len() >= 2);
    }

    #[test]
    fn test_coalition_formation_all_different() {
        let kg = make_kg();
        let mpd = MultiPartyDebate::new(kg);

        let parties = vec![
            DebateParty {
                name: "X".into(),
                position: "zzxxww".into(),
                confidence: 0.5,
                evidence_node_ids: vec![],
            },
            DebateParty {
                name: "Y".into(),
                position: "qqrrpp".into(),
                confidence: 0.6,
                evidence_node_ids: vec![],
            },
            DebateParty {
                name: "Z".into(),
                position: "aabbcc".into(),
                confidence: 0.7,
                evidence_node_ids: vec![],
            },
        ];

        let coalitions = mpd.form_coalitions(&parties);
        assert_eq!(coalitions.len(), 3);
    }

    #[test]
    fn test_multi_party_debate_with_evidence() {
        let kg = make_kg();
        let mut c = HashMap::new();
        c.insert("text".into(), "evidence node".into());
        let n = kg.add_node("assertion".into(), c, 0.9, 1, String::new());

        let mpd = MultiPartyDebate::new(Arc::clone(&kg));

        let mut parties = vec![
            DebateParty {
                name: "pro".into(),
                position: "in favor".into(),
                confidence: 0.5,
                evidence_node_ids: vec![n.node_id],
            },
            DebateParty {
                name: "con".into(),
                position: "against".into(),
                confidence: 0.5,
                evidence_node_ids: vec![],
            },
        ];

        let result = mpd.debate("test topic", &mut parties, 3);
        assert_eq!(result.rounds, 3);
        assert!(!result.winner.is_empty());
    }

    #[test]
    fn test_coalition_strength_sums() {
        let kg = make_kg();
        let mpd = MultiPartyDebate::new(kg);

        let parties = vec![
            DebateParty {
                name: "A".into(),
                position: "same position here".into(),
                confidence: 0.4,
                evidence_node_ids: vec![],
            },
            DebateParty {
                name: "B".into(),
                position: "same position here".into(),
                confidence: 0.6,
                evidence_node_ids: vec![],
            },
        ];

        let coalitions = mpd.form_coalitions(&parties);
        // Identical positions should form one coalition
        assert_eq!(coalitions.len(), 1);
        // Strength should be sum of confidences
        assert!((coalitions[0].strength - 1.0).abs() < 1e-10);
    }

    #[test]
    fn test_winner_is_strongest_coalition() {
        let kg = make_kg();
        let mpd = MultiPartyDebate::new(kg);

        let mut parties = vec![
            DebateParty {
                name: "weak".into(),
                position: "zzyyxxww".into(),
                confidence: 0.2,
                evidence_node_ids: vec![],
            },
            DebateParty {
                name: "strong".into(),
                position: "aabbccddee".into(),
                confidence: 0.9,
                evidence_node_ids: vec![],
            },
        ];

        let result = mpd.debate("strength test", &mut parties, 1);
        assert_eq!(result.winner, "strong");
    }

    #[test]
    fn test_rounds_log_populated() {
        let kg = make_kg();
        let mpd = MultiPartyDebate::new(kg);

        let mut parties = vec![DebateParty {
            name: "test".into(),
            position: "pos".into(),
            confidence: 0.5,
            evidence_node_ids: vec![],
        }];

        let result = mpd.debate("log test", &mut parties, 3);
        assert_eq!(result.rounds_log.len(), 3);
        assert!(result.rounds_log[0].contains_key("round"));
    }
}
