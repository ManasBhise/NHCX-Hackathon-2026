"""
Enhanced FHIR Validator with percentage reporting and detailed error categorization.

Validates against:
1. FHIR R4 structural rules
2. NRCeS IG v6.5.0 profile requirements
3. NHCX-specific mandatory fields

Provides:
- Percentage-based validation scores
- Categorized error reporting
- Detailed remediation suggestions

All validation rules are configurable via config/validation_rules.yaml
"""

import logging
from typing import List, Dict, Tuple
from dataclasses import dataclass
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
        # Return default config if file not found
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
        },
        'scoring': {
            'error_penalty': 5,
            'warning_penalty': 1
        },
        'remediation': {
            'bundle': {},
            'organization': {},
            'insuranceplan': {}
        }
    }


@dataclass
class ValidationError:
    """Represents a validation error with categorization."""
    category: str  # 'BUNDLE', 'ORGANIZATION', 'INSURANCEPLAN', 'FHIR', 'PROFILE'
    severity: str  # 'ERROR', 'WARNING'
    resource: str  # 'Bundle', 'Organization', 'InsurancePlan'
    field: str  # e.g., 'identifier', 'meta.profile'
    message: str  # Detailed error message
    remediation: str  # How to fix it


@dataclass
class ValidationReport:
    """Complete validation report with percentage scores."""
    valid: bool
    total_checks: int
    passed_checks: int
    failed_checks: int
    completion_percentage: float
    compliance_percentage: float
    errors: List[ValidationError]
    warnings: List[ValidationError]
    
    def get_score_breakdown(self) -> Dict[str, float]:
        """Get scores by category."""
        breakdown = {}
        categories = set()
        
        for err in self.errors + self.warnings:
            categories.add(err.category)
        
        for category in categories:
            category_errors = [e for e in self.errors if e.category == category]
            category_warnings = [w for w in self.warnings if w.category == category]
            total_issues = len(category_errors) + len(category_warnings)
            
            if total_issues > 0:
                breakdown[category] = 100 - (len(category_errors) * 2 + len(category_warnings)) * 10
                breakdown[category] = max(0, breakdown[category])
        
        return breakdown


