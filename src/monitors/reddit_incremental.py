#!/usr/bin/env python3
"""Incremental Reddit scanner — emits NDJSON (one ScanResult per line),
so downstream consumers see matches as they arrive."""

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

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "config", "keywords.json")

REDDIT_SEARCH = "https://www.reddit.com/r/{subreddit}/search.json"

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"

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


def load_config() -> dict:
    with open(CONFIG_PATH) as f:
        return json.load(f)


def search_subreddit(subreddit: str, keyword: str, max_posts: int = 25) -> list[dict]:
    query = urllib.parse.quote(keyword)
    url = f"https://www.reddit.com/r/{subreddit}/search.json?q={query}&sort=new&restrict_sr=on&limit={max_posts}&t=day"
    headers = {"User-Agent": UA}
    req = urllib.request.Request(url, headers=headers)
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read())
                break
        except urllib.error.HTTPError as e:
            if e.code in (429, 503):
                wait = 2 ** attempt * 10
                time.sleep(wait)
                if attempt == 2:
                    return []
            else:
                return []
        except Exception:
            return []
    else:
        return []
    children = data.get("data", {}).get("children", [])
    return [c.get("data", {}) for c in children]


def extract_post_info(post: dict, subreddit: str, keyword: str) -> Optional[ScanResult]:
    title = post.get("title", "")
    selftext = post.get("selftext", "")
    combined_text = f"{title} {selftext}".lower()
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


def run_scan():
    config = load_config()
    subreddits = config.get("subreddits", [])
    keywords = config.get("keywords", [])
    max_posts = config.get("max_posts_per_search", 25)
    seen_ids: set[str] = set()
    total_matches = 0

    for subreddit in subreddits:
        for keyword in keywords:
            posts = search_subreddit(subreddit, keyword, max_posts)
            for post in posts:
                info = extract_post_info(post, subreddit, keyword)
                if info and info.post_id not in seen_ids:
                    seen_ids.add(info.post_id)
                    total_matches += 1
                    # Emit each match as NDJSON
                    print(json.dumps(asdict(info)), flush=True)
            time.sleep(2.1)

    # Summary line on stderr so it doesn't pollute NDJSON output
    import sys
    print(f"[done] {total_matches} unique matches", file=sys.stderr, flush=True)


if __name__ == "__main__":
    run_scan()
