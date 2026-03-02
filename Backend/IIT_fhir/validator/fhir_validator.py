"""
FHIR Validator for NHCX InsurancePlan bundles.

Two layers of validation:
1. FHIR R4 structural validation — using fhir.resources Pydantic models
   (ensures the JSON is valid FHIR R4)
2. NHCX profile validation — checks against NRCeS IG v6.5.0 requirements
   (identifier, period, CodeSystems, extensions, mandatory fields)

All checks are sourced from:
  https://nrces.in/ndhm/fhir/r4/StructureDefinition-InsurancePlan.html

All validation rules are configurable via config/validation_rules.yaml
"""

import logging
from typing import List
import yaml
import os

logger = logging.getLogger(__name__)


def _load_validation_config():
    """Load validation rules from YAML configuration file."""
    config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'validation_rules.yaml')
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        logger.info(f"Loaded validation rules from {config_path}")
        return config
    except Exception as e:
        logger.error(f"Failed to load validation config from {config_path}: {e}")
        return _get_default_config()


def _get_default_config():
    """Return default configuration if file not found."""
    return {
        'profiles': {
            'insurance_plan': 'https://nrces.in/ndhm/fhir/r4/StructureDefinition/InsurancePlan',
            'organization': 'https://nrces.in/ndhm/fhir/r4/StructureDefinition/Organization',
            'insurance_plan_bundle': 'https://nrces.in/ndhm/fhir/r4/StructureDefinition/InsurancePlanBundle'
        },
        'codesystems': {
            'snomed': 'http://snomed.info/sct',
            'insuranceplan_type': 'https://nrces.in/ndhm/fhir/r4/CodeSystem/ndhm-insuranceplan-type',
            'plan_type': 'https://nrces.in/ndhm/fhir/r4/CodeSystem/ndhm-plan-type',
            'claim_exclusion': 'https://nrces.in/ndhm/fhir/r4/CodeSystem/ndhm-claim-exclusion'
        },
        'extensions': {
            'claim_exclusion': 'https://nrces.in/ndhm/fhir/r4/StructureDefinition/Claim-Exclusion',
            'claim_condition': 'https://nrces.in/ndhm/fhir/r4/StructureDefinition/Claim-Condition'
        },
        'bundle': {
            'allowed_types': ['collection', 'transaction', 'document'],
            'required_entries': ['Organization', 'InsurancePlan']
        },
        'insuranceplan': {
            'allowed_statuses': ['active', 'draft', 'retired']
        }
    }


# Load config at module level
_config = _load_validation_config()
_profiles = _config.get('profiles', {})
_codesystems = _config.get('codesystems', {})
_extensions = _config.get('extensions', {})
_bundle_config = _config.get('bundle', {})


def validate(bundle: dict) -> List[str]:
    """
    Validate a FHIR Bundle containing Organization + InsurancePlan.
    Returns a list of error strings. Empty list = valid.
    """
    errors = []

    # ── Bundle-level checks ──
    errors.extend(_validate_bundle_structure(bundle))

    # ── Per-resource validation ──
    for i, entry in enumerate(bundle.get("entry", [])):
        resource = entry.get("resource", {})
        res_type = resource.get("resourceType", "Unknown")

        # Check fullUrl
        if not entry.get("fullUrl"):
            errors.append(f"entry[{i}] ({res_type}): missing fullUrl")

        # FHIR R4 Pydantic model validation
        errors.extend(_validate_fhir_model(resource, i))

        # NHCX profile-specific checks
        if res_type == "Organization":
            errors.extend(_validate_nhcx_organization(resource, i))
        elif res_type == "InsurancePlan":
            errors.extend(_validate_nhcx_insurance_plan(resource, i))

    logger.info(f"Validation complete: {len(errors)} error(s) found")
    return errors


