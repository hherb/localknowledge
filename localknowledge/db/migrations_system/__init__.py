"""
Database migrations system for the LocalKnowledge library.

This module provides functionality for managing database schema migrations.
It tracks the current database version and applies migrations in sequence.
"""

from .manager import MigrationsManager
from .config import get_migrations_dir

__all__ = ['MigrationsManager', 'get_migrations_dir']
