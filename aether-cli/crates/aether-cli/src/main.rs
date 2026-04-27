mod config;
mod repl;

use anyhow::Result;
use clap::{Parser, Subcommand};

#[derive(Parser)]
#[command(
    name = "aether",
    about = "Aether Mind — terminal interface to the world's first on-chain AI",
    version,
    after_help = "Examples:\n  aether                    Open interactive chat\n  aether chat \"what is QBC\"  One-shot query\n  aether --mine             Chat + mine simultaneously\n  aether status             Show chain info + Aether stats\n  aether wallet create      Generate a new keypair"
)]
struct Cli {
    /// Enable background VQE mining while chatting.
    #[arg(long)]
    mine: bool,

    /// Number of mining threads (default: 1).
    #[arg(long, default_value = "1")]
    threads: u32,

    /// Aether Mind API URL.
    #[arg(long, env = "AETHER_API_URL", default_value = "https://ai.qbc.network")]
    api_url: String,

    /// Substrate node RPC URL (for mining).
    #[arg(long, env = "AETHER_SUBSTRATE_URL", default_value = "https://rpc.qbc.network")]
    substrate_url: String,

    #[command(subcommand)]
    command: Option<Commands>,
}

#[derive(Subcommand)]
enum Commands {
    /// Send a one-shot chat message and exit.
    Chat {
        /// The message to send.
        message: String,

        /// Temperature for generation.
        #[arg(short, long, default_value = "0.7")]
        temperature: f32,

        /// Max tokens to generate.
        #[arg(short = 'n', long, default_value = "256")]
        max_tokens: usize,
    },

    /// Show chain info and Aether Mind status.
    Status,

    /// Mine QBC (no TUI, log output only).
    Mine {
        /// Number of mining threads.
        #[arg(short, long, default_value = "1")]
        threads: u32,
    },

    /// Wallet management.
    Wallet {
        #[command(subcommand)]
        action: WalletAction,
    },

    /// Search the knowledge fabric.
    Search {
        /// Search query.
        query: String,

        /// Max results.
        #[arg(short, long, default_value = "5")]
        limit: usize,
    },

    /// Gradient submission and status.
    Gradient {
        #[command(subcommand)]
        action: GradientAction,
    },

    /// View and claim gradient mining rewards.
    Rewards {
        #[command(subcommand)]
        action: RewardsAction,
    },
}

#[derive(Subcommand)]
enum WalletAction {
    /// Create a new wallet keypair.
    Create {
        /// Human-readable label for this wallet.
        #[arg(short, long, default_value = "default")]
        label: String,
    },
    /// List all wallets in the keystore.
    List,
    /// Show a wallet's address and public key.
    Info {
        /// Wallet address (defaults to first wallet).
        #[arg(long)]
        address: Option<String>,
    },
    /// Import a wallet from a hex-encoded private key.
    Import {
        /// 64-character hex private key.
        key: String,
        /// Label for the imported wallet.
        #[arg(short, long, default_value = "imported")]
        label: String,
    },
    /// Export wallet secret key (requires password).
    Export {
        /// Wallet address to export.
        #[arg(long)]
        address: Option<String>,
    },
    /// Delete a wallet from the keystore.
    Delete {
        /// Wallet address to delete.
        address: String,
    },
}

#[derive(Subcommand)]
enum GradientAction {
    /// Show gradient aggregation pool status.
    Status,
    /// Submit a test gradient (for development/testing).
    Submit {
        /// Miner ID to submit as.
        #[arg(long)]
        miner_id: Option<String>,
    },
}

#[derive(Subcommand)]
enum RewardsAction {
    /// Show earned rewards for your miner wallet.
    Show {
        /// Miner ID (defaults to wallet address).
        #[arg(long)]
        miner_id: Option<String>,
    },
    /// Show the global reward pool status.
    Pool,
    /// Claim unclaimed rewards to your wallet.
    Claim {
        /// Miner ID (defaults to wallet address).
        #[arg(long)]
        miner_id: Option<String>,
    },
}

#[tokio::main]
async fn main() -> Result<()> {
    env_logger::Builder::from_env(env_logger::Env::default().default_filter_or("info"))
        .format_timestamp(None)
        .init();

    let cli = Cli::parse();
    let client = aether_client::AetherClient::new(&cli.api_url);

    match cli.command {
        None => {
            // Interactive TUI mode
            let miner_config = if cli.mine {
                Some(aether_miner::MinerConfig {
                    substrate_rpc: cli.substrate_url.clone(),
                    max_attempts: 100,
                    threads: cli.threads,
                })
            } else {
                None
            };

            repl::run(client, miner_config).await
        }

        Some(Commands::Chat {
            message,
            temperature,
            max_tokens,
        }) => {
            cmd_chat(&client, &message, temperature, max_tokens).await
        }

        Some(Commands::Status) => cmd_status(&client).await,

        Some(Commands::Mine { threads }) => {
            cmd_mine(cli.substrate_url, threads).await
        }

        Some(Commands::Wallet { action }) => cmd_wallet(action).await,

        Some(Commands::Search { query, limit }) => {
            cmd_search(&client, &query, limit).await
        }

        Some(Commands::Gradient { action }) => {
            cmd_gradient(&client, action).await
        }

        Some(Commands::Rewards { action }) => {
            cmd_rewards(&client, action).await
        }
    }
}

