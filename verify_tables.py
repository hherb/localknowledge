#!/usr/bin/env python3
"""
Script to verify that the unified_multiembeddings and embedding_source tables exist.
"""

import os
import sys
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Set timeout
os.environ['PGCONNECT_TIMEOUT'] = '5'
os.environ['PGTIMEOUT'] = '5'

# Get database connection parameters from environment variables
DB_HOST = os.getenv('POSTGRES_HOST', 'localhost')
DB_PORT = os.getenv('POSTGRES_PORT', '5432')
DB_NAME = os.getenv('POSTGRES_DB')
DB_USER = os.getenv('POSTGRES_USER', 'postgres')
DB_PASSWORD = os.getenv('POSTGRES_PASSWORD', '')

if not DB_NAME:
    print("Error: POSTGRES_DB environment variable must be set")
    sys.exit(1)

# Connect to the database
try:
    conn = psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    conn.autocommit = True
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    # Check if the tables exist
    cursor.execute("""
    SELECT EXISTS (
        SELECT FROM information_schema.tables
        WHERE table_schema = 'public'
        AND table_name = 'unified_multiembeddings'
    );
    """)
    unified_multiembeddings_exists = cursor.fetchone()[0]

    cursor.execute("""
    SELECT EXISTS (
        SELECT FROM information_schema.tables
        WHERE table_schema = 'public'
        AND table_name = 'embedding_source'
    );
    """)
    embedding_source_exists = cursor.fetchone()[0]

    print(f"unified_multiembeddings table exists: {unified_multiembeddings_exists}")
    print(f"embedding_source table exists: {embedding_source_exists}")

    # If the tables exist, get some information about them
    if unified_multiembeddings_exists:
        cursor.execute("SELECT COUNT(*) FROM unified_multiembeddings")
        count = cursor.fetchone()[0]
        print(f"unified_multiembeddings table has {count} rows")

        cursor.execute("""
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_name = 'unified_multiembeddings'
        ORDER BY ordinal_position
        """)
        columns = cursor.fetchall()
        print("unified_multiembeddings table columns:")
        for column in columns:
            print(f"  {column['column_name']}: {column['data_type']}")

    if embedding_source_exists:
        cursor.execute("SELECT COUNT(*) FROM embedding_source")
        count = cursor.fetchone()[0]
        print(f"embedding_source table has {count} rows")

        cursor.execute("SELECT id, name, description FROM embedding_source")
        sources = cursor.fetchall()
        print("embedding_source table rows:")
        for source in sources:
            print(f"  {source['id']}: {source['name']} - {source['description']}")

    # Close the connection
    cursor.close()
    conn.close()

    print("Verification completed successfully")

except Exception as e:
    print(f"Error: {e}")
    sys.exit(1)
