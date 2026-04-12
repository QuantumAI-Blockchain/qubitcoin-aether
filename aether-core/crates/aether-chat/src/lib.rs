//! aether-chat: Chat engine and LLM adapter for the Aether Tree AGI system.
//!
//! This crate ports two Python modules into Rust:
//!
//! 1. **AetherChat** (`chat.py`) -- main chat engine with intent detection,
//!    KG-first response synthesis, session management, entity extraction,
//!    and persistent per-user memory.
//!
//! 2. **LLMAdapter** (`llm_adapter.py`) -- pluggable LLM backends (Ollama,
//!    OpenAI-compatible, local models) with blocking HTTP clients, token
//!    counting, and a KnowledgeDistiller for feeding LLM insights back
//!    into the knowledge graph.
//!
//! Architecture (ADR-038 / ADR-039):
//! - Responses are built KG-first: pull live system state and knowledge
//!   graph facts before touching any LLM.
//! - LLM is a fallback for when KG context is insufficient (<80 chars).
//! - No template prose -- responses are synthesized from live data.
//! - Personality: warm, curious, self-reflective (per ADR-039).
//!
//! All structures are thread-safe via `parking_lot::RwLock`.
//! No PyO3 annotations -- pure Rust. PyO3 bindings come in a later batch.

pub mod intent;
pub mod response;
pub mod llm_adapter;
pub mod chat_engine;

// Re-export primary types
pub use intent::{Intent, IntentDetector};
pub use response::{ChatResponse, ChatContext, ResponseBuilder};
pub use llm_adapter::{LLMResponse, LLMAdapter, OllamaAdapter, OpenAICompatAdapter, KnowledgeDistiller};
pub use chat_engine::{AetherChat, ChatSession, ChatMessage, ChatMemory};
