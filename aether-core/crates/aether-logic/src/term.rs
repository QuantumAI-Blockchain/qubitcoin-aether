//! First-Order Logic terms with interned symbols.
//!
//! Terms are the building blocks of formulas:
//! - `Variable(u32)` -- a logic variable (e.g., X, Y)
//! - `Constant(Symbol)` -- a ground constant (e.g., alice, bob)
//! - `Compound(Symbol, Vec<Term>)` -- a function application (e.g., parent(alice, X))
//!
//! Symbols are interned via `SymbolTable` for O(1) equality checks and compact storage.

use rustc_hash::{FxHashMap, FxHashSet};
use serde::{Deserialize, Serialize};
use std::fmt;

// ---------------------------------------------------------------------------
// Symbol interning
// ---------------------------------------------------------------------------

/// An interned symbol -- a u32 index into a `SymbolTable`.
#[derive(Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub struct Symbol(pub u32);

impl fmt::Debug for Symbol {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "Symbol({})", self.0)
    }
}

/// Bidirectional `String <-> Symbol` mapping.
#[derive(Clone, Debug, Default)]
pub struct SymbolTable {
    to_id: FxHashMap<String, u32>,
    to_name: Vec<String>,
}

impl SymbolTable {
    /// Create a new empty symbol table.
    pub fn new() -> Self {
        Self::default()
    }

    /// Intern a string and return its `Symbol`. Idempotent.
    pub fn intern(&mut self, name: &str) -> Symbol {
        if let Some(&id) = self.to_id.get(name) {
            return Symbol(id);
        }
        let id = self.to_name.len() as u32;
        self.to_name.push(name.to_string());
        self.to_id.insert(name.to_string(), id);
        Symbol(id)
    }

    /// Resolve a `Symbol` back to its string. Panics if the symbol is invalid.
    pub fn resolve(&self, sym: Symbol) -> &str {
        &self.to_name[sym.0 as usize]
    }

    /// Try to resolve a symbol, returning `None` if invalid.
    pub fn try_resolve(&self, sym: Symbol) -> Option<&str> {
        self.to_name.get(sym.0 as usize).map(|s| s.as_str())
    }

    /// Number of interned symbols.
    pub fn len(&self) -> usize {
        self.to_name.len()
    }

    /// Whether the table is empty.
    pub fn is_empty(&self) -> bool {
        self.to_name.is_empty()
    }
}

// ---------------------------------------------------------------------------
// Term
// ---------------------------------------------------------------------------

/// A first-order logic term.
#[derive(Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum Term {
    /// A logic variable, identified by a unique u32.
    Variable(u32),
    /// A ground constant (interned symbol).
    Constant(Symbol),
    /// A compound term: functor applied to arguments. `f(t1, t2, ...)`
    Compound(Symbol, Vec<Term>),
}

impl Term {
    // -- Constructors -------------------------------------------------------

    /// Shorthand for `Term::Variable(id)`.
    pub fn var(id: u32) -> Self {
        Term::Variable(id)
    }

    /// Shorthand for `Term::Constant(sym)`.
    pub fn constant(sym: Symbol) -> Self {
        Term::Constant(sym)
    }

    /// Shorthand for `Term::Compound(functor, args)`.
    pub fn compound(functor: Symbol, args: Vec<Term>) -> Self {
        Term::Compound(functor, args)
    }

    // -- Queries ------------------------------------------------------------

    /// Collect all free variable IDs in this term.
    pub fn variables(&self) -> FxHashSet<u32> {
        let mut vars = FxHashSet::default();
        self.collect_vars(&mut vars);
        vars
    }

    fn collect_vars(&self, out: &mut FxHashSet<u32>) {
        match self {
            Term::Variable(v) => {
                out.insert(*v);
            }
            Term::Constant(_) => {}
            Term::Compound(_, args) => {
                for arg in args {
                    arg.collect_vars(out);
                }
            }
        }
    }

    /// Does this term contain the variable `var`? (Occurs check.)
    pub fn contains_var(&self, var: u32) -> bool {
        match self {
            Term::Variable(v) => *v == var,
            Term::Constant(_) => false,
            Term::Compound(_, args) => args.iter().any(|a| a.contains_var(var)),
        }
    }

    /// Apply a substitution, producing a new term.
    pub fn substitute(&self, bindings: &FxHashMap<u32, Term>) -> Term {
        match self {
            Term::Variable(v) => {
                if let Some(bound) = bindings.get(v) {
                    // Recursively apply in case binding itself contains variables.
                    bound.substitute(bindings)
                } else {
                    self.clone()
                }
            }
            Term::Constant(_) => self.clone(),
            Term::Compound(f, args) => {
                let new_args = args.iter().map(|a| a.substitute(bindings)).collect();
                Term::Compound(*f, new_args)
            }
        }
    }

