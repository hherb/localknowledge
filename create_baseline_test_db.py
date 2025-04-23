#!/usr/bin/env python3
"""
Script to create a baseline test database.

This script creates a baseline test database with all the tables and indices
needed for testing the application.
"""

import os
import sys
import logging
import psycopg2
from datetime import datetime
from typing import Dict, List, Optional, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import the basic_infrastructure module if available
try:
    from localknowledge.db.basic_infrastructure import load_environment, get_db_connection_params
    BASIC_INFRASTRUCTURE_AVAILABLE = True
except ImportError:
    BASIC_INFRASTRUCTURE_AVAILABLE = False
    from dotenv import load_dotenv

# Test database settings
TEST_ENV_FILE = ".env.test"


class BaselineTestDBCreator:
    """Class to create a baseline test database."""
    
    def __init__(self, force: bool = False):
        """
        Initialize the baseline test database creator.
        
        Args:
            force: Whether to force recreation of tables (WARNING: This will delete all data)
        """
        self.force = force
        self.connection = None
        
        # Load environment variables
        if os.path.exists(TEST_ENV_FILE):
            logger.info(f"Using environment file: {TEST_ENV_FILE}")
            if BASIC_INFRASTRUCTURE_AVAILABLE:
                load_environment(dotenv_path=TEST_ENV_FILE)
            else:
                from dotenv import load_dotenv
                load_dotenv(TEST_ENV_FILE)
        
        # Connect to the database
        self.connect()
    
    def connect(self):
        """Connect to the database."""
        if BASIC_INFRASTRUCTURE_AVAILABLE:
            connection_params = get_db_connection_params(dotenv_path=TEST_ENV_FILE)
        else:
            dbname = os.environ.get('POSTGRES_DB')
            user = os.environ.get('POSTGRES_USER', 'postgres')
            password = os.environ.get('POSTGRES_PASSWORD', '')
            host = os.environ.get('POSTGRES_HOST', 'localhost')
            port = os.environ.get('POSTGRES_PORT', '5432')
            
            connection_params = {
                'dbname': dbname,
                'user': user,
                'password': password,
                'host': host,
                'port': port
            }
        
        logger.info(f"Connecting to database {connection_params['dbname']} at {connection_params['host']}:{connection_params['port']}")
        self.connection = psycopg2.connect(**connection_params)
    
    def execute(self, query: str, params: Optional[tuple] = None) -> Optional[List[Dict[str, Any]]]:
        """
        Execute a SQL query.
        
        Args:
            query: SQL query to execute
            params: Query parameters
            
        Returns:
            List of dictionaries with query results, or None for non-SELECT queries
        """
        cursor = self.connection.cursor()
        try:
            cursor.execute(query, params)
            
            # For SELECT queries, return the results
            if query.strip().upper().startswith("SELECT"):
                columns = [desc[0] for desc in cursor.description]
                return [dict(zip(columns, row)) for row in cursor.fetchall()]
            
            return None
        except Exception as e:
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
    
    def drop_all_tables(self):
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
        
        # Set autocommit to True for dropping tables
        original_autocommit = self.connection.autocommit
        self.connection.autocommit = True
        
        try:
            # Drop all tables
            for row in result:
                table_name = row['tablename']
                logger.info(f"Dropping table {table_name}")
                self.execute(f"DROP TABLE IF EXISTS {table_name} CASCADE")
            
            logger.info("All tables dropped")
        finally:
            # Restore original autocommit setting
            self.connection.autocommit = original_autocommit
    
    def create_baseline_database(self):
        """Create the baseline database schema."""
        # Check if tables already exist
        if self.check_if_tables_exist():
            if self.force:
                logger.warning("Tables already exist, but --force flag is set. Dropping all tables.")
                self.drop_all_tables()
            else:
                logger.error("Tables already exist. Use --force to drop and recreate them.")
                return
        
        # Set autocommit to True for all operations
        original_autocommit = self.connection.autocommit
        self.connection.autocommit = True
        
        try:
            # Create version table
            logger.info("Creating version table")
            self.execute("""
            CREATE TABLE IF NOT EXISTS version (
                version INTEGER UNIQUE NOT NULL,
                migrated TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                migration_success BOOLEAN NOT NULL
            )
            """)
            
            # Insert initial version record
            logger.info("Inserting initial version record")
            self.execute("""
            INSERT INTO version (version, migrated, migration_success)
            VALUES (1, CURRENT_TIMESTAMP, TRUE)
            ON CONFLICT (version) DO NOTHING
            """)
            
            # Create users table
            logger.info("Creating users table")
            self.execute("""
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
            """)
            
            # Create user preferences table
            logger.info("Creating user preferences table")
            self.execute("""
            CREATE TABLE IF NOT EXISTS user_preferences (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                preference_key TEXT NOT NULL,
                preference_value TEXT,
                UNIQUE (user_id, preference_key)
            )
            """)
            
            # Create sources table
            logger.info("Creating sources table")
            self.execute("""
            CREATE TABLE IF NOT EXISTS sources (
                id SERIAL PRIMARY KEY,
                name TEXT UNIQUE NOT NULL,
                description TEXT,
                url TEXT,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
            """)
            
            # Create categories table
            logger.info("Creating categories table")
            self.execute("""
            CREATE TABLE IF NOT EXISTS categories (
                id SERIAL PRIMARY KEY,
                name TEXT UNIQUE NOT NULL,
                parent_id INTEGER REFERENCES categories(id),
                description TEXT,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
            """)
            
            # Create document table
            logger.info("Creating document table")
            self.execute("""
            CREATE TABLE IF NOT EXISTS document (
                id SERIAL PRIMARY KEY,
                source_id INTEGER REFERENCES sources(id),
                external_id TEXT NOT NULL,
                doi TEXT,
                title TEXT,
                abstract TEXT,
                category_id INTEGER REFERENCES categories(id),
                keywords TEXT[],
                augmented_keywords TEXT[],
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
            """)
            
            # Create document_keywords table
            logger.info("Creating document_keywords table")
            self.execute("""
            CREATE TABLE IF NOT EXISTS document_keywords (
                id SERIAL PRIMARY KEY,
                document_id INTEGER REFERENCES document(id) ON DELETE CASCADE,
                keyword TEXT NOT NULL,
                weight FLOAT,
                source TEXT,
                UNIQUE (document_id, keyword, source)
            )
            """)
            
            # Create tags table
            logger.info("Creating tags table")
            self.execute("""
            CREATE TABLE IF NOT EXISTS tags (
                id SERIAL PRIMARY KEY,
                document_id INTEGER REFERENCES document(id) ON DELETE CASCADE,
                user_id INTEGER REFERENCES users(id),
                tag TEXT NOT NULL,
                UNIQUE (document_id, user_id, tag)
            )
            """)
            
            # Create reading_records table
            logger.info("Creating reading_records table")
            self.execute("""
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
            """)
            
            # Create embedding_source table
            logger.info("Creating embedding_source table")
            self.execute("""
            CREATE TABLE IF NOT EXISTS embedding_source (
                id SERIAL PRIMARY KEY,
                name TEXT UNIQUE NOT NULL,
                description TEXT,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
            """)
            
            # Insert default embedding sources
            logger.info("Inserting default embedding sources")
            self.execute("""
            INSERT INTO embedding_source (name, description)
            VALUES
                ('abstract', 'Document abstract'),
                ('full_text', 'Full document text'),
                ('chunk', 'Document text chunk'),
                ('qa_pair', 'Question-answer pair')
            ON CONFLICT (name) DO NOTHING
            """)
            
            # Create unified_multiembeddings table
            logger.info("Creating unified_multiembeddings table")
            self.execute("""
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
            """)
            
            # Create legacy tables
            logger.info("Creating legacy tables")
            
            # Create preprints table (legacy MedRxiv table)
            self.execute("""
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
            """)
            
            # Create summaries table (legacy MedRxiv table)
            self.execute("""
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
            """)
            
            # Create pubmed_articles table (legacy PubMed table)
            self.execute("""
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
            """)
            
            # Create legacy embeddings table
            self.execute("""
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
            """)
            
            # Create legacy qaembeddings table
            self.execute("""
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
            """)
            
            # Create indices
            logger.info("Creating indices")
            
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
            
            # Vector indices
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
                    logger.info(f"Creating index: {index_query}")
                    self.execute(index_query)
                except Exception as e:
                    logger.error(f"Error creating index: {e}")
            
            logger.info("Baseline database created successfully")
        except Exception as e:
            logger.error(f"Error creating baseline database: {e}")
            raise
        finally:
            # Restore original autocommit setting
            self.connection.autocommit = original_autocommit
    
    def close(self):
        """Close the database connection."""
        if self.connection:
            self.connection.close()
            self.connection = None


def main():
    """Main function."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Create baseline test database')
    parser.add_argument('--force', action='store_true', help='Force recreation of tables (WARNING: This will delete all data)')
    args = parser.parse_args()
    
    try:
        creator = BaselineTestDBCreator(force=args.force)
        creator.create_baseline_database()
        creator.close()
        logger.info("Baseline test database created successfully")
        return 0
    except Exception as e:
        logger.error(f"Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
