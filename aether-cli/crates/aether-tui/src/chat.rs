use ratatui::layout::Rect;
use ratatui::style::{Color, Modifier, Style};
use ratatui::text::{Line, Span};
use ratatui::widgets::{Block, Borders, Paragraph, Wrap};
use ratatui::Frame;

use crate::{BORDER, DIM, GREEN, VIOLET};

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
                role: Role::System,
                content: Self::welcome_banner(),
            }],
            scroll_offset: 0,
            waiting: false,
        }
    }

    fn welcome_banner() -> String {
        [
            "",
            "              .    *    .   *       .         *",
            "         *       _/|\\_    .        *",
            "           .    / /|\\ \\      .        *",
            "              /  / | \\  \\   *     .",
            "            /--/   |  \\--\\       *",
            "       .   |  (KETER)    |   .        *",
            "          / / \\    / \\  \\     .",
            "         |BINAH | CHOCHMAH|   *     .",
            "          \\ \\ /  \\ / \\ /        *",
            "         |GEVURAH| CHESED|      .",
            "           \\ \\  | /  /    *        *",
            "        .  |  TIFERET |   .        .",
            "            / /  \\  \\       *",
            "        *  |HOD  | NETZACH|     .     *",
            "            \\ \\ /  /   .      *",
            "        .   | YESOD |      .       .",
            "             \\_|_/    *         *",
            "           |MALKUTH|   .      .",
            "              |||         *        .",
            "",
            "  ══════════════════════════════════════════════",
            "           A E T H E R    M I N D",
            "   The Blockchain That Thinks  ·  qbc.network",
            "  ══════════════════════════════════════════════",
            "",
            "  SYSTEM",
            "  ──────────────────────────────────────────────",
            "  Chain ········ 3303 (mainnet)",
            "  Crypto ······· CRYSTALS-Dilithium5 (NIST L5)",
            "  Mining ······· VQE 4-Qubit Proof-of-SUSY",
            "  Reward ······· 15.27 QBC/block (Era 0)",
            "  Supply ······· 3,300,000,000 QBC max",
            "  Wallet ······· Argon2id + AES-256-GCM",
            "  API ·········· ai.qbc.network",
            "  RPC ·········· rpc.qbc.network",
            "",
            "  COMMANDS",
            "  ──────────────────────────────────────────────",
            "  aether                 Interactive chat (TUI)",
            "  aether --mine          Chat + mine together",
            "  aether chat \"...\"      One-shot query",
            "  aether status          Chain + Aether stats",
            "",
            "  aether wallet create   Dilithium5 keypair",
            "  aether wallet list     List wallets",
            "  aether wallet balance  On-chain balance",
            "  aether wallet send     Sign + submit UTXO tx",
            "  aether wallet sign     Dilithium5 signature",
            "  aether wallet verify   Verify signature",
            "  aether wallet import   Import private key",
            "  aether wallet export   Export private key",
            "",
            "  aether mine            Headless VQE mining",
            "  aether search \"...\"    Knowledge fabric search",
            "  aether gradient status Gradient pool status",
            "  aether gradient submit Submit gradient update",
            "  aether rewards show    View earned QBC",
            "  aether rewards pool    Global reward pool",
            "  aether rewards claim   Claim to wallet",
            "",
            "  INNOVATIONS (5 Patents)",
            "  ──────────────────────────────────────────────",
            "  aether cogwork         Proof-of-Cognitive-Work",
            "  aether entangle        Entangled Wallet Protocol",
            "  aether optimize        UTXO Coalescing Engine",
            "  aether recover         ZK Cognitive Recovery",
            "  aether synapse         Symbiotic Mining AI",
            "  aether privacy         Susy Swaps (stealth tx)",
            "",
            "  SECURITY",
            "  ──────────────────────────────────────────────",
            "  Signatures ··· CRYSTALS-Dilithium5 (NIST L5)",
            "  Keystore ····· Argon2id + AES-256-GCM",
            "  Addresses ···· SHA-256(Dilithium5_PK) 32 bytes",
            "  Key sizes ···· PK=2592B  SK=4896B  Sig=4627B",
            "",
            "  ──────────────────────────────────────────────",
            "  Type a message to chat  ·  /help for commands",
            "  Ctrl+C to exit  ·  Esc to go back",
            "",
        ]
        .join("\n")
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
