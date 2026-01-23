"""
Optimized ingestion module with batch operations and incremental sync support.
"""
import io
import csv
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from sqlalchemy import and_
from sqlalchemy.dialects.postgresql import insert
from .db import SessionLocal
from .models import Course, Assignment, Student, Submission

logger = logging.getLogger(__name__)

def _ts():
    """Return current timestamp for debug logs."""
    return datetime.now().strftime('%H:%M:%S.%f')[:-3]


def should_sync_assignment(
    session, 
    course_id: int, 
    assignment_id: str, 
    force_sync: bool = False,
    sync_if_older_than_hours: int = 24
) -> bool:
    """
    Check if an assignment needs to be synced based on last sync time.
    
    Args:
        session: Database session
        course_id: Internal course ID
        assignment_id: Gradescope assignment ID
        force_sync: If True, always sync regardless of last sync time
        sync_if_older_than_hours: Sync if last sync was more than N hours ago
        
    Returns:
        True if assignment should be synced, False otherwise
    """
    if force_sync:
        return True
    
    assignment = session.query(Assignment).filter(
        Assignment.assignment_id == str(assignment_id),
        Assignment.course_id == course_id
    ).first()
    
    if not assignment or not assignment.last_synced_at:
        # Never synced before, must sync
        return True
    
    # Check if last sync was too long ago
    now = datetime.now(timezone.utc)
    hours_since_sync = (now - assignment.last_synced_at).total_seconds() / 3600
    
    return hours_since_sync >= sync_if_older_than_hours


def batch_upsert_submissions(
    session,
    assignment_db_id: int,
    submissions_data: List[Dict[str, Any]]
) -> int:
    """
    Batch upsert submissions using PostgreSQL's ON CONFLICT.
    Much faster than individual inserts.
    
    Args:
        session: Database session
        assignment_db_id: Database ID of the assignment
        submissions_data: List of submission dicts
        
    Returns:
        Number of submissions upserted
    """
    if not submissions_data:
        return 0
    
    # Prepare data for bulk upsert
    for sub in submissions_data:
        sub['assignment_id'] = assignment_db_id
    
    # Use PostgreSQL INSERT ... ON CONFLICT DO UPDATE
    stmt = insert(Submission).values(submissions_data)
    stmt = stmt.on_conflict_do_update(
        constraint='uq_assignment_student',
        set_={
            'total_score': stmt.excluded.total_score,
            'max_points': stmt.excluded.max_points,
            'status': stmt.excluded.status,
            'submission_id': stmt.excluded.submission_id,
            'submission_time': stmt.excluded.submission_time,
            'lateness': stmt.excluded.lateness,
            'view_count': stmt.excluded.view_count,
            'submission_count': stmt.excluded.submission_count,
            'scores_by_question': stmt.excluded.scores_by_question,
        }
    )
    
    session.execute(stmt)
    session.commit()
    
    logger.info(f"Batch upserted {len(submissions_data)} submissions")
    return len(submissions_data)


def batch_upsert_students(
    session,
    students_data: List[Dict[str, str]]
) -> Dict[str, int]:
    """
    Batch upsert students and return mapping of email -> student_id.
    
    Args:
        session: Database session
        students_data: List of student dicts with 'sid' and 'email'
        
    Returns:
        Dict mapping email to student_id
    """
    if not students_data:
        return {}
    
    # Use PostgreSQL INSERT ... ON CONFLICT DO NOTHING
    stmt = insert(Student).values(students_data)
    stmt = stmt.on_conflict_do_nothing(constraint='uq_student_sid_email')
    
    session.execute(stmt)
    session.commit()
    
    # Query to get all student IDs
    emails = [s['email'] for s in students_data]
    students = session.query(Student).filter(Student.email.in_(emails)).all()
    
    email_to_id = {s.email: s.id for s in students}
    logger.info(f"Batch processed {len(students_data)} students")
    
    return email_to_id


