//! Row structs that map 1:1 to CockroachDB tables.
//!
//! Each struct derives `sqlx::FromRow` for automatic query mapping and
//! provides conversion methods to/from the canonical `aether-types` types.

use chrono::NaiveDateTime;
use serde::{Deserialize, Serialize};
use serde_json::Value as JsonValue;
use std::collections::HashMap;

use aether_types::{KeterEdge, KeterNode};

// ---------------------------------------------------------------------------
// knowledge_nodes
// ---------------------------------------------------------------------------

/// Row from the `knowledge_nodes` table.
#[derive(Clone, Debug, Serialize, Deserialize, sqlx::FromRow)]
pub struct KnowledgeNodeRow {
    pub id: i64,
    pub node_type: String,
    pub content_hash: String,
    pub content: JsonValue,
    pub confidence: f64,
    pub source_block: i64,
    pub domain: String,
    pub grounding_source: String,
    pub reference_count: i32,
    pub last_referenced_block: i64,
    pub search_text: Option<String>,
    pub created_at: NaiveDateTime,
}

impl KnowledgeNodeRow {
    /// Convert a DB row into a `KeterNode`.
    ///
    /// The `content` JSONB column is flattened to `HashMap<String, String>` by
    /// converting every value to its JSON string representation.
    pub fn into_keter_node(self) -> KeterNode {
        let content = jsonb_to_hashmap(&self.content);
        KeterNode::new(
            self.id,
            self.node_type,
            self.content_hash,
            content,
            self.confidence,
            self.source_block,
            self.created_at.and_utc().timestamp() as f64,
            self.domain,
            self.last_referenced_block,
            self.reference_count as i64,
            self.grounding_source,
            vec![],
            vec![],
        )
    }

    /// Build a row from a `KeterNode` (for inserts).
    ///
    /// The `id` and `created_at` fields are ignored on insert (DB auto-generates them).
    pub fn from_keter_node(node: &KeterNode) -> Self {
        Self {
            id: node.node_id,
            node_type: node.node_type.clone(),
            content_hash: node.content_hash.clone(),
            content: hashmap_to_jsonb(&node.content),
            confidence: node.confidence,
            source_block: node.source_block,
            domain: node.domain.clone(),
            grounding_source: node.grounding_source.clone(),
            reference_count: node.reference_count as i32,
            last_referenced_block: node.last_referenced_block,
            search_text: node.content.get("text").cloned(),
            created_at: NaiveDateTime::default(),
        }
    }
}

// ---------------------------------------------------------------------------
// knowledge_edges
// ---------------------------------------------------------------------------

/// Row from the `knowledge_edges` table.
#[derive(Clone, Debug, Serialize, Deserialize, sqlx::FromRow)]
pub struct KnowledgeEdgeRow {
    pub id: i64,
    pub from_node_id: i64,
    pub to_node_id: i64,
    pub edge_type: String,
    pub weight: f64,
    pub created_at: NaiveDateTime,
}

impl KnowledgeEdgeRow {
    /// Convert a DB row into a `KeterEdge`.
    pub fn into_keter_edge(self) -> KeterEdge {
        KeterEdge::new(
            self.from_node_id,
            self.to_node_id,
            self.edge_type,
            self.weight,
            self.created_at.and_utc().timestamp() as f64,
        )
    }

    /// Build a row from a `KeterEdge` (for inserts).
    pub fn from_keter_edge(edge: &KeterEdge) -> Self {
        Self {
            id: 0,
            from_node_id: edge.from_node_id,
            to_node_id: edge.to_node_id,
            edge_type: edge.edge_type.clone(),
            weight: edge.weight,
            created_at: NaiveDateTime::default(),
        }
    }
}

// ---------------------------------------------------------------------------
// reasoning_operations
// ---------------------------------------------------------------------------

/// Row from the `reasoning_operations` table.
#[derive(Clone, Debug, Serialize, Deserialize, sqlx::FromRow)]
pub struct ReasoningOperationRow {
    pub id: i64,
    pub operation_type: String,
    pub premise_nodes: JsonValue,
    pub conclusion_node_id: i64,
    pub confidence: f64,
    pub reasoning_chain: JsonValue,
    pub block_height: i64,
    pub created_at: NaiveDateTime,
}

// ---------------------------------------------------------------------------
// phi_measurements
// ---------------------------------------------------------------------------

/// Row from the `phi_measurements` table.
#[derive(Clone, Debug, Serialize, Deserialize, sqlx::FromRow)]
pub struct PhiMeasurementRow {
    pub id: i64,
    pub phi_value: f64,
    pub phi_threshold: f64,
    pub integration_score: f64,
    pub differentiation_score: f64,
    pub num_nodes: i64,
    pub num_edges: i64,
    pub block_height: i64,
    pub measured_at: NaiveDateTime,
}

