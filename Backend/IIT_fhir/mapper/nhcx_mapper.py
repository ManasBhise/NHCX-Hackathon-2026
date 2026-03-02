"""
NHCX-compliant FHIR InsurancePlan mapper.

Maps LLM-extracted insurance data to FHIR R4 Bundles that conform to
the NRCeS IG v6.5.0 InsurancePlan profile.

All CodeSystems, ValueSets, extension URLs, and structural patterns
are sourced from:
  https://nrces.in/ndhm/fhir/r4/StructureDefinition-InsurancePlan.html
  https://nrces.in/ndhm/fhir/r4/InsurancePlan-example-01.json.html
"""

import uuid
import yaml
import logging
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────
# NHCX Profile URLs (NRCeS IG v6.5.0)
# ──────────────────────────────────────────────────────────
NHCX_INSURANCE_PLAN_PROFILE = "https://nrces.in/ndhm/fhir/r4/StructureDefinition/InsurancePlan"
NHCX_ORGANIZATION_PROFILE = "https://nrces.in/ndhm/fhir/r4/StructureDefinition/Organization"
NHCX_INSURANCE_PLAN_BUNDLE_PROFILE = "https://nrces.in/ndhm/fhir/r4/StructureDefinition/InsurancePlanBundle"

# ──────────────────────────────────────────────────────────
# NRCeS CodeSystem URLs (NRCeS IG v6.5.0)
# ──────────────────────────────────────────────────────────
SNOMED_SYSTEM = "http://snomed.info/sct"
INSURANCEPLAN_TYPE_SYSTEM = "https://nrces.in/ndhm/fhir/r4/CodeSystem/ndhm-insuranceplan-type"
PLAN_TYPE_SYSTEM = "https://nrces.in/ndhm/fhir/r4/CodeSystem/ndhm-plan-type"
CLAIM_EXCLUSION_CODESYSTEM = "https://nrces.in/ndhm/fhir/r4/CodeSystem/ndhm-claim-exclusion"
NDHM_IDENTIFIER_TYPE_SYSTEM = "https://nrces.in/ndhm/fhir/r4/CodeSystem/ndhm-identifier-type-code"
COST_TYPE_SYSTEM = "http://terminology.hl7.org/CodeSystem/insuranceplan-cost-type"

# ──────────────────────────────────────────────────────────
# NRCeS Extension URLs (NRCeS IG v6.5.0)
# ──────────────────────────────────────────────────────────
CLAIM_EXCLUSION_URL = "https://nrces.in/ndhm/fhir/r4/StructureDefinition/Claim-Exclusion"
CLAIM_CONDITION_URL = "https://nrces.in/ndhm/fhir/r4/StructureDefinition/Claim-Condition"

# ──────────────────────────────────────────────────────────
# Load benefit name normalization from config
# ──────────────────────────────────────────────────────────
try:
    with open("config/mapping.yaml", "r") as f:
        MAPPING_CONFIG = yaml.safe_load(f)
except FileNotFoundError:
    MAPPING_CONFIG = {"benefit_mapping": {}, "coverage_types": {}}
    logger.warning("mapping.yaml not found, using empty defaults")

# ──────────────────────────────────────────────────────────
# SNOMED CT codes for coverage types and benefit types
# Source: NRCeS ValueSet ndhm-coverage-type / ndhm-benefit-type
# All entries use system http://snomed.info/sct
# ──────────────────────────────────────────────────────────
SNOMED_BENEFIT_MAP = {
    "inpatient":            {"code": "737481003", "display": "Inpatient care management (procedure)"},
    "outpatient":           {"code": "737492002", "display": "Outpatient care management (procedure)"},
    "daycare":              {"code": "737850002", "display": "Day care case management"},
    "pre_hospitalization":  {"code": "409972000", "display": "Pre-hospital care (situation)"},
    "post_hospitalization": {"code": "710967003", "display": "Management of health status after discharge from hospital (procedure)"},
    "ambulance":            {"code": "49122002",  "display": "Ambulance, device (physical object)"},
    "organ_donor":          {"code": "51032003",  "display": "Hospital admission, donor for transplant organ (procedure)"},
    "ayush":                {"code": "1259939000","display": "Ayurveda medicine (qualifier value)"},
    "mental_health":        {"code": "410225009", "display": "Mental health care management (procedure)"},
    "rehabilitation":       {"code": "410083007", "display": "Rehabilitation therapy management (procedure)"},
    "domiciliary":          {"code": "60689008",  "display": "Home care of patient (regime/therapy)"},
    "dental":               {"code": "410345004", "display": "Medical/dental care case management (procedure)"},
    "maternity":            {"code": "737481003", "display": "Inpatient care management (procedure)"},
    "other":                {"code": "737481003", "display": "Inpatient care management (procedure)"},
}

# InsurancePlan product type codes
# Source: NRCeS CodeSystem ndhm-insuranceplan-type
INSURANCEPLAN_TYPE_MAP = {
    "health":           {"code": "01", "display": "Hospitalisation Indemnity Policy"},
    "accident":         {"code": "01", "display": "Hospitalisation Indemnity Policy"},
    "critical_illness": {"code": "03", "display": "Critical Illness Cover -Indemnity"},
    "top_up":           {"code": "09", "display": "Package Policy (covering more than one type of health above)"},
}

