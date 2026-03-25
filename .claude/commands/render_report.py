#!/usr/bin/env python3
"""Render a manuscript review JSON into a self-contained HTML report.

Usage: python3 render_report.py <input.json> <output.html>
"""

import html
import json
import re
import sys

# ---------------------------------------------------------------------------
# CSS (matches the existing report template)
# ---------------------------------------------------------------------------
CSS = """\
@page { size: A4; margin: 2cm 2cm 2.5cm 2cm; }
@page { @bottom-center { content: counter(page); font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; font-size: 11px; color: #a0aec0; } }
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
  color: #2d3748; line-height: 1.6; max-width: 800px;
  margin: 0 auto; padding: 40px 20px; background: #fff;
}
h1 { text-align: center; font-size: 24px; font-weight: 800; color: #1a202c; letter-spacing: 2px; margin-bottom: 8px; }
.subtitle { text-align: center; font-size: 18px; color: #4a5568; margin-bottom: 6px; }
.meta { text-align: center; font-size: 13px; color: #a0aec0; margin-bottom: 40px; }
.about-box { border-left: 4px solid #63b3ed; background: #f7fafc; padding: 20px 24px; margin-bottom: 40px; border-radius: 0 8px 8px 0; }
.about-box h2 { font-size: 16px; font-weight: 700; color: #2d3748; margin-bottom: 8px; letter-spacing: 1px; }
.about-box p { font-size: 14px; color: #4a5568; }
.section-title { font-size: 20px; font-weight: 800; color: #2d3748; letter-spacing: 1px; margin-top: 50px; margin-bottom: 4px; }
.section-divider { border: none; border-top: 2px solid #e2e8f0; margin-bottom: 16px; }
.summary-text { font-size: 15px; color: #4a5568; margin-bottom: 24px; }
.stats-row { display: flex; justify-content: space-around; margin: 24px 0 40px 0; text-align: center; }
.stat-box { flex: 1; border-right: 1px solid #e2e8f0; }
.stat-box:last-child { border-right: none; }
.stat-label { font-size: 11px; font-weight: 700; color: #718096; letter-spacing: 1px; margin-bottom: 4px; }
.stat-number { font-size: 28px; font-weight: 700; }
.stat-number.critical { color: #e53e3e; }
.stat-number.major { color: #dd6b20; }
.stat-number.minor { color: #38a169; }
.badge { display: inline-block; padding: 2px 12px; border-radius: 12px; font-size: 12px; font-weight: 600; float: right; }
.badge-critical { background: #fed7d7; color: #c53030; }
.badge-major { background: #feebc8; color: #c05621; }
.badge-minor { background: #fefcbf; color: #975a16; }
.count-badge { display: inline-block; padding: 2px 12px; border-radius: 12px; font-size: 12px; font-weight: 600; margin-right: 6px; }
.count-critical { background: #fed7d7; color: #c53030; }
.count-major { background: #feebc8; color: #c05621; }
.count-minor { background: #fefcbf; color: #975a16; }
.issue-card { border: 1px solid #e2e8f0; border-radius: 8px; padding: 20px; margin-bottom: 16px; background: #fff; page-break-inside: avoid; }
.issue-location { font-size: 13px; color: #718096; margin-bottom: 12px; }
.original-block { background: #f7fafc; border-left: 3px solid #cbd5e0; padding: 10px 14px; font-family: 'SF Mono', 'Fira Code', 'Fira Mono', Menlo, monospace; font-size: 13px; margin-bottom: 8px; white-space: pre-wrap; word-wrap: break-word; line-height: 1.5; }
.suggestion-block { background: #f0fff4; border-left: 3px solid #68d391; padding: 10px 14px; font-family: 'SF Mono', 'Fira Code', 'Fira Mono', Menlo, monospace; font-size: 13px; margin-bottom: 12px; white-space: pre-wrap; word-wrap: break-word; line-height: 1.5; }
.suggestion-block strong { font-weight: 700; }
.explanation { font-size: 14px; color: #4a5568; border-top: 1px dashed #e2e8f0; padding-top: 12px; }
.explanation strong { color: #2d3748; font-weight: 700; }
.grade-card { border-left: 4px solid #68d391; padding: 12px 20px; margin-bottom: 12px; background: #fff; display: flex; justify-content: space-between; align-items: center; border-radius: 0 8px 8px 0; }
.grade-card.grade-b { border-left-color: #f6e05e; }
.grade-card.grade-c { border-left-color: #ed8936; }
.grade-card.grade-d { border-left-color: #fc8181; }
.grade-card.grade-f { border-left-color: #e53e3e; }
.grade-title { font-weight: 700; font-size: 15px; }
.grade-desc { font-size: 13px; color: #718096; margin-top: 2px; }
.grade-badge { display: inline-flex; align-items: center; justify-content: center; width: 36px; height: 36px; border-radius: 50%; color: #fff; font-weight: 700; font-size: 14px; flex-shrink: 0; }
.grade-a { background: #48bb78; }
.grade-a-plus { background: #38a169; }
.grade-a-minus { background: #68d391; }
.grade-b-badge { background: #ecc94b; color: #744210; }
.grade-b-plus-badge { background: #d69e2e; color: #fff; }
.grade-c-badge { background: #ed8936; color: #fff; }
.grade-d-badge { background: #fc8181; color: #fff; }
.grade-f-badge { background: #e53e3e; color: #fff; }
.overall-grade { display: inline-flex; align-items: center; justify-content: center; width: 40px; height: 40px; border-radius: 50%; color: #fff; font-weight: 700; font-size: 16px; margin-left: 10px; vertical-align: middle; }
.review-table { width: 100%; border-collapse: collapse; margin: 16px 0 40px 0; }
.review-table th { font-size: 11px; font-weight: 700; color: #718096; letter-spacing: 1px; text-align: left; padding: 10px 12px; border-bottom: 2px solid #e2e8f0; }
.review-table th:nth-child(2), .review-table th:nth-child(3) { text-align: center; }
.review-table td { padding: 12px; border-bottom: 1px solid #edf2f7; vertical-align: top; }
.review-table td:nth-child(2), .review-table td:nth-child(3) { text-align: center; }
.table-section-name { font-weight: 600; font-size: 14px; color: #2d3748; }
.table-section-desc { font-size: 12px; color: #a0aec0; }
.status-pass { display: inline-flex; align-items: center; justify-content: center; width: 28px; height: 28px; border-radius: 50%; background: #c6f6d5; color: #276749; font-size: 16px; }
.status-fail { display: inline-flex; align-items: center; justify-content: center; width: 28px; height: 28px; border-radius: 50%; background: #fed7d7; color: #c53030; font-size: 14px; font-weight: 700; }
.status-info { display: inline-flex; align-items: center; justify-content: center; width: 28px; height: 28px; border-radius: 50%; background: #bee3f8; color: #2b6cb0; font-size: 16px; }
.issues-count { font-weight: 600; font-size: 15px; color: #4a5568; }
.strengths-list, .improvements-list { margin: 8px 0 16px 20px; font-size: 14px; }
.strengths-list li, .improvements-list li { margin-bottom: 4px; color: #4a5568; }
strong.label { color: #2d3748; }
.content-note { background: #ebf8ff; border-left: 4px solid #4299e1; padding: 16px 20px; margin-bottom: 16px; border-radius: 0 8px 8px 0; font-size: 14px; color: #2b6cb0; page-break-inside: avoid; }
.content-note strong { color: #2c5282; }
.badge-auto { display: inline-block; padding: 1px 8px; border-radius: 10px; font-size: 11px; font-weight: 600; background: #e9d8fd; color: #553c9a; }
.retraction-warning { border: 2px solid #e53e3e; background: #fff5f5; border-radius: 8px; padding: 16px 20px; margin-bottom: 16px; }
.pubpeer-flag { border: 2px solid #dd6b20; background: #fffaf0; border-radius: 8px; padding: 16px 20px; margin-bottom: 16px; }
.disagreement-note { background: #fefcbf; border-left: 4px solid #d69e2e; padding: 12px 16px; margin-bottom: 12px; font-size: 13px; border-radius: 0 8px 8px 0; }
.page-break { page-break-before: always; }
.no-break { page-break-inside: avoid; }
"""

