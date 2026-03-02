import os
import json
import time
import logging
from dotenv import load_dotenv
from openai import OpenAI, RateLimitError, APIError

load_dotenv()

logger = logging.getLogger(__name__)

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY")
)

####################################################
# SETTINGS
####################################################

MODEL = "gpt-4o-mini"

CHUNK_SIZE = 25000   # bigger chunks = fewer requests

MAX_RETRIES = 6

BASE_DELAY = 10   # seconds

KEYWORDS = [
    "benefit", "coverage", "sum insured", "limit",
    "hospital", "expenses", "eligibility", "exclusion",
    "room rent", "icu", "ambulance", "treatment", "claim",
    "co-pay", "copay", "deductible", "waiting period",
    "sub-limit", "sublimit", "maternity", "daycare",
    "pre-existing", "network", "cashless",
    # Additional keywords for better extraction coverage
    "uin", "irdai", "product name", "plan name",
    "cancer", "heart", "income protect", "critical illness",
    "cin no", "registration", "section i", "section ii", "section iii",
    "premium", "insured", "opd", "dental", "ayush",
    "domiciliary", "organ donor", "rehabilitation",
    "reimbursement", "pre-hospitalization", "post-hospitalization",
    "lump sum", "payout", "accident", "personal accident",
    "cosmetic", "suicide", "alcohol", "hiv", "war",
    "specific disease", "specified disease",
]


####################################################
# SYSTEM PROMPT — detailed instructions for LLM
####################################################

