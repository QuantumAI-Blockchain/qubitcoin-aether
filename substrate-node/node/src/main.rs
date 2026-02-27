//! Qubitcoin Node — Substrate-based quantum-secured Layer 1 blockchain.
//!
//! Entry point for the node binary. Parses CLI arguments and starts the service.

mod chain_spec;
mod cli;
mod rpc;
mod service;

fn main() -> sc_cli::Result<()> {
    cli::run()
}
