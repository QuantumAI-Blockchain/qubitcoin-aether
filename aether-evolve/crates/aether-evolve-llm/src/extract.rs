use anyhow::Result;
use tracing::warn;

/// Extracted and parsed LLM response.
#[derive(Debug, Clone)]
pub struct ExtractedResponse {
    pub raw: String,
}

impl ExtractedResponse {
    pub fn new(raw: String) -> Self {
        Self { raw }
    }

    /// Extract content between XML tags.
    pub fn extract_xml(&self, tag: &str) -> Vec<String> {
        let open = format!("<{tag}>");
        let close = format!("</{tag}>");
        let mut results = Vec::new();
        let mut search_from = 0;

        while let Some(start) = self.raw[search_from..].find(&open) {
            let abs_start = search_from + start + open.len();
            if let Some(end) = self.raw[abs_start..].find(&close) {
                let content = self.raw[abs_start..abs_start + end].trim().to_string();
                results.push(content);
                search_from = abs_start + end + close.len();
            } else {
                break;
            }
        }

        results
    }

    /// Extract JSON code blocks.
    pub fn extract_json_blocks(&self) -> Vec<String> {
        let mut results = Vec::new();
        let mut search_from = 0;

        while let Some(start) = self.raw[search_from..].find("```json") {
            let abs_start = search_from + start + 7; // len("```json")
            if let Some(end) = self.raw[abs_start..].find("```") {
                let content = self.raw[abs_start..abs_start + end].trim().to_string();
                results.push(content);
                search_from = abs_start + end + 3;
            } else {
                break;
            }
        }

        results
    }

    /// Parse SEARCH/REPLACE patches from the response.
    pub fn extract_patches(&self) -> Vec<(String, String)> {
        let patches = self.extract_xml("patch");
        let mut results = Vec::new();

        for patch in patches {
            let search_parts = extract_between(&patch, "<search>", "</search>");
            let replace_parts = extract_between(&patch, "<replace>", "</replace>");

            if let (Some(search), Some(replace)) = (search_parts, replace_parts) {
                results.push((search, replace));
            } else {
                warn!("Malformed patch block, skipping");
            }
        }

        results
    }

    /// Extract diagnosis items.
    pub fn extract_diagnosis_items(&self) -> Vec<DiagnosisXml> {
        let items = self.extract_xml("item");
        let mut results = Vec::new();

        for item_raw in items {
            // Wrap it back for inner parsing
            let wrapped = format!("<item>{item_raw}</item>");
            results.push(DiagnosisXml {
                description: extract_between(&wrapped, "<description>", "</description>")
                    .unwrap_or_default(),
                root_cause: extract_between(&wrapped, "<root_cause>", "</root_cause>")
                    .unwrap_or_default(),
                intervention: extract_between(&wrapped, "<intervention>", "</intervention>")
                    .unwrap_or_default(),
                target_files: extract_between(&wrapped, "<target_files>", "</target_files>")
                    .unwrap_or_default(),
                expected_improvement: extract_between(
                    &wrapped,
                    "<expected_improvement>",
                    "</expected_improvement>",
                )
                .unwrap_or_default(),
            });
        }

        results
    }

    /// Try to parse the response as JSON.
    pub fn parse_json<T: serde::de::DeserializeOwned>(&self) -> Result<T> {
        // Try raw first
        if let Ok(v) = serde_json::from_str(&self.raw) {
            return Ok(v);
        }
        // Try extracting from code blocks
        for block in self.extract_json_blocks() {
            if let Ok(v) = serde_json::from_str(&block) {
                return Ok(v);
            }
        }
        anyhow::bail!("No valid JSON found in response")
    }
}

#[derive(Debug, Clone)]
pub struct DiagnosisXml {
    pub description: String,
    pub root_cause: String,
    pub intervention: String,
    pub target_files: String,
    pub expected_improvement: String,
}

fn extract_between(text: &str, open: &str, close: &str) -> Option<String> {
    let start = text.find(open)?;
    let abs_start = start + open.len();
    let end = text[abs_start..].find(close)?;
    Some(text[abs_start..abs_start + end].trim().to_string())
}
