//! Domain enums for the Aether Tree AI engine.
//!
//! All enums carry serde + PyO3 derives and implement Display/FromStr for
//! round-tripping through JSON, SQL, and Python boundaries.

use pyo3::prelude::*;
use serde::{Deserialize, Serialize};
use std::fmt;
use std::str::FromStr;

// ---------------------------------------------------------------------------
// NodeType
// ---------------------------------------------------------------------------

/// The type of a knowledge node in the Aether Tree.
#[pyclass(eq)]
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum NodeType {
    Assertion,
    Observation,
    Inference,
    Axiom,
    Prediction,
    MetaObservation,
}

impl fmt::Display for NodeType {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        let s = match self {
            Self::Assertion => "assertion",
            Self::Observation => "observation",
            Self::Inference => "inference",
            Self::Axiom => "axiom",
            Self::Prediction => "prediction",
            Self::MetaObservation => "meta_observation",
        };
        write!(f, "{}", s)
    }
}

impl FromStr for NodeType {
    type Err = String;

    fn from_str(s: &str) -> Result<Self, Self::Err> {
        match s {
            "assertion" => Ok(Self::Assertion),
            "observation" => Ok(Self::Observation),
            "inference" => Ok(Self::Inference),
            "axiom" => Ok(Self::Axiom),
            "prediction" => Ok(Self::Prediction),
            "meta_observation" => Ok(Self::MetaObservation),
            other => Err(format!("unknown NodeType: '{}'", other)),
        }
    }
}

#[pymethods]
impl NodeType {
    /// Return the lowercase string representation (DB-compatible).
    pub fn as_str(&self) -> &'static str {
        match self {
            Self::Assertion => "assertion",
            Self::Observation => "observation",
            Self::Inference => "inference",
            Self::Axiom => "axiom",
            Self::Prediction => "prediction",
            Self::MetaObservation => "meta_observation",
        }
    }

    /// Parse from a string.
    #[staticmethod]
    pub fn from_string(s: &str) -> PyResult<Self> {
        Self::from_str(s).map_err(pyo3::exceptions::PyValueError::new_err)
    }

    fn __repr__(&self) -> String {
        format!("NodeType.{}", self.as_str())
    }

    fn __str__(&self) -> String {
        self.to_string()
    }

    /// Return all variants as a list of strings.
    #[staticmethod]
    pub fn variants() -> Vec<&'static str> {
        vec![
            "assertion",
            "observation",
            "inference",
            "axiom",
            "prediction",
            "meta_observation",
        ]
    }
}

// ---------------------------------------------------------------------------
// EdgeType
// ---------------------------------------------------------------------------

/// The type of a directed edge between knowledge nodes.
#[pyclass(eq)]
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum EdgeType {
    Supports,
    Contradicts,
    Derives,
    Requires,
    Refines,
    Causes,
    Abstracts,
    AnalogousTo,
}

impl fmt::Display for EdgeType {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{}", self.as_str())
    }
}

impl FromStr for EdgeType {
    type Err = String;

    fn from_str(s: &str) -> Result<Self, Self::Err> {
        match s {
            "supports" => Ok(Self::Supports),
            "contradicts" => Ok(Self::Contradicts),
            "derives" => Ok(Self::Derives),
            "requires" => Ok(Self::Requires),
            "refines" => Ok(Self::Refines),
            "causes" => Ok(Self::Causes),
            "abstracts" => Ok(Self::Abstracts),
            "analogous_to" => Ok(Self::AnalogousTo),
            other => Err(format!("unknown EdgeType: '{}'", other)),
        }
    }
}

#[pymethods]
impl EdgeType {
    /// Return the lowercase string representation (DB-compatible).
    pub fn as_str(&self) -> &'static str {
        match self {
            Self::Supports => "supports",
            Self::Contradicts => "contradicts",
            Self::Derives => "derives",
            Self::Requires => "requires",
            Self::Refines => "refines",
            Self::Causes => "causes",
            Self::Abstracts => "abstracts",
            Self::AnalogousTo => "analogous_to",
        }
    }

    #[staticmethod]
    pub fn from_string(s: &str) -> PyResult<Self> {
        Self::from_str(s).map_err(pyo3::exceptions::PyValueError::new_err)
    }

    fn __repr__(&self) -> String {
        format!("EdgeType.{}", self.as_str())
    }

    fn __str__(&self) -> String {
        self.to_string()
    }

    #[staticmethod]
    pub fn variants() -> Vec<&'static str> {
        vec![
            "supports",
            "contradicts",
            "derives",
            "requires",
            "refines",
            "causes",
            "abstracts",
            "analogous_to",
        ]
    }
}

