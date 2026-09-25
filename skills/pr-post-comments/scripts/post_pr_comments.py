#!/usr/bin/env python3
"""Post PR comments and review-thread replies through gh, one at a time, paced.

Every comment the pr-* skills post goes through here, so pacing and the voice
lint can't be skipped. Run it in the background; --check lints the file and
prints the schedule without posting.

    post_pr_comments.py <owner/repo> <pr> <comments.json> [--commit SHA] [--check]

The JSON file is a list, one object per comment, posted in order:

    {"in_reply_to": 3992873113, "body": "..."}             reply on a review thread
    {"path": "app/a.py", "line": 12, "body": "[o] ..."}      new inline comment
    {"path": "app/a.py", "start_line": 9, "line": 12, ...}   inline over a span
    {"body": "..."}                                          PR-level comment

Inline comments need --commit and an [r], [o], [f] or [c] tag. Every body is
linted against the voice rules in pr-post-comments/SKILL.md first, and one
failing body stops the whole batch before anything is posted.

The wait before a comment models the time spent writing it
(pr-post-comments, Step 6): 15-35 s of reading plus a second per six
characters, swung +/-25% and capped. It counts from the last post of any run,
kept in ~/.claude/state, and a lock there keeps two runs from interleaving.
A failed post is reported and does not stop the rest.
"""

from __future__ import annotations

import argparse
import contextlib
import fcntl
import json
import os
import random
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

STATE_DIR = Path(os.environ.get("PR_COMMENTS_STATE_DIR") or Path.home() / ".claude" / "state")
LAST_POST_FILE = "pr-comments-last-post"
LOCK_FILE = "pr-comments.lock"
# Background shells run with a thin PATH, so fall back to the Homebrew binary.
GH = os.environ.get("PR_COMMENTS_GH") or shutil.which("gh") or "/opt/homebrew/bin/gh"

# pr-post-comments, Step 6.
READ_SECONDS = (15.0, 35.0)
CHARS_PER_SECOND = 6.0
WRITE_SWING = (0.75, 1.25)
WRITE_CAP_SECONDS = 225.0

TAG_RE = re.compile(r"^\[[rofc]\]\s")
CODE_RE = re.compile(r"```.*?```|`[^`\n]*`", re.S)
DASH_RE = re.compile("[–—]")
OPENER_RE = re.compile(r"(?:\A\s*|[.!?]\s+|\n\s*)(So|Okay|Well|Yeah)(?=[\s,.!?]|\Z)", re.I)
BANNED_RE = re.compile(
    r"\b(?:furthermore|moreover|additionally|consequently|utilize|facilitate|robust"
    r"|seamless|synergy|deep dive|circle back|touch base|nuanced|that being said|that said"
    r"|it'?s important to note|it is important to note|in terms of|I'd like to highlight"
    r"|this is where it gets interesting|I (?:checked|verified|double-checked))\b",
    re.I,
)


class PostError(Exception):
    """gh refused or failed one post."""


@dataclass(frozen=True)
class Comment:
    label: str
    endpoint: str
    payload: dict
    body: str


def lint(body: str, *, needs_tag: bool) -> list:
    """What a body breaks of the voice rules; code spans are exempt."""
    problems = []
    if needs_tag and not TAG_RE.match(body):
        problems.append("inline comment must open with [r], [o], [f] or [c]")
    prose = CODE_RE.sub(" ", body)
    if DASH_RE.search(prose):
        problems.append("em or en dash, use a regular dash")
    for match in OPENER_RE.finditer(prose):
        problems.append(f"sentence opens with {match.group(1)!r}")
    for match in BANNED_RE.finditer(prose):
        problems.append(f"banned phrase {match.group(0)!r}")
    return problems


