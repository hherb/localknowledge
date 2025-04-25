"""
Migration 003: add_project_management

This migration script adds project management tables for the Researcher's Workbench (RWB).
It creates the projects table and project_contributors table for managing research projects.
"""

import logging
from typing import Callable, Optional
from localknowledge.db.migrations_system.manager import MigrationsManager

# Configure logging
logger = logging.getLogger(__name__)


def migrate(db_manager: MigrationsManager, progress_callback: Optional[Callable[[int, int, str], None]] = None) -> None:
    """
    Run the migration.
    
    Args:
        db_manager: Database manager to use for the migration
        progress_callback: Optional callback function for progress updates
    """
    logger.info("Starting migration 003: add_project_management")
    
    # Step 1: Check if the projects table already exists
    logger.info("Checking if projects table already exists")
    result = db_manager.execute_without_timeout("""
    SELECT table_name
    FROM information_schema.tables
    WHERE table_schema = 'public' AND table_name = 'projects';
    """)
    
    if result and len(result) > 0:
        logger.info("Projects table already exists, skipping creation")
    else:
        # Step 2: Create the projects table
        logger.info("Creating projects table")
        db_manager.execute_without_timeout("""
        CREATE TABLE IF NOT EXISTS projects (
            id SERIAL PRIMARY KEY,
            title TEXT NOT NULL,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_worked_on TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            manager_id INTEGER REFERENCES users(id) ON DELETE SET NULL
        )
        """, commit=True)
        
        if progress_callback:
            progress_callback(1, 4, "Created projects table")
    
    # Step 3: Check if the project_contributors table already exists
    logger.info("Checking if project_contributors table already exists")
    result = db_manager.execute_without_timeout("""
    SELECT table_name
    FROM information_schema.tables
    WHERE table_schema = 'public' AND table_name = 'project_contributors';
    """)
    
    if result and len(result) > 0:
        logger.info("Project_contributors table already exists, skipping creation")
    else:
        # Step 4: Create the project_contributors table
        logger.info("Creating project_contributors table")
        db_manager.execute_without_timeout("""
        CREATE TABLE IF NOT EXISTS project_contributors (
            project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            PRIMARY KEY (project_id, user_id)
        )
        """, commit=True)
        
        if progress_callback:
            progress_callback(2, 4, "Created project_contributors table")
    
    # Step 5: Create index for project contributors if it doesn't exist
    logger.info("Creating index for project contributors")
    db_manager.execute_without_timeout("""
    CREATE INDEX IF NOT EXISTS idx_project_contributors_user_id 
    ON project_contributors(user_id)
    """, commit=True)
    
    if progress_callback:
        progress_callback(3, 4, "Created index for project contributors")
    
    # Step 6: Create index for projects by manager if it doesn't exist
    logger.info("Creating index for projects by manager")
    db_manager.execute_without_timeout("""
    CREATE INDEX IF NOT EXISTS idx_projects_manager_id 
    ON projects(manager_id)
    """, commit=True)
    
    if progress_callback:
        progress_callback(4, 4, "Created index for projects by manager")
    
    logger.info("Migration 003 completed")
