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

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_extract_xml_single_tag() {
        let resp = ExtractedResponse::new(
            "prefix <description>This is a test</description> suffix".into(),
        );
        let results = resp.extract_xml("description");
        assert_eq!(results.len(), 1);
        assert_eq!(results[0], "This is a test");
    }

    #[test]
    fn test_extract_xml_multiple_tags() {
        let resp = ExtractedResponse::new(
            "<item>first</item> middle <item>second</item> end".into(),
        );
        let results = resp.extract_xml("item");
        assert_eq!(results.len(), 2);
        assert_eq!(results[0], "first");
        assert_eq!(results[1], "second");
    }

    #[test]
    fn test_extract_xml_no_match() {
        let resp = ExtractedResponse::new("no tags here".into());
        assert!(resp.extract_xml("missing").is_empty());
    }

    #[test]
    fn test_extract_xml_trims_whitespace() {
        let resp = ExtractedResponse::new("<code>\n  some code  \n</code>".into());
        let results = resp.extract_xml("code");
        assert_eq!(results[0], "some code");
    }

    #[test]
    fn test_extract_json_blocks() {
        let resp = ExtractedResponse::new(
            "Here:\n```json\n{\"key\": \"value\"}\n```\nMore:\n```json\n[1, 2]\n```\n".into(),
        );
        let blocks = resp.extract_json_blocks();
        assert_eq!(blocks.len(), 2);
        assert_eq!(blocks[0], "{\"key\": \"value\"}");
        assert_eq!(blocks[1], "[1, 2]");
    }

    #[test]
    fn test_extract_json_blocks_empty() {
        let resp = ExtractedResponse::new("no json here".into());
        assert!(resp.extract_json_blocks().is_empty());
    }

    #[test]
    fn test_extract_patches() {
        let resp = ExtractedResponse::new(
            "<patch>\n<search>old_fn()</search>\n<replace>new_fn()</replace>\n</patch>".into(),
        );
        let patches = resp.extract_patches();
        assert_eq!(patches.len(), 1);
        assert_eq!(patches[0].0, "old_fn()");
        assert_eq!(patches[0].1, "new_fn()");
    }

    #[test]
    fn test_extract_patches_multiple() {
        let resp = ExtractedResponse::new(
            "<patch><search>a</search><replace>b</replace></patch>\n\
             <patch><search>c</search><replace>d</replace></patch>"
                .into(),
        );
        let patches = resp.extract_patches();
        assert_eq!(patches.len(), 2);
    }

    #[test]
    fn test_extract_patches_malformed_skipped() {
        let resp = ExtractedResponse::new(
            "<patch><search>only search</search></patch>".into(),
        );
        assert!(resp.extract_patches().is_empty());
    }

    #[test]
    fn test_extract_diagnosis_items() {
        let resp = ExtractedResponse::new(
            "<item>\n\
             <description>Phi is zero</description>\n\
             <root_cause>No nodes</root_cause>\n\
             <intervention>knowledge_seed</intervention>\n\
             <target_files>kg.py</target_files>\n\
             <expected_improvement>Phi > 0</expected_improvement>\n\
             </item>"
                .into(),
        );
        let items = resp.extract_diagnosis_items();
        assert_eq!(items.len(), 1);
        assert_eq!(items[0].description, "Phi is zero");
        assert_eq!(items[0].root_cause, "No nodes");
        assert_eq!(items[0].intervention, "knowledge_seed");
    }

    #[test]
    fn test_parse_json_direct() {
        let resp = ExtractedResponse::new(r#"{"name": "test", "value": 42}"#.into());
        let parsed: serde_json::Value = resp.parse_json().unwrap();
        assert_eq!(parsed["name"], "test");
        assert_eq!(parsed["value"], 42);
    }

    #[test]
    fn test_parse_json_from_code_block() {
        let resp = ExtractedResponse::new(
            "Result:\n```json\n{\"status\": \"ok\"}\n```\n".into(),
        );
        let parsed: serde_json::Value = resp.parse_json().unwrap();
        assert_eq!(parsed["status"], "ok");
    }

    #[test]
    fn test_parse_json_no_json_fails() {
        let resp = ExtractedResponse::new("just plain text".into());
        let result: Result<serde_json::Value, _> = resp.parse_json();
        assert!(result.is_err());
    }

    #[test]
    fn test_extract_between_helper() {
        assert_eq!(
            extract_between("<a>hello</a>", "<a>", "</a>"),
            Some("hello".into())
        );
        assert_eq!(extract_between("no tags", "<a>", "</a>"), None);
        assert_eq!(
            extract_between("<a>  spaced  </a>", "<a>", "</a>"),
            Some("spaced".into())
        );
    }
}
