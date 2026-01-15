"""
Core data layer module

Provides database connection, ORM models, and data persistence.
"""
from . import db
from . import models
from . import ingest

__all__ = ['db', 'models', 'ingest']
