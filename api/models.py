from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Numeric, JSON, Text, UniqueConstraint
from sqlalchemy.sql import func

Base = declarative_base()


class Course(Base):
    __tablename__ = "courses"
    id = Column(Integer, primary_key=True)
    gradescope_course_id = Column(String, unique=True, index=True, nullable=False)
    spreadsheet_id = Column(String)
    name = Column(String)
    department = Column(String)
    course_number = Column(String)
    semester = Column(String)
    year = Column(String)
    instructor = Column(String)
    number_of_students = Column(Integer)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Assignment(Base):
    __tablename__ = "assignments"
    id = Column(Integer, primary_key=True)
    assignment_id = Column(String, index=True, nullable=False)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=True, index=True)
    title = Column(String)
    category = Column(String)
    max_points = Column(Numeric)
    assignment_metadata = Column(JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class Student(Base):
    __tablename__ = "students"
    id = Column(Integer, primary_key=True)
    sid = Column(String, index=True)
    email = Column(String, index=True)
    legal_name = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (
        UniqueConstraint('sid', 'email', name='uq_student_sid_email'),
    )


class Submission(Base):
    __tablename__ = "submissions"
    id = Column(Integer, primary_key=True)
    assignment_id = Column(Integer, ForeignKey("assignments.id"), nullable=False, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False, index=True)
    total_score = Column(Numeric)
    max_points = Column(Numeric)
    status = Column(String)
    submission_id = Column(String)
    submission_time = Column(DateTime(timezone=True))
    lateness = Column(String)
    view_count = Column(Integer)
    submission_count = Column(Integer)
    scores_by_question = Column(JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (
        UniqueConstraint('assignment_id', 'student_id', name='uq_assignment_student'),
    )


class SheetSync(Base):
    __tablename__ = "sheet_syncs"
    id = Column(Integer, primary_key=True)
    course_id = Column(Integer, ForeignKey("courses.id"))
    last_summary_sync_at = Column(DateTime(timezone=True))
    summary_spreadsheet_id = Column(String)
    notes = Column(JSON)