async fn cmd_chat(
    client: &aether_client::AetherClient,
    message: &str,
    temperature: f32,
    max_tokens: usize,
) -> Result<()> {
    let resp = client.chat(message, temperature, max_tokens).await?;
    println!("{}", resp.response);
    println!(
        "\n\x1b[90m({} tokens, {}ms, phi={:.3}, vectors={}, height={})\x1b[0m",
        resp.tokens_generated, resp.latency_ms, resp.phi, resp.knowledge_vectors, resp.chain_height
    );
    Ok(())
}

async fn cmd_status(client: &aether_client::AetherClient) -> Result<()> {
    match client.health().await {
        Ok(health) => {
            println!("\x1b[1;32mAether Mind\x1b[0m — {}", health.version);
            println!("  Status:     {}", health.status);
            println!("  Model:      {}", health.model);
            println!("  Arch:       {}", health.architecture);
            println!("  Parameters: {}M", health.parameters / 1_000_000);
            println!("  Memory:     {}MB", health.memory_mb);
            println!("  Vectors:    {}", health.knowledge_vectors);
            println!("  Phi:        {:.6}", health.phi);
            println!("  Height:     {}", health.chain_height);
            println!("  Emotions:");
            println!("    curiosity:     {:.2}", health.emotional_state.curiosity);
            println!("    satisfaction:  {:.2}", health.emotional_state.satisfaction);
            println!("    wonder:        {:.2}", health.emotional_state.wonder);
            println!("    excitement:    {:.2}", health.emotional_state.excitement);
            println!("    frustration:   {:.2}", health.emotional_state.frustration);
        }
        Err(e) => {
            eprintln!("\x1b[31mCannot reach Aether Mind:\x1b[0m {e}");
            eprintln!("Is aether-mind running on the configured URL?");
        }
    }
    Ok(())
}

async fn cmd_mine(substrate_url: String, threads: u32) -> Result<()> {
    println!("\x1b[1;32mStarting VQE miner\x1b[0m ({threads} thread(s))");
    println!("Substrate RPC: {substrate_url}");
    println!("Press Ctrl+C to stop.\n");

    let handle = aether_miner::start(aether_miner::MinerConfig {
        substrate_rpc: substrate_url,
        max_attempts: 100,
        threads,
    });

    // Wait until Ctrl+C
    tokio::signal::ctrl_c().await?;
    handle.stop();
    let stats = handle.stats();
    println!(
        "\nMiner stopped. Blocks found: {}, Total attempts: {}",
        stats.blocks_found, stats.attempts_total
    );
    Ok(())
}

