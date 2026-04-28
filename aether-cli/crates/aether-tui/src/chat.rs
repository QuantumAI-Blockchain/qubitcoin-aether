use ratatui::layout::Rect;
use ratatui::style::{Color, Modifier, Style};
use ratatui::text::{Line, Span};
use ratatui::widgets::{Block, Borders, Paragraph, Wrap};
use ratatui::Frame;

use crate::{AMBER, BORDER, DIM, GREEN, VIOLET};

const WHITE: Color = Color::Rgb(230, 237, 243);
const SEP: Color = Color::Rgb(45, 51, 59);
const SECTION: Color = Color::Rgb(139, 148, 158);
const CYAN: Color = Color::Rgb(100, 180, 255);

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
        let bi = |fg| Style::default().fg(fg).add_modifier(Modifier::BOLD | Modifier::ITALIC);

        // ── Box-drawing helpers ──
        let top = |title: &'static str, color: Color| {
            Line::from(vec![
                Span::styled("  ┌─ ", s(SEP)),
                Span::styled(title, b(color)),
                Span::styled(
                    format!(" {}", "─".repeat(56 - title.len())),
                    s(SEP),
                ),
                Span::styled("┐", s(SEP)),
            ])
        };
        let mid = |spans: Vec<Span<'static>>| {
            let mut v = vec![Span::styled("  │ ", s(SEP))];
            v.extend(spans);
            v.push(Span::styled(" │", s(SEP)));
            Line::from(v)
        };
        let bot = || {
            Line::from(Span::styled(
                format!("  └{}┘", "─".repeat(60)),
                s(SEP),
            ))
        };
        let blank = || {
            Line::from(vec![
                Span::styled("  │", s(SEP)),
                Span::raw(format!("{}", " ".repeat(61))),
                Span::styled("│", s(SEP)),
            ])
        };

        vec![
            // ══════════════════════════════════════════════════════
            // ── HEADER: ASCII Art Banner ──
            // ══════════════════════════════════════════════════════
            Line::from(""),
            Line::from(vec![
                Span::styled("  ┏", b(GREEN)),
                Span::styled("━".repeat(62), b(GREEN)),
                Span::styled("┓", b(GREEN)),
            ]),
            Line::from(vec![
                Span::styled("  ┃", b(GREEN)),
                Span::raw("                                                              "),
                Span::styled("┃", b(GREEN)),
            ]),
            // Line 1 of ASCII art
            Line::from(vec![
                Span::styled("  ┃", b(GREEN)),
                Span::styled(
                    "   ▄▀█ █▀▀ ▀█▀ █ █ █▀▀ █▀█   █▀▄▀█ █ █▄ █ █▀▄   ",
                    b(GREEN),
                ),
                Span::styled("        ┃", b(GREEN)),
            ]),
            // Line 2 of ASCII art
            Line::from(vec![
                Span::styled("  ┃", b(GREEN)),
                Span::styled(
                    "   █▀█ ██▄  █  █▀█ ██▄ █▀▄   █ ▀ █ █ █ ▀█ █▄▀   ",
                    b(GREEN),
                ),
                Span::styled("        ┃", b(GREEN)),
            ]),
            Line::from(vec![
                Span::styled("  ┃", b(GREEN)),
                Span::raw("                                                              "),
                Span::styled("┃", b(GREEN)),
            ]),
            // Tagline
            Line::from(vec![
                Span::styled("  ┃", b(GREEN)),
                Span::raw("       "),
                Span::styled("The Blockchain That Thinks", bi(WHITE)),
                Span::styled("  ·  ", s(DIM)),
                Span::styled("qbc.network", b(CYAN)),
                Span::raw("              "),
                Span::styled("┃", b(GREEN)),
            ]),
            // Subtitle
            Line::from(vec![
                Span::styled("  ┃", b(GREEN)),
                Span::raw("    "),
                Span::styled("On-chain AI", s(SECTION)),
                Span::styled(" · ", s(DIM)),
                Span::styled("Dilithium5", s(VIOLET)),
                Span::styled(" · ", s(DIM)),
                Span::styled("VQE Mining", s(AMBER)),
                Span::styled(" · ", s(DIM)),
                Span::styled("10 Sephirot", s(GREEN)),
                Span::raw("            "),
                Span::styled("┃", b(GREEN)),
            ]),
            Line::from(vec![
                Span::styled("  ┃", b(GREEN)),
                Span::raw("                                                              "),
                Span::styled("┃", b(GREEN)),
            ]),
            Line::from(vec![
                Span::styled("  ┗", b(GREEN)),
                Span::styled("━".repeat(62), b(GREEN)),
                Span::styled("┛", b(GREEN)),
            ]),
            Line::from(""),

            // ══════════════════════════════════════════════════════
            // ── SYSTEM STATUS ──
            // ══════════════════════════════════════════════════════
            top("SYSTEM STATUS", WHITE),
            mid(vec![
                Span::styled("Chain ", s(SECTION)),
                Span::styled("3303", b(GREEN)),
                Span::styled("    ·  Reward ", s(SECTION)),
                Span::styled("15.27 QBC", b(AMBER)),
                Span::styled("/block  ·  Supply ", s(SECTION)),
                Span::styled("3.3B", b(AMBER)),
            ]),
            mid(vec![
                Span::styled("Crypto ", s(SECTION)),
                Span::styled("Dilithium5 NIST L5", b(GREEN)),
                Span::styled("  ·  PK ", s(SECTION)),
                Span::styled("2,592B", s(WHITE)),
                Span::styled("  Sig ", s(SECTION)),
                Span::styled("4,627B", s(WHITE)),
            ]),
            mid(vec![
                Span::styled("Wallet ", s(SECTION)),
                Span::styled("Argon2id + AES-256-GCM", s(GREEN)),
                Span::styled("  ·  Keystore encrypted", s(SECTION)),
            ]),
            mid(vec![
                Span::styled("API ", s(SECTION)),
                Span::styled("ai.qbc.network", s(CYAN)),
                Span::styled("  ·  RPC ", s(SECTION)),
                Span::styled("rpc.qbc.network", s(CYAN)),
            ]),
            bot(),

            // ══════════════════════════════════════════════════════
            // ── COMMANDS ──
            // ══════════════════════════════════════════════════════
            top("COMMANDS", GREEN),
            mid(vec![
                Span::styled("aether", b(GREEN)),
                Span::styled("              TUI chat       ", s(SECTION)),
                Span::styled("aether --mine", b(GREEN)),
                Span::styled("   Chat+mine", s(SECTION)),
            ]),
            mid(vec![
                Span::styled("aether chat \".\"", b(GREEN)),
                Span::styled("      One-shot       ", s(SECTION)),
                Span::styled("aether status", b(GREEN)),
                Span::styled("     Stats", s(SECTION)),
            ]),
            mid(vec![
                Span::styled("aether mine", b(GREEN)),
                Span::styled("           Headless      ", s(SECTION)),
                Span::styled("aether search \".\"", b(GREEN)),
                Span::styled("  Find", s(SECTION)),
            ]),
            bot(),

            // ══════════════════════════════════════════════════════
            // ── WALLET ──
            // ══════════════════════════════════════════════════════
            top("WALLET", VIOLET),
            mid(vec![
                Span::styled("create", b(GREEN)),
                Span::styled("  Dilithium5 keypair    ", s(SECTION)),
                Span::styled("list", b(GREEN)),
                Span::styled("      Show wallets       ", s(SECTION)),
            ]),
            mid(vec![
                Span::styled("send", b(GREEN)),
                Span::styled("    Sign + submit UTXO  ", s(SECTION)),
                Span::styled("balance", b(GREEN)),
                Span::styled("   On-chain balance      ", s(SECTION)),
            ]),
            mid(vec![
                Span::styled("sign", b(GREEN)),
                Span::styled("    Dilithium5 sign     ", s(SECTION)),
                Span::styled("verify", b(GREEN)),
                Span::styled("    Check signature      ", s(SECTION)),
            ]),
            mid(vec![
                Span::styled("import", b(GREEN)),
                Span::styled("  Import private key    ", s(SECTION)),
                Span::styled("export", b(GREEN)),
                Span::styled("    Export secret key     ", s(SECTION)),
            ]),
            bot(),

            // ══════════════════════════════════════════════════════
            // ── MINING & REWARDS ──
            // ══════════════════════════════════════════════════════
            top("MINING & REWARDS", AMBER),
            mid(vec![
                Span::styled("Reward Pool ", s(SECTION)),
                Span::styled("1,000,000 QBC", b(AMBER)),
                Span::styled("  ·  Gradient learning rewarded", s(SECTION)),
            ]),
            mid(vec![
                Span::styled("gradient status", b(GREEN)),
                Span::styled("   Pool       ", s(SECTION)),
                Span::styled("gradient submit", b(GREEN)),
                Span::styled("   Earn QBC      ", s(SECTION)),
            ]),
            mid(vec![
                Span::styled("rewards show", b(GREEN)),
                Span::styled("      Earned     ", s(SECTION)),
                Span::styled("rewards claim", b(GREEN)),
                Span::styled("     To wallet     ", s(SECTION)),
            ]),
            mid(vec![
                Span::styled("rewards pool", b(GREEN)),
                Span::styled("      Global     ", s(SECTION)),
                Span::raw("                               "),
            ]),
            bot(),

            // ══════════════════════════════════════════════════════
            // ── INNOVATIONS ──
            // ══════════════════════════════════════════════════════
            top("INNOVATIONS  (6 Patents)", VIOLET),
            mid(vec![
                Span::styled("cogwork ", b(VIOLET)),
                Span::styled("  Proof-of-Cognitive-Work           ", s(SECTION)),
                Span::styled("(PoCW)", s(DIM)),
                Span::raw("       "),
            ]),
            mid(vec![
                Span::styled("entangle", b(VIOLET)),
                Span::styled("  Quantum-Entangled Wallets         ", s(SECTION)),
                Span::styled("(QEW)", s(DIM)),
                Span::raw("        "),
            ]),
            mid(vec![
                Span::styled("optimize", b(VIOLET)),
                Span::styled("  Predictive UTXO Coalescing        ", s(SECTION)),
                Span::styled("(PUC)", s(DIM)),
                Span::raw("        "),
            ]),
            mid(vec![
                Span::styled("recover ", b(VIOLET)),
                Span::styled("  ZK Cognitive Recovery             ", s(SECTION)),
                Span::styled("(ZCR)", s(DIM)),
                Span::raw("        "),
            ]),
            mid(vec![
                Span::styled("synapse ", b(VIOLET)),
                Span::styled("  Symbiotic Mining AI               ", s(SECTION)),
                Span::styled("(SMIP)", s(DIM)),
                Span::raw("       "),
            ]),
            mid(vec![
                Span::styled("privacy ", b(VIOLET)),
                Span::styled("  Susy Swaps — Stealth Transactions ", s(SECTION)),
                Span::styled("(SS)", s(DIM)),
                Span::raw("         "),
            ]),
            bot(),

            // ══════════════════════════════════════════════════════
            // ── IN-CHAT COMMANDS ──
            // ══════════════════════════════════════════════════════
            top("IN-CHAT COMMANDS", WHITE),
            mid(vec![
                Span::styled("/status", b(AMBER)),
                Span::styled("  Chain stats    ", s(SECTION)),
                Span::styled("/info", b(AMBER)),
                Span::styled("  Architecture   ", s(SECTION)),
                Span::styled("/gates", b(AMBER)),
                Span::styled("  Milestones", s(SECTION)),
            ]),
            mid(vec![
                Span::styled("/gradient", b(AMBER)),
                Span::styled(" Submit        ", s(SECTION)),
                Span::styled("/rewards", b(AMBER)),
                Span::styled(" Earned        ", s(SECTION)),
                Span::styled("/pool", b(AMBER)),
                Span::styled("   Pool     ", s(SECTION)),
            ]),
            mid(vec![
                Span::styled("/search", b(AMBER)),
                Span::styled("  Knowledge    ", s(SECTION)),
                Span::styled("/wallet", b(AMBER)),
                Span::styled("  Address        ", s(SECTION)),
                Span::styled("/help", b(AMBER)),
                Span::styled("   All cmds ", s(SECTION)),
            ]),
            bot(),
            Line::from(""),

            // ── Footer ──
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
