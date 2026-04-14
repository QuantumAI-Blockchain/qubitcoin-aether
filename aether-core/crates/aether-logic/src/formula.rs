//! First-Order Logic formulas.
//!
//! A `Formula` represents a logical statement built from atoms, connectives,
//! and quantifiers. This is the language that the Aether Tree's reasoning
//! engine operates over.

use crate::term::{Symbol, SymbolTable, Term};
use rustc_hash::{FxHashMap, FxHashSet};
use serde::{Deserialize, Serialize};
use std::fmt;

/// A first-order logic formula.
#[derive(Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum Formula {
    /// Predicate application: `causes(A, B)`, `parent(alice, bob)`
    Atom(Symbol, Vec<Term>),
    /// Logical negation: `!P`
    Not(Box<Formula>),
    /// Conjunction: `P & Q & R`
    And(Vec<Formula>),
    /// Disjunction: `P | Q | R`
    Or(Vec<Formula>),
    /// Material implication: `P -> Q`
    Implies(Box<Formula>, Box<Formula>),
    /// Universal quantification: `forall X. P(X)`
    ForAll(u32, Box<Formula>),
    /// Existential quantification: `exists X. P(X)`
    Exists(u32, Box<Formula>),
}

impl Formula {
    // -- Constructors -------------------------------------------------------

    /// Create an atom: `predicate(args...)`.
    pub fn atom(predicate: Symbol, args: Vec<Term>) -> Self {
        Formula::Atom(predicate, args)
    }

    /// Create a negation.
    pub fn not(f: Formula) -> Self {
        Formula::Not(Box::new(f))
    }

    /// Create a conjunction.
    pub fn and(fs: Vec<Formula>) -> Self {
        Formula::And(fs)
    }

    /// Create a disjunction.
    pub fn or(fs: Vec<Formula>) -> Self {
        Formula::Or(fs)
    }

    /// Create an implication: `antecedent -> consequent`.
    pub fn implies(antecedent: Formula, consequent: Formula) -> Self {
        Formula::Implies(Box::new(antecedent), Box::new(consequent))
    }

    /// Create a universal quantification.
    pub fn forall(var: u32, body: Formula) -> Self {
        Formula::ForAll(var, Box::new(body))
    }

    /// Create an existential quantification.
    pub fn exists(var: u32, body: Formula) -> Self {
        Formula::Exists(var, Box::new(body))
    }

    // -- Queries ------------------------------------------------------------

    /// Collect all free variables in this formula.
    pub fn free_variables(&self) -> FxHashSet<u32> {
        let mut free = FxHashSet::default();
        self.collect_free_vars(&mut free, &mut FxHashSet::default());
        free
    }

    fn collect_free_vars(&self, free: &mut FxHashSet<u32>, bound: &mut FxHashSet<u32>) {
        match self {
            Formula::Atom(_, terms) => {
                for t in terms {
                    for v in t.variables() {
                        if !bound.contains(&v) {
                            free.insert(v);
                        }
                    }
                }
            }
            Formula::Not(f) => f.collect_free_vars(free, bound),
            Formula::And(fs) | Formula::Or(fs) => {
                for f in fs {
                    f.collect_free_vars(free, bound);
                }
            }
            Formula::Implies(a, b) => {
                a.collect_free_vars(free, bound);
                b.collect_free_vars(free, bound);
            }
            Formula::ForAll(v, body) | Formula::Exists(v, body) => {
                bound.insert(*v);
                body.collect_free_vars(free, bound);
                bound.remove(v);
            }
        }
    }

