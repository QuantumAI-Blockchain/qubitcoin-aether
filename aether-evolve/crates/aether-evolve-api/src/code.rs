use aether_evolve_core::CodeDiff;
use anyhow::{bail, Context, Result};
use std::path::Path;
use std::process::Command;
use tracing::{info, warn};

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

            if !content.contains(&diff.search) {
                warn!(file = %diff.file_path, "SEARCH string not found, skipping");
                continue;
            }

            let new_content = content.replacen(&diff.search, &diff.replace, 1);
            std::fs::write(path, &new_content)
                .with_context(|| format!("Failed to write {full_path}"))?;

            changed_files.push(diff.file_path.clone());
            info!(file = %diff.file_path, "Applied diff");
        }

        Ok(changed_files)
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
