#!/usr/bin/env python3
"""
Monolithic database initialization script for the LocalKnowledge library.

This script creates all database tables, indices, and extensions in a single
transaction. It should be run only once to initialize a new database. After
the initial setup, all schema changes should be done through migrations.

Usage:
    python -m localknowledge.db.create_baseline_db [--force]

Options:
    --force    Force recreation of tables (WARNING: This will delete all data)
"""

import os
import sys
import argparse
import logging
import psycopg2
from typing import Dict, Any, Optional, List

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import the basic_infrastructure module
try:
    from localknowledge.db.basic_infrastructure import load_environment, get_db_connection_params
    BASIC_INFRASTRUCTURE_AVAILABLE = True
except ImportError:
    logger.warning("Basic infrastructure module not available. Using direct environment access.")
    BASIC_INFRASTRUCTURE_AVAILABLE = False
    from dotenv import load_dotenv


class BaselineDBCreator:
    """Class to create the baseline database schema."""

    def __init__(self, force: bool = False, dotenv_path: Optional[str] = None):
        """
        Initialize the baseline database creator.

        Args:
            force: Whether to force recreation of tables (WARNING: This will delete all data)
            dotenv_path: Path to the .env file. If None, uses DOTENV_FILE environment variable or defaults to '.env'
        """
        self.force = force
        self.dotenv_path = dotenv_path
        self.connection = None

        # Load environment variables
        if BASIC_INFRASTRUCTURE_AVAILABLE:
            load_environment(dotenv_path=self.dotenv_path)
        else:
            # Fallback to direct environment variable access
            dotenv_file = os.environ.get('DOTENV_FILE', '.env')
            if os.path.exists(dotenv_file):
                load_dotenv(dotenv_file)
            else:
                load_dotenv()

        self.connect()

    def connect(self) -> None:
        """Connect to the database using environment variables."""
        try:
            if BASIC_INFRASTRUCTURE_AVAILABLE:
                # Use the centralized environment loading
                connection_params = get_db_connection_params(dotenv_path=self.dotenv_path)

                self.connection = psycopg2.connect(**connection_params)
                logger.info(f"Connected to database {connection_params['dbname']} at {connection_params['host']}:{connection_params['port']}")
            else:
                # Fallback to direct environment variable access
                dbname = os.environ.get('POSTGRES_DB')
                user = os.environ.get('POSTGRES_USER', 'postgres')
                password = os.environ.get('POSTGRES_PASSWORD', '')
                host = os.environ.get('POSTGRES_HOST', 'localhost')
                port = os.environ.get('POSTGRES_PORT', '5432')

                if not dbname:
                    raise ValueError("POSTGRES_DB environment variable must be set")

                self.connection = psycopg2.connect(
                    dbname=dbname,
                    user=user,
                    password=password,
                    host=host,
                    port=port
                )
                logger.info(f"Connected to database {dbname} at {host}:{port}")
        except psycopg2.Error as e:
            raise ConnectionError(f"Failed to connect to PostgreSQL database: {e}")

    def execute(self, query: str, params: Optional[tuple] = None) -> Optional[List[Dict[str, Any]]]:
        """
        Execute a SQL query.

        Args:
            query: SQL query to execute
            params: Query parameters

        Returns:
            Query results as a list of dictionaries, or None for non-SELECT queries
        """
        if not self.connection:
            self.connect()

        cursor = self.connection.cursor()
        try:
            cursor.execute(query, params or ())

            if cursor.description:  # This is a SELECT query
                columns = [col[0] for col in cursor.description]
                return [dict(zip(columns, row)) for row in cursor.fetchall()]
            return None

        except psycopg2.Error as e:
            logger.error(f"Error executing query: {e}")
            raise
        finally:
            cursor.close()

    def check_if_tables_exist(self) -> bool:
        """
        Check if any tables already exist in the database.

        Returns:
            bool: True if tables exist, False otherwise
        """
        query = """
        SELECT COUNT(*) as table_count
        FROM information_schema.tables
        WHERE table_schema = 'public'
        """
        result = self.execute(query)

        if result and result[0]['table_count'] > 0:
            return True
        return False

    def create_extensions(self) -> None:
        """Create required PostgreSQL extensions."""
        logger.info("Creating required PostgreSQL extensions")

        # Create pgvector extension
        self.execute("CREATE EXTENSION IF NOT EXISTS vector")
        logger.info("Created pgvector extension")

    def drop_all_tables(self) -> None:
        """Drop all tables in the database."""
        if not self.force:
            logger.error("Cannot drop tables without --force flag")
            return

        logger.warning("Dropping all tables in the database")

        # Get all tables
        query = """
        SELECT tablename
        FROM pg_tables
        WHERE schemaname = 'public'
        """
        result = self.execute(query)

        if not result:
            logger.info("No tables to drop")
            return

        # Drop all tables
        for row in result:
            table_name = row['tablename']
            logger.info(f"Dropping table {table_name}")
            self.execute(f"DROP TABLE IF EXISTS {table_name} CASCADE")

        logger.info("All tables dropped")

    def create_migrations_table(self) -> None:
        """Create the version table for migrations."""
        logger.info("Creating version table for migrations")

        query = """
        CREATE TABLE IF NOT EXISTS version (
            version INTEGER UNIQUE NOT NULL,
            migrated TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            migration_success BOOLEAN NOT NULL
        )
        """
        self.execute(query)

        # Insert initial version record
        query = """
        INSERT INTO version (version, migrated, migration_success)
        VALUES (1, CURRENT_TIMESTAMP, TRUE)
        ON CONFLICT (version) DO NOTHING
        """
        self.execute(query)

        logger.info("Version table created and initialized to version 1")

    def create_user_tables(self) -> None:
        """Create user-related tables."""
        logger.info("Creating user tables")

        # Create users table
        query = """
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            firstname TEXT,
            surname TEXT,
            email TEXT UNIQUE,
            pwdhash TEXT NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP WITH TIME ZONE
        )
        """
        self.execute(query)

        # Create user preferences table
        query = """
        CREATE TABLE IF NOT EXISTS user_preferences (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            preference_key TEXT NOT NULL,
            preference_value TEXT,
            UNIQUE (user_id, preference_key)
        )
        """
        self.execute(query)

        logger.info("User tables created")

    def create_document_tables(self) -> None:
        """Create document-related tables."""
        logger.info("Creating document tables")

        # Create sources table
        query = """
        CREATE TABLE IF NOT EXISTS sources (
            id SERIAL PRIMARY KEY,
            name TEXT UNIQUE NOT NULL,
            description TEXT,
            url TEXT,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        )
        """
        self.execute(query)

        # Create categories table
        query = """
        CREATE TABLE IF NOT EXISTS categories (
            id SERIAL PRIMARY KEY,
            name TEXT UNIQUE NOT NULL,
            parent_id INTEGER REFERENCES categories(id),
            description TEXT,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        )
        """
        self.execute(query)

        # Create document table
        query = """
        CREATE TABLE IF NOT EXISTS document (
            id SERIAL PRIMARY KEY,
            source_id INTEGER REFERENCES sources(id),
            external_id TEXT NOT NULL,  -- e.g., DOI or PMID
            doi TEXT,
            title TEXT,
            abstract TEXT,
            category_id INTEGER REFERENCES categories(id),
            keywords TEXT[],
            augmented_keywords TEXT[],  -- keywords expanded and AI generated
            mesh_terms TEXT[],
            authors TEXT[],
            publication TEXT,
            publication_date DATE,
            url TEXT,
            pdf_url TEXT,
            pdf_filename TEXT,
            full_text TEXT,
            added_date TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            updated_date TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            withdrawn_date TIMESTAMP WITH TIME ZONE,
            withdrawn_reason TEXT,
            UNIQUE (source_id, external_id)
        )
        """
        self.execute(query)

        # Create document_keywords table
        query = """
        CREATE TABLE IF NOT EXISTS document_keywords (
            id SERIAL PRIMARY KEY,
            document_id INTEGER REFERENCES document(id) ON DELETE CASCADE,
            keyword TEXT NOT NULL,
            weight FLOAT,
            source TEXT,  -- e.g., 'author', 'extracted', 'ai_generated'
            UNIQUE (document_id, keyword, source)
        )
        """
        self.execute(query)

        # Create tags table
        query = """
        CREATE TABLE IF NOT EXISTS tags (
            id SERIAL PRIMARY KEY,
            document_id INTEGER REFERENCES document(id) ON DELETE CASCADE,
            user_id INTEGER REFERENCES users(id),
            tag TEXT NOT NULL,
            UNIQUE (document_id, user_id, tag)
        )
        """
        self.execute(query)

        logger.info("Document tables created")

    def create_reading_tracker_tables(self) -> None:
        """Create reading tracker tables."""
        logger.info("Creating reading tracker tables")

        query = """
        CREATE TABLE IF NOT EXISTS reading_records (
            id SERIAL PRIMARY KEY,
            source_type TEXT,
            content_id TEXT,
            document_id INTEGER REFERENCES document(id) ON DELETE CASCADE,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            read_timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            rating INTEGER,
            notes TEXT,
            UNIQUE (document_id, user_id)
        )
        """
        self.execute(query)

        logger.info("Reading tracker tables created")

    def create_embedding_tables(self) -> None:
        """Create embedding-related tables."""
        logger.info("Creating embedding tables")

        # Create embedding_source table
        query = """
        CREATE TABLE IF NOT EXISTS embedding_source (
            id SERIAL PRIMARY KEY,
            name TEXT UNIQUE NOT NULL,
            description TEXT,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        )
        """
        self.execute(query)

        # Insert default embedding sources
        query = """
        INSERT INTO embedding_source (name, description)
        VALUES
            ('abstract', 'Document abstract'),
            ('full_text', 'Full document text'),
            ('chunk', 'Document text chunk'),
            ('qa_pair', 'Question-answer pair')
        ON CONFLICT (name) DO NOTHING
        """
        self.execute(query)

        # Create unified_multiembeddings table
        query = """
        CREATE TABLE IF NOT EXISTS unified_multiembeddings (
            id SERIAL PRIMARY KEY,
            document_id INTEGER REFERENCES document(id) ON DELETE CASCADE,
            embed_source_id INTEGER REFERENCES embedding_source(id),
            chunk_no INTEGER,
            page_no INTEGER,
            text TEXT NOT NULL,
            keywords TEXT[],
            embedding vector(1024),
            model_name TEXT NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (document_id, embed_source_id, chunk_no, model_name)
        )
        """
        self.execute(query)

        # Create legacy embeddings table (for backward compatibility)
        query = """
        CREATE TABLE IF NOT EXISTS embeddings (
            id SERIAL PRIMARY KEY,
            source_id TEXT NOT NULL,
            document_id TEXT NOT NULL,
            document_ref_id INTEGER REFERENCES document(id) ON DELETE CASCADE,
            chunk_no INTEGER NOT NULL,
            page_no INTEGER,
            text TEXT NOT NULL,
            keywords TEXT[],
            embedding vector(1024),
            model_name TEXT NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (source_id, document_id, chunk_no)
        )
        """
        self.execute(query)

        # Create legacy qaembeddings table (for backward compatibility)
        query = """
        CREATE TABLE IF NOT EXISTS qaembeddings (
            id SERIAL PRIMARY KEY,
            source_id TEXT NOT NULL,
            document_id TEXT NOT NULL,
            document_ref_id INTEGER REFERENCES document(id) ON DELETE CASCADE,
            chunk_no INTEGER NOT NULL,
            page_no INTEGER,
            qa_pairs TEXT NOT NULL,
            embedding vector(1024),
            model_name TEXT NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (source_id, document_id, chunk_no)
        )
        """
        self.execute(query)

        logger.info("Embedding tables created")

    def create_legacy_tables(self) -> None:
        """Create legacy tables for backward compatibility."""
        logger.info("Creating legacy tables for backward compatibility")

        # Create preprints table (legacy MedRxiv table)
        query = """
        CREATE TABLE IF NOT EXISTS preprints (
            doi TEXT PRIMARY KEY,
            title TEXT,
            abstract TEXT,
            authors TEXT,
            date_posted TEXT,
            category TEXT,
            pdf_url TEXT,
            local_pdf_path TEXT,
            full_text TEXT
        )
        """
        self.execute(query)

        # Create summaries table (legacy MedRxiv table)
        query = """
        CREATE TABLE IF NOT EXISTS summaries (
            id SERIAL PRIMARY KEY,
            publication_id TEXT REFERENCES preprints(doi) ON DELETE CASCADE,
            document_id INTEGER REFERENCES document(id) ON DELETE CASCADE,
            summary TEXT,
            evaluation BOOLEAN,
            reason TEXT,
            interests TEXT[],
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        )
        """
        self.execute(query)

        # Create pubmed_articles table (legacy PubMed table)
        query = """
        CREATE TABLE IF NOT EXISTS pubmed_articles (
            pmid TEXT PRIMARY KEY,
            title TEXT,
            abstract TEXT,
            authors TEXT,
            publication_year TEXT,
            journal TEXT,
            mesh_terms TEXT,
            keywords TEXT,
            doi TEXT,
            date_created TEXT,
            date_completed TEXT,
            date_revised TEXT,
            pdf_path TEXT,
            imported_date TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        )
        """
        self.execute(query)

        logger.info("Legacy tables created")

    def create_indices(self) -> None:
        """Create indices for all tables."""
        logger.info("Creating indices for all tables")

        # Document table indices
        indices = [
            "CREATE INDEX IF NOT EXISTS idx_document_external_id ON document(external_id)",
            "CREATE INDEX IF NOT EXISTS idx_document_doi ON document(doi)",
            "CREATE INDEX IF NOT EXISTS idx_document_title ON document USING gin(to_tsvector('english', title))",
            "CREATE INDEX IF NOT EXISTS idx_document_abstract ON document USING gin(to_tsvector('english', abstract))",
            "CREATE INDEX IF NOT EXISTS idx_document_keywords ON document USING gin(keywords)",
            "CREATE INDEX IF NOT EXISTS idx_document_publication_date ON document(publication_date)"
        ]

        # Reading records indices
        indices.extend([
            "CREATE INDEX IF NOT EXISTS idx_reading_records_document_id ON reading_records(document_id)",
            "CREATE INDEX IF NOT EXISTS idx_reading_records_user_id ON reading_records(user_id)",
            "CREATE INDEX IF NOT EXISTS idx_reading_records_timestamp ON reading_records(read_timestamp)"
        ])

        # Embedding indices
        indices.extend([
            "CREATE INDEX IF NOT EXISTS idx_unified_multiembeddings_document_id ON unified_multiembeddings(document_id)",
            "CREATE INDEX IF NOT EXISTS idx_unified_multiembeddings_embed_source_id ON unified_multiembeddings(embed_source_id)",
            "CREATE INDEX IF NOT EXISTS idx_unified_multiembeddings_model_name ON unified_multiembeddings(model_name)",
            "CREATE INDEX IF NOT EXISTS idx_unified_multiembeddings_created_at ON unified_multiembeddings(created_at)"
        ])

        # Vector indices (these can take a long time to create)
        indices.extend([
            "CREATE INDEX IF NOT EXISTS idx_unified_multiembeddings_vector ON unified_multiembeddings USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)"
        ])

        # Legacy table indices
        indices.extend([
            # MedRxiv indices
            "CREATE INDEX IF NOT EXISTS idx_title_rx ON preprints(title)",
            "CREATE INDEX IF NOT EXISTS idx_abstract_fts ON preprints USING gin(to_tsvector('english', abstract))",
            "CREATE INDEX IF NOT EXISTS idx_category ON preprints(category)",
            "CREATE INDEX IF NOT EXISTS idx_summaries_publication_id ON summaries(publication_id)",

            # PubMed indices
            "CREATE INDEX IF NOT EXISTS idx_title_pm ON pubmed_articles(substring(title, 1, 2000))",
            "CREATE INDEX IF NOT EXISTS idx_abstract_fts_pm ON pubmed_articles USING gin(to_tsvector('english', left(abstract, 100000)))",
            "CREATE INDEX IF NOT EXISTS idx_authors_pm ON pubmed_articles(substring(authors, 1, 2000))",
            "CREATE INDEX IF NOT EXISTS idx_year_pm ON pubmed_articles(publication_year)",
            "CREATE INDEX IF NOT EXISTS idx_mesh_pm ON pubmed_articles(substring(mesh_terms, 1, 2000))",

            # Legacy embedding indices
            "CREATE INDEX IF NOT EXISTS idx_embeddings_source_id ON embeddings(source_id)",
            "CREATE INDEX IF NOT EXISTS idx_embeddings_document_id ON embeddings(document_id)",
            "CREATE INDEX IF NOT EXISTS idx_embeddings_document_ref_id ON embeddings(document_ref_id)",
            "CREATE INDEX IF NOT EXISTS idx_embeddings_vector ON embeddings USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)",

            # Legacy QA embedding indices
            "CREATE INDEX IF NOT EXISTS idx_qaembeddings_source_id ON qaembeddings(source_id)",
            "CREATE INDEX IF NOT EXISTS idx_qaembeddings_document_id ON qaembeddings(document_id)",
            "CREATE INDEX IF NOT EXISTS idx_qaembeddings_document_ref_id ON qaembeddings(document_ref_id)",
            "CREATE INDEX IF NOT EXISTS idx_qaembeddings_vector ON qaembeddings USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)"
        ])

        # Create all indices
        for index_query in indices:
            try:
                logger.debug(f"Creating index: {index_query}")
                self.execute(index_query)
            except Exception as e:
                logger.error(f"Error creating index: {e}")

        logger.info("All indices created")

    def create_baseline_database(self) -> None:
        """Create the baseline database schema."""
        # Check if tables already exist
        if self.check_if_tables_exist():
            if self.force:
                logger.warning("Tables already exist, but --force flag is set. Dropping all tables.")
                self.drop_all_tables()
            else:
                logger.error("Tables already exist. Use --force to drop and recreate them.")
                return

        # Set autocommit to True for creating extensions
        self.connection.autocommit = True

        try:
            # Create extensions (must be done outside a transaction)
            self.create_extensions()

            # Start a transaction for the rest of the operations
            self.connection.autocommit = False

            try:
                # Create migrations table
                self.create_migrations_table()

                # Create user tables
                self.create_user_tables()

                # Create document tables
                self.create_document_tables()

                # Create reading tracker tables
                self.create_reading_tracker_tables()

                # Create embedding tables
                self.create_embedding_tables()

                # Create legacy tables
                self.create_legacy_tables()

                # Create indices
                self.create_indices()

                # Commit the transaction
                self.connection.commit()
                logger.info("Baseline database created successfully")
            except Exception as e:
                # Roll back the transaction on error
                self.connection.rollback()
                logger.error(f"Error creating baseline database: {e}")
                raise
            finally:
                # Restore autocommit
                self.connection.autocommit = True
        except Exception as e:
            logger.error(f"Error creating extensions: {e}")
            raise

    def close(self) -> None:
        """Close the database connection."""
        if self.connection:
            self.connection.close()
            self.connection = None


def main():
    """Main function to execute when run as a script."""
    parser = argparse.ArgumentParser(description='Create baseline database schema')
    parser.add_argument('--force', action='store_true', help='Force recreation of tables (WARNING: This will delete all data)')
    parser.add_argument('--dotenv', help='Path to the .env file to use')
    args = parser.parse_args()

    # Get dotenv path from command line or environment variable
    dotenv_path = args.dotenv or os.environ.get('DOTENV_FILE')

    try:
        creator = BaselineDBCreator(force=args.force, dotenv_path=dotenv_path)
        creator.create_baseline_database()
        creator.close()
        return 0
    except Exception as e:
        logger.error(f"Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
