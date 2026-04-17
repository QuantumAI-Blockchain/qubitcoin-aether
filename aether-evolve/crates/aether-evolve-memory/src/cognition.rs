use anyhow::{Context, Result};
use serde::{Deserialize, Serialize};
use std::path::PathBuf;
use tracing::info;

/// A cognition item — domain knowledge used to inform evolution decisions.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CognitionItem {
    pub id: String,
    pub domain: String,
    pub title: String,
    pub content: String,
    pub tags: Vec<String>,
}

/// File-backed cognition store. Loads from TOML files in the cognition/ directory.
pub struct CognitionStore {
    items: Vec<CognitionItem>,
}

impl CognitionStore {
    /// Load all cognition items from TOML files in the given directory.
    pub fn load(cognition_dir: &std::path::Path) -> Result<Self> {
        let mut items = Vec::new();

        if !cognition_dir.exists() {
            info!("Cognition directory does not exist, starting empty");
            return Ok(Self { items });
        }

        for entry in std::fs::read_dir(cognition_dir).context("Failed to read cognition dir")? {
            let entry = entry?;
            let path = entry.path();
            if path.extension().and_then(|e| e.to_str()) == Some("toml") {
                match load_cognition_file(&path) {
                    Ok(mut file_items) => {
                        info!(
                            file = %path.display(),
                            count = file_items.len(),
                            "Loaded cognition items"
                        );
                        items.append(&mut file_items);
                    }
                    Err(e) => {
                        tracing::warn!(file = %path.display(), "Failed to load cognition file: {e}");
                    }
                }
            }
        }

        info!(total = items.len(), "Cognition store loaded");
        Ok(Self { items })
    }

    /// Search for items by keyword (simple substring match).
    pub fn search(&self, query: &str, max_results: usize) -> Vec<&CognitionItem> {
        let query_lower = query.to_lowercase();
        let mut results: Vec<&CognitionItem> = self
            .items
            .iter()
            .filter(|item| {
                item.content.to_lowercase().contains(&query_lower)
                    || item.title.to_lowercase().contains(&query_lower)
                    || item.tags.iter().any(|t| t.to_lowercase().contains(&query_lower))
            })
            .collect();
        results.truncate(max_results);
        results
    }

    /// Get all items for a domain.
    pub fn by_domain(&self, domain: &str) -> Vec<&CognitionItem> {
        self.items
            .iter()
            .filter(|item| item.domain == domain)
            .collect()
    }

    pub fn count(&self) -> usize {
        self.items.len()
    }

    /// Add a new item (learned from experiments).
    pub fn add(&mut self, item: CognitionItem) {
        self.items.push(item);
    }

    /// Save new items to a file.
    pub fn save_learned(&self, data_dir: &std::path::Path) -> Result<()> {
        let path = data_dir.join("learned_cognition.jsonl");
        let mut file = std::fs::OpenOptions::new()
            .create(true)
            .write(true)
            .truncate(true)
            .open(&path)
            .context("Failed to open learned cognition file")?;

        use std::io::Write;
        for item in &self.items {
            let line = serde_json::to_string(item)?;
            writeln!(file, "{line}")?;
        }
        Ok(())
    }
}

#[derive(Deserialize)]
struct CognitionFile {
    #[serde(default)]
    domain: String,
    #[serde(default)]
    items: Vec<CognitionFileItem>,
}

#[derive(Deserialize)]
struct CognitionFileItem {
    #[serde(default)]
    id: String,
    #[serde(default)]
    title: String,
    #[serde(default)]
    content: String,
    #[serde(default)]
    tags: Vec<String>,
}

fn load_cognition_file(path: &PathBuf) -> Result<Vec<CognitionItem>> {
    let content = std::fs::read_to_string(path)?;
    let file: CognitionFile = toml::from_str(&content)?;
    Ok(file
        .items
        .into_iter()
        .map(|item| CognitionItem {
            id: item.id,
            domain: file.domain.clone(),
            title: item.title,
            content: item.content,
            tags: item.tags,
        })
        .collect())
}
