//! Inductive generalization via anti-unification.
//!
//! Given a set of specific examples (ground formulas), induction finds the
//! **least general generalization (LGG)** -- the most specific formula that
//! still covers all examples. This is the dual of unification: where unification
//! finds the most general specialization, anti-unification finds the most
//! specific generalization.
//!
//! Example:
//!   Input:  parent(alice, bob), parent(alice, carol)
//!   Output: forall X. parent(alice, X)   -- alice is a parent of someone

use crate::formula::Formula;
use crate::term::{Symbol, Term};
use rustc_hash::FxHashMap;
use serde::{Deserialize, Serialize};
use std::sync::atomic::{AtomicU32, Ordering};

/// Counter for generating fresh variable IDs during anti-unification.
static FRESH_VAR_COUNTER: AtomicU32 = AtomicU32::new(10_000);

fn fresh_var() -> u32 {
    FRESH_VAR_COUNTER.fetch_add(1, Ordering::Relaxed)
}

/// A generalization produced by inductive reasoning.
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Generalization {
    /// The generalized formula (universally quantified over introduced variables).
    pub formula: Formula,
    /// How many of the input examples this generalization covers.
    pub coverage: usize,
    /// Total examples provided.
    pub total_examples: usize,
    /// The variable mappings: for each introduced variable, what concrete terms
    /// it replaces across the examples.
    pub variable_instances: FxHashMap<u32, Vec<Term>>,
}

/// Anti-unify two terms: find their least general generalization.
///
/// Returns the generalized term and a mapping from each introduced variable
/// to the pair of concrete terms it replaces.
///
/// Algorithm:
/// - If both are identical, return the term as-is.
/// - If both are compounds with the same functor and arity, anti-unify arguments.
/// - Otherwise, introduce a fresh variable.
pub fn anti_unify(t1: &Term, t2: &Term) -> (Term, FxHashMap<u32, Vec<Term>>) {
    let mut var_map = FxHashMap::default();
    let mut memo: FxHashMap<(u64, u64), u32> = FxHashMap::default();
    let result = anti_unify_inner(t1, t2, &mut var_map, &mut memo);
    (result, var_map)
}

fn anti_unify_inner(
    t1: &Term,
    t2: &Term,
    var_map: &mut FxHashMap<u32, Vec<Term>>,
    memo: &mut FxHashMap<(u64, u64), u32>,
) -> Term {
    // If identical, return as-is.
    if t1 == t2 {
        return t1.clone();
    }

    // Both compounds with same functor and arity: recurse on arguments.
    if let (Term::Compound(f1, args1), Term::Compound(f2, args2)) = (t1, t2) {
        if f1 == f2 && args1.len() == args2.len() {
            let new_args: Vec<Term> = args1
                .iter()
                .zip(args2.iter())
                .map(|(a1, a2)| anti_unify_inner(a1, a2, var_map, memo))
                .collect();
            return Term::Compound(*f1, new_args);
        }
    }

    // Check memo to reuse the same variable for the same pair of terms.
    let key = (term_hash(t1), term_hash(t2));
    if let Some(&var_id) = memo.get(&key) {
        return Term::Variable(var_id);
    }

    // Introduce a fresh variable for this disagreement.
    let var_id = fresh_var();
    memo.insert(key, var_id);
    var_map.insert(var_id, vec![t1.clone(), t2.clone()]);
    Term::Variable(var_id)
}

/// Anti-unify two atomic formulas.
///
/// Both must have the same predicate symbol and arity. Returns the generalized
/// atom and the variable mapping.
fn anti_unify_atoms(
    f1: &Formula,
    f2: &Formula,
) -> Option<(Formula, FxHashMap<u32, Vec<Term>>)> {
    match (f1, f2) {
        (Formula::Atom(p1, args1), Formula::Atom(p2, args2))
            if p1 == p2 && args1.len() == args2.len() =>
        {
            let mut combined_map = FxHashMap::default();
            let mut memo = FxHashMap::default();
            let generalized_args: Vec<Term> = args1
                .iter()
                .zip(args2.iter())
                .map(|(a1, a2)| {
                    let t = anti_unify_inner(a1, a2, &mut combined_map, &mut memo);
                    t
                })
                .collect();
            Some((Formula::Atom(*p1, generalized_args), combined_map))
        }
        _ => None,
    }
}

