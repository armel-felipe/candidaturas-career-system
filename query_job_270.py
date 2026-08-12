#!/usr/bin/env python3
"""Compatibility wrapper for fetching a Notion record by project ID."""

from __future__ import annotations

import sys

from fetch_270 import main as fetch_main


if __name__ == "__main__":
    if len(sys.argv) == 1:
        sys.argv.append("270")
    raise SystemExit(fetch_main())
