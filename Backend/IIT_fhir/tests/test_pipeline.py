"""
Tests for the NHCX Insurance Plan PDF-to-FHIR pipeline.

Tests verify compliance with NRCeS IG v6.5.0 InsurancePlan profile:
- SNOMED CT codes for coverage.type and benefit.type
- ndhm-insuranceplan-type for InsurancePlan.type
- ndhm-plan-type for plan.type
- Claim-Exclusion / Claim-Condition extensions
- Required fields: identifier, period, ownedBy
- Sum insured in plan.generalCost.cost (Money)

Run with:  python -m pytest tests/ -v
"""

import pytest
import json
import os
import sys

# Ensure project root is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mapper.nhcx_mapper import (
    map_to_fhir, _normalize_benefit_name, _get_snomed_coding,
    _get_specific_snomed_coding,
    _build_coverage, _build_plan_section, _build_exclusion_extensions,
    _build_eligibility_conditions, _parse_amount,
    SNOMED_SYSTEM, INSURANCEPLAN_TYPE_SYSTEM, PLAN_TYPE_SYSTEM,
    CLAIM_EXCLUSION_URL, CLAIM_CONDITION_URL,
    CLAIM_EXCLUSION_CODESYSTEM, NDHM_IDENTIFIER_TYPE_SYSTEM,
    NHCX_INSURANCE_PLAN_BUNDLE_PROFILE, COST_TYPE_SYSTEM,
)
from validator.fhir_validator import validate, format_validation_report
from llm.openai_llm import (
    merge_results, _dedupe_by_name, _normalize_key,
    _merge_benefit_entries, extract_relevant_sections, chunk_text,
)


# ─────────────────────────────────────────────
# Test fixtures
# ─────────────────────────────────────────────

@pytest.fixture
def sample_extracted_data():
    """Realistic structured data as the LLM would return."""
    return {
        "organization": "Bajaj Allianz General Insurance",
        "plan_name": "Health Guard Gold",
        "plan_type": "individual",
        "coverage_type": "health",
        "sum_insured": "500000",
        "currency": "INR",
        "benefits": [
            {
                "name": "In-Patient Hospitalization",
                "category": "inpatient",
                "description": "Covers all inpatient hospitalization expenses",
                "limit_amount": "500000",
                "limit_unit": "amount",
                "sub_limits": [
                    {"name": "Room Rent", "limit_amount": "5000", "limit_unit": "per_day"},
                    {"name": "ICU Charges", "limit_amount": "10000", "limit_unit": "per_day"}
                ],
                "copay_percent": "10",
                "waiting_period_value": "30",
                "waiting_period_unit": "days",
                "is_optional": False
            },
            {
                "name": "Day Care Treatment",
                "category": "daycare",
                "description": "Covers day care procedures",
                "limit_amount": "",
                "limit_unit": "no_limit",
                "sub_limits": [],
                "copay_percent": "",
                "waiting_period_value": "",
                "waiting_period_unit": "",
                "is_optional": False
            },
            {
                "name": "Ambulance Cover",
                "category": "ambulance",
                "description": "Road ambulance up to Rs 2000 per hospitalization",
                "limit_amount": "2000",
                "limit_unit": "amount",
                "sub_limits": [],
                "copay_percent": "",
                "waiting_period_value": "",
                "waiting_period_unit": "",
                "is_optional": False
            }
        ],
        "exclusions": [
            {
                "name": "Cosmetic Surgery",
                "description": "Any cosmetic or aesthetic treatment",
                "category": "permanent",
                "waiting_period_value": "",
                "waiting_period_unit": ""
            },
            {
                "name": "Pre-existing Diseases",
                "description": "48 months waiting period",
                "category": "time_bound",
                "waiting_period_value": "48",
                "waiting_period_unit": "months"
            }
        ],
        "eligibility": {
            "min_age": "18",
            "max_age": "65",
            "renewal_age": "lifelong",
            "pre_existing_waiting": "48",
            "conditions": ["Must be Indian resident"]
        },
        "network_type": "both",
        "portability": True
    }


@pytest.fixture
def minimal_data():
    """Minimum viable data."""
    return {
        "organization": "Test Insurer",
        "plan_name": "Test Plan",
        "plan_type": "individual",
        "coverage_type": "health",
        "sum_insured": "",
        "currency": "INR",
        "benefits": [
            {
                "name": "Basic Hospitalization",
                "category": "inpatient",
                "description": "Basic coverage",
                "limit_amount": "",
                "limit_unit": "",
                "sub_limits": [],
                "copay_percent": "",
                "waiting_period_value": "",
                "waiting_period_unit": "",
                "is_optional": False
            }
        ],
        "exclusions": [],
        "eligibility": {
            "min_age": "",
            "max_age": "",
            "renewal_age": "",
            "pre_existing_waiting": "",
            "conditions": []
        },
        "network_type": "",
        "portability": None
    }


@pytest.fixture
def empty_data():
    """Edge case: no meaningful data extracted."""
    return {
        "organization": "",
        "plan_name": "",
        "plan_type": "",
        "coverage_type": "",
        "sum_insured": "",
        "currency": "INR",
        "benefits": [],
        "exclusions": [],
        "eligibility": {
            "min_age": "", "max_age": "", "renewal_age": "",
            "pre_existing_waiting": "", "conditions": []
        },
        "network_type": "",
        "portability": None
    }