SYSTEM_PROMPT = """You are an expert health insurance policy parser for Indian insurance plans.

Extract ONLY real information found in the text. Do NOT hallucinate or invent data.

Return a JSON object with this EXACT structure:

{
  "organization": "Name of the insurance company",
  "insurer_id": "IRDAI Registration Number (2-4 digit number). Look for 'IRDAI Reg. No.' or 'Registration No.'",
  "uin": "Unique Identification Number (UIN) of the product. Format: XXXXXXXXXXXXVXXXXXX",
  "plan_name": "Name of the insurance plan/product — the PRODUCT NAME from the PDF title/header (e.g. 'Group Protect', 'Health Shield'). NOT a benefit name.",
  "plan_type": "individual | family_floater | group",
  "coverage_type": "health | accident | critical_illness | top_up",
  "sum_insured": "Overall sum insured amount as string e.g. '500000'",
  "currency": "INR",
  "premium_amount": "Annual premium amount if mentioned",
  "telecom": {
    "phone": "Customer service phone number or toll-free number",
    "email": "Customer service email address",
    "website": "Company website URL"
  },
  "benefits": [
    {
      "name": "Benefit name — must be distinct and specific (see rules below)",
      "category": "inpatient | outpatient | daycare | maternity | ambulance | ayush | dental | mental_health | organ_donor | rehabilitation | domiciliary | pre_hospitalization | post_hospitalization | other",
      "description": "COMPLETE description of what is covered. Copy the FULL paragraph from the PDF. Never truncate.",
      "limit_amount": "Monetary limit OR day limit as string, or empty",
      "limit_unit": "amount | percentage_of_si | days | no_limit",
      "sub_limits": [
        {
          "name": "Sub-limit name e.g. Room Rent",
          "limit_amount": "Amount or percentage",
          "limit_unit": "amount | percentage_of_si | per_day | days"
        }
      ],
      "copay_percent": "Co-pay percentage as string or empty",
      "waiting_period_value": "Numeric waiting period as string or empty",
      "waiting_period_unit": "days | months | years",
      "is_optional": false
    }
  ],
  "exclusions": [
    {
      "name": "Exclusion name",
      "description": "Brief description",
      "category": "permanent | time_bound | conditional",
      "irdai_code": "IRDAI standard exclusion code if referenced (Excl01-Excl18)",
      "waiting_period_value": "Numeric waiting period as string or empty",
      "waiting_period_unit": "days | months | years"
    }
  ],
  "eligibility": {
    "min_age": "Minimum entry age",
    "max_age": "Maximum entry age",
    "renewal_age": "Maximum renewal age",
    "pre_existing_waiting": "Waiting period for pre-existing diseases in months",
    "conditions": ["List of other eligibility conditions"]
  },
  "network_type": "cashless | reimbursement | both",
  "portability": true
}

════════════════════════════════════════
CRITICAL RULES — READ CAREFULLY
════════════════════════════════════════

▶ SUM INSURED (MUST extract if present):
  - Search for: "Sum Insured", "SI", "Cover Amount", "Sum Assured", "Basic Sum Insured",
    "Policy Limit", "Maximum Limit", "Cover", "Capital Sum Insured", "CSI".
  - Convert lakhs: "5 Lakhs" = "500000", "10 Lakh" = "1000000", "1 Crore" = "10000000".
  - If the text mentions ANY sum insured, you MUST extract it. NEVER leave sum_insured empty
    if the text contains a sum insured amount.
  - If multiple variants exist (e.g., table with 3L/5L/10L), use the first or base value.

▶ BENEFIT NAMES — MUST be distinct and specific:
  - NEVER use "In-Patient Hospitalization" as the name for pre-hosp or post-hosp benefits.
  - Pre-hospitalization expenses → name: "Pre-Hospitalization Medical Expenses", category: "pre_hospitalization"
  - Post-hospitalization expenses → name: "Post-Hospitalization Medical Expenses", category: "post_hospitalization"
  - ICU charges → name: "ICU Charges", category: "inpatient"
  - Room rent → name: "Room Rent", category: "inpatient"
  - Ambulance → name: "Ambulance Cover", category: "ambulance"
  - Day care → name: "Day Care Treatment", category: "daycare"
  - OPD → name: "OPD Expenses", category: "outpatient"
  - AYUSH → name: "AYUSH Treatment", category: "ayush"
  - Organ donor → name: "Organ Donor Cover", category: "organ_donor"
  - Domiciliary → name: "Domiciliary Hospitalization", category: "domiciliary"
  - Dental → name: "Dental Treatment", category: "dental"
  - Maternity → name: "Maternity Cover", category: "maternity"
  Each benefit MUST have a UNIQUE name. Do NOT create duplicates.

▶ DAY-BASED LIMITS (CRITICAL):
  - When a benefit says "up to 60 days" or "90 days" or "30 days before/after hospitalization",
    set limit_amount to the number and limit_unit to "days".
  - Examples:
    "Pre-hospitalization expenses up to 60 days" →
      limit_amount: "60", limit_unit: "days"
    "Post-hospitalization expenses up to 90 days" →
      limit_amount: "90", limit_unit: "days"
    "ICU up to 15 days" →
      limit_amount: "15", limit_unit: "days"
  - This is NOT a waiting period — it is a coverage duration limit.
  - Only use limit_unit "amount" for monetary amounts (₹).
  - Only use limit_unit "days" for time-based coverage limits.

▶ WAITING PERIODS:
  - Always specify BOTH waiting_period_value AND waiting_period_unit.
  - "30 days" → waiting_period_value: "30", waiting_period_unit: "days"
  - "24 months" → waiting_period_value: "24", waiting_period_unit: "months"
  - Do NOT confuse waiting periods (time before coverage starts) with
    day-based limits (how many days of coverage).

▶ FINANCIAL LIMITS — MUST EXTRACT (THIS IS THE MOST IMPORTANT SECTION):
  Every benefit MUST have limit_amount and limit_unit populated if the text mentions ANY of these:
  - "X% of Sum Insured"  → limit_amount: "X", limit_unit: "percentage_of_si"
  - "Rs. X" / "₹X" / "X Lakhs"  → limit_amount: number as string, limit_unit: "amount"
  - "up to X days"  → limit_amount: "X", limit_unit: "days"
  - "no sub-limit" / "no limit" / "as per actuals"  → limit_amount: "", limit_unit: "no_limit"

  Common patterns to look for:
  - Room Rent: "1% of SI per day" → sub_limit with name "Room Rent", limit_amount "1", limit_unit "percentage_of_si"
  - ICU: "2% of SI per day" → sub_limit with name "ICU", limit_amount "2", limit_unit "percentage_of_si"
  - Ambulance: "Rs. 2000 per hospitalization" → limit_amount "2000", limit_unit "amount"
  - Pre-hospitalization: "60 days" → limit_amount "60", limit_unit "days"  
  - Post-hospitalization: "90 days" → limit_amount "90", limit_unit "days"
  - Cancer stages: "100% of Sum Insured" → limit_amount "100", limit_unit "percentage_of_si"
  - OPD: "Rs. 5000 per year" → limit_amount "5000", limit_unit "amount"

  ▶ SUB-LIMITS — MUST EXTRACT:
  When a benefit mentions room rent caps, ICU caps, ambulance limits, or any per-item limits,
  create sub_limits entries. For In-Patient Hospitalization, always check for these sub-limits:
  - Room Rent (e.g., "1% of SI per day", "Single Private AC Room", "Rs 5000/day")
  - ICU Charges (e.g., "2% of SI per day", "No sub-limit")
  - Ambulance Cover (if mentioned as sub-limit of hospitalization)

  Sub-limit examples:
  "Room Rent: up to 1% of Sum Insured per day" →
    sub_limits: [{"name": "Room Rent", "limit_amount": "1", "limit_unit": "percentage_of_si"}]
  "ICU charges: up to 2% of Sum Insured per day" →
    sub_limits: [{"name": "ICU Charges", "limit_amount": "2", "limit_unit": "percentage_of_si"}]
  "Ambulance: Rs. 2000 per hospitalization" →
    sub_limits: [{"name": "Ambulance", "limit_amount": "2000", "limit_unit": "amount"}]

  If the text says "as per Policy Schedule" or "as specified in Certificate of Insurance"
  for a limit, that means the limit varies per policyholder. In that case:
  - Still create the benefit entry with proper name and category
  - Set limit_amount to "" and limit_unit to "no_limit"
  - Do NOT skip the benefit

▶ GENERAL RULES:
  - Extract exact ₹ amounts when present.
  - Convert lakhs to numbers: 5 Lakhs = 500000.
  - Extract ALL benefits, sub-limits, exclusions.
  - If a field is not found, use empty string "" for strings, [] for arrays, null for objects.
  - For benefits that say "up to X% of Sum Insured", set limit_unit to "percentage_of_si".
  - Classify each benefit into one of the categories listed.
  - Mark optional/add-on benefits with is_optional: true.

▶ DO NOT include these as benefits (they are plan features, not coverage benefits):
  - "Cashless Facility" (service feature)
  - "Co-Payment" / "Co-pay" (cost-sharing rule)
  - "Deductible" (cost-sharing rule)
  - "Cumulative Bonus" / "No Claim Bonus" (renewal reward)
  - "Portability" (regulatory feature)
  - "Free Look Period" (cancellation clause)
  - Any definition-only text that does not describe actual coverage

▶ DO NOT create duplicate entries. If the same benefit appears multiple times with different
  details, merge them into ONE entry with the most complete information.

▶ IRDAI EXCLUSION CODES (map exclusions to standard codes when referenced):
  - Pre-existing diseases → Excl01
  - Specified disease/procedure waiting period → Excl02
  - 30-day waiting period → Excl03
  - War/nuclear → Excl04
  - Breach of law → Excl05
  - Hazardous/adventure sports → Excl06
  - Suicide/self-inflicted → Excl07
  - Alcohol/substance abuse → Excl08
  - HIV/AIDS → Excl09
  - Refractive error/spectacles → Excl10
  - Cosmetic/plastic surgery → Excl11
  - Circumcision → Excl12
  - Gender change → Excl13
  - Non-allopathic treatment → Excl14
  - Experimental/unproven treatment → Excl15
  - Preventive care/vaccination → Excl16
  - Hearing aid → Excl17
  - Dental → Excl18
  Set the irdai_code field for each exclusion ONLY if you are confident it matches one of the above.
  If the exclusion does NOT clearly match any standard IRDAI category, set irdai_code to null or empty string.
  Do NOT guess or default to Excl04. Leave it blank rather than assign a wrong code.

▶ EXTRACTION COMPLETENESS:
  - Extract from ALL numbered sections (Section I, II, III, sub-sections like II.2, II.3).
  - For multi-option covers (e.g., Cancer Options 1-2, Heart Options 1-8),
    extract ALL options as separate benefits.
  - Benefit descriptions must be COMPLETE — copy the full paragraph.
    Include all qualifying conditions, sublimits, criteria, and exceptions.
  - NEVER truncate or summarize benefit descriptions."""


