"""Expert rule tests: MRSA, ESBL, intrinsic resistance."""
from breakpoints.engine import Classification
from breakpoints.expert_rules import (
    ATC_AMOXICILLIN,
    ATC_AMPICILLIN,
    ATC_CEFTRIAXONE,
    ATC_OXACILLIN,
    ATC_PENICILLIN_G,
    TAXID_E_COLI,
    TAXID_K_PNEUMONIAE,
    TAXID_S_AUREUS,
    IsolatePanel,
    apply,
)


def _classification(sir: str) -> Classification:
    return Classification(sir=sir, standard="EUCAST", version="2025.1")


def test_mrsa_propagates_to_all_beta_lactams():
    """Oxacillin-resistant S. aureus -> all (non-carbapenem) beta-lactams marked R."""
    panel = IsolatePanel(
        organism_taxid=TAXID_S_AUREUS,
        classifications={
            ATC_OXACILLIN:    _classification("R"),
            ATC_AMOXICILLIN:  _classification("S"),
            ATC_PENICILLIN_G: _classification("S"),
        },
    )
    apply(panel)
    assert panel.classifications[ATC_AMOXICILLIN].sir == "R"
    assert panel.classifications[ATC_AMOXICILLIN].expert_rule == "mrsa_beta_lactams"
    assert panel.classifications[ATC_PENICILLIN_G].sir == "R"


def test_mssa_does_not_trigger_mrsa_rule():
    """Oxacillin-susceptible S. aureus: other beta-lactams keep their original SIR."""
    panel = IsolatePanel(
        organism_taxid=TAXID_S_AUREUS,
        classifications={
            ATC_OXACILLIN:   _classification("S"),
            ATC_AMOXICILLIN: _classification("S"),
        },
    )
    apply(panel)
    assert panel.classifications[ATC_AMOXICILLIN].sir == "S"
    assert panel.classifications[ATC_AMOXICILLIN].expert_rule is None


def test_esbl_makes_cephalosporins_resistant():
    """E. coli with ceftriaxone-R -> all 1st-3rd gen cephalosporins R."""
    panel = IsolatePanel(
        organism_taxid=TAXID_E_COLI,
        classifications={
            ATC_CEFTRIAXONE: _classification("R"),
            "J01DC01":       _classification("S"),  # cefoxitin
        },
    )
    apply(panel)
    assert panel.classifications["J01DC01"].sir == "R"
    assert panel.classifications["J01DC01"].expert_rule == "esbl_phenotype"


def test_klebsiella_intrinsic_ampicillin_resistance():
    """K. pneumoniae is intrinsically R to ampicillin regardless of MIC."""
    panel = IsolatePanel(
        organism_taxid=TAXID_K_PNEUMONIAE,
        classifications={
            ATC_AMPICILLIN: _classification("S"),  # spurious lab result
        },
    )
    apply(panel)
    assert panel.classifications[ATC_AMPICILLIN].sir == "R"
    assert panel.classifications[ATC_AMPICILLIN].expert_rule == "intrinsic_resistance"


def test_other_organisms_unaffected():
    """A susceptible E. coli should not be touched by any rule."""
    panel = IsolatePanel(
        organism_taxid=TAXID_E_COLI,
        classifications={
            ATC_AMPICILLIN:  _classification("S"),
            ATC_CEFTRIAXONE: _classification("S"),
        },
    )
    apply(panel)
    assert panel.classifications[ATC_AMPICILLIN].sir == "S"
    assert panel.classifications[ATC_CEFTRIAXONE].sir == "S"