# ─────────────────────────────────────────────
# Mapper: Bundle structure tests
# ─────────────────────────────────────────────

class TestMapperBundle:

    def test_produces_valid_bundle(self, sample_extracted_data):
        bundle = map_to_fhir(sample_extracted_data)
        assert bundle["resourceType"] == "Bundle"
        assert bundle["type"] == "collection"
        assert len(bundle["entry"]) == 2
        assert bundle["id"]
        assert bundle["meta"]["lastUpdated"]

    def test_bundle_meta_profile(self, sample_extracted_data):
        """Bundle.meta.profile must declare InsurancePlanBundle."""
        bundle = map_to_fhir(sample_extracted_data)
        profiles = bundle["meta"]["profile"]
        assert NHCX_INSURANCE_PLAN_BUNDLE_PROFILE in profiles

    def test_bundle_meta_version_id(self, sample_extracted_data):
        """Bundle.meta.versionId should be present."""
        bundle = map_to_fhir(sample_extracted_data)
        assert bundle["meta"]["versionId"] == "1"

    def test_bundle_has_fullurl(self, sample_extracted_data):
        bundle = map_to_fhir(sample_extracted_data)
        for entry in bundle["entry"]:
            assert entry["fullUrl"].startswith("urn:uuid:")

    def test_minimal_data_produces_valid_bundle(self, minimal_data):
        bundle = map_to_fhir(minimal_data)
        assert bundle["resourceType"] == "Bundle"
        assert len(bundle["entry"]) == 2

    def test_empty_data_produces_bundle(self, empty_data):
        bundle = map_to_fhir(empty_data)
        assert bundle["resourceType"] == "Bundle"
        plan = bundle["entry"][1]["resource"]
        assert plan["name"] == "Unknown Plan"


# ─────────────────────────────────────────────
# Mapper: Organization tests
# ─────────────────────────────────────────────

class TestMapperOrganization:

    def test_organization_fields(self, sample_extracted_data):
        bundle = map_to_fhir(sample_extracted_data)
        org = bundle["entry"][0]["resource"]
        assert org["resourceType"] == "Organization"
        assert org["name"] == "Bajaj Allianz General Insurance"
        assert org["meta"]["profile"][0].endswith("Organization")
        assert org["identifier"][0]["system"] == "https://irdai.gov.in/insurer-id"
        assert org["active"] is True

    def test_organization_identifier_type(self, sample_extracted_data):
        """Organization identifier must have type with ndhm-identifier-type-code."""
        bundle = map_to_fhir(sample_extracted_data)
        org = bundle["entry"][0]["resource"]
        id_type = org["identifier"][0]["type"]
        assert id_type["coding"][0]["system"] == NDHM_IDENTIFIER_TYPE_SYSTEM
        assert id_type["coding"][0]["code"] == "ROHINI"


# ─────────────────────────────────────────────
# Mapper: InsurancePlan required fields
# ─────────────────────────────────────────────

class TestMapperInsurancePlan:

    def test_insurance_plan_basic_fields(self, sample_extracted_data):
        bundle = map_to_fhir(sample_extracted_data)
        plan = bundle["entry"][1]["resource"]
        assert plan["resourceType"] == "InsurancePlan"
        assert plan["name"] == "Health Guard Gold"
        assert plan["status"] == "active"
        assert plan["meta"]["profile"][0].endswith("InsurancePlan")
        assert plan["ownedBy"]["reference"].startswith("urn:uuid:")

    def test_has_identifier(self, sample_extracted_data):
        """NRCeS profile requires identifier 1..1."""
        bundle = map_to_fhir(sample_extracted_data)
        plan = bundle["entry"][1]["resource"]
        assert "identifier" in plan
        assert plan["identifier"][0]["system"] in ("https://irdai.gov.in/uin", "https://irdai.gov.in")
        assert plan["identifier"][0]["value"]

    def test_has_period(self, sample_extracted_data):
        """NRCeS profile requires period 1..1."""
        bundle = map_to_fhir(sample_extracted_data)
        plan = bundle["entry"][1]["resource"]
        assert "period" in plan
        assert plan["period"]["start"]
        assert plan["period"]["end"]

    def test_has_administered_by(self, sample_extracted_data):
        """NRCeS profile supports administeredBy."""
        bundle = map_to_fhir(sample_extracted_data)
        plan = bundle["entry"][1]["resource"]
        assert "administeredBy" in plan
        assert plan["administeredBy"]["reference"].startswith("urn:uuid:")

    def test_type_uses_ndhm_insuranceplan_type(self, sample_extracted_data):
        """InsurancePlan.type must use ndhm-insuranceplan-type CodeSystem."""
        bundle = map_to_fhir(sample_extracted_data)
        plan = bundle["entry"][1]["resource"]
        type_coding = plan["type"][0]["coding"][0]
        assert type_coding["system"] == INSURANCEPLAN_TYPE_SYSTEM
        assert type_coding["code"] == "01"
        assert type_coding["display"] == "Hospitalisation Indemnity Policy"

    def test_critical_illness_type(self):
        """Critical illness should use code 03."""
        data = {
            "organization": "Test", "plan_name": "CI Plan",
            "plan_type": "individual", "coverage_type": "critical_illness",
            "sum_insured": "", "currency": "INR",
            "benefits": [{"name": "CI", "category": "inpatient", "description": ""}],
            "exclusions": [], "eligibility": {}, "network_type": "",
        }
        bundle = map_to_fhir(data)
        plan = bundle["entry"][1]["resource"]
        assert plan["type"][0]["coding"][0]["code"] == "03"


