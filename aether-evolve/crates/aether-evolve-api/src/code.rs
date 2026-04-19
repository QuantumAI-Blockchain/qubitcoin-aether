use aether_evolve_core::CodeDiff;
use anyhow::{bail, Context, Result};
use std::path::Path;
use std::process::Command;
use tracing::{debug, info, warn};

pub struct CodePatcher {
    repo_root: String,
}

impl CodePatcher {
    pub fn new(repo_root: &str) -> Self {
        Self {
            repo_root: repo_root.to_string(),
        }
    }

    /// Apply a set of SEARCH/REPLACE diffs to files.
    ///
    /// Uses a multi-strategy matching approach:
    /// 1. Exact match (fastest, most reliable)
    /// 2. Whitespace-normalized match (handles indentation differences)
    /// 3. Line-by-line fuzzy match (handles LLM adding/removing blank lines)
    pub fn apply_diffs(&self, diffs: &[CodeDiff]) -> Result<Vec<String>> {
        let mut changed_files = Vec::new();

        for diff in diffs {
            let full_path = if diff.file_path.starts_with('/') {
                diff.file_path.clone()
            } else {
                format!("{}/{}", self.repo_root, diff.file_path)
            };

            let path = Path::new(&full_path);
            if !path.exists() {
                bail!("Target file does not exist: {full_path}");
            }

            let content = std::fs::read_to_string(path)
                .with_context(|| format!("Failed to read {full_path}"))?;

            // Strategy 1: Exact match
            if content.contains(&diff.search) {
                let new_content = content.replacen(&diff.search, &diff.replace, 1);
                std::fs::write(path, &new_content)
                    .with_context(|| format!("Failed to write {full_path}"))?;
                changed_files.push(diff.file_path.clone());
                info!(file = %diff.file_path, strategy = "exact", "Applied diff");
                continue;
            }

            // Strategy 2: Whitespace-normalized match
            if let Some(new_content) = self.try_normalized_match(&content, &diff.search, &diff.replace) {
                std::fs::write(path, &new_content)
                    .with_context(|| format!("Failed to write {full_path}"))?;
                changed_files.push(diff.file_path.clone());
                info!(file = %diff.file_path, strategy = "normalized", "Applied diff");
                continue;
            }

            // Strategy 3: Line-by-line fuzzy match
            if let Some(new_content) = self.try_fuzzy_line_match(&content, &diff.search, &diff.replace) {
                std::fs::write(path, &new_content)
                    .with_context(|| format!("Failed to write {full_path}"))?;
                changed_files.push(diff.file_path.clone());
                info!(file = %diff.file_path, strategy = "fuzzy_line", "Applied diff");
                continue;
            }

            // All strategies failed
            let search_lines = diff.search.lines().count();
            let search_preview: String = diff.search.lines().take(3).collect::<Vec<_>>().join(" | ");
            warn!(
                file = %diff.file_path,
                search_lines,
                search_preview = %search_preview,
                "All matching strategies failed, skipping diff"
            );
        }

        Ok(changed_files)
    }

    /// Try matching after normalizing whitespace in both content and search string.
    /// Handles cases where LLM generates slightly different indentation.
    fn try_normalized_match(&self, content: &str, search: &str, replace: &str) -> Option<String> {
        let normalize = |s: &str| -> String {
            s.lines()
                .map(|line| {
                    // Normalize: collapse multiple spaces to single, trim trailing
                    let trimmed = line.trim_end();
                    // Preserve leading whitespace structure but normalize tabs→spaces
                    trimmed.replace('\t', "    ")
                })
                .collect::<Vec<_>>()
                .join("\n")
        };

        let norm_content = normalize(content);
        let norm_search = normalize(search);

        if !norm_content.contains(&norm_search) {
            return None;
        }

        // Find the actual position in the original content by matching line-by-line
        let content_lines: Vec<&str> = content.lines().collect();
        let search_lines: Vec<&str> = search.lines().collect();

        if search_lines.is_empty() {
            return None;
        }

        // Find where the normalized search starts in the original
        let norm_content_lines: Vec<String> = content_lines.iter()
            .map(|l| l.trim_end().replace('\t', "    "))
            .collect();
        let norm_search_lines: Vec<String> = search_lines.iter()
            .map(|l| l.trim_end().replace('\t', "    "))
            .collect();

        for start_idx in 0..=content_lines.len().saturating_sub(norm_search_lines.len()) {
            let matches = norm_search_lines.iter().enumerate().all(|(i, sl)| {
                start_idx + i < norm_content_lines.len() && norm_content_lines[start_idx + i] == *sl
            });

            if matches {
                // Found it — replace the original lines
                let mut result = Vec::new();
                result.extend_from_slice(&content_lines[..start_idx]);
                for replace_line in replace.lines() {
                    result.push(replace_line);
                }
                let end_idx = start_idx + norm_search_lines.len();
                if end_idx < content_lines.len() {
                    result.extend_from_slice(&content_lines[end_idx..]);
                }
                return Some(result.join("\n") + if content.ends_with('\n') { "\n" } else { "" });
            }
        }

        None
    }