def write_assignment_scores_optimized(
    course_gradescope_id: str,
    assignment_id: str,
    assignment_name: str,
    csv_content: str,
    course_config: Optional[Dict[str, Any]] = None,
    force_sync: bool = False
) -> Dict[str, Any]:
    """
    Optimized version of write_assignment_scores_to_db with batch operations.
    
    Args:
        course_gradescope_id: Gradescope course ID
        assignment_id: Gradescope assignment ID
        assignment_name: Assignment title
        csv_content: CSV content as string
        course_config: Optional course configuration
        force_sync: Force sync even if recently synced
        
    Returns:
        Dict with sync results
    """
    import time as _time
    _fn_start = _time.time()
    print(f"[{_ts()}] DB: Starting write_assignment_scores_optimized for {assignment_name}")
    
    session = SessionLocal()
    print(f"[{_ts()}] DB: Session created ({_time.time() - _fn_start:.2f}s)")
    
    try:
        # Get or create course
        _step_start = _time.time()
        course = session.query(Course).filter(
            Course.gradescope_course_id == course_gradescope_id
        ).first()
        print(f"[{_ts()}] DB: Course query ({_time.time() - _step_start:.2f}s)")
        
        if not course:
            logger.error(f"Course {course_gradescope_id} not found in database")
            session.close()
            return {"success": False, "error": "Course not found"}
        
        # Check if we should sync this assignment
        _step_start = _time.time()
        if not should_sync_assignment(session, course.id, assignment_id, force_sync):
            print(f"[{_ts()}] DB: should_sync=False ({_time.time() - _step_start:.2f}s)")
            logger.info(f"Skipping {assignment_name} - recently synced")
            session.close()
            print(f"[{_ts()}] DB: Session closed for skipped assignment")
            return {
                "success": True,
                "skipped": True,
                "reason": "Recently synced"
            }
        print(f"[{_ts()}] DB: should_sync=True ({_time.time() - _step_start:.2f}s)")
        
        # Get or create assignment
        _step_start = _time.time()
        assignment = session.query(Assignment).filter(
            Assignment.assignment_id == str(assignment_id),
            Assignment.course_id == course.id
        ).first()
        print(f"[{_ts()}] DB: Assignment query ({_time.time() - _step_start:.2f}s)")
        
        if not assignment:
            assignment = Assignment(
                assignment_id=str(assignment_id),
                course_id=course.id,
                title=assignment_name
            )
            session.add(assignment)
            session.flush()
        
        # Parse CSV
        reader = csv.DictReader(io.StringIO(csv_content))
        
        # Collect data for batch operations
        students_data = []
        submissions_data = []
        seen_emails = set()
        
        for row in reader:
            email = row.get('Email', '').strip()
            sid = row.get('SID', '').strip()
            
            if not email or email in seen_emails:
                continue
            
            seen_emails.add(email)
            
            # Student data
            students_data.append({
                'email': email,
                'sid': sid,
                'legal_name': row.get(reader.fieldnames[0], '') if reader.fieldnames else ''
            })
            
            # Submission data (will add student_id later)
            submission = {
                'total_score': float(row.get('Total Score', 0) or 0),
                'max_points': float(row.get('Max Points', 0) or 0),
                'status': row.get('Status', ''),
                'submission_id': row.get('Submission ID', ''),
                'lateness': row.get('Lateness (H:M:S)', ''),
                'view_count': int(row.get('View Count', 0) or 0),
                'submission_count': int(row.get('Submission Count', 0) or 0),
            }
            
            # Parse submission time - only add if valid to avoid SQLAlchemy bound parameter issues
            sub_time_str = row.get('Submission Time', '')
            if sub_time_str:
                try:
                    parsed_time = datetime.fromisoformat(
                        sub_time_str.replace('Z', '+00:00')
                    )
                    if parsed_time:
                        submission['submission_time'] = parsed_time
                except:
                    pass  # Skip invalid timestamps, leave field unset
            
            submissions_data.append({**submission, 'email': email})
        
        # Batch upsert students
        email_to_id = batch_upsert_students(session, students_data)
        
        # Add student_id to submissions and remove email
        final_submissions = []
        for sub in submissions_data:
            email = sub.pop('email')
            student_id = email_to_id.get(email)
            if student_id:
                sub['student_id'] = student_id
                final_submissions.append(sub)
        
        # Batch upsert submissions
        num_submissions = batch_upsert_submissions(
            session,
            assignment.id,
            final_submissions
        )
        
        # Update assignment sync timestamp
        assignment.last_synced_at = datetime.now(timezone.utc)
        session.commit()
        
        logger.info(f"Successfully synced {assignment_name}: {num_submissions} submissions")
        
        return {
            "success": True,
            "assignment_name": assignment_name,
            "students_processed": len(students_data),
            "submissions_processed": num_submissions
        }
        
    except Exception as e:
        session.rollback()
        logger.error(f"Error syncing {assignment_name}: {e}")
        return {
            "success": False,
            "error": str(e)
        }
    
    finally:
        session.close()
