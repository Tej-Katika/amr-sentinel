"""EUCAST expert rules.

Some classifications are determined by clinical context, not just the raw MIC.
This module applies post-classification overrides:

    1. MRSA (S. aureus + oxacillin R) -> all beta-lactams reported as R
       (except ceftaroline / ceftobiprole, which we don't model yet)
    2. ESBL phenotype (Enterobacteriaceae + ceftazidime/ceftriaxone R) ->
       all 1st/2nd/3rd gen cephalosporins reported as R
    3. K. pneumoniae intrinsic resistance to ampicillin
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional

from .engine import Classification

# NCBI taxids
TAXID_S_AUREUS = 1280
TAXID_K_PNEUMONIAE = 573
TAXID_E_COLI = 562

# ATC codes
ATC_OXACILLIN = "J01CF04"
ATC_CEFTAZIDIME = "J01DD02"
ATC_CEFTRIAXONE = "J01DD04"
ATC_AMPICILLIN = "J01CA01"
ATC_AMOXICILLIN = "J01CA04"
ATC_PENICILLIN_G = "J01CE01"
ATC_CEFOXITIN = "J01DC01"
ATC_CEFEPIME = "J01DE01"

BETA_LACTAMS_NON_CARBAPENEM = {
    ATC_AMPICILLIN, ATC_AMOXICILLIN, ATC_PENICILLIN_G, ATC_OXACILLIN,
    ATC_CEFTAZIDIME, ATC_CEFTRIAXONE, ATC_CEFEPIME, ATC_CEFOXITIN,
    "J01CR02",  # Amox/clav
    "J01CR05",  # Pip/tazo
}

CEPHALOSPORINS_1_3 = {
    ATC_CEFOXITIN, ATC_CEFTAZIDIME, ATC_CEFTRIAXONE,
}

ENTEROBACTERIACEAE_TAXIDS = {TAXID_E_COLI, TAXID_K_PNEUMONIAE}


@dataclass
class IsolatePanel:
    """One isolate's full antibiotic panel keyed by ATC code."""
    organism_taxid: int
    classifications: dict[str, Classification]


def apply(panel: IsolatePanel) -> IsolatePanel:
    """Mutate-and-return: apply expert rules to a panel."""
    panel = _intrinsic_resistance(panel)
    panel = _mrsa_beta_lactams(panel)
    panel = _esbl_cephalosporins(panel)
    return panel


def _intrinsic_resistance(panel: IsolatePanel) -> IsolatePanel:
    """K. pneumoniae is intrinsically resistant to ampicillin."""
    if panel.organism_taxid == TAXID_K_PNEUMONIAE:
        panel.classifications[ATC_AMPICILLIN] = Classification(
            sir="R",
            standard="INTRINSIC",
            version="2025",
            expert_rule="intrinsic_resistance",
        )
    return panel


def _mrsa_beta_lactams(panel: IsolatePanel) -> IsolatePanel:
    """If S. aureus is oxacillin-R, mark all (non-carbapenem) beta-lactams R."""
    if panel.organism_taxid != TAXID_S_AUREUS:
        return panel
    oxa = panel.classifications.get(ATC_OXACILLIN)
    if oxa is None or oxa.sir != "R":
        return panel
    for atc in BETA_LACTAMS_NON_CARBAPENEM:
        if atc == ATC_OXACILLIN:
            continue
        existing = panel.classifications.get(atc)
        panel.classifications[atc] = Classification(
            sir="R",
            standard=existing.standard if existing else "EUCAST",
            version=existing.version if existing else "2025",
            expert_rule="mrsa_beta_lactams",
        )
    return panel


def _esbl_cephalosporins(panel: IsolatePanel) -> IsolatePanel:
    """If Enterobacteriaceae is resistant to ceftriaxone or ceftazidime,
    apply ESBL phenotype: 1st-3rd gen cephalosporins all R."""
    if panel.organism_taxid not in ENTEROBACTERIACEAE_TAXIDS:
        return panel
    flag = False
    for atc in (ATC_CEFTAZIDIME, ATC_CEFTRIAXONE):
        c = panel.classifications.get(atc)
        if c and c.sir == "R":
            flag = True
            break
    if not flag:
        return panel
    for atc in CEPHALOSPORINS_1_3:
        existing = panel.classifications.get(atc)
        panel.classifications[atc] = Classification(
            sir="R",
            standard=existing.standard if existing else "EUCAST",
            version=existing.version if existing else "2025",
            expert_rule="esbl_phenotype",
        )
    return panel


def panel_from_classifications(
    organism_taxid: int,
    items: Iterable[tuple[str, Optional[Classification]]],
) -> IsolatePanel:
    """Helper: build IsolatePanel from (atc, Classification|None) pairs."""
    panel = IsolatePanel(organism_taxid=organism_taxid, classifications={})
    for atc, classification in items:
        if classification is not None:
            panel.classifications[atc] = classification
    return panel