class EnhancedValidator:
    """Enhanced FHIR validator with percentage reporting."""
    
    def __init__(self):
        self.errors: List[ValidationError] = []
        self.warnings: List[ValidationError] = []
        self.checks_performed = 0
        self.checks_passed = 0
        
        # Load configuration from YAML
        self.config = _load_validation_config()
        self.profiles = self.config.get('profiles', {})
        self.codesystems = self.config.get('codesystems', {})
        self.extensions = self.config.get('extensions', {})
        self.bundle_config = self.config.get('bundle', {})
        self.org_config = self.config.get('organization', {})
        self.plan_config = self.config.get('insuranceplan', {})
        self.scoring_config = self.config.get('scoring', {})
        self.remediation_config = self.config.get('remediation', {})
    
    def validate(self, bundle: dict) -> ValidationReport:
        """
        Validate a FHIR Bundle against FHIR R4 and NRCeS IG v6.5.0.
        
        Returns:
            ValidationReport with scores, errors, and remediation steps
        """
        self.errors = []
        self.warnings = []
        self.checks_performed = 0
        self.checks_passed = 0
        
        # Bundle level validation
        self._validate_bundle_structure(bundle)
        
        # Per-resource validation
        for i, entry in enumerate(bundle.get("entry", [])):
            resource = entry.get("resource", {})
            res_type = resource.get("resourceType", "Unknown")
            
            self._validate_resource_entry(resource, i, res_type)
            
            if res_type == "Organization":
                self._validate_nhcx_organization(resource, i)
            elif res_type == "InsurancePlan":
                self._validate_nhcx_insurance_plan(resource, i)
        
        # Calculate percentages
        completion_pct = (self.checks_passed / self.checks_performed * 100) if self.checks_performed > 0 else 0
        compliance_pct = 100 - (len(self.errors) * 5)  # Each error reduces by 5%
        compliance_pct = max(0, compliance_pct)
        
        is_valid = len(self.errors) == 0
        
        report = ValidationReport(
            valid=is_valid,
            total_checks=self.checks_performed,
            passed_checks=self.checks_passed,
            failed_checks=self.checks_performed - self.checks_passed,
            completion_percentage=completion_pct,
            compliance_percentage=compliance_pct,
            errors=self.errors,
            warnings=self.warnings
        )
        
        logger.info(
            f"Validation complete: {len(self.errors)} errors, "
            f"{len(self.warnings)} warnings, "
            f"{completion_pct:.1f}% completion, "
            f"{compliance_pct:.1f}% compliance"
        )
        
        return report
    
    def _check(self, condition: bool, message: str = "") -> None:
        """Track a check."""
        self.checks_performed += 1
        if condition:
            self.checks_passed += 1
    
    def _add_error(self, category: str, resource: str, field: str, message: str, remediation: str) -> None:
        """Add an error."""
        self.errors.append(ValidationError(
            category=category,
            severity='ERROR',
            resource=resource,
            field=field,
            message=message,
            remediation=remediation
        ))
        self._check(False)
    
    def _add_warning(self, category: str, resource: str, field: str, message: str, remediation: str) -> None:
        """Add a warning."""
        self.warnings.append(ValidationError(
            category=category,
            severity='WARNING',
            resource=resource,
            field=field,
            message=message,
            remediation=remediation
        ))
    
    def _validate_bundle_structure(self, bundle: dict) -> None:
        """Check top-level Bundle structure."""
        # Check resourceType
        self._check(bundle.get("resourceType") == "Bundle")
        if bundle.get("resourceType") != "Bundle":
            remediation = self.remediation_config.get('bundle', {}).get('resourcetype_invalid', 
                "Set resourceType to 'Bundle' at the root level")
            self._add_error(
                'BUNDLE', 'Bundle', 'resourceType',
                "resourceType must be 'Bundle'",
                remediation
            )
        
        # Check id
        self._check(bool(bundle.get("id")))
        if not bundle.get("id"):
            remediation = self.remediation_config.get('bundle', {}).get('id_missing',
                "Add a UUID to the 'id' field (e.g., '9297ca93-6746-4d2b-af8a-e2b78bde98b4')")
            self._add_error(
                'BUNDLE', 'Bundle', 'id',
                "Missing id field",
                remediation
            )
        
        # Check type - use configured allowed types
        allowed_types = self.bundle_config.get('allowed_types', ['collection', 'transaction', 'document'])
        self._check(bundle.get("type") in allowed_types)
        if bundle.get("type") not in allowed_types:
            remediation = self.remediation_config.get('bundle', {}).get('type_invalid',
                f"Set type to one of: {', '.join(allowed_types)}")
            self._add_error(
                'BUNDLE', 'Bundle', 'type',
                f"Invalid type '{bundle.get('type')}'",
                remediation
            )
        
        # Check profile - use configured profile URL
        bundle_profile = self.profiles.get('insurance_plan_bundle')
        self._check(bundle_profile in bundle.get("meta", {}).get("profile", []))
        if bundle_profile not in bundle.get("meta", {}).get("profile", []):
            remediation = self.remediation_config.get('bundle', {}).get('profile_missing',
                f"Add '{bundle_profile}' to meta.profile array")
            self._add_error(
                'PROFILE', 'Bundle', 'meta.profile',
                "Missing NRCeS InsurancePlanBundle profile",
                remediation
            )
        
        # Check entries
        entries = bundle.get("entry", [])
        self._check(len(entries) > 0)
        if not entries:
            remediation = self.remediation_config.get('bundle', {}).get('entries_missing',
                "Add Organization and InsurancePlan resources to the entry array")
            self._add_error(
                'BUNDLE', 'Bundle', 'entry',
                "No entries in bundle",
                remediation
            )
            return
        
        # Check mandatory resources
        resource_types = [e.get("resource", {}).get("resourceType") for e in entries]
        required_entries = self.bundle_config.get('required_entries', ['Organization', 'InsurancePlan'])
        
        self._check("Organization" in resource_types)
        if "Organization" not in resource_types:
            remediation = self.remediation_config.get('bundle', {}).get('organization_missing',
                "Add an Organization resource entry to the bundle")
            self._add_error(
                'BUNDLE', 'Bundle', 'entry',
                "Missing Organization resource",
                remediation
            )
        
        self._check("InsurancePlan" in resource_types)
        if "InsurancePlan" not in resource_types:
            remediation = self.remediation_config.get('bundle', {}).get('insuranceplan_missing',
                "Add an InsurancePlan resource entry to the bundle")
            self._add_error(
                'BUNDLE', 'Bundle', 'entry',
                "Missing InsurancePlan resource",
                remediation
            )
    
    def _validate_resource_entry(self, resource: dict, index: int, res_type: str) -> None:
        """Validate individual resource entry structure."""
        # Check fullUrl
        fullurl_exists = bool(resource.get("fullUrl") if isinstance(resource, dict) else False)
        self._check(fullurl_exists)
        if not fullurl_exists:
            self._add_warning(
                'FHIR', res_type, 'fullUrl',
                f"Missing fullUrl in entry[{index}]",
                f"Add fullUrl in entry[{index}] (e.g., 'urn:uuid:xxxxx')"
            )
        
        # FHIR R4 model validation
        self._validate_fhir_model(resource, index, res_type)
    
    def _validate_fhir_model(self, resource: dict, entry_index: int, res_type: str) -> None:
        """Validate resource against FHIR R4 Pydantic models."""
        try:
            if res_type == "Organization":
                from fhir.resources.organization import Organization
                # Try Pydantic v2 method first, fall back to v1
                if hasattr(Organization, 'model_validate'):
                    Organization.model_validate(resource)
                else:
                    Organization.parse_obj(resource)
                self._check(True)
            elif res_type == "InsurancePlan":
                from fhir.resources.insuranceplan import InsurancePlan
                # Try Pydantic v2 method first, fall back to v1
                if hasattr(InsurancePlan, 'model_validate'):
                    InsurancePlan.model_validate(resource)
                else:
                    InsurancePlan.parse_obj(resource)
                self._check(True)
            elif res_type == "Bundle":
                from fhir.resources.bundle import Bundle
                # Try Pydantic v2 method first, fall back to v1
                if hasattr(Bundle, 'model_validate'):
                    Bundle.model_validate(resource)
                else:
                    Bundle.parse_obj(resource)
                self._check(True)
            else:
                self._check(False)
                self._add_warning(
                    'FHIR', res_type, 'resourceType',
                    f"Unknown resourceType: {res_type}",
                    "Use standard FHIR resourceTypes (Organization, InsurancePlan, etc.)"
                )
        except Exception as e:
            self._check(False)
            err_msg = str(e)[:200]
            self._add_error(
                'FHIR', res_type, 'structure',
                f"FHIR R4 validation failed: {err_msg}",
                "Review FHIR R4 specification for correct resource structure"
            )
    
    def _validate_nhcx_organization(self, resource: dict, entry_index: int) -> None:
        """Validate Organization against NRCeS profile."""
        # Profile check - use configured profile URL
        org_profile = self.profiles.get('organization')
        self._check(org_profile in resource.get("meta", {}).get("profile", []))
        if org_profile not in resource.get("meta", {}).get("profile", []):
            remediation = self.remediation_config.get('organization', {}).get('profile_missing',
                f"Add '{org_profile}' to Organization.meta.profile")
            self._add_error(
                'PROFILE', 'Organization', 'meta.profile',
                "Missing NRCeS Organization profile",
                remediation
            )
        
        # Name check
        self._check(bool(resource.get("name")))
        if not resource.get("name"):
            remediation = self.remediation_config.get('organization', {}).get('name_missing',
                "Add the organization name (e.g., 'Bajaj Allianz Insurance')")
            self._add_error(
                'ORGANIZATION', 'Organization', 'name',
                "Missing organization name",
                remediation
            )
        
        # Identifier check
        self._check(bool(resource.get("identifier")))
        if not resource.get("identifier"):
            remediation = self.remediation_config.get('organization', {}).get('identifier_missing',
                "Add IRDAI registration identifier to Organization.identifier array")
            self._add_error(
                'ORGANIZATION', 'Organization', 'identifier',
                "Missing identifier",
                remediation
            )
    
    def _validate_nhcx_insurance_plan(self, resource: dict, entry_index: int) -> None:
        """Validate InsurancePlan against NRCeS IG v6.5.0."""
        # Profile - use configured profile URL
        plan_profile = self.profiles.get('insurance_plan')
        self._check(plan_profile in resource.get("meta", {}).get("profile", []))
        if plan_profile not in resource.get("meta", {}).get("profile", []):
            remediation = self.remediation_config.get('insuranceplan', {}).get('profile_missing',
                f"Add '{plan_profile}' to meta.profile")
            self._add_error(
                'PROFILE', 'InsurancePlan', 'meta.profile',
                "Missing NRCeS InsurancePlan profile",
                remediation
            )
        
        # Identifier
        identifiers = resource.get("identifier", [])
        self._check(len(identifiers) > 0)
        if not identifiers:
            remediation = self.remediation_config.get('insuranceplan', {}).get('identifier_missing',
                "Add UIN to InsurancePlan.identifier array")
            self._add_error(
                'INSURANCEPLAN', 'InsurancePlan', 'identifier',
                "Missing identifier (required 1..1)",
                remediation
            )
        
        # Status - use configured allowed statuses
        allowed_statuses = self.plan_config.get('allowed_statuses', ['active', 'draft', 'retired'])
        self._check(resource.get("status") in allowed_statuses)
        if resource.get("status") not in allowed_statuses:
            remediation = self.remediation_config.get('insuranceplan', {}).get('status_invalid',
                f"Set status to one of: {', '.join(allowed_statuses)}")
            self._add_error(
                'INSURANCEPLAN', 'InsurancePlan', 'status',
                f"Invalid status: {resource.get('status')}",
                remediation
            )
        
        # Name
        self._check(bool(resource.get("name")))
        if not resource.get("name"):
            remediation = self.remediation_config.get('insuranceplan', {}).get('name_missing',
                "Add the insurance plan name (e.g., 'Global Health Care')")
            self._add_error(
                'INSURANCEPLAN', 'InsurancePlan', 'name',
                "Missing plan name",
                remediation
            )
        
        # Period
        period = resource.get("period", {})
        self._check(bool(period.get("start")))
        if not period or not period.get("start"):
            remediation = self.remediation_config.get('insuranceplan', {}).get('period_start_missing',
                "Add policy start date in YYYY-MM-DD format")
            self._add_error(
                'INSURANCEPLAN', 'InsurancePlan', 'period.start',
                "Missing period.start (required 1..1)",
                remediation
            )
        
        # Type
        types = resource.get("type", [])
        self._check(len(types) > 0)
        if not types:
            remediation = self.remediation_config.get('insuranceplan', {}).get('type_missing',
                "Add insurance plan type with SNOMED coding")
            self._add_error(
                'INSURANCEPLAN', 'InsurancePlan', 'type',
                "Missing type (required 1..1)",
                remediation
            )
        elif types:
            plan_type_system = self.codesystems.get('insuranceplan_type')
            system = types[0].get("coding", [{}])[0].get("system", "")
            self._check(system == plan_type_system)
            if system != plan_type_system:
                remediation = self.remediation_config.get('insuranceplan', {}).get('type_codesystem_wrong',
                    f"Use '{plan_type_system}'")
                self._add_warning(
                    'PROFILE', 'InsurancePlan', 'type.coding.system',
                    f"Wrong CodeSystem: {system}",
                    remediation
                )
        
        # OwnedBy
        owned_by = resource.get("ownedBy", {}).get("reference", "")
        self._check(bool(owned_by))
        if not owned_by:
            remediation = self.remediation_config.get('insuranceplan', {}).get('ownedby_missing',
                "Add reference to Organization that owns this plan")
            self._add_error(
                'INSURANCEPLAN', 'InsurancePlan', 'ownedBy',
                "Missing ownedBy reference to Organization",
                remediation
            )
        
        # Coverage
        coverages = resource.get("coverage", [])
        self._check(len(coverages) > 0)
        if not coverages:
            remediation = self.remediation_config.get('insuranceplan', {}).get('coverage_missing',
                "Add coverage types with benefits")
            self._add_error(
                'INSURANCEPLAN', 'InsurancePlan', 'coverage',
                "Missing coverage (at least one required)",
                remediation
            )
        else:
            snomed_system = self.codesystems.get('snomed')
            for ci, cov in enumerate(coverages):
                # Coverage type coding
                codings = cov.get("type", {}).get("coding", [])
                self._check(len(codings) > 0)
                if codings and codings[0].get("system") != snomed_system:
                    remediation = self.remediation_config.get('insuranceplan', {}).get('type_codesystem_wrong',
                        f"Use '{snomed_system}' for coverage types")
                    self._add_warning(
                        'PROFILE', 'InsurancePlan', f'coverage[{ci}].type.coding.system',
                        f"Missing or wrong SNOMED system",
                        remediation
                    )
                
                # Benefits
                benefits = cov.get("benefit", [])
                self._check(len(benefits) > 0)
                if not benefits:
                    self._add_error(
                        'INSURANCEPLAN', 'InsurancePlan', f'coverage[{ci}].benefit',
                        f"Coverage[{ci}] has no benefits",
                        "Add at least one benefit to each coverage"
                    )


