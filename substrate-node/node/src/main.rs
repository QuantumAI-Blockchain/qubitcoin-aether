//! Qubitcoin Node — Substrate-based quantum-secured Layer 1 blockchain.
//!
//! Entry point for the node binary. Parses CLI arguments and starts the service.

mod block_author;
mod chain_spec;
mod cli;
mod rpc;
mod service;
mod weighted_chain;

fn main() -> sc_cli::Result<()> {
    cli::run()
}