# Plan type codes
# Source: NRCeS CodeSystem ndhm-plan-type
PLAN_TYPE_MAP = {
    "individual":      {"code": "01", "display": "Individual"},
    "family_floater":  {"code": "02", "display": "Individual Floater"},
    "group":           {"code": "03", "display": "Group"},
}

# ──────────────────────────────────────────────────────────
# Claim-Exclusion CodeSystem codes (ndhm-claim-exclusion)
# Source: https://nrces.in/ndhm/fhir/r4/CodeSystem-ndhm-claim-exclusion.html
# ──────────────────────────────────────────────────────────
CLAIM_EXCLUSION_CODES = {
    # Excl01 - Pre-Existing Diseases
    "pre-existing":       {"code": "Excl01", "display": "Pre-Existing Diseases"},
    "pre_existing":       {"code": "Excl01", "display": "Pre-Existing Diseases"},
    "ped":                {"code": "Excl01", "display": "Pre-Existing Diseases"},
    # Excl02 - Specified disease/procedure waiting period
    "time_bound":         {"code": "Excl02", "display": "Specified disease/procedure waiting period"},
    "waiting":            {"code": "Excl02", "display": "Specified disease/procedure waiting period"},
    "specified disease":  {"code": "Excl02", "display": "Specified disease/procedure waiting period"},
    "specific waiting":   {"code": "Excl02", "display": "Specified disease/procedure waiting period"},
    # Excl03 - 30-day waiting period
    "30 day":             {"code": "Excl03", "display": "30-day waiting period"},
    "first 30":           {"code": "Excl03", "display": "30-day waiting period"},
    "initial waiting":    {"code": "Excl03", "display": "30-day waiting period"},
    # Excl04 - War/nuclear
    "war":                {"code": "Excl04", "display": "War and war-like perils"},
    "act of war":         {"code": "Excl04", "display": "War and war-like perils"},
    "nuclear":            {"code": "Excl04", "display": "War and war-like perils"},
    # Excl05 - Breach of law
    "breach of law":      {"code": "Excl05", "display": "Breach of law"},
    "criminal":           {"code": "Excl05", "display": "Breach of law"},
    # Excl06 - Hazardous/adventure sports
    "hazardous":          {"code": "Excl06", "display": "Hazardous/adventure sports"},
    "adventure sport":    {"code": "Excl06", "display": "Hazardous/adventure sports"},
    # Excl07 - Suicide/self-inflicted
    "suicide":            {"code": "Excl07", "display": "Suicide and self-inflicted injuries"},
    "self-inflicted":     {"code": "Excl07", "display": "Suicide and self-inflicted injuries"},
    "self inflicted":     {"code": "Excl07", "display": "Suicide and self-inflicted injuries"},
    # Excl08 - Alcohol/substance abuse
    "alcohol":            {"code": "Excl08", "display": "Alcohol and substance abuse"},
    "substance abuse":    {"code": "Excl08", "display": "Alcohol and substance abuse"},
    "drug":               {"code": "Excl08", "display": "Alcohol and substance abuse"},
    # Excl09 - HIV/AIDS
    "hiv":                {"code": "Excl09", "display": "HIV/AIDS"},
    "aids":               {"code": "Excl09", "display": "HIV/AIDS"},
    # Excl10 - Refractive error
    "refractive":         {"code": "Excl10", "display": "Refractive error correction"},
    "spectacle":          {"code": "Excl10", "display": "Refractive error correction"},
    # Excl11 - Cosmetic/plastic surgery
    "cosmetic":           {"code": "Excl11", "display": "Cosmetic or plastic surgery"},
    "plastic surgery":    {"code": "Excl11", "display": "Cosmetic or plastic surgery"},
    # Excl12 - Circumcision
    "circumcision":       {"code": "Excl12", "display": "Circumcision"},
    # Excl13 - Gender change
    "gender change":      {"code": "Excl13", "display": "Gender change treatment"},
    "sex change":         {"code": "Excl13", "display": "Gender change treatment"},
    # Excl14 - Non-allopathic treatment
    "non-allopathic":     {"code": "Excl14", "display": "Non-allopathic treatment"},
    "non allopathic":     {"code": "Excl14", "display": "Non-allopathic treatment"},
    # Excl15 - Experimental/unproven treatment
    "experimental":       {"code": "Excl15", "display": "Experimental or unproven treatment"},
    "unproven":           {"code": "Excl15", "display": "Experimental or unproven treatment"},
    # Excl16 - Preventive care
    "preventive care":    {"code": "Excl16", "display": "Preventive care and vaccination"},
    "vaccination":        {"code": "Excl16", "display": "Preventive care and vaccination"},
    # Excl17 - Hearing aid
    "hearing aid":        {"code": "Excl17", "display": "Hearing aid"},
    # Excl18 - Dental
    "dental exclusion":   {"code": "Excl18", "display": "Dental treatment exclusion"},
    # Age/congenital
    "congenital":         {"code": "Excl02", "display": "Specified disease/procedure waiting period"},
    "maternity":          {"code": "Excl02", "display": "Specified disease/procedure waiting period"},
    "infertility":        {"code": "Excl02", "display": "Specified disease/procedure waiting period"},
}

