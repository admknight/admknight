#!/usr/bin/env python3
"""Monitor the latest meaningful GitHub Actions result for each public workflow.

Publishes public-only Shields endpoint JSON and a detailed Markdown report.
No access to private repositories is requested or published.
"""

import argparse
import json
import os
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

API_ROOT = "https://api.github.com"
FAILURES = {"failure", "timed_out", "startup_failure", "action_required"}
NON_DECISIVE = {"cancelled", "skipped", "neutral"}


def github_api(path):
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "account-actions-monitor",
    }
    if os.environ.get("GITHUB_TOKEN"):
        headers["Authorization"] = "Bearer " + os.environ["GITHUB_TOKEN"]
    request = Request(API_ROOT + path, headers=headers)
    try:
        with urlopen(request, timeout=18) as response:
            return json.load(response)
    except (HTTPError, URLError) as error:
        raise RuntimeError(f"GitHub API request failed ({path}): {error}") from error


def pages(api, path, field=None):
    result = []
    page = 1
    while True:
        separator = "&" if "?" in path else "?"
        payload = api(f"{path}{separator}per_page=100&page={page}")
        records = payload[field] if field else payload
        if not isinstance(records, list):
            raise ValueError(f"Unexpected GitHub API response for {path}")
        result.extend(records)
        if len(records) < 100:
            return result
        page += 1


def last_meaningful_run(runs):
    """Keep failures visible while a rerun is underway or runs are cancelled."""
    for run in runs:
        if run.get("status") != "completed":
            continue
        if run.get("conclusion") not in NON_DECISIVE:
            return run
    return None


def scan(user, api=github_api):
    summary = {"repos": 0, "workflows": [], "unknown": [], "latest": None}
    try:
        repos = pages(api, f"/users/{quote(user)}/repos?type=owner")
    except Exception as error:
        summary["unknown"].append(("Repository discovery", str(error)))
        return summary

    public = [repo for repo in repos if not repo.get("private") and repo.get("owner", {}).get("login", "").casefold() == user.casefold()]
    summary["repos"] = len(public)
    summary["stars"] = sum(int(repo.get("stargazers_count") or 0) for repo in public)
    for repo in public:
        name = repo["full_name"]
        safe_name = quote(name, safe="/")
        try:
            workflows = pages(api, f"/repos/{safe_name}/actions/workflows", "workflows")
        except Exception as error:
            summary["unknown"].append((name, str(error)))
            continue
        for workflow in workflows:
            if workflow.get("state") != "active":
                continue
            # Avoid the monitoring workflow itself becoming a self-referential result.
            if name.casefold() == f"{user}/{user}".casefold() and workflow.get("path", "").endswith("account-actions-monitor.yml"):
                continue
            label = workflow.get("name") or str(workflow.get("id"))
            try:
                payload = api(f"/repos/{safe_name}/actions/workflows/{workflow['id']}/runs?per_page=10")
                runs = payload["workflow_runs"]
                if not isinstance(runs, list):
                    raise ValueError("Unexpected workflow run response")
            except Exception as error:
                summary["unknown"].append((f"{name} / {label}", str(error)))
                continue
            if not runs:
                continue
            newest = runs[0]
            decisive = last_meaningful_run(runs)
            item = {
                "repo": name,
                "workflow": label,
                "latest": newest,
                "decisive": decisive,
                "running": newest.get("status") != "completed",
                "failed": bool(decisive and decisive.get("conclusion") in FAILURES),
            }
            summary["workflows"].append(item)
            if summary["latest"] is None or newest.get("created_at", "") > summary["latest"].get("created_at", ""):
                summary["latest"] = {**newest, "repo": name, "workflow": label}
    return summary


def md(text):
    """Keep dynamic API metadata from breaking a public Markdown table."""
    return str(text).replace("|", "\\|").replace("\n", " ").replace("\r", " ").replace("<", "&lt;").replace(">", "&gt;")


