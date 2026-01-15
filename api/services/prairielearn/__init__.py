"""
PrairieLearn Service Module

Provides client for PrairieLearn API access and sync operations.
"""
from .client import PrairieLearnClient, CourseInfo, AssessmentInfo
from .sync import PrairieLearnSync

__all__ = ['PrairieLearnClient', 'CourseInfo', 'AssessmentInfo', 'PrairieLearnSync']