    /// Apply a substitution to all terms in this formula.
    pub fn substitute(&self, bindings: &FxHashMap<u32, Term>) -> Formula {
        match self {
            Formula::Atom(pred, terms) => {
                let new_terms = terms.iter().map(|t| t.substitute(bindings)).collect();
                Formula::Atom(*pred, new_terms)
            }
            Formula::Not(f) => Formula::Not(Box::new(f.substitute(bindings))),
            Formula::And(fs) => Formula::And(fs.iter().map(|f| f.substitute(bindings)).collect()),
            Formula::Or(fs) => Formula::Or(fs.iter().map(|f| f.substitute(bindings)).collect()),
            Formula::Implies(a, b) => Formula::Implies(
                Box::new(a.substitute(bindings)),
                Box::new(b.substitute(bindings)),
            ),
            Formula::ForAll(v, body) => {
                // Avoid capturing: skip if the quantified var is in bindings.
                let mut filtered = bindings.clone();
                filtered.remove(v);
                Formula::ForAll(*v, Box::new(body.substitute(&filtered)))
            }
            Formula::Exists(v, body) => {
                let mut filtered = bindings.clone();
                filtered.remove(v);
                Formula::Exists(*v, Box::new(body.substitute(&filtered)))
            }
        }
    }

    /// Return the negation of this formula, with double-negation elimination.
    pub fn negate(&self) -> Formula {
        match self {
            Formula::Not(inner) => (**inner).clone(),
            other => Formula::Not(Box::new(other.clone())),
        }
    }

    /// Is this formula an atom?
    pub fn is_atom(&self) -> bool {
        matches!(self, Formula::Atom(_, _))
    }

    /// Is this formula an implication?
    pub fn is_implication(&self) -> bool {
        matches!(self, Formula::Implies(_, _))
    }

    /// Try to extract the predicate symbol and arity from an atom.
    pub fn atom_predicate(&self) -> Option<(Symbol, usize)> {
        match self {
            Formula::Atom(pred, args) => Some((*pred, args.len())),
            _ => None,
        }
    }

    /// Display this formula given a symbol table.
    pub fn display<'a>(&'a self, symbols: &'a SymbolTable) -> FormulaDisplay<'a> {
        FormulaDisplay {
            formula: self,
            symbols,
        }
    }
}

impl fmt::Debug for Formula {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Formula::Atom(p, args) => {
                write!(f, "p{}(", p.0)?;
                for (i, a) in args.iter().enumerate() {
                    if i > 0 {
                        write!(f, ", ")?;
                    }
                    write!(f, "{a:?}")?;
                }
                write!(f, ")")
            }
            Formula::Not(inner) => write!(f, "!({inner:?})"),
            Formula::And(fs) => {
                write!(f, "(")?;
                for (i, formula) in fs.iter().enumerate() {
                    if i > 0 {
                        write!(f, " & ")?;
                    }
                    write!(f, "{formula:?}")?;
                }
                write!(f, ")")
            }
            Formula::Or(fs) => {
                write!(f, "(")?;
                for (i, formula) in fs.iter().enumerate() {
                    if i > 0 {
                        write!(f, " | ")?;
                    }
                    write!(f, "{formula:?}")?;
                }
                write!(f, ")")
            }
            Formula::Implies(a, b) => write!(f, "({a:?} -> {b:?})"),
            Formula::ForAll(v, body) => write!(f, "(forall ?{v}. {body:?})"),
            Formula::Exists(v, body) => write!(f, "(exists ?{v}. {body:?})"),
        }
    }
}

/// Helper for pretty-printing formulas with resolved symbol names.
pub struct FormulaDisplay<'a> {
    formula: &'a Formula,
    symbols: &'a SymbolTable,
}