# ──────────────────────────────────────────────────────────
# Specific SNOMED CT codes for individual benefit types
# Source: NRCeS ValueSet ndhm-benefit-type (45 codes)
# These map benefit names to the most specific code available,
# falling back to the category code from SNOMED_BENEFIT_MAP.
# ──────────────────────────────────────────────────────────
SNOMED_SPECIFIC_BENEFIT_MAP = {
    "icu":               {"code": "309904001", "display": "Intensive care unit (environment)"},
    "intensive care":    {"code": "309904001", "display": "Intensive care unit (environment)"},
    "room rent":         {"code": "224663004", "display": "Single room (environment)"},
    "room charges":      {"code": "224663004", "display": "Single room (environment)"},
    "blood":             {"code": "87612001",  "display": "Blood (substance)"},
    "oxygen":            {"code": "24099007",  "display": "Oxygen (substance)"},
    "organ donor":       {"code": "105461009", "display": "Organ donor (person)"},
    "living donor":      {"code": "105461009", "display": "Organ donor (person)"},
    "consultation":      {"code": "11429006",  "display": "Consultation (procedure)"},
    "surgery":           {"code": "387713003", "display": "Surgical procedure (procedure)"},
    "surgical":          {"code": "387713003", "display": "Surgical procedure (procedure)"},
    "medicine":          {"code": "763158003", "display": "Medicinal product (product)"},
    "mental":            {"code": "75516001",  "display": "Psychotherapy (regime/therapy)"},
    "psychiatric":       {"code": "75516001",  "display": "Psychotherapy (regime/therapy)"},
    "physiotherapy":     {"code": "91251008",  "display": "Physical therapy procedure (regime/therapy)"},
    "rehabilitation":    {"code": "91251008",  "display": "Physical therapy procedure (regime/therapy)"},
    "laboratory":        {"code": "15220000",  "display": "Laboratory test (procedure)"},
    "lab test":          {"code": "15220000",  "display": "Laboratory test (procedure)"},
    "diagnostic":        {"code": "16310003",  "display": "Diagnostic ultrasonography (procedure)"},
    "ecg":               {"code": "29303009",  "display": "Electrocardiographic procedure (procedure)"},
    "dialysis":          {"code": "108241001", "display": "Dialysis procedure (procedure)"},
    "chemotherapy":      {"code": "367336001", "display": "Chemotherapy (procedure)"},
    "radiotherapy":      {"code": "367336001", "display": "Chemotherapy (procedure)"},
    "health check":      {"code": "275926002", "display": "Health check (procedure)"},
    "vaccination":       {"code": "33879002",  "display": "Vaccination (procedure)"},
    "immunization":      {"code": "33879002",  "display": "Vaccination (procedure)"},
    "eye care":          {"code": "385907003", "display": "Eye care (procedure)"},
    "dental":            {"code": "410345004", "display": "Medical/dental care case management"},
    "ambulance":         {"code": "465341007", "display": "Automobile ambulance (physical object)"},
    "road ambulance":    {"code": "465341007", "display": "Automobile ambulance (physical object)"},
    "air ambulance":     {"code": "73957001",  "display": "Air ambulance (physical object)"},
    "angiography":       {"code": "77343006",  "display": "Angiography (procedure)"},
    "robotic surgery":   {"code": "711364006", "display": "Robotic assisted procedure"},
    "stem cell":         {"code": "1269349006","display": "Transplantation of stem cell"},
    "immunotherapy":     {"code": "76334006",  "display": "Immunotherapy (procedure)"},
    "homeopathic":       {"code": "1259938008","display": "Homeopathy (qualifier value)"},
    "homeopathy":        {"code": "1259938008","display": "Homeopathy (qualifier value)"},
    "ayurvedic":         {"code": "1259939000","display": "Ayurveda (qualifier value)"},
    "ayurveda":          {"code": "1259939000","display": "Ayurveda (qualifier value)"},
    "ayush":             {"code": "1259939000","display": "Ayurveda (qualifier value)"},
    "yoga":              {"code": "1259940003","display": "Yoga (qualifier value)"},
    "unani":             {"code": "1259218001","display": "Unani medicine (qualifier value)"},
    "siddha":            {"code": "1259219009","display": "Siddha medicine (qualifier value)"},
    "naturopathy":       {"code": "1259939000","display": "Ayurveda (qualifier value)"},
    "hospital equipment":{"code": "272181003", "display": "Clinical equipment (physical object)"},
    "clinical equipment":{"code": "272181003", "display": "Clinical equipment (physical object)"},
    "hospital unit":     {"code": "568291000005106", "display": "Hospital unit (environment)"},
    "advance care":      {"code": "713603004", "display": "Advance care planning (procedure)"},
    "oral chemo":        {"code": "266719004", "display": "Oral chemotherapy (procedure)"},
    "bronchial":         {"code": "713348007", "display": "Bronchial thermoplasty (procedure)"},
}

# Items that are plan features, NOT actual coverage benefits
NON_BENEFIT_KEYWORDS = {
    "cashless facility", "cashless", "co-payment", "co payment",
    "copay", "copayment", "deductible", "cumulative bonus",
    "no claim bonus", "portability", "free look period",
    "free look", "premium", "cooling off", "cancellation",
    "moratorium", "grace period",
}


