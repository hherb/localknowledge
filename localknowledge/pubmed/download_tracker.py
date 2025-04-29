"""
Tracks PubMed downloads to avoid reprocessing files that have already been downloaded and processed.
"""
import os
import logging
import re
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple

from localknowledge.db.base import DatabaseManager

logger = logging.getLogger()

class PubMedDownloadTracker(DatabaseManager):
    """
    Tracks PubMed downloads to avoid reprocessing files.

    This class maintains a database table that records which PubMed update files
    have been downloaded and processed, preventing duplicate processing when
    running the script on a regular schedule.
    """

    def __init__(self):
        """Initialize the PubMed download tracker."""
        super().__init__()
        self._ensure_table_exists()

    def _ensure_table_exists(self) -> None:
        """
        Create the pubmed_download_log table if it doesn't exist.
        """
        try:
            with self.connection.cursor() as cursor:
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS pubmed_download_log (
                    id SERIAL PRIMARY KEY,
                    file_name VARCHAR(255) NOT NULL,
                    file_type VARCHAR(50) NOT NULL,
                    download_date TIMESTAMP NOT NULL,
                    processed BOOLEAN DEFAULT FALSE,
                    process_date TIMESTAMP,
                    file_size BIGINT,
                    checksum VARCHAR(64),
                    status VARCHAR(20) DEFAULT 'downloaded',
                    UNIQUE(file_name)
                )
                ''')
                self.connection.commit()
                logger.info("Ensured pubmed_download_log table exists")
        except Exception as e:
            logger.error(f"Error creating tracking table: {e}")
            self.connection.rollback()
            raise

    def is_file_downloaded(self, file_name: str) -> bool:
        """
        Check if a file has been downloaded already.

        Args:
            file_name: Name of the file to check

        Returns:
            Boolean indicating if the file has been downloaded
        """
        try:
            with self.connection.cursor() as cursor:
                cursor.execute(
                    "SELECT 1 FROM pubmed_download_log WHERE file_name = %s",
                    (file_name,)
                )
                return cursor.fetchone() is not None
        except Exception as e:
            logger.error(f"Error checking download status: {e}")
            return False

    def log_download(self, file_name: str, file_type: str, file_size: int) -> None:
        """
        Log a file as downloaded in the database.

        Args:
            file_name: Name of the downloaded file
            file_type: Type of file ('baseline' or 'update')
            file_size: Size of the file in bytes
        """
        try:
            with self.connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO pubmed_download_log
                    (file_name, file_type, download_date, file_size)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (file_name)
                    DO UPDATE SET
                        file_size = EXCLUDED.file_size,
                        download_date = EXCLUDED.download_date,
                        status = 'downloaded'
                    """,
                    (file_name, file_type, datetime.now(), file_size)
                )
                self.connection.commit()
                logger.info(f"Logged download of {file_name}")
        except Exception as e:
            logger.error(f"Error logging download: {e}")
            self.connection.rollback()

    def mark_as_processed(self, file_name: str) -> None:
        """
        Mark a file as processed in the database.

        Args:
            file_name: Name of the file that was processed
        """
        try:
            with self.connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE pubmed_download_log
                    SET processed = TRUE, process_date = %s, status = 'processed'
                    WHERE file_name = %s
                    """,
                    (datetime.now(), file_name)
                )
                self.connection.commit()
                logger.info(f"Marked {file_name} as processed")
        except Exception as e:
            logger.error(f"Error marking file as processed: {e}")
            self.connection.rollback()

    def is_file_processed(self, file_name: str) -> bool:
        """
        Check if a file has been processed already.

        Args:
            file_name: Name of the file to check

        Returns:
            Boolean indicating if the file has been processed
        """
        try:
            with self.connection.cursor() as cursor:
                cursor.execute(
                    "SELECT processed FROM pubmed_download_log WHERE file_name = %s",
                    (file_name,)
                )
                result = cursor.fetchone()
                return result is not None and result[0] is True
        except Exception as e:
            logger.error(f"Error checking processing status: {e}")
            return False

    def get_unprocessed_files(self, file_type: Optional[str] = None) -> List[str]:
        """
        Get list of downloaded but unprocessed files.

        Args:
            file_type: Optional filter by file type ('baseline' or 'update')

        Returns:
            List of filenames that have been downloaded but not processed
        """
        try:
            with self.connection.cursor() as cursor:
                if file_type:
                    cursor.execute(
                        """
                        SELECT file_name FROM pubmed_download_log
                        WHERE processed = FALSE AND file_type = %s
                        ORDER BY file_name
                        """,
                        (file_type,)
                    )
                else:
                    cursor.execute(
                        """
                        SELECT file_name FROM pubmed_download_log
                        WHERE processed = FALSE
                        ORDER BY file_name
                        """
                    )
                return [row[0] for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Error getting unprocessed files: {e}")
            return []

    def get_download_stats(self) -> Dict[str, Any]:
        """
        Get statistics about downloads and processing.

        Returns:
            Dictionary with statistics
        """
        stats = {
            'total_files': 0,
            'downloaded_files': 0,
            'processed_files': 0,
            'baseline_files': 0,
            'update_files': 0,
            'last_download_date': None,
            'last_process_date': None
        }

        try:
            with self.connection.cursor() as cursor:
                # Get total counts
                cursor.execute(
                    "SELECT COUNT(*) FROM pubmed_download_log"
                )
                stats['total_files'] = cursor.fetchone()[0]

                # Get processed count
                cursor.execute(
                    "SELECT COUNT(*) FROM pubmed_download_log WHERE processed = TRUE"
                )
                stats['processed_files'] = cursor.fetchone()[0]

                # Calculate downloaded but not processed
                stats['downloaded_files'] = stats['total_files'] - stats['processed_files']

                # Get file type counts
                cursor.execute(
                    "SELECT COUNT(*) FROM pubmed_download_log WHERE file_type = 'baseline'"
                )
                stats['baseline_files'] = cursor.fetchone()[0]

                cursor.execute(
                    "SELECT COUNT(*) FROM pubmed_download_log WHERE file_type = 'update'"
                )
                stats['update_files'] = cursor.fetchone()[0]

                # Get latest dates
                cursor.execute(
                    "SELECT MAX(download_date) FROM pubmed_download_log"
                )
                result = cursor.fetchone()
                stats['last_download_date'] = result[0] if result else None

                cursor.execute(
                    "SELECT MAX(process_date) FROM pubmed_download_log"
                )
                result = cursor.fetchone()
                stats['last_process_date'] = result[0] if result else None

                return stats
        except Exception as e:
            logger.error(f"Error getting download stats: {e}")
            return stats

    def get_highest_sequence_number(self, processed_only=False) -> int:
        """
        Get the highest sequence number from PubMed filenames in the database.

        The filenames are in the format pubmed<year>n<sequence_number>.xml.gz
        For example: pubmed25n1378.xml.gz where 1378 is the sequence number.

        Args:
            processed_only (bool): If True, only consider files that have been processed

        Returns:
            The highest sequence number as an integer, or 0 if no files are found
        """
        try:
            with self.connection.cursor() as cursor:
                # Get the file with the highest sequence number by ordering by filename in descending order
                if processed_only:
                    cursor.execute(
                        "SELECT file_name FROM pubmed_download_log WHERE processed = TRUE ORDER BY file_name DESC LIMIT 1"
                    )
                else:
                    cursor.execute(
                        "SELECT file_name FROM pubmed_download_log ORDER BY file_name DESC LIMIT 1"
                    )
                result = cursor.fetchone()

                if result and result[0]:
                    filename = result[0]
                    # Extract the sequence number using regex
                    match = re.search(r'pubmed\d+n(\d+)\.xml\.gz', filename)
                    if match:
                        return int(match.group(1))
                    else:
                        logger.warning(f"Could not extract sequence number from filename: {filename}")

                # Return 0 if no files found or couldn't extract sequence number
                return 0

        except Exception as e:
            logger.error(f"Error getting highest sequence number: {e}")
            return 0
