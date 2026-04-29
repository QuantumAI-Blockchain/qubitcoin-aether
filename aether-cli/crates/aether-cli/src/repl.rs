use std::sync::Arc;
use std::time::Duration;

use anyhow::Result;
use crossterm::event::{self, Event, KeyCode, KeyEvent, KeyModifiers};
use crossterm::terminal::{self, EnterAlternateScreen, LeaveAlternateScreen};
use crossterm::ExecutableCommand;
use ratatui::backend::CrosstermBackend;
use ratatui::Terminal;
use tokio::sync::mpsc;

use aether_client::{AetherClient, ChatResponse, ChatTurn};
use aether_miner::{MinerConfig, MinerHandle};
use aether_tui::chat::Role;
use aether_tui::status::MiningStatus;
use aether_tui::App;

/// Result of an async chat request completing in the background.
enum ChatResult {
    Ok(ChatResponse),
    Err(String),
}

/// Run the interactive TUI REPL.
pub async fn run(client: AetherClient, miner_config: Option<MinerConfig>) -> Result<()> {
    // Setup terminal
    terminal::enable_raw_mode()?;
    let mut stdout = std::io::stdout();
    stdout.execute(EnterAlternateScreen)?;
    let backend = CrosstermBackend::new(stdout);
    let mut terminal = Terminal::new(backend)?;

    let mut app = App::new();

    // Start miner if configured
    let miner_handle: Option<MinerHandle> = miner_config.map(aether_miner::start);

    // Initial health poll
    if let Ok(health) = client.health().await {
        app.status.chain_height = health.chain_height;
        app.status.phi = health.phi;
        app.status.knowledge_vectors = health.knowledge_vectors;
        app.status.connected = true;
    }

    // Try to load wallet address
    if let Ok(wallet) = aether_wallet::Wallet::open(aether_wallet::default_keystore_dir()) {
        if let Ok(Some(addr)) = wallet.address() {
            app.status.wallet_addr = Some(addr);
        }
    }

    // Load gates
    if let Ok(gates) = client.gates().await {
        app.status.gates_passed = gates.gates_passed;
    }

    let mut last_poll = std::time::Instant::now();
    let poll_interval = Duration::from_secs(5);

    // Conversation session state — maintained across the REPL lifetime
    let session_id: Arc<tokio::sync::Mutex<Option<String>>> = Arc::new(tokio::sync::Mutex::new(None));
    let chat_history: Arc<tokio::sync::Mutex<Vec<ChatTurn>>> = Arc::new(tokio::sync::Mutex::new(Vec::new()));

    // Channel for receiving async chat responses without blocking the UI
    let (chat_tx, mut chat_rx) = mpsc::channel::<ChatResult>(4);

    loop {
        // Draw
        terminal.draw(|f| app.draw(f))?;

        // Check for completed chat responses (non-blocking)
        while let Ok(result) = chat_rx.try_recv() {
            app.chat.waiting = false;
            match result {
                ChatResult::Ok(resp) => {
                    // Store assistant response in local history
                    chat_history.lock().await.push(ChatTurn {
                        role: "assistant".into(),
                        content: resp.response.clone(),
                    });
                    // Update session_id from server response
                    if let Some(sid) = &resp.session_id {
                        *session_id.lock().await = Some(sid.clone());
                    }
                    app.chat.push(Role::Aether, resp.response);
                    app.status.chain_height = resp.chain_height;
                    app.status.phi = resp.phi;
                    app.status.knowledge_vectors = resp.knowledge_vectors;
                    app.status.connected = true;
                }
                ChatResult::Err(e) => {
                    app.chat.push(Role::System, format!("Error: {e}"));
                    app.status.connected = false;
                }
            }
        }

        // Update mining stats
        if let Some(ref handle) = miner_handle {
            let stats = handle.stats();
            app.status.mining = MiningStatus::Running {
                hashrate: stats.attempts_total as f64
                    / last_poll.elapsed().as_secs_f64().max(1.0),
                blocks_found: stats.blocks_found,
            };
        }

        // Poll health every 5s
        if last_poll.elapsed() >= poll_interval {
            last_poll = std::time::Instant::now();
            let client = client.clone();
            // Non-blocking health poll
            match tokio::time::timeout(Duration::from_secs(3), client.health()).await {
                Ok(Ok(health)) => {
                    app.status.chain_height = health.chain_height;
                    app.status.phi = health.phi;
                    app.status.knowledge_vectors = health.knowledge_vectors;
                    app.status.connected = true;
                }
                _ => {
                    app.status.connected = false;
                }
            }
        }

        // Handle input events (50ms timeout for responsive UI)
        if event::poll(Duration::from_millis(50))? {
            if let Event::Key(key) = event::read()? {
                if handle_key(&mut app, key, &client, &miner_handle, &chat_tx, &session_id, &chat_history).await? {
                    break;
                }
            }
        }
    }

    // Cleanup
    if let Some(handle) = miner_handle {
        handle.stop();
    }
    terminal::disable_raw_mode()?;
    std::io::stdout().execute(LeaveAlternateScreen)?;
    Ok(())
}

