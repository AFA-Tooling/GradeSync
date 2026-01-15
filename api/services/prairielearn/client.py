"""
PrairieLearn API Client

Modern client for PrairieLearn API with retry logic and error handling.
"""
import requests
import pandas as pd
import time
import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class CourseInfo:
    """PrairieLearn course information."""
    course_id: str
    short_name: str
    title: str
    display_timezone: str


@dataclass
class AssessmentInfo:
    """PrairieLearn assessment information."""
    assessment_id: str
    title: str
    number: str
    type: str  # Homework, Exam, etc.
    points: float


class PrairieLearnClient:
    """
    Client for PrairieLearn API v1.
    
    Features:
    - Automatic retry on 502 errors
    - Type-safe data models
    - Gradebook access
    - Assessment details
    
    API Documentation:
    https://prairielearn.readthedocs.io/en/latest/api/
    """
    
    DEFAULT_SERVER = "https://us.prairielearn.com/pl/api/v1"
    
    def __init__(
        self,
        api_token: str,
        server: Optional[str] = None
    ):
        """
        Initialize PrairieLearn client.
        
        Args:
            api_token: PrairieLearn private API token
            server: API server URL (default: us.prairielearn.com)
        """
        self.api_token = api_token
        self.server = server or self.DEFAULT_SERVER
        self.session = requests.Session()
        self.session.headers.update({
            "Private-Token": api_token,
            "Accept": "application/json"
        })
    
    def _call_api(
        self,
        endpoint: str,
        method: str = "GET",
        retry_502_max: int = 30,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Call PrairieLearn API with automatic retry on 502 errors.
        
        Args:
            endpoint: API endpoint (with or without leading /)
            method: HTTP method (GET, POST, etc.)
            retry_502_max: Maximum retries for 502 errors
            **kwargs: Additional arguments for requests
            
        Returns:
            JSON response as dictionary
            
        Raises:
            ValueError: If non-200 status or max retries exceeded
        """
        if not endpoint.startswith('/'):
            endpoint = '/' + endpoint
        
        url = self.server + endpoint
        logger.info(f"Calling PrairieLearn API: {method} {url}")
        
        retry_502_count = 0
        
        while True:
            response = self.session.request(method, url, **kwargs)
            
            if response.status_code == 200:
                logger.info(f"API call successful: {url}")
                return response.json()
            
            if response.status_code == 502:
                retry_502_count += 1
                logger.warning(
                    f"502 Bad Gateway at {url} "
                    f"(retry {retry_502_count}/{retry_502_max})"
                )
                
                if retry_502_count >= retry_502_max:
                    logger.error(f"Max retries reached for {url}")
                    raise ValueError(
                        f"Max retries reached on 502 error for {url}"
                    )
                
                time.sleep(10)
                continue
            
            # Other error status codes
            logger.error(f"API error: {response.status_code} at {url}")
            logger.error(f"Response: {response.text}")
            raise ValueError(
                f"API returned status {response.status_code} for {url}"
            )
    
    def get_course_info(self, course_id: str) -> CourseInfo:
        """
        Get information about a course.
        
        Args:
            course_id: Course instance ID
            
        Returns:
            CourseInfo object
        """
        data = self._call_api(f"/course_instances/{course_id}")
        return CourseInfo(
            course_id=course_id,
            short_name=data.get('short_name', ''),
            title=data.get('title', ''),
            display_timezone=data.get('display_timezone', 'UTC')
        )
    
    def get_assessments(self, course_id: str) -> List[AssessmentInfo]:
        """
        Get all assessments for a course.
        
        Args:
            course_id: Course instance ID
            
        Returns:
            List of AssessmentInfo objects
        """
        data = self._call_api(f"/course_instances/{course_id}/assessments")
        
        assessments = []
        for item in data:
            assessments.append(AssessmentInfo(
                assessment_id=str(item['assessment_id']),
                title=item.get('title', ''),
                number=item.get('number', ''),
                type=item.get('type', ''),
                points=float(item.get('max_points', 0))
            ))
        
        logger.info(f"Found {len(assessments)} assessments in course {course_id}")
        return assessments
    
    def get_assessment_instances(
        self,
        course_id: str,
        assessment_id: str
    ) -> pd.DataFrame:
        """
        Get student instances for an assessment.
        
        Args:
            course_id: Course instance ID
            assessment_id: Assessment ID
            
        Returns:
            DataFrame with columns: user_id, points, max_points, score_perc, etc.
        """
        endpoint = (
            f"/course_instances/{course_id}"
            f"/assessments/{assessment_id}/assessment_instances"
        )
        data = self._call_api(endpoint)
        
        df = pd.DataFrame(data)
        logger.info(
            f"Retrieved {len(df)} instances for assessment {assessment_id}"
        )
        return df
    
    def get_gradebook(self, course_id: str) -> pd.DataFrame:
        """
        Get complete gradebook for a course.
        
        Args:
            course_id: Course instance ID
            
        Returns:
            DataFrame with all student grades and assessments
        """
        endpoint = f"/course_instances/{course_id}/gradebook"
        data = self._call_api(endpoint)
        
        df = pd.DataFrame(data)
        logger.info(f"Retrieved gradebook with {len(df)} records")
        return df
    
    def get_student_gradebook(
        self,
        course_id: str,
        user_id: str
    ) -> Dict[str, Any]:
        """
        Get gradebook for a specific student.
        
        Args:
            course_id: Course instance ID
            user_id: Student user ID
            
        Returns:
            Dictionary with student's grades
        """
        endpoint = f"/course_instances/{course_id}/gradebook/{user_id}"
        data = self._call_api(endpoint)
        
        logger.info(f"Retrieved gradebook for user {user_id}")
        return data
    
    def get_submissions(
        self,
        course_id: str,
        assessment_id: str,
        question_id: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Get submissions for an assessment or question.
        
        Args:
            course_id: Course instance ID
            assessment_id: Assessment ID
            question_id: Optional question ID to filter
            
        Returns:
            DataFrame with submission details
        """
        endpoint = (
            f"/course_instances/{course_id}"
            f"/assessments/{assessment_id}/submissions"
        )
        
        params = {}
        if question_id:
            params['question_id'] = question_id
        
        data = self._call_api(endpoint, params=params)
        df = pd.DataFrame(data)
        
        logger.info(f"Retrieved {len(df)} submissions")
        return df
    
    def export_gradebook_to_dict(self, course_id: str) -> Dict[str, pd.DataFrame]:
        """
        Export gradebook organized by assessment.
        
        Args:
            course_id: Course instance ID
            
        Returns:
            Dictionary mapping assessment titles to DataFrames
        """
        gradebook_df = self.get_gradebook(course_id)
        assessments = self.get_assessments(course_id)
        
        result = {}
        for assessment in assessments:
            # Filter gradebook for this assessment
            assessment_data = gradebook_df[
                gradebook_df['assessment_id'] == int(assessment.assessment_id)
            ].copy()
            
            if len(assessment_data) > 0:
                result[assessment.title] = assessment_data
        
        logger.info(f"Exported {len(result)} assessments to dict")
        return result
    
    def close(self):
        """Close the HTTP session."""
        self.session.close()
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