# ──────────────────────────────────────────────────────────
# Helper functions
# ──────────────────────────────────────────────────────────

def _make_uuid():
    return str(uuid.uuid4())


def _make_urn(uid):
    return f"urn:uuid:{uid}"


def _normalize_benefit_name(name):
    """Use mapping.yaml to normalize benefit names if a match exists."""
    benefit_map = MAPPING_CONFIG.get("benefit_mapping", {})
    name_lower = name.lower().strip()
    for key, display in benefit_map.items():
        if key in name_lower:
            return display
    return name


def _parse_amount(raw):
    """Parse a monetary string to float. Handles Indian formats: Lakh, Crore, ₹, Rs., commas.
    Returns None on failure."""
    if not raw:
        return None
    try:
        s = str(raw).strip()
        # Remove currency symbols and words
        s = s.replace("₹", "").replace("Rs.", "").replace("Rs", "").replace(",", "").strip()

        # Handle Lakh/Crore suffixes
        lower = s.lower()
        if "crore" in lower:
            base = float(lower.replace("crore", "").strip())
            return base * 10000000
        if "lakh" in lower or "lac" in lower:
            base = float(lower.replace("lakh", "").replace("lac", "").strip())
            return base * 100000

        # Remove trailing % if present (for percentages)
        s = s.rstrip("%").strip()

        if not s:
            return None

        n = float(s)
        return n if n != 0 else None
    except (ValueError, TypeError, AttributeError):
        return None


def _get_snomed_coding(category):
    """Return a SNOMED CT coding dict for a benefit/coverage category."""
    cat = category.lower().strip() if category else "other"
    entry = SNOMED_BENEFIT_MAP.get(cat, SNOMED_BENEFIT_MAP["other"])
    return {
        "system": SNOMED_SYSTEM,
        "code": entry["code"],
        "display": entry["display"]
    }


def _get_specific_snomed_coding(benefit_name, category):
    """
    Get the most specific SNOMED code for a benefit by name,
    falling back to the broad category code if no specific match.

    Uses SNOMED_SPECIFIC_BENEFIT_MAP (from ndhm-benefit-type ValueSet)
    for fine-grained codes like ICU=309904001, Blood=87612001,
    instead of always returning the parent category code.

    Matches longer keys first to avoid substring collisions
    (e.g., "air ambulance" vs "ambulance").
    """
    name_lower = benefit_name.lower().strip()
    # Sort by key length descending to prefer longer (more specific) matches
    for key in sorted(SNOMED_SPECIFIC_BENEFIT_MAP, key=len, reverse=True):
        if key in name_lower:
            entry = SNOMED_SPECIFIC_BENEFIT_MAP[key]
            return {
                "system": SNOMED_SYSTEM,
                "code": entry["code"],
                "display": entry["display"]
            }
    # Fall back to category-level code
    return _get_snomed_coding(category)


def _timestamp():
    """Return current UTC timestamp in FHIR instant format."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def _today_str():
    """Return today's date in FHIR date format."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _next_year_str():
    """Return date one year from now in FHIR date format."""
    return (datetime.now(timezone.utc) + timedelta(days=365)).strftime("%Y-%m-%d")


# ──────────────────────────────────────────────────────────
# Coverage builder
# ──────────────────────────────────────────────────────────

def _build_coverage(data):
    """
    Build InsurancePlan.coverage[] grouped by benefit category.

    Per NRCeS IG v6.5.0:
    - coverage.type uses SNOMED CT (ValueSet ndhm-coverage-type)
    - coverage.benefit.type uses SNOMED CT (ValueSet ndhm-benefit-type)
    - Each category group becomes a separate coverage entry
    - Claim-Condition extensions carry benefit descriptions

    Reference: https://nrces.in/ndhm/fhir/r4/InsurancePlan-example-01.json.html
    """
    # Group benefits by category
    groups = {}  # category -> [benefit_dicts]
    for b in data.get("benefits", []):
        if not isinstance(b, dict):
            b = {"name": str(b), "category": "other", "description": ""}
        name = b.get("name", "")
        category = b.get("category", "other")

        # Skip non-benefit items
        if name.lower().strip() in NON_BENEFIT_KEYWORDS:
            logger.debug(f"Filtered non-benefit item: {name}")
            continue

        groups.setdefault(category, []).append(b)

    # If no benefits, create a minimal coverage (coverage 1..* is required)
    if not groups:
        groups["other"] = [{"name": "General Coverage", "category": "other", "description": ""}]

    coverages = []
    for category, benefits in groups.items():
        coverage_coding = _get_snomed_coding(category)

        # Build benefit entries within this coverage
        benefit_entries = []
        for b in benefits:
            name = b.get("name", "") if isinstance(b, dict) else str(b)
            normalized = _normalize_benefit_name(name)

            benefit_entry = {
                "type": {
                    "coding": [_get_specific_snomed_coding(
                        name or "",
                        b.get("category", category) if isinstance(b, dict) else category
                    )],
                    "text": normalized or name
                }
            }

            # Duration-based limits go in coverage.benefit.limit
            # Per official example: Quantity with value + comparator + unit
            if isinstance(b, dict) and b.get("limit_unit") == "days" and b.get("limit_amount"):
                try:
                    days = int(float(str(b["limit_amount"]).replace(",", "")))
                    if days > 0:
                        benefit_entry["limit"] = [{
                            "value": {
                                "value": days,
                                "comparator": "<=",
                                "unit": "day"
                            }
                        }]
                except (ValueError, TypeError):
                    pass

            benefit_entries.append(benefit_entry)

        # Build coverage entry
        coverage_entry = {
            "type": {
                "coding": [coverage_coding]
            },
            "benefit": benefit_entries
        }

        # Add Claim-Condition extensions for benefits with descriptions
        # Per NRCeS extension: Claim-Condition on coverage level
        claim_conditions = []
        for b in benefits:
            desc = b.get("description", "") if isinstance(b, dict) else ""
            if desc:
                claim_conditions.append({
                    "extension": [
                        {"url": "claim-condition", "valueString": desc}
                    ],
                    "url": CLAIM_CONDITION_URL
                })
        if claim_conditions:
            coverage_entry["extension"] = claim_conditions

        coverages.append(coverage_entry)

    return coverages


