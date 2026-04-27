use ratatui::layout::Rect;
use ratatui::style::{Color, Style};
use ratatui::text::Span;
use ratatui::widgets::{Block, Borders, Paragraph};
use ratatui::Frame;

pub struct InputPanel {
    pub content: String,
    pub cursor_pos: usize,
}

impl InputPanel {
    pub fn new() -> Self {
        Self {
            content: String::new(),
            cursor_pos: 0,
        }
    }

    pub fn insert(&mut self, c: char) {
        self.content.insert(self.cursor_pos, c);
        self.cursor_pos += c.len_utf8();
    }

    pub fn backspace(&mut self) {
        if self.cursor_pos > 0 {
            // Find the previous char boundary
            let prev = self.content[..self.cursor_pos]
                .char_indices()
                .next_back()
                .map(|(i, _)| i)
                .unwrap_or(0);
            self.content.drain(prev..self.cursor_pos);
            self.cursor_pos = prev;
        }
    }

    pub fn delete(&mut self) {
        if self.cursor_pos < self.content.len() {
            let next = self.content[self.cursor_pos..]
                .char_indices()
                .nth(1)
                .map(|(i, _)| self.cursor_pos + i)
                .unwrap_or(self.content.len());
            self.content.drain(self.cursor_pos..next);
        }
    }

    pub fn move_left(&mut self) {
        if self.cursor_pos > 0 {
            self.cursor_pos = self.content[..self.cursor_pos]
                .char_indices()
                .next_back()
                .map(|(i, _)| i)
                .unwrap_or(0);
        }
    }

    pub fn move_right(&mut self) {
        if self.cursor_pos < self.content.len() {
            self.cursor_pos = self.content[self.cursor_pos..]
                .char_indices()
                .nth(1)
                .map(|(i, _)| self.cursor_pos + i)
                .unwrap_or(self.content.len());
        }
    }

    pub fn home(&mut self) {
        self.cursor_pos = 0;
    }

    pub fn end(&mut self) {
        self.cursor_pos = self.content.len();
    }

    pub fn take(&mut self) -> String {
        let text = std::mem::take(&mut self.content);
        self.cursor_pos = 0;
        text
    }

    pub fn clear(&mut self) {
        self.content.clear();
        self.cursor_pos = 0;
    }

    pub fn draw(&self, frame: &mut Frame, area: Rect) {
        let block = Block::default()
            .borders(Borders::ALL)
            .border_style(Style::default().fg(Color::DarkGray))
            .title(Span::styled(
                " > ",
                Style::default().fg(Color::Rgb(0, 255, 136)),
            ));

        let inner = block.inner(area);

        // Show content with cursor
        let display = if self.content.is_empty() {
            Paragraph::new(Span::styled(
                "Type your message... (Enter to send, Ctrl+C to exit)",
                Style::default().fg(Color::DarkGray),
            ))
        } else {
            Paragraph::new(Span::raw(&self.content))
        };

        frame.render_widget(display.block(block), area);

        // Place cursor
        let cursor_x = inner.x + self.cursor_display_offset() as u16;
        let cursor_y = inner.y;
        frame.set_cursor_position((cursor_x, cursor_y));
    }

    fn cursor_display_offset(&self) -> usize {
        // Count display width of chars before cursor
        self.content[..self.cursor_pos].chars().count()
    }
}