async fn cmd_wallet(action: WalletAction) -> Result<()> {
    let wallet = aether_wallet::Wallet::open(aether_wallet::default_keystore_dir())?;
    let ks_dir = aether_wallet::default_keystore_dir();

    match action {
        WalletAction::Create { label } => {
            let password = read_password("Set wallet password: ")?;
            let confirm = read_password("Confirm password: ")?;
            if password != confirm {
                anyhow::bail!("Passwords do not match");
            }

            let info = wallet.create(&password, &label)?;
            println!("\x1b[1;32mWallet created!\x1b[0m");
            println!("  Address:    {}", info.address);
            println!("  Public key: {}", info.public_key);
            println!("  Label:      {}", info.label);
            println!("  Keystore:   {}", ks_dir.display());
            println!("\n\x1b[33mBack up your password. There is no recovery.\x1b[0m");
        }

        WalletAction::List => {
            let wallets = wallet.list()?;
            if wallets.is_empty() {
                eprintln!("No wallets found. Run `aether wallet create` to create one.");
                return Ok(());
            }
            println!("\x1b[1;32mWallets\x1b[0m ({})\n", wallets.len());
            for (i, w) in wallets.iter().enumerate() {
                let marker = if i == 0 { " \x1b[33m(default)\x1b[0m" } else { "" };
                println!("  \x1b[1m{}.\x1b[0m {}{}", i + 1, w.address, marker);
                println!("     Label:      {}", w.label);
                println!("     Public key: {}...{}", &w.public_key[..8], &w.public_key[w.public_key.len()-8..]);
                println!("     Created:    {}", w.created_at);
                println!();
            }
            println!("  Keystore: {}", ks_dir.display());
        }

        WalletAction::Info { address } => {
            let addr = match address {
                Some(a) => a,
                None => match wallet.address()? {
                    Some(a) => a,
                    None => {
                        eprintln!("No wallet found. Run `aether wallet create` first.");
                        return Ok(());
                    }
                },
            };

            let password = read_password("Enter wallet password: ")?;
            let info = wallet.load(&addr, &password)?;
            println!("\x1b[1;32mWallet Info\x1b[0m");
            println!("  Address:    {}", info.address);
            println!("  Public key: {}", info.public_key);
            println!("  Label:      {}", info.label);
            println!("  Created:    {}", info.created_at);
        }

        WalletAction::Import { key, label } => {
            let password = read_password("Set password for imported wallet: ")?;
            let confirm = read_password("Confirm password: ")?;
            if password != confirm {
                anyhow::bail!("Passwords do not match");
            }

            let info = wallet.import_hex(&key, &password, &label)?;
            println!("\x1b[1;32mWallet imported!\x1b[0m");
            println!("  Address:    {}", info.address);
            println!("  Public key: {}", info.public_key);
            println!("  Label:      {}", info.label);
        }

        WalletAction::Export { address } => {
            let addr = match address {
                Some(a) => a,
                None => match wallet.address()? {
                    Some(a) => a,
                    None => {
                        eprintln!("No wallet found. Run `aether wallet create` first.");
                        return Ok(());
                    }
                },
            };

            let password = read_password("Enter wallet password: ")?;
            let secret = wallet.export_secret(&addr, &password)?;
            println!("{}", serde_json::to_string_pretty(&serde_json::json!({
                "address": addr,
                "secret_key": secret,
                "warning": "NEVER share this key. Anyone with it controls the wallet."
            }))?);
        }

        WalletAction::Delete { address } => {
            eprint!("Delete wallet {}? This is IRREVERSIBLE. Type 'yes' to confirm: ", address);
            use std::io::Write;
            std::io::stderr().flush()?;
            let mut confirm = String::new();
            std::io::stdin().read_line(&mut confirm)?;
            if confirm.trim() != "yes" {
                println!("Cancelled.");
                return Ok(());
            }
            wallet.delete(&address)?;
            println!("\x1b[1;31mWallet {} deleted.\x1b[0m", address);
        }
    }

    Ok(())
}

async fn cmd_search(
    client: &aether_client::AetherClient,
    query: &str,
    limit: usize,
) -> Result<()> {
    let resp = client.knowledge_search(query, limit).await?;
    if resp.results.is_empty() {
        println!("No results found.");
        return Ok(());
    }
    println!("Found {} results:\n", resp.total);
    for (i, r) in resp.results.iter().enumerate() {
        println!(
            "  \x1b[1m{}.\x1b[0m [domain {}] (sim: {:.3})",
            i + 1,
            r.domain,
            r.similarity
        );
        // Indent and truncate long text
        let text = if r.text.len() > 200 {
            format!("{}...", &r.text[..200])
        } else {
            r.text.clone()
        };
        for line in text.lines() {
            println!("     {line}");
        }
        println!();
    }
    Ok(())
}

async fn cmd_gradient(client: &aether_client::AetherClient, action: GradientAction) -> Result<()> {
    match action {
        GradientAction::Status => {
            match client.gradient_status().await {
                Ok(status) => {
                    println!("\x1b[1;32mGradient Pool Status\x1b[0m");
                    println!("  Queued peers:      {}", status.peer_gradients_queued);
                    println!("  Delta norm:        {:.6}", status.embedding_delta_norm);
                    println!("  Delta dimensions:  {}", status.embedding_delta_size);
                    println!("  Validation loss:   {:.6}", status.current_validation_loss);
                    if status.peer_gradients_queued >= 2 {
                        println!("  FedAvg:            \x1b[33mARMED (will trigger on next submit)\x1b[0m");
                    }
                }
                Err(e) => eprintln!("\x1b[31mError:\x1b[0m {e}"),
            }
        }

        GradientAction::Submit { miner_id } => {
            // Resolve miner_id from wallet if not provided
            let id = match miner_id {
                Some(id) => id,
                None => {
                    match aether_wallet::Wallet::open(aether_wallet::default_keystore_dir())
                        .ok()
                        .and_then(|w| w.address().ok().flatten())
                    {
                        Some(addr) => addr,
                        None => {
                            eprintln!("No --miner-id specified and no wallet found.");
                            eprintln!("Run `aether wallet create` or pass --miner-id.");
                            return Ok(());
                        }
                    }
                }
            };

            println!("Submitting test gradient as miner: {id}");

            // Generate a small test gradient (random-ish sparse update)
            let total_params: u64 = 1024;
            let k = 50; // top-k
            let indices: Vec<u32> = (0..k).collect();
            let values: Vec<f32> = (0..k).map(|i| 0.01 * (i as f32 + 1.0)).collect();

            match client.submit_gradients(&id, indices, values, total_params).await {
                Ok(resp) => {
                    println!("\x1b[1;32mGradient accepted!\x1b[0m");
                    println!("  FedAvg triggered:  {}", resp.fedavg_triggered);
                    println!("  Embeddings merged: {}", resp.embeddings_ingested);
                    println!("  Knowledge vectors: {}", resp.total_knowledge_vectors);
                    println!("  \x1b[1;33mReward: {:.8} QBC\x1b[0m", resp.reward_qbc);
                    println!("  Pool remaining:    {:.2} QBC", resp.pool_remaining_qbc);
                }
                Err(e) => eprintln!("\x1b[31mSubmission failed:\x1b[0m {e}"),
            }
        }
    }
    Ok(())
}

