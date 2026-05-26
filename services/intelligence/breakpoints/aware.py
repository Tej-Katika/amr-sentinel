"""WHO AWaRe (Access / Watch / Reserve) classification lookup."""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Optional

DEFAULT_AWARE_CSV = Path(__file__).resolve().parents[3] / "data" / "aware" / "aware_2023.csv"


class AWaReClassifier:
    def __init__(self) -> None:
        self._by_atc: dict[str, str] = {}

    def load(self, csv_path: Path | str = DEFAULT_AWARE_CSV) -> int:
        path = Path(csv_path)
        with path.open() as f:
            reader = csv.DictReader(f)
            for row in reader:
                self._by_atc[row["atc_code"]] = row["aware_category"].upper()
        return len(self._by_atc)

    def lookup(self, atc_code: str) -> Optional[str]:
        return self._by_atc.get(atc_code)


_classifier: Optional[AWaReClassifier] = None


def get_classifier() -> AWaReClassifier:
    global _classifier
    if _classifier is None:
        _classifier = AWaReClassifier()
        try:
            _classifier.load()
        except FileNotFoundError:
            pass
    return _classifier
