use ratatui::layout::Rect;
use ratatui::style::{Color, Modifier, Style};
use ratatui::text::{Line, Span};
use ratatui::widgets::{Block, Borders, Paragraph, Wrap};
use ratatui::Frame;

use crate::{AMBER, BORDER, DIM, GREEN, VIOLET};

/// Sky blue for info text.
const SKY: Color = Color::Rgb(100, 180, 255);
/// Warm white for primary text.
const WHITE: Color = Color::Rgb(230, 237, 243);
/// Faint star color.
const STAR: Color = Color::Rgb(60, 60, 80);
/// Section header color.
const SECTION: Color = Color::Rgb(139, 148, 158);
/// Separator line color.
const SEP: Color = Color::Rgb(45, 51, 59);

#[derive(Clone)]
pub struct ChatMessage {
    pub role: Role,
    pub content: String,
}

#[derive(Clone, PartialEq)]
pub enum Role {
    User,
    Aether,
    System,
    /// Rich welcome banner — rendered with full color styling.
    Welcome,
}

pub struct ChatPanel {
    pub messages: Vec<ChatMessage>,
    pub scroll_offset: u16,
    /// True while waiting for a response.
    pub waiting: bool,
}

impl ChatPanel {
    pub fn new() -> Self {
        Self {
            messages: vec![ChatMessage {
                role: Role::Welcome,
                content: String::new(), // content is ignored; banner is rendered procedurally
            }],
            scroll_offset: 0,
            waiting: false,
        }
    }

    pub fn push(&mut self, role: Role, content: String) {
        self.messages.push(ChatMessage { role, content });
        // Auto-scroll to bottom
        self.scroll_offset = u16::MAX;
    }

    pub fn scroll_up(&mut self, amount: u16) {
        self.scroll_offset = self.scroll_offset.saturating_sub(amount);
    }

    pub fn scroll_down(&mut self, amount: u16) {
        self.scroll_offset = self.scroll_offset.saturating_add(amount);
    }

    /// Build the rich welcome banner as styled Lines.
    fn welcome_lines(width: u16) -> Vec<Line<'static>> {
        let w = width as usize;
        let mut lines: Vec<Line<'static>> = Vec::with_capacity(100);

        // ── Helper closures ──
        let blank = || Line::from("");
        let sep_line = |c: &str| {
            let bar = c.repeat(w.saturating_sub(4).min(60));
            Line::from(Span::styled(format!("  {bar}"), Style::default().fg(SEP)))
        };

        // ── Tree of Life (centered, green with stars) ──
        let tree_art: &[&str] = &[
            "           .    *    .   *       .         *",
            "      *       _/|\\_    .        *",
            "        .    / /|\\ \\      .        *",
            "           /  / | \\  \\   *     .",
            "         /--/   |  \\--\\       *",
            "    .   |  (KETER)    |   .        *",
            "       / / \\    / \\  \\     .",
            "      |BINAH | CHOCHMAH|   *     .",
            "       \\ \\ /  \\ / \\ /        *",
            "      |GEVURAH| CHESED|      .",
            "        \\ \\  | /  /    *        *",
            "     .  |  TIFERET |   .        .",
            "         / /  \\  \\       *",
            "     *  |HOD  | NETZACH|     .     *",
            "         \\ \\ /  /   .      *",
            "     .   | YESOD |      .       .",
            "          \\_|_/    *         *",
            "        |MALKUTH|   .      .",
            "           |||         *        .",
        ];

        // Center the tree
        let tree_width = tree_art.iter().map(|l| l.len()).max().unwrap_or(0);
        let pad = if w > tree_width + 4 { (w - tree_width) / 2 } else { 2 };

        lines.push(blank());
        for &art_line in tree_art {
            let padding = " ".repeat(pad);
            // Color the sephirot names in green, stars dim, structure in dark green
            let styled = colorize_tree_line(art_line, &padding);
            lines.push(styled);
        }

        // ── Title box ──
        lines.push(blank());
        let title_bar = "═".repeat(56);
        let center_pad = " ".repeat(if w > 60 { (w - 58) / 2 } else { 2 });