// ---------------------------------------------------------------------------
// consciousness_events
// ---------------------------------------------------------------------------

/// Row from the `consciousness_events` table.
#[derive(Clone, Debug, Serialize, Deserialize, sqlx::FromRow)]
pub struct ConsciousnessEventRow {
    pub id: i64,
    pub event_type: String,
    pub phi_at_event: f64,
    pub trigger_data: JsonValue,
    pub is_verified: bool,
    pub block_height: i64,
    pub created_at: NaiveDateTime,
}

// ---------------------------------------------------------------------------
// conversation_sessions
// ---------------------------------------------------------------------------

/// Row from the `conversation_sessions` table.
#[derive(Clone, Debug, Serialize, Deserialize, sqlx::FromRow)]
pub struct ConversationSessionRow {
    pub session_id: uuid::Uuid,
    pub user_id: String,
    pub user_address: String,
    pub title: String,
    pub created_at: NaiveDateTime,
    pub last_activity: NaiveDateTime,
    pub expires_at: NaiveDateTime,
    pub message_count: i32,
    pub fees_paid_atoms: i64,
    pub status: String,
    pub context_summary: String,
    pub primary_topic: String,
    pub topics: JsonValue,
}

// ---------------------------------------------------------------------------
// conversation_messages
// ---------------------------------------------------------------------------

/// Row from the `conversation_messages` table.
#[derive(Clone, Debug, Serialize, Deserialize, sqlx::FromRow)]
pub struct ConversationMessageRow {
    pub id: i64,
    pub session_id: uuid::Uuid,
    pub role: String,
    pub content: String,
    pub content_hash: String,
    pub created_at: NaiveDateTime,
    pub reasoning_trace: JsonValue,
    pub phi_at_response: f64,
    pub knowledge_nodes_referenced: JsonValue,
    pub proof_of_thought_hash: String,
    pub quality_score: f64,
    pub intent: String,
    pub entities: JsonValue,
}

// ---------------------------------------------------------------------------
// user_memory
// ---------------------------------------------------------------------------

/// Row from the `user_memory` table.
#[derive(Clone, Debug, Serialize, Deserialize, sqlx::FromRow)]
pub struct UserMemoryRow {
    pub id: i64,
    pub user_id: String,
    pub memory_key: String,
    pub memory_value: String,
    pub created_at: NaiveDateTime,
    pub updated_at: NaiveDateTime,
    pub source: String,
}

// ---------------------------------------------------------------------------
// conversation_insights
// ---------------------------------------------------------------------------

/// Row from the `conversation_insights` table.
#[derive(Clone, Debug, Serialize, Deserialize, sqlx::FromRow)]
pub struct ConversationInsightRow {
    pub id: i64,
    pub session_id: uuid::Uuid,
    pub user_id: String,
    pub insight_type: String,
    pub content: String,
    pub confidence: f64,
    pub knowledge_node_id: Option<i64>,
    pub created_at: NaiveDateTime,
}

// ---------------------------------------------------------------------------
// helpers
// ---------------------------------------------------------------------------

/// Convert a JSONB `serde_json::Value` (expected object) into `HashMap<String, String>`.
fn jsonb_to_hashmap(val: &JsonValue) -> HashMap<String, String> {
    match val {
        JsonValue::Object(map) => map
            .iter()
            .map(|(k, v)| {
                let s = match v {
                    JsonValue::String(s) => s.clone(),
                    other => other.to_string(),
                };
                (k.clone(), s)
            })
            .collect(),
        _ => HashMap::new(),
    }
}