    /// Is this term ground (contains no variables)?
    pub fn is_ground(&self) -> bool {
        match self {
            Term::Variable(_) => false,
            Term::Constant(_) => true,
            Term::Compound(_, args) => args.iter().all(|a| a.is_ground()),
        }
    }

    /// Display this term given a symbol table for human-readable output.
    pub fn display<'a>(&'a self, symbols: &'a SymbolTable) -> TermDisplay<'a> {
        TermDisplay {
            term: self,
            symbols,
        }
    }
}

impl fmt::Debug for Term {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Term::Variable(v) => write!(f, "?{v}"),
            Term::Constant(s) => write!(f, "c{}", s.0),
            Term::Compound(s, args) => {
                write!(f, "f{}(", s.0)?;
                for (i, a) in args.iter().enumerate() {
                    if i > 0 {
                        write!(f, ", ")?;
                    }
                    write!(f, "{a:?}")?;
                }
                write!(f, ")")
            }
        }
    }
}

/// Helper for pretty-printing terms with resolved symbol names.
pub struct TermDisplay<'a> {
    term: &'a Term,
    symbols: &'a SymbolTable,
}

impl<'a> fmt::Display for TermDisplay<'a> {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self.term {
            Term::Variable(v) => write!(f, "?X{v}"),
            Term::Constant(s) => {
                write!(f, "{}", self.symbols.resolve(*s))
            }
            Term::Compound(s, args) => {
                write!(f, "{}(", self.symbols.resolve(*s))?;
                for (i, a) in args.iter().enumerate() {
                    if i > 0 {
                        write!(f, ", ")?;
                    }
                    write!(f, "{}", a.display(self.symbols))?;
                }
                write!(f, ")")
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

    fn make_table() -> SymbolTable {
        let mut t = SymbolTable::new();
        t.intern("alice"); // 0
        t.intern("bob");   // 1
        t.intern("parent"); // 2
        t
    }

    #[test]
    fn test_symbol_intern_idempotent() {
        let mut t = SymbolTable::new();
        let a1 = t.intern("foo");
        let a2 = t.intern("foo");
        assert_eq!(a1, a2);
        assert_eq!(t.len(), 1);
    }

    #[test]
    fn test_symbol_resolve() {
        let mut t = SymbolTable::new();
        let s = t.intern("hello");
        assert_eq!(t.resolve(s), "hello");
    }

    #[test]
    fn test_variables_collected() {
        let term = Term::Compound(
            Symbol(2),
            vec![Term::Variable(0), Term::Variable(1)],
        );
        let vars = term.variables();
        assert!(vars.contains(&0));
        assert!(vars.contains(&1));
        assert_eq!(vars.len(), 2);
    }

    #[test]
    fn test_contains_var_occurs_check() {
        // f(X, g(Y))
        let term = Term::Compound(
            Symbol(0),
            vec![
                Term::Variable(0),
                Term::Compound(Symbol(1), vec![Term::Variable(1)]),
            ],
        );
        assert!(term.contains_var(0));
        assert!(term.contains_var(1));
        assert!(!term.contains_var(2));
    }

    #[test]
    fn test_substitute() {
        let mut table = make_table();
        let alice = table.intern("alice");
        let parent = table.intern("parent");

        // parent(X, Y) with {X -> alice}
        let term = Term::Compound(parent, vec![Term::var(0), Term::var(1)]);
        let mut bindings = FxHashMap::default();
        bindings.insert(0, Term::Constant(alice));

        let result = term.substitute(&bindings);
        match &result {
            Term::Compound(_, args) => {
                assert_eq!(args[0], Term::Constant(alice));
                assert_eq!(args[1], Term::Variable(1));
            }
            _ => panic!("Expected compound"),
        }
    }

    #[test]
    fn test_is_ground() {
        let c = Term::Constant(Symbol(0));
        assert!(c.is_ground());

        let v = Term::Variable(0);
        assert!(!v.is_ground());

        let compound = Term::Compound(Symbol(0), vec![Term::Constant(Symbol(1))]);
        assert!(compound.is_ground());

        let compound_with_var = Term::Compound(Symbol(0), vec![Term::Variable(0)]);
        assert!(!compound_with_var.is_ground());
    }

    #[test]
    fn test_display_with_symbols() {
        let mut table = SymbolTable::new();
        let alice = table.intern("alice");
        let bob = table.intern("bob");
        let parent = table.intern("parent");

        let term = Term::Compound(parent, vec![Term::Constant(alice), Term::Constant(bob)]);
        let displayed = format!("{}", term.display(&table));
        assert_eq!(displayed, "parent(alice, bob)");
    }
}