async fn cmd_rewards(client: &aether_client::AetherClient, action: RewardsAction) -> Result<()> {
    // Helper to resolve miner ID from wallet
    let resolve_miner = |explicit: Option<String>| -> Option<String> {
        explicit.or_else(|| {
            aether_wallet::Wallet::open(aether_wallet::default_keystore_dir())
                .ok()
                .and_then(|w| w.address().ok().flatten())
        })
    };

    match action {
        RewardsAction::Show { miner_id } => {
            let id = match resolve_miner(miner_id) {
                Some(id) => id,
                None => {
                    eprintln!("No --miner-id specified and no wallet found.");
                    return Ok(());
                }
            };

            match client.rewards(&id).await {
                Ok(r) => {
                    println!("\x1b[1;32mGradient Rewards\x1b[0m — miner: {}", r.miner_id);
                    println!("  Earned:       \x1b[1;33m{:.8} QBC\x1b[0m", r.earned_qbc);
                    println!("  Claimed:      {:.8} QBC", r.claimed_qbc);
                    println!("  Unclaimed:    \x1b[1;33m{:.8} QBC\x1b[0m", r.unclaimed_qbc);
                    println!("  Submissions:  {}", r.submissions);
                    println!("  Last block:   {}", r.last_block);
                    println!("  Avg improvement: {:.4}", r.avg_improvement_ratio);
                }
                Err(e) => eprintln!("\x1b[31mError:\x1b[0m {e}"),
            }
        }

        RewardsAction::Pool => {
            match client.reward_pool().await {
                Ok(p) => {
                    println!("\x1b[1;32mGradient Reward Pool\x1b[0m");
                    println!("  Pool address:  {}", p.pool_address);
                    println!("  Pool balance:  \x1b[1;33m{:.2} QBC\x1b[0m", p.pool_balance_qbc);
                    println!("  Distributed:   {:.8} QBC", p.total_distributed_qbc);
                    println!("  Claimed:       {:.8} QBC", p.total_claimed_qbc);
                    println!("  Unclaimed:     {:.8} QBC", p.total_unclaimed_qbc);
                    println!("  Base reward:   {:.4} QBC/submission", p.base_reward_qbc);
                    println!("  Max multiplier: {:.1}x", p.max_multiplier);
                    println!("  Total miners:  {}", p.total_miners);
                    println!("  Total submits: {}", p.total_submissions);
                }
                Err(e) => eprintln!("\x1b[31mError:\x1b[0m {e}"),
            }
        }

        RewardsAction::Claim { miner_id } => {
            let id = match resolve_miner(miner_id) {
                Some(id) => id,
                None => {
                    eprintln!("No --miner-id specified and no wallet found.");
                    return Ok(());
                }
            };

            // Get wallet address for payout
            let wallet_addr = match aether_wallet::Wallet::open(aether_wallet::default_keystore_dir())
                .ok()
                .and_then(|w| w.address().ok().flatten())
            {
                Some(addr) => addr,
                None => {
                    eprintln!("No wallet found. Run `aether wallet create` first.");
                    return Ok(());
                }
            };

            match client.claim_rewards(&id, &wallet_addr).await {
                Ok(c) => {
                    println!("\x1b[1;32mRewards claimed!\x1b[0m");
                    println!("  Amount: \x1b[1;33m{:.8} QBC\x1b[0m", c.amount_qbc);
                    println!("  Wallet: {}", c.wallet_address);
                    println!("  Status: {}", c.status);
                }
                Err(e) => eprintln!("\x1b[31mClaim failed:\x1b[0m {e}"),
            }
        }
    }
    Ok(())
}

fn read_password(prompt: &str) -> Result<String> {
    use std::io::Write;
    eprint!("{prompt}");
    std::io::stderr().flush()?;
    let mut password = String::new();
    std::io::stdin().read_line(&mut password)?;
    Ok(password.trim().to_string())
}