/// Induce generalizations from a set of example formulas.
///
/// Algorithm:
/// 1. Group examples by predicate symbol and arity.
/// 2. Within each group, pairwise anti-unify to find generalizations.
/// 3. Progressively generalize: anti-unify the result with each subsequent example.
/// 4. Score by coverage (how many examples the generalization matches).
/// 5. Wrap introduced variables in universal quantifiers.
///
/// Returns ranked generalizations.
pub fn induce(examples: &[Formula]) -> Vec<Generalization> {
    if examples.is_empty() {
        return Vec::new();
    }

    // Group by predicate + arity.
    let mut groups: FxHashMap<(Symbol, usize), Vec<&Formula>> = FxHashMap::default();
    for ex in examples {
        if let Some((pred, arity)) = ex.atom_predicate() {
            groups.entry((pred, arity)).or_default().push(ex);
        }
    }

    let mut results = Vec::new();

    for ((_pred, _arity), group) in &groups {
        if group.len() < 2 {
            continue; // Need at least 2 examples to generalize.
        }

        // Progressive anti-unification: start from the first example and
        // fold in each subsequent one.
        let mut current = group[0].clone();
        let mut combined_var_map: FxHashMap<u32, Vec<Term>> = FxHashMap::default();

        for other in &group[1..] {
            if let Some((generalized, var_map)) = anti_unify_atoms(&current, other) {
                current = generalized;
                for (var_id, terms) in var_map {
                    combined_var_map
                        .entry(var_id)
                        .or_default()
                        .extend(terms);
                }
            }
        }

        // Count coverage: how many of the group examples match the generalization.
        let coverage = group.len(); // By construction, anti-unification covers all inputs.

        // Wrap free variables in universal quantifiers.
        let free = current.free_variables();
        let mut quantified = current.clone();
        for var_id in &free {
            quantified = Formula::forall(*var_id, quantified);
        }

        results.push(Generalization {
            formula: quantified,
            coverage,
            total_examples: examples.len(),
            variable_instances: combined_var_map,
        });
    }

    // Sort by coverage descending, then by formula simplicity.
    results.sort_by(|a, b| {
        b.coverage
            .cmp(&a.coverage)
            .then_with(|| a.formula.free_variables().len().cmp(&b.formula.free_variables().len()))
    });

    results
}