def parse_entries(repo: str, pr: int, raw: object, commit) -> tuple:
    """The comments to post and every problem found, entry by entry."""
    if not isinstance(raw, list) or not raw:
        return [], ["the file must hold a non-empty JSON list"]
    comments, problems = [], []
    for number, entry in enumerate(raw, start=1):
        where = f"entry {number}"
        body = entry.get("body") if isinstance(entry, dict) else None
        if not isinstance(body, str) or not body.strip():
            problems.append(f"{where}: missing body")
            continue
        if "in_reply_to" in entry:
            target = str(entry["in_reply_to"])
            if "path" in entry or not target.isdigit():
                problems.append(f"{where}: a reply takes a numeric in_reply_to and no path")
                continue
            comment = Comment(
                f"reply to {target}", f"repos/{repo}/pulls/{pr}/comments/{target}/replies",
                {"body": body}, body,
            )
        elif "path" in entry:
            line, start = entry.get("line"), entry.get("start_line")
            if not commit or not isinstance(line, int) or (start is not None and not (isinstance(start, int) and start < line)):
                problems.append(f"{where}: inline needs --commit, an int line, and start_line below it")
                continue
            payload = {"commit_id": commit, "path": entry["path"], "line": line, "side": "RIGHT", "body": body}
            if start is not None:
                payload.update(start_line=start, start_side="RIGHT")
            comment = Comment(f"{entry['path']}:{line}", f"repos/{repo}/pulls/{pr}/comments", payload, body)
        else:
            comment = Comment("PR comment", f"repos/{repo}/issues/{pr}/comments", {"body": body}, body)
        problems.extend(f"{where} ({comment.label}): {p}" for p in lint(body, needs_tag="path" in entry))
        comments.append(comment)
    return comments, problems


def delay_for(length: int, rng: random.Random) -> float:
    """Seconds to wait before a comment of this many characters goes up."""
    writing = min(length / CHARS_PER_SECOND * rng.uniform(*WRITE_SWING), WRITE_CAP_SECONDS)
    return rng.uniform(*READ_SECONDS) + writing


def read_last_post(path: Path) -> float:
    try:
        return float(path.read_text().strip())
    except (OSError, ValueError):
        return 0.0


def gh_post(comment: Comment) -> str:
    result = subprocess.run(
        [GH, "api", "--method", "POST", comment.endpoint, "--input", "-", "--jq", ".html_url"],
        input=json.dumps(comment.payload), capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise PostError(result.stderr.strip() or f"gh exited {result.returncode}")
    return result.stdout.strip()


def run(comments: list, *, post, clock, sleep, rng: random.Random, last_post: Path) -> list:
    """Post each comment after its writing delay; return the labels that failed."""
    failures, last, total = [], read_last_post(last_post), len(comments)
    for number, comment in enumerate(comments, start=1):
        wait = last + delay_for(len(comment.body), rng) - clock()
        if wait > 0:
            print(f"[{number}/{total}] waiting {wait:.0f}s for {len(comment.body)} chars", flush=True)
            sleep(wait)
        try:
            url = post(comment)
        except PostError as error:
            print(f"[{number}/{total}] {comment.label} FAILED: {error}", flush=True)
            failures.append(comment.label)
            continue
        last = clock()
        last_post.write_text(f"{last}\n")
        print(f"[{number}/{total}] {comment.label} -> {url}", flush=True)
    return failures


@contextlib.contextmanager
def exclusive(lock_path: Path):
    with open(lock_path, "w") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print("another paced run is posting; waiting for it to finish", flush=True)
            fcntl.flock(handle, fcntl.LOCK_EX)
        yield


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("repo")
    parser.add_argument("pr", type=int)
    parser.add_argument("comments")
    parser.add_argument("--commit")
    parser.add_argument("--check", action="store_true", help="lint and show the schedule, post nothing")
    opts = parser.parse_args(argv)

    with open(opts.comments) as handle:
        comments, problems = parse_entries(opts.repo, opts.pr, json.load(handle), opts.commit)
    if problems:
        print("nothing posted:", *problems, sep="\n  ", file=sys.stderr)
        return 2

    STATE_DIR.mkdir(parents=True, exist_ok=True)
    rng = random.Random()
    if opts.check:
        waits = [delay_for(len(c.body), rng) for c in comments[1:]]
        print(f"ok: {len(comments)} comments, about {sum(waits) / 60:.0f} min of waits after the first")
        return 0
    with exclusive(STATE_DIR / LOCK_FILE):
        failures = run(
            comments, post=gh_post, clock=time.time, sleep=time.sleep, rng=rng,
            last_post=STATE_DIR / LAST_POST_FILE,
        )
    if failures:
        print(f"failed: {', '.join(failures)}", flush=True)
        return 1
    print(f"posted {len(comments)} comments", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