ABOUT_WITH_METACHECK = (
    'This report was generated by an AI-powered manuscript review skill for Claude Code. '
    'It combines LLM-based analysis with automated checks powered by the '
    '<a href="https://github.com/scienceverse/metacheck">metacheck R package</a> '
    '(DeBruine, 2024). Automated checks are marked with <span class="badge-auto">[metacheck]</span> badges. '
    'All suggestions should be verified by the authors. <strong>Note:</strong> Some apparent errors '
    'may stem from PDF text extraction and should be verified against the source document.'
)

ABOUT_WITHOUT_METACHECK = (
    'This report was generated by an AI-powered manuscript review skill for Claude Code. '
    'It checks for common formatting, referencing, and structural issues in academic manuscripts '
    'to help authors prepare their best work for submission. It also includes light content observations. '
    'Automated statistical and reference integrity checks were not performed in this review &mdash; '
    'install the <a href="https://github.com/scienceverse/metacheck">metacheck R package</a> '
    'for retraction screening, PubPeer lookups, and statistical error detection. '
    'All suggestions should be verified by the authors. <strong>Note:</strong> Some apparent errors '
    'may stem from PDF text extraction and should be verified against the source document.'
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def esc(text):
    """HTML-escape text, returning empty string for None."""
    if text is None:
        return ""
    return html.escape(str(text))


def md_bold(text):
    """Convert **bold** markers to <strong> tags. Text must already be escaped."""
    if text is None:
        return ""
    escaped = esc(text)
    return re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', escaped)


def grade_badge_css(grade):
    """Return CSS class for grade badge circle."""
    g = grade.strip().replace('\u2212', '-').replace('\u2013', '-').upper()
    mapping = {
        'A+': 'grade-a-plus', 'A': 'grade-a', 'A-': 'grade-a-minus',
        'B+': 'grade-b-plus-badge', 'B': 'grade-b-badge', 'B-': 'grade-b-badge',
        'C+': 'grade-c-badge', 'C': 'grade-c-badge', 'C-': 'grade-c-badge',
        'D+': 'grade-d-badge', 'D': 'grade-d-badge', 'D-': 'grade-d-badge',
        'F': 'grade-f-badge',
    }
    return mapping.get(g, 'grade-a')


def grade_card_css(grade):
    """Return extra CSS class for grade card border colour."""
    g = grade.strip().replace('\u2212', '-').replace('\u2013', '-').upper()
    if g.startswith('B'):
        return ' grade-b'
    if g.startswith('C'):
        return ' grade-c'
    if g.startswith('D'):
        return ' grade-d'
    if g == 'F':
        return ' grade-f'
    return ''


def grade_display(grade):
    """Format grade for display, using &minus; for minus signs."""
    g = grade.strip()
    return esc(g).replace('-', '&minus;')


def severity_badge(severity):
    """Return a severity badge span."""
    s = severity.lower()
    return f'<span class="badge badge-{s}">{esc(severity.capitalize())}</span>'


def count_badges(issues):
    """Return count badge HTML from a list of issues."""
    counts = {'critical': 0, 'major': 0, 'minor': 0}
    for issue in issues:
        s = issue.get('severity', '').lower()
        if s in counts:
            counts[s] += 1
    parts = []
    for sev in ('critical', 'major', 'minor'):
        if counts[sev] > 0:
            parts.append(
                f'<span class="count-badge count-{sev}">'
                f'{counts[sev]} {sev.capitalize()}</span>'
            )
    total = sum(counts.values())
    if total == 0:
        return '<span class="count-badge" style="background:#c6f6d5; color:#276749;">0 issues</span>'
    return f'{total} issue{"s" if total != 1 else ""}: {" ".join(parts)}'


def status_icon(status):
    """Return status icon HTML for the section review table."""
    s = status.lower()
    if s == 'pass':
        return '<span class="status-pass">&#10003;</span>'
    if s == 'fail':
        return '<span class="status-fail">&times;</span>'
    if s == 'info':
        return '<span class="status-info">&#8505;</span>'
    if s == 'skipped':
        return '<span class="status-info">&#8505;</span>'
    return '<span class="status-info">&#8505;</span>'


def issue_count_display(section):
    """Return display text for issue count in the section review table."""
    status = section.get('status', '').lower()
    display = section.get('display_count')
    if display:
        if display.lower() in ('observations', 'skipped'):
            return f'<span class="issues-count" style="color: #a0aec0;">{esc(display)}</span>'
        return f'<span class="issues-count">{esc(display)}</span>'
    count = section.get('issue_count', 0)
    return f'<span class="issues-count">{count}</span>'


def metacheck_badge():
    """Return metacheck badge HTML."""
    return '<span class="badge-auto">[metacheck]</span>'


# ---------------------------------------------------------------------------
# Section renderers
# ---------------------------------------------------------------------------

def render_header(data):
    meta = data.get('metadata', {})
    title = esc(meta.get('manuscript_title', 'Untitled'))
    date = esc(meta.get('date', ''))
    review_meta = meta.get('review_meta', '')
    meta_line = f'{date} &bull; Review by Claude'
    if review_meta:
        meta_line += f' &bull; {esc(review_meta)}'
    return (
        f'<h1>MANUSCRIPT REVIEW REPORT</h1>\n'
        f'<p class="subtitle">{title}</p>\n'
        f'<p class="meta">{meta_line}</p>'
    )


def render_about(data):
    mc = data.get('metadata', {}).get('metacheck_available', False)
    text = ABOUT_WITH_METACHECK if mc else ABOUT_WITHOUT_METACHECK
    return (
        f'<div class="about-box">\n'
        f'  <h2>ABOUT THIS REPORT</h2>\n'
        f'  <p>{text}</p>\n'
        f'</div>'
    )


def render_summary(data):
    summary = data.get('overall_summary', {})
    text = esc(summary.get('text', ''))
    c = summary.get('critical_count', 0)
    m = summary.get('major_count', 0)
    mi = summary.get('minor_count', 0)
    return (
        f'<h2 class="section-title">OVERALL SUMMARY</h2>\n'
        f'<hr class="section-divider">\n'
        f'<p class="summary-text">{text}</p>\n'
        f'<div class="stats-row">\n'
        f'  <div class="stat-box">\n'
        f'    <div class="stat-label">CRITICAL ISSUES</div>\n'
        f'    <div class="stat-number critical">{c}</div>\n'
        f'  </div>\n'
        f'  <div class="stat-box">\n'
        f'    <div class="stat-label">MAJOR ISSUES</div>\n'
        f'    <div class="stat-number major">{m}</div>\n'
        f'  </div>\n'
        f'  <div class="stat-box">\n'
        f'    <div class="stat-label">MINOR ISSUES</div>\n'
        f'    <div class="stat-number minor">{mi}</div>\n'
        f'  </div>\n'
        f'</div>'
    )


def render_critical_issues(data):
    issues = data.get('top_critical_issues', [])
    if not issues:
        return ''
    parts = [
        '<h2 class="section-title">TOP CRITICAL ISSUES</h2>',
        '<hr class="section-divider">',
    ]
    for issue in issues:
        parts.append(
            f'<div class="issue-card">\n'
            f'  <span class="badge badge-critical">Critical</span>\n'
            f'  <strong>{esc(issue.get("title", ""))}</strong>\n'
            f'  <div class="issue-location">Location: {esc(issue.get("category", ""))}</div>\n'
            f'  <div class="explanation">{esc(issue.get("details", ""))}</div>\n'
            f'</div>'
        )
    return '\n'.join(parts)


def render_language_quality(data):
    lq = data.get('language_quality', {})
    overall = lq.get('overall_grade', 'N/A')
    badge_css = grade_badge_css(overall)

    parts = [
        '<h2 class="section-title">LANGUAGE QUALITY</h2>',
        '<hr class="section-divider">',
        f'<p class="summary-text">Overall Language Score: <strong>{grade_display(overall)}</strong> '
        f'<span class="overall-grade {badge_css}">{grade_display(overall)}</span></p>',
    ]

    dims = lq.get('dimensions', [])
    if dims:
        parts.append('<p style="margin-top: 16px; margin-bottom: 8px;"><strong class="label">Notable dimensions:</strong></p>')
    for dim in dims:
        grade = dim.get('grade', 'N/A')
        card_extra = grade_card_css(grade)
        parts.append(
            f'<div class="grade-card{card_extra}">\n'
            f'  <div>\n'
            f'    <div class="grade-title">{esc(dim.get("name", ""))}</div>\n'
            f'    <div class="grade-desc">{esc(dim.get("description", ""))}</div>\n'
            f'  </div>\n'
            f'  <div class="grade-badge {grade_badge_css(grade)}">{grade_display(grade)}</div>\n'
            f'</div>'
        )

    strengths = lq.get('key_strengths', [])
    if strengths:
        parts.append('<p style="margin-top: 16px;"><strong class="label">Key Strengths:</strong></p>')
        parts.append('<ul class="strengths-list">')
        for s in strengths:
            parts.append(f'  <li>{esc(s)}</li>')
        parts.append('</ul>')

    improvements = lq.get('areas_for_improvement', [])
    if improvements:
        parts.append('<p><strong class="label">Areas for Improvement:</strong></p>')
        parts.append('<ul class="improvements-list">')
        for i in improvements:
            parts.append(f'  <li>{esc(i)}</li>')
        parts.append('</ul>')

    return '\n'.join(parts)


def render_section_review_table(data):
    sections = data.get('section_review', [])
    # Override status based on actual issue count (agent sometimes gets this wrong)
    for sec in sections:
        count = sec.get('issue_count', 0)
        display = sec.get('display_count', '')
        if isinstance(count, int) and count > 0 and not display:
            sec['status'] = 'fail'
        elif isinstance(count, int) and count == 0 and sec.get('status') not in ('info', 'skipped'):
            if not display:
                sec['status'] = 'pass'
    rows = []
    for sec in sections:
        rows.append(
            f'    <tr>\n'
            f'      <td>\n'
            f'        <div class="table-section-name">{esc(sec.get("name", ""))}</div>\n'
            f'        <div class="table-section-desc">{esc(sec.get("description", ""))}</div>\n'
            f'      </td>\n'
            f'      <td>{status_icon(sec.get("status", "pass"))}</td>\n'
            f'      <td>{issue_count_display(sec)}</td>\n'
            f'    </tr>'
        )
    return (
        '<h2 class="section-title">SECTION REVIEW SUMMARY</h2>\n'
        '<hr class="section-divider">\n'
        '<table class="review-table">\n'
        '  <thead>\n'
        '    <tr>\n'
        '      <th>SECTION</th>\n'
        '      <th>STATUS</th>\n'
        '      <th>ISSUES</th>\n'
        '    </tr>\n'
        '  </thead>\n'
        '  <tbody>\n'
        + '\n'.join(rows) + '\n'
        '  </tbody>\n'
        '</table>'
    )


def render_issue_card(issue, show_number=False, number_prefix=""):
    """Render a single issue card."""
    sev = issue.get('severity', 'minor')
    location = issue.get('location', '')
    original = issue.get('original')
    suggestion = issue.get('suggestion')
    action = issue.get('action')
    explanation = issue.get('explanation', '')
    badge_auto = issue.get('badge_auto', False)
    title = issue.get('title', '')

    parts = ['<div class="issue-card no-break">']

    # Location line with severity badge
    loc_line = f'  <div class="issue-location">'
    if title:
        # If there's a title, show badge then title on one line, location below
        parts.append(f'  {severity_badge(sev)}')
        parts.append(f'  <strong>{md_bold(title) if "**" in (title or "") else esc(title)}</strong>')
        if location:
            parts.append(f'  <div class="issue-location">Location: {esc(location)}</div>')
    else:
        loc_line += f'Location: {esc(location)} {severity_badge(sev)}'
        loc_line += '</div>'
        parts.append(loc_line)

    # Original text block
    if original:
        parts.append(f'  <div class="original-block"><strong>Original:</strong> {md_bold(original)}</div>')

    # Suggestion or Action block
    if suggestion:
        parts.append(f'  <div class="suggestion-block"><strong>Suggestion:</strong> {md_bold(suggestion)}</div>')
    elif action:
        parts.append(f'  <div class="suggestion-block"><strong>Action:</strong> {md_bold(action)}</div>')

    # Explanation
    if explanation:
        auto_badge = f' {metacheck_badge()}' if badge_auto else ''
        parts.append(f'  <p class="explanation"><strong>Explanation:</strong> {md_bold(explanation)}{auto_badge}</p>')

    parts.append('</div>')
    return '\n'.join(parts)


def render_doi_table(suggestions):
    """Render DOI suggestion table."""
    if not suggestions:
        return ''
    confidence_icons = {
        'high': '<span class="status-pass">&#10003;</span>',
        'moderate': '<span class="status-info">&#8505;</span>',
        'low': '<span class="status-fail">&times;</span>',
    }
    rows = []
    for s in suggestions:
        ref = esc(s.get('reference', ''))
        doi = s.get('doi', '')
        doi_url = s.get('doi_url', f'https://doi.org/{doi}')
        conf = s.get('confidence', 'moderate').lower()
        icon = confidence_icons.get(conf, confidence_icons['moderate'])
        rows.append(
            f'    <tr>\n'
            f'      <td>{ref}</td>\n'
            f'      <td style="text-align: left;"><a href="{esc(doi_url)}">{esc(doi)}</a></td>\n'
            f'      <td>{icon}</td>\n'
            f'    </tr>'
        )
    return (
        '<table class="review-table" style="margin-top: 12px; font-size: 13px;">\n'
        '  <thead>\n'
        '    <tr>\n'
        '      <th>REFERENCE</th>\n'
        '      <th style="text-align: left;">SUGGESTED DOI</th>\n'
        '      <th>CONFIDENCE</th>\n'
        '    </tr>\n'
        '  </thead>\n'
        '  <tbody>\n'
        + '\n'.join(rows) + '\n'
        '  </tbody>\n'
        '</table>\n'
        '<p style="font-size: 12px; color: #718096; margin-top: 8px;">'
        'Confidence: <span class="status-pass" style="width: 18px; height: 18px; font-size: 12px;">&#10003;</span> '
        'High (score &gt; 100) &mdash; '
        '<span class="status-info" style="width: 18px; height: 18px; font-size: 12px;">&#8505;</span> '
        'Moderate (score 60&ndash;100) &mdash; '
        '<span class="status-fail" style="width: 18px; height: 18px; font-size: 12px;">&times;</span> '
        'Low (score &lt; 60, likely wrong match). CrossRef match scores from metacheck.</p>'
    )


def render_statcheck_table(results):
    """Render statcheck verification table."""
    if not results:
        return ''
    rows = []
    for r in results:
        status = r.get('status', 'pass').lower()
        icon = '<span class="status-pass">&#10003;</span>' if status == 'pass' else '<span class="status-fail">&times;</span>'
        rows.append(
            f'    <tr>\n'
            f'      <td style="font-size: 13px;">{esc(r.get("reported", ""))}</td>\n'
            f'      <td style="font-size: 13px;">{esc(r.get("computed", ""))}</td>\n'
            f'      <td>{icon}</td>\n'
            f'    </tr>'
        )
    return (
        '<table class="review-table" style="margin-top: 12px;">\n'
        '  <thead>\n'
        '    <tr>\n'
        '      <th>TEST</th>\n'
        '      <th>REPORTED</th>\n'
        '      <th>STATUS</th>\n'
        '    </tr>\n'
        '  </thead>\n'
        '  <tbody>\n'
        + '\n'.join(rows) + '\n'
        '  </tbody>\n'
        '</table>'
    )


def render_replication_results(results):
    """Render replication/reproduction results."""
    if not results:
        return ''
    parts = []
    for r in results:
        orig = esc(r.get('original', ''))
        repl = esc(r.get('replication', ''))
        context = r.get('context_note', '')
        parts.append('<div class="issue-card no-break">')
        parts.append(f'  <p><strong>Original:</strong> {orig}</p>')
        parts.append(f'  <p><strong>Replication:</strong> {repl}</p>')
        if context:
            parts.append(f'  <p style="font-size: 13px; color: #718096; margin-top: 8px;">{esc(context)}</p>')
        parts.append('</div>')
    return '\n'.join(parts)


def render_subsection(sub):
    """Render a subsection within a check category."""
    title = esc(sub.get('title', ''))
    badge = f' {metacheck_badge()}' if sub.get('badge') == 'metacheck' else ''
    summary = sub.get('summary', '')

    parts = [
        f'<h4 style="font-size: 15px; font-weight: 600; color: #4a5568; '
        f'margin-top: 20px; margin-bottom: 12px;">{title}{badge}</h4>'
    ]

    if summary:
        parts.append(f'<p class="summary-text">{md_bold(summary)}</p>')

    for issue in sub.get('issues', []):
        parts.append(render_issue_card(issue))

    # Render any inline HTML content (for complex subsections)
    content_html = sub.get('content_html', '')
    if content_html:
        parts.append(content_html)

    return '\n'.join(parts)


def render_metacheck_info(info):
    """Render metacheck-specific information within a category."""
    if not info:
        return ''
    parts = []

    # Retraction summary
    retraction = info.get('retraction_summary')
    if retraction:
        parts.append(f'<p class="summary-text">{md_bold(retraction)}</p>')

    # DOI suggestions table
    doi_sugg = info.get('doi_suggestions', [])
    if doi_sugg:
        parts.append(render_doi_table(doi_sugg))

    # Replication results
    repl = info.get('replication_results', [])
    if repl:
        parts.append(render_replication_results(repl))

    # Statcheck results
    statcheck = info.get('statcheck_results', [])
    if statcheck:
        parts.append(render_statcheck_table(statcheck))

    # P-value summary
    pval = info.get('p_value_summary')
    if pval:
        parts.append(f'<p class="summary-text">{md_bold(pval)}</p>')

    # Marginal significance notes
    marginal = info.get('marginal_notes')
    if marginal:
        parts.append(f'<p class="summary-text">{md_bold(marginal)}</p>')

    # Open science items
    open_sci = info.get('open_science', [])
    if open_sci:
        parts.append('<ul class="strengths-list">')
        for item in open_sci:
            parts.append(f'  <li>{md_bold(item)}</li>')
        parts.append('</ul>')

    # Disagreements
    for d in info.get('disagreements', []):
        parts.append(
            f'<div class="disagreement-note">\n'
            f'  <strong>Note:</strong> {md_bold(d.get("text", ""))}\n'
            f'</div>'
        )

    return '\n'.join(parts)


def render_detailed_sections(data):
    """Render all detailed recommendation sections."""
    categories = data.get('check_categories', [])
    parts = [
        '<h2 class="section-title">DETAILED RECOMMENDATIONS</h2>',
        '<hr class="section-divider">',
    ]

    for cat in categories:
        num = cat.get('number', '')
        name = esc(cat.get('name', ''))
        summary = cat.get('summary', '')
        all_issues = cat.get('issues', [])

        # Collect all issues from subsections too for counting
        sub_issues = []
        for sub in cat.get('subsections', []):
            sub_issues.extend(sub.get('issues', []))

        combined_issues = all_issues + sub_issues
        badges_html = count_badges(combined_issues) if combined_issues else \
            '<span class="count-badge" style="background:#c6f6d5; color:#276749;">0 issues</span>'

        # Add page break before referencing section (typically the longest)
        if cat.get('page_break', False):
            parts.append('<div class="page-break"></div>')

        parts.append(
            f'<h3 style="font-size: 17px; font-weight: 700; color: #2d3748; '
            f'margin-top: 32px; margin-bottom: 4px;">{num}. {name}</h3>'
        )
        parts.append(f'<p style="margin-bottom: 16px;">{badges_html}</p>')

        if summary:
            parts.append(f'<p class="summary-text">{md_bold(summary)}</p>')

        # Top-level issues
        for issue in all_issues:
            parts.append(render_issue_card(issue))

        # Subsections
        for sub in cat.get('subsections', []):
            parts.append(render_subsection(sub))

        # Metacheck info
        mc_info = cat.get('metacheck_info')
        if mc_info:
            parts.append(render_metacheck_info(mc_info))

        # Content observations
        for obs in cat.get('content_observations', []):
            badge = f' {metacheck_badge()}' if obs.get('badge') == 'metacheck' else ''
            parts.append(
                f'<div class="content-note">\n'
                f'  <strong>{esc(obs.get("title", ""))}:</strong>{badge} {md_bold(obs.get("text", ""))}\n'
                f'</div>'
            )

    return '\n'.join(parts)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def render_html(data):
    """Render complete HTML from review data."""
    sections = [
        '<!DOCTYPE html>',
        '<html lang="en">',
        '<head>',
        '<meta charset="UTF-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1.0">',
        '<title>Manuscript Review Report</title>',
        f'<style>\n{CSS}</style>',
        '</head>',
        '<body>',
        '',
        render_header(data),
        '',
        render_about(data),
        '',
        render_summary(data),
        '',
        render_critical_issues(data),
        '',
        render_language_quality(data),
        '',
        render_section_review_table(data),
        '',
        render_detailed_sections(data),
        '',
        '</body>',
        '</html>',
    ]
    return '\n'.join(sections)


def inject_metacheck(data, metacheck):
    """Inject metacheck data directly into the review data for rendering.

    Populates DOI suggestions, statcheck results, retraction/PubPeer summaries,
    and other fields that the agent should NOT have to copy manually.
    """
    if not metacheck or 'results' not in metacheck:
        return
    results = metacheck['results']

    # Find categories by number
    cats = {c['number']: c for c in data.get('check_categories', [])}

    # --- Category 7: Referencing ---
    cat7 = cats.get(7)
    if cat7:
        mc = cat7.setdefault('metacheck_info', {}) or {}
        cat7['metacheck_info'] = mc

        # DOI suggestions: read directly from metacheck, filter by agent exclusions
        doi_exclusions = set(mc.get('doi_exclusions', []))
        doi_check = results.get('ref_doi_check', {}).get('table', [])
        doi_suggestions = []
        for entry in doi_check:
            doi = entry.get('DOI')
            if not doi or doi in doi_exclusions:
                continue
            score = entry.get('score', 0)
            if score >= 60:
                conf = 'high' if score > 100 else 'moderate'
            else:
                conf = 'low'
            ref_text = entry.get('ref', '').replace('<em>', '').replace('</em>', '')
            ref_text = ref_text.replace('&ldquo;', '\u201c').replace('&rdquo;', '\u201d')
            doi_suggestions.append({
                'reference': ref_text,
                'doi': doi,
                'doi_url': f'https://doi.org/{doi}',
                'confidence': conf,
            })
        if doi_suggestions:
            mc['doi_suggestions'] = doi_suggestions

        # Retraction summary
        retraction = results.get('ref_retraction', {})
        if retraction.get('report') and not mc.get('retraction_summary'):
            mc['retraction_summary'] = retraction['report']

        # PubPeer summary
        pubpeer = results.get('ref_pubpeer', {})
        if pubpeer.get('report') and not mc.get('retraction_summary'):
            mc['retraction_summary'] = (mc.get('retraction_summary', '') + ' ' +
                                         pubpeer['report']).strip()

        # Replication results
        repl = results.get('ref_replication', {}).get('table', [])
        if repl and not mc.get('replication_results'):
            repl_results = []
            for r in repl:
                repl_results.append({
                    'original': r.get('original_ref', r.get('ref', '')),
                    'replication': r.get('replication_ref', r.get('flora_ref', '')),
                    'context_note': r.get('context', None),
                })
            mc['replication_results'] = repl_results

    # --- Category 12: Statistical Reporting ---
    cat12 = cats.get(12)
    if cat12:
        mc = cat12.setdefault('metacheck_info', {}) or {}
        cat12['metacheck_info'] = mc

        # Statcheck results
        stat_check = results.get('stat_check', {}).get('table', [])
        if stat_check and not mc.get('statcheck_results'):
            mc['statcheck_results'] = [
                {
                    'reported': s.get('raw', ''),
                    'computed': f"Computed p = {s.get('computed_p', 'N/A')}",
                    'status': 'fail' if s.get('error') else 'pass',
                }
                for s in stat_check
            ]

        # P-value summary
        p_vals = results.get('all_p_values', {}).get('table', [])
        if p_vals and not mc.get('p_value_summary'):
            mc['p_value_summary'] = f"{len(p_vals)} p-values detected in the manuscript."

        # Marginal significance
        marginal = results.get('marginal', {}).get('table', [])
        if marginal and not mc.get('marginal_notes'):
            texts = [m.get('text', '') for m in marginal]
            mc['marginal_notes'] = f"{len(marginal)} instance(s) of marginal significance language detected: {'; '.join(texts)}"

    # --- Category 10: Funding & Compliance ---
    cat10 = cats.get(10)
    if cat10:
        mc = cat10.setdefault('metacheck_info', {}) or {}
        cat10['metacheck_info'] = mc

        open_sci = []
        op = results.get('open_practices', {})
        if op.get('report'):
            open_sci.append(f"**Open practices:** {op['report']}")
        prereg = results.get('prereg_check', {})
        if prereg.get('report'):
            open_sci.append(f"**Preregistration:** {prereg['report']}")
        coi = results.get('coi_check', {})
        if coi.get('report'):
            open_sci.append(f"**COI statement:** {coi['report']}")
        funding = results.get('funding_check', {})
        if funding.get('report'):
            open_sci.append(f"**Funding statement:** {funding['report']}")
        if open_sci and not mc.get('open_science'):
            mc['open_science'] = open_sci


def main():
    if len(sys.argv) < 3:
        print("Usage: render_report.py <input.json> <output.html> [metacheck.json]", file=sys.stderr)
        sys.exit(1)

    input_path = sys.argv[1]
    output_path = sys.argv[2]
    metacheck_path = sys.argv[3] if len(sys.argv) > 3 else None

    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Inject metacheck data directly (DOI table, statcheck, etc.)
    if metacheck_path:
        try:
            with open(metacheck_path, 'r', encoding='utf-8') as f:
                metacheck = json.load(f)
            inject_metacheck(data, metacheck)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"Warning: Could not load metacheck data: {e}", file=sys.stderr)

    html_content = render_html(data)

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_content)

    print(f"Report written to {output_path}", file=sys.stderr)


if __name__ == '__main__':
    main()