# ─────────────────────────────────────────────
# Mapper: Coverage with SNOMED CT
# ─────────────────────────────────────────────

class TestMapperCoverage:

    def test_coverage_type_uses_snomed(self, sample_extracted_data):
        """coverage.type must use http://snomed.info/sct."""
        bundle = map_to_fhir(sample_extracted_data)
        plan = bundle["entry"][1]["resource"]
        for cov in plan["coverage"]:
            coding = cov["type"]["coding"][0]
            assert coding["system"] == SNOMED_SYSTEM

    def test_benefit_type_uses_snomed(self, sample_extracted_data):
        """coverage.benefit.type must use http://snomed.info/sct."""
        bundle = map_to_fhir(sample_extracted_data)
        plan = bundle["entry"][1]["resource"]
        for cov in plan["coverage"]:
            for ben in cov["benefit"]:
                coding = ben["type"]["coding"][0]
                assert coding["system"] == SNOMED_SYSTEM

    def test_benefits_grouped_by_category(self, sample_extracted_data):
        """Benefits should be grouped into separate coverage entries by category."""
        bundle = map_to_fhir(sample_extracted_data)
        plan = bundle["entry"][1]["resource"]
        # 3 benefits with categories: inpatient, daycare, ambulance → 3 coverages
        assert len(plan["coverage"]) == 3

    def test_inpatient_snomed_code(self):
        """Inpatient category should map to SNOMED 737481003."""
        coding = _get_snomed_coding("inpatient")
        assert coding["system"] == SNOMED_SYSTEM
        assert coding["code"] == "737481003"
        assert "Inpatient" in coding["display"]

    def test_ambulance_snomed_code(self):
        """Ambulance category should map to SNOMED 49122002."""
        coding = _get_snomed_coding("ambulance")
        assert coding["code"] == "49122002"
        assert "Ambulance" in coding["display"]

    def test_daycare_snomed_code(self):
        """Daycare category should map to SNOMED 737850002."""
        coding = _get_snomed_coding("daycare")
        assert coding["code"] == "737850002"

    def test_unknown_category_falls_back(self):
        """Unknown category should fall back to inpatient code."""
        coding = _get_snomed_coding("nonexistent_xyz")
        assert coding["code"] == "737481003"

    def test_specific_snomed_icu(self):
        """ICU benefit should use specific SNOMED code 309904001."""
        coding = _get_specific_snomed_coding("ICU Charges", "inpatient")
        assert coding["code"] == "309904001"
        assert coding["system"] == SNOMED_SYSTEM

    def test_specific_snomed_room_rent(self):
        """Room Rent benefit should use specific SNOMED code 224663004."""
        coding = _get_specific_snomed_coding("Room Rent", "inpatient")
        assert coding["code"] == "224663004"

    def test_specific_snomed_ambulance(self):
        """Ambulance benefit should use specific code 465341007."""
        coding = _get_specific_snomed_coding("Ambulance Cover", "ambulance")
        assert coding["code"] == "465341007"

    def test_specific_snomed_air_ambulance(self):
        """Air Ambulance should use specific code 73957001."""
        coding = _get_specific_snomed_coding("Air Ambulance", "ambulance")
        assert coding["code"] == "73957001"

    def test_specific_snomed_falls_back_to_category(self):
        """Unknown benefit name should fall back to category code."""
        coding = _get_specific_snomed_coding("Some Random Benefit", "inpatient")
        assert coding["code"] == "737481003"

    def test_specific_snomed_dialysis(self):
        """Dialysis should use specific code 108241001."""
        coding = _get_specific_snomed_coding("Dialysis Treatment", "inpatient")
        assert coding["code"] == "108241001"

    def test_specific_snomed_in_coverage_benefit(self):
        """coverage.benefit.type should use specific SNOMED codes, not category."""
        data = {
            "organization": "Test", "plan_name": "Plan",
            "plan_type": "individual", "coverage_type": "health",
            "sum_insured": "", "currency": "INR",
            "benefits": [
                {"name": "ICU Charges", "category": "inpatient", "description": ""},
                {"name": "Room Rent", "category": "inpatient", "description": ""},
            ],
            "exclusions": [], "eligibility": {}, "network_type": "",
        }
        bundle = map_to_fhir(data)
        plan = bundle["entry"][1]["resource"]
        # Both are inpatient category but should get different specific codes
        benefits = plan["coverage"][0]["benefit"]
        codes = [b["type"]["coding"][0]["code"] for b in benefits]
        assert "309904001" in codes  # ICU
        assert "224663004" in codes  # Room Rent

    def test_claim_condition_on_coverage(self, sample_extracted_data):
        """Benefits with descriptions should generate Claim-Condition extensions."""
        bundle = map_to_fhir(sample_extracted_data)
        plan = bundle["entry"][1]["resource"]
        # First coverage (inpatient) should have Claim-Condition
        inpatient_cov = plan["coverage"][0]
        assert "extension" in inpatient_cov
        ext_urls = [e["url"] for e in inpatient_cov["extension"]]
        assert CLAIM_CONDITION_URL in ext_urls

    def test_duration_limit_in_coverage(self):
        """Duration limits (days) should go in coverage.benefit.limit."""
        data = {
            "organization": "Test", "plan_name": "Plan",
            "plan_type": "individual", "coverage_type": "health",
            "sum_insured": "", "currency": "INR",
            "benefits": [{
                "name": "Post-Hosp", "category": "post_hospitalization",
                "description": "", "limit_amount": "90", "limit_unit": "days",
                "sub_limits": [], "copay_percent": "",
                "waiting_period_value": "", "waiting_period_unit": "",
            }],
            "exclusions": [], "eligibility": {}, "network_type": "",
        }
        bundle = map_to_fhir(data)
        plan = bundle["entry"][1]["resource"]
        benefit = plan["coverage"][0]["benefit"][0]
        assert "limit" in benefit
        assert benefit["limit"][0]["value"]["value"] == 90
        assert benefit["limit"][0]["value"]["comparator"] == "<="
        assert benefit["limit"][0]["value"]["unit"] == "day"


