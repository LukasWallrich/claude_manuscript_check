# Manuscript Review Skill

You are an orchestrator for the manuscript review process. Your ONLY job is to spawn a Haiku agent that handles the full workflow. Do not perform the review yourself.

## Input

The user provides a path to a PDF file: `$ARGUMENTS`

If no argument is provided, ask the user for the path to the PDF file.

## Process

First, determine the absolute paths needed:
- `PDF_PATH`: The absolute path to the PDF (resolve `$ARGUMENTS` relative to the current working directory if needed)
- `REPO_DIR`: The current working directory (this repository's root)

Then immediately use the Agent tool with `model: "haiku"` to spawn an orchestrator agent. In the agent prompt, substitute all paths with their resolved absolute values:

---

You are a lightweight orchestrator for a manuscript review workflow. Execute the following steps in order. Do NOT read the PDF or any large data files yourself — your job is to run scripts and delegate analysis.

### Step 1: Parse the PDF with GROBID

```bash
python3 REPO_DIR/.claude/commands/parse_manuscript.py "PDF_PATH" > /tmp/manuscript_parsed.json 2>/tmp/manuscript_parse_errors.log
```

Check the exit code. If it failed, read `/tmp/manuscript_parse_errors.log` to understand why. The analysis agent will handle GROBID failures gracefully.

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
>
> **Output:** Write your JSON review to `/tmp/review_data.json` using the Write tool.

Wait for the agent to complete. If it reports an error, inform the user.

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
