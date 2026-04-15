//! PyO3 bindings for the LogicBridge — exposes FOL reasoning to Python.
//!
//! This module wraps `LogicBridge` behind `#[pyclass]` so that the Python
//! `reasoning.py` can call real first-order logic deduction, backward-chaining
//! proof, abduction, and induction **without any LLM dependency**.

use pyo3::prelude::*;
use pyo3::BoundObject;
use std::collections::HashMap;

use aether_graph::KnowledgeGraph;
use crate::logic_bridge::LogicBridge;

/// Helper: convert a value into a PyObject via IntoPyObject.
fn to_py<'py, T: IntoPyObject<'py>>(py: Python<'py>, val: T) -> PyObject {
    val.into_pyobject(py)
        .map_err(|_| ())
        .expect("IntoPyObject failed")
        .into_any()
        .unbind()
}

/// Python-visible wrapper around the Rust LogicBridge.
///
/// Usage from Python:
/// ```python
/// from aether_core import LogicBridge
/// bridge = LogicBridge()
/// bridge.load_from_graph(knowledge_graph, max_nodes=2000)
/// derived = bridge.deduce(max_steps=50)
/// proof = bridge.prove_relation(42, 99, "causes", max_depth=20)
/// explanations = bridge.explain(42)
/// rules = bridge.generalise([1, 2, 3, 4])
/// ```
#[pyclass(name = "LogicBridge")]
pub struct PyLogicBridge {
    inner: LogicBridge,
}

#[pymethods]
impl PyLogicBridge {
    #[new]
    fn new() -> Self {
        Self {
            inner: LogicBridge::new(),
        }
    }

    /// Load nodes and edges from a KnowledgeGraph into the FOL knowledge base.
    #[pyo3(signature = (kg, max_nodes=None))]
    fn load_from_graph(&mut self, kg: &KnowledgeGraph, max_nodes: Option<usize>) {
        match max_nodes {
            Some(n) => self.inner.load_from_graph_bounded(kg, n),
            None => self.inner.load_from_graph(kg),
        }
    }

    /// Number of FOL facts in the knowledge base.
    fn fact_count(&self) -> usize {
        self.inner.fact_count()
    }

    /// Number of FOL rules in the knowledge base.
    fn rule_count(&self) -> usize {
        self.inner.rule_count()
    }

    /// Run forward chaining (modus ponens) and return newly derived facts.
    ///
    /// Returns a list of dicts with keys: description, source_node_ids.
    #[pyo3(signature = (max_steps=50))]
    fn deduce(&mut self, max_steps: usize) -> Vec<HashMap<String, PyObject>> {
        let derived = self.inner.deduce(max_steps);
        Python::with_gil(|py| {
            derived
                .into_iter()
                .map(|d| {
                    let mut m = HashMap::new();
                    m.insert("description".into(), to_py(py, d.description));
                    m.insert("source_node_ids".into(), to_py(py, d.source_node_ids));
                    m
                })
                .collect()
        })
    }

    /// Run forward chaining starting from specific premise node IDs.
    #[pyo3(signature = (premise_node_ids, max_steps=50))]
    fn deduce_from(
        &mut self,
        premise_node_ids: Vec<i64>,
        max_steps: usize,
    ) -> Vec<HashMap<String, PyObject>> {
        let derived = self.inner.deduce_from(&premise_node_ids, max_steps);
        Python::with_gil(|py| {
            derived
                .into_iter()
                .map(|d| {
                    let mut m = HashMap::new();
                    m.insert("description".into(), to_py(py, d.description));
                    m.insert("source_node_ids".into(), to_py(py, d.source_node_ids));
                    m
                })
                .collect()
        })
    }

    /// Try to prove a relationship between two nodes via backward chaining.
    ///
    /// Returns a dict with keys: proved (bool), summary (str).
    #[pyo3(signature = (from_node_id, to_node_id, relation, max_depth=20))]
    fn prove_relation(
        &self,
        from_node_id: i64,
        to_node_id: i64,
        relation: &str,
        max_depth: usize,
    ) -> HashMap<String, PyObject> {
        let result = self.inner.prove_relation(from_node_id, to_node_id, relation, max_depth);
        Python::with_gil(|py| {
            let mut m = HashMap::new();
            m.insert("proved".into(), to_py(py, result.proved));
            m.insert("summary".into(), to_py(py, result.summary));
            m
        })
    }

    /// Generate abductive explanations for an observed node.
    ///
    /// Returns a list of dicts with keys: description, score, also_explains_count.
    fn explain(&self, observation_node_id: i64) -> Vec<HashMap<String, PyObject>> {
        let explanations = self.inner.explain(observation_node_id);
        Python::with_gil(|py| {
            explanations
                .into_iter()
                .map(|e| {
                    let mut m = HashMap::new();
                    m.insert("description".into(), to_py(py, e.description));
                    m.insert("score".into(), to_py(py, e.score));
                    m.insert("also_explains_count".into(), to_py(py, e.also_explains.len()));
                    m
                })
                .collect()
        })
    }

    /// Generalise from a set of example node IDs via inductive reasoning.
    ///
    /// Returns a list of dicts with keys: description, coverage, total_examples.
    fn generalise(&self, example_node_ids: Vec<i64>) -> Vec<HashMap<String, PyObject>> {
        let rules = self.inner.generalise(&example_node_ids);
        Python::with_gil(|py| {
            rules
                .into_iter()
                .map(|r| {
                    let mut m = HashMap::new();
                    m.insert("description".into(), to_py(py, r.description));
                    m.insert("coverage".into(), to_py(py, r.coverage));
                    m.insert("total_examples".into(), to_py(py, r.total_examples));
                    m
                })
                .collect()
        })
    }

    /// Summary stats of the knowledge base.
    fn stats(&self) -> HashMap<String, usize> {
        let mut m = HashMap::new();
        m.insert("facts".into(), self.inner.fact_count());
        m.insert("rules".into(), self.inner.rule_count());
        m.insert("nodes_loaded".into(), self.inner.knowledge_base().facts.len());
        m
    }
}