# ─────────────────────────────────────────────
# Mapper: Exclusions as Claim-Exclusion extension
# ─────────────────────────────────────────────

class TestMapperExclusions:

    def test_exclusions_as_claim_exclusion_extension(self, sample_extracted_data):
        """Exclusions must be Claim-Exclusion extensions on InsurancePlan root."""
        bundle = map_to_fhir(sample_extracted_data)
        plan = bundle["entry"][1]["resource"]
        assert "extension" in plan
        excl_exts = [e for e in plan["extension"] if e["url"] == CLAIM_EXCLUSION_URL]
        assert len(excl_exts) == 2

    def test_exclusion_has_category_and_statement(self, sample_extracted_data):
        """Claim-Exclusion must have category and statement sub-extensions."""
        bundle = map_to_fhir(sample_extracted_data)
        plan = bundle["entry"][1]["resource"]
        excl_exts = [e for e in plan["extension"] if e["url"] == CLAIM_EXCLUSION_URL]
        for ext in excl_exts:
            sub_urls = [se["url"] for se in ext["extension"]]
            assert "category" in sub_urls
            assert "statement" in sub_urls

    def test_exclusion_category_is_codeable_concept(self, sample_extracted_data):
        """Claim-Exclusion.category should be a CodeableConcept."""
        bundle = map_to_fhir(sample_extracted_data)
        plan = bundle["entry"][1]["resource"]
        excl_exts = [e for e in plan["extension"] if e["url"] == CLAIM_EXCLUSION_URL]
        cat_ext = [se for se in excl_exts[0]["extension"] if se["url"] == "category"][0]
        assert "valueCodeableConcept" in cat_ext
        assert "text" in cat_ext["valueCodeableConcept"]

    def test_exclusion_category_uses_claim_exclusion_codesystem(self, sample_extracted_data):
        """Pre-existing exclusion should use ndhm-claim-exclusion CodeSystem (Excl01)."""
        bundle = map_to_fhir(sample_extracted_data)
        plan = bundle["entry"][1]["resource"]
        excl_exts = [e for e in plan["extension"] if e["url"] == CLAIM_EXCLUSION_URL]
        # Find the pre-existing exclusion (second in sample data)
        ped_ext = excl_exts[1]  # "Pre-existing Diseases" with category=time_bound
        cat = [se for se in ped_ext["extension"] if se["url"] == "category"][0]
        codeable = cat["valueCodeableConcept"]
        assert "coding" in codeable
        assert codeable["coding"][0]["system"] == CLAIM_EXCLUSION_CODESYSTEM
        assert codeable["coding"][0]["code"] in ("Excl01", "Excl02")

    def test_permanent_exclusion_text_only(self):
        """Permanent exclusions without matching code should use text-only category."""
        data = {
            "organization": "Test", "plan_name": "Plan",
            "plan_type": "individual", "coverage_type": "health",
            "sum_insured": "", "currency": "INR",
            "benefits": [{"name": "IPD", "category": "inpatient", "description": "Test"}],
            "exclusions": [{
                "name": "Cosmetic Surgery",
                "description": "Any cosmetic treatment",
                "category": "permanent",
                "waiting_period_value": "", "waiting_period_unit": ""
            }],
            "eligibility": {}, "network_type": "",
        }
        bundle = map_to_fhir(data)
        plan = bundle["entry"][1]["resource"]
        excl_exts = [e for e in plan["extension"] if e["url"] == CLAIM_EXCLUSION_URL]
        cat = [se for se in excl_exts[0]["extension"] if se["url"] == "category"][0]
        codeable = cat["valueCodeableConcept"]
        # Permanent exclusion with no matching code → text only
        assert "text" in codeable
        assert codeable["text"] == "Cosmetic Surgery"

    def test_exclusion_waiting_period_in_statement(self):
        """Waiting period should be included in the statement text."""
        data = {
            "organization": "Test", "plan_name": "Plan",
            "plan_type": "individual", "coverage_type": "health",
            "sum_insured": "", "currency": "INR",
            "benefits": [{"name": "IPD", "category": "inpatient", "description": "Test"}],
            "exclusions": [{
                "name": "PED", "description": "Pre-existing disease exclusion",
                "category": "time_bound",
                "waiting_period_value": "48", "waiting_period_unit": "months"
            }],
            "eligibility": {}, "network_type": "",
        }
        bundle = map_to_fhir(data)
        plan = bundle["entry"][1]["resource"]
        excl_exts = [e for e in plan["extension"] if e["url"] == CLAIM_EXCLUSION_URL]
        stmt = [se for se in excl_exts[0]["extension"] if se["url"] == "statement"][0]
        assert "48 months" in stmt["valueString"]


