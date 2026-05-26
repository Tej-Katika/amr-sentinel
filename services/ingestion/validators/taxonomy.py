"""Lookup helpers for organism (NCBI taxid) and antibiotic (ATC) resolution."""
from __future__ import annotations

import json
from dataclasses import dataclass
from difflib import get_close_matches
from pathlib import Path
from typing import Optional

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"


@dataclass
class OrganismRecord:
    taxid: int
    name: str
    gram_stain: Optional[str] = None
    family: Optional[str] = None


@dataclass
class AntibioticRecord:
    atc: str
    name: str
    drug_class: Optional[str] = None


class TaxonomyResolver:
    """Resolves organism codes / names to NCBI taxids and antibiotic codes / names to ATC codes.

    Loaded once at startup; lookups are O(1) for exact matches and
    O(N) fuzzy fallback only when needed.
    """

    def __init__(self) -> None:
        self._organism_by_code: dict[str, OrganismRecord] = {}
        self._organism_by_name: dict[str, int] = {}
        self._organisms_by_taxid: dict[int, OrganismRecord] = {}
        self._abx_by_code: dict[str, AntibioticRecord] = {}
        self._abx_by_name: dict[str, str] = {}
        self._abx_by_atc: dict[str, AntibioticRecord] = {}
        self._load()

    def _load(self) -> None:
        with (CONFIG_DIR / "organism_taxonomy.json").open() as f:
            data = json.load(f)
        for code, payload in data["by_whonet_code"].items():
            rec = OrganismRecord(**payload)
            self._organism_by_code[code.lower()] = rec
            self._organisms_by_taxid[rec.taxid] = rec
        for name, taxid in data["by_name"].items():
            self._organism_by_name[name.lower()] = int(taxid)

        with (CONFIG_DIR / "antibiotic_atc.json").open() as f:
            data = json.load(f)
        for code, payload in data["by_whonet_code"].items():
            rec = AntibioticRecord(**payload)
            self._abx_by_code[code.upper()] = rec
            self._abx_by_atc[rec.atc] = rec
        for name, atc in data["by_name"].items():
            self._abx_by_name[name.lower()] = atc

    # ------------- Organisms -------------

    def resolve_organism(self, value: str) -> Optional[OrganismRecord]:
        if not value:
            return None
        v = value.strip().lower()

        # exact code match
        if v in self._organism_by_code:
            return self._organism_by_code[v]

        # exact name match
        taxid = self._organism_by_name.get(v)
        if taxid is not None:
            return self._organisms_by_taxid.get(taxid)

        # fuzzy fallback
        candidates = get_close_matches(v, self._organism_by_name.keys(), n=1, cutoff=0.85)
        if candidates:
            taxid = self._organism_by_name[candidates[0]]
            return self._organisms_by_taxid.get(taxid)
        return None

    # ------------- Antibiotics -------------

    def resolve_antibiotic(self, value: str) -> Optional[AntibioticRecord]:
        if not value:
            return None
        v_upper = value.strip().upper()

        # exact ATC code
        if v_upper in self._abx_by_atc:
            return self._abx_by_atc[v_upper]

        # exact WHONET code (handle codes like "AMP_ND10" -> "AMP")
        base_code = v_upper.split("_")[0]
        if base_code in self._abx_by_code:
            return self._abx_by_code[base_code]

        # exact name match (case insensitive)
        v_lower = value.strip().lower()
        atc = self._abx_by_name.get(v_lower)
        if atc:
            return self._abx_by_atc.get(atc)

        # fuzzy fallback
        candidates = get_close_matches(v_lower, self._abx_by_name.keys(), n=1, cutoff=0.85)
        if candidates:
            atc = self._abx_by_name[candidates[0]]
            return self._abx_by_atc.get(atc)
        return None


_resolver: Optional[TaxonomyResolver] = None


def get_resolver() -> TaxonomyResolver:
    global _resolver
    if _resolver is None:
        _resolver = TaxonomyResolver()
    return _resolver
