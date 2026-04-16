#!/usr/bin/env python3
"""
Generates _data/page_metadata.json with git metadata for every Markdown file.
Uses the GitHub API when GITHUB_TOKEN is set, otherwise falls back to git log.
Source .md files are never modified.
"""
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

REPO = "codeday/docs"
TOKEN = os.environ.get("GITHUB_TOKEN")


def github_commits(file_path: str):
    if not TOKEN:
        return None
    url = f"https://api.github.com/repos/{REPO}/commits?path={urllib.parse.quote(file_path)}&per_page=100"
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Accept": "application/vnd.github.v3+json",
        },
    )
    try:
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        print(f"  GitHub API {e.code} for {file_path}", file=sys.stderr)
        return None


def get_metadata(file_path: str) -> dict:
    commits = github_commits(file_path)
    if commits:
        last = commits[0]["commit"]["committer"]["date"].split("T")[0]
        latest = commits[0]
        last_login = (latest.get("author") or {}).get("login")
        last_name = latest["commit"]["author"]["name"]

        seen, authors = set(), []
        for c in commits:
            login = (c.get("author") or {}).get("login")
            name = c["commit"]["author"]["name"]
            key = login or name
            if key not in seen:
                seen.add(key)
                authors.append({"login": login, "name": name})

        return {
            "last_modified_date": last,
            "last_modified_by": {"login": last_login, "name": last_name},
            "authors": authors,
        }

    # Fallback: local git log
    last_commit = subprocess.run(
        ["git", "log", "-1", "--format=%ai\t%an", "--", file_path],
        capture_output=True, text=True,
    ).stdout.strip()
    last_date, last_author_name = (last_commit.split("\t") + ["", ""])[:2]
    last_date = last_date.split(" ")[0] or None

    authors_out = subprocess.run(
        ["git", "log", "--format=%an", "--", file_path],
        capture_output=True, text=True,
    ).stdout.strip().split("\n")
    seen, authors = set(), []
    for name in authors_out:
        if name and name not in seen:
            seen.add(name)
            authors.append({"login": None, "name": name})

    return {
        "last_modified_date": last_date,
        "last_modified_by": {"login": None, "name": last_author_name} if last_author_name else None,
        "authors": authors,
    }


# ---- main ---------------------------------------------------------------
source = Path(__file__).parent.parent.parent
md_files = [
    p for p in source.rglob("*.md")
    if not any(part.startswith(".") or part in ("_site", "node_modules") for part in p.parts)
]

metadata = {}
for filepath in sorted(md_files):
    rel = str(filepath.relative_to(source))
    print(f"Processing {rel} …", end=" ", flush=True)
    metadata[rel] = get_metadata(rel)
    print("done")

out = source / "_data" / "page_metadata.json"
out.parent.mkdir(exist_ok=True)
out.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
print(f"\nWrote {out.relative_to(source)} ({len(metadata)} entries)")
