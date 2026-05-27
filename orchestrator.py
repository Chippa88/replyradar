#!/usr/bin/env python3
"""ReplyRadar — Main Orchestrator.

Runs the full pipeline: scan → draft → notify.
Designed to run via Hermes cron job every 1-2 hours.

Usage:
    python orchestrator.py
"""

import os
import sys
import json
from datetime import datetime

BASE = os.path.dirname(os.path.abspath(__file__))

def step(msg: str):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


def main():
    step("ReplyRadar pipeline starting...")

    # 1. Run scanner
    step("Running Reddit scanner...")
    scanner = os.path.join(BASE, "src", "monitors", "reddit_scanner.py")
    result = os.system(f"cd '{BASE}' && python3 '{scanner}' --no-save 2>&1 | tail -5")
    if result != 0:
        step(f"Scanner exited with code {result}")
        # Try to find the latest scan
    else:
        step("Scan complete")

    # 2. Find latest scan
    scans_dir = os.path.join(BASE, "data", "scans")
    scans = sorted(
        [f for f in os.listdir(scans_dir) if f.endswith(".json")],
        reverse=True
    ) if os.path.isdir(scans_dir) else []

    if not scans:
        step("No scans found — nothing to draft")
        return

    latest = os.path.join(scans_dir, scans[0])
    step(f"Using scan: {scans[0]}")

    # 3. Run drafter
    drafter = os.path.join(BASE, "src", "drafters", "reply_drafter.py")
    os.system(f"cd '{BASE}' && python3 '{drafter}' '{latest}' 5 2>&1 | tail -5")

    # 4. Count drafts
    drafts_dir = os.path.join(BASE, "data", "drafts")
    all_drafts = sorted(
        [f for f in os.listdir(drafts_dir) if f.endswith(".json")],
        reverse=True
    ) if os.path.isdir(drafts_dir) else []

    if all_drafts:
        with open(os.path.join(drafts_dir, all_drafts[0])) as f:
            data = json.load(f)
            count = data.get("count", 0)
            step(f"{count} drafts ready for approval")
            print(f"\n{'='*50}")
            print(f"  {count} new replies waiting in your approval queue")
            print(f"  Open: cd {BASE} && python3 src/drafters/approval_queue.py {all_drafts[0]}")
            print(f"{'='*50}")

    step("Pipeline complete")


if __name__ == "__main__":
    main()