/// Simple hash for terms (used in anti-unification memoization).
fn term_hash(t: &Term) -> u64 {
    use std::collections::hash_map::DefaultHasher;
    use std::hash::{Hash, Hasher};
    let mut hasher = DefaultHasher::new();
    t.hash(&mut hasher);
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

    #[test]
    fn test_anti_unify_identical() {
        let t = Term::Constant(sym(0));
        let (result, var_map) = anti_unify(&t, &t);
        assert_eq!(result, t);
        assert!(var_map.is_empty());
    }

    #[test]
    fn test_anti_unify_different_constants() {
        let t1 = Term::Constant(sym(0)); // alice
        let t2 = Term::Constant(sym(1)); // bob
        let (result, var_map) = anti_unify(&t1, &t2);
        // Should introduce a fresh variable.
        assert!(matches!(result, Term::Variable(_)));
        assert_eq!(var_map.len(), 1);
        let instances = var_map.values().next().unwrap();
        assert_eq!(instances.len(), 2);
    }

    #[test]
    fn test_anti_unify_compounds_same_functor() {
        // parent(alice, bob) and parent(alice, carol)
        // -> parent(alice, X)
        let parent = sym(0);
        let alice = sym(1);
        let bob = sym(2);
        let carol = sym(3);

        let t1 = Term::Compound(
            parent,
            vec![Term::Constant(alice), Term::Constant(bob)],
        );
        let t2 = Term::Compound(
            parent,
            vec![Term::Constant(alice), Term::Constant(carol)],
        );
        let (result, var_map) = anti_unify(&t1, &t2);

        match &result {
            Term::Compound(f, args) => {
                assert_eq!(*f, parent);
                assert_eq!(args[0], Term::Constant(alice)); // Same in both
                assert!(matches!(args[1], Term::Variable(_))); // Different -> variable
            }
            _ => panic!("Expected compound, got {:?}", result),
        }
        assert_eq!(var_map.len(), 1);
    }

    #[test]
    fn test_anti_unify_different_functors() {
        let t1 = Term::Compound(sym(0), vec![Term::Constant(sym(2))]);
        let t2 = Term::Compound(sym(1), vec![Term::Constant(sym(2))]);
        let (result, var_map) = anti_unify(&t1, &t2);
        // Different functors -> a variable replaces the whole compound.
        assert!(matches!(result, Term::Variable(_)));
        assert_eq!(var_map.len(), 1);
    }

    #[test]
    fn test_induce_parent_generalization() {
        let parent = sym(0);
        let alice = sym(1);
        let bob = sym(2);
        let carol = sym(3);

        let examples = vec![
            Formula::atom(
                parent,
                vec![Term::Constant(alice), Term::Constant(bob)],
            ),
            Formula::atom(
                parent,
                vec![Term::Constant(alice), Term::Constant(carol)],
            ),
        ];

        let generalizations = induce(&examples);
        assert!(!generalizations.is_empty());

        let gen = &generalizations[0];
        assert_eq!(gen.coverage, 2);
        assert_eq!(gen.total_examples, 2);

        // The generalization should have at least one universally quantified variable.
        match &gen.formula {
            Formula::ForAll(_, body) => match body.as_ref() {
                Formula::Atom(pred, args) => {
                    assert_eq!(*pred, parent);
                    assert_eq!(args[0], Term::Constant(alice)); // Common constant preserved
                }
                _ => panic!("Expected atom inside forall"),
            },
            _ => panic!("Expected ForAll, got {:?}", gen.formula),
        }
    }

    #[test]
    fn test_induce_multiple_predicates() {
        let parent = sym(0);
        let likes = sym(1);
        let alice = sym(2);
        let bob = sym(3);
        let carol = sym(4);
        let dave = sym(5);

        let examples = vec![
            Formula::atom(parent, vec![Term::Constant(alice), Term::Constant(bob)]),
            Formula::atom(parent, vec![Term::Constant(alice), Term::Constant(carol)]),
            Formula::atom(likes, vec![Term::Constant(bob), Term::Constant(dave)]),
            Formula::atom(likes, vec![Term::Constant(carol), Term::Constant(dave)]),
        ];

        let generalizations = induce(&examples);
        assert_eq!(generalizations.len(), 2); // One for parent, one for likes
    }

    #[test]
    fn test_induce_single_example_no_generalization() {
        let parent = sym(0);
        let alice = sym(1);
        let bob = sym(2);

        let examples = vec![Formula::atom(
            parent,
            vec![Term::Constant(alice), Term::Constant(bob)],
        )];
        let generalizations = induce(&examples);
        assert!(generalizations.is_empty()); // Need >= 2 examples
    }

    #[test]
    fn test_induce_fully_different_examples() {
        let parent = sym(0);
        let alice = sym(1);
        let bob = sym(2);
        let carol = sym(3);
        let dave = sym(4);

        let examples = vec![
            Formula::atom(parent, vec![Term::Constant(alice), Term::Constant(bob)]),
            Formula::atom(parent, vec![Term::Constant(carol), Term::Constant(dave)]),
        ];

        let generalizations = induce(&examples);
        assert!(!generalizations.is_empty());

        // Both arguments differ, so we should get parent(X, Y) -- two quantified vars.
        let gen = &generalizations[0];
        // Count ForAll depth
        let mut depth = 0;
        let mut current = &gen.formula;
        while let Formula::ForAll(_, body) = current {
            depth += 1;
            current = body;
        }
        assert_eq!(depth, 2, "Expected 2 universally quantified variables");
    }
}
