-- Migration: Add multi-tenant user and configuration system
-- Date: 2026-01-21
-- Description: Creates tables for users, roles, permissions, and configuration management

-- Users table
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    google_id VARCHAR(255) UNIQUE,
    profile_picture TEXT,
    name VARCHAR(255),
    role VARCHAR(50) DEFAULT 'instructor' CHECK (role IN ('superadmin', 'admin', 'instructor', 'ta', 'readonly')),
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_login_at TIMESTAMP WITH TIME ZONE
);

-- Course-User permissions (many-to-many relationship)
CREATE TABLE IF NOT EXISTS course_permissions (
    id SERIAL PRIMARY KEY,
    course_id INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    permission_level VARCHAR(50) DEFAULT 'viewer' CHECK (permission_level IN ('owner', 'editor', 'viewer')),
    granted_by INTEGER REFERENCES users(id),
    granted_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_course_user UNIQUE (course_id, user_id)
);

-- Course configuration (replaces config.json courses section)
CREATE TABLE IF NOT EXISTS course_configs (
    id SERIAL PRIMARY KEY,
    course_id INTEGER NOT NULL UNIQUE REFERENCES courses(id) ON DELETE CASCADE,
    
    -- Gradescope settings
    gradescope_enabled BOOLEAN DEFAULT false,
    gradescope_course_id VARCHAR(255),
    gradescope_sync_interval_hours INTEGER DEFAULT 24,
    
    -- PrairieLearn settings
    prairielearn_enabled BOOLEAN DEFAULT false,
    prairielearn_course_id VARCHAR(255),
    
    -- iClicker settings
    iclicker_enabled BOOLEAN DEFAULT false,
    iclicker_course_names TEXT[], -- Array of course names
    
    -- Database settings
    database_enabled BOOLEAN DEFAULT true,
    use_as_primary BOOLEAN DEFAULT true,
    
    -- Spreadsheet settings
    spreadsheet_id VARCHAR(255),
    spreadsheet_scopes TEXT[] DEFAULT ARRAY['https://www.googleapis.com/auth/spreadsheets'],
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Assignment categories configuration
CREATE TABLE IF NOT EXISTS assignment_categories (
    id SERIAL PRIMARY KEY,
    course_id INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    patterns TEXT[], -- Array of pattern strings
    display_order INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_course_category UNIQUE (course_id, name)
);

-- Global system configuration (replaces global_settings in config.json)
CREATE TABLE IF NOT EXISTS system_config (
    id SERIAL PRIMARY KEY,
    key VARCHAR(255) UNIQUE NOT NULL,
    value TEXT,
    value_type VARCHAR(50) DEFAULT 'string' CHECK (value_type IN ('string', 'integer', 'boolean', 'json')),
    description TEXT,
    is_public BOOLEAN DEFAULT false, -- Whether non-admin users can read this
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- GradeView specific configuration
CREATE TABLE IF NOT EXISTS gradeview_config (
    id SERIAL PRIMARY KEY,
    key VARCHAR(255) UNIQUE NOT NULL,
    value TEXT,
    value_type VARCHAR(50) DEFAULT 'string' CHECK (value_type IN ('string', 'integer', 'boolean', 'json')),
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Configuration change audit log
CREATE TABLE IF NOT EXISTS config_audit_log (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    table_name VARCHAR(100) NOT NULL,
    record_id INTEGER,
    action VARCHAR(50) NOT NULL CHECK (action IN ('INSERT', 'UPDATE', 'DELETE')),
    old_values JSONB,
    new_values JSONB,
    ip_address INET,
    user_agent TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);
CREATE INDEX IF NOT EXISTS idx_course_permissions_course_id ON course_permissions(course_id);
CREATE INDEX IF NOT EXISTS idx_course_permissions_user_id ON course_permissions(user_id);
CREATE INDEX IF NOT EXISTS idx_course_configs_course_id ON course_configs(course_id);
CREATE INDEX IF NOT EXISTS idx_assignment_categories_course_id ON assignment_categories(course_id);
CREATE INDEX IF NOT EXISTS idx_config_audit_log_user_id ON config_audit_log(user_id);
CREATE INDEX IF NOT EXISTS idx_config_audit_log_created_at ON config_audit_log(created_at);

-- Add foreign key to courses table for owner
ALTER TABLE courses ADD COLUMN IF NOT EXISTS owner_id INTEGER REFERENCES users(id);
ALTER TABLE courses ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT true;
ALTER TABLE courses ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP;

-- Insert default system configurations
INSERT INTO system_config (key, value, value_type, description, is_public) VALUES
    ('csv_output_dir', 'data/exports', 'string', 'Directory for exported CSV files', false),
    ('log_level', 'INFO', 'string', 'Logging verbosity (DEBUG, INFO, WARNING, ERROR)', false),
    ('retry_attempts', '3', 'integer', 'Maximum retry attempts for failed operations', false),
    ('retry_delay_seconds', '5', 'integer', 'Delay between retry attempts in seconds', false),
    ('default_scopes', '["https://www.googleapis.com/auth/spreadsheets"]', 'json', 'Default Google API scopes', false)
ON CONFLICT (key) DO NOTHING;

-- Insert default GradeView configurations
INSERT INTO gradeview_config (key, value, value_type, description) VALUES
    ('redis_host', 'redis', 'string', 'Redis server hostname'),
    ('redis_port', '6379', 'integer', 'Redis server port'),
    ('redis_username', 'default', 'string', 'Redis username'),
    ('spreadsheet_id', '1_gsKSmSxD-tyTSsrK5iRZW4X7eGuJMHlhrEE5krjW94', 'string', 'Default spreadsheet ID'),
    ('google_oauth_client_id', '960156693240-hje09pstet1al4g4tr08271kkcjfqnn2.apps.googleusercontent.com', 'string', 'Google OAuth Client ID'),
    ('grade_page_name', 'HAID', 'string', 'Grade page worksheet name'),
    ('grade_page_meta_row', '2', 'integer', 'Assignment metadata row number'),
    ('grade_page_start_row', '4', 'integer', 'First row of student data'),
    ('grade_page_start_col', 'C', 'string', 'First column of student data'),
    ('bin_page_name', 'Constants', 'string', 'Bin page worksheet name'),
    ('bin_page_start_cell', 'A51', 'string', 'Bin page start cell'),
    ('bin_page_end_cell', 'B61', 'string', 'Bin page end cell')
ON CONFLICT (key) DO NOTHING;

-- Comments for documentation
COMMENT ON TABLE users IS 'System users with role-based access control';
COMMENT ON TABLE course_permissions IS 'Per-course user permissions (owner/editor/viewer)';
COMMENT ON TABLE course_configs IS 'Per-course integration and sync settings';
COMMENT ON TABLE assignment_categories IS 'Assignment categorization rules per course';
COMMENT ON TABLE system_config IS 'Global system configuration key-value store';
COMMENT ON TABLE gradeview_config IS 'GradeView-specific configuration key-value store';
COMMENT ON TABLE config_audit_log IS 'Audit trail for all configuration changes';

COMMENT ON COLUMN users.role IS 'Global role: superadmin (full access), admin (multi-course), instructor (own courses), ta, readonly';
COMMENT ON COLUMN course_permissions.permission_level IS 'Course-level permission: owner (full control), editor (modify), viewer (read-only)';

