# NHCX Insurance Plan PDF-to-FHIR Converter

---

## Brief Functional Scope

This solution automates the conversion of insurance product PDF documents into **NRCeS IG v6.5.0 compliant FHIR R4 InsurancePlan bundles** for the ABDM NHCX ecosystem.

**What it does:**

1. Accepts an insurance plan PDF (product brochure / policy wording)
2. Extracts text from the PDF
3. Uses an LLM to parse insurance-specific structured data (benefits, limits, sub-limits, exclusions, waiting periods, co-pay, eligibility rules)
4. Maps the extracted data into a FHIR R4 Bundle containing `Organization` + `InsurancePlan` resources, fully profiled per NRCeS NHCX StructureDefinitions
5. Validates the output against both FHIR R4 structural rules and NRCeS IG profile constraints
6. Outputs the validated JSON bundle

**Interfaces available:**
- CLI batch pipeline (`python main.py`)
- REST API with Swagger docs (`POST /convert`, `POST /validate`)
- React + Vite human review UI

---

## High-Level Architecture

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   PDF Input  │────▶│  Text        │────▶│  LLM         │────▶│  FHIR        │────▶│  Validator   │
│              │     │  Extractor   │     │  Extraction  │     │  Mapper      │     │              │
│  (PyMuPDF)   │     │  (pdf.py)    │     │ (openai_llm) │     │(nhcx_mapper) │     │(fhir_valid.) │
└──────────────┘     └──────────────┘     └──────────────┘     └──────────────┘     └──────┬───────┘
                                                                                           │
                                                                          ┌────────────────┼────────────┐
                                                                          │                │            │
                                                                   ┌──────▼──────┐  ┌──────▼──────┐     │
                                                                   │  Streamlit  │  │  JSON File  │     │
                                                                   │  Review UI  │  │  Output     │     │
                                                                   │  (optional) │  │             │     │
                                                                   └─────────────┘  └─────────────┘     │
                                                                                                        │
                                                                                              ┌─────────▼───┐
                                                                                              │  FastAPI    │
                                                                                              │  REST API   │
                                                                                              │  /convert   │
                                                                                              │  /validate  │
                                                                                              └─────────────┘
```

**Pipeline stages:**

| Stage | Module | Description |
|-------|--------|-------------|
| 1. Extract | `extractor/pdf.py` | Extracts raw text from PDF using PyMuPDF |
| 2. Parse | `llm/openai_llm.py` | Sends text to GPT-4o-mini with structured prompts; filters irrelevant sections via keyword matching; chunks large documents; returns structured JSON |
| 3. Map | `mapper/nhcx_mapper.py` | Builds FHIR R4 Bundle with Organization + InsurancePlan resources. Applies SNOMED CT coding, NDHM CodeSystems, Claim-Exclusion/Claim-Condition extensions. Validates IRDAI exclusion codes via keyword guard |
| 4. Validate | `validator/fhir_validator.py` | Two-layer validation: (a) FHIR R4 Pydantic model validation via `fhir.resources`, (b) NRCeS IG profile checks (identifiers, CodeSystems, mandatory fields, extension structure) |
| 5. Output | `main.py` / `app_api.py` | Saves JSON or returns via REST API |

---

## Tools and Libraries Used

### Open Source

| Library | Version | Purpose |
|---------|---------|---------|
| Python | 3.11 | Runtime |
| PyMuPDF (fitz) | 1.24.9 | PDF text extraction |
| fhir.resources | 7.1.0 | FHIR R4 Pydantic model validation |
| Pydantic | 2.8.2 | Data validation and JSON schema |
| FastAPI | 0.115.0 | REST API framework |
| Uvicorn | 0.30.6 | ASGI server for FastAPI |
| Streamlit | 1.37.1 | Human review UI |
| PyYAML | 6.0.2 | Configuration file parsing |
| python-dotenv | 1.0.1 | Environment variable management |
| httpx | 0.27.2 | HTTP client (used by OpenAI SDK) |
| tqdm | 4.66.5 | CLI progress bars |
| python-multipart | 0.0.22 | File upload handling for FastAPI |
| pytest | (dev) | Test framework (82 tests) |

### Closed Source

| Service | Purpose |
|---------|---------|
| OpenAI GPT-4o-mini | LLM for structured data extraction from PDF text |

> **Note:** The OpenAI API is the only closed-source dependency. All application code, mapping logic, FHIR construction, and validation are fully open source. The LLM can be swapped for any OpenAI-compatible API (the codebase already has a Google GenAI import path in requirements).

---

## Setup Instructions

### Prerequisites

- Python 3.11+
- OpenAI API key with GPT-4o-mini access

### Step 1 — Clone and install dependencies

```bash
git clone <repo-url>
cd NHCX
pip install -r requirements.txt
```

### Step 2 — Configure environment

Create a `.env` file in the project root:

```
OPENAI_API_KEY=sk-your-key-here
```

### Step 3 — Configure pipeline settings

Edit `config/settings.yaml`:

```yaml
llm:
  provider: openai
  model: gpt-4o-mini

pipeline:
  enable_validation: true
  enable_human_review: false   # set true to route output through Streamlit UI

paths:
  input: input_pdfs/pdfs       # folder containing input PDFs
  output: output               # folder for generated FHIR bundles
```

### Step 4 — Run

**CLI batch pipeline:**
```bash
# Process all PDFs in the configured input folder
python main.py

# Process a specific folder
python main.py --input input_pdfs/test
```

**REST API:**
```bash
# Start the API server
cd NHCX
python -m uvicorn app_api:app --host 0.0.0.0 --port 8000

