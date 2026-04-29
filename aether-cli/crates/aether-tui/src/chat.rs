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

    /// Build the welcome screen, dynamically sized to fill `w` columns.
    fn welcome_lines(w: usize) -> Vec<Line<'static>> {
        let s = |fg| Style::default().fg(fg);
        let b = |fg| Style::default().fg(fg).add_modifier(Modifier::BOLD);
        let bi = |fg| Style::default().fg(fg).add_modifier(Modifier::BOLD | Modifier::ITALIC);

        // ── Dynamic layout math ──
        // Total line = indent(2) + col(cw+4) + gap(2) + col(cw+4) = 2*cw + 12
        let w = w.max(60);
        let cw = (w.saturating_sub(12)) / 2; // column inner content width
        let fw = 2 * cw + 6;                 // full-width inner (keeps alignment)

        // ── Helper closures ──

        // Header cell — centered content inside ┃ ... ┃
        let hcenter = |spans: Vec<Span<'static>>| -> Line<'static> {
            let used: usize = spans.iter().map(|sp| sp.content.chars().count()).sum();
            let total = fw.saturating_sub(used);
            let lp = total / 2;
            let rp = total - lp;
            let gb = Style::default().fg(GREEN).add_modifier(Modifier::BOLD);
            let mut v = vec![Span::raw("  "), Span::styled("┃", gb)];
            v.push(Span::raw(" ".repeat(lp + 1)));
            v.extend(spans);
            v.push(Span::raw(" ".repeat(rp + 1)));
            v.push(Span::styled("┃", gb));
            Line::from(v)
        };

        // Two-column data row
        let dual = |left: Vec<Span<'static>>, right: Vec<Span<'static>>| -> Line<'static> {
            let lu: usize = left.iter().map(|sp| sp.content.chars().count()).sum();
            let lp = cw.saturating_sub(lu);
            let ru: usize = right.iter().map(|sp| sp.content.chars().count()).sum();
            let rp = cw.saturating_sub(ru);
            let br = Style::default().fg(SEP);
            let mut v = vec![Span::raw("  "), Span::styled("│ ", br)];
            v.extend(left);
            if lp > 0 { v.push(Span::raw(" ".repeat(lp))); }
            v.push(Span::styled(" │", br));
            v.push(Span::raw("  "));
            v.push(Span::styled("│ ", br));
            v.extend(right);
            if rp > 0 { v.push(Span::raw(" ".repeat(rp))); }
            v.push(Span::styled(" │", br));
            Line::from(v)
        };

        // Two-column top border
        let dtop = |lt: &'static str, lc: Color, rt: &'static str, rc: Color| -> Line<'static> {
            let ld = cw.saturating_sub(lt.len()).saturating_sub(1);
            let rd = cw.saturating_sub(rt.len()).saturating_sub(1);
            let br = Style::default().fg(SEP);
            let bl = |c| Style::default().fg(c).add_modifier(Modifier::BOLD);
            Line::from(vec![
                Span::raw("  "),
                Span::styled("┌─ ", br), Span::styled(lt, bl(lc)),
                Span::styled(format!(" {}┐", "─".repeat(ld)), br),
                Span::raw("  "),
                Span::styled("┌─ ", br), Span::styled(rt, bl(rc)),
                Span::styled(format!(" {}┐", "─".repeat(rd)), br),
            ])
        };

        // Two-column bottom border
        let dbot = || -> Line<'static> {
            let d = "─".repeat(cw + 2);
            let br = Style::default().fg(SEP);
            Line::from(vec![
                Span::raw("  "),
                Span::styled(format!("└{d}┘"), br),
                Span::raw("  "),
                Span::styled(format!("└{d}┘"), br),
            ])
        };

        // Full-width data row
        let frow = |spans: Vec<Span<'static>>| -> Line<'static> {
            let used: usize = spans.iter().map(|sp| sp.content.chars().count()).sum();
            let pad = fw.saturating_sub(used);
            let br = Style::default().fg(SEP);
            let mut v = vec![Span::raw("  "), Span::styled("│ ", br)];
            v.extend(spans);
            if pad > 0 { v.push(Span::raw(" ".repeat(pad))); }
            v.push(Span::styled(" │", br));
            Line::from(v)
        };

        // Full-width top border
        let ftop = |title: &'static str, color: Color| -> Line<'static> {
            let d = fw.saturating_sub(title.len()).saturating_sub(1);
            let br = Style::default().fg(SEP);
            Line::from(vec![
                Span::raw("  "),
                Span::styled("┌─ ", br),
                Span::styled(title, Style::default().fg(color).add_modifier(Modifier::BOLD)),
                Span::styled(format!(" {}┐", "─".repeat(d)), br),
            ])
        };

        // Full-width bottom border
        let fbot = || -> Line<'static> {
            let br = Style::default().fg(SEP);
            Line::from(vec![
                Span::raw("  "),
                Span::styled(format!("└{}┘", "─".repeat(fw + 2)), br),
            ])
        };

        // ── Header border widths ──
        let hbar = "━".repeat(fw + 2);

        vec![
            // ══════════════════════════════════════════════════════════
            // ── HEADER — centered ASCII art + info ──
            // ══════════════════════════════════════════════════════════
            Line::from(""),
            Line::from(vec![
                Span::raw("  "),
                Span::styled("┏", b(GREEN)),
                Span::styled(hbar.clone(), b(GREEN)),
                Span::styled("┓", b(GREEN)),
            ]),
            hcenter(vec![]),

            // ── ASCII art: AETHER (green) ──
            hcenter(vec![Span::styled(
                "▄▀█ █▀▀ ▀█▀ █ █ █▀▀ █▀█",
                b(GREEN),
            )]),
            hcenter(vec![Span::styled(
                "█▀█ ██▄  █  █▀█ ██▄ █▀▄",
                b(GREEN),
            )]),

            // ── Decorative separator ──
            hcenter(vec![Span::styled(
                "◈━━━━━━━━━━━━━━━━━━━━━◈",
                s(DIM),
            )]),

            // ── ASCII art: MIND (violet) ──
            hcenter(vec![Span::styled(
                "█▀▄▀█ █ █▄ █ █▀▄",
                b(VIOLET),
            )]),
            hcenter(vec![Span::styled(
                "█ ▀ █ █ █ ▀█ █▄▀",
                b(VIOLET),
            )]),

            hcenter(vec![]),

            // ── Tagline ──
            hcenter(vec![
                Span::styled("\"The Blockchain That Thinks\"", bi(WHITE)),
                Span::styled("  ·  ", s(DIM)),
                Span::styled("qbc.network", b(CYAN)),
            ]),

            // ── Subtitle ──
            hcenter(vec![
                Span::styled("On-chain AI", s(SECTION)),
                Span::styled(" · ", s(DIM)),
                Span::styled("Dilithium5", s(VIOLET)),
                Span::styled(" · ", s(DIM)),
                Span::styled("VQE Mining", s(AMBER)),
                Span::styled(" · ", s(DIM)),
                Span::styled("10 Sephirot", s(GREEN)),
                Span::styled(" · ", s(DIM)),
                Span::styled("Susy Swaps", s(CYAN)),
            ]),

            hcenter(vec![]),
            Line::from(vec![
                Span::raw("  "),
                Span::styled("┗", b(GREEN)),
                Span::styled(hbar, b(GREEN)),
                Span::styled("┛", b(GREEN)),
            ]),
            Line::from(""),

            // ══════════════════════════════════════════════════════════
            // ── NETWORK + SECURITY ──
            // ══════════════════════════════════════════════════════════
            dtop("NETWORK", WHITE, "SECURITY", VIOLET),
            dual(
                vec![Span::styled("Chain     ", s(SECTION)), Span::styled("3303 (Mainnet)", b(GREEN))],
                vec![Span::styled("Crypto    ", s(SECTION)), Span::styled("Dilithium5 NIST L5", b(GREEN))],
            ),
            dual(
                vec![Span::styled("Block     ", s(SECTION)), Span::styled("3.3s target", s(WHITE))],
                vec![Span::styled("Keystore  ", s(SECTION)), Span::styled("Argon2id+AES-256-GCM", s(WHITE))],
            ),
            dual(
                vec![
                    Span::styled("Reward    ", s(SECTION)),
                    Span::styled("15.27 QBC", b(AMBER)),
                    Span::styled("/block", s(SECTION)),
                ],
                vec![
                    Span::styled("PK ", s(SECTION)),
                    Span::styled("2,592B", s(WHITE)),
                    Span::styled(" · Sig ", s(SECTION)),
                    Span::styled("4,627B", s(WHITE)),
                ],
            ),
            dual(
                vec![
                    Span::styled("Supply    ", s(SECTION)),
                    Span::styled("3.3B QBC", b(AMBER)),
                    Span::styled(" max", s(SECTION)),
                ],
                vec![Span::styled("Address   ", s(SECTION)), Span::styled("SHA-256(pk) · 32B", s(WHITE))],
            ),
            dual(
                vec![Span::styled("Consensus ", s(SECTION)), Span::styled("PoSA + VQE Mining", s(WHITE))],
                vec![Span::styled("Mining    ", s(SECTION)), Span::styled("4-qubit VQE ansatz", s(WHITE))],
            ),
            dbot(),
            Line::from(""),

            // ══════════════════════════════════════════════════════════
            // ── COMMANDS + WALLET ──
            // ══════════════════════════════════════════════════════════
            dtop("COMMANDS", GREEN, "WALLET", VIOLET),
            dual(
                vec![Span::styled("aether            ", b(GREEN)), Span::styled("TUI chat", s(SECTION))],
                vec![Span::styled("wallet create     ", b(GREEN)), Span::styled("New keypair", s(SECTION))],
            ),
            dual(
                vec![Span::styled("aether --mine     ", b(GREEN)), Span::styled("Chat + mine", s(SECTION))],
                vec![Span::styled("wallet list       ", b(GREEN)), Span::styled("Show all", s(SECTION))],
            ),
            dual(
                vec![Span::styled("aether chat \"msg\" ", b(GREEN)), Span::styled("One-shot", s(SECTION))],
                vec![Span::styled("wallet balance    ", b(GREEN)), Span::styled("On-chain QBC", s(SECTION))],
            ),
            dual(
                vec![Span::styled("aether status     ", b(GREEN)), Span::styled("Chain stats", s(SECTION))],
                vec![Span::styled("wallet send       ", b(GREEN)), Span::styled("Sign + send", s(SECTION))],
            ),
            dual(
                vec![Span::styled("aether mine       ", b(GREEN)), Span::styled("Headless VQE", s(SECTION))],
                vec![Span::styled("wallet sign       ", b(GREEN)), Span::styled("Sign message", s(SECTION))],
            ),
            dual(
                vec![Span::styled("aether search \"q\" ", b(GREEN)), Span::styled("Knowledge", s(SECTION))],
                vec![Span::styled("wallet verify     ", b(GREEN)), Span::styled("Check sig", s(SECTION))],
            ),
            dbot(),
            Line::from(""),

            // ══════════════════════════════════════════════════════════
            // ── IN-CHAT + MINING & REWARDS ──
            // ══════════════════════════════════════════════════════════
            dtop("IN-CHAT", AMBER, "MINING & REWARDS", AMBER),
            dual(
                vec![
                    Span::styled("/status ", b(AMBER)), Span::styled("Stats  ", s(SECTION)),
                    Span::styled("/info ", b(AMBER)), Span::styled("Arch", s(SECTION)),
                ],
                vec![Span::styled("gradient status   ", b(GREEN)), Span::styled("Pool info", s(SECTION))],
            ),
            dual(
                vec![
                    Span::styled("/gates  ", b(AMBER)), Span::styled("Gates  ", s(SECTION)),
                    Span::styled("/search ", b(AMBER)), Span::styled("Find", s(SECTION)),
                ],
                vec![Span::styled("gradient submit   ", b(GREEN)), Span::styled("Earn QBC", s(SECTION))],
            ),
            dual(
                vec![
                    Span::styled("/gradient ", b(AMBER)), Span::styled("Go   ", s(SECTION)),
                    Span::styled("/rewards ", b(AMBER)), Span::styled("Earn", s(SECTION)),
                ],
                vec![Span::styled("rewards show      ", b(GREEN)), Span::styled("Your earnings", s(SECTION))],
            ),
            dual(
                vec![
                    Span::styled("/pool ", b(AMBER)), Span::styled("Pool    ", s(SECTION)),
                    Span::styled("/wallet ", b(AMBER)), Span::styled("Addr", s(SECTION)),
                ],
                vec![Span::styled("rewards claim     ", b(GREEN)), Span::styled("Claim to wallet", s(SECTION))],
            ),
            dual(
                vec![
                    Span::styled("/help ", b(AMBER)), Span::styled("Help    ", s(SECTION)),
                    Span::styled("/quit ", b(AMBER)), Span::styled("Exit", s(SECTION)),
                ],
                vec![Span::styled("rewards pool      ", b(GREEN)), Span::styled("Global stats", s(SECTION))],
            ),
            dbot(),
            Line::from(""),

            // ══════════════════════════════════════════════════════════
            // ── INNOVATIONS ──
            // ══════════════════════════════════════════════════════════
            ftop("INNOVATIONS (6 Patents)", VIOLET),
            frow(vec![
                Span::styled("cogwork  ", b(VIOLET)), Span::styled("Proof-of-Cognitive-Work", s(SECTION)),
                Span::styled("      ", s(SEP)),
                Span::styled("recover  ", b(VIOLET)), Span::styled("ZK Cognitive Recovery", s(SECTION)),
            ]),
            frow(vec![
                Span::styled("entangle ", b(VIOLET)), Span::styled("Quantum-Entangled Wallets", s(SECTION)),
                Span::styled("    ", s(SEP)),
                Span::styled("synapse  ", b(VIOLET)), Span::styled("Symbiotic Mining", s(SECTION)),
            ]),
            frow(vec![
                Span::styled("optimize ", b(VIOLET)), Span::styled("Predictive UTXO Coalesce", s(SECTION)),
                Span::styled("     ", s(SEP)),
                Span::styled("privacy  ", b(VIOLET)), Span::styled("Susy Swaps (stealth)", s(SECTION)),
            ]),
            fbot(),
            Line::from(""),

            // ── Footer ──
            Line::from(vec![
                Span::styled("  Type a message to chat", s(WHITE)),
                Span::styled("  ·  ", s(DIM)),
                Span::styled("/help", b(GREEN)),
                Span::styled(" for commands  ·  ", s(SECTION)),
                Span::styled("Ctrl+C", b(AMBER)),
                Span::styled(" exit  ·  ", s(SECTION)),
                Span::styled("PgUp/Dn", b(AMBER)),
                Span::styled(" scroll", s(SECTION)),
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
        let avail_width = inner.width as usize;

        let mut lines: Vec<Line> = Vec::new();
        for msg in &self.messages {
            if !lines.is_empty() {
                lines.push(Line::from(""));
            }
            match msg.role {
                Role::Welcome => {
                    lines.extend(Self::welcome_lines(avail_width));
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
