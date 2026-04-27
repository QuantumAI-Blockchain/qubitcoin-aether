use ratatui::layout::Rect;
use ratatui::style::{Color, Modifier, Style};
use ratatui::text::{Line, Span};
use ratatui::widgets::Paragraph;
use ratatui::Frame;

pub struct StatusBar {
    pub chain_height: u64,
    pub phi: f64,
    pub knowledge_vectors: usize,
    pub gates_passed: u8,
    pub mining: MiningStatus,
    pub wallet_addr: Option<String>,
    pub connected: bool,
}

pub enum MiningStatus {
    Off,
    Running {
        hashrate: f64,
        blocks_found: u64,
    },
}

impl StatusBar {
    pub fn new() -> Self {
        Self {
            chain_height: 0,
            phi: 0.0,
            knowledge_vectors: 0,
            gates_passed: 0,
            mining: MiningStatus::Off,
            wallet_addr: None,
            connected: false,
        }
    }

    fn format_vectors(&self) -> String {
        if self.knowledge_vectors >= 1_000_000 {
            format!("{:.1}M", self.knowledge_vectors as f64 / 1_000_000.0)
        } else if self.knowledge_vectors >= 1_000 {
            format!("{:.1}K", self.knowledge_vectors as f64 / 1_000.0)
        } else {
            self.knowledge_vectors.to_string()
        }
    }

    pub fn draw(&self, frame: &mut Frame, area: Rect) {
        let green = Color::Rgb(0, 255, 136);
        let dim = Style::default().fg(Color::DarkGray);
        let val = Style::default().fg(Color::White);

        let mining_span = match &self.mining {
            MiningStatus::Off => Span::styled("Mining: OFF", dim),
            MiningStatus::Running { hashrate, blocks_found } => Span::styled(
                format!("Mining: {hashrate:.1} H/s | {blocks_found} blocks"),
                Style::default().fg(green),
            ),
        };

        let wallet_span = match &self.wallet_addr {
            Some(addr) => {
                let short = if addr.len() > 12 {
                    format!("{}...{}", &addr[..6], &addr[addr.len() - 4..])
                } else {
                    addr.clone()
                };
                Span::styled(format!("Wallet: {short}"), val)
            }
            None => Span::styled("Wallet: not configured", dim),
        };

        let conn_indicator = if self.connected {
            Span::styled(" * ", Style::default().fg(green).add_modifier(Modifier::BOLD))
        } else {
            Span::styled(" x ", Style::default().fg(Color::Red).add_modifier(Modifier::BOLD))
        };

        let line = Line::from(vec![
            Span::styled(" ", Style::default()),
            conn_indicator,
            Span::styled("height: ", dim),
            Span::styled(
                format_with_commas(self.chain_height),
                val,
            ),
            Span::styled(" | ", dim),
            Span::styled("phi: ", dim),
            Span::styled(format!("{:.3}", self.phi), Style::default().fg(green)),
            Span::styled(" | ", dim),
            Span::styled("vectors: ", dim),
            Span::styled(self.format_vectors(), val),
            Span::styled(" | ", dim),
            Span::styled("gate: ", dim),
            Span::styled(format!("{}/10", self.gates_passed), val),
            Span::styled(" | ", dim),
            mining_span,
            Span::styled(" | ", dim),
            wallet_span,
        ]);

        frame.render_widget(Paragraph::new(line), area);
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