####################################################
# STEP 1: Extract relevant sections
####################################################

def extract_relevant_sections(text):
    lines = text.split("\n")

    # Always keep header (product name, UIN) and footer (IRDAI Reg No, CIN)
    header_lines = lines[:20]
    footer_lines = lines[-15:] if len(lines) > 35 else []

    relevant = []
    for line in lines:
        if any(k in line.lower() for k in KEYWORDS):
            relevant.append(line)

    # If filtering removes too much → use full text
    if len(relevant) < 50:
        return text

    # Prepend header + append footer to ensure critical metadata is captured
    header_text = "\n".join(header_lines)
    footer_text = "\n".join(footer_lines)
    body_text = "\n".join(relevant)
    return header_text + "\n\n" + body_text + "\n\n" + footer_text


####################################################
# STEP 2: Chunk text
####################################################

def chunk_text(text):
    chunks = []
    start = 0

    while start < len(text):
        end = start + CHUNK_SIZE
        chunks.append(text[start:end])
        start = end

    return chunks


####################################################
# STEP 3: Safe LLM call with exponential backoff
####################################################

def call_llm(prompt):
    delay = BASE_DELAY

    for attempt in range(MAX_RETRIES):
        try:
            response = client.chat.completions.create(
                model=MODEL,
                temperature=0,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ]
            )

            return json.loads(response.choices[0].message.content)

        except RateLimitError:
            logger.warning(f"Rate limit hit. Waiting {delay}s (attempt {attempt+1})")
            time.sleep(delay)
            delay *= 2

        except APIError as e:
            logger.error(f"API error: {e}")
            time.sleep(delay)

        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return None

    logger.error("Failed after all retries.")
    return None


