"""
Pydantic schemas for request/response models.

This module contains all data validation and serialization models used
by the GradeSync API endpoints. Each schema provides:
- Type validation and coercion
- Documentation for OpenAPI/Swagger
- Example values for API docs
- Data transformation logic
"""

from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field


# ============================================================================
# COURSE SCHEMAS
# ============================================================================

class CourseInfo(BaseModel):
    """Course information model."""
    id: str = Field(..., description="Course identifier", example="cs10_fa25")
    name: str = Field(..., description="Full course name", example="CS10: The Beauty and Joy of Computing")
    department: str = Field(..., description="Department code", example="COMPSCI")
    course_number: str = Field(..., description="Course number", example="10")
    semester: str = Field(..., description="Semester", example="Fall")
    year: int = Field(..., description="Year", example=2025)
    instructor: str = Field(..., description="Instructor name", example="Dan Garcia")
    enabled_sources: Dict[str, bool] = Field(
        ..., 
        description="Enabled integration sources",
        example={"gradescope": True, "prairielearn": True, "iclicker": True}
    )


class CoursesResponse(BaseModel):
    """Response model for listing courses."""
    courses: List[CourseInfo] = Field(..., description="List of courses")
    total: int = Field(..., description="Total number of courses", example=3)


# ============================================================================
# SYNC SCHEMAS
# ============================================================================

class SyncResultDetail(BaseModel):
    """Detailed result from a single sync operation."""
    source: str = Field(..., description="Source system name", example="gradescope")
    success: bool = Field(..., description="Whether sync succeeded", example=True)
    message: str = Field(..., description="Status message", example="Successfully synced 45 assignments")
    details: Dict[str, Any] = Field(
        default_factory=dict, 
        description="Additional details",
        example={"assignments_synced": 45, "students_updated": 320}
    )
    timestamp: str = Field(..., description="ISO 8601 timestamp", example="2026-01-14T10:30:00Z")


class SyncResponse(BaseModel):
    """Response model for sync operations."""
    course_id: str = Field(..., description="Course identifier", example="cs10_fa25")
    course_name: str = Field(..., description="Course name", example="CS10: The Beauty and Joy of Computing")
    timestamp: str = Field(..., description="Sync start timestamp", example="2026-01-14T10:30:00Z")
    results: List[SyncResultDetail] = Field(..., description="Sync results from each source")
    overall_success: bool = Field(..., description="Whether all syncs succeeded", example=True)


# ============================================================================
# GRADE SCHEMAS
# ============================================================================

class StudentScore(BaseModel):
    """Student score record."""
    legal_name: str = Field(..., description="Student name", example="John Doe")
    email: str = Field(..., description="Student email", example="john@berkeley.edu")
    scores: Dict[str, Optional[float]] = Field(
        ..., 
        description="Assignment scores",
        example={"Lab 1": 10.0, "Project 1": 95.5, "Quiz 1": 4.0}
    )


class SummaryResponse(BaseModel):
    """Response model for course summary."""
    assignments: List[str] = Field(..., description="List of assignment names", example=["Lab 1", "Project 1", "Quiz 1"])
    students: List[StudentScore] = Field(..., description="Student records with scores")
    categories: Dict[str, str] = Field(
        ..., 
        description="Assignment category mappings",
        example={"Lab 1": "Labs", "Project 1": "Projects", "Quiz 1": "Quizzes"}
    )
    max_points: Dict[str, float] = Field(
        ..., 
        description="Maximum points per assignment",
        example={"Lab 1": 10.0, "Project 1": 100.0, "Quiz 1": 4.0}
    )
