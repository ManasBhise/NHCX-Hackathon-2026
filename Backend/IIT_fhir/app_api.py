"""
NHCX FastAPI endpoints.

1. POST /convert        — Upload a PDF, get FHIR InsurancePlan Bundle JSON back
2. POST /validate       — Upload a JSON file, get detailed validation report with percentages
3. POST /json-to-excel  — Upload a JSON bundle, get Excel mapping file back
4. GET /health          — Health check

Run:
    cd NHCX
    python -m uvicorn app_api:app --host 0.0.0.0 --port 8000
"""

import os
import sys
import json
import uuid
import logging
import tempfile
import traceback
import time
import asyncio

# Ensure the project root is on sys.path so imports work from any cwd
_PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
os.chdir(_PROJECT_ROOT)

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware

from utils.logger import setup_logging
from extractor.pdf import extract_text
from llm.openai_llm import extract_insurance_data
from mapper.nhcx_mapper import map_to_fhir
from validator.enhanced_validator import validate_with_percentage, format_percentage_report
from utils.excel_generator import generate_excel_from_json

setup_logging()
logger = logging.getLogger(__name__)

app = FastAPI(
    title="NHCX PDF-to-FHIR API",
    description="Convert insurance PDF documents to NRCeS IG v6.5.0 compliant FHIR InsurancePlan bundles, and validate existing bundles.",
    version="1.0.0",
)

# Add CORS middleware to allow frontend requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins in development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global progress tracking
_conversion_progress = {
    "status": "idle",  # idle, extracting, mapping, complete
    "current_step": 0,  # 0-100
    "current_chunk": 0,
    "total_chunks": 0,
    "message": "Waiting for upload..."
}


# ─────────────────────────────────────────────
# POST /convert — PDF ➜ FHIR JSON
# ─────────────────────────────────────────────
@app.post("/convert", summary="Convert PDF to FHIR InsurancePlan Bundle")
async def convert_pdf(file: UploadFile = File(...)):
    """
    Upload an insurance policy PDF. Returns the FHIR InsurancePlan Bundle JSON.

    Response includes:
    - `bundle`: The FHIR Bundle (InsurancePlanBundle + Organization + InsurancePlan)
    - `filename`: Original filename
    - `message`: Conversion status
    
    Note: No automatic validation. Use POST /validate endpoint separately for detailed validation.
    """
    global _conversion_progress

    # ── Guard: must be PDF ──
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted.")

    # ── Save upload to temp file ──
    tmp_path = None
    try:
        _conversion_progress = {
            "status": "uploading",
            "current_step": 5,
            "current_chunk": 0,
            "total_chunks": 0,
            "message": "Processing uploaded file..."
        }

        contents = await file.read()
        if len(contents) == 0:
            raise HTTPException(status_code=400, detail="Uploaded file is empty.")

        suffix = ".pdf"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(contents)
            tmp_path = tmp.name

        # Step 1 — Extract text (granular progress updates)
        _conversion_progress = {
            "status": "extracting",
            "current_step": 10,
            "current_chunk": 0,
            "total_chunks": 0,
            "message": "Starting text extraction from PDF..."
        }
        await asyncio.sleep(0.3)  # Small delay for UI update
        
        text = extract_text(tmp_path)
        
        _conversion_progress = {
            "status": "extracting",
            "current_step": 25,
            "current_chunk": 0,
            "total_chunks": 0,
            "message": "Text extraction complete, processing content..."
        }
        
        if not text.strip():
            raise HTTPException(
                status_code=422,
                detail="Could not extract any text from the PDF. The file may be scanned/image-only.",
            )

        # Step 2 — LLM extraction (granular progress)
        _conversion_progress = {
            "status": "extracting",
            "current_step": 40,
            "current_chunk": 0,
            "total_chunks": 0,
            "message": "Extracting insurance data with AI..."
        }
        await asyncio.sleep(0.3)
        
        data = extract_insurance_data(text)
        
        _conversion_progress = {
            "status": "extracting",
            "current_step": 60,
            "current_chunk": 0,
            "total_chunks": 0,
            "message": "Insurance data extraction complete..."
        }
        
        if not data.get("plan_name") and not data.get("benefits"):
            raise HTTPException(
                status_code=422,
                detail="LLM could not extract meaningful insurance data from the PDF.",
            )

        # Step 3 — Map to FHIR (NO automatic validation, granular progress)
        _conversion_progress = {
            "status": "mapping",
            "current_step": 75,
            "current_chunk": 0,
            "total_chunks": 0,
            "message": "Mapping to FHIR standard format..."
        }
        await asyncio.sleep(0.3)
        
        bundle = map_to_fhir(data)
        
        _conversion_progress = {
            "status": "completing",
            "current_step": 95,
            "current_chunk": 0,
            "total_chunks": 0,
            "message": "Finalizing conversion..."
        }
        await asyncio.sleep(0.2)

        _conversion_progress = {
            "status": "complete",
            "current_step": 100,
            "current_chunk": 0,
            "total_chunks": 0,
            "message": "✓ Conversion complete!"
        }

        logger.info(f"Converted {file.filename} to FHIR Bundle successfully")

        return JSONResponse(
            status_code=200,
            content={
                "filename": file.filename,
                "bundle": bundle,
                "message": "✓ PDF successfully converted to FHIR Bundle. Use POST /validate endpoint for validation.",
            },
        )

    except HTTPException:
        _conversion_progress = {
            "status": "error",
            "current_step": 0,
            "current_chunk": 0,
            "total_chunks": 0,
            "message": "Conversion failed"
        }
        raise
    except Exception as e:
        _conversion_progress = {
            "status": "error",
            "current_step": 0,
            "current_chunk": 0,
            "total_chunks": 0,
            "message": f"Error: {str(e)}"
        }
        logger.error(f"Conversion failed for {file.filename}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Conversion failed: {str(e)}")
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


