#!/usr/bin/env python3
"""Update assignment categories based on assignment names."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from api.core.db import SessionLocal, init_db
from api.core.models import Assignment, Course
from api.core.ingest import _categorize_assignment
from api.config_manager import get_config_manager

def main(course_id: str = None):
    """
    Update assignment categories.
    
    Args:
        course_id: Optional course ID to update. If None, updates all courses.
    """
    init_db()
    config_manager = get_config_manager()
    session = SessionLocal()
    
    try:
        # Get assignments to update
        query = session.query(Assignment)
        if course_id:
            # Get course from database
            course = session.query(Course).filter(Course.gradescope_course_id == course_id).first()
            if not course:
                print(f"❌ Course {course_id} not found in database")
                return
            query = query.filter(Assignment.course_id == course.id)
            
            # Get course categories from config
            course_config = config_manager.get_course(course_id)
            if not course_config:
                print(f"⚠️  Course {course_id} not found in config, using legacy categories")
                categories = None
            else:
                categories = course_config.categories
                print(f"📋 Using categories from config for course: {course_config.name}")
        else:
            categories = None
            print("📋 Updating all assignments with legacy categories")
        
        assignments = query.all()
        updated = 0
        
        for assignment in assignments:
            category = _categorize_assignment(assignment.title, categories)
            if assignment.category != category:
                print(f"Updating {assignment.title}: {assignment.category} -> {category}")
                assignment.category = category
                updated += 1
        
        session.commit()
        print(f"\n✅ Updated {updated} assignments out of {len(assignments)} total")
        
    finally:
        session.close()

if __name__ == '__main__':
    # Allow passing course_id as argument
    course_arg = sys.argv[1] if len(sys.argv) > 1 else None
    main(course_arg)
