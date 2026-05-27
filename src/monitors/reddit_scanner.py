#!/usr/bin/env python3
"""ReplyRadar — Reddit Keyword Monitor.

Uses Serper.dev (Google search) with site:reddit.com to find posts
matching business/automation keywords across target subreddits.

Usage:
    python reddit_scanner.py                    # full scan
    python reddit_scanner.py --keyword "AI agent" --subreddit SaaS
"""

import json
import os
import time
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Optional
from dataclasses import dataclass, asdict, field
import urllib.request
import urllib.parse
import urllib.error

# ── Config ────────────────────────────────────────────────────
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "config", "keywords.json")
SERPER_KEY = os.environ.get("SERPER_API_KEY", "5ea925348ac9c261d542aea4028ed33142f729b6")
SERPER_URL = "https://google.serper.dev/search"
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "scans")

# ── Data model ────────────────────────────────────────────────

@dataclass
class ScanResult:
    post_id: str
    subreddit: str
    title: str
    author: str
    url: str
    body_snippet: str
    matched_keywords: list[str]
    score: int
    num_comments: int
    created_utc: str
    scan_time: str


# ── Core ──────────────────────────────────────────────────────

def load_config() -> dict:
    with open(CONFIG_PATH) as f:
        return json.load(f)


def search_subreddit(subreddit: str, keyword: str, max_posts: int = 50) -> list[dict]:
    """Search Reddit via Serper.dev for a keyword in a specific subreddit."""
    query = f'site:reddit.com/r/{subreddit} "{keyword}"'
    payload = json.dumps({"q": query, "num": max_posts}).encode()

    req = urllib.request.Request(
        SERPER_URL,
        data=payload,
        headers={
            "X-API-KEY": SERPER_KEY,
            "Content-Type": "application/json",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"[!] Serper HTTP {e.code} for r/{subreddit}: {body[:200]}")
        return []
    except Exception as e:
        print(f"[!] Serper error for r/{subreddit}: {e}")
        return []

    return data.get("organic", [])


def extract_post_info(result: dict, subreddit: str, keyword: str, config: dict) -> Optional[ScanResult]:
    """Parse a Serper result into a ScanResult."""
    title = result.get("title", "")
    url = result.get("link", "")
    snippet = result.get("snippet", "")

    # Extract author from Reddit URL or snippet
    author = "unknown"
    if "/user/" in url:
        parts = url.split("/user/")
        if len(parts) > 1:
            author = parts[1].split("/")[0]

    # Build a stable post ID from URL
    post_id = hashlib.md5(url.encode()).hexdigest()[:12]

    # Score/comments are not directly available from Serper — estimate
    # In production, switch to Reddit JSON API for exact numbers
    score = max(1, len(snippet) // 50)
    num_comments = 0

    return ScanResult(
        post_id=post_id,
        subreddit=subreddit,
        title=title[:200],
        author=author,
        url=url,
        body_snippet=snippet[:500],
        matched_keywords=[keyword],
        score=score,
        num_comments=num_comments,
        created_utc=datetime.now(timezone.utc).isoformat(),
        scan_time=datetime.now(timezone.utc).isoformat(),
    )


def run_scan(config: Optional[dict] = None) -> list[dict]:
    """Run a full scan across all subreddits and keywords. Returns list of ScanResult dicts."""
    if config is None:
        config = load_config()

    subreddits = config.get("subreddits", [])
    keywords = config.get("keywords", [])
    max_posts = config.get("max_posts_per_search", 30)
    results: list[ScanResult] = []
    seen_ids: set[str] = set()

    total = len(subreddits) * len(keywords)
    count = 0
    print(f"[scan] {len(subreddits)} subreddits × {len(keywords)} keywords = {total} queries")

    for subreddit in subreddits:
        for keyword in keywords:
            count += 1
            print(f"  [{count}/{total}] r/{subreddit} + \"{keyword}\"", end=" ", flush=True)

            posts = search_subreddit(subreddit, keyword, max_posts)
            print(f"→ {len(posts)} results", flush=True)

            for post in posts:
                info = extract_post_info(post, subreddit, keyword, config)
                if info and info.post_id not in seen_ids:
                    seen_ids.add(info.post_id)
                    results.append(info)

            # Rate limit: 55 req/min to stay under 60 limit
            if count % 50 == 0:
                time.sleep(2)
            else:
                time.sleep(1.0)

    return [asdict(r) for r in results]


def save_results(results: list[dict]) -> str:
    """Save scan results to a timestamped JSON file."""
    os.makedirs(DATA_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"scan_{timestamp}.json"
    filepath = os.path.join(DATA_DIR, filename)

    with open(filepath, "w") as f:
        json.dump(
            {
                "scan_time": timestamp,
                "total_posts": len(results),
                "results": results,
            },
            f,
            indent=2,
        )

    print(f"[✓] Saved {len(results)} results to {filepath}")
    return filepath


# ── CLI ───────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="ReplyRadar Reddit Scanner")
    parser.add_argument("--keyword", help="Single keyword to search")
    parser.add_argument("--subreddit", help="Single subreddit to search")
    parser.add_argument("--no-save", action="store_true")
    args = parser.parse_args()

    if args.keyword and args.subreddit:
        config = load_config()
        posts = search_subreddit(args.subreddit, args.keyword)
        results = []
        seen = set()
        for p in posts:
            info = extract_post_info(p, args.subreddit, args.keyword, config)
            if info and info.post_id not in seen:
                seen.add(info.post_id)
                results.append(asdict(info))
        print(json.dumps(results, indent=2))
    else:
        results = run_scan()
        if not args.no_save:
            save_results(results)
        else:
            print(json.dumps(results, indent=2))
