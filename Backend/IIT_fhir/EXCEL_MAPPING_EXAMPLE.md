# Excel Mapping File - Visual Example

This document shows what the Excel mapping files look like with actual data from the Bajaj_01 insurance plan.

## File: Bajaj_01_mapping.xlsx

---

## Sheet 1: Mapping Rules

### Benefit Mapping Rules

| Keyword (Source) | Mapped To (FHIR Display Name) |
|---|---|
| air ambulance | Air Ambulance Cover |
| ambulance | Ambulance Cover |
| ayurvedic | AYUSH Treatment |
| ayush | AYUSH Treatment |
| chemotherapy | Chemotherapy |
| critical illness | Critical Illness Cover |
| daycare | Day Care Treatment |
| day care | Day Care Treatment |
| dental | Dental Treatment |
| dialysis | Dialysis Treatment |
| domiciliary | Domiciliary Hospitalization |
| home treatment | Domiciliary Hospitalization |
| emergency | Emergency Treatment |
| ... | ... |

**Purpose:** Reference for keyword transformations applied during LLM→FHIR mapping

---

## Sheet 2: Organization

| Property | Value |
|---|---|
| Resource Type | Organization |
| ID | 59e8c81a-af5d-4428-9912-8c9f3f13f113 |
| Name | Bajaj Allianz General Insurance Co. Ltd. |
| Active | True |
| Identifier 1 (Code: ROHINI) | 113 |
| Telecom 1 (phone) | 1800 209 0144 / 1800 209 5858 |
| Telecom 2 (email) | bagichelp@bajajallianz.co.in |
| Telecom 3 (url) | www.bajajallianz.com |

**Purpose:** Insurance company information extracted from FHIR bundle

---

## Sheet 3: Insurance Plan

### Basic Information

| Property | Value |
|---|---|
| Plan Name | Global Health Care |
| Status | active |
| Period Start | 2026-03-01 |
| Period End | 2027-03-01 |
| Plan Type | Individual |

### Coverage & Benefits

| Coverage Type | Benefit Name | Benefit Code | Display |
|---|---|---|---|
| Inpatient care management (procedure) | Death Benefit | 737481003 | Inpatient care management (procedure) |
| Inpatient care management (procedure) | Permanent Total Disablement Benefit | 737481003 | Inpatient care management (procedure) |
| Inpatient care management (procedure) | In-Patient Hospitalization | 737481003 | Inpatient care management (procedure) |
| Inpatient care management (procedure) | Pre-Hospitalization Medical Expenses | 737481003 | Inpatient care management (procedure) |
| Inpatient care management (procedure) | Post-Hospitalization Medical Expenses | 737481003 | Inpatient care management (procedure) |
| (Additional coverage types...) | ... | ... | ... |

**Purpose:** Plan structure, coverage types, and benefits with SNOMED CT codes

---

## Sheet 4: Exclusions

| Exclusion Category | Statement |
|---|---|
| Pre-Existing Disease | Expenses related to the treatment of a Pre-Existing Disease (PED) and its direct complications shall be excluded until the expiry of 36 months of continuous coverage after the date of inception of the first Global Health Care Policy. (Waiting period: 36 months) |
| Specified Conditions | Expenses related to the treatment of the listed Conditions, surgeries/treatments shall be excluded until the expiry of 24 months of continuous coverage after the date of inception of the first Global Health Care Policy with Us. (Waiting period: 24 months) |
| Initial Waiting Period | Expenses related to any Illness within 30 days from the first Policy commencement date shall be excluded except claims arising due to an Accident, provided the same are covered. (Waiting period: 30 days) |
| Dietary Supplements | Dietary supplements and substances that can be purchased without prescription, including but not limited to Vitamins, minerals and organic substances unless prescribed by a Medical Practitioner as part of Hospitalization claim or Day Care Treatment. |
| Unproven Treatment | Expenses related to any unproven treatment, services and supplies for or in connection with any treatment. Unproven Treatments are treatments, procedures or supplies that lack significant medical documentation. |
| Maternity | Medical Treatment Expenses traceable to childbirth (including complicated deliveries and caesarean sections incurred during Hospitalization) except ectopic pregnancy. Expenses towards miscarriage (unless due to an Accident) and lawful medical termination of pregnancy during. |
| Dental | Any Dental Treatment that comprises of cosmetic surgery, dentures, dental prosthesis, dental implants, orthodontics, surgery of any kind unless as a result of Accidental Bodily Injury to natural teeth and also requiring Hospitalization unless specified. |
| OPD Without Hospitalization | Medical expenses where Inpatient care is not warranted and does not require supervision of qualified nursing. |
| War and Conflict | War, invasion, acts of foreign enemies, hostilities (whether war be declared or not), civil war, commotion, unrest. Any Medical expenses incurred due to Act of Terrorism will be covered under the Policy. |
| Non-Allopathic Treatment | Treatment for any other system other than modern medicine (allopathy). |
| Home Medical Equipment | External medical equipment of any kind used at home as post Hospitalization care including cost of instrument used in the treatment of Sleep Apnoea Syndrome (C.P.A.P), Continuous Peritoneal Ambulatory Dialysis (C.P.A.D). |
| Intentional Harm | Intentional self-Injury (including but not limited to the use or misuse of any intoxicating drugs or alcohol). |
| Vaccination | Vaccination or inoculation unless forming a part of post bite treatment or if medically necessary and forming a part of treatment recommended by the treating Medical Practitioner. |
| Circumcision | Circumcision unless required for the treatment of Illness or Accidental bodily Injury. |
| Chemical/Radiation Exposure | Treatment for any medical conditions arising directly or indirectly from chemical contamination, radioactivity. |
| Alternative Medicine | Alternate/ Complementary treatment, with the exception of those treatments shown in the Table of Benefits. |
| Complications from Excluded Coverage | Expenses incurred because of complications directly caused by an Illness, Injury or treatment for which cover is excluded or limited under Your plan. |

