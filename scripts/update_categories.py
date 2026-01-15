#!/usr/bin/env python3
"""Update assignment categories based on assignment names."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from api.db import SessionLocal, init_db
from api.models import Assignment
from api.ingest import _categorize_assignment

def main():
    init_db()
    session = SessionLocal()
    try:
        assignments = session.query(Assignment).all()
        updated = 0
        for assignment in assignments:
            category = _categorize_assignment(assignment.title)
            if assignment.category != category:
                print(f"Updating {assignment.title}: {assignment.category} -> {category}")
                assignment.category = category
                updated += 1
        
        session.commit()
        print(f"\nUpdated {updated} assignments out of {len(assignments)} total")
    finally:
        session.close()

if __name__ == '__main__':
    main()
