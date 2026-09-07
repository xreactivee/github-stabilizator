from __future__ import annotations

import base64
import time
from typing import Any

import requests

API_BASE = "https://api.github.com"


class GitHubError(RuntimeError):
    pass


class GitHubClient:
    def __init__(self, token: str):
        self._session = requests.Session()
        self._session.headers.update(
            {
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            }
        )

    def _request(self, method: str, path: str, **kwargs) -> requests.Response:
        url = path if path.startswith("http") else f"{API_BASE}{path}"
        for attempt in range(5):
            resp = self._session.request(method, url, **kwargs)
            if resp.status_code == 403 and "rate limit" in resp.text.lower():
                reset = int(resp.headers.get("X-RateLimit-Reset", time.time() + 30))
                wait = max(reset - time.time(), 1)
                time.sleep(min(wait, 60))
                continue
            return resp
        raise GitHubError(f"Rate limited repeatedly on {method} {url}")

    def _get(self, path: str, **kwargs) -> requests.Response:
        return self._request("GET", path, **kwargs)

    def get_authenticated_user(self) -> str:
        resp = self._get("/user")
        if resp.status_code != 200:
            raise GitHubError(f"GET /user failed: {resp.status_code} {resp.text}")
        return resp.json()["login"]

    def list_repos(self, exclude_forks: bool = True) -> list[dict[str, Any]]:
        repos: list[dict[str, Any]] = []
        page = 1
        while True:
            resp = self._get(
                "/user/repos",
                params={
                    "visibility": "all",
                    "affiliation": "owner",
                    "per_page": 100,
                    "page": page,
                },
            )
            if resp.status_code != 200:
                raise GitHubError(f"GET /user/repos failed: {resp.status_code} {resp.text}")
            batch = resp.json()
            if not batch:
                break
            repos.extend(batch)
            page += 1
        if exclude_forks:
            repos = [r for r in repos if not r.get("fork")]
        return repos

    def update_repo(self, owner: str, repo: str, **fields) -> None:
        resp = self._request("PATCH", f"/repos/{owner}/{repo}", json=fields)
        if resp.status_code != 200:
            raise GitHubError(f"PATCH /repos/{owner}/{repo} failed: {resp.status_code} {resp.text}")

    def get_topics(self, owner: str, repo: str) -> list[str]:
        resp = self._get(f"/repos/{owner}/{repo}/topics")
        if resp.status_code != 200:
            raise GitHubError(f"GET topics failed: {resp.status_code} {resp.text}")
        return resp.json().get("names", [])

    def set_topics(self, owner: str, repo: str, topics: list[str]) -> None:
        resp = self._request("PUT", f"/repos/{owner}/{repo}/topics", json={"names": topics})
        if resp.status_code != 200:
            raise GitHubError(f"PUT topics failed: {resp.status_code} {resp.text}")

    def get_file(self, owner: str, repo: str, path: str) -> dict[str, Any] | None:
        resp = self._get(f"/repos/{owner}/{repo}/contents/{path}")
        if resp.status_code == 404:
            return None
        if resp.status_code != 200:
            raise GitHubError(f"GET contents/{path} failed: {resp.status_code} {resp.text}")
        data = resp.json()
        if isinstance(data, list):
            return None
        content = base64.b64decode(data["content"]).decode("utf-8", errors="replace")
        return {"sha": data["sha"], "content": content}

    def put_file(
        self,
        owner: str,
        repo: str,
        path: str,
        content: str,
        message: str,
        sha: str | None = None,
    ) -> None:
        body = {
            "message": message,
            "content": base64.b64encode(content.encode("utf-8")).decode("ascii"),
        }
        if sha:
            body["sha"] = sha
        resp = self._request("PUT", f"/repos/{owner}/{repo}/contents/{path}", json=body)
        if resp.status_code not in (200, 201):
            raise GitHubError(f"PUT contents/{path} failed: {resp.status_code} {resp.text}")

    def get_license(self, owner: str, repo: str) -> dict[str, Any] | None:
        resp = self._get(f"/repos/{owner}/{repo}/license")
        if resp.status_code == 404:
            return None
        if resp.status_code != 200:
            raise GitHubError(f"GET license failed: {resp.status_code} {resp.text}")
        return resp.json()

    def get_license_template(self, key: str) -> dict[str, Any]:
        resp = self._get(f"/licenses/{key}")
        if resp.status_code != 200:
            raise GitHubError(f"GET /licenses/{key} failed: {resp.status_code} {resp.text}")
        return resp.json()

    def list_releases(self, owner: str, repo: str) -> list[dict[str, Any]]:
        resp = self._get(f"/repos/{owner}/{repo}/releases", params={"per_page": 100})
        if resp.status_code != 200:
            raise GitHubError(f"GET releases failed: {resp.status_code} {resp.text}")
        return resp.json()

    def delete_release(self, owner: str, repo: str, release_id: int) -> None:
        resp = self._request("DELETE", f"/repos/{owner}/{repo}/releases/{release_id}")
        if resp.status_code != 204:
            raise GitHubError(f"DELETE release failed: {resp.status_code} {resp.text}")

    def list_environments(self, owner: str, repo: str) -> list[dict[str, Any]]:
        resp = self._get(f"/repos/{owner}/{repo}/environments")
        if resp.status_code == 404:
            return []
        if resp.status_code != 200:
            raise GitHubError(f"GET environments failed: {resp.status_code} {resp.text}")
        return resp.json().get("environments", [])

    def get_environment(self, owner: str, repo: str, name: str) -> dict[str, Any] | None:
        resp = self._get(f"/repos/{owner}/{repo}/environments/{name}")
        if resp.status_code == 404:
            return None
        if resp.status_code != 200:
            raise GitHubError(f"GET environment failed: {resp.status_code} {resp.text}")
        return resp.json()

    def create_or_update_environment(
        self, owner: str, repo: str, name: str, body: dict[str, Any] | None = None
    ) -> None:
        resp = self._request(
            "PUT", f"/repos/{owner}/{repo}/environments/{name}", json=body or {}
        )
        if resp.status_code not in (200, 201):
            raise GitHubError(f"PUT environment failed: {resp.status_code} {resp.text}")

    def delete_environment(self, owner: str, repo: str, name: str) -> None:
        resp = self._request("DELETE", f"/repos/{owner}/{repo}/environments/{name}")
        if resp.status_code != 204:
            raise GitHubError(f"DELETE environment failed: {resp.status_code} {resp.text}")