# Swagger docs at http://localhost:8000/docs
```

**Human review UI:**
```bash
streamlit run reviewer/review_ui.py
```

**Run tests:**
```bash
python -m pytest tests/ -v
```

**Generate Excel mapping files (automatic during pipeline, or manually):**
```bash
# Generate Excel for all JSON files in a directory
python generate_excel_mappings.py --dir output/pending

# Generate Excel for a single JSON file
python generate_excel_mappings.py --file output/pending/Plan_Name.json
```

See [EXCEL_MAPPING_DOCUMENTATION.md](EXCEL_MAPPING_DOCUMENTATION.md) for details on Excel file contents and usage.

---

## Dependencies

All dependencies are pinned in `requirements.txt`:

```
openai==1.51.0
pymupdf==1.24.9
pyyaml==6.0.2
tqdm==4.66.5
streamlit==1.37.1
fhir.resources==7.1.0
python-dotenv==1.0.1
pydantic==2.8.2
fastapi==0.115.0
uvicorn==0.30.6
python-multipart==0.0.22
httpx==0.27.2
```

Install all with: `pip install -r requirements.txt`

---

## Implementation Details

### Project Structure

```
NHCX/
├── main.py                  # CLI pipeline entry point (argparse, batch processing)
├── app_api.py               # FastAPI REST API (POST /convert, POST /validate, GET /health)
├── requirements.txt         # Pinned Python dependencies
├── Dockerfile               # Container deployment
├── .env                     # OpenAI API key (not committed)
├── config/
│   ├── settings.yaml        # Pipeline configuration (LLM model, paths, flags)
│   └── mapping.yaml         # Benefit/exclusion terminology normalization (80+ mappings)
├── extractor/
│   └── pdf.py               # PDF text extraction via PyMuPDF
├── llm/
│   └── openai_llm.py        # LLM extraction: keyword filtering, chunking, structured prompts,
│                             #   placeholder detection, rate-limit retry logic
├── mapper/
│   └── nhcx_mapper.py       # FHIR R4 Bundle builder: SNOMED CT coding, NDHM CodeSystems,
│                             #   IRDAI exclusion code keyword validation guard (Excl01–Excl18),
│                             #   Claim-Exclusion/Claim-Condition extensions
├── validator/
│   └── fhir_validator.py    # Two-layer validation: FHIR R4 Pydantic + NRCeS IG profile checks
├── reviewer/
│   └── review_ui.py         # Streamlit UI for human review and approval
├── utils/
│   └── logger.py            # Centralized logging configuration
├── tests/
│   └── test_pipeline.py     # 82 automated tests
├── input_pdfs/              # Input PDF documents
├── output/                  # Generated FHIR JSON bundles
│   └── pending/             # Bundles awaiting human review
└── logs/                    # Pipeline and LLM debug logs
```

### FHIR Compliance — NRCeS IG v6.5.0

The output bundle conforms to the following NRCeS NHCX profiles:

| Profile | URL |
|---------|-----|
| InsurancePlanBundle | `https://nrces.in/ndhm/fhir/r4/StructureDefinition/InsurancePlanBundle` |
| InsurancePlan | `https://nrces.in/ndhm/fhir/r4/StructureDefinition/InsurancePlan` |
| Organization | `https://nrces.in/ndhm/fhir/r4/StructureDefinition/Organization` |

**CodeSystems used:**

| CodeSystem | URL | Usage |
|------------|-----|-------|
| SNOMED CT | `http://snomed.info/sct` | `coverage.benefit.type` (real SNOMED codes) |
| NDHM InsurancePlan Type | `https://nrces.in/ndhm/fhir/r4/CodeSystem/ndhm-insuranceplan-type` | `InsurancePlan.type` |
| NDHM Plan Type | `https://nrces.in/ndhm/fhir/r4/CodeSystem/ndhm-plan-type` | `plan.type` |
| NDHM Claim Exclusion | `https://nrces.in/ndhm/fhir/r4/CodeSystem/ndhm-claim-exclusion` | Exclusion coding (Excl01–Excl18) |
| NDHM Identifier Type | `https://nrces.in/ndhm/fhir/r4/CodeSystem/ndhm-identifier-type-code` | Organization identifier type |
| InsurancePlan Cost Type | `http://terminology.hl7.org/CodeSystem/insuranceplan-cost-type` | `plan.specificCost` |

**Extensions used:**

| Extension | URL | Purpose |
|-----------|-----|---------|
| Claim-Exclusion | `https://nrces.in/ndhm/fhir/r4/StructureDefinition/Claim-Exclusion` | Policy exclusions with category + statement |
| Claim-Condition | `https://nrces.in/ndhm/fhir/r4/StructureDefinition/Claim-Condition` | Eligibility and claim conditions |

### IRDAI Exclusion Code Validation

The mapper includes a keyword validation guard that prevents incorrect IRDAI exclusion code assignments. Each exclusion code (Excl01–Excl18) has associated keywords that must appear in the exclusion text for the code to be assigned. If the text does not match, the exclusion is output as text-only (no `coding`), avoiding false IRDAI mappings.

### REST API Endpoints

| Method | Path | Input | Output |
|--------|------|-------|--------|
| `POST` | `/convert` | PDF file (multipart upload) | FHIR Bundle JSON + validation report |
| `POST` | `/validate` | JSON file (multipart upload) | Validation report (pass/fail + error list) |
| `GET` | `/health` | — | `{"status": "ok"}` |

Swagger documentation: `http://localhost:8000/docs`

### Output Format

Each output is a FHIR R4 Bundle (`type: collection`) containing:
- **Organization** — insurer name, ROHINI ID, contact details
- **InsurancePlan** — plan name, UIN, period, coverage with coded benefits, plan costs with sub-limits and waiting periods, exclusions as extensions

---

## License

Open source.
