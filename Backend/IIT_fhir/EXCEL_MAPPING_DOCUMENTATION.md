# Excel Mapping File Generation - Documentation

## Overview

You now have a complete system that automatically generates **Excel mapping files** alongside your FHIR JSON outputs. These Excel files provide a detailed view of how insurance plan data has been mapped from PDFs into the FHIR R4 standard format.

## What's New

### 1. **Automated Excel Generation on Pipeline Run**
When you run `python main.py`, the system now automatically generates a corresponding Excel file for each JSON output.

### 2. **Excel File Structure**

Each generated Excel file contains **4 sheets**:

#### Sheet 1: **Mapping Rules**
- Shows the benefit name mappings defined in `config/mapping.yaml`
- Displays the keyword matching patterns and their normalized FHIR display names
- Shows exclusion category mappings
- **Purpose:** Understand what transformation rules were applied

#### Sheet 2: **Organization**
- Contains the insurance company/provider details
- Fields include:
  - Company name
  - IRDAI registration number
  - Contact information (phone, email, website)
  - Resource identifiers
- **Purpose:** View organization metadata from the FHIR bundle

#### Sheet 3: **Insurance Plan**
- Shows the main insurance plan details
- Includes:
  - Plan name and status
  - Policy period (start/end dates)
  - Plan type classification
  - Coverage types
  - Benefits offered with SNOMED CT codes
- **Purpose:** Review plan structure and benefits in tabular format

#### Sheet 4: **Exclusions**
- Lists all claim exclusions defined in the policy
- Two columns:
  - **Exclusion Category:** The type of exclusion (e.g., "Pre-Existing Disease")
  - **Statement:** The detailed exclusion text
- **Purpose:** Easily review policy limitations and exclusions

## File Naming Convention

```
Source JSON:     Bajaj_01.json
Excel File:      Bajaj_01_mapping.xlsx
```

Each Excel file shares the same base name as its corresponding JSON file but includes `_mapping` before the `.xlsx` extension.

## How to Use

### Option 1: Automatic Generation (Recommended)
Just run the normal pipeline:
```bash
python main.py
```
Excel files are automatically created in the same folder as the JSON outputs.

### Option 2: Manual Generation from Existing JSONs
If you already have JSON files and want to (re)generate Excel mappings:

**Process a single file:**
```bash
python generate_excel_mappings.py --file "output/pending/Aditya Birla_02.json"
```

**Process all files in a directory:**
```bash
python generate_excel_mappings.py --dir "output/pending"
```

**Check all available options:**
```bash
python generate_excel_mappings.py --help
```

## Current Generated Files

The following Excel mapping files have been created:

| JSON File | Excel File | Size |
|-----------|-----------|------|
| Aditya Birla_02.json | Aditya Birla_02_mapping.xlsx | 9.5 KB |
| Bajaj_01.json | Bajaj_01_mapping.xlsx | 11.5 KB |
| Bajaj_02.json | Bajaj_02_mapping.xlsx | 9.6 KB |
| Bajaj(G)_03.json | Bajaj(G)_03_mapping.xlsx | 9.4 KB |
| Care_01.json | Care_01_mapping.xlsx | 10.2 KB |
| Care(G)_02.json | Care(G)_02_mapping.xlsx | 10.1 KB |
| Cholamandalam(G)_03.json | Cholamandalam(G)_03_mapping.xlsx | 9.3 KB |

All files are located in: `output/pending/`

## Technical Details

### Implementation Components

1. **`utils/excel_generator.py`** - Core Excel generation logic
   - `generate_excel_from_json()` - Convert single JSON to Excel
   - `process_all_outputs()` - Batch process directory of JSONs
   - Functions to build each sheet with proper formatting

2. **`generate_excel_mappings.py`** - CLI utility
   - Command-line interface for manual Excel generation
   - Flexible options for single files or directories

3. **Integration in `main.py`**
   - Step 6 of the pipeline automatically calls Excel generator
   - Uses the logging system for status updates
   - Non-blocking (errors in Excel generation don't fail the pipeline)

### Technologies Used

- **openpyxl** (v3.1.2) - Excel file creation and formatting
- **Styling:** Header colors, merged cells, wrapped text, borders
- **Auto-sizing:** Columns adjust to content width for readability

## Use Cases for Hackathon

### 1. **Documentation & Submission**
Include both JSON and Excel files in your hackathon submission:
- JSON files for programmatic validation and processing
- Excel files for human review and presentation

### 2. **Data Quality Review**
Use the sheets to verify:
- Are all benefits properly extracted and mapped?
- Are exclusions correctly categorized?
- Is organization data complete?

### 3. **Mapping Validation**
Check the "Mapping Rules" sheet to confirm:
- Which benefit keywords were matched
- What normalization rules were applied
- Which display names were assigned

### 4. **Stakeholder Presentation**
Excel files are more accessible type for:
- Insurance company representatives
- Reviewers and evaluators
- Non-technical stakeholders

## Customization

To modify the Excel output, edit `utils/excel_generator.py`:

- **Change colors:** Modify `setup_styles()` function
- **Add/remove sheets:** Add new `add_*_sheet()` functions
- **Change data displayed:** Modify sheet-building functions
- **Adjust formatting:** Edit styling parameters

## Dependencies

Added to `requirements.txt`:
- `openpyxl==3.1.2`

Install with:
```bash
pip install -r requirements.txt
```

## FAQ

**Q: Will Excel generation slow down my pipeline?**
A: No. Excel generation adds ~0.5-1 second per file, which is negligible compared to PDF extraction and LLM processing.

**Q: What if JSON generation fails?**
A: Excel files are only generated if JSON output is successfully created. If JSON generation fails, no Excel file is created.

**Q: Can I customize the Excel format?**
A: Yes! Edit `utils/excel_generator.py` to change colors, add/remove columns, modify sheet structure, etc.

**Q: Do I need to regenerate existing Excel files?**
A: Only if you modify the `utils/excel_generator.py` code or want to update old files. Use:
```bash
python generate_excel_mappings.py --dir "output/pending"
```

**Q: Can I process files from other directories?**
A: Yes, use the `--dir` parameter:
```bash
python generate_excel_mappings.py --dir "output/"
```

## Summary

You now have a complete solution for generating Excel mapping files that document:
1. **What rules were applied** (Mapping Rules sheet)
2. **What was extracted** (Organization and Insurance Plan sheets)
3. **What was excluded** (Exclusions sheet)

This provides both technical documentation (JSON) and human-readable documentation (Excel) suitable for hackathon submission and stakeholder communication.
