use ratatui::layout::Rect;
use ratatui::style::{Color, Modifier, Style};
use ratatui::text::{Line, Span};
use ratatui::widgets::{Block, Borders, Paragraph, Wrap};
use ratatui::Frame;

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
                content: "Welcome to Aether Mind. Type a message to begin.".into(),
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

    pub fn draw(&self, frame: &mut Frame, area: Rect) {
        let block = Block::default()
            .borders(Borders::ALL)
            .border_style(Style::default().fg(Color::DarkGray))
            .title(Span::styled(
                " Aether Mind ",
                Style::default()
                    .fg(Color::Rgb(0, 255, 136))
                    .add_modifier(Modifier::BOLD),
            ));

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
                            "  You: ",
                            Style::default()
                                .fg(Color::Cyan)
                                .add_modifier(Modifier::BOLD),
                        ),
                        Span::raw(""),
                    ]));
                    for text_line in msg.content.lines() {
                        lines.push(Line::from(format!("  {text_line}")));
                    }
                }
                Role::Aether => {
                    lines.push(Line::from(vec![Span::styled(
                        "  Aether: ",
                        Style::default()
                            .fg(Color::Rgb(0, 255, 136))
                            .add_modifier(Modifier::BOLD),
                    )]));
                    for text_line in msg.content.lines() {
                        // Simple markdown-ish: lines starting with ``` get code color
                        if text_line.trim_start().starts_with("```") {
                            lines.push(Line::from(Span::styled(
                                format!("  {text_line}"),
                                Style::default().fg(Color::DarkGray),
                            )));
                        } else if text_line.trim_start().starts_with("- ")
                            || text_line.trim_start().starts_with("* ")
                        {
                            lines.push(Line::from(Span::styled(
                                format!("  {text_line}"),
                                Style::default().fg(Color::White),
                            )));
                        } else {
                            lines.push(Line::from(format!("  {text_line}")));
                        }
                    }
                }
                Role::System => {
                    for text_line in msg.content.lines() {
                        lines.push(Line::from(Span::styled(
                            format!("  {text_line}"),
                            Style::default()
                                .fg(Color::DarkGray)
                                .add_modifier(Modifier::ITALIC),
                        )));
                    }
                }
            }
        }

        // If waiting, add a spinner line
        if self.waiting {
            lines.push(Line::from(""));
            lines.push(Line::from(Span::styled(
                "  Aether is thinking...",
                Style::default()
                    .fg(Color::Rgb(0, 255, 136))
                    .add_modifier(Modifier::ITALIC),
            )));
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