# ─────────────────────────────────────────────
# Mapper: Plan section (generalCost, specificCost)
# ─────────────────────────────────────────────

class TestMapperPlanSection:

    def test_plan_has_identifier(self, sample_extracted_data):
        """plan.identifier should be present with use=official."""
        bundle = map_to_fhir(sample_extracted_data)
        plan = bundle["entry"][1]["resource"]
        pid = plan["plan"][0]["identifier"][0]
        assert pid["use"] == "official"
        assert pid["value"] == "Health Guard Gold"

    def test_plan_type_uses_ndhm_plan_type(self, sample_extracted_data):
        """plan.type must use ndhm-plan-type CodeSystem."""
        bundle = map_to_fhir(sample_extracted_data)
        plan = bundle["entry"][1]["resource"]
        pt = plan["plan"][0]["type"]["coding"][0]
        assert pt["system"] == PLAN_TYPE_SYSTEM
        assert pt["code"] == "01"
        assert pt["display"] == "Individual"

    def test_group_plan_type(self):
        """Group plan type should use code 03."""
        data = {
            "organization": "Test", "plan_name": "Group Plan",
            "plan_type": "group", "coverage_type": "health",
            "sum_insured": "", "currency": "INR",
            "benefits": [{"name": "IPD", "category": "inpatient", "description": ""}],
            "exclusions": [], "eligibility": {}, "network_type": "",
        }
        bundle = map_to_fhir(data)
        plan = bundle["entry"][1]["resource"]
        assert plan["plan"][0]["type"]["coding"][0]["code"] == "03"

    def test_sum_insured_in_general_cost(self, sample_extracted_data):
        """Sum insured must go in plan.generalCost.cost as Money."""
        bundle = map_to_fhir(sample_extracted_data)
        plan = bundle["entry"][1]["resource"]
        gc = plan["plan"][0]["generalCost"][0]
        assert gc["cost"]["value"] == 500000.0
        assert gc["cost"]["currency"] == "INR"

    def test_no_sum_insured_no_general_cost(self, minimal_data):
        """Without sum insured, generalCost should be absent."""
        bundle = map_to_fhir(minimal_data)
        plan = bundle["entry"][1]["resource"]
        assert "generalCost" not in plan["plan"][0]

    def test_monetary_limit_in_specific_cost(self, sample_extracted_data):
        """Monetary benefit limits should go in plan.specificCost."""
        bundle = map_to_fhir(sample_extracted_data)
        plan = bundle["entry"][1]["resource"]
        assert "specificCost" in plan["plan"][0]
        sc = plan["plan"][0]["specificCost"]
        assert len(sc) >= 1
        # Check the first specificCost has proper SNOMED category
        assert sc[0]["category"]["coding"][0]["system"] == SNOMED_SYSTEM

    def test_copay_in_specific_cost(self, sample_extracted_data):
        """Copay should appear in specificCost.benefit.cost."""
        bundle = map_to_fhir(sample_extracted_data)
        plan = bundle["entry"][1]["resource"]
        sc = plan["plan"][0]["specificCost"]
        # Find the inpatient specific cost (has copay)
        inpatient_sc = [s for s in sc if "Inpatient" in s["category"].get("text", "")
                        or "In-Patient" in s["category"].get("text", "")]
        assert len(inpatient_sc) >= 1
        costs = inpatient_sc[0]["benefit"][0]["cost"]
        copay_costs = [c for c in costs if c["type"].get("coding", [{}])[0].get("code") == "copay"]
        assert len(copay_costs) >= 1

    def test_cost_type_has_system(self, sample_extracted_data):
        """All cost.type.coding entries must have system URI (FHIR R4 requirement)."""
        bundle = map_to_fhir(sample_extracted_data)
        plan = bundle["entry"][1]["resource"]
        for sc in plan["plan"][0].get("specificCost", []):
            for ben in sc.get("benefit", []):
                for cost in ben.get("cost", []):
                    codings = cost.get("type", {}).get("coding", [])
                    for coding in codings:
                        assert coding.get("system") == COST_TYPE_SYSTEM, \
                            f"cost.type.coding must have system={COST_TYPE_SYSTEM}, got {coding}"


# ─────────────────────────────────────────────
# Mapper: Eligibility as Claim-Condition
# ─────────────────────────────────────────────

