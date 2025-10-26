#!/usr/bin/env python3
"""
Maintenance-aware documentation organizer.
Normalizes maintenance/guide/test write-ups into their dedicated folders.
"""

import shutil
from pathlib import Path

ROOT = Path(__file__).parent.resolve()

DOC_DESTINATIONS = {
    "maintenance": {
        "docs": {
            "dir": ROOT / "Maintenance" / "docs",
            "patterns": [
                "all_fix", "summary", "fix", "bug", "patch",
                "troubleshoot", "issue", "problem"
            ],
        },
        "scripts": {
            "dir": ROOT / "Maintenance" / "scripts",
            "patterns": [
                "fix_", "apply_", "_fix", "cleanup", "patch"
            ],
        },
        "tests": {
            "dir": ROOT / "Maintenance" / "tests",
            "patterns": [
                "test_", "verify_", "_fix", "regression"
            ],
        },
    },
    "documentation": {
        "Guides": {
            "dir": ROOT / "Documentation" / "Guides",
            "patterns": [
                "guide", "setup", "deployment", "archive", "launch", "start", "manual"
            ],
        },
        "Checklists": {
            "dir": ROOT / "Documentation" / "Checklists",
            "patterns": [
                "checklist", "upgrade", "ready", "testing"
            ],
        },
        "Reports": {
            "dir": ROOT / "Documentation" / "Reports",
            "patterns": [
                "report", "review", "summary", "status", "improvement", "session",
                "phase", "tier", "complete", "progress", "roadmap", "implemented", "removed"
            ],
        },
        "Reference": {
            "dir": ROOT / "Documentation" / "Reference",
            "patterns": [
                "reference", "strategy", "notes", "quick", "refactor",
                "recommendation", "architectural"
            ],
        },
    }
}


def ensure_directories():
    for groups in DOC_DESTINATIONS.values():
        for meta in groups.values():
            meta["dir"].mkdir(parents=True, exist_ok=True)


def classify_target(name: str) -> Path | None:
    lower_name = name.lower()
    stem = lower_name.replace(".bak", "")

    for meta in DOC_DESTINATIONS["maintenance"].values():
        if any(pattern in stem for pattern in meta["patterns"]):
            return meta["dir"]

    for meta in DOC_DESTINATIONS["documentation"].values():
        if any(pattern in stem for pattern in meta["patterns"]):
            return meta["dir"]

    return None


def move_files():
    moved = []
    # Files to keep in root directory
    keep_in_root = {"README.md", "main.py", "config.py", "requirements.txt"}

    for item in ROOT.iterdir():
        if item.is_dir():
            continue
        if item.name in keep_in_root:
            continue  # Keep these files in root
        if item.suffix not in {".md", ".py"}:
            continue
        target_dir = classify_target(item.name)
        if not target_dir:
            continue
        try:
            destination = target_dir / item.name
            if item.resolve() == destination.resolve():
                continue
            if destination.exists():
                backup = destination.with_suffix(destination.suffix + ".bak")
                destination.rename(backup)
            shutil.move(str(item), destination)
            moved.append((item.name, target_dir))
        except Exception as exc:
            print(f"Warning: Could not move {item} -> {target_dir}: {exc}")
    return moved


def main():
    ensure_directories()
    moved = move_files()
    if moved:
        print("Organized the following files:")
        for name, directory in moved:
            print(f"  {name} -> {directory.relative_to(ROOT)}")
    else:
        print("No files required organization.")


if __name__ == "__main__":
    main()