async fn handle_key(
    app: &mut App,
    key: KeyEvent,
    client: &AetherClient,
    _miner: &Option<MinerHandle>,
    chat_tx: &mpsc::Sender<ChatResult>,
    session_id: &Arc<tokio::sync::Mutex<Option<String>>>,
    chat_history: &Arc<tokio::sync::Mutex<Vec<ChatTurn>>>,
) -> Result<bool> {
    match key.code {
        // Quit
        KeyCode::Char('c') if key.modifiers.contains(KeyModifiers::CONTROL) => {
            return Ok(true);
        }
        KeyCode::Char('d') if key.modifiers.contains(KeyModifiers::CONTROL) => {
            if app.input.content.is_empty() {
                return Ok(true);
            }
        }

        // Submit message
        KeyCode::Enter => {
            let text = app.input.take();
            if text.is_empty() {
                return Ok(false);
            }

            // Handle slash commands
            if text.starts_with('/') {
                return Ok(handle_command(app, &text, client, session_id, chat_history).await?);
            }

            // Don't allow sending while waiting for a response
            if app.chat.waiting {
                app.input.content = text;
                return Ok(false);
            }

            // Send chat message — spawn in background so UI stays responsive
            app.chat.push(Role::User, text.clone());
            app.chat.waiting = true;

            // Record user turn in local history
            chat_history.lock().await.push(ChatTurn {
                role: "user".into(),
                content: text.clone(),
            });

            let client = client.clone();
            let tx = chat_tx.clone();
            let sid = session_id.lock().await.clone();
            let history_snapshot = chat_history.lock().await.clone();
            tokio::spawn(async move {
                match client.chat_with_session(&text, 0.7, 5000, sid, Some(history_snapshot)).await {
                    Ok(resp) => {
                        let _ = tx.send(ChatResult::Ok(resp)).await;
                    }
                    Err(e) => {
                        let _ = tx.send(ChatResult::Err(e.to_string())).await;
                    }
                }
            });
        }

        // Kill input line
        KeyCode::Char('u') if key.modifiers.contains(KeyModifiers::CONTROL) => {
            app.input.clear();
        }

        // Text input
        KeyCode::Char(c) => {
            app.input.insert(c);
        }
        KeyCode::Backspace => {
            app.input.backspace();
        }
        KeyCode::Delete => {
            app.input.delete();
        }
        KeyCode::Left => {
            app.input.move_left();
        }
        KeyCode::Right => {
            app.input.move_right();
        }
        KeyCode::Home => {
            app.input.home();
        }
        KeyCode::End => {
            app.input.end();
        }

        // Scroll chat
        KeyCode::PageUp => {
            app.chat.scroll_up(10);
        }
        KeyCode::PageDown => {
            app.chat.scroll_down(10);
        }
        KeyCode::Up if key.modifiers.contains(KeyModifiers::CONTROL) => {
            app.chat.scroll_up(3);
        }
        KeyCode::Down if key.modifiers.contains(KeyModifiers::CONTROL) => {
            app.chat.scroll_down(3);
        }

        _ => {}
    }

    Ok(false)
}

