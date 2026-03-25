# Render: Detailed Recommendations Body

You write the **detailed recommendations** section of a manuscript review HTML report. The header, summary, language quality, and section review table have already been generated. You write only the body content that follows.

First, run: `echo "$(date +%H:%M:%S) Step 3c - Rendering: STARTED" >> /tmp/manuscript_review.log`

## Input

Read **`/tmp/render_context.json`**. It contains:

- `check_categories` — array of 12 categories, each with `number`, `name`, `summary`, `issues[]`, `subsections[]`, `content_observations[]`, `metacheck_info`
- `category_badges` — pre-generated HTML badge strings keyed by category number (e.g., `"2"` → `"3 issues: <span ...>3 Minor</span>"`)
- `snippets` — pre-generated HTML tables (paste verbatim):
  - `doi_table` — DOI suggestions table HTML (for category 7)
  - `statcheck_table` — statcheck results table HTML (for category 12)
  - `replication_results` — replication results card HTML (for category 7)

Note: Narrative metacheck content (retraction summaries, open science, p-values, marginal notes) is in `metacheck_info` on each category. **Write these as proper narratives** — do not dump raw data.

## Output

Write a single HTML fragment to **`/tmp/review_body.html`** using the Write tool. This will be inserted into the report template. Do NOT include `<!DOCTYPE>`, `<html>`, `<head>`, `<style>`, or `<body>` tags.

## HTML Structure

Start with:
```html
<h2 class="section-title">DETAILED RECOMMENDATIONS</h2>
<hr class="section-divider">
```

Then for each category:

```html
<h3>{number}. {name}</h3>
<p style="margin-bottom: 16px;">{paste category_badges[number] verbatim}</p>
<p class="summary-text">{summary — rewrite if needed for coherence and cross-references}</p>
```

### Issue cards

For issues with original/suggestion:
```html
<div class="issue-card no-break">
  <div class="issue-location">Location: {location} <span class="badge badge-{severity}">{Severity}</span></div>
  <div class="original-block"><strong>Original:</strong> {text}</div>
  <div class="suggestion-block"><strong>Suggestion:</strong> {text with <strong>bold</strong> for changes}</div>
  <p class="explanation"><strong>Explanation:</strong> {text}</p>
</div>
```

For action-only issues (no original/suggestion):
```html
<div class="issue-card no-break">
  <div class="issue-location">Location: {location} <span class="badge badge-{severity}">{Severity}</span></div>
  <div class="suggestion-block"><strong>Action:</strong> {text}</div>
  <p class="explanation"><strong>Explanation:</strong> {text}</p>
</div>
```

If the issue has a `title`, add `<strong>{title}</strong><br>` before the issue-location div.

### Content observations

Before the first observation in a category, add `<h4>Observations</h4>`. Then:
```html
<div class="content-note">
  <strong>{title}:</strong> {text}
</div>
```

### Metacheck subsections

Use `<h4>` with `<span class="badge-auto">[metacheck]</span>`:
```html
<h4>{title} <span class="badge-auto">[metacheck]</span></h4>
<p class="summary-text">{narrative text}</p>
```

### Metacheck subsections by category

**Category 7** (Referencing):
- Write a narrative for "Retraction & Integrity Check" using `metacheck_info.retraction_summary`. Mention DOI count, retraction status, PubPeer status.
- Paste `snippets.doi_table` verbatim under `<h4>DOI Suggestions <span class="badge-auto">[metacheck]</span></h4>` if non-empty.
- Paste `snippets.replication_results` verbatim if non-empty.

**Category 10** (Funding & Compliance):
- Write a narrative for "Open Science Practices" using `metacheck_info.open_science` items. Summarize what was detected (data sharing, code sharing, preregistration, COI, funding) in a coherent paragraph — do NOT dump raw data.

**Category 12** (Statistical Reporting):
- Paste `snippets.statcheck_table` verbatim under a statcheck heading if non-empty. If empty, write a brief note explaining why (e.g., no APA-formatted statistics detected).
- Write a "P-values & Marginal Significance" narrative using `metacheck_info.p_value_summary` and `metacheck_info.marginal_notes`. Integrate with the category summary — avoid repeating what's already there. Reference other categories if relevant (e.g., "addressed in Category 11").

If a snippet is empty or a `metacheck_info` field is absent, omit that subsection.

## Critical Rules

1. **Use category_badges verbatim** — do not recalculate counts.
2. **Paste snippets verbatim** — do not rewrite DOI tables or statcheck tables.
3. **Cross-references**: When a finding relates to another category, reference it (e.g., "addressed in Category 11 above").
4. **No duplication**: Don't repeat information already in the summary when writing issue cards, or vice versa. Don't repeat metacheck data already mentioned in the summary.
5. **Coherence**: Rewrite category summaries if the JSON text doesn't flow well in context. Ensure each section reads naturally.
6. **HTML-escape** user-facing text. Convert `**bold**` markers to `<strong>` tags.
7. **Subsection handling**: If a subsection in the JSON says all flags were GROBID artifacts or no genuine issues were found, do NOT render it — the category summary already covers this.

When finished, run: `echo "$(date +%H:%M:%S) Step 3c - Rendering: COMPLETED" >> /tmp/manuscript_review.log`
