//! Knowledge base with forward and backward chaining.
//!
//! The `KnowledgeBase` stores ground facts and implication rules, and provides
//! two inference strategies:
//!
//! - **Forward chaining** (data-driven): repeatedly apply rules to known facts
//!   to derive new conclusions until a fixpoint or step limit is reached.
//!
//! - **Backward chaining** (goal-driven): given a goal formula, search for a
//!   proof by recursively matching against facts and rule consequents. This is
//!   essentially SLD resolution (the strategy used by Prolog).
//!
//! Every derivation produces an auditable `Proof` tree.

use crate::formula::Formula;
use crate::inference;
use crate::unify::{self, Substitution};
use rustc_hash::FxHashSet;
use serde::{Deserialize, Serialize};
use std::fmt;
use tracing::trace;

/// The inference rule used in a proof step.
#[derive(Clone, Debug, Serialize, Deserialize)]
pub enum InferenceRule {
    /// Direct fact lookup (axiom).
    Axiom,
    /// Modus ponens: P, (P -> Q) |- Q.
    ModusPonens,
    /// Modus tollens: ~Q, (P -> Q) |- ~P.
    ModusTollens,
    /// Universal instantiation: forall X. P(X) |- P(t).
    UniversalInstantiation,
    /// Resolution: complementary literal elimination.
    Resolution,
    /// Hypothetical syllogism: (A->B), (B->C) |- (A->C).
    HypotheticalSyllogism,
}

impl fmt::Display for InferenceRule {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            InferenceRule::Axiom => write!(f, "axiom"),
            InferenceRule::ModusPonens => write!(f, "modus_ponens"),
            InferenceRule::ModusTollens => write!(f, "modus_tollens"),
            InferenceRule::UniversalInstantiation => write!(f, "universal_instantiation"),
            InferenceRule::Resolution => write!(f, "resolution"),
            InferenceRule::HypotheticalSyllogism => write!(f, "hypothetical_syllogism"),
        }
    }
}

/// A single step in a proof tree.
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct ProofStep {
    /// The conclusion derived at this step.
    pub conclusion: Formula,
    /// The inference rule used.
    pub rule: InferenceRule,
    /// The sub-proofs for the premises of this step.
    pub premises: Vec<ProofStep>,
}

impl ProofStep {
    /// Create a leaf proof step (axiom / direct fact).
    pub fn axiom(fact: Formula) -> Self {
        Self {
            conclusion: fact,
            rule: InferenceRule::Axiom,
            premises: Vec::new(),
        }
    }

    /// Create a derived proof step.
    pub fn derived(conclusion: Formula, rule: InferenceRule, premises: Vec<ProofStep>) -> Self {
        Self {
            conclusion,
            rule,
            premises,
        }
    }

    /// Depth of this proof tree.
    pub fn depth(&self) -> usize {
        if self.premises.is_empty() {
            0
        } else {
            1 + self.premises.iter().map(|p| p.depth()).max().unwrap_or(0)
        }
    }

    /// Total number of steps in this proof tree.
    pub fn size(&self) -> usize {
        1 + self.premises.iter().map(|p| p.size()).sum::<usize>()
    }
}

/// A complete proof (wrapper around the root ProofStep).
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Proof {
    pub root: ProofStep,
    pub substitution: Substitution,
}

/// A knowledge base containing facts and rules for logical inference.
#[derive(Clone, Debug, Default)]
pub struct KnowledgeBase {
    /// Ground facts (atoms without free variables, or atoms with universally
    /// quantified variables treated as facts).
    pub facts: Vec<Formula>,
    /// Implication rules: each is `(antecedent -> consequent)`.
    pub rules: Vec<Formula>,
}

impl KnowledgeBase {
    /// Create a new empty knowledge base.
    pub fn new() -> Self {
        Self::default()
    }

    /// Add a ground fact.
    pub fn add_fact(&mut self, fact: Formula) {
        self.facts.push(fact);
    }

    /// Add an implication rule (must be `Implies`).
    pub fn add_rule(&mut self, rule: Formula) {
        debug_assert!(rule.is_implication(), "add_rule expects an implication");
        self.rules.push(rule);
    }

    /// Number of facts.
    pub fn fact_count(&self) -> usize {
        self.facts.len()
    }

    /// Number of rules.
    pub fn rule_count(&self) -> usize {
        self.rules.len()
    }

    // -----------------------------------------------------------------------
    // Forward Chaining
    // -----------------------------------------------------------------------

