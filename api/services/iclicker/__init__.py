"""
iClicker Service Module

Provides client for iClicker attendance data access and sync operations.
"""
from .client import IClickerClient
from .sync import IClickerSync

__all__ = ['IClickerClient', 'IClickerSync']
