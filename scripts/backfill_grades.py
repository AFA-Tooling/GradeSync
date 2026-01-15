#!/usr/bin/env python3
"""
Backfill script: populates DB from saved CSVs or re-downloads missing assignments from Gradescope.

Usage:
    python scripts/backfill_grades.py --config gradescope/config/cs10_fa25.json [--dry-run]
    
Environment variables required:
    - DATABASE_URL
    - GRADESCOPE_EMAIL
    - GRADESCOPE_PASSWORD
    - SERVICE_ACCOUNT_CREDENTIALS
"""
import sys
import os
import argparse
import json
import logging
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from fullGSapi.api import client as GradescopeClient
from api.core.ingest import write_assignment_scores_to_db
from api.core.db import init_db
from api.config_loader import load_config, DEFAULT_SCOPES
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)


def get_assignment_id_to_names_from_gradescope(gs_client, course_id):
    """Parse Gradescope assignments page to get assignment metadata."""
    import re
    if not gs_client.logged_in:
        logger.error("Not logged in to Gradescope")
        return {}
    
    res = gs_client.session.get(f"https://www.gradescope.com/courses/{course_id}/assignments")
    if not res or not res.ok:
        logger.error(f"Failed to get assignments from Gradescope: {res}")
        return {}
    
    # Decode bytes to string properly
    course_info_response = res.content.decode('utf-8')
    pattern = r'\{"id":(\d+),"title":"([^"]+)"\}'
    matches = re.findall(pattern, course_info_response)
    
    assignment_to_names = {}
    for assignment_id, title in matches:
        assignment_to_names[str(assignment_id)] = title
    
    return assignment_to_names


def backfill_from_csv_directory(csv_dir, course_id, config, dry_run=False):
    """Backfill DB from all CSV files in a directory."""
    csv_path = Path(csv_dir)
    if not csv_path.exists():
        logger.warning(f"CSV directory does not exist: {csv_dir}")
        return 0
    
    csv_files = list(csv_path.glob("*.csv"))
    logger.info(f"Found {len(csv_files)} CSV files in {csv_dir}")
    
    count = 0
    for csv_file in csv_files:
        # Extract assignment_id from filename (format: assignment_<id>_<name>_<timestamp>.csv)
        filename = csv_file.stem
        parts = filename.split("_")
        if len(parts) < 3 or parts[0] != "assignment":
            logger.warning(f"Skipping file with unexpected name format: {csv_file.name}")
            continue
        
        assignment_id = parts[1]
        assignment_name = "_".join(parts[2:-1]) if len(parts) > 3 else parts[2]
        
        logger.info(f"Processing {csv_file.name} -> assignment {assignment_id} ({assignment_name})")
        
        if not dry_run:
            try:
                write_assignment_scores_to_db(
                    course_gradescope_id=str(course_id),
                    assignment_id=assignment_id,
                    assignment_name=assignment_name,
                    csv_filepath=str(csv_file),
                    spreadsheet_id=config.get("spreadsheet_id"),
                    course_name=config.get('course_name'),
                    department=config.get('department'),
                    course_number=config.get('course_number'),
                    semester=config.get('semester'),
                    year=config.get('year'),
                    instructor=config.get('staff', {}).get('instructor')
                )
                count += 1
            except Exception as e:
                logger.exception(f"Failed to ingest {csv_file.name}: {e}")
        else:
            count += 1
    
    return count