def _validate_bundle_structure(bundle: dict) -> List[str]:
    """Check top-level Bundle structure."""
    errors = []
    bundle_profile = _profiles.get('insurance_plan_bundle')
    allowed_types = _bundle_config.get('allowed_types', ['collection', 'transaction', 'document'])

    if bundle.get("resourceType") != "Bundle":
        errors.append("Bundle: resourceType must be 'Bundle'")

    if not bundle.get("id"):
        errors.append("Bundle: missing id")

    if bundle.get("type") not in allowed_types:
        errors.append(
            f"Bundle: type '{bundle.get('type')}' is not valid for NHCX "
            f"(expected {'/'.join(allowed_types)})"
        )

    # Bundle.meta.profile must declare InsurancePlanBundle
    bundle_profiles = bundle.get("meta", {}).get("profile", [])
    if bundle_profile not in bundle_profiles:
        errors.append(
            f"Bundle: meta.profile must include {bundle_profile}"
        )

    entries = bundle.get("entry", [])
    if not entries:
        errors.append("Bundle: no entries found")
        return errors

    # Must have at least Organization + InsurancePlan
    resource_types = [e.get("resource", {}).get("resourceType") for e in entries]
    required_entries = _bundle_config.get('required_entries', ['Organization', 'InsurancePlan'])
    
    for required_type in required_entries:
        if required_type not in resource_types:
            errors.append(f"Bundle: missing {required_type} resource")

    return errors


def _validate_fhir_model(resource: dict, entry_index: int) -> List[str]:
    """
    Validate a resource against the fhir.resources Pydantic model.
    This catches structural FHIR R4 issues (wrong types, missing required fields).
    """
    errors = []
    res_type = resource.get("resourceType", "")

    try:
        if res_type == "Bundle":
            from fhir.resources.bundle import Bundle
            Bundle.model_validate(resource)
        elif res_type == "Organization":
            from fhir.resources.organization import Organization
            Organization.model_validate(resource)
        elif res_type == "InsurancePlan":
            from fhir.resources.insuranceplan import InsurancePlan
            InsurancePlan.model_validate(resource)
        else:
            errors.append(f"entry[{entry_index}]: unknown resourceType '{res_type}'")
    except Exception as e:
        err_msg = str(e)
        if len(err_msg) > 500:
            err_msg = err_msg[:500] + "..."
        errors.append(
            f"entry[{entry_index}] ({res_type}) FHIR model validation failed: {err_msg}"
        )

    return errors


def _validate_nhcx_organization(resource: dict, entry_index: int) -> List[str]:
    """NHCX-specific checks for Organization."""
    errors = []
    prefix = f"entry[{entry_index}] (Organization)"
    org_profile = _profiles.get('organization')

    # meta.profile must reference NHCX profile
    profiles = resource.get("meta", {}).get("profile", [])
    if org_profile not in profiles:
        errors.append(f"{prefix}: meta.profile must include {org_profile}")

    # Must have a name
    if not resource.get("name"):
        errors.append(f"{prefix}: missing name")

    # Should have an identifier
    if not resource.get("identifier"):
        errors.append(f"{prefix}: missing identifier")

    return errors


