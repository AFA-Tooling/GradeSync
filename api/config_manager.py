"""
Unified Configuration Manager for GradeSync

Loads configuration from root config.json and provides
easy access to course-specific settings.
"""
import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Any
import logging

logger = logging.getLogger(__name__)

# Default configuration file location
DEFAULT_CONFIG_PATH = Path(__file__).parent.parent / "config.json"


class CourseConfig:
    """Configuration for a single course."""
    
    def __init__(self, course_data: Dict[str, Any]):
        self.data = course_data
        self.id = course_data.get("id")
        self.name = course_data.get("name")
        self.department = course_data.get("department")
        self.course_number = course_data.get("course_number")
        self.semester = course_data.get("semester")
        self.year = course_data.get("year")
        self.instructor = course_data.get("instructor")
        
        # Module configurations
        self.gradescope = course_data.get("gradescope", {})
        self.prairielearn = course_data.get("prairielearn", {})
        self.iclicker = course_data.get("iclicker", {})
        self.spreadsheet = course_data.get("spreadsheet", {})
        self.database = course_data.get("database", {})
        self.assignment_categories = course_data.get("assignment_categories", [])
    
    @property
    def gradescope_enabled(self) -> bool:
        return self.gradescope.get("enabled", False)
    
    @property
    def gradescope_course_id(self) -> Optional[str]:
        return self.gradescope.get("course_id")
    
    @property
    def prairielearn_enabled(self) -> bool:
        return self.prairielearn.get("enabled", False)
    
    @property
    def prairielearn_course_id(self) -> Optional[str]:
        return self.prairielearn.get("course_id")
    
    @property
    def iclicker_enabled(self) -> bool:
        return self.iclicker.get("enabled", False)
    
    @property
    def iclicker_course_names(self) -> List[str]:
        return self.iclicker.get("course_names", [])
    
    @property
    def spreadsheet_id(self) -> Optional[str]:
        return self.spreadsheet.get("id")
    
    @property
    def database_enabled(self) -> bool:
        return self.database.get("enabled", False)
    
    @property
    def use_db_as_primary(self) -> bool:
        return self.database.get("use_as_primary", False)
    
    @property
    def categories(self) -> List[Dict[str, Any]]:
        """Get assignment categories configuration."""
        return self.assignment_categories
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return self.data


class ConfigManager:
    """Manages application configuration."""
    
    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or DEFAULT_CONFIG_PATH
        self.config_data: Dict[str, Any] = {}
        self.courses: Dict[str, CourseConfig] = {}
        self.global_settings: Dict[str, Any] = {}
        self._load_config()
    
    def _load_config(self):
        """Load configuration from JSON file."""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {self.config_path}")
        
        try:
            with open(self.config_path, 'r') as f:
                self.config_data = json.load(f)
            
            # Load courses
            for course_data in self.config_data.get("courses", []):
                course_config = CourseConfig(course_data)
                self.courses[course_config.id] = course_config
            
            # Load global settings
            self.global_settings = self.config_data.get("global_settings", {})
            
            logger.info(f"Loaded configuration for {len(self.courses)} courses")
            
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in configuration file: {e}")
    
    def get_course(self, course_id: str) -> Optional[CourseConfig]:
        """Get configuration for a specific course."""
        return self.courses.get(course_id)
    
    def list_courses(self) -> List[str]:
        """List all available course IDs."""
        return list(self.courses.keys())
    
    def list_course_configs(self) -> List[CourseConfig]:
        """List all course configurations."""
        return list(self.courses.values())
    
    def get_global_setting(self, key: str, default: Any = None) -> Any:
        """Get a global setting value."""
        return self.global_settings.get(key, default)
    
    def reload(self):
        """Reload configuration from file."""
        self.courses.clear()
        self.global_settings.clear()
        self._load_config()


# Global configuration manager instance
_config_manager: Optional[ConfigManager] = None


def get_config_manager(config_path: Optional[Path] = None) -> ConfigManager:
    """Get or create the global configuration manager."""
    global _config_manager
    if _config_manager is None or config_path is not None:
        _config_manager = ConfigManager(config_path)
    return _config_manager


def get_course_config(course_id: str) -> Optional[CourseConfig]:
    """Convenience function to get a course configuration."""
    return get_config_manager().get_course(course_id)


def list_available_courses() -> List[str]:
    """Convenience function to list all available courses."""
    return get_config_manager().list_courses()


# Environment variables configuration
class EnvConfig:
    """Manages environment variables."""
    
    @staticmethod
    def get_gradescope_credentials() -> tuple[str, str]:
        """Get Gradescope email and password."""
        email = os.getenv("GRADESCOPE_EMAIL")
        password = os.getenv("GRADESCOPE_PASSWORD")
        if not email or not password:
            raise ValueError("GRADESCOPE_EMAIL and GRADESCOPE_PASSWORD must be set")
        return email, password
    
    @staticmethod
    def get_prairielearn_token() -> str:
        """Get PrairieLearn API token."""
        token = os.getenv("PL_API_TOKEN")
        if not token:
            raise ValueError("PL_API_TOKEN must be set")
        return token
    
    @staticmethod
    def get_iclicker_credentials() -> tuple[str, str]:
        """Get iClicker username and password."""
        username = os.getenv("ICLICKER_USERNAME")
        password = os.getenv("ICLICKER_PASSWORD")
        if not username or not password:
            raise ValueError("ICLICKER_USERNAME and ICLICKER_PASSWORD must be set")
        return username, password
    
    @staticmethod
    def get_service_account_credentials() -> str:
        """Get Google Service Account credentials JSON."""
        credentials = os.getenv("SERVICE_ACCOUNT_CREDENTIALS")
        if not credentials:
            raise ValueError("SERVICE_ACCOUNT_CREDENTIALS must be set")
        return credentials
    
    @staticmethod
    def get_database_url() -> str:
        """Get database connection URL."""
        url = os.getenv("DATABASE_URL")
        if not url:
            raise ValueError("DATABASE_URL must be set")
        return url
