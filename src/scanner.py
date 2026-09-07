from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import REPORTS_DIR
from gemini_client import GeminiClient
from github_client import GitHubClient
from taxonomy import normalize_topic

PLACEHOLDER_PATTERN = re.compile(
    r"<your[_-]?username>|your[_-]?username", re.IGNORECASE
)


def _gather_repo_state(client: GitHubClient, owner: str, repo: dict[str, Any]) -> dict[str, Any]:
    name = repo["name"]
    topics = client.get_topics(owner, name)
    readme = client.get_file(owner, name, "README.md")
    license_info = client.get_license(owner, name)
    releases = client.list_releases(owner, name)
    environments = client.list_environments(owner, name)

    return {
        "name": name,
        "description": repo.get("description"),
        "topics": topics,
        "language": repo.get("language"),
        "clone_url": repo.get("clone_url"),
        "html_url": repo.get("html_url"),
        "default_branch": repo.get("default_branch"),
        "readme": readme["content"] if readme else None,
        "readme_sha": readme["sha"] if readme else None,
        "license": license_info["license"]["spdx_id"] if license_info else None,
        "releases": [{"id": r["id"], "tag_name": r["tag_name"], "name": r["name"]} for r in releases],
        "environments": [e["name"] for e in environments],
    }


def _has_placeholder(readme: str | None) -> bool:
    return bool(readme and PLACEHOLDER_PATTERN.search(readme))


def _diff_entry(state: dict[str, Any], proposal: dict[str, Any]) -> dict[str, Any]:
    old_topics = sorted(state["topics"])
    normalized_new = [normalize_topic(t) for t in proposal["topics"]]
    new_topics = sorted(dict.fromkeys(t for t in normalized_new if t))
    description_changed = (state["description"] or "").strip() != proposal["description"].strip()
    topics_changed = old_topics != new_topics
    readme_changed = (state["readme"] or "") != proposal["readme_markdown"]
    needs_license = state["license"] is None

    no_change = not (description_changed or topics_changed or readme_changed or needs_license)

    return {
        "repo": state["name"],
        "html_url": state["html_url"],
        "no_change": no_change,
        "category": proposal["category"],
        "description": {
            "old": state["description"],
            "new": proposal["description"],
            "changed": description_changed,
        },
        "topics": {
            "old": old_topics,
            "new": new_topics,
            "changed": topics_changed,
        },
        "readme": {
            "changed": readme_changed,
            "had_placeholder": _has_placeholder(state["readme"]),
            "sha": state["readme_sha"],
            "new_content": proposal["readme_markdown"],
        },
        "license": {
            "missing": needs_license,
            "current": state["license"],
        },
        "releases": state["releases"],
        "environments": state["environments"],
        "notes": proposal.get("notes", ""),
    }


def run_dry_run(
    github: GitHubClient,
    gemini: GeminiClient,
    only: str | None = None,
) -> list[dict[str, Any]]:
    owner = github.get_authenticated_user()
    repos = github.list_repos(exclude_forks=True)
    if only:
        repos = [r for r in repos if r["name"] == only]
        if not repos:
            raise SystemExit(f"No repo named '{only}' found for {owner}.")

    results: list[dict[str, Any]] = []

    for repo in repos:
        print(f"Scanning {owner}/{repo['name']}...")
        state = _gather_repo_state(github, owner, repo)
        proposal = gemini.generate_repo_metadata(state)
        results.append(_diff_entry(state, proposal))

    REPORTS_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    changes_path = REPORTS_DIR / "changes.json"
    report_path = REPORTS_DIR / f"report_{timestamp}.md"

    changes_path.write_text(
        json.dumps({"owner": owner, "generated_at": timestamp, "repos": results}, indent=2),
        encoding="utf-8",
    )
    report_path.write_text(_render_report(owner, results), encoding="utf-8")

    print(f"\nWrote {changes_path}")
    print(f"Wrote {report_path}")
    return results


def _render_report(owner: str, results: list[dict[str, Any]]) -> str:
    lines = [f"# Dry-run report for {owner}", ""]
    changed = [r for r in results if not r["no_change"]]
    unchanged = [r for r in results if r["no_change"]]
    lines.append(f"{len(changed)} repo(s) with proposed changes, {len(unchanged)} already standard.\n")

    for r in changed:
        lines.append(f"## {r['repo']} ({r['category']}) — {r['html_url']}")
        if r["description"]["changed"]:
            lines.append(f"- description: `{r['description']['old']}` -> `{r['description']['new']}`")
        if r["topics"]["changed"]:
            lines.append(f"- topics: {r['topics']['old']} -> {r['topics']['new']}")
        if r["readme"]["changed"]:
            flag = " (had placeholder username)" if r["readme"]["had_placeholder"] else ""
            lines.append(f"- README: rewritten{flag}")
        if r["license"]["missing"]:
            lines.append("- LICENSE: missing, will add MIT")
        if r["releases"]:
            names = ", ".join(f"{rel['tag_name']}" for rel in r["releases"])
            lines.append(f"- existing releases: {names} (not touched by --apply; use --delete-release)")
        if r["environments"]:
            lines.append(
                f"- existing environments: {r['environments']} "
                f"(not touched by --apply; use --fix-environments)"
            )
        if r["notes"]:
            lines.append(f"- notes: {r['notes']}")
        lines.append("")

    if unchanged:
        lines.append("## Already standard, no changes proposed")
        for r in unchanged:
            lines.append(f"- {r['repo']}")

    return "\n".join(lines)
