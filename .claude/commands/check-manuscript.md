# Manuscript Review Skill

You are an orchestrator for the manuscript review process. Your ONLY job is to spawn a Sonnet agent that handles the full workflow. Do not perform the review yourself.

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

### Pipeline log

Before EACH step, append a timestamped line to `/tmp/manuscript_review.log`. Clear the log at the start. At the end, read the log and include it in your report.

```bash
echo "" > /tmp/manuscript_review.log
```

Log format: `echo "$(date +%H:%M:%S) STEP_NAME: STATUS" >> /tmp/manuscript_review.log`

### Step 1: Parse the PDF with GROBID

```bash
python3 REPO_DIR/.claude/commands/parse_manuscript.py "PDF_PATH" > /tmp/manuscript_parsed.json 2>/tmp/manuscript_parse_errors.log
```

Check the exit code. If it failed, read `/tmp/manuscript_parse_errors.log` to understand why.

### Step 1b: Extract page map (if available)

```bash
PATH="/opt/homebrew/bin:$PATH" python3 REPO_DIR/.claude/commands/extract_page_map.py "PDF_PATH" > /tmp/manuscript_page_map.json 2>/tmp/page_map_errors.log
```

Check the exit code. Exit 0 = page_map_available = true. Otherwise false.

### Step 2: Run metacheck (if available)

```bash
Rscript REPO_DIR/.claude/commands/run_metacheck.R "PDF_PATH" /tmp/manuscript_grobid.xml > /tmp/metacheck_results.json 2>/tmp/metacheck_errors.log
```

Check the exit code. Exit 0 = metacheck_available = true. Otherwise false.

### Step 3: Spawn the analysis agent

Use the Agent tool with `model: "opus"` and this prompt:

> Read your instructions from `REPO_DIR/.claude/manuscript_analysis_prompt.md` and follow them.
>
> PDF to review: `PDF_PATH`
> GROBID data: `/tmp/manuscript_parsed.json`
> Metacheck results: `/tmp/metacheck_results.json` (metacheck_available = {true/false})
> Page map: `/tmp/manuscript_page_map.json` (page_map_available = {true/false})
>
> Write output to `/tmp/review_data.json`.

Wait for the agent to complete.

### Step 3b: Verify issues against PDF

Use the Agent tool with `model: "sonnet"` and this prompt:

> Read your instructions from `REPO_DIR/.claude/manuscript_verification_prompt.md` and follow them.
>
> PDF to verify against: `PDF_PATH`

Wait for the agent to complete.

### Step 4: Render the HTML report

Determine the output path: same directory as the PDF, named `{pdf_basename}_review.html`.

```bash
python3 REPO_DIR/.claude/commands/render_report.py /tmp/review_data.json "OUTPUT_HTML_PATH" /tmp/metacheck_results.json
```

### Step 5: Convert to PDF

```bash
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless --disable-gpu --run-all-compositor-stages-before-draw --no-pdf-header-footer --print-to-pdf="OUTPUT_PDF_PATH" "file://ABSOLUTE_HTML_PATH"
```

If Chrome is not at that path, try `google-chrome` or `chromium`. If all fail, inform the user the HTML report was generated.

### Step 6: Report to user

Read `/tmp/manuscript_review.log` and tell the user:
- The pipeline log (so they can see what ran)
- The HTML report path
- The PDF report path (if conversion succeeded)
- A brief note on any issues encountered

---
