#!/usr/bin/env python3
"""
Quick dashboard health probe with helpful diagnostics.

Usage:
    python scripts/check_dashboard_health.py --host http://localhost:8000
Environment:
    DASHBOARD_API_KEY   required if --api-key is not provided
    DASHBOARD_BASE_URL  optional default host override
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Dict

import requests


DEFAULT_HOST = "http://localhost:8000"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Probe trading dashboard health endpoint.")
    parser.add_argument(
        "--host",
        default=os.environ.get("DASHBOARD_BASE_URL", DEFAULT_HOST),
        help="Base URL for the dashboard API (default: %(default)s)",
    )
    parser.add_argument(
        "--api-key",
        default=os.environ.get("DASHBOARD_API_KEY"),
        help="Dashboard API key (falls back to DASHBOARD_API_KEY env var)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=5.0,
        help="Request timeout in seconds (default: %(default)s)",
    )
    return parser.parse_args()


def prettify_json(data: Dict[str, Any]) -> str:
    return json.dumps(data, indent=2, sort_keys=True)


def main() -> int:
    args = parse_args()

    if not args.api_key:
        print("DASHBOARD_API_KEY is required. Set the environment variable or pass --api-key.", file=sys.stderr)
        return 1

    url = args.host.rstrip("/") + "/health"
    headers = {"X-API-Key": args.api_key}

    try:
        response = requests.get(url, headers=headers, timeout=args.timeout)
        response.raise_for_status()
    except requests.exceptions.RequestException as exc:
        print(f"Failed to connect to the server ({url}): {exc}", file=sys.stderr)
        return 2

    print("Successfully connected to the server.")
    try:
        print(prettify_json(response.json()))
    except ValueError:
        body_preview = response.text.strip().splitlines()
        # Show the first non-empty line to aid debugging without dumping huge payloads.
        first_line = next((line for line in body_preview if line), "")
        print("Server returned non-JSON response. First line:")
        print(first_line[:200])

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
