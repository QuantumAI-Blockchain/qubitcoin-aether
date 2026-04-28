use ratatui::layout::Rect;
use ratatui::style::{Color, Modifier, Style};
use ratatui::text::{Line, Span};
use ratatui::widgets::{Block, Borders, Paragraph};
use ratatui::Frame;

use crate::{AMBER, BORDER, DIM, GREEN, VIOLET};

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

    pub fn draw(&self, frame: &mut Frame, area: Rect) {
        let block = Block::default()
            .borders(Borders::TOP)
            .border_style(Style::default().fg(BORDER));

        let label = Style::default().fg(DIM);
        let val = Style::default().fg(Color::White);

        let mining_spans: Vec<Span> = match &self.mining {
            MiningStatus::Off => vec![
                Span::styled("Mining ", label),
                Span::styled("OFF", Style::default().fg(DIM)),
            ],
            MiningStatus::Running { hashrate, blocks_found } => vec![
                Span::styled("Mining ", label),
                Span::styled(
                    format!("{hashrate:.1} H/s"),
                    Style::default().fg(AMBER).add_modifier(Modifier::BOLD),
                ),
                Span::styled(format!(" ({blocks_found} found)"), Style::default().fg(AMBER)),
            ],
        };

        let wallet_spans: Vec<Span> = match &self.wallet_addr {
            Some(addr) => {
                let short = if addr.len() > 14 {
                    format!("{}..{}", &addr[..6], &addr[addr.len() - 4..])
                } else {
                    addr.clone()
                };
                vec![Span::styled(short, Style::default().fg(VIOLET))]
            }
            None => vec![Span::styled("no wallet", label)],
        };

        let conn = if self.connected {
            Span::styled(" * ", Style::default().fg(GREEN).add_modifier(Modifier::BOLD))
        } else {
            Span::styled(" x ", Style::default().fg(Color::Red).add_modifier(Modifier::BOLD))
        };

        let sep = Span::styled(" | ", label);

        let mut spans = vec![
            Span::styled(" ", Style::default()),
            conn,
            Span::styled("h:", label),
            Span::styled(
                crate::format_with_commas(self.chain_height),
                val,
            ),
            sep.clone(),
            Span::styled("phi:", label),
            Span::styled(format!("{:.3}", self.phi), Style::default().fg(GREEN)),
            sep.clone(),
            Span::styled("v:", label),
            Span::styled(crate::format_vectors(self.knowledge_vectors), val),
            sep.clone(),
            Span::styled("g:", label),
            Span::styled(
                format!("{}/10", self.gates_passed),
                Style::default().fg(if self.gates_passed >= 6 { GREEN } else { AMBER }),
            ),
            sep.clone(),
        ];
        spans.extend(mining_spans);
        spans.push(sep.clone());
        spans.extend(wallet_spans);

        let line = Line::from(spans);
        let paragraph = Paragraph::new(line).block(block);
        frame.render_widget(paragraph, area);
    }
}
