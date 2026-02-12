# Check Manuscript — Claude Code Skill

A [Claude Code](https://docs.anthropic.com/en/docs/claude-code) skill that reviews academic manuscript PDFs and generates professional, structured review reports. It combines LLM-based analysis with automated checks to catch formatting errors, referencing issues, statistical inconsistencies, and compliance gaps before submission.

> [!WARNING]
> This is not validated, and should not be used to make claims about other people's manuscripts. Use with judgement to improve your own papers, or to build a more robust version of a pre-review tool.

> [!NOTE]
> The code of the skill itself is MIT licenced ((c) Lukas Wallrich, 2025). This does not apply to the example papers included. 

## What It Does

Given a PDF of an academic manuscript, the skill:

1. **Parses the PDF** via [GROBID](https://github.com/kermitt2/grobid) to extract structured metadata (title, authors, abstract, sections, bibliography, in-text citations)
2. **Runs automated checks** via the [metacheck](https://github.com/scienceverse/metacheck) R package (statcheck, retraction screening, PubPeer lookups, DOI validation, open science detection)
3. **Performs LLM-based review** across 12 check categories (title, headings, title page, abstract, structure, figures/tables, referencing, language, acronyms, funding/compliance, content, statistics)
4. **Generates an HTML report** with severity-coded issue cards, language quality grades, and a summary table
5. **Converts to PDF** via Chrome headless

### Check Categories

| Category | What It Checks |
|---|---|
| Title | Clarity, length, accuracy, abbreviations |
| Main Headings | Capitalization consistency, hierarchy, numbering |
| Title Page | Author info, affiliations, corresponding author, keywords, ORCID |
| Abstract | Structure, length (150-300 words), no citations/abbreviations |
| Structure | Standard sections present and in order |
| Figures & Tables | All cited in text, sequential order, caption quality |
| Referencing | Cross-reference integrity, formatting, retractions, PubPeer |
| Language | Grammar, spelling, punctuation, consistency |
| Acronyms | Defined on first use, consistent usage |
| Funding & Compliance | Funding, COI, ethics/IRB, author contributions, preregistration |
| Light Content Checks | Background adequacy, limitations, sample description, effect sizes |
| Statistical Reporting | Statcheck verification, p-value consistency, marginal significance |

## Getting Started

### Quick start (use directly from the cloned repo)

```bash
git clone https://github.com/LukasWallrich/claude_manuscript_check.git
cd claude_manuscript_check
claude "/check-manuscript path/to/your/manuscript.pdf"
```

### Install into an existing project

If you want to add this skill to a project you're already working on with Claude Code, copy the three skill files into your project's `.claude/commands/` directory:

```bash
# Clone the repo somewhere
git clone https://github.com/LukasWallrich/claude_manuscript_check.git /tmp/claude_manuscript_check

# Copy the skill files into your project
mkdir -p .claude/commands
cp /tmp/claude_manuscript_check/.claude/commands/check-manuscript.md .claude/commands/
cp /tmp/claude_manuscript_check/.claude/commands/parse_manuscript.py .claude/commands/
cp /tmp/claude_manuscript_check/.claude/commands/run_metacheck.R .claude/commands/
```

Then from your project directory:

```bash
claude "/check-manuscript path/to/manuscript.pdf"
```

## Requirements

- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) CLI
- **Python 3** (standard library only — no pip dependencies for the parser)
- **Internet access** (the GROBID parser calls a free public API at `kermitt2-grobid.hf.space`)
- **Google Chrome** (for HTML-to-PDF conversion; falls back gracefully if unavailable)

### Optional (recommended)

- **R** with the [metacheck](https://github.com/scienceverse/metacheck) package — enables automated statistical checks (statcheck), retraction screening, PubPeer lookups, DOI validation, and open science detection. Without it, the report will note that these checks were skipped.

To install metacheck:

```r
if (!require("devtools")) install.packages("devtools")
devtools::install_github("scienceverse/metacheck")
```

## Usage

From within the project directory (or any directory containing the `.claude/` folder), run:

```bash
claude "/check-manuscript path/to/manuscript.pdf"
```

Or simply:

```bash
claude "/check-manuscript"
```

and provide the path when prompted.

### Example

```bash
claude "/check-manuscript example/example_article.pdf"
```

This produces two files alongside the input PDF:

- `example/example_article_review.html` — self-contained HTML report
- `example/example_article_review.pdf` — PDF version (if Chrome is available)

## Output

The report includes:

- **Overall Summary** with critical/major/minor issue counts
- **Language Quality** grades (A+ through F) across six dimensions
- **Section Review Summary** table with pass/fail status per category
- **Detailed Recommendations** with issue cards containing:
  - Location and severity badge
  - Original text and suggested fix (with changes highlighted)
  - Explanation of why it matters
- **Metacheck results** (when available) badged with `[metacheck]` markers, including:
  - Statcheck table showing each verified test statistic
  - Retraction and PubPeer screening results
  - Open science practice detection (data sharing, code, preregistration)

### Severity Levels

- **Critical** — Errors that could cause rejection or serious misunderstanding
- **Major** — Issues that should be fixed before submission
- **Minor** — Polish items that improve quality but aren't essential

## Project Structure

```
.claude/
  commands/
    check-manuscript.md    # Skill prompt (the review instructions)
    parse_manuscript.py    # GROBID PDF parser (Python, no dependencies)
    run_metacheck.R        # Metacheck runner (R, requires metacheck package)
example/
    example_article.pdf    # Sample manuscript for testing
    example_article_review.html  # Generated HTML report
    example_article_review.pdf   # Generated PDF report
```

## Limitations

- **GROBID parsing** uses a free public API that may occasionally be slow or unavailable. The parser has fallback logic (dedicated references endpoint, then local PDF text extraction) but results may vary.
- **Metacheck** is alpha software; false positives and negatives occur at unknown rates. All automated findings should be verified manually.
- **LLM-based checks** may miss issues or flag false positives, particularly for non-standard manuscript formats. The report notes that suggestions should be verified by the authors.
- **PDF text extraction** can introduce artifacts (e.g., ligature issues, column merging). The report warns about this where relevant.
- Best suited for **empirical social science manuscripts** in APA-like format. Other fields and formats will work but may produce less relevant compliance checks.
