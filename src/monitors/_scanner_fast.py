#!/usr/bin/env python3
"""ReplyRadar — Reddit Keyword Monitor.

Uses Reddit's public JSON API (no auth required) to search subreddits
for posts matching business/automation keywords.

Usage:
    python reddit_scanner.py                    # full scan
    python reddit_scanner.py --keyword "AI agent" --subreddit SaaS
"""

import json
import os
import time
import hashlib
from datetime import datetime, timezone
from typing import Optional
from dataclasses import dataclass, asdict
import urllib.request
import urllib.parse
import urllib.error

# ── Config ────────────────────────────────────────────────────
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "config", "keywords.json")
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "scans")
os.makedirs(DATA_DIR, exist_ok=True)

# Reddit JSON API — add .json to any URL
REDDIT_SEARCH = "https://www.reddit.com/r/{subreddit}/search.json"


# ── Data model ────────────────────────────────────────────────

@dataclass
class ScanResult:
    post_id: str
    subreddit: str
    title: str
    author: str
    url: str
    body: str
    matched_keywords: list[str]
    score: int
    num_comments: int
    created_utc: float
    scan_time: str


# ── Core ──────────────────────────────────────────────────────

def load_config() -> dict:
    with open(CONFIG_PATH) as f:
        return json.load(f)


def search_subreddit(subreddit: str, keyword: str, max_posts: int = 25) -> list[dict]:
    """Search Reddit for a keyword in a specific subreddit using the public JSON API."""
    query = urllib.parse.quote(keyword)
    url = f"https://www.reddit.com/r/{subreddit}/search.json?q={query}&sort=new&restrict_sr=on&limit={max_posts}&t=day"

    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    }

    req = urllib.request.Request(url, headers=headers)

    # Retry with backoff on 429/503
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read())
                break
        except urllib.error.HTTPError as e:
            body = e.read().decode()
            if e.code in (429, 503):
                wait = 2 ** attempt * 5
                print(f"[429] r/{subreddit} + \"{keyword}\" — retrying in {wait}s (attempt {attempt+1}/4)")
                time.sleep(wait)
                if attempt == 3:
                    print(f"[!] Reddit HTTP {e.code} for r/{subreddit}: {body[:200]}")
                    return []
            else:
                print(f"[!] Reddit HTTP {e.code} for r/{subreddit}: {body[:200]}")
                return []
        except Exception as e:
            print(f"[!] Reddit error for r/{subreddit}: {e}")
            return []
    else:
        return []

    children = data.get("data", {}).get("children", [])
    return [c.get("data", {}) for c in children]


def extract_post_info(post: dict, subreddit: str, keyword: str) -> Optional[ScanResult]:
    """Parse a Reddit post object into a ScanResult."""
    title = post.get("title", "")
    selftext = post.get("selftext", "")
    combined_text = f"{title} {selftext}".lower()

    # Check if keyword actually appears
    if keyword.lower() not in combined_text:
        return None

    post_id = post.get("id", hashlib.md5((title + subreddit).encode()).hexdigest()[:12])

    return ScanResult(
        post_id=post_id,
        subreddit=subreddit,
        title=title[:200],
        author=post.get("author", "unknown"),
        url=f"https://reddit.com{post.get('permalink', '')}",
        body=selftext[:800] if selftext else "",
        matched_keywords=[keyword],
        score=post.get("score", 0),
        num_comments=post.get("num_comments", 0),
        created_utc=post.get("created_utc", 0),
        scan_time=datetime.now(timezone.utc).isoformat(),
    )


def run_scan(config: Optional[dict] = None) -> list[dict]:
    """Run a full scan across all subreddits and keywords."""
    if config is None:
        config = load_config()

    subreddits = config.get("subreddits", [])
    keywords = config.get("keywords", [])
    max_posts = config.get("max_posts_per_search", 25)
    no_save = config.get("no_save", False)
    results: list[ScanResult] = []
    seen_ids: set[str] = set()

    total = len(subreddits) * len(keywords)
    count = 0
    if not no_save:
        print(f"[scan] {len(subreddits)} subreddits × {len(keywords)} keywords = {total} queries")

    for subreddit in subreddits:
        for keyword in keywords:
            count += 1
            if not no_save:
                print(f"  [{count}/{total}] r/{subreddit} + \"{keyword}\"", end=" ", flush=True)

            posts = search_subreddit(subreddit, keyword, max_posts)
            matched = 0
            for post in posts:
                info = extract_post_info(post, subreddit, keyword)
                if info and info.post_id not in seen_ids:
                    seen_ids.add(info.post_id)
                    results.append(info)
                    matched += 1
            if not no_save:
                print(f"→ {matched} matches", flush=True)

            # Rate limit: Reddit allows ~60 req/min for JSON API
            time.sleep(0.5)

    return [asdict(r) for r in results]


def save_results(results: list[dict]) -> str:
    """Save scan results to a timestamped JSON file."""
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
    parser.add_argument("--no-save", action="store_true", help="Print to stdout only")
    parser.add_argument("--max-posts", type=int, default=25, help="Max posts per query")
    args = parser.parse_args()

    if args.keyword and args.subreddit:
        config = load_config()
        posts = search_subreddit(args.subreddit, args.keyword, args.max_posts)
        results = []
        seen = set()
        for p in posts:
            info = extract_post_info(p, args.subreddit, args.keyword)
            if info and info.post_id not in seen:
                seen.add(info.post_id)
                results.append(asdict(info))
        print(json.dumps(results, indent=2))
    else:
        config = load_config()
        if args.no_save:
            config["no_save"] = True
        results = run_scan(config)
        if args.no_save:
            print(json.dumps(results, indent=2))
        elif results:
            save_results(results)
        else:
            print("[!] No results found across all queries.")
