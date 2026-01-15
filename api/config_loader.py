"""Simple configuration loader for multi-course setup."""
import json
from typing import Dict, Any, List

DEFAULT_SCOPES = ['https://www.googleapis.com/auth/spreadsheets']


def load_config(config_path: str, course_id: str = None) -> Dict[str, Any]:
    """
    Load course configuration.
    
    Args:
        config_path: Path to config file
        course_id: Optional course ID to select. If None, returns first course.
        
    Returns:
        Course configuration dict
    """
    with open(config_path, 'r') as f:
        config = json.load(f)
    
    courses = config.get('courses', [])
    if not courses:
        raise ValueError("No courses found in config")
    
    # Find course by ID or return first
    if course_id:
        for course in courses:
            if course.get('id') == course_id:
                return course
        raise ValueError(f"Course ID '{course_id}' not found")
    
    return courses[0]


def list_courses(config_path: str) -> List[Dict[str, Any]]:
    """
    List all courses in config file.
    
    Returns:
        List of course dicts with id, name, semester, year
    """
    with open(config_path, 'r') as f:
        config = json.load(f)
    
    return [
        {
            'id': c.get('id'),
            'name': c.get('course_name'),
            'semester': c.get('semester'),
            'year': c.get('year')
        }
        for c in config.get('courses', [])
    ]
