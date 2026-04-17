use anyhow::{Context, Result};
use chrono::Utc;
use serde::Serialize;
use std::fs::OpenOptions;
use std::io::Write;
use std::path::PathBuf;

pub struct AuditLog {
    log_path: PathBuf,
}

#[derive(Debug, Serialize)]
struct AuditEntry {
    timestamp: String,
    step: u64,
    action: String,
    details: String,
    success: bool,
}

impl AuditLog {
    pub fn new(data_dir: &std::path::Path) -> Result<Self> {
        let log_path = data_dir.join("audit.jsonl");
        // Ensure parent exists
        if let Some(parent) = log_path.parent() {
            std::fs::create_dir_all(parent).context("Failed to create audit log directory")?;
        }
        Ok(Self { log_path })
    }

    pub fn record(
        &self,
        step: u64,
        action: &str,
        details: &str,
        success: bool,
    ) -> Result<()> {
        let entry = AuditEntry {
            timestamp: Utc::now().to_rfc3339(),
            step,
            action: action.to_string(),
            details: details.to_string(),
            success,
        };

        let line = serde_json::to_string(&entry).context("Failed to serialize audit entry")?;

        let mut file = OpenOptions::new()
            .create(true)
            .append(true)
            .open(&self.log_path)
            .context("Failed to open audit log")?;

        writeln!(file, "{line}").context("Failed to write audit entry")?;
        Ok(())
    }
}