    /// Forward chaining: repeatedly apply modus ponens with all facts and rules
    /// until no new facts are derived or `max_steps` iterations are exhausted.
    ///
    /// Returns the list of **newly derived** facts (not the original facts).
    pub fn forward_chain(&mut self, max_steps: usize) -> Vec<Formula> {
        let mut new_facts: Vec<Formula> = Vec::new();
        let mut seen: FxHashSet<u64> = FxHashSet::default();

        // Hash existing facts for dedup.
        for f in &self.facts {
            seen.insert(formula_hash(f));
        }

        for step in 0..max_steps {
            let mut derived_this_step = Vec::new();

            // For each rule, try modus ponens against every known fact.
            for rule in &self.rules {
                // We need all facts including newly derived ones.
                let all_facts: Vec<Formula> = self
                    .facts
                    .iter()
                    .chain(new_facts.iter())
                    .cloned()
                    .collect();

                for fact in &all_facts {
                    if let Some(derivation) = inference::modus_ponens(fact, rule) {
                        let h = formula_hash(&derivation.conclusion);
                        if !seen.contains(&h) {
                            seen.insert(h);
                            trace!(
                                step,
                                rule = "modus_ponens",
                                "Forward chain derived: {:?}",
                                derivation.conclusion
                            );
                            derived_this_step.push(derivation.conclusion);
                        }
                    }
                }
            }

            if derived_this_step.is_empty() {
                trace!(step, "Forward chain reached fixpoint");
                break;
            }

            new_facts.extend(derived_this_step);
        }

        // Add all new facts to the KB.
        self.facts.extend(new_facts.clone());
        new_facts
    }

    // -----------------------------------------------------------------------
    // Backward Chaining
    // -----------------------------------------------------------------------

    /// Backward chaining: try to prove `goal` from facts and rules.
    ///
    /// Uses depth-limited SLD resolution:
    /// 1. If goal unifies with a known fact, succeed (axiom).
    /// 2. If goal unifies with the consequent of a rule, try to prove the antecedent.
    /// 3. Recursion is bounded by `max_depth` to prevent infinite loops.
    ///
    /// Returns a `Proof` if the goal can be proven, `None` otherwise.
    pub fn backward_chain(&self, goal: &Formula, max_depth: usize) -> Option<Proof> {
        let mut visited = FxHashSet::default();
        self.backward_chain_inner(goal, max_depth, &mut visited)
    }

    fn backward_chain_inner(
        &self,
        goal: &Formula,
        depth: usize,
        visited: &mut FxHashSet<u64>,
    ) -> Option<Proof> {
        if depth == 0 {
            return None;
        }

        let goal_hash = formula_hash(goal);
        if visited.contains(&goal_hash) {
            return None; // Cycle detection
        }
        visited.insert(goal_hash);

        // 1. Try to unify goal with a known fact.
        for fact in &self.facts {
            if let Some(sub) = unify::unify_atoms(goal, fact) {
                visited.remove(&goal_hash);
                return Some(Proof {
                    root: ProofStep::axiom(fact.clone()),
                    substitution: sub,
                });
            }
        }

        // 2. Try each rule whose consequent unifies with the goal.
        for rule in &self.rules {
            if let Formula::Implies(antecedent, consequent) = rule {
                if let Some(sub) = unify::unify_atoms(goal, consequent) {
                    // We need to prove the antecedent (with substitution applied).
                    let subgoal = antecedent.substitute(&sub);

                    // Handle conjunction in antecedent: prove each conjunct.
                    let subgoals = match &subgoal {
                        Formula::And(conjuncts) => conjuncts.clone(),
                        other => vec![other.clone()],
                    };

                    let mut premise_proofs = Vec::new();
                    let mut combined_sub = sub.clone();
                    let mut all_proved = true;

                    for sg in &subgoals {
                        let sg_applied = sg.substitute(&combined_sub);
                        if let Some(sub_proof) =
                            self.backward_chain_inner(&sg_applied, depth - 1, visited)
                        {
                            combined_sub =
                                unify::compose(&combined_sub, &sub_proof.substitution);
                            premise_proofs.push(sub_proof.root);
                        } else {
                            all_proved = false;
                            break;
                        }
                    }

                    if all_proved {
                        visited.remove(&goal_hash);
                        let conclusion = goal.substitute(&combined_sub);
                        return Some(Proof {
                            root: ProofStep::derived(
                                conclusion,
                                InferenceRule::ModusPonens,
                                premise_proofs,
                            ),
                            substitution: combined_sub,
                        });
                    }
                }
            }
        }

        visited.remove(&goal_hash);
        None
    }
}

