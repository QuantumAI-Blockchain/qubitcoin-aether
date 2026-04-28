use ratatui::layout::Rect;
use ratatui::style::{Color, Modifier, Style};
use ratatui::text::{Line, Span};
use ratatui::widgets::{Block, Borders, Paragraph, Wrap};
use ratatui::Frame;

use crate::{AMBER, BORDER, DIM, GREEN, VIOLET};

const WHITE: Color = Color::Rgb(230, 237, 243);
const SEP: Color = Color::Rgb(45, 51, 59);
const SECTION: Color = Color::Rgb(139, 148, 158);

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
    Welcome,
}

pub struct ChatPanel {
    pub messages: Vec<ChatMessage>,
    pub scroll_offset: u16,
    pub waiting: bool,
}

impl ChatPanel {
    pub fn new() -> Self {
        Self {
            messages: vec![ChatMessage {
                role: Role::Welcome,
                content: String::new(),
            }],
            scroll_offset: 0,
            waiting: false,
        }
    }

    pub fn push(&mut self, role: Role, content: String) {
        self.messages.push(ChatMessage { role, content });
        self.scroll_offset = u16::MAX;
    }

    pub fn scroll_up(&mut self, amount: u16) {
        self.scroll_offset = self.scroll_offset.saturating_sub(amount);
    }

    pub fn scroll_down(&mut self, amount: u16) {
        self.scroll_offset = self.scroll_offset.saturating_add(amount);
    }

    fn welcome_lines() -> Vec<Line<'static>> {
        let s = |fg| Style::default().fg(fg);
        let b = |fg| Style::default().fg(fg).add_modifier(Modifier::BOLD);
        let sep = || Line::from(Span::styled(
            " ──────────────────────────────────────────────────────────────────",
            s(SEP),
        ));

