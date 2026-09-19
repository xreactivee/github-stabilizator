from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import load_selected_model, load_settings
from gemini_client import GeminiClient
from github_client import GitHubClient, GitHubError
from scanner import run_dry_run


def parse_repo_name(url: str) -> str:
    name = url.strip().rstrip("/")
    if name.endswith(".git"):
        name = name[:-4]
    return name.split("/")[-1]


def apply_results(github: GitHubClient, owner: str, results: list[dict[str, Any]]) -> None:
    for entry in results:
        if entry["no_change"]:
            continue
        name = entry["repo"]
        print(f"\n== {owner}/{name} ==")

        if entry["description"]["changed"]:
            github.update_repo(owner, name, description=entry["description"]["new"])
            print(f"  description -> {entry['description']['new']}")

        if entry["topics"]["changed"]:
            github.set_topics(owner, name, entry["topics"]["new"])
            print(f"  topics -> {entry['topics']['new']}")

        if entry["readme"]["changed"]:
            github.put_file(
                owner,
                name,
                "README.md",
                entry["readme"]["new_content"],
                message="chore: standardize README",
                sha=entry["readme"]["sha"],
            )
            print("  README updated")

        if entry["license"]["missing"]:
            template = github.get_license_template("mit")
            license_text = template["body"].replace("[year]", str(date.today().year)).replace(
                "[fullname]", owner
            )
            github.put_file(
                owner, name, "LICENSE", license_text, message="chore: add MIT license"
            )
            print("  LICENSE added")

        print("  done")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--all", action="store_true", help="scan every repo, write a report, and push all fixes")
    parser.add_argument("--one", metavar="REPO_URL", help="scan a single repo by URL and push all fixes")
    args = parser.parse_args()

    if not args.all and not args.one:
        raise SystemExit("Pass --all or --one <repo_url>.")

    settings = load_settings()
    github = GitHubClient(settings.github_token)
    model = load_selected_model()
    gemini = GeminiClient(settings.gemini_api_key, model)
    only = parse_repo_name(args.one) if args.one else None

    try:
        results = run_dry_run(github, gemini, only)
        owner = github.get_authenticated_user()
        apply_results(github, owner, results)
    except GitHubError as exc:
        raise SystemExit(f"GitHub API error: {exc}")


if __name__ == "__main__":
    main()
