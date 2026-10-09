"""Self-contained SVG visualizations for public profile metrics and Actions."""
from xml.sax.saxutils import escape

BORDER = "#30455d"
INK = "#f1f7ff"
MUTED = "#9bb0c7"
CYAN = "#69b9fb"
GREEN = "#55d6b3"
RED = "#fb7785"
AMBER = "#ffcb75"


def xml(text):
    return escape(str(text), {'"': '&quot;', "'": '&apos;'})


def cut(text, length=29):
    text = str(text)
    return text if len(text) <= length else text[:length-3] + "..."


def surround(width, height, body, title):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
            f'viewBox="0 0 {width} {height}" role="img" aria-label="{xml(title)}">\n'
            f'<title>{xml(title)}</title>\n'
            '<defs><linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">'
            '<stop offset="0" stop-color="#111f31"/>'
            '<stop offset="1" stop-color="#14283c"/></linearGradient></defs>\n'
            f'<rect x="1" y="1" width="{width-2}" height="{height-2}" rx="13" '
            f'fill="url(#bg)" stroke="{BORDER}" stroke-width="1"/>\n'
            + body + '\n</svg>\n')


def actions_card(summary, checked):
    workflows = summary.get("workflows", [])
    failing = sum(1 for w in workflows if w.get("failed"))
    unknown = len(summary.get("unknown", []))
    running = sum(1 for w in workflows if w.get("running"))
    if failing:
        statement = f"{failing} workflow" + (" needs attention" if failing == 1 else "s need attention")
        label, color = "ISSUES DETECTED", RED
    elif unknown:
        statement, label, color = f"{unknown} checks unavailable", "PARTIAL COVERAGE", AMBER
    elif running:
        statement, label, color = f"{running} workflow" + (" running" if running == 1 else "s running"), "UPDATING", CYAN
    elif workflows:
        statement, label, color = "All checked workflows healthy", "ALL CLEAR", GREEN
    else:
        statement, label, color = "Waiting for workflow results", "NO RECENT DATA", AMBER
    latest = summary.get("latest") or {}
    repo = cut(latest.get("repo", "-").split("/")[-1])
    outcome = latest.get("conclusion") or latest.get("status") or "no runs"
    outcome_color = GREEN if outcome == "success" else RED if outcome == "failure" else CYAN
    body = f'''
<rect x="1" y="14" width="4" height="84" rx="2" fill="{color}"/>
<circle cx="27" cy="27" r="5" fill="{color}"/>
<text x="41" y="31" font-family="Arial,Helvetica,sans-serif" font-size="11" letter-spacing="1.6" fill="{MUTED}">ACCOUNT-WIDE ACTIONS</text>
<text x="27" y="64" font-family="Arial,Helvetica,sans-serif" font-size="21" font-weight="700" fill="{INK}">{xml(statement)}</text>
<text x="27" y="88" font-family="Arial,Helvetica,sans-serif" font-size="12" fill="{color}" font-weight="700" letter-spacing="1">{label}</text>
<path d="M435 23V89" stroke="{BORDER}" stroke-width="1"/>
<text x="456" y="31" font-family="Arial,Helvetica,sans-serif" font-size="11" letter-spacing="1.2" fill="{MUTED}">MOST RECENT RUN</text>
<text x="456" y="59" font-family="Arial,Helvetica,sans-serif" font-size="16" font-weight="700" fill="{INK}">{xml(repo)}</text>
<text x="456" y="81" font-family="Arial,Helvetica,sans-serif" font-size="12" fill="{MUTED}">Outcome: <tspan fill="{outcome_color}">{xml(outcome)}</tspan></text>
<text x="27" y="103" font-family="Arial,Helvetica,sans-serif" font-size="9.5" fill="{MUTED}">{summary.get("repos", 0)} public repositories / {len(workflows)} monitored workflows / checked {xml(checked)} UTC</text>'''
    return surround(760, 116, body, f"Account Actions: {statement}; latest: {repo} {outcome}")


def stats_strip(repos, stars, followers, gists):
    stats = [("PUBLIC REPOS", repos), ("TOTAL STARS", stars), ("FOLLOWERS", followers), ("PUBLIC GISTS", gists)]
    lines = []
    for i, (name, value) in enumerate(stats):
        x = 26 + i*184
        if i:
            lines.append(f'<path d="M{x-14} 22V78" stroke="{BORDER}" stroke-width="1"/>')
        lines += [
            f'<text x="{x}" y="33" font-family="Arial,Helvetica,sans-serif" font-size="10.5" letter-spacing="1" fill="{MUTED}">{xml(name)}</text>',
            f'<text x="{x}" y="70" font-family="Arial,Helvetica,sans-serif" font-size="27" font-weight="700" fill="{INK}">{xml(value)}</text>'
        ]
    return surround(760, 98, '\n'.join(lines), "GitHub statistics: " + ", ".join(f"{name}: {value}" for name, value in stats))


def quick_link(kind):
    if kind == "portfolio":
        width, title, subtitle, accent = 252, "PORTFOLIO", "Personal website", CYAN
        icon = (f'<circle cx="27" cy="26" r="11" fill="none" stroke="{accent}" stroke-width="1.4"/>'
                f'<path d="M16 26H38M27 15C21 19 21 33 27 37M27 15C33 19 33 33 27 37" fill="none" stroke="{accent}" stroke-width="1.2"/>')
    elif kind == "builder":
        width, title, subtitle, accent = 280, "PERSONAL REPO BUILDER", "Choose your extensions", GREEN
        icon = (f'<rect x="17" y="16" width="14" height="14" rx="2" fill="none" stroke="{accent}" stroke-width="1.5"/>'
                f'<rect x="24" y="23" width="15" height="15" rx="2" fill="none" stroke="{accent}" stroke-width="1.5"/>')
    else:
        raise ValueError("Unknown quick link")
    body = f'''<rect x="1" y="1" width="4" height="50" rx="2" fill="{accent}"/>
{icon}
<text x="50" y="23" font-family="Arial,Helvetica,sans-serif" font-size="12" font-weight="700" letter-spacing="0.6" fill="{INK}">{title}</text>
<text x="50" y="39" font-family="Arial,Helvetica,sans-serif" font-size="10.5" fill="{MUTED}">{subtitle}</text>
<path d="M{width-28} 25h10m-4-5 5 5-5 5" fill="none" stroke="{accent}" stroke-width="1.4" stroke-linejoin="round"/>'''
    return surround(width, 54, body, title + ": " + subtitle)