# ─────────────────────────────────────────────
# POST /validate — JSON ➜ Validation Report (with percentages)
# ─────────────────────────────────────────────
@app.post("/validate", summary="Validate FHIR Bundle with percentage-based reporting")
async def validate_bundle(file: UploadFile = File(...)):
    """
    Upload a FHIR Bundle JSON file. Returns detailed validation results with percentage scores.

    Response includes:
    - `valid`: Boolean — true if zero errors
    - `completion_percentage`: % of checks passed (0-100)
    - `compliance_percentage`: % FHIR/NHCX compliance (0-100)
    - `error_count`: Number of errors found
    - `warning_count`: Number of warnings found
    - `errors`: Detailed error list with remediation steps
    - `warnings`: Detailed warning list
    - `category_scores`: Breakdown by validation category
    - `detailed_report`: Human-readable report with percentages
    """

    if not file.filename.lower().endswith(".json"):
        raise HTTPException(status_code=400, detail="Only JSON files are accepted.")

    try:
        contents = await file.read()
        if len(contents) == 0:
            raise HTTPException(status_code=400, detail="Uploaded file is empty.")

        # Parse JSON
        try:
            bundle = json.loads(contents.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            raise HTTPException(status_code=400, detail=f"Invalid JSON: {str(e)}")

        # Basic sanity check
        if not isinstance(bundle, dict):
            raise HTTPException(status_code=400, detail="JSON root must be an object.")

        if bundle.get("resourceType") != "Bundle":
            raise HTTPException(
                status_code=400,
                detail=f"Expected resourceType 'Bundle', got '{bundle.get('resourceType', 'missing')}'.",
            )

        # Validate with percentage reporting
        report = validate_with_percentage(bundle)
        detailed_report = format_percentage_report(report)

        logger.info(
            f"Validated {file.filename}: "
            f"{report.compliance_percentage:.1f}% compliance, "
            f"{len(report.errors)} errors, "
            f"{len(report.warnings)} warnings"
        )

        # Build response
        errors_list = [
            {
                "category": e.category,
                "severity": e.severity,
                "resource": e.resource,
                "field": e.field,
                "message": e.message,
                "remediation": e.remediation
            }
            for e in report.errors
        ]
        
        warnings_list = [
            {
                "category": w.category,
                "severity": w.severity,
                "resource": w.resource,
                "field": w.field,
                "message": w.message,
                "remediation": w.remediation
            }
            for w in report.warnings
        ]

        return JSONResponse(
            status_code=200,
            content={
                "filename": file.filename,
                "valid_percentage": round(report.completion_percentage, 2),
                "compliance_percentage": round(report.compliance_percentage, 2),
                "total_checks": report.total_checks,
                "passed_checks": report.passed_checks,
                "failed_checks": report.failed_checks,
                "error_count": len(report.errors),
                "warning_count": len(report.warnings),
                "errors": errors_list,
                "warnings": warnings_list,
                "detailed_report": detailed_report,
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Validation failed for {file.filename}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Validation failed: {str(e)}")


# ─────────────────────────────────────────────
# POST /json-to-excel — JSON ➜ Excel Mapping File
# ─────────────────────────────────────────────
@app.post("/json-to-excel", summary="Convert FHIR Bundle JSON to Excel mapping file")
async def json_to_excel(file: UploadFile = File(...)):
    """
    Upload a FHIR Bundle JSON file. Returns an Excel file with mapping sheets.

    The Excel file includes:
    1. Data Mapping: Source clinical attributes → FHIR resource paths
    2. Mapping Rules: Benefit keyword normalization rules
    3. Organization: Insurance company details
    4. Insurance Plan: Benefits and coverage structure
    5. Exclusions: Policy exclusions and limitations

    Returns the Excel file as a downloadable attachment.
    """

    if not file.filename.lower().endswith(".json"):
        raise HTTPException(status_code=400, detail="Only JSON files are accepted.")

    tmp_excel_path = None
    tmp_json_path = None
    
    try:
        contents = await file.read()
        if len(contents) == 0:
            raise HTTPException(status_code=400, detail="Uploaded file is empty.")

        # Parse JSON to validate it's correct
        try:
            bundle = json.loads(contents.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            raise HTTPException(status_code=400, detail=f"Invalid JSON: {str(e)}")

        # Verify it's a Bundle
        if not isinstance(bundle, dict) or bundle.get("resourceType") != "Bundle":
            raise HTTPException(
                status_code=400,
                detail="JSON must be a FHIR Bundle (resourceType='Bundle')"
            )

        # Save JSON to temp file (needed for excel generator to find raw_llm file)
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix=".json") as tmp_json:
            json.dump(bundle, tmp_json)
            tmp_json_path = tmp_json.name

        # Generate temporary Excel output path
        with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp_excel:
            tmp_excel_path = tmp_excel.name

        # Generate Excel from the JSON
        excel_filename = file.filename.replace(".json", "_mapping.xlsx")
        result_path = generate_excel_from_json(tmp_json_path, output_excel_path=tmp_excel_path, logger_obj=logger)
        
        if not result_path or not os.path.exists(result_path):
            raise Exception("Excel generation failed - no output file created")

        logger.info(f"Generated Excel for {file.filename}: {excel_filename}")

        # Return the Excel file
        return FileResponse(
            path=result_path,
            filename=excel_filename,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={excel_filename}"}
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Excel generation failed for {file.filename}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Excel generation failed: {str(e)}"
        )
    finally:
        # Clean up temp JSON file
        if tmp_json_path and os.path.exists(tmp_json_path):
            try:
                os.unlink(tmp_json_path)
            except:
                pass
        # Note: tmp_excel_path cleanup deferred - file is returned to client before cleanup


# ─────────────────────────────────────────────
# GET /progress — Get conversion progress
# ─────────────────────────────────────────────
@app.get("/progress", summary="Get PDF conversion progress")
async def get_progress():
    """
    Returns the current progress of PDF to FHIR conversion.
    
    Response includes:
    - `status`: Current step (idle, extracting, mapping, complete)
    - `current_step`: Overall progress 0-100
    - `current_chunk`: Current chunk being processed
    - `total_chunks`: Total chunks to process
    - `message`: Human-readable status message
    """
    global _conversion_progress
    return _conversion_progress


# ─────────────────────────────────────────────
# GET /health — Health check
# ─────────────────────────────────────────────
@app.get("/health", summary="Health check")
async def health():
    return {"status": "ok"}
