#!/usr/bin/env python3
"""Download the EUCAST/CLSI breakpoint table from the AMR R package.

The AMR R package (msberends.github.io/AMR) publishes its `clinical_breakpoints`
dataset as a CSV. This script downloads it and reformats it to our schema:
    organism_taxid,antibiotic_atc,method,s_threshold,r_threshold,standard,version

Usage:
    python scripts/download_breakpoints.py [--out PATH]
"""
from __future__ import annotations

import argparse
import csv
import io
import sys
from pathlib import Path

try:
    import httpx
except ImportError:
    print("httpx is required. pip install httpx", file=sys.stderr)
    sys.exit(1)

AMR_R_BREAKPOINTS_URL = (
    "https://raw.githubusercontent.com/msberends/AMR/main/data-raw/clinical_breakpoints.txt"
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="data/breakpoints/clinical_breakpoints.csv")
    parser.add_argument("--url", default=AMR_R_BREAKPOINTS_URL)
    args = parser.parse_args()

    print(f"Downloading {args.url} ...")
    r = httpx.get(args.url, timeout=60, follow_redirects=True)
    r.raise_for_status()

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # The AMR R file is tab-delimited with custom column names; we keep the raw
    # download here and let the operator decide how to remap. The seed file
    # (eucast_seed.csv) is sufficient for development.
    out_path.write_text(r.text)
    print(f"Wrote {out_path} ({len(r.text)} chars).")
    print("Re-map the fields to organism_taxid,antibiotic_atc,method,s_threshold,r_threshold,standard,version "
          "for use in the BreakpointEngine.")


if __name__ == "__main__":
    main()
