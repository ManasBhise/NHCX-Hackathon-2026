# Hackathon Output - Complete Package

## Overview

Your system now generates a **complete submission package** for each insurance plan containing both **FHIR-compliant JSON** and **human-readable Excel mapping documentation**.

## Output Structure

```
output/pending/
├── [Plan Name].json              ← FHIR R4 InsurancePlan Bundle (machine-readable)
├── [Plan Name]_mapping.xlsx      ← Excel mapping & documentation (human-readable)
├── [Plan Name].json
├── [Plan Name]_mapping.xlsx
└── ... (repeated for each insurance plan)
```

## Example: Bajaj_01

### `Bajaj_01.json`
- **Type:** FHIR R4 Bundle containing:
  - Organization resource (insurance company info)
  - InsurancePlan resource (plan details, coverage, benefits, exclusions)
- **Format:** JSON, NRCeS IG v6.5.0 compliant
- **Use:** API integration, FHIR validators, healthcare systems
- **Size:** ~50-100 KB

### `Bajaj_01_mapping.xlsx`
- **Type:** Excel spreadsheet with 4 sheets
- **Format:** XLSX, human-readable with formatting
- **Use:** Review, documentation, stakeholder communication
- **Size:** ~10 KB

## What Each Excel Sheet Contains

### Sheet 1: Mapping Rules
**Purpose:** Show what transformation rules were applied

| Keyword (Source) | Mapped To (FHIR Display Name) |
|---|---|
| inpatient | In-Patient Hospitalization |
| hospitalisation | In-Patient Hospitalization |
| daycare | Day Care Treatment |
| icu | ICU Charges |
| ... | ... |

**Use:** Understand how raw PDF text keywords were normalized to FHIR standard names

---

### Sheet 2: Organization
**Purpose:** Insurance company information extracted from bundle

| Property | Value |
|---|---|
| Name | Bajaj Allianz General Insurance Co. Ltd. |
| Active | True |
| Identifier (ROHINI) | 113 |
| Telecom (phone) | 1800 209 0144 |
| Telecom (email) | bagichelp@bajajallianz.co.in |

**Use:** Quick reference for company details

---

### Sheet 3: Insurance Plan
**Purpose:** Plan details and available coverage

**Section A: Basic Information**

| Property | Value |
|---|---|
| Plan Name | Global Health Care |
| Status | active |
| Period Start | 2026-03-01 |
| Period End | 2027-03-01 |

**Section B: Coverage & Benefits**

| Coverage Type | Benefit Name | Benefit Code | Display |
|---|---|---|---|
| Inpatient care management | In-Patient Hospitalization | 737481003 | Inpatient care management (procedure) |
| Inpatient care management | ICU Charges | 50960008 | ICU care (procedure) |
| Outpatient care management | OPD Expenses | 737492002 | Outpatient care management (procedure) |

**Use:** Review available coverages and SNOMED CT coding

---

### Sheet 4: Exclusions
**Purpose:** Policy exclusions and limitations

| Exclusion Category | Statement |
|---|---|
| Pre-Existing Disease | Expenses related to the treatment of a Pre-Existing Disease (PED) and its direct complications shall be excluded until the expiry of 36 months... |
| Specified Procedures | Expenses related to the treatment of the listed Conditions, surgeries/treatments shall be excluded until the expiry of 24 months... |
| Initial Waiting Period | Expenses related to any Illness within 30 days from the first Policy... |

**Use:** Understand policy limitations and waiting periods

---

## How to Create Excel Files

### Automatic (During Pipeline)
```bash
python main.py
```
Excel files are automatically generated alongside JSON outputs.

### Manual (From Existing JSONs)
```bash
# Single file
python generate_excel_mappings.py --file output/pending/Plan_Name.json

# All files in directory
python generate_excel_mappings.py --dir output/pending
```

---

## Submitting for Hackathon

### What to Include

For each insurance plan, submit **both files**:

```
Submission Package
├── JSON Bundle
│   └── Plan_Name.json (FHIR R4 format)
└── Mapping Documentation
    └── Plan_Name_mapping.xlsx (Excel reference)
```

### Data Flow Diagram

```
PDF Input
   ↓
[1. Extract Text] (PyMuPDF)
   ↓
[2. Parse with LLM] (GPT-4o-mini)
   ↓
[3. Map to FHIR] (nhcx_mapper.py)
   ↓
[4. Validate] (fhir.resources + NRCeS checks)
   ↓
[5. Save JSON] (output/pending/)
   ↓
[6. Generate Excel] ← NEW!
   ↓
Outputs
├── plan_name.json
└── plan_name_mapping.xlsx
```

---

## Current Status

✅ **7 Insurance Plans Processed:**

| Plan | Company | JSON | Excel |
|---|---|---|---|
| Saral Suraksha Bima | Aditya Birla | ✓ | ✓ |
| Global Health Care | Bajaj | ✓ | ✓ |
| Rider Insurance | Bajaj | ✓ | ✓ |
| [Plan G] | Bajaj | ✓ | ✓ |
| [Plan 1] | Care | ✓ | ✓ |
| [Plan G] | Care | ✓ | ✓ |
| [Plan G] | Cholamandalam | ✓ | ✓ |

All files available in: `output/pending/`

---

## File Sizes

| Type | Typical Size | Notes |
|---|---|---|
| JSON Bundle | 50-100 KB | Varies by coverage complexity |
| Excel Mapping | 10-12 KB | Consistent overhead per file |
| **Total per Plan** | **60-112 KB** | Both machine & human readable |

---

## Technical Specifications

### JSON Format
- **Standard:** FHIR R4
- **Profile:** NRCeS IG v6.5.0 InsurancePlanBundle
- **Validation:** Pydantic + FHIR profile checks
- **Encoding:** UTF-8

### Excel Format
- **Standard:** XLSX (Office Open XML)
- **Sheets:** 4 (Mapping Rules, Organization, Insurance Plan, Exclusions)
- **Styling:** Colored headers, wrapped text, auto-sized columns
- **Library:** openpyxl v3.1.2

---

## Next Steps for Hackathon

1. ✅ **Generate JSONs** - Done (Python pipeline)
2. ✅ **Generate Excel Mappings** - Done (Now integrated)
3. **Package for submission** - Zip both JSON and Excel files
4. **Document mappings** - Use Excel files as documentation
5. **Present findings** - Show Excel sheets to judges/stakeholders

---

## Key Features

| Feature | Benefit |
|---|---|
| **Automated Excel Generation** | No manual work, integrated in pipeline |
| **4 Informative Sheets** | Complete documentation of data transformation |
| **NRCeS Compliant** | Follows official NDHM standards for FHIR |
| **Human-Readable** | Excel files for non-technical stakeholders |
| **Machine-Readable** | JSON for systems and validators |
| **Complete Mapping Trail** | See exactly what was extracted and how it maps |

---

## Troubleshooting

**Q: Excel files not generating?**
A: Check that `openpyxl` is installed:
```bash
pip install openpyxl
```

**Q: Want to regenerate all Excel files?**
A: Run:
```bash
python generate_excel_mappings.py --dir output/pending
```

**Q: Can I customize the Excel format?**
A: Yes, edit `utils/excel_generator.py` to change styles, add sheets, modify data, etc.

---

## Documentation Files

- **[EXCEL_MAPPING_DOCUMENTATION.md](EXCEL_MAPPING_DOCUMENTATION.md)** - Detailed Excel guide
- **[README.md](README.md)** - Main project documentation
- **[output compliant format.txt](output%20compliant%20format.txt)** - FHIR compliance notes
