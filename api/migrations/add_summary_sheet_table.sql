-- Migration: Add summary_sheets table
-- Date: 2026-01-14
-- Description: Creates a new table to store pre-computed summary sheet data

CREATE TABLE IF NOT EXISTS summary_sheets (
    id SERIAL PRIMARY KEY,
    course_id INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    assignment_id INTEGER NOT NULL REFERENCES assignments(id) ON DELETE CASCADE,
    score NUMERIC,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE,
    CONSTRAINT uq_summary_course_student_assignment UNIQUE (course_id, student_id, assignment_id)
);

-- Add indexes for faster queries
CREATE INDEX IF NOT EXISTS idx_summary_sheets_course_id ON summary_sheets(course_id);
CREATE INDEX IF NOT EXISTS idx_summary_sheets_student_id ON summary_sheets(student_id);
CREATE INDEX IF NOT EXISTS idx_summary_sheets_assignment_id ON summary_sheets(assignment_id);

-- Add comments for documentation
COMMENT ON TABLE summary_sheets IS 'Pre-computed summary sheet data for efficient retrieval';
COMMENT ON COLUMN summary_sheets.course_id IS 'Reference to the course';
COMMENT ON COLUMN summary_sheets.student_id IS 'Reference to the student';
COMMENT ON COLUMN summary_sheets.assignment_id IS 'Reference to the assignment';
COMMENT ON COLUMN summary_sheets.score IS 'Student score for this assignment';
COMMENT ON COLUMN summary_sheets.created_at IS 'Timestamp when record was created';
COMMENT ON COLUMN summary_sheets.updated_at IS 'Timestamp when record was last updated';
