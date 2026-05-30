#!/usr/bin/env python3
"""Run full Reddit scan and save results to timestamped JSON file."""

import json
import os
import sys
import time
import hashlib
from datetime import datetime, timezone
from typing import Optional
from dataclasses import dataclass, asdict
import urllib.request
import urllib.parse
import urllib.error

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(SCRIPT_DIR, "..", "..", "config", "keywords.json")
DATA_DIR = os.path.join(SCRIPT_DIR, "..", "..", "data", "scans")
os.makedirs(DATA_DIR, exist_ok=True)

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
                print(f"  [429] r/{subreddit} + '{keyword}' — retrying in {wait}s", file=sys.stderr)
                time.sleep(wait)
                if attempt == 2:
                    print(f"  [!] Giving up on r/{subreddit} + '{keyword}'", file=sys.stderr)
                    return []
            else:
                print(f"  [!] HTTP {e.code} for r/{subreddit} + '{keyword}'", file=sys.stderr)
                return []
        except Exception as e:
            print(f"  [!] Error for r/{subreddit} + '{keyword}': {e}", file=sys.stderr)
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

def main():
    config = load_config()
    subreddits = config.get("subreddits", [])
    keywords = config.get("keywords", [])
    max_posts = config.get("max_posts_per_search", 25)
    results: list[ScanResult] = []
    seen_ids: set[str] = set()
    total = len(subreddits) * len(keywords)
    count = 0

    print(f"[scan] {len(subreddits)} subreddits × {len(keywords)} keywords = {total} queries", file=sys.stderr)

    for subreddit in subreddits:
        for keyword in keywords:
            count += 1
            posts = search_subreddit(subreddit, keyword, max_posts)
            matched = 0
            for post in posts:
                info = extract_post_info(post, subreddit, keyword)
                if info and info.post_id not in seen_ids:
                    seen_ids.add(info.post_id)
                    results.append(info)
                    matched += 1
            if matched:
                print(f"  [{count}/{total}] r/{subreddit} + '{keyword}' → {matched} matches", file=sys.stderr)
            time.sleep(2.1)

    # Save results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"scan_{timestamp}.json"
    filepath = os.path.join(DATA_DIR, filename)

    output = {
        "scan_time": timestamp,
        "total_queries": total,
        "total_posts": len(results),
        "results": [asdict(r) for r in results],
    }

    with open(filepath, "w") as f:
        json.dump(output, f, indent=2)

    # Print summary to stdout
    print(json.dumps({"total_matches": len(results), "filepath": filepath, "results": output["results"]}))

if __name__ == "__main__":
    main()
