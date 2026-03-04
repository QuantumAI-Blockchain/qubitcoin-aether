//! CLI configuration for the Qubitcoin node.

use sc_cli::{RunCmd, SubstrateCli};
use std::sync::Arc;

#[derive(Debug, clap::Parser)]
pub struct Cli {
    #[command(subcommand)]
    pub subcommand: Option<Subcommand>,

    #[clap(flatten)]
    pub run: RunCmd,

    /// Enable VQE mining.
    #[clap(long)]
    pub mine: bool,

    /// Number of mining threads (default: 1).
    #[clap(long, default_value = "1")]
    pub mining_threads: u32,
}

#[derive(Debug, clap::Subcommand)]
pub enum Subcommand {
    /// Build a chain specification.
    BuildSpec(sc_cli::BuildSpecCmd),

    /// Validate blocks.
    CheckBlock(sc_cli::CheckBlockCmd),

    /// Export blocks.
    ExportBlocks(sc_cli::ExportBlocksCmd),

    /// Export the state of a given block into a chain spec.
    ExportState(sc_cli::ExportStateCmd),

    /// Import blocks.
    ImportBlocks(sc_cli::ImportBlocksCmd),

    /// Remove the whole chain.
    PurgeChain(sc_cli::PurgeChainCmd),

    /// Revert the chain to a previous state.
    Revert(sc_cli::RevertCmd),

    /// Sub-commands concerned with benchmarking.
    #[command(subcommand)]
    Benchmark(frame_benchmarking_cli::BenchmarkCmd),

    /// Key management CLI utilities.
    #[command(subcommand)]
    Key(sc_cli::KeySubcommand),

    /// DB meta columns information.
    ChainInfo(sc_cli::ChainInfoCmd),
}

impl SubstrateCli for Cli {
    fn impl_name() -> String {
        "Qubitcoin Node".into()
    }

    fn impl_version() -> String {
        env!("CARGO_PKG_VERSION").into()
    }

    fn description() -> String {
        "Qubitcoin — Quantum-secured Layer 1 blockchain with on-chain AGI".into()
    }

    fn author() -> String {
        "Qubitcoin Team <dev@qbc.network>".into()
    }

    fn support_url() -> String {
        "https://github.com/BlockArtica/Qubitcoin/issues".into()
    }

    fn copyright_start_year() -> i32 {
        2024
    }

    fn load_spec(&self, id: &str) -> Result<Box<dyn sc_service::ChainSpec>, String> {
        Ok(match id {
            "mainnet" => Box::new(crate::chain_spec::mainnet_config()?),
            "testnet" => Box::new(crate::chain_spec::testnet_config()?),
            "dev" => Box::new(crate::chain_spec::development_config()?),
            "" | "local" => Box::new(crate::chain_spec::local_testnet_config()?),
            path => {
                Box::new(crate::chain_spec::ChainSpec::from_json_file(std::path::PathBuf::from(path))?)
            }
        })
    }
}

/// Parse and run command line arguments.
pub fn run() -> sc_cli::Result<()> {
    let cli = Cli::from_args();

    match &cli.subcommand {
        Some(Subcommand::BuildSpec(cmd)) => {
            let runner = cli.create_runner(cmd)?;
            runner.sync_run(|config| cmd.run(config.chain_spec, config.network))
        }
        Some(Subcommand::CheckBlock(cmd)) => {
            let runner = cli.create_runner(cmd)?;
            runner.async_run(|config| {
                let (client, _, import_queue, task_manager) =
                    crate::service::new_chain_ops(&config)?;
                Ok((cmd.run(client, import_queue), task_manager))
            })
        }
        Some(Subcommand::ExportBlocks(cmd)) => {
            let runner = cli.create_runner(cmd)?;
            runner.async_run(|config| {
                let (client, _, _, task_manager) = crate::service::new_chain_ops(&config)?;
                Ok((cmd.run(client, config.database), task_manager))
            })
        }
        Some(Subcommand::ExportState(cmd)) => {
            let runner = cli.create_runner(cmd)?;
            runner.async_run(|config| {
                let (client, _, _, task_manager) = crate::service::new_chain_ops(&config)?;
                Ok((cmd.run(client, config.chain_spec), task_manager))
            })
        }
        Some(Subcommand::ImportBlocks(cmd)) => {
            let runner = cli.create_runner(cmd)?;
            runner.async_run(|config| {
                let (client, _, import_queue, task_manager) =
                    crate::service::new_chain_ops(&config)?;
                Ok((cmd.run(client, import_queue), task_manager))
            })
        }
        Some(Subcommand::PurgeChain(cmd)) => {
            let runner = cli.create_runner(cmd)?;
            runner.sync_run(|config| cmd.run(config.database))
        }
        Some(Subcommand::Revert(cmd)) => {
            let runner = cli.create_runner(cmd)?;
            runner.async_run(|config| {
                let (client, backend, _, task_manager) = crate::service::new_chain_ops(&config)?;
                let aux_revert: Option<Box<dyn FnOnce(
                    Arc<crate::service::FullClient>,
                    Arc<sc_service::TFullBackend<qbc_runtime::opaque::Block>>,
                    sp_runtime::traits::NumberFor<qbc_runtime::opaque::Block>,
                ) -> Result<(), sc_cli::Error>>> = Some(Box::new(|c, _b, blocks| {
                    sc_consensus_grandpa::revert(c, blocks)?;
                    Ok(())
                }));
                Ok((cmd.run(client, backend, aux_revert), task_manager))
            })
        }
        Some(Subcommand::Key(cmd)) => cmd.run(&cli),
        Some(Subcommand::ChainInfo(cmd)) => {
            let runner = cli.create_runner(cmd)?;
            runner.sync_run(|config| cmd.run::<qbc_runtime::Block>(&config))
        }
        Some(Subcommand::Benchmark(_cmd)) => {
            Err("Benchmarking not yet implemented".into())
        }
        None => {
            let mine = cli.mine;
            let mining_threads = cli.mining_threads;
            let runner = cli.create_runner(&cli.run)?;
            runner.run_node_until_exit(|config| async move {
                crate::service::new_full(config, mine, mining_threads)
                    .map_err(sc_cli::Error::Service)
            })
        }
    }
}
