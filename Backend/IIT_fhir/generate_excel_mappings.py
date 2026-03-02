#!/usr/bin/env python3
"""
CLI utility to generate Excel mapping files from FHIR JSON bundles.

Usage:
    python generate_excel_mappings.py                 — process all JSON in output/
    python generate_excel_mappings.py --file file.json  — process single file
    python generate_excel_mappings.py --dir output/pending  — process directory
"""

import argparse
import logging
import os
from pathlib import Path

from utils.logger import setup_logging
from utils.excel_generator import generate_excel_from_json, process_all_outputs

setup_logging()
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(
        description="Generate Excel mapping files from FHIR JSON bundles"
    )
    parser.add_argument(
        "--file", "-f",
        type=str,
        default=None,
        help="Process a single JSON file"
    )
    parser.add_argument(
        "--dir", "-d",
        type=str,
        default="output",
        help="Process all JSON files in a directory (default: output/)"
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        default=None,
        help="Output Excel file path (only with --file)"
    )
    
    args = parser.parse_args()
    
    if args.file:
        # Process single file
        if not os.path.exists(args.file):
            logger.error(f"File not found: {args.file}")
            return 1
        
        try:
            excel_path = generate_excel_from_json(args.file, args.output, logger_obj=logger)
            if excel_path:
                logger.info(f"✓ Generated: {excel_path}")
                return 0
            else:
                return 1
        except Exception as e:
            logger.error(f"✗ Failed to process {args.file}: {str(e)}")
            return 1
    else:
        # Process all files in directory
        if not os.path.exists(args.dir):
            logger.error(f"Directory not found: {args.dir}")
            return 1
        
        logger.info(f"Processing all JSON files in {args.dir}/")
        generated_files = process_all_outputs(args.dir, logger_obj=logger)
        
        if generated_files:
            logger.info(f"\n✓ Generated {len(generated_files)} Excel files:")
            for excel_file in generated_files:
                logger.info(f"  - {excel_file}")
            return 0
        else:
            logger.info("No JSON files found to process")
            return 0


if __name__ == "__main__":
    exit(main())