class TestMapperEligibility:

    def test_eligibility_as_claim_condition(self, sample_extracted_data):
        """Eligibility data should generate Claim-Condition extensions on coverage[0]."""
        bundle = map_to_fhir(sample_extracted_data)
        plan = bundle["entry"][1]["resource"]
        # Per NRCeS IG, Claim-Condition belongs on coverage, not root
        cov0_exts = plan["coverage"][0].get("extension", [])
        cond_exts = [e for e in cov0_exts if e["url"] == CLAIM_CONDITION_URL]
        # Should have conditions for: min_age, max_age, renewal_age, pre_existing, 1 condition
        assert len(cond_exts) >= 5
        # Must NOT be on root InsurancePlan.extension
        root_conds = [e for e in plan.get("extension", []) if e["url"] == CLAIM_CONDITION_URL]
        assert len(root_conds) == 0

    def test_no_fabricated_extensions(self, sample_extracted_data):
        """Must NOT contain fabricated InsurancePlanEligibility-* extensions."""
        bundle = map_to_fhir(sample_extracted_data)
        plan = bundle["entry"][1]["resource"]
        for ext in plan.get("extension", []):
            assert "InsurancePlanEligibility" not in ext.get("url", "")
            assert "InsurancePlan-SumInsured" not in ext.get("url", "")
            assert "WaitingPeriod" not in ext.get("url", "")


# ─────────────────────────────────────────────
# Mapper: Non-benefit filtering
# ─────────────────────────────────────────────

class TestNonBenefitFiltering:

    def test_cashless_facility_filtered(self):
        data = {
            "organization": "Test", "plan_name": "Plan",
            "plan_type": "individual", "coverage_type": "health",
            "sum_insured": "", "currency": "INR",
            "benefits": [
                {"name": "Cashless Facility", "category": "other", "description": "Cashless treatment"},
                {"name": "In-Patient Hospitalization", "category": "inpatient", "description": "Hospital stay"},
                {"name": "Co-Payment", "category": "other", "description": "Cost sharing"},
            ],
            "exclusions": [], "eligibility": {}, "network_type": "",
        }
        bundle = map_to_fhir(data)
        plan = bundle["entry"][1]["resource"]
        all_benefit_texts = []
        for cov in plan["coverage"]:
            for b in cov["benefit"]:
                all_benefit_texts.append(b["type"]["text"])
        assert "Cashless Facility" not in all_benefit_texts
        assert "Co-Payment" not in all_benefit_texts
        assert "In-Patient Hospitalization" in all_benefit_texts


# ─────────────────────────────────────────────
# Mapper: Utility function tests
# ─────────────────────────────────────────────

class TestMapperPercentageAndSubLimits:
    """Test percentage_of_si and per_day handling in specificCost."""

    def _make_data(self, benefits):
        return {
            "organization": "Test", "plan_name": "Plan",
            "plan_type": "individual", "coverage_type": "health",
            "sum_insured": "500000", "currency": "INR",
            "benefits": benefits,
            "exclusions": [], "eligibility": {}, "network_type": "",
        }

    def test_percentage_of_si_limit(self):
        """percentage_of_si limits should produce % unit in specificCost."""
        data = self._make_data([{
            "name": "Cancer Stage Payout", "category": "inpatient",
            "description": "100% of SI", "limit_amount": "100",
            "limit_unit": "percentage_of_si", "sub_limits": [],
            "copay_percent": "", "waiting_period_value": "",
            "waiting_period_unit": "", "is_optional": False,
        }])
        bundle = map_to_fhir(data)
        plan = bundle["entry"][1]["resource"]
        sc = plan["plan"][0]["specificCost"]
        assert len(sc) >= 1
        cost = sc[0]["benefit"][0]["cost"][0]
        assert cost["value"]["value"] == 100.0
        assert cost["value"]["unit"] == "%"
        assert "Sum Insured" in cost["type"].get("text", "")

    def test_sub_limit_percentage_of_si(self):
        """Sub-limits with percentage_of_si should show % unit."""
        data = self._make_data([{
            "name": "In-Patient Hospitalization", "category": "inpatient",
            "description": "IPD", "limit_amount": "", "limit_unit": "no_limit",
            "sub_limits": [
                {"name": "Room Rent", "limit_amount": "1", "limit_unit": "percentage_of_si"},
                {"name": "ICU Charges", "limit_amount": "2", "limit_unit": "percentage_of_si"},
            ],
            "copay_percent": "", "waiting_period_value": "",
            "waiting_period_unit": "", "is_optional": False,
        }])
        bundle = map_to_fhir(data)
        plan = bundle["entry"][1]["resource"]
        sc = plan["plan"][0]["specificCost"]
        # Should have specificCost entry with sub-limit costs
        inpatient_sc = [s for s in sc if "In-Patient" in s["category"].get("text", "")]
        assert len(inpatient_sc) >= 1
        costs = inpatient_sc[0]["benefit"][0]["cost"]
        assert len(costs) >= 2
        room_cost = [c for c in costs if "Room Rent" in c["type"].get("text", "")]
        assert len(room_cost) == 1
        assert room_cost[0]["value"]["unit"] == "%"
        assert room_cost[0]["value"]["value"] == 1.0

    def test_sub_limit_per_day(self):
        """Sub-limits with per_day unit should show INR/day."""
        data = self._make_data([{
            "name": "In-Patient Hospitalization", "category": "inpatient",
            "description": "IPD", "limit_amount": "", "limit_unit": "no_limit",
            "sub_limits": [
                {"name": "Room Rent", "limit_amount": "5000", "limit_unit": "per_day"},
            ],
            "copay_percent": "", "waiting_period_value": "",
            "waiting_period_unit": "", "is_optional": False,
        }])
        bundle = map_to_fhir(data)
        plan = bundle["entry"][1]["resource"]
        sc = plan["plan"][0]["specificCost"]
        inpatient_sc = [s for s in sc if "In-Patient" in s["category"].get("text", "")]
        assert len(inpatient_sc) >= 1
        costs = inpatient_sc[0]["benefit"][0]["cost"]
        room_cost = [c for c in costs if "Room Rent" in c["type"].get("text", "")]
        assert len(room_cost) == 1
        assert room_cost[0]["value"]["unit"] == "INR/day"
        assert room_cost[0]["value"]["value"] == 5000.0

    def test_monetary_limit_still_works(self):
        """Standard monetary limits should still produce INR unit."""
        data = self._make_data([{
            "name": "Ambulance Cover", "category": "ambulance",
            "description": "Ambulance", "limit_amount": "2000",
            "limit_unit": "amount", "sub_limits": [],
            "copay_percent": "", "waiting_period_value": "",
            "waiting_period_unit": "", "is_optional": False,
        }])
        bundle = map_to_fhir(data)
        plan = bundle["entry"][1]["resource"]
        sc = plan["plan"][0]["specificCost"]
        assert len(sc) >= 1
        cost = sc[0]["benefit"][0]["cost"][0]
        assert cost["value"]["value"] == 2000.0
        assert cost["value"]["unit"] == "INR"


