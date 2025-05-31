"""
Import Tracker Database Manager

This module provides functionality for tracking PubMed file processing
to avoid reprocessing the same files when restarting interrupted processes.
"""

import os
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional, Set
from pathlib import Path

from localknowledge.db.base import DatabaseManager

logger = logging.getLogger(__name__)


class ImportTracker(DatabaseManager):
    """
    Tracks PubMed file processing to avoid reprocessing files.

    This class maintains a database table that records which PubMed XML files
    have been imported, chunked, and embedded, preventing duplicate processing
    when running scripts on a regular schedule or after interruptions.
    """

    def __init__(self):
        """Initialize the import tracker."""
        super().__init__()
        self._ensure_table_exists()

    def _ensure_table_exists(self) -> None:
        """
        Create the import_tracker table if it doesn't exist.
        This is a fallback in case migrations haven't been run.
        """
        try:
            self.execute("""
            CREATE TABLE IF NOT EXISTS import_tracker (
                filename TEXT NOT NULL PRIMARY KEY,
                imported TIMESTAMP WITH TIME ZONE DEFAULT NULL,
                chunked TIMESTAMP WITH TIME ZONE DEFAULT NULL,
                embedded BOOLEAN DEFAULT FALSE,
                md5checked BOOLEAN DEFAULT FALSE
            )
            """, commit=True)
            logger.debug("Ensured import_tracker table exists")
        except Exception as e:
            logger.error(f"Error creating import_tracker table: {e}")
            raise

    def is_file_imported(self, filename: str) -> bool:
        """
        Check if a file has been imported already.

        Args:
            filename: Name of the file to check (just the filename, not full path)

        Returns:
            Boolean indicating if the file has been imported
        """
        try:
            results = self.execute(
                "SELECT imported FROM import_tracker WHERE filename = %s",
                (filename,)
            )
            if results:
                result = results[0]
                return result is not None and result['imported'] is not None
            return False
        except Exception as e:
            logger.error(f"Error checking import status for {filename}: {e}")
            return False

    def is_file_chunked(self, filename: str) -> bool:
        """
        Check if a file has been chunked already.

        Args:
            filename: Name of the file to check

        Returns:
            Boolean indicating if the file has been chunked
        """
        try:
            results = self.execute(
                "SELECT chunked FROM import_tracker WHERE filename = %s",
                (filename,)
            )
            if results:
                result = results[0]
                return result is not None and result['chunked'] is not None
            return False
        except Exception as e:
            logger.error(f"Error checking chunked status for {filename}: {e}")
            return False

    def is_file_embedded(self, filename: str) -> bool:
        """
        Check if a file has been embedded already.

        Args:
            filename: Name of the file to check

        Returns:
            Boolean indicating if the file has been embedded
        """
        try:
            results = self.execute(
                "SELECT embedded FROM import_tracker WHERE filename = %s",
                (filename,)
            )
            if results:
                result = results[0]
                return result is not None and result['embedded'] is True
            return False
        except Exception as e:
            logger.error(f"Error checking embedded status for {filename}: {e}")
            return False

    def is_file_md5checked(self, filename: str) -> bool:
        """
        Check if a file has been MD5 checked already.

        Args:
            filename: Name of the file to check

        Returns:
            Boolean indicating if the file has been MD5 checked
        """
        try:
            results = self.execute(
                "SELECT md5checked FROM import_tracker WHERE filename = %s",
                (filename,)
            )
            if results:
                result = results[0]
                return result is not None and result['md5checked'] is True
            return False
        except Exception as e:
            logger.error(f"Error checking MD5 status for {filename}: {e}")
            return False

    def mark_file_imported(self, filename: str) -> None:
        """
        Mark a file as imported.

        Args:
            filename: Name of the file to mark as imported
        """
        try:
            self.execute("""
            INSERT INTO import_tracker (filename, imported)
            VALUES (%s, CURRENT_TIMESTAMP)
            ON CONFLICT (filename)
            DO UPDATE SET imported = CURRENT_TIMESTAMP
            """, (filename,), commit=True)
            logger.debug(f"Marked {filename} as imported")
        except Exception as e:
            logger.error(f"Error marking {filename} as imported: {e}")
            raise

    def mark_file_chunked(self, filename: str) -> None:
        """
        Mark a file as chunked.

        Args:
            filename: Name of the file to mark as chunked
        """
        try:
            self.execute("""
            INSERT INTO import_tracker (filename, chunked)
            VALUES (%s, CURRENT_TIMESTAMP)
            ON CONFLICT (filename)
            DO UPDATE SET chunked = CURRENT_TIMESTAMP
            """, (filename,), commit=True)
            logger.debug(f"Marked {filename} as chunked")
        except Exception as e:
            logger.error(f"Error marking {filename} as chunked: {e}")
            raise

    def mark_file_embedded(self, filename: str) -> None:
        """
        Mark a file as embedded.

        Args:
            filename: Name of the file to mark as embedded
        """
        try:
            self.execute("""
            INSERT INTO import_tracker (filename, embedded)
            VALUES (%s, TRUE)
            ON CONFLICT (filename)
            DO UPDATE SET embedded = TRUE
            """, (filename,), commit=True)
            logger.debug(f"Marked {filename} as embedded")
        except Exception as e:
            logger.error(f"Error marking {filename} as embedded: {e}")
            raise

    def mark_file_md5checked(self, filename: str) -> None:
        """
        Mark a file as MD5 checked.

        Args:
            filename: Name of the file to mark as MD5 checked
        """
        try:
            self.execute("""
            INSERT INTO import_tracker (filename, md5checked)
            VALUES (%s, TRUE)
            ON CONFLICT (filename)
            DO UPDATE SET md5checked = TRUE
            """, (filename,), commit=True)
            logger.debug(f"Marked {filename} as MD5 checked")
        except Exception as e:
            logger.error(f"Error marking {filename} as MD5 checked: {e}")
            raise

    def get_unprocessed_files(self, file_list: List[str],
                             check_imported: bool = True,
                             check_chunked: bool = False,
                             check_embedded: bool = False) -> List[str]:
        """
        Get files from the list that haven't been processed according to the specified criteria.

        Args:
            file_list: List of filenames to check
            check_imported: Whether to filter out already imported files
            check_chunked: Whether to filter out already chunked files
            check_embedded: Whether to filter out already embedded files

        Returns:
            List of filenames that haven't been processed
        """
        if not file_list:
            return []

        unprocessed = []
        for filename in file_list:
            should_process = True

            if check_imported and self.is_file_imported(filename):
                should_process = False
            elif check_chunked and self.is_file_chunked(filename):
                should_process = False
            elif check_embedded and self.is_file_embedded(filename):
                should_process = False

            if should_process:
                unprocessed.append(filename)

        return unprocessed

    def get_processing_stats(self) -> Dict[str, int]:
        """
        Get statistics about file processing.

        Returns:
            Dictionary with processing statistics
        """
        try:
            results = self.execute("""
            SELECT
                COUNT(*) as total_files,
                COUNT(imported) as imported_files,
                COUNT(chunked) as chunked_files,
                SUM(CASE WHEN embedded THEN 1 ELSE 0 END) as embedded_files,
                SUM(CASE WHEN md5checked THEN 1 ELSE 0 END) as md5checked_files
            FROM import_tracker
            """)

            if results:
                result = results[0]
                return {
                    'total_files': result['total_files'],
                    'imported_files': result['imported_files'],
                    'chunked_files': result['chunked_files'],
                    'embedded_files': result['embedded_files'],
                    'md5checked_files': result['md5checked_files']
                }
            else:
                return {
                    'total_files': 0,
                    'imported_files': 0,
                    'chunked_files': 0,
                    'embedded_files': 0,
                    'md5checked_files': 0
                }
        except Exception as e:
            logger.error(f"Error getting processing stats: {e}")
            return {
                'total_files': 0,
                'imported_files': 0,
                'chunked_files': 0,
                'embedded_files': 0,
                'md5checked_files': 0
            }

    def reset_file_status(self, filename: str) -> None:
        """
        Reset all processing status for a file (useful for reprocessing).

        Args:
            filename: Name of the file to reset
        """
        try:
            self.execute("""
            DELETE FROM import_tracker WHERE filename = %s
            """, (filename,), commit=True)
            logger.info(f"Reset processing status for {filename}")
        except Exception as e:
            logger.error(f"Error resetting status for {filename}: {e}")
            raise