        vec![
            // ── Header ──
            Line::from(""),
            Line::from(vec![
                Span::styled("  ╔══╗ ", b(VIOLET)),
                Span::styled("AETHER MIND", b(GREEN)),
                Span::styled("  —  ", s(DIM)),
                Span::styled("The Blockchain That Thinks", s(WHITE)),
                Span::styled("  ·  ", s(DIM)),
                Span::styled("qbc.network", s(GREEN)),
            ]),
            Line::from(vec![
                Span::styled("  ╚══╝ ", b(VIOLET)),
                Span::styled("World's first on-chain AI  ·  Dilithium5  ·  VQE Mining  ·  10 Sephirot", s(DIM)),
            ]),
            sep(),
            // ── System ──
            Line::from(vec![
                Span::styled("  Chain ", s(SECTION)), Span::styled("3303", b(GREEN)),
                Span::styled("  ·  Reward ", s(SECTION)), Span::styled("15.27 QBC", b(AMBER)),
                Span::styled("/block  ·  Supply ", s(SECTION)), Span::styled("3.3B", b(AMBER)),
                Span::styled("  ·  Crypto ", s(SECTION)), Span::styled("Dilithium5 L5", b(GREEN)),
            ]),
            Line::from(vec![
                Span::styled("  Wallet ", s(SECTION)), Span::styled("Argon2id+AES-256-GCM", s(GREEN)),
                Span::styled("  ·  API ", s(SECTION)), Span::styled("ai.qbc.network", s(Color::Rgb(100,180,255))),
                Span::styled("  ·  RPC ", s(SECTION)), Span::styled("rpc.qbc.network", s(Color::Rgb(100,180,255))),
            ]),
            sep(),
            // ── Core Commands ──
            Line::from(Span::styled(" COMMANDS", b(WHITE))),
            Line::from(vec![
                Span::styled("  aether", s(GREEN)),           Span::styled("            TUI chat    ", s(SECTION)),
                Span::styled("aether --mine", s(GREEN)),      Span::styled("     Chat + mine", s(SECTION)),
            ]),
            Line::from(vec![
                Span::styled("  aether chat \"..\"", s(GREEN)), Span::styled("    One-shot     ", s(SECTION)),
                Span::styled("aether status", s(GREEN)),      Span::styled("        Stats", s(SECTION)),
            ]),
            Line::from(vec![
                Span::styled("  aether mine", s(GREEN)),      Span::styled("          Headless     ", s(SECTION)),
                Span::styled("aether search \"..\"", s(GREEN)), Span::styled("   Knowledge", s(SECTION)),
            ]),
            Line::from(""),
            // ── Wallet ──
            Line::from(Span::styled(" WALLET", b(WHITE))),
            Line::from(vec![
                Span::styled("  create", s(GREEN)),    Span::styled("  Dilithium5 keypair   ", s(SECTION)),
                Span::styled("list", s(GREEN)),        Span::styled("    Show all wallets    ", s(SECTION)),
                Span::styled("balance", s(GREEN)),     Span::styled("  On-chain", s(SECTION)),
            ]),
            Line::from(vec![
                Span::styled("  send", s(GREEN)),      Span::styled("    Sign+submit UTXO   ", s(SECTION)),
                Span::styled("sign", s(GREEN)),        Span::styled("    Dilithium5 sig      ", s(SECTION)),
                Span::styled("verify", s(GREEN)),      Span::styled("   Check sig", s(SECTION)),
            ]),
            Line::from(vec![
                Span::styled("  import", s(GREEN)),    Span::styled("  Import private key   ", s(SECTION)),
                Span::styled("export", s(GREEN)),      Span::styled("  Export secret key     ", s(SECTION)),
                Span::styled("delete", s(GREEN)),      Span::styled("   Remove", s(SECTION)),
            ]),
            Line::from(""),
            // ── Mining & Rewards ──
            Line::from(vec![
                Span::styled(" MINING & REWARDS", b(WHITE)),
                Span::styled("  (1,000,000 QBC pool)", s(DIM)),
            ]),
            Line::from(vec![
                Span::styled("  gradient status", s(GREEN)),  Span::styled("  Pool     ", s(SECTION)),
                Span::styled("gradient submit", s(GREEN)),    Span::styled("  Earn QBC   ", s(SECTION)),
                Span::styled("rewards show", s(GREEN)),       Span::styled("  Earned", s(SECTION)),
            ]),
            Line::from(vec![
                Span::styled("  rewards pool", s(GREEN)),     Span::styled("     Global   ", s(SECTION)),
                Span::styled("rewards claim", s(GREEN)),      Span::styled("   To wallet", s(SECTION)),
            ]),
            Line::from(""),
            // ── Innovations ──
            Line::from(vec![
                Span::styled(" INNOVATIONS", b(VIOLET)),
                Span::styled("  (5 Patents)", s(DIM)),
            ]),
            Line::from(vec![
                Span::styled("  cogwork", s(VIOLET)),   Span::styled("  Proof-of-Cognitive-Work         ", s(SECTION)),
                Span::styled("entangle", s(VIOLET)),    Span::styled("  Quantum-Entangled Wallets", s(SECTION)),
            ]),
            Line::from(vec![
                Span::styled("  optimize", s(VIOLET)),  Span::styled(" UTXO Coalescing Engine            ", s(SECTION)),
                Span::styled("recover", s(VIOLET)),     Span::styled("   ZK Cognitive Recovery", s(SECTION)),
            ]),
            Line::from(vec![
                Span::styled("  synapse", s(VIOLET)),   Span::styled("  Symbiotic Mining AI (SMIP)      ", s(SECTION)),
                Span::styled("privacy", s(VIOLET)),     Span::styled("   Susy Swaps (stealth tx)", s(SECTION)),
            ]),
            Line::from(""),
            // ── TUI slash commands ──
            Line::from(Span::styled(" IN-CHAT", b(WHITE))),
            Line::from(vec![
                Span::styled("  /status", s(AMBER)),    Span::styled("  Chain stats  ", s(SECTION)),
                Span::styled("/info", s(AMBER)),         Span::styled("  Architecture  ", s(SECTION)),
                Span::styled("/gates", s(AMBER)),        Span::styled("  Milestones  ", s(SECTION)),
                Span::styled("/help", s(AMBER)),         Span::styled("  All cmds", s(SECTION)),
            ]),
            Line::from(vec![
                Span::styled("  /gradient", s(AMBER)),  Span::styled(" Submit        ", s(SECTION)),
                Span::styled("/rewards", s(AMBER)),      Span::styled(" Earned         ", s(SECTION)),
                Span::styled("/pool", s(AMBER)),         Span::styled("    Reward pool  ", s(SECTION)),
                Span::styled("/quit", s(AMBER)),         Span::styled("  Exit", s(SECTION)),
            ]),
            sep(),
            // ── Security + Footer ──
            Line::from(vec![
                Span::styled("  Signatures ", s(SECTION)), Span::styled("Dilithium5 NIST L5", s(GREEN)),
                Span::styled("  ·  PK ", s(SECTION)), Span::styled("2,592B", s(WHITE)),
                Span::styled("  SK ", s(SECTION)), Span::styled("4,896B", s(WHITE)),
                Span::styled("  Sig ", s(SECTION)), Span::styled("4,627B", s(WHITE)),
                Span::styled("  ·  Keystore ", s(SECTION)), Span::styled("Argon2id+AES", s(GREEN)),
            ]),
            sep(),
            Line::from(vec![
                Span::styled("  Type a message to chat", s(WHITE)),
                Span::styled("  ·  ", s(DIM)),
                Span::styled("/help", b(GREEN)),
                Span::styled(" for commands  ·  ", s(SECTION)),
                Span::styled("Ctrl+C", b(AMBER)),
                Span::styled(" exit  ·  ", s(SECTION)),
                Span::styled("Esc", b(AMBER)),
                Span::styled(" back", s(SECTION)),
            ]),
            Line::from(""),
        ]
    }

    pub fn draw(&self, frame: &mut Frame, area: Rect) {
        let block = Block::default()
            .borders(Borders::ALL)
            .border_style(Style::default().fg(BORDER))
            .title(Span::styled(
                " Chat ",
                Style::default().fg(GREEN).add_modifier(Modifier::BOLD),
            ))
            .title_bottom(Line::from(vec![
                Span::styled(" ", Style::default()),
                Span::styled(
                    format!(" {} messages ", self.messages.len()),
                    Style::default().fg(DIM),
                ),
            ]));

        let inner = block.inner(area);

        let mut lines: Vec<Line> = Vec::new();
        for msg in &self.messages {
            if !lines.is_empty() {
                lines.push(Line::from(""));
            }
            match msg.role {
                Role::Welcome => {
                    lines.extend(Self::welcome_lines());
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
                            Style::default().fg(Color::Black).bg(VIOLET),
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
                    Style::default().fg(GREEN).add_modifier(Modifier::ITALIC),
                ),
            ]));
        }

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
