pub mod client;
pub mod prompt;
pub mod extract;

pub use client::{LlmClient, OllamaClient, ClaudeClient, LlmBackend};
pub use prompt::PromptManager;
pub use extract::ExtractedResponse;