####################################################
# STEP 4: Extract chunk
####################################################

def extract_chunk(chunk):
    prompt = f"""Extract insurance plan structured data from the following text.
Return the JSON object as specified in your instructions.

CRITICAL REMINDERS:
- plan_name = the PRODUCT NAME from the PDF title/header (e.g. "Group Protect", "Family Shield").
  It is NOT a benefit name. Look at the first page or document header.
- insurer_id = IRDAI Registration Number (2-4 digit number, NOT the UIN).
  Look for "IRDAI Reg. No." or "Registration No." in the text.
- uin = the product UIN (format like XXXXXXXXXXXXVXXXXXX). Look for "UIN:" in the text.
- Extract EVERY benefit section: Section I, II, III and all sub-sections.
  Include Cancer, Heart, Income Protect, Credit Protect, OPD, Ambulance, etc.
- For each benefit, COPY THE FULL DESCRIPTION. Never truncate.
  Include all qualifying conditions, sublimits, and criteria.
- Every benefit MUST have limit_amount filled if any monetary value exists.
  If benefit says "up to Sum Insured", use the actual sum insured amount.
- For exclusions, include irdai_code (Excl01-Excl18) ONLY if it clearly matches a standard IRDAI category.
  If unsure, leave irdai_code as null — do NOT default to Excl04 or guess.
- waiting_period_value: ONLY set if explicitly stated. Do NOT assume or invent.

For EVERY benefit, you MUST extract:
1. limit_amount and limit_unit (monetary limit, percentage of SI, or day limit)
2. sub_limits array (room rent caps, ICU caps, ambulance limits, etc.)
3. waiting_period_value and waiting_period_unit
4. copay_percent if applicable

Look carefully for amounts like "Rs.", "₹", "Lakhs", "% of Sum Insured", "per day", "per claim".
Do NOT leave limit_amount empty if the text mentions ANY limit for that benefit.

TEXT:
{chunk}
"""

    result = call_llm(prompt)

    # Wait between requests to avoid TPM rate limits (Tier 1 accounts)
    time.sleep(30)
    return result


####################################################
# STEP 5: Merge structured results from chunks
####################################################