def download_and_ingest_assignment(gs_client, course_id, assignment_id, assignment_name, csv_dir, config, dry_run=False):
    """Download one assignment CSV from Gradescope and ingest into DB."""
    from datetime import datetime
    
    logger.info(f"Downloading assignment {assignment_id} ({assignment_name}) from Gradescope")
    
    if dry_run:
        logger.info(f"[DRY RUN] Would download and ingest {assignment_name}")
        return True
    
    try:
        # Download CSV
        csv_bytes = gs_client.download_scores(course_id, assignment_id)
        csv_content = csv_bytes.decode('utf-8') if isinstance(csv_bytes, bytes) else csv_bytes
        
        # Save to disk
        csv_path = Path(csv_dir)
        csv_path.mkdir(parents=True, exist_ok=True)
        
        ts = datetime.now().strftime('%Y%m%dT%H%M%S')
        safe_name = assignment_name.replace('/', '_').replace(' ', '_')
        filename = f'assignment_{assignment_id}_{safe_name}_{ts}.csv'
        filepath = csv_path / filename
        
        with open(filepath, 'w', encoding='utf-8') as fh:
            fh.write(csv_content)
        
        logger.info(f"Saved CSV to {filepath}")
        
        # Ingest into DB
        write_assignment_scores_to_db(
            course_gradescope_id=str(course_id),
            assignment_id=str(assignment_id),
            assignment_name=assignment_name,
            csv_filepath=str(filepath),
            spreadsheet_id=config.get("spreadsheet_id"),
            course_name=config.get('course_name'),
            department=config.get('department'),
            course_number=config.get('course_number'),
            semester=config.get('semester'),
            year=config.get('year'),
            instructor=config.get('staff', {}).get('instructor')
        )
        
        return True
    except Exception as e:
        logger.exception(f"Failed downloading/ingesting assignment {assignment_id}: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Backfill grades from CSVs or Gradescope")
    parser.add_argument("--config", required=True, help="Path to config JSON (e.g., gradescope/config/cs10_fa25.json)")
    parser.add_argument("--dry-run", action="store_true", help="Simulate without writing to DB")
    parser.add_argument("--re-download", action="store_true", help="Re-download all assignments from Gradescope even if CSVs exist")
    args = parser.parse_args()
    
    # Load config
    config_path = Path(args.config)
    if not config_path.exists():
        logger.error(f"Config file not found: {args.config}")
        sys.exit(1)
    
    config = load_config(str(config_path))
    
    course_id = config["gradescope_course_id"]
    logger.info(f"Backfilling course {course_id} using config {args.config}")
    
    # Initialize DB
    if not args.dry_run:
        logger.info("Initializing database schema...")
        init_db()
    
    # CSV directory
    csv_dir = Path(__file__).parent.parent / "gradescope" / "data" / "gradescope_csvs" / str(course_id)
    
    # If not re-downloading, try backfilling from existing CSVs first
    if not args.re_download:
        count = backfill_from_csv_directory(csv_dir, course_id, config, dry_run=args.dry_run)
        logger.info(f"Backfilled {count} assignments from existing CSVs")
    
    # Login to Gradescope
    logger.info("Logging into Gradescope...")
    gs_client = GradescopeClient.GradescopeClient()
    email = os.getenv("GRADESCOPE_EMAIL")
    password = os.getenv("GRADESCOPE_PASSWORD")
    
    if not email or not password:
        logger.error("GRADESCOPE_EMAIL and GRADESCOPE_PASSWORD must be set")
        sys.exit(1)
    
    gs_client.log_in(email, password)
    
    # Get all assignments from Gradescope
    logger.info("Fetching assignment list from Gradescope...")
    assignment_id_to_names = get_assignment_id_to_names_from_gradescope(gs_client, course_id)
    logger.info(f"Found {len(assignment_id_to_names)} assignments on Gradescope")
    
    # Determine which assignments need downloading
    existing_assignment_ids = set()
    if not args.re_download and csv_dir.exists():
        for csv_file in csv_dir.glob("assignment_*.csv"):
            parts = csv_file.stem.split("_")
            if len(parts) >= 2:
                existing_assignment_ids.add(parts[1])
    
    to_download = []
    for assignment_id, assignment_name in assignment_id_to_names.items():
        if args.re_download or assignment_id not in existing_assignment_ids:
            to_download.append((assignment_id, assignment_name))
    
    logger.info(f"Will download {len(to_download)} assignments")
    
    # Download and ingest missing assignments
    success_count = 0
    for assignment_id, assignment_name in to_download:
        if download_and_ingest_assignment(gs_client, course_id, assignment_id, assignment_name, csv_dir, config, dry_run=args.dry_run):
            success_count += 1
    
    logger.info(f"Successfully downloaded and ingested {success_count}/{len(to_download)} assignments")
    logger.info("Backfill complete!")


if __name__ == "__main__":
    main()