// ---------------------------------------------------------------------------
// Domain (Sephirot)
// ---------------------------------------------------------------------------

/// The 10 Sephirot cognitive domains.
#[pyclass(eq)]
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Domain {
    Keter,
    Chochmah,
    Binah,
    Chesed,
    Gevurah,
    Tiferet,
    Netzach,
    Hod,
    Yesod,
    Malkuth,
}

impl fmt::Display for Domain {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{}", self.as_str())
    }
}

impl FromStr for Domain {
    type Err = String;

    fn from_str(s: &str) -> Result<Self, Self::Err> {
        match s {
            "keter" => Ok(Self::Keter),
            "chochmah" => Ok(Self::Chochmah),
            "binah" => Ok(Self::Binah),
            "chesed" => Ok(Self::Chesed),
            "gevurah" => Ok(Self::Gevurah),
            "tiferet" => Ok(Self::Tiferet),
            "netzach" => Ok(Self::Netzach),
            "hod" => Ok(Self::Hod),
            "yesod" => Ok(Self::Yesod),
            "malkuth" => Ok(Self::Malkuth),
            other => Err(format!("unknown Domain: '{}'", other)),
        }
    }
}

#[pymethods]
impl Domain {
    pub fn as_str(&self) -> &'static str {
        match self {
            Self::Keter => "keter",
            Self::Chochmah => "chochmah",
            Self::Binah => "binah",
            Self::Chesed => "chesed",
            Self::Gevurah => "gevurah",
            Self::Tiferet => "tiferet",
            Self::Netzach => "netzach",
            Self::Hod => "hod",
            Self::Yesod => "yesod",
            Self::Malkuth => "malkuth",
        }
    }

    #[staticmethod]
    pub fn from_string(s: &str) -> PyResult<Self> {
        Self::from_str(s).map_err(pyo3::exceptions::PyValueError::new_err)
    }

    fn __repr__(&self) -> String {
        format!("Domain.{}", self.as_str())
    }

    fn __str__(&self) -> String {
        self.to_string()
    }

    #[staticmethod]
    pub fn variants() -> Vec<&'static str> {
        vec![
            "keter", "chochmah", "binah", "chesed", "gevurah",
            "tiferet", "netzach", "hod", "yesod", "malkuth",
        ]
    }
}

// ---------------------------------------------------------------------------
// ReasoningStrategy
// ---------------------------------------------------------------------------

/// Reasoning strategies available to the Aether engine.
#[pyclass(eq)]
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ReasoningStrategy {
    Deduction,
    Induction,
    Abduction,
    ChainOfThought,
    Analogy,
    ContradictionResolution,
}

impl fmt::Display for ReasoningStrategy {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{}", self.as_str())
    }
}

impl FromStr for ReasoningStrategy {
    type Err = String;

    fn from_str(s: &str) -> Result<Self, Self::Err> {
        match s {
            "deduction" => Ok(Self::Deduction),
            "induction" => Ok(Self::Induction),
            "abduction" => Ok(Self::Abduction),
            "chain_of_thought" => Ok(Self::ChainOfThought),
            "analogy" => Ok(Self::Analogy),
            "contradiction_resolution" => Ok(Self::ContradictionResolution),
            other => Err(format!("unknown ReasoningStrategy: '{}'", other)),
        }
    }
}

#[pymethods]
impl ReasoningStrategy {
    pub fn as_str(&self) -> &'static str {
        match self {
            Self::Deduction => "deduction",
            Self::Induction => "induction",
            Self::Abduction => "abduction",
            Self::ChainOfThought => "chain_of_thought",
            Self::Analogy => "analogy",
            Self::ContradictionResolution => "contradiction_resolution",
        }
    }

    #[staticmethod]
    pub fn from_string(s: &str) -> PyResult<Self> {
        Self::from_str(s).map_err(pyo3::exceptions::PyValueError::new_err)
    }

    fn __repr__(&self) -> String {
        format!("ReasoningStrategy.{}", self.as_str())
    }

    fn __str__(&self) -> String {
        self.to_string()
    }

    #[staticmethod]
    pub fn variants() -> Vec<&'static str> {
        vec![
            "deduction",
            "induction",
            "abduction",
            "chain_of_thought",
            "analogy",
            "contradiction_resolution",
        ]
    }
}