impl<'a> fmt::Display for FormulaDisplay<'a> {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self.formula {
            Formula::Atom(pred, args) => {
                write!(f, "{}(", self.symbols.resolve(*pred))?;
                for (i, a) in args.iter().enumerate() {
                    if i > 0 {
                        write!(f, ", ")?;
                    }
                    write!(f, "{}", a.display(self.symbols))?;
                }
                write!(f, ")")
            }
            Formula::Not(inner) => write!(f, "~{}", inner.display(self.symbols)),
            Formula::And(fs) => {
                write!(f, "(")?;
                for (i, formula) in fs.iter().enumerate() {
                    if i > 0 {
                        write!(f, " & ")?;
                    }
                    write!(f, "{}", formula.display(self.symbols))?;
                }
                write!(f, ")")
            }
            Formula::Or(fs) => {
                write!(f, "(")?;
                for (i, formula) in fs.iter().enumerate() {
                    if i > 0 {
                        write!(f, " | ")?;
                    }
                    write!(f, "{}", formula.display(self.symbols))?;
                }
                write!(f, ")")
            }
            Formula::Implies(a, b) => {
                write!(
                    f,
                    "({} -> {})",
                    a.display(self.symbols),
                    b.display(self.symbols)
                )
            }
            Formula::ForAll(v, body) => {
                write!(f, "forall ?X{v}. {}", body.display(self.symbols))
            }
            Formula::Exists(v, body) => {
                write!(f, "exists ?X{v}. {}", body.display(self.symbols))
            }
        }
    }
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;
    use crate::term::SymbolTable;

    fn setup() -> (SymbolTable, Symbol, Symbol, Symbol) {
        let mut t = SymbolTable::new();
        let parent = t.intern("parent");
        let ancestor = t.intern("ancestor");
        let alice = t.intern("alice");
        (t, parent, ancestor, alice)
    }

    #[test]
    fn test_atom_creation() {
        let (_, parent, _, alice) = setup();
        let f = Formula::atom(parent, vec![Term::Constant(alice), Term::var(0)]);
        assert!(f.is_atom());
        assert_eq!(f.atom_predicate(), Some((parent, 2)));
    }

    #[test]
    fn test_free_variables() {
        let (_, parent, _, alice) = setup();
        // parent(alice, X) -- X is free
        let f = Formula::atom(parent, vec![Term::Constant(alice), Term::var(0)]);
        let free = f.free_variables();
        assert!(free.contains(&0));
        assert_eq!(free.len(), 1);
    }

    #[test]
    fn test_forall_binds_variable() {
        let (_, parent, _, alice) = setup();
        // forall X. parent(alice, X) -- X is bound, no free vars
        let body = Formula::atom(parent, vec![Term::Constant(alice), Term::var(0)]);
        let f = Formula::forall(0, body);
        assert!(f.free_variables().is_empty());
    }

    #[test]
    fn test_negate_double_elimination() {
        let (_, parent, _, alice) = setup();
        let f = Formula::atom(parent, vec![Term::Constant(alice)]);
        let neg = f.negate();
        assert!(matches!(neg, Formula::Not(_)));
        let double_neg = neg.negate();
        assert_eq!(double_neg, f);
    }

    #[test]
    fn test_substitute_formula() {
        let (_, parent, _, alice) = setup();
        let f = Formula::atom(parent, vec![Term::var(0), Term::var(1)]);
        let mut bindings = FxHashMap::default();
        bindings.insert(0, Term::Constant(alice));
        let result = f.substitute(&bindings);
        match &result {
            Formula::Atom(_, args) => {
                assert_eq!(args[0], Term::Constant(alice));
                assert_eq!(args[1], Term::var(1));
            }
            _ => panic!("Expected atom"),
        }
    }

    #[test]
    fn test_implies_creation() {
        let (_, parent, ancestor, _alice) = setup();
        let p = Formula::atom(parent, vec![Term::var(0), Term::var(1)]);
        let a = Formula::atom(ancestor, vec![Term::var(0), Term::var(1)]);
        let imp = Formula::implies(p, a);
        assert!(imp.is_implication());
    }

    #[test]
    fn test_display_formula() {
        let (table, parent, _, alice) = setup();
        let f = Formula::atom(parent, vec![Term::Constant(alice), Term::var(0)]);
        let displayed = format!("{}", f.display(&table));
        assert_eq!(displayed, "parent(alice, ?X0)");
    }
}
