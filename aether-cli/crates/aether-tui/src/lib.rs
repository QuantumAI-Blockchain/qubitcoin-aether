pub mod chat;
pub mod input;
pub mod status;

use ratatui::layout::{Constraint, Direction, Layout, Rect};
use ratatui::style::{Color, Modifier, Style};
use ratatui::text::{Line, Span};
use ratatui::widgets::{Block, Borders, Paragraph};
use ratatui::Frame;

use chat::ChatPanel;
use input::InputPanel;
use status::StatusBar;

/// Quantum green accent color.
pub const GREEN: Color = Color::Rgb(0, 255, 136);
/// Quantum violet accent.
pub const VIOLET: Color = Color::Rgb(124, 58, 237);
/// Amber accent.
pub const AMBER: Color = Color::Rgb(245, 158, 11);
/// Surface background.
pub const SURFACE: Color = Color::Rgb(18, 18, 26);
/// Dim text.
pub const DIM: Color = Color::Rgb(80, 80, 100);
/// Border color.
pub const BORDER: Color = Color::Rgb(50, 50, 70);

/// Top-level TUI app state.
pub struct App {
    pub chat: ChatPanel,
    pub input: InputPanel,
    pub status: StatusBar,
    pub should_quit: bool,
    pub show_sidebar: bool,
    frame_count: u64,
}

impl App {
    pub fn new() -> Self {
        Self {
            chat: ChatPanel::new(),
            input: InputPanel::new(),
            status: StatusBar::new(),
            should_quit: false,
            show_sidebar: true,
            frame_count: 0,
        }
    }

    /// Render the full TUI layout.
    pub fn draw(&mut self, frame: &mut Frame) {
        self.frame_count += 1;
        let area = frame.area();

        // Main layout: [header(3) | body | status(2)]
        let outer = Layout::default()
            .direction(Direction::Vertical)
            .constraints([
                Constraint::Length(3),     // header banner
                Constraint::Min(8),       // body (chat + optional sidebar)
                Constraint::Length(3),     // input box
                Constraint::Length(2),     // status bar
            ])
            .split(area);

        self.draw_header(frame, outer[0]);

        // Body: chat (+ sidebar if wide enough)
        if area.width >= 80 && self.show_sidebar {
            let body = Layout::default()
                .direction(Direction::Horizontal)
                .constraints([
                    Constraint::Min(40),      // chat panel
                    Constraint::Length(30),    // sidebar
                ])
                .split(outer[1]);

            self.chat.draw(frame, body[0]);
            self.draw_sidebar(frame, body[1]);
        } else {
            self.chat.draw(frame, outer[1]);
        }

        self.input.draw(frame, outer[2]);
        self.status.draw(frame, outer[3]);
    }

    fn draw_header(&self, frame: &mut Frame, area: Rect) {
        let block = Block::default()
            .borders(Borders::BOTTOM)
            .border_style(Style::default().fg(BORDER));

        let inner = block.inner(area);

        // Animated pulse on the dot
        let pulse_char = if (self.frame_count / 10) % 2 == 0 { "*" } else { "." };

        let title_line = Line::from(vec![
            Span::styled("  ", Style::default()),
            Span::styled("AETHER", Style::default().fg(GREEN).add_modifier(Modifier::BOLD)),
            Span::styled(" ", Style::default()),
            Span::styled("MIND", Style::default().fg(Color::White).add_modifier(Modifier::BOLD)),
            Span::styled(
                format!(" {pulse_char} "),
                Style::default().fg(if self.status.connected { GREEN } else { Color::Red }),
            ),
            Span::styled(
                "The Blockchain That Thinks",
                Style::default().fg(DIM).add_modifier(Modifier::ITALIC),
            ),
        ]);

        let subtitle = Line::from(vec![
            Span::styled("  ", Style::default()),
            Span::styled("Dilithium5", Style::default().fg(VIOLET)),
            Span::styled(" | ", Style::default().fg(DIM)),
            Span::styled("VQE Mining", Style::default().fg(AMBER)),
            Span::styled(" | ", Style::default().fg(DIM)),
            Span::styled("Susy Swaps", Style::default().fg(GREEN)),
            Span::styled(" | ", Style::default().fg(DIM)),
            Span::styled("FedAvg Neural Training", Style::default().fg(Color::Rgb(100, 180, 255))),
        ]);

        let header = Paragraph::new(vec![title_line, subtitle]).block(block);
        frame.render_widget(header, area);
    }

