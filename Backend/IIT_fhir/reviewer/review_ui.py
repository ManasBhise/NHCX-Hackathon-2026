"""
Streamlit-based Human Review UI for NHCX InsurancePlan Bundles.

Launch with:  streamlit run reviewer/review_ui.py

Shows pending bundles from output/pending/, allows editing,
validates, and saves approved bundles to output/.
"""

import streamlit as st
import json
import os
import sys
import glob

# Add project root to path so imports work
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from validator.fhir_validator import validate, format_validation_report

PENDING_DIR = "output/pending"
APPROVED_DIR = "output"


def load_pending_files():
    """List all JSON files awaiting review."""
    if not os.path.exists(PENDING_DIR):
        return []
    return sorted(glob.glob(os.path.join(PENDING_DIR, "*.json")))


def load_bundle(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_bundle(bundle, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(bundle, f, indent=2, ensure_ascii=False)


def get_plan_resource(bundle):
    """Extract the InsurancePlan resource from the bundle."""
    for entry in bundle.get("entry", []):
        if entry.get("resource", {}).get("resourceType") == "InsurancePlan":
            return entry["resource"]
    return None


def get_org_resource(bundle):
    """Extract the Organization resource from the bundle."""
    for entry in bundle.get("entry", []):
        if entry.get("resource", {}).get("resourceType") == "Organization":
            return entry["resource"]
    return None


def main():
    st.set_page_config(page_title="NHCX InsurancePlan Reviewer", layout="wide")
    st.title("NHCX InsurancePlan — Human Review")

    pending_files = load_pending_files()

    if not pending_files:
        st.info("No bundles pending review. Run the pipeline first with `enable_human_review: true`.")
        return

    # ── File selector ──
    st.sidebar.header("Pending Reviews")
    selected_file = st.sidebar.selectbox(
        "Select a bundle to review:",
        pending_files,
        format_func=lambda x: os.path.basename(x)
    )

    if not selected_file:
        return

    bundle = load_bundle(selected_file)
    plan = get_plan_resource(bundle)
    org = get_org_resource(bundle)

    if not plan:
        st.error("No InsurancePlan resource found in this bundle.")
        return

    st.subheader(f"Reviewing: {os.path.basename(selected_file)}")

    # ── Organization Info ──
    st.header("1. Organization")
    col1, col2 = st.columns(2)
    with col1:
        org_name = st.text_input("Organization Name", value=org.get("name", "") if org else "")
    with col2:
        plan_status = st.selectbox("Plan Status", ["active", "draft", "retired"],
                                    index=["active", "draft", "retired"].index(plan.get("status", "active")))

    # ── Plan Info ──
    st.header("2. Plan Details")
    col1, col2 = st.columns(2)
    with col1:
        plan_name = st.text_input("Plan Name", value=plan.get("name", ""))
    with col2:
        plan_type_text = ""
        if plan.get("type") and len(plan["type"]) > 0:
            plan_type_text = plan["type"][0].get("text", "")
        plan_type = st.text_input("Plan Type", value=plan_type_text)

    # ── Benefits (grouped by coverage category) ──
    st.header("3. Benefits")
    coverages = plan.get("coverage", [])
    if coverages:
        total_benefits = sum(len(c.get("benefit", [])) for c in coverages)
        st.write(f"**{total_benefits} benefits across {len(coverages)} categories**")

        ben_idx = 0
        for ci, cov in enumerate(coverages):
            cov_type = cov.get("type", {}).get("coding", [{}])[0].get("display", "Unknown Category")
            st.subheader(f"Category: {cov_type}")

            for bi, ben in enumerate(cov.get("benefit", [])):
                with st.expander(f"Benefit {ben_idx+1}: {ben.get('type', {}).get('text', 'Unknown')}"):
                    ben_text = st.text_input(f"Name##b{ben_idx}", value=ben.get("type", {}).get("text", ""), key=f"ben_{ben_idx}")
                    if ben_text:
                        ben["type"]["text"] = ben_text

                    # Show duration limits (coverage.benefit.limit)
                    limits = ben.get("limit", [])
                    if limits:
                        for li, lim in enumerate(limits):
                            val = lim.get("value", {})
                            st.text(f"  Limit: {val.get('value', '')} {val.get('comparator', '')} {val.get('unit', '')}")

                    # Show Claim-Condition descriptions from coverage extensions
                    cov_exts = cov.get("extension", [])
                    if cov_exts and bi < len(cov_exts):
                        ext = cov_exts[bi]
                        for sub in ext.get("extension", []):
                            if sub.get("url") == "claim-condition":
                                st.text(f"  Description: {sub.get('valueString', '')}")

                ben_idx += 1
    else:
        st.warning("No coverage/benefits found.")

    # ── Exclusions (Claim-Exclusion extensions) ──
    st.header("4. Exclusions")
    CLAIM_EXCLUSION_URL = "https://nrces.in/ndhm/fhir/r4/StructureDefinition/Claim-Exclusion"
    excl_exts = [e for e in plan.get("extension", []) if e.get("url") == CLAIM_EXCLUSION_URL]
    if excl_exts:
        st.write(f"**{len(excl_exts)} exclusions found**")
        for i, ext in enumerate(excl_exts):
            # Extract category and statement from sub-extensions
            exc_name = ""
            exc_statement = ""
            for sub in ext.get("extension", []):
                if sub.get("url") == "category":
                    exc_name = sub.get("valueCodeableConcept", {}).get("text", "")
                elif sub.get("url") == "statement":
                    exc_statement = sub.get("valueString", "")

            with st.expander(f"Exclusion {i+1}: {exc_name}"):
                new_name = st.text_input(f"Name##e{i}", value=exc_name, key=f"exc_{i}")
                new_statement = st.text_area(f"Statement##e{i}", value=exc_statement, key=f"exc_s_{i}")
                # Update the extension sub-values
                for sub in ext.get("extension", []):
                    if sub.get("url") == "category":
                        sub["valueCodeableConcept"]["text"] = new_name
                    elif sub.get("url") == "statement":
                        sub["valueString"] = new_statement
    else:
        st.info("No exclusions found.")

    # ── Sum Insured ──
    st.header("4b. Sum Insured")
    plans_section = plan.get("plan", [])
    if plans_section:
        general_costs = plans_section[0].get("generalCost", [])
        if general_costs:
            cost = general_costs[0].get("cost", {})
            si_val = cost.get("value", "")
            si_cur = cost.get("currency", "INR")
            st.metric("Sum Insured", f"{si_cur} {si_val:,.0f}" if isinstance(si_val, (int, float)) else f"{si_cur} {si_val}")
        else:
            st.info("No sum insured found.")

    # ── Apply edits to bundle (BEFORE raw JSON, so they are reflected) ──
    if org:
        org["name"] = org_name
    plan["status"] = plan_status
    plan["name"] = plan_name

    # ── Raw JSON Editor ──
    st.header("5. Raw JSON (Advanced)")
    with st.expander("Edit Raw Bundle JSON"):
        raw_json = st.text_area(
            "Bundle JSON",
            json.dumps(bundle, indent=2, ensure_ascii=False),
            height=400
        )
        try:
            bundle = json.loads(raw_json)
        except json.JSONDecodeError:
            st.error("Invalid JSON — fix before saving.")

    # ── Validation ──
    st.header("6. Validation")
    if st.button("Validate Bundle"):
        errors = validate(bundle)
        report = format_validation_report(errors)
        if errors:
            st.error(report)
        else:
            st.success(report)

    # ── Approve & Save ──
    st.header("7. Approve")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Approve & Save", type="primary"):
            errors = validate(bundle)
            if errors:
                st.warning(f"Bundle has {len(errors)} validation error(s). Saving anyway with warnings.")

            # Save to approved output directory
            approved_path = os.path.join(APPROVED_DIR, os.path.basename(selected_file))
            save_bundle(bundle, approved_path)

            # Remove from pending
            os.remove(selected_file)

            st.success(f"Saved to {approved_path} and removed from pending queue.")
            st.rerun()

    with col2:
        if st.button("Reject & Skip"):
            # Move to rejected folder
            rejected_dir = "output/rejected"
            os.makedirs(rejected_dir, exist_ok=True)
            rejected_path = os.path.join(rejected_dir, os.path.basename(selected_file))
            os.rename(selected_file, rejected_path)
            st.warning(f"Moved to {rejected_path}")
            st.rerun()


if __name__ == "__main__":
    main()