**Purpose:** Complete list of policy exclusions and limitations with detailed statements

---

## Key Observations from This Example

### 1. **Organization Mapping**
- **Source:** IRDAI ID from PDF extracted via LLM
- **Mapped to:** FHIR Organization resource
- **Result:** Structured identifier system + contact information

### 2. **Benefit Mapping**
- **Source:** Raw text like "inpatient", "hospitalisation", "hospital care"
- **Mapped via:** Keyword matching in config/mapping.yaml
- **Result:** Normalized display name "In-Patient Hospitalization"

### 3. **SNOMED CT Coding**
- All benefits have SNOMED CT codes (e.g., 737481003 for inpatient care)
- These codes were assigned by the mapper based on benefit type
- **Standard:** http://snomed.info/sct per FHIR R4

### 4. **Exclusion Documentation**
- Raw exclusion statements from PDF preserved in full
- Categorized by type (Pre-Existing Disease, Waiting Periods, etc.)
- **Format:** FHIR Claim-Exclusion extensions

---

## How to Use This Example

1. **Copy the Excel file:** Open `output/pending/Bajaj_01_mapping.xlsx` in Excel
2. **Review the data:** Check each sheet for completeness
3. **Validate accuracy:** Ensure extraction matches the original PDF
4. **Use for documentation:** Share with stakeholders/judges
5. **Reference for other plans:** Use as a template for understanding output format

---

## Customization Tips

### To Change Column Order
Edit the `format_header()` calls in `utils/excel_generator.py`

### To Add More Data
Modify the sheet-building functions like `add_insurance_plan_sheet()`

### To Change Colors
Update `setup_styles()` function with different HEX color codes

### To Add/Remove Sheets
Add new functions following the pattern of existing sheets

---

## Typical File Sizes

| Sheet | Typical Rows | Size Contribution |
|---|---|---|
| Mapping Rules | 50-100 | 2-3 KB |
| Organization | 5-10 | 1 KB |
| Insurance Plan | 50-200 | 4-6 KB |
| Exclusions | 30-50 | 2-4 KB |
| **Total** | **135-360** | **~10 KB** |

---

## Format Standards

- **File Format:** XLSX (Microsoft Excel 2007+)
- **Encoding:** UTF-8
- **Column Width:** Auto-sized for readability
- **Header Styling:** Bold white text on blue background
- **Data:** Center-aligned headers, left-aligned content
- **Borders:** All cells have thin black borders
- **Text Wrapping:** Enabled for long text columns

---

## Integration with JSON

Each Excel file corresponds to a JSON bundle:

**Bajaj_01.json** contains:
```json
{
  "resourceType": "Bundle",
  "entry": [
    {
      "resource": {
        "resourceType": "Organization",
        ...  // ← Data shown in Sheet 2
      }
    },
    {
      "resource": {
        "resourceType": "InsurancePlan",
        ...  // ← Data shown in Sheet 3 & 4
      }
    }
  ]
}
```

**Bajaj_01_mapping.xlsx** provides a human-readable view of the same data structured in a more accessible format.

---

## For Hackathon Judges

When presenting or sharing your output:

1. **Show the Excel files** - Easier to understand visually
2. **Reference the JSON files** - Prove FHIR compliance
3. **Explain the mapping** - Refer to Sheet 1 for transformation logic
4. **Highlight completeness** - All exclusions documented in Sheet 4
5. **Demonstrate coverage** - Sheet 3 shows all benefits extracted

This two-file approach (JSON + Excel) provides both technical proof and accessible documentation.