async fn handle_command(
    app: &mut App,
    cmd: &str,
    client: &AetherClient,
    session_id: &Arc<tokio::sync::Mutex<Option<String>>>,
    chat_history: &Arc<tokio::sync::Mutex<Vec<ChatTurn>>>,
) -> Result<bool> {
    let parts: Vec<&str> = cmd.trim().splitn(2, ' ').collect();
    let command = parts[0].to_lowercase();

    match command.as_str() {
        "/quit" | "/exit" | "/q" => return Ok(true),

        "/clear" => {
            app.chat.messages.clear();
            // Reset conversation memory — start fresh session
            *session_id.lock().await = None;
            chat_history.lock().await.clear();
            app.chat.push(
                Role::System,
                "Chat cleared. New conversation session started.".into(),
            );
        }

        "/status" => {
            match client.health().await {
                Ok(health) => {
                    let msg = format!(
                        "Status: {}\nModel: {} ({})\nParameters: {}M | Memory: {}MB\nVectors: {} | Phi: {:.6}\nHeight: {}\nEmotions: curiosity={:.2} wonder={:.2} satisfaction={:.2}",
                        health.status, health.model, health.architecture,
                        health.parameters / 1_000_000, health.memory_mb,
                        health.knowledge_vectors, health.phi,
                        health.chain_height,
                        health.emotional_state.curiosity,
                        health.emotional_state.wonder,
                        health.emotional_state.satisfaction,
                    );
                    app.chat.push(Role::System, msg);
                }
                Err(e) => {
                    app.chat.push(Role::System, format!("Cannot reach Aether Mind: {e}"));
                }
            }
        }

        "/info" => {
            match client.info().await {
                Ok(info) => {
                    let mut msg = format!(
                        "Aether Mind v{}\n{} — {} layers, {} Sephirot heads, {} global heads\n{} parameters | {} vectors | phi={:.6}\n\nSephirot:",
                        info.version, info.architecture, info.num_layers,
                        info.num_sephirot_heads, info.num_global_heads,
                        info.parameters, info.knowledge_vectors, info.phi,
                    );
                    for s in &info.sephirot {
                        msg.push_str(&format!(
                            "\n  {} — {} (mass: {:.2})",
                            s.name, s.function, s.higgs_mass
                        ));
                    }
                    app.chat.push(Role::System, msg);
                }
                Err(e) => {
                    app.chat.push(Role::System, format!("Error: {e}"));
                }
            }
        }

        "/gates" => {
            match client.gates().await {
                Ok(gates) => {
                    let mut msg = format!("Gates passed: {}/10\n", gates.gates_passed);
                    for g in &gates.gates {
                        let icon = if g.passed { "[x]" } else { "[ ]" };
                        msg.push_str(&format!("  {icon} Gate {}: {}\n", g.gate, g.name));
                    }
                    app.chat.push(Role::System, msg);
                    app.status.gates_passed = gates.gates_passed;
                }
                Err(e) => {
                    app.chat.push(Role::System, format!("Error: {e}"));
                }
            }
        }

        "/search" => {
            if let Some(query) = parts.get(1) {
                match client.knowledge_search(query, 5).await {
                    Ok(resp) => {
                        if resp.results.is_empty() {
                            app.chat.push(Role::System, "No results found.".into());
                        } else {
                            let mut msg = format!("Found {} results:\n", resp.total);
                            for (i, r) in resp.results.iter().enumerate() {
                                let text = if r.text.len() > 150 {
                                    format!("{}...", &r.text[..150])
                                } else {
                                    r.text.clone()
                                };
                                msg.push_str(&format!(
                                    "  {}. [domain {}] (sim: {:.3}) {}\n",
                                    i + 1,
                                    r.domain,
                                    r.similarity,
                                    text,
                                ));
                            }
                            app.chat.push(Role::System, msg);
                        }
                    }
                    Err(e) => {
                        app.chat.push(Role::System, format!("Error: {e}"));
                    }
                }
            } else {
                app.chat.push(Role::System, "Usage: /search <query>".into());
            }
        }

        "/wallet" => {
            match aether_wallet::Wallet::open(aether_wallet::default_keystore_dir()) {
                Ok(wallet) => {
                    if let Ok(Some(addr)) = wallet.address() {
                        app.chat.push(Role::System, format!("Wallet address: {addr}"));
                    } else {
                        app.chat.push(
                            Role::System,
                            "No wallet configured. Run `aether wallet create` from your shell.".into(),
                        );
                    }
                }
                Err(e) => {
                    app.chat.push(Role::System, format!("Wallet error: {e}"));
                }
            }
        }

        "/export" => {
            // Export chat history to file
            let path = dirs::data_dir()
                .unwrap_or_else(|| std::path::PathBuf::from("."))
                .join("aether-cli")
                .join("chat_export.txt");
            if let Err(e) = export_chat(&app.chat.messages, &path) {
                app.chat.push(Role::System, format!("Export failed: {e}"));
            } else {
                app.chat.push(
                    Role::System,
                    format!("Chat exported to {}", path.display()),
                );
            }
        }

        "/help" | "/?" => {
            app.chat.push(
                Role::System,
                "Commands:\n  /status    — Aether Mind health + chain stats\n  /info      — Model architecture details\n  /gates     — 10-Gate milestone status\n  /search Q  — Search knowledge fabric\n  /gradient  — Gradient aggregation status\n  /rewards   — Your earned gradient rewards\n  /pool      — Reward pool status\n  /wallet    — Show wallet address\n  /export    — Export chat to file\n  /clear     — Clear chat history\n  /quit      — Exit\n\nShortcuts:\n  Ctrl+C     — Exit\n  Ctrl+U     — Clear input line\n  PgUp/PgDn  — Scroll chat\n  Ctrl+Up/Dn — Scroll chat (3 lines)".into(),
            );
        }

        "/gradient" | "/gradients" => {
            match client.gradient_status().await {
                Ok(status) => {
                    let msg = format!(
                        "Gradient Pool:\n  Queued: {} peers\n  Delta norm: {:.6}\n  Dimensions: {}\n  Validation loss: {:.6}{}",
                        status.peer_gradients_queued,
                        status.embedding_delta_norm,
                        status.embedding_delta_size,
                        status.current_validation_loss,
                        if status.peer_gradients_queued >= 2 { "\n  FedAvg: ARMED" } else { "" },
                    );
                    app.chat.push(Role::System, msg);
                }
                Err(e) => {
                    app.chat.push(Role::System, format!("Error: {e}"));
                }
            }
        }

        "/rewards" => {
            // Show rewards for current wallet
            let miner_id = app.status.wallet_addr.clone().unwrap_or_default();
            if miner_id.is_empty() {
                app.chat.push(Role::System, "No wallet configured. Run `aether wallet create`.".into());
            } else {
                match client.rewards(&miner_id).await {
                    Ok(r) => {
                        let msg = format!(
                            "Gradient Rewards (miner: {})\n  Earned:    {:.8} QBC\n  Claimed:   {:.8} QBC\n  Unclaimed: {:.8} QBC\n  Submits:   {}\n  Avg improvement: {:.4}",
                            r.miner_id, r.earned_qbc, r.claimed_qbc, r.unclaimed_qbc,
                            r.submissions, r.avg_improvement_ratio,
                        );
                        app.chat.push(Role::System, msg);
                    }
                    Err(e) => {
                        app.chat.push(Role::System, format!("Error: {e}"));
                    }
                }
            }
        }

        "/pool" => {
            match client.reward_pool().await {
                Ok(p) => {
                    let msg = format!(
                        "Reward Pool:\n  Address: {}\n  Balance: {:.2} QBC\n  Distributed: {:.8} QBC\n  Miners: {}\n  Submissions: {}\n  Base reward: {:.4} QBC",
                        p.pool_address, p.pool_balance_qbc, p.total_distributed_qbc,
                        p.total_miners, p.total_submissions, p.base_reward_qbc,
                    );
                    app.chat.push(Role::System, msg);
                }
                Err(e) => {
                    app.chat.push(Role::System, format!("Error: {e}"));
                }
            }
        }

        _ => {
            app.chat.push(
                Role::System,
                format!("Unknown command: {command}. Type /help for available commands."),
            );
        }
    }

    Ok(false)
}

fn export_chat(
    messages: &[aether_tui::chat::ChatMessage],
    path: &std::path::Path,
) -> Result<()> {
    use std::io::Write;
    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent)?;
    }
    let mut f = std::fs::File::create(path)?;
    for msg in messages {
        let role = match msg.role {
            Role::User => "You",
            Role::Aether => "Aether",
            Role::System => "System",
            Role::Welcome => continue, // skip banner in exports
        };
        writeln!(f, "[{role}]")?;
        writeln!(f, "{}\n", msg.content)?;
    }
    Ok(())
}
