"""HL7 FHIR R4 DiagnosticReport / Observation parser.

Extracts isolate-antibiotic results from a FHIR Bundle. The structure we
expect:

    Bundle
    └── DiagnosticReport (microbiology culture)
        └── result -> Observation (organism identification)
            └── component -> Observation (per-antibiotic susceptibility)

Real EHR FHIR exports vary; we accept the simple form below as a baseline.
"""
from __future__ import annotations

from typing import Iterator

from ..models import MeasurementType, RawIsolate, SourceFormat


# LOINC codes commonly used for AST results
LOINC_SUSCEPTIBILITY_PANEL = "18769-0"
LOINC_MIC = "13362-9"


def parse_fhir_bundle(bundle: dict, default_facility_id: str | None = None) -> Iterator[RawIsolate]:
    """Iterate isolates from a FHIR R4 Bundle JSON dict."""
    if bundle.get("resourceType") != "Bundle":
        return

    by_id: dict[str, dict] = {}
    for entry in bundle.get("entry", []):
        resource = entry.get("resource", {})
        rid = f"{resource.get('resourceType')}/{resource.get('id')}"
        by_id[rid] = resource

    for resource in by_id.values():
        if resource.get("resourceType") != "DiagnosticReport":
            continue

        facility_id = _facility_id_from_report(resource) or default_facility_id
        specimen_id = _specimen_id_from_report(resource) or resource.get("id", "UNKNOWN")
        collection_date = _collection_date_from_report(resource)

        if not (facility_id and collection_date):
            continue

        for ref in resource.get("result", []):
            obs = by_id.get(ref.get("reference", ""))
            if not obs:
                continue

            organism = _organism_from_observation(obs)
            if not organism:
                continue

            for component in obs.get("contained", []) + _resolve_components(obs, by_id):
                ab_result = _component_to_raw(
                    component=component,
                    facility_id=facility_id,
                    specimen_id=specimen_id,
                    organism=organism,
                    specimen_type=_specimen_type_from_report(resource),
                    collection_date=collection_date,
                )
                if ab_result:
                    yield ab_result


def _facility_id_from_report(report: dict) -> str | None:
    for performer in report.get("performer", []):
        ref = performer.get("reference", "")
        if ref.startswith("Organization/"):
            return ref.split("/", 1)[1]
    return None


def _specimen_id_from_report(report: dict) -> str | None:
    spec = report.get("specimen") or []
    if isinstance(spec, list) and spec:
        ref = spec[0].get("reference", "")
        if "/" in ref:
            return ref.split("/", 1)[1]
    return None


def _specimen_type_from_report(report: dict) -> str | None:
    code = report.get("category", [{}])[0].get("coding", [{}])[0].get("display")
    return code


def _collection_date_from_report(report: dict) -> str | None:
    return (
        report.get("effectiveDateTime")
        or report.get("issued")
        or report.get("effectivePeriod", {}).get("start")
    )


def _organism_from_observation(obs: dict) -> str | None:
    coding = obs.get("valueCodeableConcept", {}).get("coding", [])
    if coding and coding[0].get("display"):
        return coding[0]["display"]
    return obs.get("valueString")


def _resolve_components(obs: dict, by_id: dict[str, dict]) -> list[dict]:
    """FHIR can either embed components or link via 'hasMember' references."""
    out = list(obs.get("component", []))
    for ref in obs.get("hasMember", []):
        target = by_id.get(ref.get("reference", ""))
        if target:
            out.append(target)
    return out


def _component_to_raw(
    *,
    component: dict,
    facility_id: str,
    specimen_id: str,
    organism: str,
    specimen_type: str | None,
    collection_date: str,
) -> RawIsolate | None:
    code = component.get("code", {}).get("coding", [{}])[0]
    abx_name = code.get("display")
    if not abx_name:
        return None

    quantity = component.get("valueQuantity") or component.get("valueInteger")
    if isinstance(quantity, dict):
        value = quantity.get("value")
        unit = (quantity.get("unit") or "").lower()
        comparator = quantity.get("comparator")
    elif isinstance(quantity, (int, float)):
        value, unit, comparator = float(quantity), "", None
    else:
        return None

    if value is None:
        return None

    if "mm" in unit:
        measurement_type = MeasurementType.DISK
    elif "/" in unit or "ug" in unit or "µg" in unit or "mg" in unit:
        measurement_type = MeasurementType.MIC
    else:
        # Best guess: small values are MIC
        measurement_type = MeasurementType.MIC if value < 64 else MeasurementType.DISK

    return RawIsolate(
        facility_id=facility_id,
        specimen_id=specimen_id,
        specimen_type=specimen_type,
        organism_input=organism,
        antibiotic_input=abx_name,
        measurement_type=measurement_type,
        measurement_value=float(value),
        measurement_comparator=comparator,
        collection_date=collection_date,
        source_format=SourceFormat.FHIR,
    )
