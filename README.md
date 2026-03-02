# PDFs to FHIR InsurancePlan bundles Converter

This repository contains two main components:

1. **Backend** – Python/FastAPI service that converts insurance policy PDFs to FHIR InsurancePlan bundles, validates them, and exposes REST endpoints.  A detailed backend README lives in `Backend/IIT_fhir/README.md`.
2. **Frontend** – React/Vite web application providing a step‑by‑step UI for uploading PDFs, reviewing/executing conversions, running validation, and downloading results.

---

## 1. Backend

### Brief Functional Scope

This component automates the conversion of insurance product PDF documents into **NRCeS IG v6.5.0 compliant FHIR R4 InsurancePlan bundles** for the ABDM NHCX ecosystem.

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

### High-Level Architecture

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

### Tools and Libraries Used

#### Open Source

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

#### Closed Source

| Service | Purpose |
|---------|---------|
| OpenAI GPT-4o-mini | LLM for structured data extraction from PDF text |

> **Note:** The OpenAI API is the only closed-source dependency. All application code, mapping logic, FHIR construction, and validation are fully open source. The LLM can be swapped for any OpenAI-compatible API (the codebase already has a Google GenAI import path in requirements).

### Setup Instructions

#### Prerequisites

- Python 3.11+
- OpenAI API key with GPT-4o-mini access

#### Step 1 — Clone and install dependencies

```bash
git clone <repo-url>
cd NHCX
pip install -r requirements.txt
```

#### Step 2 — Configure environment

Create a `.env` file in the project root:

```
OPENAI_API_KEY=sk-your-key-here
```

#### Step 3 — Configure pipeline settings

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

#### Step 4 — Run

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

### Dependencies

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


---

## 2. Frontend

### Brief Functional Scope
A single‑page React application that interacts with the backend to:

1. Upload insurance plan PDF files.
2. Display real‑time conversion progress returned by the backend.
3. Show the resulting FHIR JSON bundle side‑by‑side with a console.
4. Allow manual edits via the console/JSON panel.
5. Trigger validation and present detailed error/warning reports.
6. Download the final JSON or generate an Excel mapping file.

### High‑Level Architecture

```
React SPA (Vite)
┌──────────┐   fetch   ┌──────────────┐
│Upload    │─────────▶│FastAPI       │
│Section   │◀─────────│/convert      │
└──────────┘   JSON   │/validate     │
    │                    └──────────────┘
    ▼
┌──────────┐
│Review &  │
│JSON Panel│
└──────────┘
    │
    ▼
┌──────────┐
│Validation│
│Results   │
└──────────┘
    │
    ▼
┌──────────┐           ┌───────────┐
│Download  │◀──────────│Excel API  │
└──────────┘           └───────────┘
```

React components are stored under `Frontend/NHCX-frontend/src/components`.

### Tools and Libraries Used

**Open Source**

- React 18 / Vite
- Tailwind CSS
- Lucide icons
- Fetch API (built‑in browser)
- ESLint / Prettier (config files included)

**Closed Source**

- None (the frontend only communicates with the backend; all proprietary functionality resides there).

### Setup Instructions

1. Install Node.js (v18+ recommended).
2. Open a terminal in `Frontend/NHCX-frontend`.
3. Run:
   ```bash
   npm install
   npm run dev      # starts development server on http://localhost:5173
   ```
4. Edit `src/components/*` as needed. Build for production with `npm run build`.

### Dependencies

Dependencies are defined in `Frontend/NHCX-frontend/package.json`:

```json
{
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "lucide-react": "^0.256.1"
  },
  "devDependencies": {
    "vite": "^4.4.9",
    "tailwindcss": "^3.4.8",
    "postcss": "^8.4.27",
    "autoprefixer": "^10.4.14"
  }
}
```

Install with `npm install`.

### Implementation Details

- **Workflow components** live under `src/components/workflow` and correspond to the four steps: Upload, Review, Validate, Download.
- JSON editing is handled by `JsonPanel.jsx`, which toggles editable state when users click the 'Edit' button.
- Progress polling occurs every 500 ms during upload; messages from `/progress` endpoint update bars.
- Validation screen shows error/warning lists returned by backend; progress metrics have been removed per requirements.
- CORS is enabled on backend (`*` allowed origins) so the frontend can run on a different port during development.

### Running End‑to‑End

1. Start the backend (see Backend README).
2. Start the frontend with `npm run dev`.
3. Open http://localhost:5173 and interact with the UI.

---

## License

All code in this repository is licensed under MIT unless noted otherwise. The only external service is the OpenAI API (see Backend README).

---

*This combined README should allow evaluators to understand and execute the entire solution.*