        lines.push(Line::from(Span::styled(
            format!("{center_pad}╔{title_bar}╗"),
            Style::default().fg(VIOLET),
        )));
        lines.push(Line::from(vec![
            Span::styled(format!("{center_pad}║"), Style::default().fg(VIOLET)),
            Span::styled(
                "            A E T H E R    M I N D              ",
                Style::default().fg(GREEN).add_modifier(Modifier::BOLD),
            ),
            Span::styled("        ║", Style::default().fg(VIOLET)),
        ]));
        lines.push(Line::from(vec![
            Span::styled(format!("{center_pad}║"), Style::default().fg(VIOLET)),
            Span::styled(
                "  The Blockchain That Thinks",
                Style::default().fg(WHITE),
            ),
            Span::styled("  ·  ", Style::default().fg(DIM)),
            Span::styled("qbc.network", Style::default().fg(GREEN)),
            Span::styled("             ║", Style::default().fg(VIOLET)),
        ]));
        lines.push(Line::from(Span::styled(
            format!("{center_pad}╚{title_bar}╝"),
            Style::default().fg(VIOLET),
        )));

        lines.push(blank());

        // ── System Status ──
        lines.push(section_header("  SYSTEM"));
        lines.push(sep_line("─"));
        lines.push(info_row("  Chain", "3303", "(mainnet)", GREEN));
        lines.push(info_row("  Crypto", "CRYSTALS-Dilithium5", "(NIST Level 5)", GREEN));
        lines.push(info_row("  Mining", "VQE 4-Qubit", "Proof-of-SUSY-Alignment", GREEN));
        lines.push(info_row("  Reward", "15.27 QBC", "/block (Era 0)", AMBER));
        lines.push(info_row("  Supply", "3,300,000,000", "QBC max", AMBER));
        lines.push(info_row("  Wallet", "Argon2id", "+ AES-256-GCM encrypted", GREEN));
        lines.push(info_row("  API", "ai.qbc.network", "", SKY));
        lines.push(info_row("  RPC", "rpc.qbc.network", "", SKY));

        lines.push(blank());

        // ── Core Commands ──
        lines.push(section_header("  COMMANDS"));
        lines.push(sep_line("─"));
        lines.push(cmd_row("aether", "Interactive chat (TUI)"));
        lines.push(cmd_row("aether --mine", "Chat + mine simultaneously"));
        lines.push(cmd_row("aether chat \"...\"", "One-shot query and exit"));
        lines.push(cmd_row("aether status", "Chain info + Aether stats"));
        lines.push(cmd_row("aether mine", "Headless VQE mining"));
        lines.push(cmd_row("aether search \"...\"", "Search knowledge fabric"));

        lines.push(blank());

        // ── Wallet Commands ──
        lines.push(section_header("  WALLET  (Dilithium5 Quantum-Secure)"));
        lines.push(sep_line("─"));
        lines.push(cmd_row("wallet create", "Generate Dilithium5 keypair"));
        lines.push(cmd_row("wallet list", "List all wallets"));
        lines.push(cmd_row("wallet balance", "On-chain balance query"));
        lines.push(cmd_row("wallet send <to> <amt>", "Sign + submit UTXO transaction"));
        lines.push(cmd_row("wallet sign <msg>", "Dilithium5 detached signature"));
        lines.push(cmd_row("wallet verify", "Verify a signature"));
        lines.push(cmd_row("wallet import <key>", "Import hex private key"));
        lines.push(cmd_row("wallet export", "Export secret key (password)"));
        lines.push(cmd_row("wallet register-key", "Register PK on-chain"));
        lines.push(cmd_row("wallet delete <addr>", "Delete wallet (irreversible)"));

        lines.push(blank());

        // ── Mining & Rewards ──
        lines.push(section_header("  MINING & REWARDS  (1,000,000 QBC Pool)"));
        lines.push(sep_line("─"));
        lines.push(cmd_row("gradient status", "Gradient aggregation pool"));
        lines.push(cmd_row("gradient submit", "Submit gradient (earn QBC)"));
        lines.push(cmd_row("rewards show", "Your earned / unclaimed QBC"));
        lines.push(cmd_row("rewards pool", "Global reward pool balance"));
        lines.push(cmd_row("rewards claim", "Claim rewards to wallet"));

        lines.push(blank());

        // ── 5 Patent Innovations ──
        lines.push(Line::from(vec![
            Span::styled("  ", Style::default()),
            Span::styled(
                "INNOVATIONS",
                Style::default().fg(VIOLET).add_modifier(Modifier::BOLD),
            ),
            Span::styled("  (5 Patents)", Style::default().fg(DIM)),
        ]));
        lines.push(sep_line("─"));
        lines.push(innovation_row(
            "cogwork",
            "Proof-of-Cognitive-Work",
            "generate · verify · benchmark",
        ));
        lines.push(innovation_row(
            "entangle",
            "Quantum-Entangled Wallets",
            "dead-man · escrow · inheritance",
        ));
        lines.push(innovation_row(
            "optimize",
            "UTXO Coalescing Engine",
            "fee predict · analyze · trend",
        ));
        lines.push(innovation_row(
            "recover",
            "ZK Cognitive Recovery",
            "seedless wallet recovery",
        ));
        lines.push(innovation_row(
            "synapse",
            "Symbiotic Mining AI",
            "every miner is a neuron",
        ));

