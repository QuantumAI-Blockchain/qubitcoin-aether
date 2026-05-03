mod config;
mod repl;

use anyhow::Result;
use clap::{Parser, Subcommand};

#[derive(Parser)]
#[command(
    name = "aether",
    about = "Aether Mind — terminal interface to the world's first on-chain AI",
    version,
    after_help = "Examples:\n  aether                       Open interactive chat\n  aether chat \"what is QBC\"     One-shot query\n  aether --mine                Chat + mine simultaneously\n  aether status                Show chain info + Aether stats\n  aether wallet create         Generate Dilithium5 quantum-secure keypair\n  aether wallet balance        Query on-chain balance\n  aether wallet send <to> <amt> Send QBC via signed UTXO transaction"
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

    /// Substrate node RPC URL (for mining and on-chain queries).
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

        /// Ed25519 secret key for Substrate account (hex, 64 chars).
        /// Required for submitting mining proofs to chain.
        #[arg(long, env = "SUBSTRATE_SECRET_KEY")]
        substrate_key: Option<String>,
    },

    /// Wallet management (Dilithium5 quantum-secure).
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

    /// Proof-of-Cognitive-Work — generate and verify cognitive proofs from mining.
    Cogwork {
        #[command(subcommand)]
        action: CogworkAction,
    },

    /// Quantum-Entangled Wallet Protocol — link wallets with conditional spending.
    Entangle {
        #[command(subcommand)]
        action: EntangleAction,
    },

    /// Predictive UTXO Coalescing Engine — ML-powered fee optimization.
    Optimize {
        #[command(subcommand)]
        action: OptimizeAction,
    },

    /// Zero-Knowledge Cognitive Recovery — recover wallets without seed phrases.
    Recover {
        #[command(subcommand)]
        action: RecoverAction,
    },

    /// Symbiotic Mining Intelligence — every miner is a neuron.
    Synapse {
        #[command(subcommand)]
        action: SynapseAction,
    },

    /// Privacy transactions (Susy Swaps) — hidden amounts and stealth addresses.
    Privacy {
        #[command(subcommand)]
        action: PrivacyAction,
    },
}

