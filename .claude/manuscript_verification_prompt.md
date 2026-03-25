# Manuscript Review Verification

You are a verification agent. Your job is to check whether issues flagged in a manuscript review are real problems visible in the PDF, or artifacts of GROBID text extraction.

## Process

1. Run: `echo "$(date +%H:%M:%S) Step 3b - Sonnet verification: STARTED" >> /tmp/manuscript_review.log`

2. Read the review JSON from `/tmp/review_data.json`

3. Read the page map from `/tmp/manuscript_page_map.json`

4. For each issue in the review that references text extracted by GROBID (keywords, bibliography entries, DOIs, author names, affiliations), read the relevant PDF page and visually verify:
   - For title page issues (keywords, authors, affiliations): read page 1 of the PDF
   - For bibliography issues: read the reference pages from `page_summary.references` in the page map
   - PDF pages render as images — compare what you SEE against the issue's "original" text

5. If the PDF looks correct but the issue is based on garbled GROBID text extraction, REMOVE that issue from the JSON.

6. Update the issue counts in `overall_summary` and `section_review` to match.

7. Write the cleaned JSON back to `/tmp/review_data.json`.

Only remove issues that are clearly GROBID artifacts. Keep all issues that reflect real problems visible in the PDF.

8. Run: `echo "$(date +%H:%M:%S) Step 3b - Sonnet verification: COMPLETED" >> /tmp/manuscript_review.log`
