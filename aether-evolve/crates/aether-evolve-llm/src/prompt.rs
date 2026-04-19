use anyhow::{Context, Result};
use std::path::Path;
use tera::Tera;

pub struct PromptManager {
    tera: Tera,
}

impl PromptManager {
    /// Load templates from a directory (*.tera files).
    pub fn from_dir(dir: &Path) -> Result<Self> {
        let glob = format!("{}/**/*.tera", dir.display());
        let tera = Tera::new(&glob).context("Failed to load prompt templates")?;
        Ok(Self { tera })
    }

    /// Create with built-in default templates.
    pub fn with_defaults() -> Result<Self> {
        let mut tera = Tera::default();

        tera.add_raw_template("diagnose", DIAGNOSE_TEMPLATE)?;
        tera.add_raw_template("research_code", RESEARCH_CODE_TEMPLATE)?;
        tera.add_raw_template("research_seed", RESEARCH_SEED_TEMPLATE)?;
        tera.add_raw_template("analyze", ANALYZE_TEMPLATE)?;

        Ok(Self { tera })
    }

    /// Render a template with the given context.
    pub fn render(&self, template: &str, context: &tera::Context) -> Result<String> {
        self.tera
            .render(template, context)
            .with_context(|| format!("Failed to render template: {template}"))
    }
}

const DIAGNOSE_TEMPLATE: &str = r#"You are an AI cognitive architecture researcher analyzing the Aether Tree system.

## Current Metrics
- Block height: {{ block_height }}
- Total nodes: {{ total_nodes }}
- Total edges: {{ total_edges }}
- HMS-Phi: {{ hms_phi }}
  - phi_micro: {{ phi_micro }}
  - phi_meso: {{ phi_meso }}
  - phi_macro: {{ phi_macro }}
- Gates passed: {{ gates_passed }}/{{ gates_total }}
- Debates: {{ debate_count }}
- Contradictions resolved: {{ contradiction_count }}
- Prediction accuracy: {{ prediction_accuracy }}%
- Novel concepts: {{ novel_concepts }}
- MIP score: {{ mip_score }}

## Subsystem Status
{% for sub in subsystems %}
- {{ sub.name }}: {{ sub.runs }} runs, active={{ sub.active }}
{% endfor %}

## Task
Analyze the above metrics and identify the TOP 3 weaknesses, ranked by priority.
For each weakness, provide:
1. Priority level (P0=critical, P1=gate blocker, P2=dead subsystem, P3=quality gap)
2. Root cause analysis
3. Recommended intervention type (CODE_CHANGE, KNOWLEDGE_SEED, API_CALL)
4. Target files or API endpoints
5. Expected improvement if fixed

Respond in this exact XML format:
<diagnosis>
  <item priority="P0" category="...">
    <description>...</description>
    <root_cause>...</root_cause>
    <intervention>CODE_CHANGE</intervention>
    <target_files>file1.py, file2.py</target_files>
    <expected_improvement>...</expected_improvement>
  </item>
</diagnosis>"#;

const RESEARCH_CODE_TEMPLATE: &str = r#"You are modifying the Aether Tree cognitive system to fix a critical weakness.

## Weakness
{{ diagnosis_description }}

## Root Cause
{{ root_cause }}

## File: {{ file_path }}
Lines are numbered (e.g. "  42| code"). DO NOT include line numbers in your patches.

```python
{{ file_content }}
```

## CRITICAL RULES
1. The SEARCH string must match the ACTUAL code shown above EXACTLY
2. DO NOT include line number prefixes (like "  42| ") in SEARCH or REPLACE
3. Copy-paste the exact code from above — do not retype or paraphrase
4. Include enough context lines (3-5 lines before and after the change) to ensure unique matching
5. Keep changes minimal — only change what is needed to fix the weakness
6. Each patch should be a self-contained fix

## Output Format
<patch>
<search>
exact lines from the file (without line numbers)
</search>
<replace>
the fixed version of those same lines
</replace>
</patch>

You may include multiple <patch> blocks if needed."#;

const RESEARCH_SEED_TEMPLATE: &str = r#"You are generating high-quality knowledge for the Aether Tree cognitive system.

## Current State
- Total nodes: {{ total_nodes }}
- Domains: {{ domains }}
- Weakness: {{ diagnosis_description }}

## Task
Generate {{ count }} knowledge nodes that address the identified weakness.
Each node should be substantive, factual, and cross-referenced.

Respond as a JSON array:
```json
[
  {
    "content": "Detailed factual knowledge...",
    "domain": "domain_name",
    "node_type": "fact|theory|observation|causal",
    "confidence": 0.85,
    "connections": ["related topic 1", "related topic 2"]
  }
]
```"#;

const ANALYZE_TEMPLATE: &str = r#"You are analyzing the results of an evolution experiment on the Aether Tree.

## Experiment
- Type: {{ intervention_type }}
- Hypothesis: {{ hypothesis }}
- Step: {{ step }}

## Pre-Metrics
- HMS-Phi: {{ pre_phi }}
- Nodes: {{ pre_nodes }}
- Gates: {{ pre_gates }}/10
- Debates: {{ pre_debates }}

## Post-Metrics
- HMS-Phi: {{ post_phi }}
- Nodes: {{ post_nodes }}
- Gates: {{ post_gates }}/10
- Debates: {{ post_debates }}

## Changes Applied
{{ changes_summary }}

## Task
Analyze whether this intervention was successful. Provide:
1. What improved and why
2. What didn't improve and why
3. Key lesson learned (one sentence)
4. Recommended next step
5. Score (0-100)

Respond in this format:
<analysis>
  <improved>...</improved>
  <not_improved>...</not_improved>
  <lesson>...</lesson>
  <next_step>...</next_step>
  <score>...</score>
</analysis>"#;