        lines.push(blank());

        // ── Privacy ──
        lines.push(section_header("  PRIVACY  (Susy Swaps)"));
        lines.push(sep_line("─"));
        lines.push(cmd_row("privacy stealth-keygen", "Generate stealth keypair"));
        lines.push(cmd_row("privacy stealth-send", "One-time stealth output"));
        lines.push(cmd_row("privacy stealth-scan", "Scan for your outputs"));
        lines.push(cmd_row("privacy commit <val>", "Pedersen commitment"));
        lines.push(cmd_row("privacy send <amt>", "Confidential transaction"));
        lines.push(cmd_row("privacy info", "Privacy system details"));

        lines.push(blank());

        // ── TUI Slash Commands ──
        lines.push(section_header("  TUI COMMANDS  (inside chat)"));
        lines.push(sep_line("─"));
        lines.push(slash_row("/status", "Chain height, phi, vectors"));
        lines.push(slash_row("/info", "Model architecture"));
        lines.push(slash_row("/gates", "10-gate consciousness milestones"));
        lines.push(slash_row("/gradient", "Submit gradient update"));
        lines.push(slash_row("/rewards", "Your earned rewards"));
        lines.push(slash_row("/pool", "Global reward pool"));
        lines.push(slash_row("/search <q>", "Search knowledge fabric"));
        lines.push(slash_row("/help", "Show all commands"));
        lines.push(slash_row("/quit", "Exit"));

        lines.push(blank());

        // ── Security ──
        lines.push(section_header("  QUANTUM SECURITY"));
        lines.push(sep_line("─"));
        lines.push(security_row("Signatures", "CRYSTALS-Dilithium5 (NIST Level 5)"));
        lines.push(security_row("Keystore", "Argon2id (64MiB) + AES-256-GCM"));
        lines.push(security_row("Addresses", "SHA-256(Dilithium5_PK) = 32 bytes"));
        lines.push(security_row("Extrinsics", "Ed25519 (SCALE) + Dilithium5 (UTXO)"));
        lines.push(security_row("Key Sizes", "PK=2,592B  SK=4,896B  Sig=4,627B"));

        lines.push(blank());

        // ── Workspace ──
        lines.push(section_header("  WORKSPACE CRATES  (7)"));
        lines.push(sep_line("─"));
        lines.push(crate_row("aether-cli", "CLI + 30 commands + REPL", GREEN));
        lines.push(crate_row("aether-client", "HTTP + Substrate RPC client", GREEN));
        lines.push(crate_row("aether-miner", "VQE mining engine", GREEN));
        lines.push(crate_row("aether-wallet", "Dilithium5 multi-wallet keystore", GREEN));
        lines.push(crate_row("aether-tui", "Terminal UI (ratatui)", GREEN));
        lines.push(crate_row("aether-innovation", "5 patent innovations", VIOLET));
        lines.push(crate_row("aether-privacy", "Susy Swaps (stealth tx)", VIOLET));

        lines.push(blank());

        // ── Footer ──
        lines.push(sep_line("═"));
        lines.push(Line::from(vec![
            Span::styled("  Type a message to chat", Style::default().fg(WHITE)),
            Span::styled("  ·  ", Style::default().fg(DIM)),
            Span::styled("/help", Style::default().fg(GREEN)),
            Span::styled(" for commands", Style::default().fg(SECTION)),
            Span::styled("  ·  ", Style::default().fg(DIM)),
            Span::styled("Ctrl+C", Style::default().fg(AMBER)),
            Span::styled(" to exit", Style::default().fg(SECTION)),
        ]));
        lines.push(Line::from(vec![
            Span::styled("  ", Style::default()),
            Span::styled(
                "Built with Rust  ·  Powered by Aether Mind  ·  Secured by quantum physics",
                Style::default().fg(DIM).add_modifier(Modifier::ITALIC),
            ),
        ]));
        lines.push(blank());