# Placeholder / invalid values that should be treated as empty
_PLACEHOLDER_VALUES = {
    "not specified", "n/a", "unknown", "na", "none", "nil", "0", "-", "--",
    "not available", "not applicable", "not mentioned", "not found",
    "irdai reg. no. not found", "irdai registration no. not found",
    "registration number not found", "insurer id not found",
    "not extracted", "not provided", "not disclosed",
}


def _is_placeholder(value):
    """Check if a string value is a placeholder/invalid."""
    if not value:
        return True
    return str(value).strip().lower() in _PLACEHOLDER_VALUES


def _clean_value(value):
    """Return empty string if value is a placeholder, otherwise strip it."""
    if _is_placeholder(value):
        return ""
    return str(value).strip()


def _normalize_key(name):
    """Normalize a benefit/exclusion name for deduplication matching."""
    import re
    name = name.lower().strip()
    # Remove punctuation, collapse whitespace, normalize common variations
    name = re.sub(r'[^\w\s]', ' ', name)
    name = re.sub(r'\s+', ' ', name).strip()
    # Normalize common synonyms
    name = name.replace('hospitalisation', 'hospitalization')
    name = name.replace('in patient', 'inpatient')
    name = name.replace('in-patient', 'inpatient')
    name = name.replace('out patient', 'outpatient')
    name = name.replace('out-patient', 'outpatient')
    return name


def _merge_benefit_entries(existing, new):
    """Merge two benefit dicts, preferring the more complete one."""
    merged = dict(existing)
    for key, val in new.items():
        if key == "sub_limits":
            # Merge sub-limit lists
            existing_subs = {s.get("name", "").lower(): s for s in merged.get("sub_limits", [])}
            for sub in val or []:
                sub_key = sub.get("name", "").lower()
                if sub_key and sub_key not in existing_subs:
                    merged.setdefault("sub_limits", []).append(sub)
        elif val and not merged.get(key):
            # Fill in missing fields from the new entry
            merged[key] = val
    return merged


def _dedupe_by_name(items):
    """De-duplicate a list of dicts by their normalized 'name' field, merging details."""
    seen = {}  # normalized_name -> (index, item)
    unique = []
    for item in items:
        name = item.get("name", "").strip()
        if not name:
            continue
        norm = _normalize_key(name)
        if norm in seen:
            # Merge into existing entry
            idx = seen[norm]
            unique[idx] = _merge_benefit_entries(unique[idx], item)
        else:
            seen[norm] = len(unique)
            unique.append(item)
    return unique