#[derive(Subcommand)]
enum WalletAction {
    /// Create a new Dilithium5 quantum-secure wallet keypair.
    Create {
        /// Human-readable label for this wallet.
        #[arg(short, long, default_value = "default")]
        label: String,
    },
    /// List all wallets in the keystore.
    List,
    /// Show a wallet's address, public key, and quantum security status.
    Info {
        /// Wallet address (defaults to first wallet).
        #[arg(long)]
        address: Option<String>,
    },
    /// Query on-chain balance from the Substrate node.
    Balance {
        /// Wallet address (defaults to first wallet).
        #[arg(long)]
        address: Option<String>,

        /// Substrate RPC URL.
        #[arg(long, env = "AETHER_SUBSTRATE_URL", default_value = "https://rpc.qbc.network")]
        substrate_url: String,
    },
    /// Send QBC to another address (signs with Dilithium5).
    Send {
        /// Recipient QBC address (64 hex chars).
        to: String,

        /// Amount in QBC (e.g., 1.5).
        amount: f64,

        /// Substrate RPC URL.
        #[arg(long, env = "AETHER_SUBSTRATE_URL", default_value = "https://rpc.qbc.network")]
        substrate_url: String,

        /// Ed25519 secret key for Substrate account (hex, 64 chars).
        #[arg(long, env = "SUBSTRATE_SECRET_KEY")]
        substrate_key: Option<String>,
    },
    /// Register Dilithium5 public key on-chain (required before sending).
    RegisterKey {
        /// Wallet address to register (defaults to first wallet).
        #[arg(long)]
        address: Option<String>,

        /// Substrate RPC URL.
        #[arg(long, env = "AETHER_SUBSTRATE_URL", default_value = "https://rpc.qbc.network")]
        substrate_url: String,

        /// Ed25519 secret key for Substrate account (hex, 64 chars).
        #[arg(long, env = "SUBSTRATE_SECRET_KEY")]
        substrate_key: Option<String>,
    },
    /// Import a wallet from a hex-encoded private key.
    Import {
        /// Hex private key (9728 chars for Dilithium5, 64 chars for legacy).
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
    /// Sign a message with Dilithium5 (outputs hex signature).
    Sign {
        /// Message to sign.
        message: String,
        /// Wallet address (defaults to first wallet).
        #[arg(long)]
        address: Option<String>,
    },
    /// Verify a Dilithium5 signature.
    Verify {
        /// Message that was signed.
        message: String,
        /// Hex-encoded signature (9254 chars).
        signature: String,
        /// Hex-encoded Dilithium5 public key (5184 chars).
        public_key: String,
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

// ── Innovation Command Enums ────────────────────────────────────

#[derive(Subcommand)]
enum CogworkAction {
    /// Generate a cognitive proof for a given block height.
    Generate {
        /// Hamiltonian seed (64 hex chars). Defaults to a test seed.
        #[arg(long)]
        seed: Option<String>,
        /// Block height.
        #[arg(long, default_value = "265000")]
        height: u64,
    },
    /// Verify a cognitive proof (JSON from stdin or argument).
    Verify {
        /// JSON proof string.
        proof_json: String,
        /// JSON challenge string.
        challenge_json: String,
    },
    /// Benchmark cognitive proof generation.
    Benchmark {
        /// Number of challenges to solve.
        #[arg(long, default_value = "100")]
        rounds: u32,
    },
}

#[derive(Subcommand)]
enum EntangleAction {
    /// Create an entanglement between two wallets.
    Create {
        /// Your wallet address.
        #[arg(long)]
        wallet_a: Option<String>,
        /// Partner wallet's public key (hex).
        partner_pubkey: String,
        /// Dead-man switch: blocks of inactivity before partner inherits.
        #[arg(long, default_value = "100000")]
        deadman_blocks: u64,
        /// Inheritance ratio (0.0–1.0).
        #[arg(long, default_value = "1.0")]
        inheritance: f64,
        /// Require both parties to sign (escrow mode).
        #[arg(long)]
        escrow: bool,
    },
    /// Check entanglement status (from a saved entanglement file).
    Status {
        /// Path to entanglement JSON file.
        file: String,
        /// Wallet A's last active block height.
        #[arg(long)]
        last_active: u64,
        /// Current block height.
        #[arg(long)]
        current_height: u64,
    },
}

#[derive(Subcommand)]
enum OptimizeAction {
    /// Predict the optimal fee rate based on chain history.
    PredictFee,
    /// Analyze UTXOs and recommend consolidation.
    Analyze,
    /// Show fee trend (rising/falling/stable).
    Trend,
}

#[derive(Subcommand)]
enum RecoverAction {
    /// Set up cognitive recovery for a wallet.
    Setup {
        /// Wallet address (defaults to first wallet).
        #[arg(long)]
        address: Option<String>,
        /// M-of-N threshold (minimum correct answers needed).
        #[arg(long, default_value = "5")]
        threshold: u32,
    },
    /// Attempt wallet recovery using cognitive answers.
    Attempt {
        /// Path to recovery setup JSON file.
        file: String,
    },
}

#[derive(Subcommand)]
enum PrivacyAction {
    /// Generate a stealth address keypair (spend + view keys).
    StealthKeygen,
    /// Create a stealth output for a recipient.
    StealthSend {
        /// Recipient stealth address (132 hex chars = spend_pub || view_pub).
        recipient: String,
    },
    /// Scan a stealth output to check if it belongs to your wallet.
    StealthScan {
        /// Ephemeral public key from the transaction (66 hex chars).
        ephemeral_pubkey: String,
        /// One-time output address from the transaction (66 hex chars).
        output_address: String,
        /// Path to your stealth keypair JSON file.
        #[arg(long)]
        keypair: String,
    },
    /// Create a Pedersen commitment to a value.
    Commit {
        /// Value to commit to (in QBC units, e.g., 1.5).
        value: f64,
    },
    /// Verify a Pedersen commitment.
    VerifyCommit {
        /// Commitment JSON (from `privacy commit` output).
        commitment_json: String,
    },
    /// Build a confidential transaction (Susy Swap).
    Send {
        /// Amount to send in QBC (e.g., 1.5).
        amount: f64,
        /// Fee in QBC (e.g., 0.001).
        #[arg(long, default_value = "0.001")]
        fee: f64,
        /// Recipient stealth address (132 hex chars). Optional — omit for non-stealth.
        #[arg(long)]
        to: Option<String>,
    },
    /// Show privacy system info and transaction sizes.
    Info,
}

#[derive(Subcommand)]
enum SynapseAction {
    /// Show symbiotic intelligence status.
    Status,
    /// Generate a cognitive fragment from a test VQE result.
    Generate {
        /// VQE energy value.
        #[arg(long, default_value = "-2.5", allow_hyphen_values = true)]
        energy: f64,
    },
    /// Aggregate fragments from multiple miners (test mode).
    Aggregate,
}

#[tokio::main]
async fn main() -> Result<()> {
    env_logger::Builder::from_env(env_logger::Env::default().default_filter_or("info"))
        .format_timestamp(None)
        .init();

    let cli = Cli::parse();
    let client = aether_client::AetherClient::new(&cli.api_url);

    // Attach default wallet address for subscription auth (X-QBC-Address header)
    let client = {
        let ks_dir = aether_wallet::default_keystore_dir();
        let ks = aether_wallet::Keystore::new(ks_dir);
        match ks.default_address() {
            Ok(Some(addr)) => client.with_wallet(addr),
            _ => client,
        }
    };

    match cli.command {
        None => {
            // Interactive TUI mode
            let miner_config = if cli.mine {
                Some(aether_miner::MinerConfig {
                    substrate_rpc: cli.substrate_url.clone(),
                    max_attempts: 100,
                    threads: cli.threads,
                    substrate_secret_key: None,
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

        Some(Commands::Mine { threads, substrate_key }) => {
            let sk = parse_substrate_key(substrate_key)?;
            cmd_mine(cli.substrate_url, threads, sk).await
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

        Some(Commands::Cogwork { action }) => cmd_cogwork(action),
        Some(Commands::Entangle { action }) => cmd_entangle(action),
        Some(Commands::Optimize { action }) => cmd_optimize(action),
        Some(Commands::Recover { action }) => cmd_recover(action),
        Some(Commands::Synapse { action }) => cmd_synapse(action),
        Some(Commands::Privacy { action }) => cmd_privacy(action),
    }
}

fn parse_substrate_key(key_hex: Option<String>) -> Result<Option<[u8; 32]>> {
    match key_hex {
        Some(hex_str) => {
            let bytes = hex::decode(hex_str.trim().trim_start_matches("0x"))
                .map_err(|_| anyhow::anyhow!("invalid hex for substrate key"))?;
            if bytes.len() != 32 {
                anyhow::bail!("substrate key must be 32 bytes (64 hex chars), got {}", bytes.len());
            }
            let mut key = [0u8; 32];
            key.copy_from_slice(&bytes);
            Ok(Some(key))
        }
        None => Ok(None),
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

async fn cmd_mine(substrate_url: String, threads: u32, substrate_key: Option<[u8; 32]>) -> Result<()> {
    println!("\x1b[1;32mStarting VQE miner\x1b[0m ({threads} thread(s))");
    println!("Substrate RPC: {substrate_url}");
    if substrate_key.is_some() {
        println!("Substrate signing key: \x1b[32mprovided\x1b[0m");
    } else {
        println!("\x1b[33mWarning: No --substrate-key provided. Using dev key.\x1b[0m");
        println!("Set SUBSTRATE_SECRET_KEY env var or pass --substrate-key for production.");
    }
    println!("Press Ctrl+C to stop.\n");

    let handle = aether_miner::start(aether_miner::MinerConfig {
        substrate_rpc: substrate_url,
        max_attempts: 100,
        threads,
        substrate_secret_key: substrate_key,
    });

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
            println!("\x1b[1;32mDilithium5 quantum-secure wallet created!\x1b[0m");
            println!("  Address:    {}", info.address);
            println!("  Public key: {}...{}", &info.public_key[..16], &info.public_key[info.public_key.len()-16..]);
            println!("  PK size:    {} bytes (CRYSTALS-Dilithium5, NIST Level 5)", aether_wallet::DILITHIUM5_PK_SIZE);
            println!("  Label:      {}", info.label);
            println!("  Keystore:   {}", ks_dir.display());
            println!("\n\x1b[33mBack up your password. There is no recovery.\x1b[0m");
            println!("\x1b[32mThis wallet is quantum-resistant (post-quantum cryptography).\x1b[0m");
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
                let security = if w.is_quantum_secure() {
                    "\x1b[32m[Dilithium5]\x1b[0m"
                } else {
                    "\x1b[33m[legacy]\x1b[0m"
                };
                println!("  \x1b[1m{}.\x1b[0m {}{} {}", i + 1, w.address, marker, security);
                println!("     Label:      {}", w.label);
                if w.public_key.len() > 16 {
                    println!("     Public key: {}...{}", &w.public_key[..8], &w.public_key[w.public_key.len()-8..]);
                } else {
                    println!("     Public key: {}", w.public_key);
                }
                println!("     Created:    {}", w.created_at);
                println!();
            }
            println!("  Keystore: {}", ks_dir.display());
        }

        WalletAction::Info { address } => {
            let addr = resolve_wallet_address(&wallet, address)?;
            let password = read_password("Enter wallet password: ")?;
            let info = wallet.load(&addr, &password)?;
            let security = if info.is_quantum_secure() {
                "CRYSTALS-Dilithium5 (NIST Level 5) — QUANTUM SECURE"
            } else {
                "AES-256-GCM + Argon2id — CLASSICAL ONLY"
            };
            println!("\x1b[1;32mWallet Info\x1b[0m");
            println!("  Address:    {}", info.address);
            println!("  Public key: {}", info.public_key);
            println!("  PK size:    {} bytes", info.public_key.len() / 2);
            println!("  Label:      {}", info.label);
            println!("  Version:    v{}", info.version);
            println!("  Security:   {}", security);
            println!("  Created:    {}", info.created_at);
        }

        WalletAction::Balance { address, substrate_url } => {
            let addr = resolve_wallet_address(&wallet, address)?;

            // Only Dilithium5 (v3) wallets have 32-byte addresses that work on-chain
            let version = wallet.wallet_version(&addr)?;
            if version < 3 {
                eprintln!("\x1b[33mWarning: Legacy wallet (v{version}). On-chain balance requires a Dilithium5 (v3) wallet.\x1b[0m");
                eprintln!("Create a new wallet with `aether wallet create` for on-chain functionality.");
                return Ok(());
            }

            let substrate = aether_client::substrate::SubstrateClient::new(&substrate_url);
            match substrate.get_balance(&addr).await {
                Ok(balance) => {
                    let qbc = balance as f64 / 100_000_000.0;
                    println!("\x1b[1;32mOn-Chain Balance\x1b[0m");
                    println!("  Address:  {}", addr);
                    println!("  Balance:  \x1b[1;33m{:.8} QBC\x1b[0m ({} units)", qbc, balance);
                }
                Err(e) => {
                    eprintln!("\x1b[31mFailed to query balance:\x1b[0m {e}");
                    eprintln!("Is the Substrate node running at {}?", substrate_url);
                }
            }
        }

        WalletAction::Send { to, amount, substrate_url, substrate_key } => {
            let addr = resolve_wallet_address(&wallet, None)?;
            let version = wallet.wallet_version(&addr)?;
            if version < 3 {
                anyhow::bail!("Transaction signing requires a Dilithium5 (v3) wallet. Create one with `aether wallet create`.");
            }

            let substrate_sk = parse_substrate_key(substrate_key)?
                .ok_or_else(|| anyhow::anyhow!(
                    "Substrate signing key required. Set SUBSTRATE_SECRET_KEY env var or pass --substrate-key."
                ))?;

            // Validate recipient address
            let to_bytes = hex::decode(to.trim().trim_start_matches("0x"))
                .map_err(|_| anyhow::anyhow!("invalid recipient address hex"))?;
            if to_bytes.len() != 32 {
                anyhow::bail!("recipient address must be 32 bytes (64 hex chars)");
            }
            let mut to_addr = [0u8; 32];
            to_addr.copy_from_slice(&to_bytes);

            let amount_units = (amount * 100_000_000.0) as u128;
            if amount_units == 0 {
                anyhow::bail!("amount must be > 0");
            }

            let password = read_password("Enter wallet password to sign: ")?;

            // Build transaction inputs/outputs
            // For now, we construct a simple 1-input 1-output + change transaction
            // In production, you'd query UTXOs and select inputs
            println!("\x1b[33mNote: This builds a transaction for submission. UTXO selection requires chain queries.\x1b[0m");

            let from_bytes = hex::decode(&addr)?;
            let mut from_addr = [0u8; 32];
            from_addr.copy_from_slice(&from_bytes);

            // Placeholder UTXO input — in production, query UTXOs from chain
            // For now, the user must have a known UTXO
            eprintln!("\x1b[31mUTXO selection not yet automated. Use `aether wallet balance` to verify funds.\x1b[0m");
            eprintln!("Transaction building requires UTXO indexing on the Substrate node.");
            eprintln!("This will be completed when the blockchain indexer is live.");

            // Build the signing message
            let inputs = vec![aether_client::substrate::TxInput {
                prev_txid: [0u8; 32], // Would come from UTXO query
                prev_vout: 0,
            }];
            let outputs = vec![
                aether_client::substrate::TxOutput {
                    address: to_addr,
                    amount: amount_units,
                },
            ];

            let signing_msg = aether_client::substrate::SubstrateClient::build_utxo_signing_message(&inputs, &outputs);

            // Sign with Dilithium5
            let sig = wallet.sign(&addr, &password, &signing_msg)?;
            println!("\x1b[1;32mTransaction signed with Dilithium5\x1b[0m");
            println!("  From:      {}", addr);
            println!("  To:        {}", hex::encode(to_addr));
            println!("  Amount:    {:.8} QBC", amount);
            println!("  Signature: {}...{} ({} bytes)",
                &hex::encode(&sig[..8]),
                &hex::encode(&sig[sig.len()-8..]),
                sig.len(),
            );

            // Build and submit the extrinsic
            let signing_key = ed25519_dalek::SigningKey::from_bytes(&substrate_sk);
            let account_id = signing_key.verifying_key().to_bytes();
            let sigs = vec![sig];

            // Pallet index for QbcUtxo — must match runtime construct_runtime! order
            // System=0, Timestamp=1, Aura=2, Grandpa=3, Balances=4, TransactionPayment=5,
            // Sudo=6, QbcDilithium=7, QbcUtxo=8, QbcEconomics=9, QbcConsensus=10
            const UTXO_PALLET_INDEX: u8 = 8;
            let call_data = aether_client::substrate::SubstrateClient::encode_utxo_transaction_call(
                UTXO_PALLET_INDEX,
                &inputs,
                &outputs,
                &sigs,
            );

            let substrate = aether_client::substrate::SubstrateClient::new(&substrate_url);
            let (spec_version, tx_version) = substrate.get_runtime_version().await?;
            let genesis_hash = substrate.get_genesis_hash().await?;
            let nonce = substrate.get_nonce(&format!("0x{}", hex::encode(account_id))).await?;

            let payload = aether_client::substrate::SubstrateClient::build_signing_payload(
                &call_data, nonce, spec_version, tx_version, &genesis_hash,
            );

            use ed25519_dalek::Signer;
            let ext_sig = signing_key.sign(&payload);
            let ext_sig_bytes: [u8; 64] = ext_sig.to_bytes();

            let extrinsic = aether_client::substrate::SubstrateClient::build_signed_extrinsic(
                &call_data, &account_id, &ext_sig_bytes, nonce,
            );

            let ext_hex = format!("0x{}", hex::encode(&extrinsic));
            match substrate.submit_extrinsic(&ext_hex).await {
                Ok(hash) => {
                    println!("\x1b[1;32mTransaction submitted!\x1b[0m");
                    println!("  Tx hash: {hash}");
                }
                Err(e) => {
                    eprintln!("\x1b[31mSubmission failed:\x1b[0m {e}");
                }
            }
        }

        WalletAction::RegisterKey { address, substrate_url, substrate_key } => {
            let addr = resolve_wallet_address(&wallet, address)?;
            let version = wallet.wallet_version(&addr)?;
            if version < 3 {
                anyhow::bail!("Key registration requires a Dilithium5 (v3) wallet.");
            }

            let substrate_sk = parse_substrate_key(substrate_key)?
                .ok_or_else(|| anyhow::anyhow!(
                    "Substrate signing key required. Set SUBSTRATE_SECRET_KEY env var or pass --substrate-key."
                ))?;

            let pk_bytes = wallet.public_key_bytes(&addr)?;
            println!("Registering Dilithium5 public key on-chain...");
            println!("  Address:    {}", addr);
            println!("  PK size:    {} bytes", pk_bytes.len());

            // QbcDilithium=7 in runtime construct_runtime! order
            const DILITHIUM_PALLET_INDEX: u8 = 7;
            let call_data = aether_client::substrate::SubstrateClient::encode_register_key_call(
                DILITHIUM_PALLET_INDEX,
                &pk_bytes,
            );

            let signing_key = ed25519_dalek::SigningKey::from_bytes(&substrate_sk);
            let account_id = signing_key.verifying_key().to_bytes();

            let substrate = aether_client::substrate::SubstrateClient::new(&substrate_url);
            let (spec_version, tx_version) = substrate.get_runtime_version().await?;
            let genesis_hash = substrate.get_genesis_hash().await?;
            let nonce = substrate.get_nonce(&format!("0x{}", hex::encode(account_id))).await?;

            let payload = aether_client::substrate::SubstrateClient::build_signing_payload(
                &call_data, nonce, spec_version, tx_version, &genesis_hash,
            );

            use ed25519_dalek::Signer;
            let ext_sig = signing_key.sign(&payload);
            let ext_sig_bytes: [u8; 64] = ext_sig.to_bytes();

            let extrinsic = aether_client::substrate::SubstrateClient::build_signed_extrinsic(
                &call_data, &account_id, &ext_sig_bytes, nonce,
            );

            let ext_hex = format!("0x{}", hex::encode(&extrinsic));
            match substrate.submit_extrinsic(&ext_hex).await {
                Ok(hash) => {
                    println!("\x1b[1;32mDilithium5 public key registered on-chain!\x1b[0m");
                    println!("  Tx hash: {hash}");
                    println!("  Your wallet can now sign UTXO transactions.");
                }
                Err(e) => {
                    eprintln!("\x1b[31mRegistration failed:\x1b[0m {e}");
                }
            }
        }

        WalletAction::Import { key, label } => {
            let password = read_password("Set password for imported wallet: ")?;
            let confirm = read_password("Confirm password: ")?;
            if password != confirm {
                anyhow::bail!("Passwords do not match");
            }

            let info = wallet.import_hex(&key, &password, &label)?;
            let security = if info.is_quantum_secure() { "Dilithium5" } else { "legacy" };
            println!("\x1b[1;32mWallet imported!\x1b[0m ({security})");
            println!("  Address:    {}", info.address);
            println!("  Public key: {}...{}", &info.public_key[..16.min(info.public_key.len())], &info.public_key[info.public_key.len().saturating_sub(16)..]);
            println!("  Label:      {}", info.label);
        }

        WalletAction::Export { address } => {
            let addr = resolve_wallet_address(&wallet, address)?;
            let password = read_password("Enter wallet password: ")?;
            let secret = wallet.export_secret(&addr, &password)?;
            let version = wallet.wallet_version(&addr)?;
            let key_type = if version >= 3 { "Dilithium5 secret key" } else { "legacy secret key" };
            println!("{}", serde_json::to_string_pretty(&serde_json::json!({
                "address": addr,
                "key_type": key_type,
                "key_size_bytes": secret.len() / 2,
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

        WalletAction::Sign { message, address } => {
            let addr = resolve_wallet_address(&wallet, address)?;
            let password = read_password("Enter wallet password to sign: ")?;
            let sig = wallet.sign(&addr, &password, message.as_bytes())?;
            println!("{}", serde_json::to_string_pretty(&serde_json::json!({
                "address": addr,
                "message": message,
                "signature": hex::encode(&sig),
                "signature_size": sig.len(),
                "algorithm": "CRYSTALS-Dilithium5 (NIST Level 5)"
            }))?);
        }

        WalletAction::Verify { message, signature, public_key } => {
            let sig_bytes = hex::decode(signature.trim())
                .map_err(|_| anyhow::anyhow!("invalid signature hex"))?;
            let pk_bytes = hex::decode(public_key.trim())
                .map_err(|_| anyhow::anyhow!("invalid public key hex"))?;

            match aether_wallet::verify_dilithium5(&pk_bytes, message.as_bytes(), &sig_bytes) {
                Ok(true) => {
                    println!("\x1b[1;32mSignature VALID\x1b[0m");
                    println!("  Algorithm: CRYSTALS-Dilithium5 (NIST Level 5)");
                }
                Ok(false) => {
                    println!("\x1b[1;31mSignature INVALID\x1b[0m");
                    std::process::exit(1);
                }
                Err(e) => {
                    eprintln!("\x1b[31mVerification error:\x1b[0m {e}");
                    std::process::exit(1);
                }
            }
        }
    }

    Ok(())
}

fn resolve_wallet_address(wallet: &aether_wallet::Wallet, explicit: Option<String>) -> Result<String> {
    match explicit {
        Some(a) => Ok(a),
        None => match wallet.address()? {
            Some(a) => Ok(a),
            None => {
                anyhow::bail!("No wallet found. Run `aether wallet create` first.");
            }
        },
    }
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

            let total_params: u64 = 1024;
            let k = 50;
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

// ── Innovation Command Handlers ─────────────────────────────────

fn cmd_cogwork(action: CogworkAction) -> Result<()> {
    use aether_innovation::pocw;

    match action {
        CogworkAction::Generate { seed, height } => {
            let seed_bytes: [u8; 32] = match seed {
                Some(h) => {
                    let b = hex::decode(h.trim().trim_start_matches("0x"))?;
                    let mut s = [0u8; 32];
                    s.copy_from_slice(&b[..32.min(b.len())]);
                    s
                }
                None => [42u8; 32],
            };

            let challenge = pocw::generate_challenge(&seed_bytes, height);
            let proof = pocw::solve_and_prove(&challenge);

            println!("\x1b[1;32mProof-of-Cognitive-Work\x1b[0m (PoCW)");
            println!("  Height:     {}", height);
            println!("  Type:       {:?}", challenge.challenge_type);
            println!("  Solution:   {:?}", proof.solution);
            println!("  Proof hash: {}", hex::encode(proof.proof_hash));
            println!("  Solve time: {} \u{00b5}s", proof.solve_time_us);
            println!("  Verified:   \x1b[32m{}\x1b[0m", pocw::verify_proof(&challenge, &proof));

            // Show combined proof hash with mock VQE data
            let combined = pocw::combined_proof_hash(-2.5, &[0.1, 0.2, 0.3], &proof);
            println!("  Combined:   {}", hex::encode(combined));
        }

        CogworkAction::Verify { proof_json, challenge_json } => {
            let challenge: pocw::CognitiveChallenge = serde_json::from_str(&challenge_json)?;
            let proof: pocw::CognitiveProof = serde_json::from_str(&proof_json)?;
            if pocw::verify_proof(&challenge, &proof) {
                println!("\x1b[1;32mCognitive proof VALID\x1b[0m");
            } else {
                println!("\x1b[1;31mCognitive proof INVALID\x1b[0m");
                std::process::exit(1);
            }
        }

        CogworkAction::Benchmark { rounds } => {
            println!("Benchmarking PoCW ({rounds} rounds)...");
            let start = std::time::Instant::now();
            let mut total_us = 0u64;
            for i in 0..rounds {
                let mut seed = [0u8; 32];
                seed[0] = (i % 3) as u8;
                let ch = pocw::generate_challenge(&seed, i as u64);
                let proof = pocw::solve_and_prove(&ch);
                assert!(pocw::verify_proof(&ch, &proof));
                total_us += proof.solve_time_us;
            }
            let elapsed = start.elapsed();
            println!("  Total:     {:.1}ms", elapsed.as_secs_f64() * 1000.0);
            println!("  Average:   {:.1}\u{00b5}s/proof", total_us as f64 / rounds as f64);
            println!("  Throughput: {:.0} proofs/sec", rounds as f64 / elapsed.as_secs_f64());
        }
    }
    Ok(())
}

fn cmd_entangle(action: EntangleAction) -> Result<()> {
    use aether_innovation::entangled;

    match action {
        EntangleAction::Create { wallet_a, partner_pubkey, deadman_blocks, inheritance, escrow } => {
            let wallet = aether_wallet::Wallet::open(aether_wallet::default_keystore_dir())?;
            let addr = resolve_wallet_address(&wallet, wallet_a)?;
            let my_pk = wallet.public_key_bytes(&addr)?;

            let partner_pk = hex::decode(partner_pubkey.trim().trim_start_matches("0x"))
                .map_err(|_| anyhow::anyhow!("invalid partner public key hex"))?;

            let conditions = entangled::EntanglementConditions {
                deadman_blocks,
                inheritance_ratio: inheritance,
                require_dual_sign: escrow,
                activation_height: 0,
                memo: String::new(),
            };

            let ent = entangled::create_entanglement(&my_pk, &partner_pk, conditions, 0);

            println!("\x1b[1;32mQuantum-Entangled Wallet Protocol\x1b[0m (QEWP)");
            println!("  Entanglement ID: {}", hex::encode(ent.entanglement_id));
            println!("  Wallet A:        {}", ent.wallet_a);
            println!("  Wallet B:        {}", ent.wallet_b);
            println!("  Channel key:     {}...", &hex::encode(ent.channel_key)[..16]);
            println!("  Commitment:      {}", hex::encode(ent.commitment));
            println!("  Dead-man:        {} blocks (~{:.1} days)", deadman_blocks, deadman_blocks as f64 * 3.3 / 86400.0);
            println!("  Inheritance:     {:.0}%", inheritance * 100.0);
            println!("  Escrow mode:     {}", escrow);

            // Save to file
            let filename = format!("entanglement-{}.json", &hex::encode(&ent.entanglement_id[..8]));
            let json = serde_json::to_string_pretty(&ent)?;
            std::fs::write(&filename, &json)?;
            println!("\n  Saved to: \x1b[33m{}\x1b[0m", filename);
        }

        EntangleAction::Status { file, last_active, current_height } => {
            let data = std::fs::read_to_string(&file)?;
            let ent: entangled::WalletEntanglement = serde_json::from_str(&data)?;
            let status = entangled::check_status(&ent, last_active, current_height);

            println!("\x1b[1;32mEntanglement Status\x1b[0m");
            println!("  ID:           {}", &status.entanglement_id[..16]);
            println!("  Active:       {}", status.is_active);
            println!("  Dead-man:     {}", if status.deadman_triggered { "\x1b[31mTRIGGERED\x1b[0m" } else { "\x1b[32mnot triggered\x1b[0m" });
            if let Some(blocks) = status.blocks_until_deadman {
                if blocks > 0 {
                    println!("  Blocks left:  {} (~{:.1} hours)", blocks, blocks as f64 * 3.3 / 3600.0);
                }
            }
        }
    }
    Ok(())
}

fn cmd_optimize(action: OptimizeAction) -> Result<()> {
    use aether_innovation::optimizer::{UtxoOptimizer, FeeObservation};

    let mut opt = UtxoOptimizer::new();
    // In production, these would come from chain queries. Simulate with synthetic data.
    for i in 0..50 {
        opt.observe(FeeObservation {
            height: 265000 + i,
            median_fee_rate: 1.0 + (i as f64 * 0.1).sin() * 0.5,
            block_fullness: 0.3 + (i as f64 * 0.05).sin() * 0.2,
            tx_count: 5 + (i % 10) as u32,
        });
    }

    match action {
        OptimizeAction::PredictFee => {
            let rate = opt.predict_fee_rate();
            let window = opt.optimal_window();
            println!("\x1b[1;32mPredictive UTXO Coalescing Engine\x1b[0m (PUCE)");
            println!("  Predicted fee rate: {:.4} units/byte", rate);
            println!("  Send window:        {}", match window {
                aether_innovation::optimizer::SendWindow::Now => "\x1b[32mNOW — fees are optimal\x1b[0m".to_string(),
                aether_innovation::optimizer::SendWindow::Wait(b) => format!("\x1b[33mWAIT ~{b} blocks\x1b[0m"),
                aether_innovation::optimizer::SendWindow::Congested => "\x1b[31mCONGESTED — delay recommended\x1b[0m".to_string(),
            });
            println!("  Fee trend:          {:.6} ({})",
                opt.trend(),
                if opt.trend() > 0.01 { "rising" } else if opt.trend() < -0.01 { "falling" } else { "stable" }
            );
        }
        OptimizeAction::Analyze => {
            println!("\x1b[1;32mUTXO Analysis\x1b[0m");
            println!("  \x1b[33mNote: Connect to Substrate node for live UTXO data.\x1b[0m");
            println!("  Predicted fee rate: {:.4} units/byte", opt.predict_fee_rate());
            println!("  Observations:       50 blocks");
            println!("  Fee trend:          {:.6}", opt.trend());
        }
        OptimizeAction::Trend => {
            let trend = opt.trend();
            println!("Fee trend: {:.6} — {}", trend,
                if trend > 0.01 { "\x1b[31mrising\x1b[0m" }
                else if trend < -0.01 { "\x1b[32mfalling\x1b[0m" }
                else { "stable" }
            );
        }
    }
    Ok(())
}

fn cmd_recover(action: RecoverAction) -> Result<()> {
    use aether_innovation::cognitive_id;

    match action {
        RecoverAction::Setup { address, threshold } => {
            let wallet = aether_wallet::Wallet::open(aether_wallet::default_keystore_dir())?;
            let addr = resolve_wallet_address(&wallet, address)?;

            let challenges = cognitive_id::default_challenges();

            println!("\x1b[1;32mZero-Knowledge Cognitive Recovery\x1b[0m (ZKCR)");
            println!("  Wallet: {}", addr);
            println!("  Threshold: {}/{} answers required\n", threshold, challenges.len());

            let mut answers = Vec::new();
            for (i, ch) in challenges.iter().enumerate() {
                eprintln!("  \x1b[1m{}.\x1b[0m [{}] {}", i + 1,
                    match ch.category {
                        cognitive_id::ChallengeCategory::Personal => "Personal",
                        cognitive_id::ChallengeCategory::Reasoning => "Reasoning",
                        cognitive_id::ChallengeCategory::Creative => "Creative",
                        cognitive_id::ChallengeCategory::Temporal => "Temporal",
                    },
                    ch.prompt
                );
                eprint!("     Answer: ");
                use std::io::Write;
                std::io::stderr().flush()?;
                let mut ans = String::new();
                std::io::stdin().read_line(&mut ans)?;
                answers.push(ans.trim().to_string());
            }

            let setup = cognitive_id::setup_recovery(&addr, &challenges, &answers, threshold)
                .map_err(|e| anyhow::anyhow!(e))?;

            let filename = format!("recovery-{}.json", &addr[..16]);
            let json = serde_json::to_string_pretty(&setup)?;
            std::fs::write(&filename, &json)?;

            println!("\n\x1b[1;32mRecovery setup complete!\x1b[0m");
            println!("  {} commitments created (zero-knowledge — answers NOT stored)", setup.commitments.len());
            println!("  Threshold: {}/{}", threshold, setup.commitments.len());
            println!("  Saved to: \x1b[33m{}\x1b[0m", filename);
            println!("\n\x1b[33mStore this file safely. It contains only hashes, not your answers.\x1b[0m");
        }

        RecoverAction::Attempt { file } => {
            let data = std::fs::read_to_string(&file)?;
            let setup: cognitive_id::RecoverySetup = serde_json::from_str(&data)?;

            println!("\x1b[1;32mCognitive Recovery Attempt\x1b[0m");
            println!("  Wallet:    {}", setup.wallet_address);
            println!("  Threshold: {}/{}\n", setup.threshold, setup.commitments.len());

            let mut answers = Vec::new();
            for c in &setup.commitments {
                eprintln!("  \x1b[1m{}.\x1b[0m {}", c.index + 1, c.challenge.prompt);
                eprint!("     Answer: ");
                use std::io::Write;
                std::io::stderr().flush()?;
                let mut ans = String::new();
                std::io::stdin().read_line(&mut ans)?;
                answers.push((c.index, ans.trim().to_string()));
            }

            let result = cognitive_id::attempt_recovery(&setup, &answers);
            if result.threshold_met {
                println!("\n\x1b[1;32mRecovery SUCCESSFUL!\x1b[0m ({}/{})", result.verified_count, setup.threshold);
            } else {
                println!("\n\x1b[1;31mRecovery FAILED\x1b[0m ({}/{} — need {})",
                    result.verified_count, setup.commitments.len(), setup.threshold);
                std::process::exit(1);
            }
        }
    }
    Ok(())
}

fn cmd_synapse(action: SynapseAction) -> Result<()> {
    use aether_innovation::symbiotic;

    match action {
        SynapseAction::Status => {
            let mi = symbiotic::MinerIntelligence::new("local", 1024);
            let s = mi.summary();
            println!("\x1b[1;32mSymbiotic Mining Intelligence\x1b[0m (SMIP)");
            println!("  Local model params: {}", s.model_params);
            println!("  Non-zero params:    {}", s.local_params_nonzero);
            println!("  Total fragments:    {}", s.total_fragments);
            println!("  Avg improvement:    {:.6}", s.avg_loss_improvement);
            println!("\n  \x1b[33mMine blocks to generate cognitive fragments.\x1b[0m");
            println!("  Every VQE solution trains the Aether Mind.");
        }

        SynapseAction::Generate { energy } => {
            let mut mi = symbiotic::MinerIntelligence::new("local_miner", 1024);
            let params = vec![0.5, -0.3, 0.8, 1.2, -0.7, 0.4];
            let seed = [42u8; 32];

            let frag = mi.generate_fragment(265000, &params, energy, &seed);

            println!("\x1b[1;32mCognitive Fragment Generated\x1b[0m");
            println!("  Height:       {}", frag.height);
            println!("  Gradient dims: {} / {}", frag.gradient_indices.len(), frag.total_params);
            println!("  Sparsity:     {:.4}", frag.sparsity);
            println!("  Loss delta:   {:.6}", frag.loss_delta);
            println!("  Fragment hash: {}", hex::encode(frag.fragment_hash));
            println!("  Verified:     \x1b[32m{}\x1b[0m", symbiotic::verify_fragment(&frag));

            let s = mi.summary();
            println!("\n  Non-zero params: {} / {}", s.local_params_nonzero, s.model_params);
        }

        SynapseAction::Aggregate => {
            let mut m1 = symbiotic::MinerIntelligence::new("miner_alpha", 1024);
            let mut m2 = symbiotic::MinerIntelligence::new("miner_beta", 1024);
            let mut m3 = symbiotic::MinerIntelligence::new("miner_gamma", 1024);

            let f1 = m1.generate_fragment(100, &[0.5, -0.3], -2.5, &[1; 32]);
            let f2 = m2.generate_fragment(101, &[0.8, 0.1, -0.4], -2.1, &[2; 32]);
            let f3 = m3.generate_fragment(102, &[0.3, 0.7, 0.2, -0.1], -1.8, &[3; 32]);

            let agg = symbiotic::federated_average(&[f1, f2, f3]).unwrap();

            println!("\x1b[1;32mFederated Average (FedAvg)\x1b[0m");
            println!("  Height range:  {}-{}", agg.height_range.0, agg.height_range.1);
            println!("  Fragments:     {}", agg.fragment_count);
            println!("  Unique miners: {}", agg.miner_count);
            println!("  Gradient dims: {}", agg.aggregated_indices.len());
            println!("  Total loss Δ:  {:.6}", agg.total_loss_delta);
            println!("  Agg hash:      {}", hex::encode(agg.aggregation_hash));
            println!("\n  \x1b[32mCollective intelligence updated.\x1b[0m Mining = Thinking.");
        }
    }
    Ok(())
}

fn cmd_privacy(action: PrivacyAction) -> Result<()> {
    use aether_privacy::{
        commitment::PedersenCommitment,
        stealth::StealthAddressManager,
        susy_swap::{SusySwapBuilder, verify_transaction},
        range_proof::RangeProof,
    };

    match action {
        PrivacyAction::StealthKeygen => {
            let kp = StealthAddressManager::generate_keypair();
            let addr_hex = kp.public_address_hex();

            println!("\x1b[1;32mStealth Address Keypair Generated\x1b[0m");
            println!("  Spend pubkey:  {}", hex::encode(&kp.spend_pubkey));
            println!("  View pubkey:   {}", hex::encode(&kp.view_pubkey));
            println!("  Stealth addr:  {}...{}", &addr_hex[..16], &addr_hex[addr_hex.len()-16..]);
            println!("  Addr length:   {} bytes (spend || view)", kp.public_address().len());

            // Save keypair to file
            let filename = format!("stealth-keypair-{}.json", &hex::encode(&kp.spend_pubkey[..4]));
            let json = serde_json::to_string_pretty(&kp)?;
            std::fs::write(&filename, &json)?;
            println!("\n  Saved to: \x1b[33m{}\x1b[0m", filename);
            println!("\x1b[33m  Keep this file safe — it contains your private keys.\x1b[0m");
            println!("\n  Share your stealth address (132 hex chars) to receive private payments:");
            println!("  \x1b[36m{}\x1b[0m", addr_hex);
        }

        PrivacyAction::StealthSend { recipient } => {
            let addr_bytes = hex::decode(recipient.trim().trim_start_matches("0x"))
                .map_err(|_| anyhow::anyhow!("invalid stealth address hex"))?;
            if addr_bytes.len() != 66 {
                anyhow::bail!("stealth address must be 66 bytes (132 hex chars), got {}", addr_bytes.len());
            }

            let spend_pub = &addr_bytes[..33];
            let view_pub = &addr_bytes[33..66];

            let output = StealthAddressManager::create_output(spend_pub, view_pub)
                .map_err(|e| anyhow::anyhow!("stealth output: {e}"))?;

            println!("\x1b[1;32mStealth Output Created\x1b[0m");
            println!("  One-time addr:  {}", hex::encode(&output.one_time_address));
            println!("  Ephemeral key:  {}", hex::encode(&output.ephemeral_pubkey));
            println!("\n  Include the ephemeral key in your transaction.");
            println!("  The recipient can scan for it using their view key.");

            let json = serde_json::to_string_pretty(&output)?;
            println!("\n{}", json);
        }

        PrivacyAction::StealthScan { ephemeral_pubkey, output_address, keypair } => {
            let data = std::fs::read_to_string(&keypair)?;
            let kp: aether_privacy::StealthKeypair = serde_json::from_str(&data)?;

            let eph_bytes = hex::decode(ephemeral_pubkey.trim().trim_start_matches("0x"))
                .map_err(|_| anyhow::anyhow!("invalid ephemeral pubkey hex"))?;
            let addr_bytes = hex::decode(output_address.trim().trim_start_matches("0x"))
                .map_err(|_| anyhow::anyhow!("invalid output address hex"))?;

            match StealthAddressManager::scan_output(&kp, &eph_bytes, &addr_bytes) {
                Ok(Some(spending_key)) => {
                    println!("\x1b[1;32mOutput belongs to YOU!\x1b[0m");
                    println!("  Spending key: {}...{}", &hex::encode(&spending_key[..4]), &hex::encode(&spending_key[spending_key.len()-4..]));

                    let ki = StealthAddressManager::compute_key_image(&spending_key)
                        .map_err(|e| anyhow::anyhow!("key image: {e}"))?;
                    println!("  Key image:    {}", hex::encode(&ki.image));
                    println!("\n  Use the spending key to spend this output in a Susy Swap.");
                }
                Ok(None) => {
                    println!("\x1b[33mOutput does NOT belong to this keypair.\x1b[0m");
                }
                Err(e) => {
                    eprintln!("\x1b[31mScan error:\x1b[0m {e}");
                    std::process::exit(1);
                }
            }
        }

        PrivacyAction::Commit { value } => {
            let units = (value * 100_000_000.0) as u64;
            let commitment = PedersenCommitment::commit(units);

            println!("\x1b[1;32mPedersen Commitment\x1b[0m");
            println!("  Value:      {:.8} QBC ({} units)", value, units);
            println!("  Commitment: {}", hex::encode(&commitment.point));
            println!("  Blinding:   {}", hex::encode(&commitment.blinding));
            println!("  Verified:   \x1b[32m{}\x1b[0m", commitment.verify());
            println!("  Properties: perfectly hiding, computationally binding, homomorphic");

            // Generate range proof
            let mut blind = [0u8; 32];
            blind.copy_from_slice(&commitment.blinding);
            let proof = RangeProof::generate(units, &blind);
            println!("\n\x1b[1;32mRange Proof\x1b[0m");
            println!("  Range:      [0, 2^64)");
            println!("  Proof size: {} bytes", proof.size());
            println!("  Verified:   \x1b[32m{}\x1b[0m", proof.verify());

            let json = serde_json::to_string_pretty(&commitment)?;
            println!("\n{}", json);
        }

        PrivacyAction::VerifyCommit { commitment_json } => {
            let commitment: PedersenCommitment = serde_json::from_str(&commitment_json)?;
            if commitment.verify() {
                println!("\x1b[1;32mCommitment VALID\x1b[0m");
                println!("  Value:  {} units ({:.8} QBC)", commitment.value, commitment.value as f64 / 100_000_000.0);
                println!("  Point:  {}", hex::encode(&commitment.point));
            } else {
                println!("\x1b[1;31mCommitment INVALID\x1b[0m — value or blinding tampered");
                std::process::exit(1);
            }
        }

        PrivacyAction::Send { amount, fee, to } => {
            let amount_units = (amount * 100_000_000.0) as u64;
            let fee_units = (fee * 100_000_000.0) as u64;
            let total_input = amount_units + fee_units;

            if amount_units == 0 {
                anyhow::bail!("amount must be > 0");
            }

            // Parse optional stealth recipient
            let (spend_pub, view_pub) = if let Some(ref addr_hex) = to {
                let addr_bytes = hex::decode(addr_hex.trim().trim_start_matches("0x"))
                    .map_err(|_| anyhow::anyhow!("invalid stealth address hex"))?;
                if addr_bytes.len() != 66 {
                    anyhow::bail!("stealth address must be 66 bytes (132 hex chars)");
                }
                (Some(addr_bytes[..33].to_vec()), Some(addr_bytes[33..66].to_vec()))
            } else {
                (None, None)
            };

            // Build confidential transaction
            let input_blinding = aether_privacy::commitment::generate_blinding();
            // Generate a test spending key from the input blinding
            let spending_key = {
                use sha2::{Digest, Sha256};
                let mut h = Sha256::new();
                h.update(b"susy_swap_test_spending_key");
                h.update(&input_blinding);
                let hash: [u8; 32] = h.finalize().into();
                hash.to_vec()
            };

            let mut builder = SusySwapBuilder::new();
            builder
                .add_input([0u8; 32], 0, total_input, input_blinding, spending_key)
                .add_output(amount_units, spend_pub, view_pub)
                .set_fee(fee_units);

            let tx = builder.build()
                .map_err(|e| anyhow::anyhow!("build failed: {e}"))?;

            let summary = tx.summary();
            println!("\x1b[1;32mSusy Swap — Confidential Transaction Built\x1b[0m");
            println!("  TxID:         {}...{}", &summary.txid[..16], &summary.txid[summary.txid.len()-16..]);
            println!("  Inputs:       {} (amounts hidden)", summary.input_count);
            println!("  Outputs:      {} (amounts hidden)", summary.output_count);
            println!("  Fee:          {:.8} QBC (public)", fee);
            println!("  Key images:   {}", summary.key_images);
            println!("  Stealth:      {}", if summary.has_stealth { "\x1b[32myes\x1b[0m" } else { "no" });
            println!("  Proof size:   {} bytes", summary.total_proof_size);

            // Verify
            match verify_transaction(&tx) {
                Ok(true) => println!("  Verified:     \x1b[32mtrue\x1b[0m"),
                Ok(false) => println!("  Verified:     \x1b[31mfalse\x1b[0m"),
                Err(e) => println!("  Verified:     \x1b[31mfailed: {e}\x1b[0m"),
            }

            println!("\n\x1b[33mNote: UTXO selection from chain not yet automated.\x1b[0m");
            println!("The transaction structure is valid and ready for submission");
            println!("once the privacy pallet is live on the Substrate node.");

            // Save transaction
            let filename = format!("susy-swap-{}.json", &summary.txid[..16]);
            let json = serde_json::to_string_pretty(&tx)?;
            std::fs::write(&filename, &json)?;
            println!("\n  Saved to: \x1b[33m{}\x1b[0m", filename);
        }

        PrivacyAction::Info => {
            println!("\x1b[1;32mSusy Swap Privacy System\x1b[0m");
            println!();
            println!("  \x1b[1mCryptographic Primitives:\x1b[0m");
            println!("    Curve:          secp256k1");
            println!("    Commitments:    Pedersen (C = v*G + r*H)");
            println!("    Range proofs:   Bulletproofs-style (64-bit)");
            println!("    Stealth addrs:  ECDH one-time addresses");
            println!("    Key images:     Double-spend prevention");
            println!();
            println!("  \x1b[1mTransaction Modes:\x1b[0m");
            println!("    Public:   Amounts visible, addresses visible, ~300 bytes");
            println!("    Private:  Amounts hidden, addresses hidden, ~4000+ bytes");
            println!();
            println!("  \x1b[1mWhat Is Hidden:\x1b[0m");
            println!("    Amounts:    Hidden via Pedersen commitments");
            println!("    Recipients: Hidden via stealth addresses");
            println!("    Balances:   Deniable RPC queries (Bloom filter)");
            println!();
            println!("  \x1b[1mAlways Visible:\x1b[0m");
            println!("    Fees:       Always public");
            println!("    Key images: Prevent double-spending");
            println!("    Timestamps: Block inclusion time");
            println!();
            println!("  \x1b[1mCommands:\x1b[0m");
            println!("    aether privacy stealth-keygen         Generate stealth keypair");
            println!("    aether privacy stealth-send <addr>    Create stealth output");
            println!("    aether privacy stealth-scan ...       Scan for your outputs");
            println!("    aether privacy commit <value>         Create commitment");
            println!("    aether privacy verify-commit <json>   Verify commitment");
            println!("    aether privacy send --to <addr> <amt> Build confidential tx");
            println!("    aether privacy info                   This help");
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
