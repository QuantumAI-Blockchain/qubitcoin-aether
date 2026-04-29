use ratatui::layout::Rect;
use ratatui::style::{Color, Modifier, Style};
use ratatui::text::{Line, Span};
use ratatui::widgets::{Block, Borders, Paragraph, Wrap};
use ratatui::Frame;

use crate::{AMBER, BORDER, DIM, GREEN, VIOLET};

const WHITE: Color = Color::Rgb(230, 237, 243);
const SEP: Color = Color::Rgb(48, 54, 62);
const LABEL: Color = Color::Rgb(125, 133, 144);
const CYAN: Color = Color::Rgb(0, 212, 255);

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
        let w = w.max(60);
        let br = Style::default().fg(SEP);
        let s = |fg: Color| Style::default().fg(fg);
        let b = |fg: Color| Style::default().fg(fg).add_modifier(Modifier::BOLD);
        let bi = |fg: Color| {
            Style::default()
                .fg(fg)
                .add_modifier(Modifier::BOLD | Modifier::ITALIC)
        };

        // ── Layout math ──
        // Two-column line: "  │ " + cw + " │  │ " + cw + " │" = 2*cw + 12
        // Full-width line: "  │ " + fw + " │"                  = fw + 6
        // Alignment: fw + 6 = 2*cw + 12  =>  fw = 2*cw + 6
        let cw = (w.saturating_sub(12)) / 2;
        let fw = 2 * cw + 6;

        // ── Full-width box helpers ──

        let ftop = |title: &'static str, color: Color| -> Line<'static> {
            let rest = (fw + 2).saturating_sub(title.len()).saturating_sub(4);
            Line::from(vec![
                Span::raw("  "),
                Span::styled("┌─ ", br),
                Span::styled(title, b(color)),
                Span::styled(format!(" {}┐", "─".repeat(rest)), br),
            ])
        };

        let fbot = || -> Line<'static> {
            Line::from(vec![
                Span::raw("  "),
                Span::styled(format!("└{}┘", "─".repeat(fw + 2)), br),
            ])
        };

        let fempty = || -> Line<'static> {
            Line::from(vec![
                Span::raw("  "),
                Span::styled("│", br),
                Span::raw(" ".repeat(fw + 2)),
                Span::styled("│", br),
            ])
        };

        let fcenter = |spans: Vec<Span<'static>>| -> Line<'static> {
            let used: usize = spans.iter().map(|sp| sp.content.chars().count()).sum();
            let total = fw.saturating_sub(used);
            let lp = total / 2;
            let rp = total - lp;
            let mut v = vec![
                Span::raw("  "),
                Span::styled("│", br),
                Span::raw(" ".repeat(lp + 1)),
            ];
            v.extend(spans);
            v.push(Span::raw(" ".repeat(rp + 1)));
            v.push(Span::styled("│", br));
            Line::from(v)
        };

        let frow = |spans: Vec<Span<'static>>| -> Line<'static> {
            let used: usize = spans.iter().map(|sp| sp.content.chars().count()).sum();
            let pad = fw.saturating_sub(used);
            let mut v = vec![Span::raw("  "), Span::styled("│ ", br)];
            v.extend(spans);
            if pad > 0 {
                v.push(Span::raw(" ".repeat(pad)));
            }
            v.push(Span::styled(" │", br));
            Line::from(v)
        };

        // Two-column inside a full-width box
        let frow2 = |left: Vec<Span<'static>>, right: Vec<Span<'static>>| -> Line<'static> {
            let half = fw / 2;
            let lu: usize = left.iter().map(|sp| sp.content.chars().count()).sum();
            let lp = half.saturating_sub(lu);
            let ru: usize = right.iter().map(|sp| sp.content.chars().count()).sum();
            let rp = (fw - half).saturating_sub(ru);
            let mut v = vec![Span::raw("  "), Span::styled("│ ", br)];
            v.extend(left);
            if lp > 0 {
                v.push(Span::raw(" ".repeat(lp)));
            }
            v.extend(right);
            if rp > 0 {
                v.push(Span::raw(" ".repeat(rp)));
            }
            v.push(Span::styled(" │", br));
            Line::from(v)
        };

        // ── Two-column box helpers ──

        let dtop = |lt: &'static str, lc: Color, rt: &'static str, rc: Color| -> Line<'static> {
            let lr = (cw + 2).saturating_sub(lt.len()).saturating_sub(4);
            let rr = (cw + 2).saturating_sub(rt.len()).saturating_sub(4);
            Line::from(vec![
                Span::raw("  "),
                Span::styled("┌─ ", br),
                Span::styled(lt, b(lc)),
                Span::styled(format!(" {}┐", "─".repeat(lr)), br),
                Span::raw("  "),
                Span::styled("┌─ ", br),
                Span::styled(rt, b(rc)),
                Span::styled(format!(" {}┐", "─".repeat(rr)), br),
            ])
        };

        let dbot = || -> Line<'static> {
            let d = "─".repeat(cw + 2);
            Line::from(vec![
                Span::raw("  "),
                Span::styled(format!("└{d}┘"), br),
                Span::raw("  "),
                Span::styled(format!("└{d}┘"), br),
            ])
        };

        let dual = |left: Vec<Span<'static>>, right: Vec<Span<'static>>| -> Line<'static> {
            let lu: usize = left.iter().map(|sp| sp.content.chars().count()).sum();
            let lp = cw.saturating_sub(lu);
            let ru: usize = right.iter().map(|sp| sp.content.chars().count()).sum();
            let rp = cw.saturating_sub(ru);
            let mut v = vec![Span::raw("  "), Span::styled("│ ", br)];
            v.extend(left);
            if lp > 0 {
                v.push(Span::raw(" ".repeat(lp)));
            }
            v.push(Span::styled(" │", br));
            v.push(Span::raw("  "));
            v.push(Span::styled("│ ", br));
            v.extend(right);
            if rp > 0 {
                v.push(Span::raw(" ".repeat(rp)));
            }
            v.push(Span::styled(" │", br));
            Line::from(v)
        };

        // ══════════════════════════════════════════════════════════════
        //  BUILD THE WELCOME SCREEN
        // ══════════════════════════════════════════════════════════════

        vec![
            Line::from(""),
            // ── HEADER BOX ──
            ftop("AETHER MIND", GREEN),
            fempty(),
            fcenter(vec![
                Span::styled(" █████  ███████ ████████ ██   ██ ███████ ██████  ", b(CYAN)),
                Span::styled("    ██    ██ ██ ██   ██ ██████  ", b(VIOLET)),
            ]),
            fcenter(vec![
                Span::styled("██   ██ ██         ██    ██   ██ ██      ██   ██ ", b(CYAN)),
                Span::styled("    ███  ███ ██ ███  ██ ██   ██ ", b(VIOLET)),
            ]),
            fcenter(vec![
                Span::styled("███████ █████      ██    ███████ █████   ██████  ", b(CYAN)),
                Span::styled("    ████████ ██ ██ ████ ██   ██ ", b(VIOLET)),
            ]),
            fcenter(vec![
                Span::styled("██   ██ ██         ██    ██   ██ ██      ██   ██ ", b(CYAN)),
                Span::styled("    ██ ██ ██ ██ ██  ███ ██   ██ ", b(VIOLET)),
            ]),
            fcenter(vec![
                Span::styled("██   ██ ███████    ██    ██   ██ ███████ ██   ██ ", b(CYAN)),
                Span::styled("    ██    ██ ██ ██   ██ ██████  ", b(VIOLET)),
            ]),
            fempty(),
            fcenter(vec![
                Span::styled("\"The Blockchain That Thinks\"", bi(WHITE)),
                Span::styled("  ·  ", s(DIM)),
                Span::styled("qbc.network", b(CYAN)),
                Span::styled("  ·  ", s(DIM)),
                Span::styled("Chain 3303", b(GREEN)),
            ]),
            fcenter(vec![
                Span::styled("On-chain AI", s(LABEL)),
                Span::styled(" · ", s(DIM)),
                Span::styled("Dilithium5", s(VIOLET)),
                Span::styled(" · ", s(DIM)),
                Span::styled("VQE Mining", s(AMBER)),
                Span::styled(" · ", s(DIM)),
                Span::styled("10 Sephirot", s(GREEN)),
                Span::styled(" · ", s(DIM)),
                Span::styled("Susy Swaps", s(CYAN)),
                Span::styled(" · ", s(DIM)),
                Span::styled("FedAvg Training", s(AMBER)),
            ]),
            fempty(),
            fbot(),
            Line::from(""),
            // ── NETWORK + SECURITY ──
            dtop("NETWORK", GREEN, "SECURITY", VIOLET),
            dual(
                vec![
                    Span::styled("Chain      ", s(LABEL)),
                    Span::styled("3303 (Mainnet)", b(GREEN)),
                ],
                vec![
                    Span::styled("Signatures ", s(LABEL)),
                    Span::styled("Dilithium5 NIST L5", b(VIOLET)),
                ],
            ),
            dual(
                vec![
                    Span::styled("Block      ", s(LABEL)),
                    Span::styled("3.3s target", s(WHITE)),
                ],
                vec![
                    Span::styled("Keystore   ", s(LABEL)),
                    Span::styled("Argon2id + AES-256-GCM", s(WHITE)),
                ],
            ),
            dual(
                vec![
                    Span::styled("Reward     ", s(LABEL)),
                    Span::styled("15.27 QBC", b(AMBER)),
                    Span::styled("/block", s(LABEL)),
                ],
                vec![
                    Span::styled("Public Key ", s(LABEL)),
                    Span::styled("2,592 bytes", s(WHITE)),
                ],
            ),
            dual(
                vec![
                    Span::styled("Supply     ", s(LABEL)),
                    Span::styled("3.3B QBC", b(AMBER)),
                    Span::styled(" max", s(LABEL)),
                ],
                vec![
                    Span::styled("Signature  ", s(LABEL)),
                    Span::styled("4,627 bytes", s(WHITE)),
                ],
            ),
            dual(
                vec![
                    Span::styled("Consensus  ", s(LABEL)),
                    Span::styled("PoSA + VQE Mining", s(WHITE)),
                ],
                vec![
                    Span::styled("Address    ", s(LABEL)),
                    Span::styled("SHA-256(pk) · 32 bytes", s(WHITE)),
                ],
            ),
            dbot(),
            Line::from(""),
            // ── CLI COMMANDS + WALLET ──
            dtop("CLI COMMANDS", GREEN, "WALLET", CYAN),
            dual(
                vec![
                    Span::styled("aether             ", b(GREEN)),
                    Span::styled("TUI chat interface", s(LABEL)),
                ],
                vec![
                    Span::styled("wallet create      ", b(CYAN)),
                    Span::styled("New Dilithium5 key", s(LABEL)),
                ],
            ),
            dual(
                vec![
                    Span::styled("aether --mine      ", b(GREEN)),
                    Span::styled("Chat + VQE mining", s(LABEL)),
                ],
                vec![
                    Span::styled("wallet list        ", b(CYAN)),
                    Span::styled("Show all wallets", s(LABEL)),
                ],
            ),
            dual(
                vec![
                    Span::styled("aether chat \"msg\"  ", b(GREEN)),
                    Span::styled("One-shot query", s(LABEL)),
                ],
                vec![
                    Span::styled("wallet balance     ", b(CYAN)),
                    Span::styled("On-chain QBC", s(LABEL)),
                ],
            ),
            dual(
                vec![
                    Span::styled("aether status      ", b(GREEN)),
                    Span::styled("Chain health", s(LABEL)),
                ],
                vec![
                    Span::styled("wallet send        ", b(CYAN)),
                    Span::styled("Sign + broadcast", s(LABEL)),
                ],
            ),
            dual(
                vec![
                    Span::styled("aether mine        ", b(GREEN)),
                    Span::styled("Headless VQE miner", s(LABEL)),
                ],
                vec![
                    Span::styled("wallet sign        ", b(CYAN)),
                    Span::styled("Sign a message", s(LABEL)),
                ],
            ),
            dual(
                vec![
                    Span::styled("aether search \"q\"  ", b(GREEN)),
                    Span::styled("Knowledge search", s(LABEL)),
                ],
                vec![
                    Span::styled("wallet verify      ", b(CYAN)),
                    Span::styled("Check signature", s(LABEL)),
                ],
            ),
            dbot(),
            Line::from(""),
            // ── IN-CHAT + MINING & REWARDS ──
            dtop("IN-CHAT COMMANDS", AMBER, "MINING & REWARDS", AMBER),
            dual(
                vec![
                    Span::styled("/status    ", b(AMBER)),
                    Span::styled("Chain stats + health", s(LABEL)),
                ],
                vec![
                    Span::styled("gradient status    ", b(GREEN)),
                    Span::styled("Pool info", s(LABEL)),
                ],
            ),
            dual(
                vec![
                    Span::styled("/info      ", b(AMBER)),
                    Span::styled("Model architecture", s(LABEL)),
                ],
                vec![
                    Span::styled("gradient submit    ", b(GREEN)),
                    Span::styled("Earn QBC rewards", s(LABEL)),
                ],
            ),
            dual(
                vec![
                    Span::styled("/gates     ", b(AMBER)),
                    Span::styled("AI milestone gates", s(LABEL)),
                ],
                vec![
                    Span::styled("rewards show       ", b(GREEN)),
                    Span::styled("Your earnings", s(LABEL)),
                ],
            ),
            dual(
                vec![
                    Span::styled("/search    ", b(AMBER)),
                    Span::styled("Knowledge query", s(LABEL)),
                ],
                vec![
                    Span::styled("rewards claim      ", b(GREEN)),
                    Span::styled("Claim to wallet", s(LABEL)),
                ],
            ),
            dual(
                vec![
                    Span::styled("/wallet    ", b(AMBER)),
                    Span::styled("Show wallet address", s(LABEL)),
                ],
                vec![
                    Span::styled("rewards pool       ", b(GREEN)),
                    Span::styled("Global pool stats", s(LABEL)),
                ],
            ),
            dual(
                vec![
                    Span::styled("/help      ", b(AMBER)),
                    Span::styled("All commands", s(LABEL)),
                ],
                vec![
                    Span::styled("/export    ", b(AMBER)),
                    Span::styled("Save chat to file", s(LABEL)),
                ],
            ),
            dbot(),
            Line::from(""),
            // ── INNOVATIONS ──
            ftop("INNOVATIONS (6 Patents)", VIOLET),
            frow2(
                vec![
                    Span::styled("cogwork   ", b(VIOLET)),
                    Span::styled("Proof-of-Cognitive-Work  (PoCW)", s(LABEL)),
                ],
                vec![
                    Span::styled("recover   ", b(VIOLET)),
                    Span::styled("ZK Cognitive Recovery    (ZCR)", s(LABEL)),
                ],
            ),
            frow2(
                vec![
                    Span::styled("entangle  ", b(VIOLET)),
                    Span::styled("Quantum-Entangled Wallet (QEW)", s(LABEL)),
                ],
                vec![
                    Span::styled("synapse   ", b(VIOLET)),
                    Span::styled("Symbiotic Mining AI     (SMIP)", s(LABEL)),
                ],
            ),
            frow2(
                vec![
                    Span::styled("optimize  ", b(VIOLET)),
                    Span::styled("Predictive UTXO Coalesce (PUC)", s(LABEL)),
                ],
                vec![
                    Span::styled("privacy   ", b(VIOLET)),
                    Span::styled("Susy Swaps — Stealth     (SS)", s(LABEL)),
                ],
            ),
            fbot(),
            Line::from(""),
            // ── TIP ──
            frow(vec![
                Span::styled("Tip: ", b(AMBER)),
                Span::styled("Type a message to chat with Aether Mind, or use ", s(LABEL)),
                Span::styled("/help", b(GREEN)),
                Span::styled(" to see all commands.", s(LABEL)),
            ]),
            Line::from(""),
            // ── FOOTER ──
            Line::from(vec![
                Span::styled("  ", Style::default()),
                Span::styled("Ctrl+C", b(AMBER)),
                Span::styled(" exit  ·  ", s(LABEL)),
                Span::styled("PgUp/PgDn", b(AMBER)),
                Span::styled(" scroll  ·  ", s(LABEL)),
                Span::styled("Ctrl+U", b(AMBER)),
                Span::styled(" clear input  ·  ", s(LABEL)),
                Span::styled("/quit", b(GREEN)),
                Span::styled(" exit", s(LABEL)),
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
                .as_millis()
                / 500)
                % 4
            {
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

        // Calculate wrapped height accounting for word-wrap
        let w = inner.width.max(1) as usize;
        let content_height: u16 = lines
            .iter()
            .map(|line| {
                let len: usize = line.spans.iter().map(|s| s.content.len()).sum();
                if len == 0 { 1u16 } else { ((len.max(1) - 1) / w + 1) as u16 }
            })
            .sum();
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