def merge_results(results):
    final = {
        "organization": "",
        "insurer_id": "",
        "uin": "",
        "plan_name": "",
        "plan_type": "",
        "coverage_type": "",
        "sum_insured": "",
        "currency": "INR",
        "premium_amount": "",
        "telecom": {"phone": "", "email": "", "website": ""},
        "benefits": [],
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

    for r in results:
        if not r:
            continue

        # Scalar fields — take the first non-placeholder value
        for key in ["organization", "insurer_id", "uin", "plan_name", "plan_type",
                     "coverage_type", "sum_insured", "currency", "network_type",
                     "premium_amount"]:
            val = _clean_value(r.get(key, ""))
            if val and not final[key]:
                final[key] = val

        if r.get("portability") is not None and final["portability"] is None:
            final["portability"] = r["portability"]

        # Telecom — merge non-empty fields
        telecom = r.get("telecom")
        if isinstance(telecom, dict):
            for tk in ["phone", "email", "website"]:
                tv = _clean_value(telecom.get(tk, ""))
                if tv and not final["telecom"][tk]:
                    final["telecom"][tk] = tv

        # Structured benefits
        for b in r.get("benefits", []):
            if isinstance(b, dict):
                name = b.get("name", "").strip()
                if not name or _is_placeholder(name):
                    continue
                # Skip optional riders
                if b.get("is_optional", False):
                    continue
                final["benefits"].append(b)
            elif isinstance(b, str) and not _is_placeholder(b):
                # Backward compat: convert flat string to structured object
                final["benefits"].append({
                    "name": b, "category": "other", "description": b,
                    "limit_amount": "", "limit_unit": "", "sub_limits": [],
                    "copay_percent": "", "waiting_period_value": "",
                    "waiting_period_unit": "", "is_optional": False
                })

        # Structured exclusions
        for e in r.get("exclusions", []):
            if isinstance(e, dict):
                name = e.get("name", "").strip()
                if not name or _is_placeholder(name):
                    continue
                final["exclusions"].append(e)
            elif isinstance(e, str) and not _is_placeholder(e):
                final["exclusions"].append({
                    "name": e, "description": e,
                    "category": "permanent", "waiting_period_value": "",
                    "waiting_period_unit": ""
                })

        # Eligibility — merge non-placeholder fields
        elig = r.get("eligibility")
        if isinstance(elig, dict):
            for key in ["min_age", "max_age", "renewal_age", "pre_existing_waiting"]:
                val = _clean_value(elig.get(key, ""))
                if val and not final["eligibility"].get(key):
                    final["eligibility"][key] = val
            for c in elig.get("conditions", []):
                if c and not _is_placeholder(c) and c not in final["eligibility"]["conditions"]:
                    final["eligibility"]["conditions"].append(c)
        elif isinstance(elig, str) and elig and not _is_placeholder(elig):
            final["eligibility"]["conditions"].append(elig)

    # De-duplicate
    final["benefits"] = _dedupe_by_name(final["benefits"])
    final["exclusions"] = _dedupe_by_name(final["exclusions"])

    # Post-processing: Validate plan_name is not a generic description
    _GENERIC_PLAN_NAMES = {
        "health insurance", "health insurance policy", "health insurance plan",
        "insurance plan", "insurance policy", "general insurance",
        "group insurance", "personal accident policy", "personal accident plan",
    }
    plan_name = final.get("plan_name", "").strip()
    if plan_name.lower() in _GENERIC_PLAN_NAMES:
        logger.warning(f"plan_name '{plan_name}' looks generic. Verify against PDF title.")

    return final


####################################################
# MAIN ENTRY
####################################################

def extract_insurance_data(full_text):
    logger.info("Extracting relevant sections...")
    relevant = extract_relevant_sections(full_text)

    chunks = chunk_text(relevant)
    logger.info(f"Split into {len(chunks)} chunks")

    results = []
    for i, chunk in enumerate(chunks):
        logger.info(f"Processing chunk {i+1}/{len(chunks)}")
        result = extract_chunk(chunk)
        if result:
            results.append(result)

    final = merge_results(results)

    # ─── Post-processing: IRDAI Reg No from raw text (regex fallback) ───
    # The LLM often misidentifies this — scan the raw text directly
    import re
    irdai_patterns = [
        r'IRDAI\s*Reg\.?\s*(?:No\.?\s*)?(\d{2,4})',
        r'IRDA\s*Reg\.?\s*(?:No\.?\s*)?(\d{2,4})',
        r'Registration\s*No\.?\s*(\d{2,4})',
        r'IRDAI\s*Registration\s*(?:Number|No\.?)\s*(\d{2,4})',
    ]
    for pattern in irdai_patterns:
        m = re.search(pattern, full_text, re.IGNORECASE)
        if m:
            extracted_id = m.group(1).strip()
            if extracted_id != final.get("insurer_id", ""):
                logger.info(f"IRDAI Reg correction: LLM gave '{final.get('insurer_id', '')}', "
                           f"regex found '{extracted_id}' → using regex value")
                final["insurer_id"] = extracted_id
            break

    # ─── Post-processing: UIN from raw text (regex fallback) ───
    if not final.get("uin") or _is_placeholder(final["uin"]):
        uin_patterns = [
            r'UIN\s*[:.]?\s*([A-Z]{3,6}\w{10,25})',
            r'([A-Z]{3}[A-Z]{2,4}[A-Z0-9]{10,20}V\d{5,8})',
        ]
        for pattern in uin_patterns:
            m = re.search(pattern, full_text)
            if m:
                final["uin"] = m.group(1).strip()
                logger.info(f"UIN extracted via regex: {final['uin']}")
                break

    logger.info("Extraction complete")
    logger.debug(json.dumps(final, indent=2, ensure_ascii=False))

    return final