// ---------------------------------------------------------------------------
// ConsciousnessEventType
// ---------------------------------------------------------------------------

/// Types of consciousness events tracked by the Aether Tree.
#[pyclass(eq)]
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ConsciousnessEventType {
    PhiThresholdCrossed,
    ContradictionResolved,
    SelfReflection,
    Genesis,
}

impl fmt::Display for ConsciousnessEventType {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{}", self.as_str())
    }
}

impl FromStr for ConsciousnessEventType {
    type Err = String;

    fn from_str(s: &str) -> Result<Self, Self::Err> {
        match s {
            "phi_threshold_crossed" => Ok(Self::PhiThresholdCrossed),
            "contradiction_resolved" => Ok(Self::ContradictionResolved),
            "self_reflection" => Ok(Self::SelfReflection),
            "genesis" => Ok(Self::Genesis),
            other => Err(format!("unknown ConsciousnessEventType: '{}'", other)),
        }
    }
}

#[pymethods]
impl ConsciousnessEventType {
    pub fn as_str(&self) -> &'static str {
        match self {
            Self::PhiThresholdCrossed => "phi_threshold_crossed",
            Self::ContradictionResolved => "contradiction_resolved",
            Self::SelfReflection => "self_reflection",
            Self::Genesis => "genesis",
        }
    }

    #[staticmethod]
    pub fn from_string(s: &str) -> PyResult<Self> {
        Self::from_str(s).map_err(pyo3::exceptions::PyValueError::new_err)
    }

    fn __repr__(&self) -> String {
        format!("ConsciousnessEventType.{}", self.as_str())
    }

    fn __str__(&self) -> String {
        self.to_string()
    }

    #[staticmethod]
    pub fn variants() -> Vec<&'static str> {
        vec![
            "phi_threshold_crossed",
            "contradiction_resolved",
            "self_reflection",
            "genesis",
        ]
    }
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;

    // -- NodeType ---------------------------------------------------------

    #[test]
    fn test_node_type_display_roundtrip() {
        for variant in &[
            NodeType::Assertion,
            NodeType::Observation,
            NodeType::Inference,
            NodeType::Axiom,
            NodeType::Prediction,
            NodeType::MetaObservation,
        ] {
            let s = variant.to_string();
            let parsed: NodeType = s.parse().unwrap();
            assert_eq!(*variant, parsed);
        }
    }

    #[test]
    fn test_node_type_serde_roundtrip() {
        let val = NodeType::MetaObservation;
        let json = serde_json::to_string(&val).unwrap();
        assert_eq!(json, "\"meta_observation\"");
        let back: NodeType = serde_json::from_str(&json).unwrap();
        assert_eq!(back, val);
    }

    #[test]
    fn test_node_type_from_str_error() {
        let result = NodeType::from_str("invalid");
        assert!(result.is_err());
        assert!(result.unwrap_err().contains("unknown NodeType"));
    }

    #[test]
    fn test_node_type_variants_count() {
        assert_eq!(NodeType::variants().len(), 6);
    }

    // -- EdgeType ---------------------------------------------------------

    #[test]
    fn test_edge_type_display_roundtrip() {
        for variant in &[
            EdgeType::Supports,
            EdgeType::Contradicts,
            EdgeType::Derives,
            EdgeType::Requires,
            EdgeType::Refines,
            EdgeType::Causes,
            EdgeType::Abstracts,
            EdgeType::AnalogousTo,
        ] {
            let s = variant.to_string();
            let parsed: EdgeType = s.parse().unwrap();
            assert_eq!(*variant, parsed);
        }
    }

    #[test]
    fn test_edge_type_serde_roundtrip() {
        let val = EdgeType::AnalogousTo;
        let json = serde_json::to_string(&val).unwrap();
        assert_eq!(json, "\"analogous_to\"");
        let back: EdgeType = serde_json::from_str(&json).unwrap();
        assert_eq!(back, val);
    }

    #[test]
    fn test_edge_type_variants_count() {
        assert_eq!(EdgeType::variants().len(), 8);
    }

    // -- Domain -----------------------------------------------------------

    #[test]
    fn test_domain_display_roundtrip() {
        for variant in &[
            Domain::Keter,
            Domain::Chochmah,
            Domain::Binah,
            Domain::Chesed,
            Domain::Gevurah,
            Domain::Tiferet,
            Domain::Netzach,
            Domain::Hod,
            Domain::Yesod,
            Domain::Malkuth,
        ] {
            let s = variant.to_string();
            let parsed: Domain = s.parse().unwrap();
            assert_eq!(*variant, parsed);
        }
    }

    #[test]
    fn test_domain_serde_roundtrip() {
        let val = Domain::Tiferet;
        let json = serde_json::to_string(&val).unwrap();
        assert_eq!(json, "\"tiferet\"");
        let back: Domain = serde_json::from_str(&json).unwrap();
        assert_eq!(back, val);
    }

    #[test]
    fn test_domain_variants_count() {
        assert_eq!(Domain::variants().len(), 10);
    }

    // -- ReasoningStrategy ------------------------------------------------

    #[test]
    fn test_reasoning_strategy_display_roundtrip() {
        for variant in &[
            ReasoningStrategy::Deduction,
            ReasoningStrategy::Induction,
            ReasoningStrategy::Abduction,
            ReasoningStrategy::ChainOfThought,
            ReasoningStrategy::Analogy,
            ReasoningStrategy::ContradictionResolution,
        ] {
            let s = variant.to_string();
            let parsed: ReasoningStrategy = s.parse().unwrap();
            assert_eq!(*variant, parsed);
        }
    }

    #[test]
    fn test_reasoning_strategy_serde_roundtrip() {
        let val = ReasoningStrategy::ChainOfThought;
        let json = serde_json::to_string(&val).unwrap();
        assert_eq!(json, "\"chain_of_thought\"");
        let back: ReasoningStrategy = serde_json::from_str(&json).unwrap();
        assert_eq!(back, val);
    }

    #[test]
    fn test_reasoning_strategy_variants_count() {
        assert_eq!(ReasoningStrategy::variants().len(), 6);
    }

    // -- ConsciousnessEventType -------------------------------------------

    #[test]
    fn test_consciousness_event_type_display_roundtrip() {
        for variant in &[
            ConsciousnessEventType::PhiThresholdCrossed,
            ConsciousnessEventType::ContradictionResolved,
            ConsciousnessEventType::SelfReflection,
            ConsciousnessEventType::Genesis,
        ] {
            let s = variant.to_string();
            let parsed: ConsciousnessEventType = s.parse().unwrap();
            assert_eq!(*variant, parsed);
        }
    }

    #[test]
    fn test_consciousness_event_type_serde_roundtrip() {
        let val = ConsciousnessEventType::PhiThresholdCrossed;
        let json = serde_json::to_string(&val).unwrap();
        assert_eq!(json, "\"phi_threshold_crossed\"");
        let back: ConsciousnessEventType = serde_json::from_str(&json).unwrap();
        assert_eq!(back, val);
    }

    #[test]
    fn test_consciousness_event_type_variants_count() {
        assert_eq!(ConsciousnessEventType::variants().len(), 4);
    }

    // -- Cross-enum tests ------------------------------------------------

    #[test]
    fn test_all_enums_are_copy() {
        let n = NodeType::Axiom;
        let n2 = n; // Copy
        assert_eq!(n, n2);

        let e = EdgeType::Causes;
        let e2 = e;
        assert_eq!(e, e2);

        let d = Domain::Keter;
        let d2 = d;
        assert_eq!(d, d2);
    }

    #[test]
    fn test_as_str_matches_display() {
        assert_eq!(NodeType::Prediction.as_str(), &NodeType::Prediction.to_string());
        assert_eq!(EdgeType::Refines.as_str(), &EdgeType::Refines.to_string());
        assert_eq!(Domain::Yesod.as_str(), &Domain::Yesod.to_string());
        assert_eq!(
            ReasoningStrategy::Abduction.as_str(),
            &ReasoningStrategy::Abduction.to_string()
        );
        assert_eq!(
            ConsciousnessEventType::Genesis.as_str(),
            &ConsciousnessEventType::Genesis.to_string()
        );
    }
}
