#!/usr/bin/env python3
"""
Test script for summary sheet database functionality.

This script demonstrates how to:
1. Save summary sheet data to database
2. Retrieve summary sheet data from database
3. Compare with original submission data

Usage:
    python test_summary_sheet_db.py --course-id 1098053
"""
import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import argparse
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def test_save_and_retrieve(course_gradescope_id):
    """Test saving and retrieving summary sheet data."""
    from api.core.db import SessionLocal
    from api.core.models import Course, Assignment, Student, Submission
    from api.core.ingest import save_summary_sheet_to_db
    from api.summary_from_db import get_summary_sheet_from_db, get_summary_data_from_db
    
    logger.info(f"Testing summary sheet DB functionality for course: {course_gradescope_id}")
    
    # 1. Get original data
    session = SessionLocal()
    try:
        course = session.query(Course).filter(
            Course.gradescope_course_id == course_gradescope_id
        ).first()
        
        if not course:
            logger.error(f"Course {course_gradescope_id} not found")
            return False
        
        assignments = session.query(Assignment).filter(
            Assignment.course_id == course.id
        ).all()
        
        students = session.query(Student).all()
        
        submissions = session.query(Submission).join(Assignment).filter(
            Assignment.course_id == course.id
        ).all()
        
        submission_lookup = {
            (sub.assignment_id, sub.student_id): sub 
            for sub in submissions
        }
        
        course_data = {
            "course": course,
            "assignments": assignments,
            "students": students,
            "submissions": submission_lookup
        }
        
        logger.info(f"Original data: {len(students)} students, {len(assignments)} assignments")
        
    finally:
        session.close()
    
    # 2. Save to summary_sheets table
    logger.info("Saving summary sheet to database...")
    try:
        save_summary_sheet_to_db(course_gradescope_id, course_data)
        logger.info("✅ Save completed")
    except Exception as e:
        logger.error(f"❌ Save failed: {e}")
        return False
    
    # 3. Retrieve from summary_sheets table
    logger.info("Retrieving summary sheet from database...")
    try:
        summary_data = get_summary_sheet_from_db(course_gradescope_id)
        logger.info(f"✅ Retrieved: {len(summary_data['students'])} students, {len(summary_data['assignments'])} assignments")
    except Exception as e:
        logger.error(f"❌ Retrieve failed: {e}")
        return False
    
    # 4. Compare with original method
    logger.info("Comparing with original method...")
    try:
        original_data = get_summary_data_from_db(course_gradescope_id)
        
        # Compare counts
        if len(summary_data['students']) != len(original_data['students']):
            logger.error(f"❌ Student count mismatch: {len(summary_data['students'])} vs {len(original_data['students'])}")
            return False
        
        if len(summary_data['assignments']) != len(original_data['assignments']):
            logger.error(f"❌ Assignment count mismatch: {len(summary_data['assignments'])} vs {len(original_data['assignments'])}")
            return False
        
        logger.info("✅ Counts match")
        
        # Spot check a few scores
        if summary_data['students']:
            student = summary_data['students'][0]
            original_student = original_data['students'][0]
            logger.info(f"Sample student: {student['legal_name']}")
            logger.info(f"  New method scores: {list(student['scores'].values())[:3]}")
            logger.info(f"  Original method scores: {list(original_student['scores'].values())[:3]}")
        
    except Exception as e:
        logger.error(f"❌ Comparison failed: {e}")
        return False
    
    logger.info("✅ All tests passed!")
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Test summary sheet database functionality"
    )
    parser.add_argument(
        "--course-id",
        required=True,
        help="Gradescope course ID to test"
    )
    
    args = parser.parse_args()
    
    success = test_save_and_retrieve(args.course_id)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
