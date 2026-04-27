pub mod chat;
pub mod input;
pub mod status;

use ratatui::layout::{Constraint, Direction, Layout};
use ratatui::Frame;

use chat::ChatPanel;
use input::InputPanel;
use status::StatusBar;

/// Top-level TUI app state.
pub struct App {
    pub chat: ChatPanel,
    pub input: InputPanel,
    pub status: StatusBar,
    pub should_quit: bool,
}

impl App {
    pub fn new() -> Self {
        Self {
            chat: ChatPanel::new(),
            input: InputPanel::new(),
            status: StatusBar::new(),
            should_quit: false,
        }
    }

    /// Render the full TUI layout.
    pub fn draw(&self, frame: &mut Frame) {
        let area = frame.area();

        // Main layout: [chat | input | status]
        let chunks = Layout::default()
            .direction(Direction::Vertical)
            .constraints([
                Constraint::Min(6),       // chat history (fills remaining)
                Constraint::Length(3),     // input box
                Constraint::Length(1),     // status bar
            ])
            .split(area);

        self.chat.draw(frame, chunks[0]);
        self.input.draw(frame, chunks[1]);
        self.status.draw(frame, chunks[2]);
    }
}
