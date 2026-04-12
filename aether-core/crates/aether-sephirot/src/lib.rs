//! aether-sephirot: Tree of Life cognitive architecture for the Aether Tree.
//!
//! Provides CSF transport (inter-Sephirot messaging), Higgs cognitive field,
//! the 10 Sephirot processor framework, and the SephirotManager orchestrator.

pub mod csf_transport;
pub mod higgs_field;
pub mod processors;
pub mod sephirot_manager;

pub use csf_transport::{CSFMessage, CSFTransport, SephirahRole};
pub use higgs_field::{
    ExcitationEvent, HiggsCognitiveField, HiggsParameters, HiggsSUSYSwap, MassHierarchyHealth,
    TickResult, PHI,
};
pub use processors::{
    create_all_processors, NodeMessage, ProcessingContext, ProcessingResult, ReasoningContext,
    ReasoningResult, SephirahProcessor,
};
pub use sephirot_manager::{
    ConsensusResult, ProposalInput, SUSYViolation, SephirahState, SephirotManager,
};