        lines
    }

    pub fn draw(&self, frame: &mut Frame, area: Rect) {
        let block = Block::default()
            .borders(Borders::ALL)
            .border_style(Style::default().fg(BORDER))
            .title(Span::styled(
                " Chat ",
                Style::default()
                    .fg(GREEN)
                    .add_modifier(Modifier::BOLD),
            ))
            .title_bottom(Line::from(vec![
                Span::styled(" ", Style::default()),
                Span::styled(
                    format!(" {} messages ", self.messages.len()),
                    Style::default().fg(DIM),
                ),
            ]));

        let inner = block.inner(area);

        // Build lines from messages
        let mut lines: Vec<Line> = Vec::new();
        for msg in &self.messages {
            // Blank line between messages
            if !lines.is_empty() {
                lines.push(Line::from(""));
            }
            match msg.role {
                Role::Welcome => {
                    // Rich procedural banner — full color styling
                    lines.extend(Self::welcome_lines(inner.width));
                }
                Role::User => {
                    lines.push(Line::from(vec![
                        Span::styled(
                            "  You ",
                            Style::default()
                                .fg(Color::Black)
                                .bg(Color::Cyan)
                                .add_modifier(Modifier::BOLD),
                        ),
                        Span::raw(" "),
                    ]));
                    for text_line in msg.content.lines() {
                        lines.push(Line::from(vec![
                            Span::styled("  ", Style::default()),
                            Span::styled(text_line.to_string(), Style::default().fg(Color::White)),
                        ]));
                    }
                }
                Role::Aether => {
                    lines.push(Line::from(vec![
                        Span::styled(
                            "  Aether ",
                            Style::default()
                                .fg(Color::Black)
                                .bg(GREEN)
                                .add_modifier(Modifier::BOLD),
                        ),
                        Span::raw(" "),
                    ]));
                    for text_line in msg.content.lines() {
                        let style = if text_line.trim_start().starts_with("```") {
                            Style::default().fg(DIM)
                        } else if text_line.trim_start().starts_with("- ")
                            || text_line.trim_start().starts_with("* ")
                        {
                            Style::default().fg(Color::Rgb(180, 200, 220))
                        } else if text_line.contains("QBC") || text_line.contains("phi") {
                            Style::default().fg(GREEN)
                        } else {
                            Style::default().fg(Color::Rgb(220, 220, 230))
                        };
                        lines.push(Line::from(vec![
                            Span::styled("  ", Style::default()),
                            Span::styled(text_line.to_string(), style),
                        ]));
                    }
                }
                Role::System => {
                    lines.push(Line::from(vec![
                        Span::styled(
                            "  sys ",
                            Style::default()
                                .fg(Color::Black)
                                .bg(VIOLET),
                        ),
                        Span::raw(" "),
                    ]));
                    for text_line in msg.content.lines() {
                        lines.push(Line::from(vec![
                            Span::styled("  ", Style::default()),
                            Span::styled(
                                text_line.to_string(),
                                Style::default().fg(DIM).add_modifier(Modifier::ITALIC),
                            ),
                        ]));
                    }
                }
            }
        }

        // Thinking indicator
        if self.waiting {
            lines.push(Line::from(""));
            let dots = match (std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap_or_default()
                .as_millis() / 500) % 4 {
                0 => ".",
                1 => "..",
                2 => "...",
                _ => "",
            };
            lines.push(Line::from(vec![
                Span::styled("  ", Style::default()),
                Span::styled(
                    format!("Aether is thinking{dots}"),
                    Style::default()
                        .fg(GREEN)
                        .add_modifier(Modifier::ITALIC),
                ),
            ]));
        }

        // Compute scroll: auto-scroll to bottom if offset is MAX
        let content_height = lines.len() as u16;
        let visible_height = inner.height;
        let max_scroll = content_height.saturating_sub(visible_height);
        let scroll = if self.scroll_offset >= max_scroll {
            max_scroll
        } else {
            self.scroll_offset
        };

        let paragraph = Paragraph::new(lines)
            .block(block)
            .wrap(Wrap { trim: false })
            .scroll((scroll, 0));

        frame.render_widget(paragraph, area);
    }
}

// ── Styling helpers ──────────────────────────────────────────────────────

