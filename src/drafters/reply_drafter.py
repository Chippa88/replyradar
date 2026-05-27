#!/usr/bin/env python3
"""ReplyRadar — AI Reply Drafter & Approval Queue.

Generates contextual, non-spammy AI replies for matched Reddit posts.
Uses OpenRouter for LLM access.

Usage:
    python reply_drafter.py scan_20260527_120000.json    # draft replies
    python approval_queue.py                              # interactive approve/reject
"""

import json
import os
import time
from datetime import datetime, timezone
from dataclasses import dataclass, asdict
from typing import Optional
import urllib.request
import urllib.error

# ── Config ────────────────────────────────────────────────────
OR_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OR_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL = "deepseek/deepseek-v4-flash"
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data")

DRAFT_SYSTEM_PROMPT = """You are a helpful Reddit user who happens to know about Vantaire Systems — an AI automation company that builds custom agent workflows and operating systems for businesses. 

Your replies must:
- Be genuinely helpful, never salesy
- Acknowledge the post's specific situation
- Provide a concrete tip or insight
- Mention Vantaire Systems ONLY if it's naturally relevant (1 out of 4 replies max)
- End with a question or invitation to continue the conversation
- NEVER use: exclamation marks, ALL CAPS, emojis, or sales language
- Keep it under 4 sentences
- Sound like a real person, not a bot"""


@dataclass
class Draft:
    post_id: str
    title: str
    url: str
    draft_reply: str
    confidence: float
    reasoning: str
    drafted_at: str
    status: str = "pending"  # pending, approved, rejected, edited


def load_scan(filepath: str) -> list[dict]:
    """Load a scan result file."""
    with open(filepath) as f:
        data = json.load(f)
    return data.get("results", [])


def draft_reply(post: dict, model: str = MODEL) -> Optional[Draft]:
    """Generate an AI reply for a single post."""
    user_prompt = f"""r/{post['subreddit']} — "{post['title']}"

The user wrote: {post['body_snippet'][:400]}

Draft a helpful reply. Be specific to their situation."""

    payload = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": DRAFT_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        "max_tokens": 250,
        "temperature": 0.7,
    }).encode()

    req = urllib.request.Request(
        OR_URL,
        data=payload,
        headers={
            "Authorization": f"Bearer {OR_KEY}",
            "Content-Type": "application/json",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"[!] LLM error {e.code}: {body[:200]}")
        return None
    except Exception as e:
        print(f"[!] LLM error: {e}")
        return None

    reply = data.get("choices", [{}])[0].get("message", {}).get("content", "")

    return Draft(
        post_id=post.get("post_id", ""),
        title=post.get("title", ""),
        url=post.get("url", ""),
        draft_reply=reply.strip(),
        confidence=0.8,
        reasoning="AI-generated draft",
        drafted_at=datetime.now(timezone.utc).isoformat(),
    )


def run_drafter(scan_path: str, max_posts: int = 10) -> list[dict]:
    """Draft replies for the top N posts in a scan."""
    posts = load_scan(scan_path)

    # Sort by score, take top N
    posts.sort(key=lambda p: p.get("score", 0), reverse=True)
    posts = posts[:max_posts]

    drafts = []
    for i, post in enumerate(posts):
        print(f"  [{i+1}/{len(posts)}] Drafting reply for: {post['title'][:80]}")
        draft = draft_reply(post)
        if draft:
            drafts.append(asdict(draft))
        time.sleep(1.5)  # Rate limit

    # Save
    os.makedirs(os.path.join(DATA_DIR, "drafts"), exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = os.path.join(DATA_DIR, "drafts", f"drafts_{ts}.json")
    with open(out_path, "w") as f:
        json.dump({"drafted_at": ts, "count": len(drafts), "drafts": drafts}, f, indent=2)

    print(f"\n[✓] Saved {len(drafts)} drafts to {out_path}")
    return drafts


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python reply_drafter.py <scan_file.json> [max_posts]")
        sys.exit(1)

    scan_file = sys.argv[1]
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 10
    run_drafter(scan_file, limit)
