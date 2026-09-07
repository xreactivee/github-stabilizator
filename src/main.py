from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import REPORTS_DIR, load_selected_model, load_settings
from gemini_client import GeminiClient
from github_client import GitHubClient, GitHubError
from scanner import run_dry_run

CANONICAL_ENV_NAMES = {
    "production": "Production",
    "prod": "Production",
    "preview": "Preview",
    "development": "Development",
    "dev": "Development",
    "staging": "Staging",
}


def confirm(prompt: str, auto_yes: bool) -> bool:
    if auto_yes:
        return True
    answer = input(f"{prompt} [y/N] ").strip().lower()
    return answer == "y"


def cmd_apply(github: GitHubClient, only: str | None, auto_yes: bool) -> None:
    changes_path = REPORTS_DIR / "changes.json"
    if not changes_path.exists():
        raise SystemExit("No reports/changes.json found. Run --dry-run first.")
    data = json.loads(changes_path.read_text(encoding="utf-8"))
    owner = data["owner"]
    repos = data["repos"]
    if only:
        repos = [r for r in repos if r["repo"] == only]

    for entry in repos:
        if entry["no_change"]:
            continue
        name = entry["repo"]
        print(f"\n== {owner}/{name} ==")
        if entry["description"]["changed"]:
            print(f"  description -> {entry['description']['new']}")
        if entry["topics"]["changed"]:
            print(f"  topics -> {entry['topics']['new']}")
        if entry["readme"]["changed"]:
            print("  README will be rewritten")
        if entry["license"]["missing"]:
            print("  LICENSE (MIT) will be added")

        if not confirm(f"Apply changes to {owner}/{name}?", auto_yes):
            print("  skipped")
            continue

        if entry["description"]["changed"] or entry["topics"]["changed"]:
            fields: dict[str, Any] = {}
            if entry["description"]["changed"]:
                fields["description"] = entry["description"]["new"]
            if fields:
                github.update_repo(owner, name, **fields)
            if entry["topics"]["changed"]:
                github.set_topics(owner, name, entry["topics"]["new"])

        if entry["readme"]["changed"]:
            github.put_file(
                owner,
                name,
                "README.md",
                entry["readme"]["new_content"],
                message="chore: standardize README",
                sha=entry["readme"]["sha"],
            )

        if entry["license"]["missing"]:
            template = github.get_license_template("mit")
            license_text = template["body"].replace("[year]", str(date.today().year)).replace(
                "[fullname]", owner
            )
            github.put_file(
                owner, name, "LICENSE", license_text, message="chore: add MIT license"
            )

        print("  done")


def cmd_delete_release(github: GitHubClient, repo: str, tag: str) -> None:
    owner = github.get_authenticated_user()
    releases = github.list_releases(owner, repo)
    match = next((r for r in releases if r["tag_name"] == tag), None)
    if not match:
        raise SystemExit(f"No release with tag '{tag}' found in {owner}/{repo}.")
    print(f"About to delete release '{match['name'] or match['tag_name']}' ({match['tag_name']}) "
          f"from {owner}/{repo}. This cannot be undone.")
    if input("Type the tag name again to confirm: ").strip() != tag:
        raise SystemExit("Confirmation did not match, aborting.")
    github.delete_release(owner, repo, match["id"])
    print("Deleted.")


def cmd_fix_environments(github: GitHubClient, only: str | None, auto_yes: bool) -> None:
    owner = github.get_authenticated_user()
    repos = github.list_repos(exclude_forks=True)
    if only:
        repos = [r for r in repos if r["name"] == only]

    for repo in repos:
        name = repo["name"]
        environments = github.list_environments(owner, name)
        if not environments:
            continue
        for env in environments:
            old_name = env["name"]
            canonical = CANONICAL_ENV_NAMES.get(old_name.strip().lower())
            if not canonical or canonical == old_name:
                continue
            print(f"\n{owner}/{name}: environment '{old_name}' -> '{canonical}'")
            print("  Note: GitHub cannot rename environments in place. This creates a new")
            print("  environment with the standardized name (copying protection rules) and")
            print("  deletes the old one. Past entries in the Deployments tab under the old")
            print("  name are not retroactively renamed.")
            if not confirm(f"Recreate '{old_name}' as '{canonical}' for {owner}/{name}?", auto_yes):
                print("  skipped")
                continue

            details = github.get_environment(owner, name, old_name) or {}
            body: dict[str, Any] = {}
            protection_rules = details.get("protection_rules", [])
            reviewers = [
                {"type": r["type"], "id": r["reviewer"]["id"]}
                for rule in protection_rules
                if rule.get("type") == "required_reviewers"
                for r in rule.get("reviewers", [])
            ]
            if reviewers:
                body["reviewers"] = reviewers
            wait_timer_rule = next(
                (r for r in protection_rules if r.get("type") == "wait_timer"), None
            )
            if wait_timer_rule:
                body["wait_timer"] = wait_timer_rule.get("wait_timer", 0)
            if details.get("deployment_branch_policy"):
                body["deployment_branch_policy"] = details["deployment_branch_policy"]

            github.create_or_update_environment(owner, name, canonical, body)
            github.delete_environment(owner, name, old_name)
            print("  done")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true", help="scan repos and write a report (default action)")
    parser.add_argument("--apply", action="store_true", help="apply changes from reports/changes.json")
    parser.add_argument("--only", metavar="REPO", help="restrict to a single repo name")
    parser.add_argument("--yes", action="store_true", help="skip per-repo confirmation prompts")
    parser.add_argument("--delete-release", nargs=2, metavar=("REPO", "TAG"), help="delete one release")
    parser.add_argument("--fix-environments", action="store_true", help="standardize environment names")
    args = parser.parse_args()

    settings = load_settings()
    github = GitHubClient(settings.github_token)

    try:
        if args.delete_release:
            repo, tag = args.delete_release
            cmd_delete_release(github, repo, tag)
        elif args.fix_environments:
            cmd_fix_environments(github, args.only, args.yes)
        elif args.apply:
            cmd_apply(github, args.only, args.yes)
        else:
            model = load_selected_model()
            gemini = GeminiClient(settings.gemini_api_key, model)
            run_dry_run(github, gemini, args.only)
    except GitHubError as exc:
        raise SystemExit(f"GitHub API error: {exc}")


if __name__ == "__main__":
    main()