class TestMapperUtils:

    def test_normalize_benefit_name(self):
        assert _normalize_benefit_name("opd consultation") == "OPD Expenses"
        assert _normalize_benefit_name("daycare procedures") == "Day Care Treatment"
        assert _normalize_benefit_name("unknown benefit xyz") == "unknown benefit xyz"

    def test_parse_amount(self):
        assert _parse_amount("5,00,000") == 500000.0
        assert _parse_amount("2000") == 2000.0
        assert _parse_amount("") is None
        assert _parse_amount(None) is None

    def test_get_snomed_coding_known(self):
        result = _get_snomed_coding("inpatient")
        assert result["system"] == SNOMED_SYSTEM
        assert result["code"] == "737481003"

    def test_get_snomed_coding_unknown(self):
        result = _get_snomed_coding("nonexistent_category")
        assert result["system"] == SNOMED_SYSTEM
        assert result["code"] == "737481003"  # falls back to inpatient


# ─────────────────────────────────────────────
# FHIR Model Validation tests
# ─────────────────────────────────────────────

class TestFHIRModelValidation:

    def test_organization_passes_fhir_model(self, sample_extracted_data):
        from fhir.resources.organization import Organization
        bundle = map_to_fhir(sample_extracted_data)
        org = bundle["entry"][0]["resource"]
        result = Organization.model_validate(org)
        assert result.name == "Bajaj Allianz General Insurance"

    def test_insurance_plan_passes_fhir_model(self, sample_extracted_data):
        from fhir.resources.insuranceplan import InsurancePlan
        bundle = map_to_fhir(sample_extracted_data)
        plan = bundle["entry"][1]["resource"]
        result = InsurancePlan.model_validate(plan)
        assert result.name == "Health Guard Gold"

    def test_minimal_passes_fhir_model(self, minimal_data):
        from fhir.resources.insuranceplan import InsurancePlan
        bundle = map_to_fhir(minimal_data)
        plan = bundle["entry"][1]["resource"]
        InsurancePlan.model_validate(plan)  # should not raise

    def test_empty_data_passes_fhir_model(self, empty_data):
        from fhir.resources.insuranceplan import InsurancePlan
        bundle = map_to_fhir(empty_data)
        plan = bundle["entry"][1]["resource"]
        InsurancePlan.model_validate(plan)  # should not raise


# ─────────────────────────────────────────────
# Validator tests
# ─────────────────────────────────────────────

