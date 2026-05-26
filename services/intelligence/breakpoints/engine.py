"""SIR classification engine using EUCAST/CLSI breakpoints.

Loads breakpoints from a CSV with the schema:
    organism_taxid,antibiotic_atc,method,s_threshold,r_threshold,standard,version

The full breakpoint table is downloaded by scripts/download_breakpoints.py from
the AMR R package. For local development we ship a minimal seed file.
"""
from __future__ import annotations

import csv
import logging
from dataclasses import dataclass
from typing import Optional

log = logging.getLogger(__name__)


@dataclass
class Breakpoint:
    organism_taxid: int
    antibiotic_atc: str
    method: str  # MIC or DISK
    s_threshold: float
    r_threshold: float
    standard: str  # EUCAST or CLSI
    version: str


@dataclass
class Classification:
    sir: str  # S, I, R
    standard: str
    version: str
    expert_rule: Optional[str] = None


class BreakpointEngine:
    def __init__(self) -> None:
        self.breakpoints: dict[str, Breakpoint] = {}

    def load(self, csv_path: str) -> int:
        with open(csv_path, "r", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                bp = Breakpoint(
                    organism_taxid=int(row["organism_taxid"]),
                    antibiotic_atc=row["antibiotic_atc"],
                    method=row["method"].upper(),
                    s_threshold=float(row["s_threshold"]),
                    r_threshold=float(row["r_threshold"]),
                    standard=row["standard"].upper(),
                    version=row["version"],
                )
                self.breakpoints[self._key(bp.organism_taxid, bp.antibiotic_atc, bp.method, bp.standard)] = bp
        log.info("Loaded %d breakpoint rules from %s", len(self.breakpoints), csv_path)
        return len(self.breakpoints)

    def classify(
        self,
        organism_taxid: int,
        antibiotic_atc: str,
        method: str,
        value: float,
        standard: str = "EUCAST",
    ) -> Optional[Classification]:
        bp = self._lookup(organism_taxid, antibiotic_atc, method, standard)
        if bp is None and standard == "EUCAST":
            # Fall back to CLSI if EUCAST has no breakpoint
            bp = self._lookup(organism_taxid, antibiotic_atc, method, "CLSI")

        if bp is None:
            return None

        if method == "MIC":
            sir = "S" if value <= bp.s_threshold else ("R" if value > bp.r_threshold else "I")
        elif method == "DISK":
            sir = "S" if value >= bp.s_threshold else ("R" if value < bp.r_threshold else "I")
        else:
            return None

        return Classification(sir=sir, standard=bp.standard, version=bp.version)

    def _lookup(self, taxid: int, atc: str, method: str, standard: str) -> Optional[Breakpoint]:
        return self.breakpoints.get(self._key(taxid, atc, method, standard))

    @staticmethod
    def _key(taxid: int, atc: str, method: str, standard: str) -> str:
        return f"{taxid}|{atc}|{method.upper()}|{standard.upper()}"
