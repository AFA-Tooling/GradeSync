"""
Unit tests for DB ingestion and summary generation.

Run with:
    pytest api/test_db_ingest.py -v
"""
import os
import tempfile
import pytest
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from api.models import Base, Course, Assignment, Student, Submission, RawCSV
from api.ingest import write_assignment_scores_to_db
from api.summary_from_db import get_summary_data_from_db, categorize_assignment_for_summary, get_max_points_from_db


@pytest.fixture(scope="function")
def test_db():
    """Create a temporary in-memory SQLite database for testing."""
    # Use in-memory SQLite for tests
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    
    # Patch the global DB to use test DB
    import api.db
    import api.ingest
    import api.summary_from_db
    
    original_session = api.db.SessionLocal
    api.db.SessionLocal = SessionLocal
    api.ingest.SessionLocal = SessionLocal
    api.summary_from_db.SessionLocal = SessionLocal
    
    yield session
    
    # Restore original
    api.db.SessionLocal = original_session
    api.ingest.SessionLocal = original_session
    api.summary_from_db.SessionLocal = original_session
    
    session.close()


@pytest.fixture
def sample_csv():
    """Create a sample CSV file for testing."""
    csv_content = """Name,SID,Email,Total Score,Max Points,Status,Submission ID,Submission Time,Lateness (H:M:S),View Count,Submission Count,Q1: Problem 1,Q2: Problem 2
Alice Smith,12345678,alice@example.com,95.0,100.0,Submitted,sub_123,2026-01-01 10:00:00,00:00:00,2,1,45.0,50.0
Bob Jones,87654321,bob@example.com,80.0,100.0,Submitted,sub_124,2026-01-01 11:00:00,01:00:00,1,1,40.0,40.0
Charlie Brown,11223344,charlie@example.com,,100.0,Missing,,,,,0,0.0,0.0
"""
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, encoding='utf-8') as f:
        f.write(csv_content)
        temp_path = f.name
    
    yield temp_path
    
    # Cleanup
    os.unlink(temp_path)


def test_csv_ingestion(test_db, sample_csv):
    """Test that CSV is correctly parsed and ingested into DB."""
    course_id = "TEST_COURSE_123"
    assignment_id = "TEST_ASSIGN_456"
    assignment_name = "Lab 1: Introduction"
    
    # Ingest the CSV
    write_assignment_scores_to_db(
        course_gradescope_id=course_id,
        assignment_id=assignment_id,
        assignment_name=assignment_name,
        csv_filepath=sample_csv
    )
    
    # Verify course was created
    course = test_db.query(Course).filter(Course.gradescope_course_id == course_id).first()
    assert course is not None
    
    # Verify assignment was created
    assignment = test_db.query(Assignment).filter(Assignment.assignment_id == assignment_id).first()
    assert assignment is not None
    assert assignment.title == assignment_name
    
    # Verify students were created
    students = test_db.query(Student).all()
    assert len(students) == 3
    
    alice = test_db.query(Student).filter(Student.email == "alice@example.com").first()
    assert alice is not None
    assert alice.sid == "12345678"
    assert alice.legal_name == "Alice Smith"
    
    # Verify submissions were created
    submissions = test_db.query(Submission).all()
    assert len(submissions) == 3
    
    alice_sub = test_db.query(Submission).filter(
        Submission.assignment_id == assignment.id,
        Submission.student_id == alice.id
    ).first()
    assert alice_sub is not None
    assert float(alice_sub.total_score) == 95.0
    assert alice_sub.status == "Submitted"
    assert alice_sub.scores_by_question is not None
    assert "Q1: Problem 1" in alice_sub.scores_by_question
    assert alice_sub.scores_by_question["Q1: Problem 1"] == "45.0"
    
    # Verify raw CSV metadata was stored
    raw_csv = test_db.query(RawCSV).first()
    assert raw_csv is not None
    assert raw_csv.assignment_id == assignment.id


def test_summary_data_generation(test_db, sample_csv):
    """Test that summary data is correctly generated from DB."""
    course_id = "TEST_COURSE_123"
    
    # Ingest multiple assignments
    write_assignment_scores_to_db(
        course_gradescope_id=course_id,
        assignment_id="1",
        assignment_name="Lab 1: Intro",
        csv_filepath=sample_csv
    )
    
    write_assignment_scores_to_db(
        course_gradescope_id=course_id,
        assignment_id="2",
        assignment_name="Discussion 2: Recursion",
        csv_filepath=sample_csv
    )
    
    # Get summary data
    summary = get_summary_data_from_db(course_id)
    
    assert len(summary["assignments"]) == 2
    assert "Lab 1: Intro" in summary["assignments"]
    assert "Discussion 2: Recursion" in summary["assignments"]
    
    assert len(summary["students"]) == 3
    
    # Check Alice's data
    alice = next(s for s in summary["students"] if s["email"] == "alice@example.com")
    assert alice["legal_name"] == "Alice Smith"
    assert alice["scores"]["Lab 1: Intro"] == 95.0
    assert alice["scores"]["Discussion 2: Recursion"] == 95.0


def test_categorization():
    """Test assignment categorization logic."""
    assert categorize_assignment_for_summary("Lab 1: Intro") == "Labs (before dropping lowest two)"
    assert categorize_assignment_for_summary("Discussion 5: Trees") == "Discussions"
    assert categorize_assignment_for_summary("Project 3: Ants") == "Projects"
    assert categorize_assignment_for_summary("Lecture Quiz 7") == "Quest (pre-clobber)"
    assert categorize_assignment_for_summary("Midterm 1") == "Midterm (pre-clobber)"
    assert categorize_assignment_for_summary("Postterm 2: Snap!") == "Postterm"
    assert categorize_assignment_for_summary("Random Assignment") == "Other"


def test_max_points_retrieval(test_db, sample_csv):
    """Test max points retrieval from DB."""
    course_id = "TEST_COURSE_123"
    assignment_name = "Lab 1: Intro"
    
    # Ingest CSV
    write_assignment_scores_to_db(
        course_gradescope_id=course_id,
        assignment_id="1",
        assignment_name=assignment_name,
        csv_filepath=sample_csv
    )
    
    # Get max points
    max_points = get_max_points_from_db(course_id, assignment_name)
    assert max_points == 100.0


def test_upsert_behavior(test_db, sample_csv):
    """Test that re-ingesting the same CSV updates existing records."""
    course_id = "TEST_COURSE_123"
    assignment_id = "1"
    assignment_name = "Lab 1"
    
    # Ingest once
    write_assignment_scores_to_db(
        course_gradescope_id=course_id,
        assignment_id=assignment_id,
        assignment_name=assignment_name,
        csv_filepath=sample_csv
    )
    
    initial_submission_count = test_db.query(Submission).count()
    initial_student_count = test_db.query(Student).count()
    
    # Ingest again
    write_assignment_scores_to_db(
        course_gradescope_id=course_id,
        assignment_id=assignment_id,
        assignment_name=assignment_name,
        csv_filepath=sample_csv
    )
    
    # Verify counts didn't increase (upsert behavior)
    assert test_db.query(Submission).count() == initial_submission_count
    assert test_db.query(Student).count() == initial_student_count


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