def validate_with_percentage(bundle: dict) -> ValidationReport:
    """
    Validate a bundle and return detailed percentage-based report.
    
    Args:
        bundle: FHIR Bundle to validate
    
    Returns:
        ValidationReport with compliance percentages and error details
    """
    validator = EnhancedValidator()
    return validator.validate(bundle)


def format_percentage_report(report: ValidationReport) -> str:
    """Format validation report with percentages."""
    lines = []
    
    lines.append("=" * 80)
    lines.append("NHCX/FHIR VALIDATION REPORT".center(80))
    lines.append("=" * 80)
    lines.append("")
    
    # Overall scores
    lines.append(f"OVERALL STATUS: {'✓ VALID' if report.valid else '✗ INVALID'}")
    lines.append("")
    lines.append(f"Completion Score:    {report.completion_percentage:6.1f}%  ({report.passed_checks}/{report.total_checks} checks passed)")
    lines.append(f"Compliance Score:    {report.compliance_percentage:6.1f}%  ({len(report.errors)} errors, {len(report.warnings)} warnings)")
    lines.append("")
    
    # Score breakdown by category
    breakdown = report.get_score_breakdown()
    if breakdown:
        lines.append("SCORE BREAKDOWN BY CATEGORY:")
        for category in sorted(breakdown.keys()):
            score = breakdown[category]
            lines.append(f"  {category:20s} {score:6.1f}%")
        lines.append("")
    
    # Errors
    if report.errors:
        lines.append(f"ERRORS ({len(report.errors)}):")
        for i, err in enumerate(report.errors, 1):
            lines.append(f"  {i}. [{err.category}] {err.field}: {err.message}")
            lines.append(f"     → Fix: {err.remediation}")
        lines.append("")
    
    # Warnings
    if report.warnings:
        lines.append(f"WARNINGS ({len(report.warnings)}):")
        for i, warn in enumerate(report.warnings, 1):
            lines.append(f"  {i}. [{warn.category}] {warn.field}: {warn.message}")
            lines.append(f"     → Fix: {warn.remediation}")
        lines.append("")
    
    lines.append("=" * 80)
    
    return"\n".join(lines)


# Keep legacy function for backward compatibility
def validate(bundle: dict) -> List[str]:
    """Legacy validation function - returns list of error strings."""
    report = validate_with_percentage(bundle)
    errors = [f"{e.field}: {e.message} — {e.remediation}" for e in report.errors]
    return errors


def format_validation_report(errors: List[str]) -> str:
    """Legacy format function."""
    if not errors:
        return "✓ Validation PASSED — No errors found."
    
    report = f"✗ Validation FAILED — {len(errors)} error(s):\n"
    for i, err in enumerate(errors, 1):
        report += f"  {i}. {err}\n"
    return report