# ──────────────────────────────────────────────────────────
# Exclusion extensions builder
# ──────────────────────────────────────────────────────────

def _build_exclusion_extensions(data):
    """
    Build Claim-Exclusion extensions for the root InsurancePlan.

    Per NRCeS StructureDefinition/Claim-Exclusion:
    - category: CodeableConcept (exclusion category name)
    - statement: string (description including waiting period)
    - item: CodeableConcept (optional specific excluded items)

    Reference: https://nrces.in/ndhm/fhir/r4/StructureDefinition-Claim-Exclusion.html
    """
    extensions = []

    for exc in data.get("exclusions", []):
        if not isinstance(exc, dict):
            exc = {"name": str(exc), "description": str(exc), "category": "permanent"}

        name = exc.get("name", "")
        desc = exc.get("description", name)
        category = exc.get("category", "permanent").lower().strip()
        wp_val = exc.get("waiting_period_value", "")
        wp_unit = exc.get("waiting_period_unit", "")

        # Build statement with waiting period info
        statement = desc
        if wp_val and wp_unit:
            if wp_unit not in ("days", "months", "years"):
                wp_unit = "days"
            statement += f" (Waiting period: {wp_val} {wp_unit})"

        # Map category to ndhm-claim-exclusion CodeSystem code
        # Excl01 = Pre-Existing Diseases, Excl02 = Specified disease waiting
        category_codeable = {}
        excl_code_entry = None

        # Combined text for validation: name + description + statement
        _combined_text = f"{name} {desc} {statement}".lower()

        # Validation keywords: each IRDAI code must have at least one keyword
        # present in the exclusion text. If none match, the code is rejected.
        _code_validators = {
            "Excl01": ["pre-existing", "pre_existing", "pre existing", "ped"],
            "Excl02": ["specified disease", "waiting period", "listed condition"],
            "Excl03": ["30 day", "30-day", "first 30", "initial waiting"],
            "Excl04": ["war", "nuclear", "hostilities", "invasion", "act of foreign"],
            "Excl05": ["breach of law", "criminal", "illegal act"],
            "Excl06": ["hazardous", "adventure sport", "extreme sport"],
            "Excl07": ["suicide", "self-inflicted", "self inflicted", "intentional self-injury"],
            "Excl08": ["alcohol", "substance abuse", "drug abuse", "intoxicat"],
            "Excl09": ["hiv", "aids", "human immunodeficiency"],
            "Excl10": ["refractive", "spectacle", "contact lens", "lasik"],
            "Excl11": ["cosmetic", "plastic surgery"],
            "Excl12": ["circumcision"],
            "Excl13": ["gender change", "sex change", "change of gender"],
            "Excl14": ["non-allopathic", "non allopathic", "ayurvedic exclusion", "homeopathic exclusion", "naturopathy"],
            "Excl15": ["experimental", "unproven"],
            "Excl16": ["preventive care", "vaccination", "inoculation"],
            "Excl17": ["hearing aid", "hearing implant"],
            "Excl18": ["maternity", "childbirth", "pregnancy", "caesarean", "miscarriage"],
        }

        def _validate_excl_code(code, text):
            """Return True if the exclusion text contains keywords matching the code."""
            import re
            keywords = _code_validators.get(code, [])
            if not keywords:
                return False
            # Use word-boundary matching to avoid substring false positives
            # e.g. "war" should not match "warmer", "warranty", "software"
            for kw in keywords:
                # Multi-word keywords: plain substring is fine (no false-positive risk)
                if " " in kw or "-" in kw or "_" in kw:
                    if kw in text:
                        return True
                else:
                    # Single-word: use word boundary regex
                    if re.search(r'\b' + re.escape(kw) + r'\b', text):
                        return True
            return False

        # Check explicit irdai_code from LLM first — but validate against text
        llm_irdai_code = exc.get("irdai_code", "") or ""
        llm_irdai_code = llm_irdai_code.strip()
        if llm_irdai_code and llm_irdai_code.startswith("Excl"):
            _code_displays = {
                "Excl01": "Pre-Existing Diseases",
                "Excl02": "Specified disease/procedure waiting period",
                "Excl03": "30-day waiting period",
                "Excl04": "War and war-like perils",
                "Excl05": "Breach of law",
                "Excl06": "Hazardous/adventure sports",
                "Excl07": "Suicide and self-inflicted injuries",
                "Excl08": "Alcohol and substance abuse",
                "Excl09": "HIV/AIDS",
                "Excl10": "Refractive error correction",
                "Excl11": "Cosmetic or plastic surgery",
                "Excl12": "Circumcision",
                "Excl13": "Gender change treatment",
                "Excl14": "Non-allopathic treatment",
                "Excl15": "Experimental/unproven treatment",
                "Excl16": "Preventive care and vaccination",
                "Excl17": "Hearing aid",
                "Excl18": "Maternity related exclusion",
            }
            canonical = _code_displays.get(llm_irdai_code)
            if canonical and _validate_excl_code(llm_irdai_code, _combined_text):
                excl_code_entry = {"code": llm_irdai_code, "display": canonical}
            # else: LLM code doesn't match text → reject, try keyword fallback

        # Check name (more specific) — e.g., "Pre-existing Diseases" → Excl01
        if not excl_code_entry:
            name_lower = name.lower()
            for key, entry in CLAIM_EXCLUSION_CODES.items():
                if key in name_lower:
                    # Validate: does the combined text support this code?
                    if _validate_excl_code(entry["code"], _combined_text):
                        excl_code_entry = entry
                        break

        # If no name match, check description
        if not excl_code_entry:
            desc_lower = desc.lower()
            for key, entry in CLAIM_EXCLUSION_CODES.items():
                if key in desc_lower:
                    if _validate_excl_code(entry["code"], _combined_text):
                        excl_code_entry = entry
                        break

        # If no name match, check category
        if not excl_code_entry and category in CLAIM_EXCLUSION_CODES:
            candidate = CLAIM_EXCLUSION_CODES[category]
            if _validate_excl_code(candidate["code"], _combined_text):
                excl_code_entry = candidate

        if excl_code_entry:
            category_codeable = {
                "coding": [{
                    "system": CLAIM_EXCLUSION_CODESYSTEM,
                    "code": excl_code_entry["code"],
                    "display": excl_code_entry["display"]
                }],
                "text": name
            }
        else:
            # No matching code — use text-only (valid FHIR CodeableConcept)
            category_codeable = {"text": name}

        sub_extensions = [
            {
                "url": "category",
                "valueCodeableConcept": category_codeable
            },
            {
                "url": "statement",
                "valueString": statement
            }
        ]

        extensions.append({
            "extension": sub_extensions,
            "url": CLAIM_EXCLUSION_URL
        })

    return extensions