    /// Try fuzzy line-by-line matching: find a contiguous block of lines in the file
    /// where ≥80% of lines match (after stripping whitespace) the search block.
    /// Handles LLM omitting blank lines or adding comments.
    fn try_fuzzy_line_match(&self, content: &str, search: &str, replace: &str) -> Option<String> {
        let content_lines: Vec<&str> = content.lines().collect();
        let search_lines: Vec<&str> = search.lines()
            .filter(|l| !l.trim().is_empty()) // Skip blank lines in search
            .collect();

        if search_lines.len() < 3 {
            // Too few lines for fuzzy matching — too risky
            return None;
        }

        let threshold = 0.80; // 80% of non-blank search lines must match
        let required_matches = (search_lines.len() as f64 * threshold).ceil() as usize;

        // Sliding window: try each possible start position
        // Window size: search_lines.len() ± 20% to allow for added/removed lines
        let min_window = search_lines.len().saturating_sub(search_lines.len() / 5);
        let max_window = search_lines.len() + search_lines.len() / 5 + 2;

        let mut best_match: Option<(usize, usize, usize)> = None; // (start, end, match_count)

        for window_size in min_window..=max_window.min(content_lines.len()) {
            for start_idx in 0..=content_lines.len().saturating_sub(window_size) {
                let window = &content_lines[start_idx..start_idx + window_size];
                let window_stripped: Vec<&str> = window.iter()
                    .filter(|l| !l.trim().is_empty())
                    .map(|l| l.trim())
                    .collect();

                // Count how many search lines appear in this window
                let mut match_count = 0;
                let mut used = vec![false; window_stripped.len()];
                for sl in &search_lines {
                    let sl_trimmed = sl.trim();
                    for (j, wl) in window_stripped.iter().enumerate() {
                        if !used[j] && *wl == sl_trimmed {
                            used[j] = true;
                            match_count += 1;
                            break;
                        }
                    }
                }

                if match_count >= required_matches {
                    if best_match.map_or(true, |(_, _, best_count)| match_count > best_count) {
                        best_match = Some((start_idx, start_idx + window_size, match_count));
                    }
                }
            }
        }

        if let Some((start, end, match_count)) = best_match {
            debug!(
                start_line = start + 1,
                end_line = end,
                match_count,
                total_search_lines = search_lines.len(),
                "Fuzzy line match found"
            );

            let mut result = Vec::new();
            result.extend_from_slice(&content_lines[..start]);
            for replace_line in replace.lines() {
                result.push(replace_line);
            }
            if end < content_lines.len() {
                result.extend_from_slice(&content_lines[end..]);
            }
            return Some(result.join("\n") + if content.ends_with('\n') { "\n" } else { "" });
        }

        None
    }

    /// Create a git branch for this evolution step.
    pub fn create_branch(&self, step: u64) -> Result<String> {
        let branch_name = format!("evolve/step-{step}");
        let output = Command::new("git")
            .args(["checkout", "-b", &branch_name])
            .current_dir(&self.repo_root)
            .output()
            .context("git checkout -b failed")?;

        if !output.status.success() {
            let stderr = String::from_utf8_lossy(&output.stderr);
            // Branch might already exist
            if stderr.contains("already exists") {
                Command::new("git")
                    .args(["checkout", &branch_name])
                    .current_dir(&self.repo_root)
                    .output()
                    .context("git checkout existing branch failed")?;
            } else {
                bail!("git checkout -b failed: {stderr}");
            }
        }

        Ok(branch_name)
    }

    /// Commit changes on the current branch.
    pub fn commit(&self, message: &str) -> Result<()> {
        Command::new("git")
            .args(["add", "-A"])
            .current_dir(&self.repo_root)
            .output()
            .context("git add failed")?;

        let output = Command::new("git")
            .args(["commit", "-m", message])
            .current_dir(&self.repo_root)
            .output()
            .context("git commit failed")?;

        if !output.status.success() {
            let stderr = String::from_utf8_lossy(&output.stderr);
            if stderr.contains("nothing to commit") {
                info!("Nothing to commit");
                return Ok(());
            }
            bail!("git commit failed: {stderr}");
        }

        Ok(())
    }

