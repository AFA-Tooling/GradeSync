from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Numeric, JSON, Text, UniqueConstraint, Boolean, ARRAY
from sqlalchemy.dialects.postgresql import INET, JSONB
from sqlalchemy.sql import func

Base = declarative_base()


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    google_id = Column(String(255), unique=True)
    profile_picture = Column(Text)
    name = Column(String(255))
    role = Column(String(50), default='instructor')  # superadmin, admin, instructor, ta, readonly
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    last_login_at = Column(DateTime(timezone=True))
    
    # Relationships
    courses_owned = relationship("Course", back_populates="owner", foreign_keys="Course.owner_id")
    course_permissions = relationship("CoursePermission", back_populates="user", foreign_keys="CoursePermission.user_id")


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
    owner_id = Column(Integer, ForeignKey("users.id"))
    is_active = Column(Boolean, default=True)
    last_synced_at = Column(DateTime(timezone=True), index=True)  # Track last full sync
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    owner = relationship("User", back_populates="courses_owned", foreign_keys=[owner_id])
    config = relationship("CourseConfig", back_populates="course", uselist=False)
    permissions = relationship("CoursePermission", back_populates="course")
    categories = relationship("AssignmentCategory", back_populates="course")


class CoursePermission(Base):
    __tablename__ = "course_permissions"
    id = Column(Integer, primary_key=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    permission_level = Column(String(50), default='viewer')  # owner, editor, viewer
    granted_by = Column(Integer, ForeignKey("users.id"))
    granted_at = Column(DateTime(timezone=True), server_default=func.now())
    
    __table_args__ = (
        UniqueConstraint('course_id', 'user_id', name='uq_course_user'),
    )
    
    # Relationships
    course = relationship("Course", back_populates="permissions")
    user = relationship("User", back_populates="course_permissions", foreign_keys=[user_id])
    granter = relationship("User", foreign_keys=[granted_by])


class CourseConfig(Base):
    __tablename__ = "course_configs"
    id = Column(Integer, primary_key=True)
    course_id = Column(Integer, ForeignKey("courses.id"), unique=True, nullable=False)
    
    # Gradescope
    gradescope_enabled = Column(Boolean, default=False)
    gradescope_course_id = Column(String(255))
    gradescope_sync_interval_hours = Column(Integer, default=24)
    
    # PrairieLearn
    prairielearn_enabled = Column(Boolean, default=False)
    prairielearn_course_id = Column(String(255))
    
    # iClicker
    iclicker_enabled = Column(Boolean, default=False)
    iclicker_course_names = Column(ARRAY(Text))
    
    # Database
    database_enabled = Column(Boolean, default=True)
    use_as_primary = Column(Boolean, default=True)
    
    # Spreadsheet
    spreadsheet_id = Column(String(255))
    spreadsheet_scopes = Column(ARRAY(Text), default=['https://www.googleapis.com/auth/spreadsheets'])
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    course = relationship("Course", back_populates="config")


class AssignmentCategory(Base):
    __tablename__ = "assignment_categories"
    id = Column(Integer, primary_key=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    patterns = Column(ARRAY(Text))
    display_order = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    __table_args__ = (
        UniqueConstraint('course_id', 'name', name='uq_course_category'),
    )
    
    # Relationships
    course = relationship("Course", back_populates="categories")


class SystemConfig(Base):
    __tablename__ = "system_config"
    id = Column(Integer, primary_key=True)
    key = Column(String(255), unique=True, nullable=False)
    value = Column(Text)
    value_type = Column(String(50), default='string')  # string, integer, boolean, json
    description = Column(Text)
    is_public = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class GradeViewConfig(Base):
    __tablename__ = "gradeview_config"
    id = Column(Integer, primary_key=True)
    key = Column(String(255), unique=True, nullable=False)
    value = Column(Text)
    value_type = Column(String(50), default='string')
    description = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ConfigAuditLog(Base):
    __tablename__ = "config_audit_log"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    table_name = Column(String(100), nullable=False)
    record_id = Column(Integer)
    action = Column(String(50), nullable=False)  # INSERT, UPDATE, DELETE
    old_values = Column(JSONB)
    new_values = Column(JSONB)
    ip_address = Column(INET)
    user_agent = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    
    # Relationships
    user = relationship("User")


class Assignment(Base):
    __tablename__ = "assignments"
    id = Column(Integer, primary_key=True)
    assignment_id = Column(String, index=True, nullable=False)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=True, index=True)
    title = Column(String)
    category = Column(String)
    max_points = Column(Numeric)
    assignment_metadata = Column(JSON)
    last_synced_at = Column(DateTime(timezone=True), index=True)  # Track last sync time
    gradescope_updated_at = Column(DateTime(timezone=True))  # From Gradescope API
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


class SummarySheet(Base):
    __tablename__ = "summary_sheets"
    id = Column(Integer, primary_key=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False, index=True)
    assignment_id = Column(Integer, ForeignKey("assignments.id"), nullable=False, index=True)
    score = Column(Numeric)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    __table_args__ = (
        UniqueConstraint('course_id', 'student_id', 'assignment_id', name='uq_summary_course_student_assignment'),
    )