/// Simple hash for formula deduplication (not cryptographic).
fn formula_hash(f: &Formula) -> u64 {
    use std::collections::hash_map::DefaultHasher;
    use std::hash::{Hash, Hasher};
    let mut hasher = DefaultHasher::new();
    f.hash(&mut hasher);
    hasher.finish()
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;
    use crate::term::{Symbol, Term};

    fn sym(id: u32) -> Symbol {
        Symbol(id)
    }

    /// Build a KB for: parent(alice, bob), parent(bob, carol),
    /// parent(X, Y) -> ancestor(X, Y),
    /// parent(X, Z) & ancestor(Z, Y) -> ancestor(X, Y)
    fn family_kb() -> KnowledgeBase {
        let parent = sym(0);
        let ancestor = sym(1);
        let alice = sym(10);
        let bob = sym(11);
        let carol = sym(12);

        let mut kb = KnowledgeBase::new();

        // Facts
        kb.add_fact(Formula::atom(
            parent,
            vec![Term::Constant(alice), Term::Constant(bob)],
        ));
        kb.add_fact(Formula::atom(
            parent,
            vec![Term::Constant(bob), Term::Constant(carol)],
        ));

        // Rule 1: parent(X, Y) -> ancestor(X, Y)
        kb.add_rule(Formula::implies(
            Formula::atom(parent, vec![Term::var(0), Term::var(1)]),
            Formula::atom(ancestor, vec![Term::var(0), Term::var(1)]),
        ));

        kb
    }

    #[test]
    fn test_forward_chain_derives_ancestors() {
        let mut kb = family_kb();
        assert_eq!(kb.fact_count(), 2);

        let new = kb.forward_chain(10);
        // Should derive: ancestor(alice, bob) and ancestor(bob, carol)
        assert!(new.len() >= 2, "Expected at least 2 new facts, got {}", new.len());
        assert!(kb.fact_count() >= 4);
    }

    #[test]
    fn test_forward_chain_fixpoint() {
        let mut kb = family_kb();
        let _round1 = kb.forward_chain(100);
        let count_after_1 = kb.fact_count();

        // Running again should produce no new facts (fixpoint).
        let round2 = kb.forward_chain(100);
        assert!(round2.is_empty(), "Expected fixpoint, but got {} new facts", round2.len());
        assert_eq!(kb.fact_count(), count_after_1);
    }

    #[test]
    fn test_backward_chain_direct_fact() {
        let kb = family_kb();
        let parent = sym(0);
        let alice = sym(10);
        let bob = sym(11);

        // parent(alice, bob) is a direct fact
        let goal = Formula::atom(parent, vec![Term::Constant(alice), Term::Constant(bob)]);
        let proof = kb.backward_chain(&goal, 10).unwrap();
        assert!(matches!(proof.root.rule, InferenceRule::Axiom));
        assert_eq!(proof.root.depth(), 0);
    }

    #[test]
    fn test_backward_chain_one_step_rule() {
        let kb = family_kb();
        let ancestor = sym(1);
        let alice = sym(10);
        let bob = sym(11);

        // ancestor(alice, bob) requires: parent(alice, bob) -> ancestor(alice, bob)
        let goal = Formula::atom(
            ancestor,
            vec![Term::Constant(alice), Term::Constant(bob)],
        );
        let proof = kb.backward_chain(&goal, 10).unwrap();
        assert!(matches!(proof.root.rule, InferenceRule::ModusPonens));
        assert!(proof.root.depth() >= 1);
    }

    #[test]
    fn test_backward_chain_unprovable() {
        let kb = family_kb();
        let ancestor = sym(1);
        let carol = sym(12);
        let alice = sym(10);

        // ancestor(carol, alice) is NOT derivable
        let goal = Formula::atom(
            ancestor,
            vec![Term::Constant(carol), Term::Constant(alice)],
        );
        assert!(kb.backward_chain(&goal, 10).is_none());
    }

    #[test]
    fn test_backward_chain_depth_limit() {
        let kb = family_kb();
        let ancestor = sym(1);
        let alice = sym(10);
        let bob = sym(11);

        // With depth 0, nothing should be provable.
        let goal = Formula::atom(
            ancestor,
            vec![Term::Constant(alice), Term::Constant(bob)],
        );
        assert!(kb.backward_chain(&goal, 0).is_none());

        // With depth 1, the direct fact lookup works but not the rule step.
        // parent(alice, bob) at depth 1 should work.
        let parent = sym(0);
        let direct = Formula::atom(parent, vec![Term::Constant(alice), Term::Constant(bob)]);
        assert!(kb.backward_chain(&direct, 1).is_some());
    }

    #[test]
    fn test_proof_size_and_depth() {
        let kb = family_kb();
        let ancestor = sym(1);
        let alice = sym(10);
        let bob = sym(11);

        let goal = Formula::atom(
            ancestor,
            vec![Term::Constant(alice), Term::Constant(bob)],
        );
        let proof = kb.backward_chain(&goal, 10).unwrap();
        assert!(proof.root.size() >= 2); // At least root + 1 premise
        assert!(proof.root.depth() >= 1);
    }

    #[test]
    fn test_forward_chain_with_variable_query() {
        let mut kb = family_kb();
        kb.forward_chain(10);

        // After forward chaining, ancestor(X, Y) with X=alice should exist
        let ancestor = sym(1);
        let alice = sym(10);

        // Try to find ancestor(alice, ?)
        let goal = Formula::atom(ancestor, vec![Term::Constant(alice), Term::var(99)]);
        let proof = kb.backward_chain(&goal, 5);
        assert!(proof.is_some(), "Should find ancestor(alice, ?) after forward chaining");
    }
}