/// Colorize a tree line: sephirot names in bright green, stars dim, structure dark green.
fn colorize_tree_line(line: &str, padding: &str) -> Line<'static> {
    let sephirot = [
        "KETER", "CHOCHMAH", "BINAH", "GEVURAH", "CHESED",
        "TIFERET", "HOD", "NETZACH", "YESOD", "MALKUTH",
    ];

    // Check if line contains any sephirot name
    let mut spans: Vec<Span<'static>> = vec![Span::raw(padding.to_string())];
    let remaining = line.to_string();

    // Find the first sephirot in this line
    let mut found = false;
    for name in &sephirot {
        if let Some(pos) = remaining.find(name) {
            found = true;
            let before = &remaining[..pos];
            let after = &remaining[pos + name.len()..];

            // Before: structure chars in dark green, stars in dim
            spans.push(colorize_structure(before));
            // Sephirot name: bright green bold
            spans.push(Span::styled(
                name.to_string(),
                Style::default().fg(GREEN).add_modifier(Modifier::BOLD),
            ));
            // After: structure
            spans.push(colorize_structure(after));
            break;
        }
    }

    // Handle lines with two sephirot (e.g., "BINAH | CHOCHMAH")
    if !found {
        spans.push(colorize_structure(&remaining));
    } else {
        // Check for second sephirot in the after-text
        let last_span = spans.last().cloned();
        if let Some(last) = last_span {
            let last_text = last.content.to_string();
            for name in &sephirot {
                if let Some(pos) = last_text.find(name) {
                    spans.pop(); // remove the last span
                    let before = &last_text[..pos];
                    let after = &last_text[pos + name.len()..];
                    spans.push(colorize_structure(before));
                    spans.push(Span::styled(
                        name.to_string(),
                        Style::default().fg(GREEN).add_modifier(Modifier::BOLD),
                    ));
                    spans.push(colorize_structure(after));
                    break;
                }
            }
        }
    }

    Line::from(spans)
}

/// Color structure characters: stars (*.) in dim, slashes/pipes in dark green.
fn colorize_structure(s: &str) -> Span<'static> {
    // Simple approach: all structure in a unified dark green
    let tree_green = Color::Rgb(0, 160, 80);
    let text = s.to_string();
    if text.trim().is_empty() || text.chars().all(|c| c == '.' || c == '*' || c == ' ') {
        Span::styled(text, Style::default().fg(STAR))
    } else {
        Span::styled(text, Style::default().fg(tree_green))
    }
}

/// Section header: bold, colored.
fn section_header(title: &str) -> Line<'static> {
    Line::from(Span::styled(
        title.to_string(),
        Style::default().fg(WHITE).add_modifier(Modifier::BOLD),
    ))
}

/// Info row: label (dim) · value (color) · suffix (dim).
fn info_row(label: &str, value: &str, suffix: &str, color: Color) -> Line<'static> {
    let dots = ".".repeat(16usize.saturating_sub(label.trim().len()));
    Line::from(vec![
        Span::styled(format!("{label} "), Style::default().fg(SECTION)),
        Span::styled(dots, Style::default().fg(SEP)),
        Span::styled(format!(" {value}"), Style::default().fg(color)),
        Span::styled(format!(" {suffix}"), Style::default().fg(DIM)),
    ])
}

/// Command row: command in green, description in white.
fn cmd_row(cmd: &str, desc: &str) -> Line<'static> {
    let padding = " ".repeat(26usize.saturating_sub(cmd.len()));
    Line::from(vec![
        Span::styled(format!("  {cmd}"), Style::default().fg(GREEN)),
        Span::raw(padding),
        Span::styled(desc.to_string(), Style::default().fg(SECTION)),
    ])
}

/// Slash command row: command in amber, description in dim.
fn slash_row(cmd: &str, desc: &str) -> Line<'static> {
    let padding = " ".repeat(20usize.saturating_sub(cmd.len()));
    Line::from(vec![
        Span::styled(format!("  {cmd}"), Style::default().fg(AMBER)),
        Span::raw(padding),
        Span::styled(desc.to_string(), Style::default().fg(SECTION)),
    ])
}

/// Innovation row: command in violet, name bold, description dim.
fn innovation_row(cmd: &str, name: &str, desc: &str) -> Line<'static> {
    Line::from(vec![
        Span::styled(format!("  {cmd}"), Style::default().fg(VIOLET)),
        Span::styled(
            format!("  {name}"),
            Style::default().fg(WHITE).add_modifier(Modifier::BOLD),
        ),
        Span::styled(format!("  {desc}"), Style::default().fg(DIM)),
    ])
}

/// Security row: label bold dim, value in green.
fn security_row(label: &str, value: &str) -> Line<'static> {
    let padding = " ".repeat(14usize.saturating_sub(label.len()));
    Line::from(vec![
        Span::styled(format!("  {label}"), Style::default().fg(SECTION)),
        Span::raw(padding),
        Span::styled(value.to_string(), Style::default().fg(GREEN)),
    ])
}

/// Crate row: name in color, description in white.
fn crate_row(name: &str, desc: &str, color: Color) -> Line<'static> {
    let padding = " ".repeat(22usize.saturating_sub(name.len()));
    Line::from(vec![
        Span::styled(format!("  {name}"), Style::default().fg(color)),
        Span::raw(padding),
        Span::styled(desc.to_string(), Style::default().fg(SECTION)),
    ])
}