    /// Rollback to master.
    pub fn rollback_to_master(&self) -> Result<()> {
        // Discard any uncommitted changes first
        let _ = Command::new("git")
            .args(["checkout", "--", "."])
            .current_dir(&self.repo_root)
            .output();

        Command::new("git")
            .args(["checkout", "master"])
            .current_dir(&self.repo_root)
            .output()
            .context("git checkout master failed")?;
        info!("Rolled back to master");
        Ok(())
    }

    /// Merge current branch into master.
    pub fn merge_to_master(&self, branch: &str) -> Result<()> {
        Command::new("git")
            .args(["checkout", "master"])
            .current_dir(&self.repo_root)
            .output()
            .context("git checkout master failed")?;

        let output = Command::new("git")
            .args(["merge", "--no-ff", branch, "-m", &format!("evolve: merge {branch}")])
            .current_dir(&self.repo_root)
            .output()
            .context("git merge failed")?;

        if !output.status.success() {
            let stderr = String::from_utf8_lossy(&output.stderr);
            bail!("git merge failed: {stderr}");
        }

        info!(branch, "Merged to master");
        Ok(())
    }

    /// Run Python syntax check on changed files.
    pub fn syntax_check(&self, files: &[String]) -> Result<bool> {
        for file in files {
            if !file.ends_with(".py") {
                continue;
            }
            let full_path = if file.starts_with('/') {
                file.clone()
            } else {
                format!("{}/{}", self.repo_root, file)
            };

            let output = Command::new("python3")
                .args(["-m", "py_compile", &full_path])
                .output()
                .with_context(|| format!("py_compile failed for {file}"))?;

            if !output.status.success() {
                let stderr = String::from_utf8_lossy(&output.stderr);
                warn!(file, "Syntax check failed: {stderr}");
                return Ok(false);
            }
        }
        Ok(true)
    }

    /// Run tests for specific module.
    pub fn run_tests(&self, module_filter: &str) -> Result<(bool, String)> {
        let output = Command::new("python3")
            .args([
                "-m",
                "pytest",
                "tests/",
                "-k",
                module_filter,
                "--tb=short",
                "-q",
            ])
            .current_dir(&self.repo_root)
            .output()
            .context("pytest failed to run")?;

        let stdout = String::from_utf8_lossy(&output.stdout).to_string();
        let passed = output.status.success();
        Ok((passed, stdout))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn make_patcher() -> CodePatcher {
        CodePatcher::new("/tmp/test-repo")
    }

    #[test]
    fn test_normalized_match_handles_tab_differences() {
        let patcher = make_patcher();
        let content = "def foo():\n    x = 1\n    y = 2\n    return x + y\n";
        let search = "def foo():\n\tx = 1\n\ty = 2\n\treturn x + y";
        let replace = "def foo():\n    x = 10\n    y = 20\n    return x + y";

        let result = patcher.try_normalized_match(content, search, replace);
        assert!(result.is_some());
        assert!(result.unwrap().contains("x = 10"));
    }

    #[test]
    fn test_normalized_match_trailing_whitespace() {
        let patcher = make_patcher();
        let content = "line1  \nline2\nline3\n";
        let search = "line1\nline2\nline3";
        let replace = "new1\nnew2\nnew3";

        let result = patcher.try_normalized_match(content, search, replace);
        assert!(result.is_some());
        assert!(result.unwrap().contains("new1"));
    }

    #[test]
    fn test_fuzzy_match_with_blank_lines() {
        let patcher = make_patcher();
        let content = "def foo():\n    x = 1\n\n    y = 2\n\n    z = 3\n    return x + y + z\n";
        // LLM omitted blank lines
        let search = "def foo():\n    x = 1\n    y = 2\n    z = 3\n    return x + y + z";
        let replace = "def foo():\n    x = 10\n    y = 20\n    z = 30\n    return x + y + z";

        let result = patcher.try_fuzzy_line_match(content, search, replace);
        assert!(result.is_some());
        assert!(result.unwrap().contains("x = 10"));
    }

    #[test]
    fn test_fuzzy_match_rejects_low_similarity() {
        let patcher = make_patcher();
        let content = "aaa\nbbb\nccc\nddd\neee\n";
        let search = "xxx\nyyy\nzzz\nwww";
        let replace = "replaced";

        let result = patcher.try_fuzzy_line_match(content, search, replace);
        assert!(result.is_none());
    }
}