    fn draw_sidebar(&self, frame: &mut Frame, area: Rect) {
        let block = Block::default()
            .borders(Borders::LEFT | Borders::TOP | Borders::BOTTOM)
            .border_style(Style::default().fg(BORDER))
            .title(Span::styled(
                " System ",
                Style::default().fg(VIOLET).add_modifier(Modifier::BOLD),
            ));

        let inner = block.inner(area);
        let mut lines: Vec<Line> = Vec::new();

        // Connection status
        let conn = if self.status.connected {
            Span::styled(" CONNECTED ", Style::default().fg(Color::Black).bg(GREEN))
        } else {
            Span::styled(" OFFLINE ", Style::default().fg(Color::White).bg(Color::Red))
        };
        lines.push(Line::from(vec![Span::raw(" "), conn]));
        lines.push(Line::from(""));

        // Chain stats
        lines.push(Line::from(vec![
            Span::styled(" Height ", Style::default().fg(DIM)),
            Span::styled(
                format_with_commas(self.status.chain_height),
                Style::default().fg(Color::White),
            ),
        ]));

        lines.push(Line::from(vec![
            Span::styled(" Phi    ", Style::default().fg(DIM)),
            Span::styled(
                format!("{:.6}", self.status.phi),
                Style::default().fg(GREEN),
            ),
        ]));

        lines.push(Line::from(vec![
            Span::styled(" Vectors ", Style::default().fg(DIM)),
            Span::styled(
                format_vectors(self.status.knowledge_vectors),
                Style::default().fg(Color::White),
            ),
        ]));

        lines.push(Line::from(vec![
            Span::styled(" Gates  ", Style::default().fg(DIM)),
            Span::styled(
                format!("{}/10", self.status.gates_passed),
                Style::default().fg(if self.status.gates_passed >= 6 { GREEN } else { AMBER }),
            ),
        ]));

        lines.push(Line::from(""));

        // Mining status
        match &self.status.mining {
            status::MiningStatus::Off => {
                lines.push(Line::from(Span::styled(
                    " Mining OFF",
                    Style::default().fg(DIM),
                )));
            }
            status::MiningStatus::Running { hashrate, blocks_found } => {
                lines.push(Line::from(vec![
                    Span::styled(" ", Style::default()),
                    Span::styled("MINING", Style::default().fg(Color::Black).bg(AMBER).add_modifier(Modifier::BOLD)),
                ]));
                lines.push(Line::from(vec![
                    Span::styled(" Rate  ", Style::default().fg(DIM)),
                    Span::styled(
                        format!("{hashrate:.1} H/s"),
                        Style::default().fg(AMBER),
                    ),
                ]));
                lines.push(Line::from(vec![
                    Span::styled(" Found ", Style::default().fg(DIM)),
                    Span::styled(
                        blocks_found.to_string(),
                        Style::default().fg(GREEN),
                    ),
                ]));
            }
        }

        lines.push(Line::from(""));

        // Wallet
        if let Some(ref addr) = self.status.wallet_addr {
            let short = if addr.len() > 16 {
                format!("{}..{}", &addr[..8], &addr[addr.len() - 6..])
            } else {
                addr.clone()
            };
            lines.push(Line::from(vec![
                Span::styled(" Wallet ", Style::default().fg(DIM)),
            ]));
            lines.push(Line::from(vec![
                Span::styled(format!(" {short}"), Style::default().fg(VIOLET)),
            ]));
        } else {
            lines.push(Line::from(Span::styled(
                " No wallet",
                Style::default().fg(DIM),
            )));
        }

        // Fill remaining space with empty lines for clean look
        while lines.len() < inner.height as usize {
            lines.push(Line::from(""));
        }

        let paragraph = Paragraph::new(lines).block(block);
        frame.render_widget(paragraph, area);
    }
}

fn format_with_commas(n: u64) -> String {
    let s = n.to_string();
    let mut result = String::with_capacity(s.len() + s.len() / 3);
    for (i, c) in s.chars().rev().enumerate() {
        if i > 0 && i % 3 == 0 {
            result.push(',');
        }
        result.push(c);
    }
    result.chars().rev().collect()
}

fn format_vectors(n: usize) -> String {
    if n >= 1_000_000 {
        format!("{:.1}M", n as f64 / 1_000_000.0)
    } else if n >= 1_000 {
        format!("{:.1}K", n as f64 / 1_000.0)
    } else {
        n.to_string()
    }
}