# ──────────────────────────────────────────────────────────
# Eligibility conditions builder
# ──────────────────────────────────────────────────────────

def _build_eligibility_conditions(data):
    """
    Convert eligibility data into Claim-Condition extensions.

    NRCeS IG has no specific eligibility extensions, so we encode
    eligibility rules as Claim-Condition extensions on the root
    InsurancePlan resource, which is a valid use per the profile.
    """
    conditions = []
    elig = data.get("eligibility")
    if not isinstance(elig, dict):
        return conditions

    parts = []
    if elig.get("min_age"):
        parts.append(f"Minimum entry age: {elig['min_age']} years")
    if elig.get("max_age"):
        parts.append(f"Maximum entry age: {elig['max_age']} years")
    if elig.get("renewal_age"):
        parts.append(f"Renewal up to age: {elig['renewal_age']}")
    if elig.get("pre_existing_waiting"):
        parts.append(f"Pre-existing disease waiting period: {elig['pre_existing_waiting']} months")
    for cond in elig.get("conditions", []):
        if cond:
            parts.append(str(cond))

    for part in parts:
        conditions.append({
            "extension": [
                {"url": "claim-condition", "valueString": part}
            ],
            "url": CLAIM_CONDITION_URL
        })

    return conditions


# ──────────────────────────────────────────────────────────
# Plan section builder
# ──────────────────────────────────────────────────────────

