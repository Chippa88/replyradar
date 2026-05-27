#!/usr/bin/env python3
"""ReplyRadar — Approval Queue.

Review, approve, reject, or edit drafted replies before posting.
Approved replies move to data/approved/. Rejected to data/rejected/.

Usage:
    python approval_queue.py drafts_20260527_120000.json
"""

import json
import os
import sys
import shutil
from datetime import datetime, timezone

DRAFTS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "drafts")
APPROVED_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "approved")
REJECTED_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "rejected")
os.makedirs(APPROVED_DIR, exist_ok=True)
os.makedirs(REJECTED_DIR, exist_ok=True)


def load_drafts(filepath: str) -> dict:
    with open(filepath) as f:
        return json.load(f)


def save_updated(drafts_data: dict, filepath: str):
    with open(filepath, "w") as f:
        json.dump(drafts_data, f, indent=2)


def approve(draft: dict) -> dict:
    draft["status"] = "approved"
    draft["approved_at"] = datetime.now(timezone.utc).isoformat()
    return draft


def reject(draft: dict, reason: str = "") -> dict:
    draft["status"] = "rejected"
    draft["rejected_at"] = datetime.now(timezone.utc).isoformat()
    draft["reject_reason"] = reason
    return draft


def export_approved(drafts: list[dict]):
    """Export approved drafts to the approved directory."""
    approved = [d for d in drafts if d.get("status") == "approved"]
    if not approved:
        return

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(APPROVED_DIR, f"approved_{ts}.json")
    with open(path, "w") as f:
        json.dump({"approved_at": ts, "count": len(approved), "replies": approved}, f, indent=2)
    print(f"[✓] {len(approved)} approved → {path}")


def export_rejected(drafts: list[dict]):
    """Export rejected drafts to the rejected directory."""
    rejected = [d for d in drafts if d.get("status") == "rejected"]
    if not rejected:
        return

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(REJECTED_DIR, f"rejected_{ts}.json")
    with open(path, "w") as f:
        json.dump({"rejected_at": ts, "count": len(rejected), "replies": rejected}, f, indent=2)
    print(f"[✗] {len(rejected)} rejected → {path}")


def interactive_review(filepath: str):
    """Interactive approval queue. Walk through each draft."""
    data = load_drafts(filepath)
    drafts = data.get("drafts", [])
    pending = [d for d in drafts if d.get("status") == "pending"]

    if not pending:
        print("No pending drafts to review.")
        return

    print(f"\n{'='*70}")
    print(f"ReplyRadar Approval Queue — {len(pending)} drafts to review")
    print(f"{'='*70}\n")

    for i, draft in enumerate(pending):
        print(f"[{i+1}/{len(pending)}] r/{draft.get('subreddit', '?')}")
        print(f"  Title: {draft['title'][:100]}")
        print(f"  URL:   {draft['url']}")
        print(f"\n  Draft:")
        print(f"  {draft['draft_reply']}")
        print(f"\n  Confidence: {draft.get('confidence', '?')}")

        print(f"\n  [A]pprove  [R]eject  [E]dit  [S]kip  [Q]uit")
        choice = input("  > ").strip().lower()

        if choice == "a":
            approve(draft)
            print("  ✓ Approved\n")
        elif choice == "r":
            reason = input("  Reject reason (optional): ").strip()
            reject(draft, reason)
            print("  ✗ Rejected\n")
        elif choice == "e":
            print("  Paste edited reply (press Enter twice to finish):")
            lines = []
            while True:
                line = input()
                if line == "" and lines and lines[-1] == "":
                    break
                lines.append(line)
            new_reply = "\n".join(lines).strip()
            if new_reply:
                draft["draft_reply"] = new_reply
                draft["edited"] = True
            approve(draft)
            print("  ✓ Edited & approved\n")
        elif choice == "q":
            print("  Exiting review.\n")
            break
        else:
            print("  Skipped\n")

    # Save updates and export
    save_updated(data, filepath)
    export_approved(drafts)
    export_rejected(drafts)
    print("[✓] Review complete.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python approval_queue.py <drafts_file.json>")
        print(f"Files in {DRAFTS_DIR}:")
        for f in sorted(os.listdir(DRAFTS_DIR)):
            if f.endswith(".json"):
                print(f"  {f}")
        sys.exit(1)

    interactive_review(sys.argv[1])