def badge(label, message, color):
    return {"schemaVersion": 1, "label": label, "message": message, "color": color}


def render(summary, checked):
    workflows = summary["workflows"]
    failing = sorted((w for w in workflows if w["failed"]), key=lambda w: w["repo"].casefold())
    running = [w for w in workflows if w["running"]]
    unknown = summary["unknown"]
    passes = sum(bool(w["decisive"] and w["decisive"].get("conclusion") == "success") for w in workflows)
    if failing:
        msg = f"{len(failing)} failing"
        if unknown:
            msg += f", {len(unknown)} unchecked"
        color = "critical"
    elif unknown:
        msg, color = f"{len(unknown)} unchecked", "orange"
    elif running:
        msg, color = f"{len(running)} running, 0 failing", "blue"
    elif workflows:
        msg, color = "no failures", "brightgreen"
    else:
        msg, color = "no workflow results", "lightgrey"
    overall_badge = badge("Public Repo Actions", msg, color)
    latest = summary["latest"]
    if latest:
        label = latest["repo"].split("/", 1)[-1]
        status = latest.get("conclusion") or latest.get("status") or "unknown"
        latest_message = f"{label[:23]}: {status}"
        latest_color = "critical" if status in FAILURES else "blue" if status != "success" else "brightgreen"
    else:
        latest_message, latest_color = "no runs", "lightgrey"
    latest_badge = badge("Latest Action", latest_message, latest_color)

    lines = [
        "# Account-wide GitHub Actions Status", "",
        f"**Checked:** {checked} UTC  ",
        f"**Coverage:** {summary['repos']} public owned repositories; active workflows with recorded runs only.  ",
        f"**Status:** {len(failing)} failing workflows · {len(running)} running · {len(unknown)} unchecked · {passes} last-result successes.", "",
        "Each workflow is checked separately. A failed latest meaningful run remains visible until that workflow has a successful run. "
        "Cancelled, skipped and neutral runs do not clear an earlier failure. This is not a live check; it updates when the monitor workflow completes.", "",
    ]
    if latest:
        lines += [f"**Latest action:** [{md(latest['repo'])} / {md(latest['workflow'])}]({latest.get('html_url', '#')}) — {md(latest.get('conclusion') or latest.get('status') or 'unknown')}.", ""]

    if failing:
        lines += ["## Needs attention", "", "| Repository | Workflow | Last meaningful outcome | Run |", "| --- | --- | --- | --- |"]
        for w in failing:
            decisive = w["decisive"]
            lines.append(f"| {md(w['repo'])} | {md(w['workflow'])} | **{md(decisive['conclusion'])}** | [Investigate]({decisive.get('html_url', '#')}) |")
        lines.append("")
    if unknown:
        lines += ["## Could not check", "", "| Target | Reason |", "| --- | --- |"]
        for target, reason in unknown:
            lines.append(f"| {md(target)} | {md(reason)[:160]} |")
        lines.append("")
    if running:
        lines += ["## Running / queued", "", "| Repository | Workflow | Run |", "| --- | --- | --- |"]
        for w in running:
            lines.append(f"| {md(w['repo'])} | {md(w['workflow'])} | [Open]({w['latest'].get('html_url', '#')}) |")
        lines.append("")
    lines += ["## All monitored workflows", "", "| Repository | Workflow | Latest meaningful result | Latest run |", "| --- | --- | --- | --- |"]
    for w in sorted(workflows, key=lambda x: (x["repo"].casefold(), x["workflow"].casefold())):
        decisive = w["decisive"]
        conclusion = (decisive or {}).get("conclusion") or "pending / no decisive result"
        lines.append(f"| {md(w['repo'])} | {md(w['workflow'])} | {md(conclusion)} | [Open]({w['latest'].get('html_url', '#')}) |")
    lines += ["", "---", "", "Generated from the public GitHub REST API by the account-actions-monitor workflow. Private repositories and disabled workflows are not included.", ""]
    return overall_badge, latest_badge, "\n".join(lines)