class TestValidator:

    def test_valid_bundle_passes(self, sample_extracted_data):
        bundle = map_to_fhir(sample_extracted_data)
        errors = validate(bundle)
        assert errors == [], f"Unexpected errors: {errors}"

    def test_missing_identifier_detected(self, sample_extracted_data):
        bundle = map_to_fhir(sample_extracted_data)
        del bundle["entry"][1]["resource"]["identifier"]
        errors = validate(bundle)
        assert any("identifier" in e for e in errors)

    def test_missing_period_detected(self, sample_extracted_data):
        bundle = map_to_fhir(sample_extracted_data)
        del bundle["entry"][1]["resource"]["period"]
        errors = validate(bundle)
        assert any("period" in e for e in errors)

    def test_missing_name_detected(self, sample_extracted_data):
        bundle = map_to_fhir(sample_extracted_data)
        bundle["entry"][1]["resource"]["name"] = ""
        errors = validate(bundle)
        assert any("missing name" in e for e in errors)

    def test_missing_fullurl_detected(self, sample_extracted_data):
        bundle = map_to_fhir(sample_extracted_data)
        del bundle["entry"][0]["fullUrl"]
        errors = validate(bundle)
        assert any("missing fullUrl" in e for e in errors)

    def test_wrong_bundle_type_detected(self, sample_extracted_data):
        bundle = map_to_fhir(sample_extracted_data)
        bundle["type"] = "searchset"
        errors = validate(bundle)
        assert any("not valid for NHCX" in e for e in errors)

    def test_missing_profile_detected(self, sample_extracted_data):
        bundle = map_to_fhir(sample_extracted_data)
        bundle["entry"][1]["resource"]["meta"]["profile"] = []
        errors = validate(bundle)
        assert any("meta.profile" in e for e in errors)

    def test_missing_bundle_profile_detected(self, sample_extracted_data):
        """Validator should detect missing InsurancePlanBundle profile on Bundle."""
        bundle = map_to_fhir(sample_extracted_data)
        bundle["meta"]["profile"] = []
        errors = validate(bundle)
        assert any("InsurancePlanBundle" in e for e in errors)

    def test_ownedby_non_urn_uuid_detected(self, sample_extracted_data):
        """Validator should detect ownedBy not using urn:uuid: format."""
        bundle = map_to_fhir(sample_extracted_data)
        bundle["entry"][1]["resource"]["ownedBy"]["reference"] = "Organization/123"
        errors = validate(bundle)
        assert any("urn:uuid:" in e for e in errors)

    def test_wrong_type_codesystem_detected(self, sample_extracted_data):
        bundle = map_to_fhir(sample_extracted_data)
        bundle["entry"][1]["resource"]["type"][0]["coding"][0]["system"] = "http://wrong.system"
        errors = validate(bundle)
        assert any("ndhm-insuranceplan-type" in e for e in errors)

    def test_wrong_coverage_codesystem_detected(self, sample_extracted_data):
        bundle = map_to_fhir(sample_extracted_data)
        bundle["entry"][1]["resource"]["coverage"][0]["type"]["coding"][0]["system"] = "http://wrong"
        errors = validate(bundle)
        assert any("snomed" in e.lower() for e in errors)

    def test_format_report_passed(self):
        report = format_validation_report([])
        assert "PASSED" in report

    def test_format_report_failed(self):
        report = format_validation_report(["error1", "error2"])
        assert "FAILED" in report
        assert "2 error" in report


# ─────────────────────────────────────────────
# LLM merge / utility tests
# ─────────────────────────────────────────────

class TestLLMUtils:

    def test_merge_results_single(self):
        results = [{
            "organization": "Test Corp",
            "plan_name": "Plan A",
            "plan_type": "individual",
            "coverage_type": "health",
            "sum_insured": "500000",
            "currency": "INR",
            "benefits": [{"name": "Benefit 1", "category": "inpatient"}],
            "exclusions": [],
            "eligibility": {"min_age": "18", "max_age": "65",
                            "renewal_age": "", "pre_existing_waiting": "",
                            "conditions": []},
            "network_type": "",
            "portability": None
        }]
        final = merge_results(results)
        assert final["organization"] == "Test Corp"
        assert len(final["benefits"]) == 1

    def test_merge_results_deduplicates_benefits(self):
        results = [
            {"benefits": [{"name": "Inpatient", "category": "inpatient"}]},
            {"benefits": [
                {"name": "Inpatient", "category": "inpatient"},
                {"name": "OPD", "category": "outpatient"}
            ]}
        ]
        final = merge_results(results)
        assert len(final["benefits"]) == 2

    def test_merge_results_backward_compat_string_benefits(self):
        results = [{"benefits": ["Day Care", "Ambulance"]}]
        final = merge_results(results)
        assert len(final["benefits"]) == 2
        assert final["benefits"][0]["name"] == "Day Care"

    def test_merge_results_eligibility_merge(self):
        results = [
            {"eligibility": {"min_age": "18", "max_age": "",
                             "renewal_age": "", "pre_existing_waiting": "",
                             "conditions": []}},
            {"eligibility": {"min_age": "", "max_age": "65",
                             "renewal_age": "99", "pre_existing_waiting": "48",
                             "conditions": ["Condition A"]}}
        ]
        final = merge_results(results)
        assert final["eligibility"]["min_age"] == "18"
        assert final["eligibility"]["max_age"] == "65"
        assert final["eligibility"]["pre_existing_waiting"] == "48"
        assert "Condition A" in final["eligibility"]["conditions"]

    def test_dedupe_by_name(self):
        items = [
            {"name": "Alpha", "value": 1},
            {"name": "Beta", "value": 2},
            {"name": "alpha", "value": 3},
        ]
        result = _dedupe_by_name(items)
        assert len(result) == 2

    def test_normalize_key_variations(self):
        assert _normalize_key("In-Patient Hospitalization") == _normalize_key("Inpatient Hospitalization")
        assert _normalize_key("In-Patient Hospitalisation") == _normalize_key("Inpatient Hospitalization")

    def test_merge_benefit_entries(self):
        a = {"name": "IPD", "category": "inpatient", "description": "Stay"}
        b = {"name": "IPD", "category": "inpatient", "description": "", "limit_amount": "500000"}
        merged = _merge_benefit_entries(a, b)
        assert merged["description"] == "Stay"
        assert merged["limit_amount"] == "500000"

    def test_extract_relevant_sections_keeps_keywords(self):
        text = "This line has benefit info\nThis is random\nRoom rent is 5000\n"
        result = extract_relevant_sections(text)
        assert "random" in result

    def test_chunk_text(self):
        text = "a" * 60000
        chunks = chunk_text(text)
        assert len(chunks) == 3


# ─────────────────────────────────────────────
# PDF extractor tests
# ─────────────────────────────────────────────

class TestPDFExtractor:

    def test_import_works(self):
        from extractor.pdf import extract_text
        assert callable(extract_text)