def _build_plan_section(data):
    """
    Build InsurancePlan.plan[] per NRCeS profile:
    - identifier: official, value = plan name
    - type: ndhm-plan-type CodeSystem
    - generalCost: sum insured as Money
    - specificCost: monetary benefit limits, copay, waiting-period costs

    Reference: https://nrces.in/ndhm/fhir/r4/InsurancePlan-example-01.json.html
    """
    plan_entry = {}

    # Plan identifier (per official example: use=official, value=plan name)
    plan_entry["identifier"] = [{
        "use": "official",
        "value": data.get("plan_name", "Unknown Plan") or "Unknown Plan"
    }]

    # Plan type from ndhm-plan-type CodeSystem
    pt_str = data.get("plan_type", "individual").lower().strip()
    pt_info = PLAN_TYPE_MAP.get(pt_str, {"code": "99", "display": "Any Other Cover Type"})
    plan_entry["type"] = {
        "coding": [{
            "system": PLAN_TYPE_SYSTEM,
            "code": pt_info["code"],
            "display": pt_info["display"]
        }]
    }

    # General cost = sum insured + premium as Money (per official example)
    general_costs = []

    # Premium
    premium = data.get("premium_amount", "")
    if premium:
        premium_amount = _parse_amount(premium)
        if premium_amount and premium_amount > 0:
            general_costs.append({
                "type": {
                    "coding": [{
                        "system": COST_TYPE_SYSTEM,
                        "code": "premium",
                        "display": "Premium"
                    }]
                },
                "cost": {
                    "value": premium_amount,
                    "currency": data.get("currency", "INR")
                }
            })

    # Sum insured
    sum_insured = data.get("sum_insured", "")
    if sum_insured:
        si_amount = _parse_amount(sum_insured)
        if si_amount and si_amount > 0:
            general_costs.append({
                "cost": {
                    "value": si_amount,
                    "currency": data.get("currency", "INR")
                }
            })

    if general_costs:
        plan_entry["generalCost"] = general_costs

    # Specific costs: monetary benefit limits, copay, waiting periods
    specific_costs = []
    for b in data.get("benefits", []):
        if not isinstance(b, dict):
            continue
        name = b.get("name", "")
        if name.lower().strip() in NON_BENEFIT_KEYWORDS:
            continue

        category = b.get("category", "other")
        limit_amount = _parse_amount(b.get("limit_amount", ""))
        copay = b.get("copay_percent", "")
        wp = b.get("waiting_period_value", "") or b.get("waiting_period_days", "")
        wp_unit = b.get("waiting_period_unit", "days") or "days"
        normalized = _normalize_benefit_name(name) or name
        snomed = _get_specific_snomed_coding(name, category)

        cost_values = []

        limit_unit = b.get("limit_unit", "")

        # Monetary limit (skip duration limits — those go in coverage.benefit.limit)
        if limit_amount and limit_amount > 0 and limit_unit != "days":
            if limit_unit == "percentage_of_si":
                cost_values.append({
                    "type": {
                        "coding": [{"system": COST_TYPE_SYSTEM, "code": "fullcoverage"}],
                        "text": f"{limit_amount}% of Sum Insured"
                    },
                    "value": {"value": limit_amount, "unit": "%"}
                })
            else:
                cost_values.append({
                    "type": {"coding": [{"system": COST_TYPE_SYSTEM, "code": "fullcoverage"}]},
                    "value": {"value": limit_amount, "unit": "INR"}
                })

        # Sub-limits as additional cost entries
        for sub in b.get("sub_limits", []):
            sub_amount = _parse_amount(sub.get("limit_amount", ""))
            sub_unit = sub.get("limit_unit", "")
            if sub_amount and sub_amount > 0:
                if sub_unit == "percentage_of_si":
                    cost_values.append({
                        "type": {
                            "coding": [{"system": COST_TYPE_SYSTEM, "code": "fullcoverage"}],
                            "text": f"{sub.get('name', 'Sub-limit')}: {sub_amount}% of Sum Insured"
                        },
                        "value": {"value": sub_amount, "unit": "%"}
                    })
                elif sub_unit == "per_day":
                    cost_values.append({
                        "type": {
                            "coding": [{"system": COST_TYPE_SYSTEM, "code": "fullcoverage"}],
                            "text": f"{sub.get('name', 'Sub-limit')}: per day"
                        },
                        "value": {"value": sub_amount, "unit": "INR/day"}
                    })
                else:
                    cost_values.append({
                        "type": {
                            "coding": [{"system": COST_TYPE_SYSTEM, "code": "fullcoverage"}],
                            "text": sub.get("name", "Sub-limit")
                        },
                        "value": {"value": sub_amount, "unit": "INR"}
                    })

        # Copay
        if copay:
            try:
                copay_val = float(str(copay).replace("%", "").strip())
            except (ValueError, TypeError):
                copay_val = 0
            cost_values.append({
                "type": {
                    "coding": [{"system": COST_TYPE_SYSTEM, "code": "copay"}],
                    "text": f"{copay}% Co-pay"
                },
                "value": {"value": copay_val, "unit": "%"}
            })

        # Waiting period as cost
        if wp:
            if wp_unit not in ("days", "months", "years"):
                wp_unit = "days"
            try:
                wp_val = float(str(wp).strip())
            except (ValueError, TypeError):
                wp_val = 0
            cost_values.append({
                "type": {
                    "coding": [{"system": COST_TYPE_SYSTEM, "code": "deductible"}],
                    "text": f"Waiting Period: {wp} {wp_unit}"
                },
                "value": {"value": wp_val, "unit": wp_unit}
            })

        if cost_values:
            specific_costs.append({
                "category": {
                    "coding": [snomed],
                    "text": normalized
                },
                "benefit": [{
                    "type": {
                        "coding": [snomed],
                        "text": normalized
                    },
                    "cost": cost_values
                }]
            })

    if specific_costs:
        plan_entry["specificCost"] = specific_costs

    return [plan_entry]


# ──────────────────────────────────────────────────────────
# Main entry point
# ──────────────────────────────────────────────────────────

