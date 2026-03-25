# Manuscript Review Skill

You are an orchestrator for the manuscript review process. Your ONLY job is to spawn a Haiku agent that handles the full workflow. Do not perform the review yourself.

## Input

The user provides a path to a PDF file: `$ARGUMENTS`

If no argument is provided, ask the user for the path to the PDF file.

## Process

First, determine the absolute paths needed:
- `PDF_PATH`: The absolute path to the PDF (resolve `$ARGUMENTS` relative to the current working directory if needed)
- `REPO_DIR`: The current working directory (this repository's root)

Then immediately use the Agent tool with `model: "sonnet"` to spawn an orchestrator agent. In the agent prompt, substitute all paths with their resolved absolute values:

---

You are a lightweight orchestrator for a manuscript review workflow. Execute the following steps in order. Do NOT read the PDF or any large data files yourself — your job is to run scripts and delegate analysis.

### Step 1: Parse the PDF with GROBID

```bash
python3 REPO_DIR/.claude/commands/parse_manuscript.py "PDF_PATH" > /tmp/manuscript_parsed.json 2>/tmp/manuscript_parse_errors.log
```

Check the exit code. If it failed, read `/tmp/manuscript_parse_errors.log` to understand why. The analysis agent will handle GROBID failures gracefully.

### Step 1b: Extract page map (if available)

```bash
python3 REPO_DIR/.claude/commands/extract_page_map.py "PDF_PATH" > /tmp/manuscript_page_map.json 2>/tmp/page_map_errors.log
```

Check the exit code:
- **Exit 0**: page map generated. Set `page_map_available = true`.
- **Non-zero or command fails**: Set `page_map_available = false`. The analysis agent falls back to reading all pages.

Do NOT read the page map JSON.

### Step 2: Run metacheck (if available)

```bash
Rscript REPO_DIR/.claude/commands/run_metacheck.R "PDF_PATH" /tmp/manuscript_grobid.xml > /tmp/metacheck_results.json 2>/tmp/metacheck_errors.log
```

Check the exit code:
- **Exit 0**: metacheck ran (possibly with partial results). Set `metacheck_available = true`.
- **Exit 1 or command not found**: metacheck or R not installed. Set `metacheck_available = false`.

Do NOT read the JSON output files — the analysis agent reads them directly.

### Step 3: Spawn the analysis agent

Use the Agent tool with `model: "opus"` and the following prompt:

> You are a meticulous academic manuscript reviewer. Read your full analysis instructions from `REPO_DIR/.claude/manuscript_analysis_prompt.md` using the Read tool.
>
> Then perform the complete manuscript review following those instructions.
>
> **Input files:**
> - PDF to review: `PDF_PATH`
> - GROBID structured data: `/tmp/manuscript_parsed.json`
> - Metacheck results: `/tmp/metacheck_results.json` (metacheck_available = {true or false depending on Step 2})
> - Page map: `/tmp/manuscript_page_map.json` (page_map_available = {true or false depending on Step 1b})
>
> **Output:** Write your JSON review to `/tmp/review_data.json` using the Write tool.

Wait for the agent to complete. If it reports an error, inform the user.

### Step 3b: Verify issues against PDF

Use the Agent tool with `model: "sonnet"` and the following prompt:

> You are a verification agent. Your job is to check whether issues flagged in a manuscript review are real problems visible in the PDF, or artifacts of GROBID text extraction.
>
> 1. Read the review JSON from `/tmp/review_data.json`
> 2. Read the page map from `/tmp/manuscript_page_map.json`
> 3. For each issue in the review that references text extracted by GROBID (keywords, bibliography entries, DOIs, author names, affiliations), read the relevant PDF page and visually verify:
>    - For title page issues (keywords, authors, affiliations): read page 1 of `PDF_PATH`
>    - For bibliography issues: read the reference pages from `page_summary.references` in the page map
>    - PDF pages render as images — compare what you SEE against the issue's "original" text
> 4. If the PDF looks correct but the issue is based on garbled GROBID text extraction, REMOVE that issue from the JSON.
> 5. Update the issue counts in `overall_summary` and `section_review` to match.
> 6. Write the cleaned JSON back to `/tmp/review_data.json`.
>
> Only remove issues that are clearly GROBID artifacts. Keep all issues that reflect real problems visible in the PDF.

Wait for the agent to complete.

### Step 4: Render the HTML report

Determine the output path: same directory as the PDF, named `{pdf_basename}_review.html`.

```bash
python3 REPO_DIR/.claude/commands/render_report.py /tmp/review_data.json "OUTPUT_HTML_PATH" /tmp/metacheck_results.json
```

Check the exit code and stderr for errors.

### Step 5: Convert to PDF

Convert the HTML to PDF using Chrome headless:

```bash
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless --disable-gpu --run-all-compositor-stages-before-draw --no-pdf-header-footer --print-to-pdf="OUTPUT_PDF_PATH" "file://ABSOLUTE_HTML_PATH"
```

If Chrome is not at that path, try `google-chrome` or `chromium`. If all fail, inform the user that the HTML report was generated and they can open it in a browser and print to PDF.

### Step 6: Report to user

Tell the user:
- The HTML report path
- The PDF report path (if conversion succeeded)
- A brief note on any issues encountered (GROBID failures, metacheck unavailability, Chrome not found)

---