# Komarev is already used for this profile's visit count. Check once per UTC
# day, not on every scheduled 15-minute scan, to avoid artificial visits.
VALID_VISITS = re.compile(r"^[0-9][0-9,]*(?:\.[0-9]+)?[kKmM]?$")


def fetch_profile_visits(user):
    params = urlencode({"username": user, "color": "356789", "style": "flat-square", "label": "VISITS"})
    request = Request("https://komarev.com/ghpvc/?" + params,
                      headers={"User-Agent": "AdamKnight-Profile-Stats", "Accept": "image/svg+xml"})
    with urlopen(request, timeout=14) as response:
        if response.status != 200 or "image/svg+xml" not in response.headers.get("Content-Type", ""):
            raise ValueError("Komarev did not return an SVG badge")
        root = ET.fromstring(response.read(30000))
    title = next((element.text or "" for element in root.iter()
                  if element.tag.rsplit("}", 1)[-1] == "title"), "")
    for content in (root.attrib.get("aria-label", ""), title):
        match = re.search(r"(?:VISITS|PROFILE VIEWS|VIEWS)\s*:\s*([0-9][0-9,]*(?:\.[0-9]+)?[kKmM]?)",
                          content, re.I)
        if match and VALID_VISITS.fullmatch(match.group(1)):
            return match.group(1)
    raise ValueError("Komarev badge did not contain a numeric visit count")


def update_profile_visits(cache_file, today, fetcher):
    old = {}
    if cache_file and cache_file.exists():
        try:
            old = json.loads(cache_file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            pass
    if not isinstance(old, dict):
        old = {}
    previous = str(old.get("value", "--"))
    if not VALID_VISITS.fullmatch(previous):
        previous = "--"
    if old.get("lastAttemptUTC") == today:
        return {"value": previous, "lastAttemptUTC": today}
    try:
        fresh = str(fetcher())
        if not VALID_VISITS.fullmatch(fresh):
            raise ValueError("Visit count was not numeric")
    except Exception as error:
        print(f"Daily visit reading unavailable: {type(error).__name__}: {error}")
        fresh = previous
    return {"value": fresh, "lastAttemptUTC": today}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--user", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--visits-cache", type=Path)
    args = parser.parse_args()
    summary = scan(args.user)
    checked = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
    overall, latest, report = render(summary, checked)
    from profile_badges import actions_card, stats_strip, quick_link
    try:
        account = github_api(f"/users/{quote(args.user)}")
    except Exception as error:
        print(f"Public account counters unavailable: {error}")
        account = {}
    args.out.mkdir(parents=True, exist_ok=True)
    visit_state = update_profile_visits(
        args.visits_cache, datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        lambda: fetch_profile_visits(args.user),
    )
    (args.out / "profile-visits.json").write_text(json.dumps(visit_state) + "\n", encoding="utf-8")
    print("Profile visit count:", visit_state["value"])
    custom_assets = {
        "actions-card.svg": actions_card(summary, checked),
        "stats-strip.svg": stats_strip(
            summary["repos"] if "stars" in summary else "--",
            summary.get("stars", "--"),
            account.get("followers", "--"), account.get("public_gists", "--"),
            visit_state["value"]),
        "portfolio.svg": quick_link("portfolio"),
        "builder.svg": quick_link("builder"),
    }
    for name, svg in custom_assets.items():
        (args.out / name).write_text(svg, encoding="utf-8")
    for filename, content in (("actions.json", overall), ("latest.json", latest)):
        (args.out / filename).write_text(json.dumps(content, separators=(",", ":")) + "\n", encoding="utf-8")
    (args.out / "ACTIONS_STATUS.md").write_text(report, encoding="utf-8")
    print(f"Scanned {summary['repos']} public repositories, {len(summary['workflows'])} workflow results, {len(summary['unknown'])} API gaps. Status: {overall['message']}")


if __name__ == "__main__":
    main()