def map_to_fhir(data):
    """
    Map extracted insurance data to an NHCX-compliant FHIR Bundle
    following NRCeS IG v6.5.0 InsurancePlan profile.

    The output mirrors the official example:
    https://nrces.in/ndhm/fhir/r4/InsurancePlan-example-01.json.html
    """
    org_id = _make_uuid()
    plan_id = _make_uuid()
    bundle_id = _make_uuid()

    org_name = data.get("organization", "") or "Unknown"
    plan_name = data.get("plan_name", "") or "Unknown Plan"
    insurer_id = data.get("insurer_id", "") or ""
    uin = data.get("uin", "") or ""

    # ─── Organization resource ───
    org_identifier_value = insurer_id if insurer_id else org_name.replace(" ", "-").lower()
    organization = {
        "resourceType": "Organization",
        "id": org_id,
        "meta": {
            "profile": [NHCX_ORGANIZATION_PROFILE]
        },
        "identifier": [{
            "type": {
                "coding": [{
                    "system": NDHM_IDENTIFIER_TYPE_SYSTEM,
                    "code": "ROHINI",
                    "display": "Registration Number"
                }]
            },
            "system": "https://irdai.gov.in/insurer-id",
            "value": org_identifier_value
        }],
        "name": org_name,
        "active": True
    }

    # Organization.telecom (phone, email, website)
    telecom_data = data.get("telecom", {})
    if isinstance(telecom_data, dict):
        org_telecom = []
        phone = telecom_data.get("phone", "")
        email = telecom_data.get("email", "")
        website = telecom_data.get("website", "")
        if phone:
            org_telecom.append({"system": "phone", "value": phone, "use": "work"})
        if email:
            org_telecom.append({"system": "email", "value": email, "use": "work"})
        if website:
            org_telecom.append({"system": "url", "value": website})
        if org_telecom:
            organization["telecom"] = org_telecom

    # ─── InsurancePlan type (ndhm-insuranceplan-type) ───
    coverage_type = data.get("coverage_type", "health").lower().strip() or "health"
    ip_type_info = INSURANCEPLAN_TYPE_MAP.get(coverage_type, INSURANCEPLAN_TYPE_MAP["health"])

    # ─── InsurancePlan extensions ───
    extensions = []
    # Claim-Exclusion extensions (real NRCeS extension)
    exclusion_exts = _build_exclusion_extensions(data)
    extensions.extend(exclusion_exts)
    # NOTE: Eligibility Claim-Condition extensions are added to
    # coverage[0].extension (not root) per NRCeS IG — see below.

    # ─── InsurancePlan identifier (UIN or plan name) ───
    plan_identifier_value = uin if uin else plan_name.replace(" ", "-").lower()
    plan_identifier_system = "https://irdai.gov.in/uin" if uin else "https://irdai.gov.in"

    # ─── InsurancePlan resource ───
    insurance_plan = {
        "resourceType": "InsurancePlan",
        "id": plan_id,
        "meta": {
            "versionId": "1",
            "profile": [NHCX_INSURANCE_PLAN_PROFILE]
        },
        "identifier": [{
            "system": plan_identifier_system,
            "value": plan_identifier_value
        }],
        "status": "active",
        "type": [{
            "coding": [{
                "system": INSURANCEPLAN_TYPE_SYSTEM,
                "code": ip_type_info["code"],
                "display": ip_type_info["display"]
            }],
            "text": data.get("coverage_type", "health") or "health"
        }],
        "name": plan_name,
        "period": {
            "start": _today_str(),
            "end": _next_year_str()
        },
        "ownedBy": {
            "reference": _make_urn(org_id),
            "display": org_name
        },
        "administeredBy": {
            "reference": _make_urn(org_id),
            "display": org_name
        },
        "coverage": _build_coverage(data),
        "plan": _build_plan_section(data)
    }

    # InsurancePlan.contact (customer service)
    contact_telecom = []
    if isinstance(telecom_data, dict):
        phone = telecom_data.get("phone", "")
        email = telecom_data.get("email", "")
        if phone:
            contact_telecom.append({"system": "phone", "value": phone})
        if email:
            contact_telecom.append({"system": "email", "value": email})
    if contact_telecom:
        insurance_plan["contact"] = [{
            "purpose": {"text": "Customer Service"},
            "telecom": contact_telecom
        }]

    # Append eligibility Claim-Condition extensions to coverage[0]
    # Per NRCeS IG, Claim-Condition is defined on InsurancePlan.coverage,
    # NOT on the InsurancePlan root.
    elig_conditions = _build_eligibility_conditions(data)
    if elig_conditions and insurance_plan.get("coverage"):
        first_cov = insurance_plan["coverage"][0]
        existing = first_cov.get("extension", [])
        existing.extend(elig_conditions)
        first_cov["extension"] = existing

    # Add extensions if any exist
    if extensions:
        insurance_plan["extension"] = extensions

    # Network type as alias (per NRCeS profile: alias 0..*)
    if data.get("network_type"):
        insurance_plan["alias"] = [data["network_type"]]

    # ─── Bundle ───
    bundle = {
        "resourceType": "Bundle",
        "id": bundle_id,
        "meta": {
            "versionId": "1",
            "lastUpdated": _timestamp(),
            "profile": [NHCX_INSURANCE_PLAN_BUNDLE_PROFILE]
        },
        "type": "collection",
        "timestamp": _timestamp(),
        "entry": [
            {
                "fullUrl": _make_urn(org_id),
                "resource": organization
            },
            {
                "fullUrl": _make_urn(plan_id),
                "resource": insurance_plan
            }
        ]
    }

    logger.info(
        f"Mapped FHIR bundle: {bundle_id} with "
        f"{len(data.get('benefits', []))} benefits, "
        f"{len(data.get('exclusions', []))} exclusions"
    )

    return bundle