def _validate_nhcx_insurance_plan(resource: dict, entry_index: int) -> List[str]:
    """
    NHCX-specific checks for InsurancePlan per NRCeS IG v6.5.0.
    Mandatory fields: identifier(1..1), status(1..1), type(1..1),
    name(1..1), period(1..1), ownedBy(1..1), coverage(1..*)
    """
    errors = []
    prefix = f"entry[{entry_index}] (InsurancePlan)"
    
    # Load configuration values
    plan_profile = _profiles.get('insurance_plan')
    snomed_system = _codesystems.get('snomed')
    insuranceplan_type_system = _codesystems.get('insuranceplan_type')
    plan_type_system = _codesystems.get('plan_type')
    claim_exclusion_url = _extensions.get('claim_exclusion')
    allowed_statuses = _config.get('insuranceplan', {}).get('allowed_statuses', ['active', 'draft', 'retired'])

    # ── meta.profile ──
    profiles = resource.get("meta", {}).get("profile", [])
    if plan_profile not in profiles:
        errors.append(f"{prefix}: meta.profile must include {plan_profile}")

    # ── identifier (1..1 required) ──
    identifiers = resource.get("identifier", [])
    if not identifiers:
        errors.append(f"{prefix}: missing identifier (required 1..1 per NRCeS profile)")

    # ── status (1..1 required) ──
    if resource.get("status") not in allowed_statuses:
        errors.append(f"{prefix}: status must be {'/'.join(allowed_statuses)}")

    # ── name (1..1 required) ──
    if not resource.get("name"):
        errors.append(f"{prefix}: missing name (required 1..1)")

    # ── period (1..1 required) ──
    period = resource.get("period", {})
    if not period or not period.get("start"):
        errors.append(f"{prefix}: missing period.start (required 1..1)")

    # ── type (1..1 required, must use ndhm-insuranceplan-type) ──
    types = resource.get("type", [])
    if not types:
        errors.append(f"{prefix}: missing type (required 1..1)")
    else:
        type_codings = types[0].get("coding", [])
        if type_codings:
            system = type_codings[0].get("system", "")
            if system != insuranceplan_type_system:
                errors.append(
                    f"{prefix}: type.coding.system should be "
                    f"{insuranceplan_type_system}, got {system}"
                )

    # ── ownedBy (1..1 required, must use urn:uuid: in collection bundles) ──
    owned_by_ref = resource.get("ownedBy", {}).get("reference", "")
    if not owned_by_ref:
        errors.append(f"{prefix}: missing ownedBy.reference to Organization")
    elif not owned_by_ref.startswith("urn:uuid:"):
        errors.append(
            f"{prefix}: ownedBy.reference should use 'urn:uuid:' format "
            f"in collection bundles, got '{owned_by_ref}'"
        )

    # ── coverage (1..* required) ──
    coverages = resource.get("coverage", [])
    if not coverages:
        errors.append(f"{prefix}: missing coverage (at least one required)")
    else:
        for ci, cov in enumerate(coverages):
            # coverage.type must have SNOMED CT coding
            cov_type = cov.get("type", {})
            codings = cov_type.get("coding", [])
            if not codings:
                errors.append(
                    f"{prefix}: coverage[{ci}].type must have SNOMED CT coding"
                )
            elif codings[0].get("system") != snomed_system:
                errors.append(
                    f"{prefix}: coverage[{ci}].type.coding.system should be "
                    f"{snomed_system}, got {codings[0].get('system')}"
                )

            # coverage must have at least one benefit
            benefits = cov.get("benefit", [])
            if not benefits:
                errors.append(f"{prefix}: coverage[{ci}] has no benefits")
            else:
                for bi, ben in enumerate(benefits):
                    if not ben.get("type"):
                        errors.append(
                            f"{prefix}: coverage[{ci}].benefit[{bi}] missing type"
                        )
                    else:
                        ben_codings = ben["type"].get("coding", [])
                        if ben_codings and ben_codings[0].get("system") != snomed_system:
                            errors.append(
                                f"{prefix}: coverage[{ci}].benefit[{bi}].type.coding.system "
                                f"should be {snomed_system}"
                            )

    # ── plan section checks ──
    plans = resource.get("plan", [])
    if not plans:
        logger.warning(f"{prefix}: no plan section (costs will be missing)")
    else:
        plan = plans[0]
        # plan.type should use ndhm-plan-type
        plan_type = plan.get("type", {})
        pt_codings = plan_type.get("coding", [])
        if pt_codings:
            pt_system = pt_codings[0].get("system", "")
            if pt_system != plan_type_system:
                errors.append(
                    f"{prefix}: plan.type.coding.system should be "
                    f"{plan_type_system}, got {pt_system}"
                )
        # plan should have identifier
        if not plan.get("identifier"):
            errors.append(f"{prefix}: plan missing identifier (recommended)")

        # plan.specificCost checks — cost.type must have system
        COST_TYPE_SYSTEM = "http://terminology.hl7.org/CodeSystem/insuranceplan-cost-type"
        for si, sc in enumerate(plan.get("specificCost", [])):
            for bi, ben in enumerate(sc.get("benefit", [])):
                for ci, cost in enumerate(ben.get("cost", [])):
                    cost_codings = cost.get("type", {}).get("coding", [])
                    for coding in cost_codings:
                        if not coding.get("system"):
                            errors.append(
                                f"{prefix}: plan.specificCost[{si}].benefit[{bi}].cost[{ci}]"
                                f".type.coding missing system (should be {COST_TYPE_SYSTEM})"
                            )

    # ── extension checks (Claim-Exclusion structure) ──
    for ext in resource.get("extension", []):
        url = ext.get("url", "")
        if url == claim_exclusion_url:
            sub_urls = [se.get("url") for se in ext.get("extension", [])]
            if "category" not in sub_urls:
                errors.append(
                    f"{prefix}: Claim-Exclusion extension missing 'category' sub-extension"
                )
            if "statement" not in sub_urls:
                errors.append(
                    f"{prefix}: Claim-Exclusion extension missing 'statement' sub-extension"
                )

    return errors


def format_validation_report(errors: List[str]) -> str:
    """Format errors into a human-readable report."""
    if not errors:
        return "Validation PASSED — no errors found."

    report = f"Validation FAILED — {len(errors)} error(s):\n"
    for i, err in enumerate(errors, 1):
        report += f"  {i}. {err}\n"
    return report