/// Convert `HashMap<String, String>` into a JSONB `serde_json::Value`.
fn hashmap_to_jsonb(map: &HashMap<String, String>) -> JsonValue {
    let obj: serde_json::Map<String, JsonValue> = map
        .iter()
        .map(|(k, v)| (k.clone(), JsonValue::String(v.clone())))
        .collect();
    JsonValue::Object(obj)
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;
    use std::collections::HashMap;

    #[test]
    fn test_jsonb_to_hashmap_object() {
        let val = serde_json::json!({"text": "hello", "count": 42});
        let map = jsonb_to_hashmap(&val);
        assert_eq!(map.get("text").unwrap(), "hello");
        assert_eq!(map.get("count").unwrap(), "42");
    }

    #[test]
    fn test_jsonb_to_hashmap_non_object() {
        let val = serde_json::json!("just a string");
        let map = jsonb_to_hashmap(&val);
        assert!(map.is_empty());
    }

    #[test]
    fn test_hashmap_to_jsonb() {
        let mut map = HashMap::new();
        map.insert("key".into(), "value".into());
        let json = hashmap_to_jsonb(&map);
        assert_eq!(json["key"], "value");
    }

    #[test]
    fn test_keter_node_roundtrip() {
        let mut content = HashMap::new();
        content.insert("text".into(), "quantum physics".into());
        content.insert("subject".into(), "science".into());

        let node = KeterNode::new(
            42,
            "assertion".into(),
            "abc123".into(),
            content,
            0.85,
            100,
            1000.0,
            "keter".into(),
            150,
            3,
            "peer_review".into(),
            vec![1, 2],
            vec![3],
        );

        let row = KnowledgeNodeRow::from_keter_node(&node);
        assert_eq!(row.id, 42);
        assert_eq!(row.node_type, "assertion");
        assert_eq!(row.content_hash, "abc123");
        assert!((row.confidence - 0.85).abs() < f64::EPSILON);
        assert_eq!(row.source_block, 100);
        assert_eq!(row.domain, "keter");
        assert_eq!(row.reference_count, 3);
        assert_eq!(row.last_referenced_block, 150);
        assert_eq!(row.grounding_source, "peer_review");
        assert_eq!(row.search_text, Some("quantum physics".into()));

        // JSONB content preserved
        assert_eq!(row.content["text"], "quantum physics");
        assert_eq!(row.content["subject"], "science");

        // Convert back — edges are lost (graph topology is separate)
        let back = row.into_keter_node();
        assert_eq!(back.node_id, 42);
        assert_eq!(back.node_type, "assertion");
        assert!((back.confidence - 0.85).abs() < f64::EPSILON);
        assert_eq!(back.content.get("text").unwrap(), "quantum physics");
        assert!(back.edges_out.is_empty()); // edges not stored in row
    }

    #[test]
    fn test_keter_edge_roundtrip() {
        let edge = KeterEdge::new(10, 20, "causes".into(), 0.75, 5000.0);

        let row = KnowledgeEdgeRow::from_keter_edge(&edge);
        assert_eq!(row.from_node_id, 10);
        assert_eq!(row.to_node_id, 20);
        assert_eq!(row.edge_type, "causes");
        assert!((row.weight - 0.75).abs() < f64::EPSILON);

        let back = row.into_keter_edge();
        assert_eq!(back.from_node_id, 10);
        assert_eq!(back.to_node_id, 20);
        assert_eq!(back.edge_type, "causes");
        assert!((back.weight - 0.75).abs() < f64::EPSILON);
    }

    #[test]
    fn test_reasoning_operation_row_deserialize() {
        let json = serde_json::json!({
            "id": 1,
            "operation_type": "deduction",
            "premise_nodes": [10, 20, 30],
            "conclusion_node_id": 40,
            "confidence": 0.9,
            "reasoning_chain": {"steps": ["a", "b"]},
            "block_height": 1000,
            "created_at": "2026-01-01T00:00:00"
        });
        let row: ReasoningOperationRow = serde_json::from_value(json).unwrap();
        assert_eq!(row.operation_type, "deduction");
        assert_eq!(row.conclusion_node_id, 40);
        assert!((row.confidence - 0.9).abs() < f64::EPSILON);
    }

    #[test]
    fn test_phi_measurement_row_deserialize() {
        let json = serde_json::json!({
            "id": 1,
            "phi_value": 2.5,
            "phi_threshold": 3.0,
            "integration_score": 0.7,
            "differentiation_score": 0.6,
            "num_nodes": 50000,
            "num_edges": 120000,
            "block_height": 180000,
            "measured_at": "2026-04-01T12:00:00"
        });
        let row: PhiMeasurementRow = serde_json::from_value(json).unwrap();
        assert!((row.phi_value - 2.5).abs() < f64::EPSILON);
        assert_eq!(row.num_nodes, 50000);
    }

    #[test]
    fn test_consciousness_event_row_deserialize() {
        let json = serde_json::json!({
            "id": 1,
            "event_type": "phi_threshold_crossed",
            "phi_at_event": 3.1,
            "trigger_data": {"gate": 6},
            "is_verified": true,
            "block_height": 200000,
            "created_at": "2026-04-10T08:30:00"
        });
        let row: ConsciousnessEventRow = serde_json::from_value(json).unwrap();
        assert_eq!(row.event_type, "phi_threshold_crossed");
        assert!(row.is_verified);
        assert!((row.phi_at_event - 3.1).abs() < f64::EPSILON);
    }
}
